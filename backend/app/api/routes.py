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
    import asyncio

    print("[DEBUG] START /process endpoint")

    async def run_pipeline_with_timeout():
        try:
            # ── Upload ────────────────────────────────────────────────────────────
            print("[DEBUG] START UPLOAD")
            upload_resp = await upload_file(file)
            file_path = upload_resp.file_path
            file_id   = upload_resp.file_id
            log.info("[Process] File saved — id=%s", file_id)
            print("[DEBUG] END UPLOAD")

            # ── OCR ───────────────────────────────────────────────────────────────
            print("[DEBUG] START OCR")
            log.info("[Process] OCR starting …")
            try:
                ocr_result = _get_ocr().extract(file_path)
                raw_text: str = ocr_result.get("text", "")
                log.info("[Process] OCR complete — %d chars, avg_conf=%.3f",
                         len(raw_text), ocr_result.get("average_confidence", 0))
            except Exception as exc:
                log.error("[Process] OCR failed: %s", exc)
                raise HTTPException(status_code=500, detail=str(_structured_error("OCR", str(exc))))
            print("[DEBUG] END OCR")

            # ── NER ───────────────────────────────────────────────────────────────
            print("[DEBUG] START NER")
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
            print("[DEBUG] END NER")

            log.debug("[Process] entity_map: %s", entity_map)

            # Persist extracted data
            try:
                save_extracted_data(file_id, entity_map)
            except Exception as exc:
                log.warning("[Process] Failed to persist extracted data: %s", exc)

            # ── Validation ────────────────────────────────────────────────────────
            print("[DEBUG] START VALIDATION")
            log.info("[Process] Running validation …")
            form26as_data = {
                "PAN":            entity_map.get("PAN", ""),
                "TAN":            entity_map.get("TAN", ""),
                "TDS":            entity_map.get("TDS", 0),
                "AssessmentYear": entity_map.get("AssessmentYear", ""),
            }
            try:
                val_result_dict = run_validation(entity_map, form26as_data)
                log.info("[Process] Validation — status=%s score=%s issues=%d",
                         val_result_dict.get("status"), val_result_dict.get("score"), len(val_result_dict.get("issues", [])))
            except Exception as exc:
                log.error("[Process] Validation stage failed: %s", exc)
                val_result_dict = {"status": "error", "score": 0, "issues": []}

            try:
                save_validation_result(file_id, val_result_dict)
            except Exception as exc:
                log.warning("[Process] Failed to persist validation result: %s", exc)
            print("[DEBUG] END VALIDATION")

            # ── Tax ───────────────────────────────────────────────────────────────
            print("[DEBUG] START TAX")
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

                print("[DEBUG] About to call compute_tax()")
                try:
                    print("[DEBUG] Inside tax computation try block")
                    tax_result = compute_tax({
                        "GrossSalary": gross,
                        "Deductions":  deductions,
                        "TDS":         tds,
                        "Regime":      regime,
                    })
                    print(f"[DEBUG] compute_tax returned: type={type(tax_result)}")

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
                    print(f"[ERROR TAX] {exc}")
                    import traceback
                    print(f"[ERROR TRACEBACK] {traceback.format_exc()}")
                    log.error("[Process] Tax computation failed: %s", exc)
                    tax_result = None
            print("[DEBUG] END TAX")

            if tax_result:
                try:
                    save_tax_result(file_id, tax_result, regime=regime)
                except Exception as exc:
                    log.warning("[Process] Failed to persist tax result: %s", exc)

            # Build response with proper error handling
            print("[DEBUG] BUILDING RESPONSE")
            try:
                print(f"[DEBUG] response params: file_id={file_id}, entities count={len(entities)}, val_result={type(val_result_dict).__name__}, tax_result={type(tax_result).__name__ if tax_result else 'None'}")
                response = ProcessResponse(
                    file_id=file_id,
                    text=raw_text,
                    entities=entities,
                    validation=val_result_dict,
                    tax=tax_result,
                )
                print("[DEBUG] RETURNING RESPONSE")
                return response
            except Exception as exc:
                print(f"[ERROR] Failed to create ProcessResponse: {exc}")
                import traceback
                print(f"[ERROR TRACEBACK] {traceback.format_exc()}")
                log.error("[Process] Failed to create response: %s", exc)
                # Return minimal valid response
                return ProcessResponse(
                    file_id=file_id,
                    text=raw_text,
                    entities=entities,
                    validation={"status": "error", "score": 0, "issues": []},
                    tax=None,
                )
        except HTTPException:
            raise
        except Exception as exc:
            print(f"[FATAL ERROR] {exc}")
            import traceback
            print(f"[FATAL TRACEBACK] {traceback.format_exc()}")
            log.error("[Process] FATAL ERROR: %s", exc)
            raise HTTPException(status_code=500, detail=str(_structured_error("process", str(exc))))

    # Run with timeout
    try:
        result = await asyncio.wait_for(run_pipeline_with_timeout(), timeout=120.0)
        return result
    except asyncio.TimeoutError:
        log.error("[Process] Pipeline timeout exceeded 120 seconds")
        print("[ERROR] Pipeline timeout!")
        raise HTTPException(status_code=504, detail="Pipeline processing timed out after 120 seconds")
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        print(f"[ERROR] Unexpected error: {exc}")
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


# ====================================================================== #
# 7. POST /generate-report   (PDF via reportlab)
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
# Health
# ====================================================================== #

@router.get("/system/health", tags=["health"])
async def health_check():
    return {"status": "ok", "service": settings.PROJECT_NAME}

