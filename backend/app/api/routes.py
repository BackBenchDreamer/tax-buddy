"""
API routes — thin controllers that delegate ALL logic to service modules.

Endpoints
---------
POST /upload          – save an uploaded file
POST /extract         – OCR → NER
POST /validate        – cross-document validation
POST /compute-tax     – income tax computation
POST /generate-itr    – ITR JSON generation
POST /process         – end-to-end pipeline
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

# Service imports
from ml.ocr.ocr_service import OCRService
from ml.ner.ner_service import NERService
from app.services.validation_service import validate as run_validation
from app.services.tax_service import compute_tax

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Upload directory (created lazily)
# ---------------------------------------------------------------------------
UPLOAD_DIR = pathlib.Path("data/uploads")

router = APIRouter()


# ---------------------------------------------------------------------------
# Singleton-ish service holders (heavy models loaded once per worker)
# ---------------------------------------------------------------------------
_ocr_service: OCRService | None = None
_ner_service: NERService | None = None


def _get_ocr() -> OCRService:
    global _ocr_service
    if _ocr_service is None:
        log.info("Initialising OCRService …")
        _ocr_service = OCRService()
    return _ocr_service


def _get_ner() -> NERService:
    global _ner_service
    if _ner_service is None:
        log.info("Initialising NERService …")
        _ner_service = NERService()
    return _ner_service


# ====================================================================== #
# 1. POST /upload
# ====================================================================== #

@router.post(
    "/upload",
    response_model=FileUploadResponse,
    tags=["pipeline"],
    summary="Upload a PDF or image file",
)
async def upload_file(file: UploadFile = File(...)):
    """Accept a PDF/image and persist it under ``data/uploads/``."""

    allowed = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"}
    ext = pathlib.Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed))}",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    dest = UPLOAD_DIR / f"{file_id}{ext}"

    log.info("Uploading %s → %s", file.filename, dest)
    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    return FileUploadResponse(file_id=file_id, file_path=str(dest))


# ====================================================================== #
# 2. POST /extract   (OCR → NER)
# ====================================================================== #

@router.post(
    "/extract",
    response_model=ExtractResponse,
    tags=["pipeline"],
    summary="Run OCR + NER on a file",
)
async def extract(body: ExtractRequest):
    """Run the OCR → NER pipeline on an already-uploaded file."""

    fp = pathlib.Path(body.file_path)
    if not fp.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {fp}")

    # OCR
    log.info("[extract] Starting OCR for %s", fp)
    try:
        ocr_result = _get_ocr().extract(str(fp))
    except Exception as exc:
        log.exception("OCR failed")
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}") from exc

    raw_text: str = ocr_result.get("text", "")

    # NER
    log.info("[extract] Starting NER …")
    try:
        ner_result = _get_ner().extract(raw_text)
    except Exception as exc:
        log.exception("NER failed")
        raise HTTPException(status_code=500, detail=f"NER failed: {exc}") from exc

    return ExtractResponse(
        text=raw_text,
        entities=ner_result.get("entities", []),
    )


# ====================================================================== #
# 3. POST /validate
# ====================================================================== #

@router.post(
    "/validate",
    response_model=ValidationResponse,
    tags=["pipeline"],
    summary="Validate Form 16 vs Form 26AS",
)
async def validate_documents(body: ValidationRequest):
    """Cross-validate extracted entities from two documents."""

    log.info("[validate] Running validation engine …")
    try:
        result = run_validation(body.form16_data, body.form26as_data)
    except Exception as exc:
        log.exception("Validation failed")
        raise HTTPException(status_code=500, detail=f"Validation failed: {exc}") from exc

    return ValidationResponse(**result)


# ====================================================================== #
# 4. POST /compute-tax
# ====================================================================== #

@router.post(
    "/compute-tax",
    response_model=TaxResponse,
    tags=["pipeline"],
    summary="Compute income tax (old / new regime)",
)
async def compute_tax_endpoint(body: TaxRequest):
    """Compute income tax with full slab breakdown."""

    payload: Dict[str, Any] = {**body.data, "Regime": body.regime}

    log.info("[compute-tax] regime=%s", body.regime)
    try:
        result = compute_tax(payload)
    except Exception as exc:
        log.exception("Tax computation failed")
        raise HTTPException(
            status_code=500, detail=f"Tax computation failed: {exc}"
        ) from exc

    return TaxResponse(**result)


# ====================================================================== #
# 5. POST /generate-itr
# ====================================================================== #

@router.post(
    "/generate-itr",
    response_model=ITRResponse,
    tags=["itr"],
    summary="Generate ITR-1 JSON from validated data + tax result",
)
async def generate_itr(body: ITRRequest):
    """Assemble an ITR-1 (Sahaj) JSON structure."""

    vd = body.validated_data
    tr = body.tax_result

    log.info("[generate-itr] Building ITR-1 JSON …")

    itr = ITRResponse(
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

    return itr


# ====================================================================== #
# 6. POST /process   (END-TO-END)
# ====================================================================== #

@router.post(
    "/process",
    response_model=ProcessResponse,
    tags=["pipeline"],
    summary="End-to-end: upload → OCR → NER → validate → tax",
)
async def process_pipeline(file: UploadFile = File(...)):
    """
    Single endpoint that runs the **full pipeline**:

    1. Save uploaded file
    2. OCR
    3. NER
    4. Validation (against a mock Form 26AS)
    5. Tax computation (old regime by default)
    """

    # ---- Step 1: Upload ----
    upload_resp = await upload_file(file)
    file_path = upload_resp.file_path
    file_id = upload_resp.file_id
    log.info("[process] File saved — id=%s", file_id)

    # ---- Step 2: OCR ----
    log.info("[process] Running OCR …")
    try:
        ocr_result = _get_ocr().extract(file_path)
    except Exception as exc:
        log.exception("OCR stage failed")
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}") from exc

    raw_text: str = ocr_result.get("text", "")

    # ---- Step 3: NER ----
    log.info("[process] Running NER …")
    try:
        ner_result = _get_ner().extract(raw_text)
    except Exception as exc:
        log.exception("NER stage failed")
        raise HTTPException(status_code=500, detail=f"NER failed: {exc}") from exc

    entities = ner_result.get("entities", [])

    # Use entity_map directly from NERService (preserves floats + exact field names)
    # Falls back to rebuilding from list if entity_map not present
    entity_map: Dict[str, Any] = ner_result.get("entity_map") or {}
    if not entity_map:
        for ent in entities:
            lbl = ent.get("label", "")
            val = ent.get("value", "")
            if lbl and lbl not in entity_map:
                entity_map[lbl] = val

    log.info("[process] DEBUG — OCR text sample: %s", raw_text[:300])
    log.info("[process] DEBUG — NER entity_map: %s", entity_map)

    # ---- Step 4: Validation ----
    log.info("[process] Running validation …")
    form16_data = entity_map  # flat dict with exact validation keys

    # Mock Form 26AS — mirrors Form 16 data (real impl would parse a separate doc)
    form26as_data = {
        "PAN":            entity_map.get("PAN", ""),
        "TAN":            entity_map.get("TAN", ""),
        "TDS":            entity_map.get("TDS", 0),
        "AssessmentYear": entity_map.get("AssessmentYear", ""),
    }

    log.info("[process] DEBUG — form16_data keys: %s", list(form16_data.keys()))
    log.info("[process] DEBUG — form26as_data: %s", form26as_data)

    try:
        val_result = run_validation(form16_data, form26as_data)
    except Exception as exc:
        log.exception("Validation stage failed")
        val_result = {"status": "error", "score": 0, "issues": []}

    log.info("[process] DEBUG — validation result: status=%s score=%s",
             val_result.get('status'), val_result.get('score'))

    # ---- Step 5: Tax computation ----
    log.info("[process] Running tax computation …")
    gross   = _to_float(entity_map.get("GrossSalary", 0))
    taxable = _to_float(entity_map.get("TaxableIncome", 0))
    deductions = gross - taxable if gross and taxable else 0
    tds = _to_float(entity_map.get("TDS", 0))

    log.info("[process] DEBUG — tax inputs: gross=%.0f taxable=%.0f deductions=%.0f tds=%.0f",
             gross, taxable, deductions, tds)

    tax_input = {
        "GrossSalary": gross,
        "Deductions":  deductions,
        "TDS":         tds,
        "Regime":      "old",
    }

    try:
        tax_result = compute_tax(tax_input)
    except Exception as exc:
        log.exception("Tax computation stage failed")
        tax_result = None

    return ProcessResponse(
        file_id=file_id,
        text=raw_text,
        entities=entities,
        validation=val_result if val_result else None,
        tax=tax_result if tax_result else None,
    )


# ---------------------------------------------------------------------------
# Health check (kept from the original endpoints.py)
# ---------------------------------------------------------------------------

@router.get("/system/health", tags=["health"], summary="Health check")
async def health_check():
    return {"status": "ok", "message": "AI Tax Filing System is up and running"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_float(val: Any) -> float:
    """Safely coerce a value to float."""
    if val is None:
        return 0.0
    try:
        cleaned = str(val).replace(",", "")
        return float(cleaned)
    except (TypeError, ValueError):
        return 0.0
