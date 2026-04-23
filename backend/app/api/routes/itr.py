from pathlib import Path
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from app.core.database import get_db
from app.core.config import settings
from app.models.db_models import Document, ExtractionResult, TaxComputation as TaxComputationDB
from app.models.schemas import ITRGenerateResponse
from app.pipeline.itr_generator import generate_itr_json, generate_itr_xml, generate_pdf_summary
from app.pipeline.tax_engine import TaxResult, SlabStep, DeductionLine
from app.pipeline.ner_extractor import ExtractionOutput, ExtractedEntity

router = APIRouter()


def _db_to_extraction(er: ExtractionResult) -> ExtractionOutput:
    output = ExtractionOutput()
    for k, v in er.entities.items():
        output.entities[k] = ExtractedEntity(value=v["value"], confidence=v["confidence"], source=v["source"])
    return output


def _db_to_tax_result(tc: TaxComputationDB) -> TaxResult:
    steps = [SlabStep(slab=s["slab"], income_in_slab=0, rate=s["rate"], tax=s["tax"])
             for s in tc.breakdown.get("steps", [])]
    return TaxResult(
        regime=tc.regime,
        gross_income=tc.gross_income,
        deductions=[],
        total_deductions=tc.total_deductions,
        taxable_income=tc.taxable_income,
        bracket_steps=steps,
        tax_before_cess=tc.tax_liability,
        surcharge=0.0,
        rebate_87a=0.0,
        cess=tc.cess,
        total_tax=tc.total_tax,
        tds_paid=tc.tds_paid,
        refund_or_payable=tc.refund_or_payable,
        refund_or_payable_label="Refund" if tc.refund_or_payable > 0 and tc.tds_paid >= tc.total_tax else "Tax Payable",
    )


@router.post("/generate-itr/{session_id}", response_model=ITRGenerateResponse)
async def generate_itr(session_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.session_id == session_id)
    result = await db.execute(stmt)
    docs = result.scalars().all()
    if not docs:
        raise HTTPException(status_code=404, detail="Session not found")

    extraction = None
    for doc in docs:
        er_stmt = select(ExtractionResult).where(ExtractionResult.document_id == doc.id)
        er_result = await db.execute(er_stmt)
        er = er_result.scalar_one_or_none()
        if er:
            extraction = _db_to_extraction(er)
            if doc.doc_type == "form16":
                break

    tc_stmt = select(TaxComputationDB).where(TaxComputationDB.session_id == session_id).order_by(TaxComputationDB.id.desc())
    tc_result = await db.execute(tc_stmt)
    tc = tc_result.scalar_one_or_none()

    if not extraction or not tc:
        raise HTTPException(status_code=422, detail="Run /extract and /compute-tax first")

    tax_result = _db_to_tax_result(tc)
    out_dir = settings.output_dir / session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = generate_itr_json(extraction, tax_result, out_dir)
    xml_path = generate_itr_xml(extraction, tax_result, out_dir)
    pdf_path = generate_pdf_summary(extraction, tax_result, out_dir)

    base_url = f"/outputs/{session_id}"
    return ITRGenerateResponse(
        session_id=session_id,
        itr_type="ITR-1",
        json_url=f"{base_url}/{json_path.name}",
        xml_url=f"{base_url}/{xml_path.name}",
        pdf_url=f"{base_url}/{pdf_path.name}",
    )


@router.get("/outputs/{session_id}/{filename}")
async def download_output(session_id: str, filename: str):
    file_path = settings.output_dir / session_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path), filename=filename)
