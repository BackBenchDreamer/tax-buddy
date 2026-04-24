"""
API routes — thin controllers delegating ALL logic to service modules.

Production hardening applied
-----------------------------
* Every service call is wrapped in try/except with structured error responses
* NER fallback: if NERService fails → use regex_utils.extract_fields() directly
* entity_map used directly from NERService (preserves floats + exact field names)
* All pipeline results persisted to SQLite
* Structured INFO/WARNING/ERROR logging at every stage
* Service singletons loaded once per worker process (avoid reload per request)

Endpoints
---------
POST /upload          – save an uploaded file
POST /extract         – OCR → NER
POST /validate        – cross-document validation
POST /compute-tax     – income tax computation
POST /generate-itr    – ITR-1 JSON generation
POST /process         – end-to-end pipeline (recommended)
GET  /system/health   – health check
"""

from __future__ import annotations

import logging
import pathlib
import shutil
import uuid
from typing import Any, Dict

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.schemas import (
    ExtractRequest,
    ExtractResponse,
    FileUploadResponse,
    ITRRequest,
    ITRResponse,
    ProcessResponse,
    TaxRequest,
    TaxResponse,
    ValidationRequest,
    ValidationResponse,
)
from app.core.config import settings
from app.core.database import (
    save_document,
    save_extracted_data,
    save_validation_result,
    save_tax_result,
)
from ml.ocr.ocr_service import OCRService
from ml.ner.ner_service import NERService
from ml.ner.regex_utils import extract_fields as regex_extract_fields
from app.services.validation_service import validate as run_validation
from app.services.tax_service import compute_tax

log = logging.getLogger(__name__)

UPLOAD_DIR = pathlib.Path(settings.UPLOAD_DIR)
router = APIRouter()

# ---------------------------------------------------------------------------
# Service singletons — initialised once per worker
# ---------------------------------------------------------------------------
_ocr_service: OCRService | None = None
_ner_service: NERService | None = None


def _get_ocr() -> OCRService:
    global _ocr_service
    if _ocr_service is None:
        log.info("[Routes] Initialising OCRService …")
        _ocr_service = OCRService()
    return _ocr_service


def _get_ner() -> NERService:
    global _ner_service
    if _ner_service is None:
        log.info("[Routes] Initialising NERService …")
        _ner_service = NERService(
            use_transformer=settings.NER_USE_TRANSFORMER,
            model_name_or_path=settings.NER_TRANSFORMER_MODEL,
            confidence_threshold=settings.NER_CONFIDENCE_THRESHOLD,
        )
    return _ner_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_float(val: Any) -> float:
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", ""))
    except (TypeError, ValueError):
        return 0.0


def _structured_error(stage: str, detail: str) -> dict:
    return {"error": detail, "stage": stage}


# ====================================================================== #
# 1. POST /upload
# ====================================================================== #

@router.post("/upload", response_model=FileUploadResponse, tags=["pipeline"])
async def upload_file(file: UploadFile = File(...)):
    """Accept a PDF/image and persist it under data/uploads/."""
    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'.")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    dest = UPLOAD_DIR / f"{file_id}{ext}"

    log.info("[Upload] %s → %s (id=%s)", file.filename, dest, file_id)
    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    try:
        save_document(file_id, file.filename or "", str(dest))
    except Exception as exc:
        log.warning("[Upload] DB save failed (non-fatal): %s", exc)

    return FileUploadResponse(file_id=file_id, file_path=str(dest))


# ====================================================================== #
# 2. POST /extract   (OCR → NER)
# ====================================================================== #

@router.post("/extract", response_model=ExtractResponse, tags=["pipeline"])
async def extract(body: ExtractRequest):
    """OCR → NER pipeline on an already-uploaded file."""
    fp = pathlib.Path(body.file_path)
    if not fp.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {fp}")

    # OCR
    log.info("[Extract] OCR starting: %s", fp)
    try:
        ocr_result = _get_ocr().extract(str(fp))
    except Exception as exc:
        log.error("[Extract] OCR failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(_structured_error("OCR", str(exc))))

    raw_text: str = ocr_result.get("text", "")
    log.info("[Extract] OCR done — %d chars", len(raw_text))

    # NER
    log.info("[Extract] NER starting …")
    try:
        ner_result = _get_ner().extract(raw_text)
    except Exception as exc:
        log.warning("[Extract] NERService failed (%s) — using regex fallback", exc)
        ner_result = {"entities": [], "entity_map": regex_extract_fields(raw_text)}

    log.info("[Extract] NER done — fields: %s", list(ner_result.get("entity_map", {}).keys()))

    return ExtractResponse(
        text=raw_text,
        entities=ner_result.get("entities", []),
    )


# ====================================================================== #
# 3. POST /validate
# ====================================================================== #

@router.post("/validate", response_model=ValidationResponse, tags=["pipeline"])
async def validate_documents(body: ValidationRequest):
    """Cross-validate extracted entities from two documents."""
    log.info("[Validate] Running validation engine …")
    try:
        result = run_validation(body.form16_data, body.form26as_data)
    except Exception as exc:
        log.error("[Validate] Validation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(_structured_error("Validation", str(exc))))

    log.info("[Validate] Done — status=%s score=%s", result.get("status"), result.get("score"))
    return ValidationResponse(**result)


# ====================================================================== #
# 4. POST /compute-tax
# ====================================================================== #

@router.post("/compute-tax", response_model=TaxResponse, tags=["pipeline"])
async def compute_tax_endpoint(body: TaxRequest):
    """Compute income tax with full slab breakdown."""
    payload: Dict[str, Any] = {**body.data, "Regime": body.regime}
    log.info("[Tax] Computing — regime=%s", body.regime)
    try:
        result = compute_tax(payload)
    except Exception as exc:
        log.error("[Tax] Computation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(_structured_error("Tax", str(exc))))

    log.info("[Tax] Done — total_tax=%.2f", result.get("total_tax", 0))
    return TaxResponse(**result)


# ====================================================================== #
# 5. POST /generate-itr
# ====================================================================== #

@router.post("/generate-itr", response_model=ITRResponse, tags=["itr"])
async def generate_itr(body: ITRRequest):
    """Assemble an ITR-1 (Sahaj) JSON structure."""
    vd = body.validated_data
    tr = body.tax_result
    log.info("[ITR] Building ITR-1 JSON for PAN=%s", vd.get("PAN", "?"))
    return ITRResponse(
        itr_form="ITR-1 (Sahaj)",
        assessment_year=vd.get("AssessmentYear", ""),
        pan=vd.get("PAN", ""),
        name=vd.get("EmployeeName", vd.get("EmployerName", "")),
        gross_total_income=float(vd.get("GrossSalary", 0)),
        deductions=float(tr.get("deductions", 0)),
        total_income=float(tr.get("taxable_income", 0)),
        tax_payable=float(tr.get("total_tax", 0)),
        tds=float(tr.get("tds_paid", 0)),
        refund_or_payable=float(tr.get("refund_or_payable", 0)),
        verification_status="pending",
    )


# ====================================================================== #
# 6. POST /process   (END-TO-END)
# ====================================================================== #

@router.post("/process", response_model=ProcessResponse, tags=["pipeline"])
async def process_pipeline(file: UploadFile = File(...)):
    """
    Full pipeline in one request:
      Upload → OCR → NER → Validation → Tax → Persist
    """

    # ── Upload ────────────────────────────────────────────────────────────
    upload_resp = await upload_file(file)
    file_path = upload_resp.file_path
    file_id   = upload_resp.file_id
    log.info("[Process] File saved — id=%s", file_id)

    # ── OCR ───────────────────────────────────────────────────────────────
    log.info("[Process] OCR starting …")
    try:
        ocr_result = _get_ocr().extract(file_path)
        raw_text: str = ocr_result.get("text", "")
        log.info("[Process] OCR complete — %d chars, avg_conf=%.3f",
                 len(raw_text), ocr_result.get("average_confidence", 0))
    except Exception as exc:
        log.error("[Process] OCR failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(_structured_error("OCR", str(exc))))

    # ── NER ───────────────────────────────────────────────────────────────
    log.info("[Process] NER starting …")
    try:
        ner_result   = _get_ner().extract(raw_text)
        entities     = ner_result.get("entities", [])
        entity_map: Dict[str, Any] = ner_result.get("entity_map") or {}
        log.info("[Process] NER complete — fields: %s", list(entity_map.keys()))
    except Exception as exc:
        log.warning("[Process] NERService failed (%s) — falling back to regex-only", exc)
        entity_map = regex_extract_fields(raw_text)
        entities   = [
            {"label": k, "value": str(v), "confidence": 0.9}
            for k, v in entity_map.items()
        ]

    log.debug("[Process] entity_map: %s", entity_map)

    # Persist extracted data
    try:
        save_extracted_data(file_id, entity_map)
    except Exception as exc:
        log.warning("[Process] Failed to persist extracted data: %s", exc)

    # ── Validation ────────────────────────────────────────────────────────
    log.info("[Process] Running validation …")
    form26as_data = {
        "PAN":            entity_map.get("PAN", ""),
        "TAN":            entity_map.get("TAN", ""),
        "TDS":            entity_map.get("TDS", 0),
        "AssessmentYear": entity_map.get("AssessmentYear", ""),
    }
    try:
        val_result = run_validation(entity_map, form26as_data)
        log.info("[Process] Validation — status=%s score=%s issues=%d",
                 val_result.get("status"), val_result.get("score"), len(val_result.get("issues", [])))
    except Exception as exc:
        log.error("[Process] Validation stage failed: %s", exc)
        val_result = {"status": "error", "score": 0, "issues": [], "error": str(exc)}

    try:
        save_validation_result(file_id, val_result)
    except Exception as exc:
        log.warning("[Process] Failed to persist validation result: %s", exc)

    # ── Tax ───────────────────────────────────────────────────────────────
    log.info("[Process] Computing tax …")
    gross      = _to_float(entity_map.get("GrossSalary", 0))
    taxable    = _to_float(entity_map.get("TaxableIncome", 0))
    deductions = gross - taxable if gross and taxable else 0.0
    tds        = _to_float(entity_map.get("TDS", 0))
    regime     = settings.DEFAULT_TAX_REGIME

    log.info("[Process] Tax inputs — gross=%.0f taxable=%.0f deductions=%.0f tds=%.0f regime=%s",
             gross, taxable, deductions, tds, regime)

    try:
        tax_result = compute_tax({
            "GrossSalary": gross,
            "Deductions":  deductions,
            "TDS":         tds,
            "Regime":      regime,
        })
        log.info("[Process] Tax done — total_tax=%.2f refund=%.2f",
                 tax_result.get("total_tax", 0), tax_result.get("refund_or_payable", 0))
    except Exception as exc:
        log.error("[Process] Tax computation failed: %s", exc)
        tax_result = None

    if tax_result:
        try:
            save_tax_result(file_id, tax_result, regime=regime)
        except Exception as exc:
            log.warning("[Process] Failed to persist tax result: %s", exc)

    return ProcessResponse(
        file_id=file_id,
        text=raw_text,
        entities=entities,
        validation=val_result,
        tax=tax_result,
    )


# ====================================================================== #
# 7. POST /generate-report   (PDF-like downloadable report)
# ====================================================================== #

from pydantic import BaseModel as _BM
from fastapi.responses import StreamingResponse
import io

class _ReportEntity(_BM):
    label: str
    value: str
    confidence: float

class _ReportValidation(_BM):
    status: str
    score: int
    issues: list = []

class _ReportRequest(_BM):
    entities: list[_ReportEntity]
    validation: _ReportValidation
    tax: dict


@router.post("/generate-report", tags=["report"])
async def generate_report(body: _ReportRequest):
    """Generate a downloadable tax report as a text file (PDF placeholder).

    A production system would use reportlab or weasyprint;
    this generates a clean .txt report for demo purposes.
    """
    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("  TAX BUDDY — AI Tax Filing Report")
    lines.append("=" * 60)
    lines.append("")

    # Extracted data
    lines.append("EXTRACTED DATA")
    lines.append("-" * 40)
    for ent in body.entities:
        conf_pct = f"{ent.confidence * 100:.0f}%"
        lines.append(f"  {ent.label:20s} {ent.value:>20s}  ({conf_pct})")
    lines.append("")

    # Validation
    lines.append("VALIDATION")
    lines.append("-" * 40)
    lines.append(f"  Status: {body.validation.status.upper()}")
    lines.append(f"  Score:  {body.validation.score}/100")
    if body.validation.issues:
        for iss in body.validation.issues:
            if isinstance(iss, dict):
                lines.append(f"  ⚠ [{iss.get('severity', '?')}] {iss.get('message', '')}")
    lines.append("")

    # Tax
    lines.append("TAX COMPUTATION")
    lines.append("-" * 40)
    tax = body.tax
    for key in ["regime", "gross_income", "deductions", "taxable_income", "base_tax", "rebate", "surcharge", "cess", "total_tax", "tds_paid", "refund_or_payable"]:
        val = tax.get(key, "N/A")
        if isinstance(val, (int, float)):
            lines.append(f"  {key:25s} ₹{val:>12,.2f}")
        else:
            lines.append(f"  {key:25s} {val}")
    lines.append("")

    # Slab breakdown
    breakdown = tax.get("breakdown", [])
    if breakdown:
        lines.append("SLAB BREAKDOWN")
        lines.append("-" * 40)
        for slab in breakdown:
            if isinstance(slab, dict):
                lines.append(f"  {slab.get('range', '?'):15s} @{slab.get('rate', 0) * 100:5.1f}%  →  ₹{slab.get('tax', 0):>10,.2f}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("  Generated by Tax Buddy · AI Tax Filing Assistant")
    lines.append("  For informational purposes only.")
    lines.append("=" * 60)

    content = "\n".join(lines)
    buf = io.BytesIO(content.encode("utf-8"))
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=tax-buddy-report.txt"},
    )


# ====================================================================== #
# Health
# ====================================================================== #

@router.get("/system/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}
