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
    AIValidationRequest,
    AIValidationResponse,
    ApiKeyRequest,
    ApiKeyStatusResponse,
    ApiKeyTestResponse,
    ExtractRequest,
    ExtractResponse,
    FileUploadResponse,
    ITRRequest,
    ITRResponse,
    OptimizeTaxRequest,
    ProcessResponse,
    TaxOptimizationResponse,
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
from ml.ner.regex_utils_26as import extract_fields_26as
from app.services.validation_service import validate as run_validation
from app.services.tax_service import compute_tax
from app.services.itr_service import generate_itr

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
# 2b. POST /extract-26as   (OCR → NER for Form 26AS)
# ====================================================================== #

@router.post("/extract-26as", response_model=ExtractResponse, tags=["pipeline"])
async def extract_26as(body: ExtractRequest):
    """OCR → NER pipeline for Form 26AS document."""
    fp = pathlib.Path(body.file_path)
    if not fp.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {fp}")

    # OCR
    log.info("[Extract-26AS] OCR starting: %s", fp)
    try:
        ocr_result = _get_ocr().extract(str(fp))
    except Exception as exc:
        log.error("[Extract-26AS] OCR failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(_structured_error("OCR", str(exc))))

    raw_text: str = ocr_result.get("text", "")
    log.info("[Extract-26AS] OCR done — %d chars", len(raw_text))

    # Extract Form 26AS fields using specialized regex
    log.info("[Extract-26AS] Extracting 26AS fields...")
    try:
        fields_26as = extract_fields_26as(raw_text)
        entities = [
            {"label": k, "value": str(v), "confidence": 0.95}
            for k, v in fields_26as.items()
            if k != "TDSEntries"  # Exclude nested structure from flat entity list
        ]
        log.info("[Extract-26AS] Extracted fields: %s", list(fields_26as.keys()))
    except Exception as exc:
        log.error("[Extract-26AS] Field extraction failed: %s", exc)
        entities = []

    return ExtractResponse(
        text=raw_text,
        entities=entities,
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

@router.post("/generate-itr", tags=["itr"])
async def generate_itr_endpoint(body: ITRRequest):
    """Generate ITR form (ITR-1 or ITR-4) with JSON, PDF, and prefill text."""
    vd = body.validated_data
    tr = body.tax_result
    log.info("[ITR] Generating ITR for PAN=%s", vd.get("PAN", "?"))
    
    try:
        from app.services.itr_service import generate_itr as gen_itr
        result = gen_itr(
            validated_data=vd,
            tax_result=tr,
            form_type=None,  # Auto-select
            presumptive_income=None,
        )
        log.info("[ITR] Generated %s", result["form_type"])
        return {
            "form_type": result["form_type"],
            "itr_json": result["itr_json"],
            "prefill_text": result["prefill_text"],
        }
    except Exception as exc:
        log.error("[ITR] Generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(_structured_error("ITR", str(exc))))


# ====================================================================== #
# 6. POST /validate-with-ai   (AI Validation)
# ====================================================================== #

@router.post("/validate-with-ai", response_model=AIValidationResponse, tags=["ai"])
async def validate_with_ai(body: AIValidationRequest):
    """
    Validate extracted fields using AI (Groq LLM).
    
    This endpoint uses AI to:
    - Validate employee vs employer name
    - Check PAN format and consistency
    - Verify amount calculations
    - Validate deduction totals
    
    Returns validation results with confidence scores and suggested corrections.
    """
    log.info("[AI-Validate] Starting AI validation for %d fields", len(body.extracted_fields))
    
    try:
        from app.services.ai_validation_service import validate_extracted_fields
        
        result = await validate_extracted_fields(
            extracted_fields=body.extracted_fields,
            ocr_text=body.ocr_text,
            enable_ai=body.enable_ai
        )
        
        log.info("[AI-Validate] Completed: %d validations, %d corrections, %d flags",
                 result["summary"]["validated"],
                 result["summary"]["corrected"],
                 result["summary"]["flagged"])
        
        return AIValidationResponse(**result)
        
    except Exception as exc:
        log.error("[AI-Validate] Validation failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=str(_structured_error("AI-Validation", str(exc)))
        )


# ====================================================================== #
# 7. POST /optimize-tax   (Tax Optimization with AI)
# ====================================================================== #

@router.post("/optimize-tax", response_model=TaxOptimizationResponse, tags=["optimization"])
async def optimize_tax_endpoint(body: OptimizeTaxRequest):
    """
    Generate AI-powered tax optimization suggestions.
    
    Analyzes the taxpayer's situation and provides:
    - Old vs New regime recommendation with reasoning
    - Deduction optimization suggestions
    - Investment recommendations for tax savings
    - Potential savings calculations
    
    Uses Groq LLM for intelligent, context-aware suggestions.
    """
    log.info("[TaxOptimization] Starting optimization analysis")
    
    try:
        from app.services.tax_optimization_service import optimize_tax
        
        result = await optimize_tax(
            validated_data=body.validated_data,
            tax_result=body.tax_result,
            ocr_text=body.ocr_text,
        )
        
        log.info("[TaxOptimization] Completed: %d suggestions, ₹%.0f potential savings",
                 len(result.get("suggestions", [])),
                 result.get("potential_savings", 0))
        
        return TaxOptimizationResponse(**result)
        
    except Exception as exc:
        log.error("[TaxOptimization] Optimization failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=str(_structured_error("TaxOptimization", str(exc)))
        )


# ====================================================================== #
# 8. POST /process   (END-TO-END)
# ====================================================================== #

@router.post("/process", response_model=ProcessResponse, tags=["pipeline"])
async def process_pipeline(file: UploadFile = File(...)):
    """
    Full pipeline in one request:
      Upload → OCR → NER → Validation → Tax

    PERFORMANCE CRITICAL:
    - <5s total
    - NO blocking I/O in main response path
    - Partial results on any error
    """
    import asyncio
    import time

    start_total = time.time()

    async def run_pipeline_with_timeout():
        try:
            # ── Upload ────────────────────────────────────────────────────────────
            start_time = time.time()
            upload_resp = await upload_file(file)
            file_path = upload_resp.file_path
            file_id   = upload_resp.file_id
            upload_elapsed = time.time() - start_time
            log.info("[Process] File saved — id=%s, time=%.3fs", file_id, upload_elapsed)

            # ── OCR ───────────────────────────────────────────────────────────────
            start_time = time.time()
            raw_text = ""
            try:
                ocr_result = _get_ocr().extract(file_path)
                raw_text: str = ocr_result.get("text", "")
                ocr_elapsed = time.time() - start_time
                log.info("[Process] OCR complete — %d chars, avg_conf=%.3f, time=%.3fs",
                         len(raw_text), ocr_result.get("average_confidence", 0), ocr_elapsed)

                if ocr_elapsed > 3.0:
                    log.warning("[Process] OCR took >3s (%.3fs)", ocr_elapsed)

            except Exception as exc:
                ocr_elapsed = time.time() - start_time
                log.error("[Process] OCR failed after %.3fs: %s", ocr_elapsed, exc)
                # Return partial response on OCR failure
                return ProcessResponse(
                    file_id=file_id,
                    text="",
                    entities=[],
                    validation={"status": "failed", "score": 0, "issues": [{"type": "OCR_FAILED", "message": str(exc), "severity": "high", "field": ""}]},
                    tax=None,
                )

            # ── NER ───────────────────────────────────────────────────────────────
            start_time = time.time()
            try:
                ner_result   = _get_ner().extract(raw_text)
                entities     = ner_result.get("entities", [])
                entity_map: Dict[str, Any] = ner_result.get("entity_map") or {}
                ner_elapsed = time.time() - start_time
                log.info("[Process] NER complete — fields: %s, time=%.3fs", list(entity_map.keys()), ner_elapsed)
            except Exception as exc:
                ner_elapsed = time.time() - start_time
                log.warning("[Process] NERService failed after %.3fs (%s) — using regex fallback", ner_elapsed, exc)
                entity_map = regex_extract_fields(raw_text)
                entities   = [
                    {"label": k, "value": str(v), "confidence": 0.9}
                    for k, v in entity_map.items()
                ]

            log.debug("[Process] entity_map: %s", entity_map)

            # ── AI Validation (Phase 2) ───────────────────────────────────────────
            start_time = time.time()
            ai_validation_result = None
            try:
                from app.services.ai_validation_service import (
                    validate_extracted_fields,
                    apply_corrections
                )
                
                # Run AI validation
                ai_validation_result = await validate_extracted_fields(
                    extracted_fields=entity_map,
                    ocr_text=raw_text,
                    enable_ai=True  # Can be made configurable via query param
                )
                
                ai_elapsed = time.time() - start_time
                log.info("[Process] AI Validation — validated=%d corrected=%d flagged=%d, time=%.3fs",
                         ai_validation_result["summary"]["validated"],
                         ai_validation_result["summary"]["corrected"],
                         ai_validation_result["summary"]["flagged"],
                         ai_elapsed)
                
                # Apply high-confidence corrections
                if ai_validation_result["corrections_applied"]:
                    entity_map = apply_corrections(entity_map, ai_validation_result)
                    log.info("[Process] Applied %d AI corrections to entity_map",
                             len(ai_validation_result["corrections_applied"]))
                
            except Exception as exc:
                ai_elapsed = time.time() - start_time
                log.warning("[Process] AI Validation failed after %.3fs (%s) — continuing without AI validation",
                           ai_elapsed, exc)
                ai_validation_result = None

            # ── Validation ────────────────────────────────────────────────────────
            start_time = time.time()
            form26as_data = {
                "PAN":            entity_map.get("PAN", ""),
                "TAN":            entity_map.get("TAN", ""),
                "TDS":            entity_map.get("TDS", 0),
                "AssessmentYear": entity_map.get("AssessmentYear", ""),
            }
            try:
                val_result_dict = run_validation(entity_map, form26as_data)
                val_elapsed = time.time() - start_time
                log.info("[Process] Validation — status=%s score=%s issues=%d, time=%.3fs",
                         val_result_dict.get("status"), val_result_dict.get("score"), len(val_result_dict.get("issues", [])), val_elapsed)
            except Exception as exc:
                val_elapsed = time.time() - start_time
                log.error("[Process] Validation stage failed after %.3fs: %s", val_elapsed, exc)
                val_result_dict = {"status": "error", "score": 0, "issues": []}

            # ── Tax ───────────────────────────────────────────────────────────────
            start_time = time.time()
            log.info("[Process] Computing tax …")
            gross      = _to_float(entity_map.get("GrossSalary", 0))
            taxable    = _to_float(entity_map.get("TaxableIncome", 0))
            deductions = gross - taxable if gross and taxable else 0.0
            tds        = _to_float(entity_map.get("TDS", 0))
            regime     = settings.DEFAULT_TAX_REGIME

            # Guard: do NOT compute tax on incomplete data
            missing_fields = []
            if gross <= 0:
                missing_fields.append("GrossSalary")
            if taxable <= 0:
                missing_fields.append("TaxableIncome")
            if tds <= 0:
                missing_fields.append("TDS")

            tax_result = None

            if missing_fields:
                log.warning(
                    "[Process] TAX SKIPPED — missing critical fields: %s. "
                    "Cannot compute reliable tax on incomplete extraction.",
                    missing_fields,
                )
            else:
                log.info("[Process] Tax inputs — gross=%.0f taxable=%.0f deductions=%.0f tds=%.0f regime=%s",
                         gross, taxable, deductions, tds, regime)

                # Sanity check: gross >= taxable
                if taxable > gross:
                    log.warning(
                        "[Process] ANOMALY: taxable (%.0f) > gross (%.0f) — "
                        "using taxable as gross for safety.",
                        taxable, gross,
                    )
                    gross = taxable
                    deductions = 0.0

                try:
                    tax_result = compute_tax({
                        "GrossSalary": gross,
                        "Deductions":  deductions,
                        "TDS":         tds,
                        "Regime":      regime,
                    })

                    # If the document itself has "TaxOnIncome" extracted, compare
                    doc_tax = _to_float(entity_map.get("TaxOnIncome", 0))
                    if doc_tax > 0:
                        computed = tax_result.get("base_tax", 0)
                        diff = abs(computed - doc_tax)
                        if diff > 10:
                            log.warning(
                                "[Process] TAX CROSS-CHECK: computed base_tax (%.0f) != "
                                "document TaxOnIncome (%.0f), diff=%.0f. "
                                "Document value may be more accurate.",
                                computed, doc_tax, diff,
                            )
                        else:
                            log.info(
                                "[Process] TAX CROSS-CHECK PASSED: computed=%.0f vs document=%.0f",
                                computed, doc_tax,
                            )

                    log.info("[Process] Tax done — total_tax=%.2f refund=%.2f",
                             tax_result.get("total_tax", 0), tax_result.get("refund_or_payable", 0))
                except Exception as exc:
                    log.error("[Process] Tax computation failed: %s", exc)
                    tax_result = None

            tax_elapsed = time.time() - start_time
            log.info("[Process] Tax completed in %.3fs", tax_elapsed)

            # ── Tax Optimization (Phase 3) ────────────────────────────────────────
            start_time = time.time()
            optimization_result = None
            
            # Only run optimization if tax computation succeeded
            if tax_result:
                try:
                    from app.services.tax_optimization_service import optimize_tax
                    
                    optimization_result = await optimize_tax(
                        validated_data=entity_map,
                        tax_result=tax_result,
                        ocr_text=raw_text,
                    )
                    
                    opt_elapsed = time.time() - start_time
                    log.info("[Process] Tax Optimization — %d suggestions, ₹%.0f savings, time=%.3fs",
                             len(optimization_result.get("suggestions", [])),
                             optimization_result.get("potential_savings", 0),
                             opt_elapsed)
                    
                except Exception as exc:
                    opt_elapsed = time.time() - start_time
                    log.warning("[Process] Tax Optimization failed after %.3fs (%s) — continuing without optimization",
                               opt_elapsed, exc)
                    optimization_result = None

            # ── BUILD RESPONSE (NO BLOCKING I/O) ──────────────────────────────────
            response = ProcessResponse(
                file_id=file_id,
                text=raw_text,
                entities=entities,
                validation=val_result_dict,
                tax=tax_result,
                ai_validation=ai_validation_result,
                optimization=optimization_result,
            )

            total_elapsed = time.time() - start_total
            log.info("[Process] Pipeline complete in %.3fs", total_elapsed)
            return response

        except HTTPException:
            raise
        except Exception as exc:
            log.error("[Process] FATAL ERROR: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(_structured_error("process", str(exc))))

    # Run with timeout
    try:
        result = await asyncio.wait_for(run_pipeline_with_timeout(), timeout=10.0)
        return result
    except asyncio.TimeoutError:
        log.error("[Process] Pipeline timeout exceeded 10 seconds")
        raise HTTPException(status_code=504, detail="Pipeline processing timed out after 10 seconds")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        log.error("[Process] Unexpected error: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ====================================================================== #
# POST /persist — Background persistence (optional, async-safe)
# ====================================================================== #

@router.post("/persist", tags=["persistence"])
async def persist_results(
    file_id: str,
    entity_map: Dict[str, Any] = {},
    validation_result: Dict[str, Any] = {},
    tax_result: Dict[str, Any] = None,
):
    """
    OPTIONAL background endpoint for deferred persistence.

    /process returns results instantly.
    Client can optionally call /persist to save to database.

    Returns immediately — actual writes happen async.
    """
    log.info("[Persist] Async save requested for file_id=%s", file_id)

    # Schedule background saves (fire and forget)
    async def background_persist():
        try:
            if entity_map:
                save_extracted_data(file_id, entity_map)
                log.debug("[Persist] Saved extracted data")
        except Exception as exc:
            log.warning("[Persist] Failed to save extracted data: %s", exc)

        try:
            if validation_result:
                save_validation_result(file_id, validation_result)
                log.debug("[Persist] Saved validation result")
        except Exception as exc:
            log.warning("[Persist] Failed to save validation result: %s", exc)

        try:
            if tax_result:
                save_tax_result(file_id, tax_result, regime=tax_result.get("regime", "old"))
                log.debug("[Persist] Saved tax result")
        except Exception as exc:
            log.warning("[Persist] Failed to save tax result: %s", exc)

    # Fire and forget
    import asyncio
    asyncio.create_task(background_persist())

    return {"status": "queued", "file_id": file_id}


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


def _build_pdf(body: _ReportRequest) -> bytes:
    """Build a valid PDF using reportlab SimpleDocTemplate."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontSize=18,
        spaceAfter=6 * mm,
        textColor=colors.HexColor("#1a1a2e"),
    )
    heading_style = ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
        textColor=colors.HexColor("#2d2d44"),
    )
    body_style = styles["BodyText"]
    small_style = ParagraphStyle(
        "Small",
        parent=styles["BodyText"],
        fontSize=8,
        textColor=colors.grey,
    )

    elements = []

    # Title
    elements.append(Paragraph("Tax Buddy — Tax Summary Report", title_style))
    elements.append(Spacer(1, 4 * mm))

    # -- Extracted Data --
    elements.append(Paragraph("Extracted Data", heading_style))
    data_rows = [["Field", "Value", "Confidence"]]
    for ent in body.entities:
        conf_str = f"{ent.confidence * 100:.0f}%"
        data_rows.append([ent.label, ent.value, conf_str])

    if len(data_rows) > 1:
        col_widths = [50 * mm, 70 * mm, 30 * mm]
        t = Table(data_rows, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8f0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)
    else:
        elements.append(Paragraph("No data extracted.", body_style))

    elements.append(Spacer(1, 4 * mm))

    # -- Validation --
    elements.append(Paragraph("Validation", heading_style))
    elements.append(Paragraph(
        f"Status: <b>{body.validation.status.upper()}</b> &nbsp;&nbsp; "
        f"Score: <b>{body.validation.score}/100</b>",
        body_style,
    ))
    if body.validation.issues:
        for iss in body.validation.issues:
            if isinstance(iss, dict):
                msg = iss.get("message", "")
                sev = iss.get("severity", "?")
                elements.append(Paragraph(f"• [{sev}] {msg}", body_style))

    elements.append(Spacer(1, 4 * mm))

    # -- Tax Computation --
    elements.append(Paragraph("Tax Computation", heading_style))
    tax = body.tax
    tax_keys = [
        ("Regime", "regime"),
        ("Gross Income", "gross_income"),
        ("Deductions", "deductions"),
        ("Taxable Income", "taxable_income"),
        ("Base Tax", "base_tax"),
        ("Rebate (87A)", "rebate"),
        ("Surcharge", "surcharge"),
        ("Cess (4%)", "cess"),
        ("Total Tax", "total_tax"),
        ("TDS Paid", "tds_paid"),
        ("Refund / Payable", "refund_or_payable"),
    ]
    tax_rows = [["Item", "Amount"]]
    for display, key in tax_keys:
        val = tax.get(key, "N/A")
        if isinstance(val, (int, float)):
            val_str = f"₹{val:,.2f}"
        else:
            val_str = str(val).capitalize()
        tax_rows.append([display, val_str])

    t2 = Table(tax_rows, colWidths=[60 * mm, 50 * mm], repeatRows=1)
    t2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8f0")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(t2)

    # -- Slab Breakdown --
    breakdown = tax.get("breakdown", [])
    if breakdown:
        elements.append(Spacer(1, 4 * mm))
        elements.append(Paragraph("Slab Breakdown", heading_style))
        slab_rows = [["Range", "Rate", "Taxable Amount", "Tax"]]
        for slab in breakdown:
            if isinstance(slab, dict):
                slab_rows.append([
                    slab.get("range", "?"),
                    f"{slab.get('rate', 0) * 100:.0f}%",
                    f"₹{slab.get('taxable_amount', 0):,.2f}",
                    f"₹{slab.get('tax', 0):,.2f}",
                ])
        t3 = Table(slab_rows, colWidths=[35 * mm, 20 * mm, 40 * mm, 35 * mm], repeatRows=1)
        t3.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e8f0")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(t3)

    # -- Footer --
    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "Generated by Tax Buddy · AI Tax Filing Assistant. "
        "For informational purposes only.",
        small_style,
    ))

    doc.build(elements)
    return buf.getvalue()


@router.post("/generate-report", tags=["report"])
async def generate_report(body: _ReportRequest):
    """Generate a valid PDF tax report using reportlab."""
    # Guard: don't generate if no data
    if not body.entities and not body.tax:
        raise HTTPException(
            status_code=400,
            detail="Cannot generate report: no extracted data or tax result available.",
        )

    log.info("[Report] Generating PDF — %d entities, tax=%s",
             len(body.entities), "present" if body.tax else "absent")

    try:
        pdf_bytes = _build_pdf(body)
    except Exception as exc:
        log.error("[Report] PDF generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    buf = io.BytesIO(pdf_bytes)
    buf.seek(0)

    log.info("[Report] PDF generated — %d bytes", len(pdf_bytes))

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=tax-buddy-report.pdf"},
    )


# ====================================================================== #
# 9. API Key Management
# ====================================================================== #

@router.post("/config/api-key", response_model=ApiKeyTestResponse, tags=["config"])
async def set_api_key(body: ApiKeyRequest):
    """
    Set user's Groq API key for the current session.
    
    The key is stored in thread-local storage and used for all AI operations
    in the current request context. It is NOT persisted to disk or database.
    
    Security:
    - Key is validated before acceptance
    - Key is never logged or exposed in responses
    - Key is cleared when session ends
    """
    log.info("[Config] Setting user API key")
    
    # Validate the API key by testing it
    try:
        from app.services.groq_service import test_api_key, set_user_api_key
        
        # Test the key first
        test_result = await test_api_key(body.api_key)
        
        if not test_result["valid"]:
            log.warning("[Config] Invalid API key provided")
            raise HTTPException(
                status_code=400,
                detail=test_result["message"]
            )
        
        # If valid, store it in thread-local storage
        set_user_api_key(body.api_key)
        
        log.info("[Config] User API key validated and stored")
        return ApiKeyTestResponse(
            valid=True,
            message="API key configured successfully",
            model=test_result["model"]
        )
        
    except HTTPException:
        raise
    except Exception as exc:
        log.error("[Config] Failed to set API key: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure API key: {str(exc)}"
        )


@router.get("/config/api-key/status", response_model=ApiKeyStatusResponse, tags=["config"])
async def get_api_key_status():
    """
    Check if an API key is configured and its source.
    
    Returns:
    - configured: Whether any API key is available
    - source: 'user' (session), 'server' (env var), or 'none'
    - model: Current Groq model being used
    """
    from app.services.groq_service import get_user_api_key
    
    user_key = get_user_api_key()
    server_key = settings.GROQ_API_KEY
    
    if user_key:
        source = "user"
        configured = True
    elif server_key:
        source = "server"
        configured = True
    else:
        source = "none"
        configured = False
    
    log.info("[Config] API key status check: source=%s", source)
    
    return ApiKeyStatusResponse(
        configured=configured,
        source=source,
        model=settings.GROQ_MODEL if configured else None
    )


@router.delete("/config/api-key", tags=["config"])
async def clear_api_key():
    """
    Clear user's API key from the current session.
    
    This removes the user-provided key from thread-local storage.
    Server-configured keys (from .env) are not affected.
    """
    from app.services.groq_service import clear_user_api_key, get_user_api_key
    
    had_key = get_user_api_key() is not None
    clear_user_api_key()
    
    if had_key:
        log.info("[Config] User API key cleared")
        return {"message": "API key cleared successfully"}
    else:
        log.info("[Config] No user API key to clear")
        return {"message": "No user API key was configured"}


@router.post("/config/api-key/test", response_model=ApiKeyTestResponse, tags=["config"])
async def test_api_key_endpoint(body: ApiKeyRequest):
    """
    Test an API key without storing it.
    
    Useful for validating a key before the user decides to save it.
    The key is NOT stored - only tested.
    """
    log.info("[Config] Testing API key")
    
    try:
        from app.services.groq_service import test_api_key
        
        result = await test_api_key(body.api_key)
        
        log.info("[Config] API key test result: valid=%s", result["valid"])
        return ApiKeyTestResponse(**result)
        
    except Exception as exc:
        log.error("[Config] API key test failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to test API key: {str(exc)}"
        )


# ====================================================================== #
# Health
# ====================================================================== #

@router.get("/system/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}

