from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from app.core.database import get_db
from app.models.db_models import Document, ExtractionResult, TaxComputation as TaxComputationDB
from app.models.schemas import TaxComputationResponse, TaxBreakdown, TaxBracketStep, DeductionDetail, TaxRegime
from app.pipeline.tax_engine import compute_both_regimes, TaxResult
from app.pipeline.ner_extractor import ExtractionOutput, ExtractedEntity

router = APIRouter()


def _db_to_extraction(er: ExtractionResult) -> ExtractionOutput:
    output = ExtractionOutput()
    for k, v in er.entities.items():
        output.entities[k] = ExtractedEntity(value=v["value"], confidence=v["confidence"], source=v["source"])
    return output


def _result_to_breakdown(r: TaxResult) -> TaxBreakdown:
    return TaxBreakdown(
        gross_income=r.gross_income,
        deductions=[DeductionDetail(section=d.section, amount=d.claimed, capped_at=d.capped_at, allowed=d.allowed) for d in r.deductions],
        total_deductions=r.total_deductions,
        taxable_income=r.taxable_income,
        surcharge=r.surcharge,
        rebate_87a=r.rebate_87a,
        bracket_steps=[TaxBracketStep(slab=s.slab, income_in_slab=s.income_in_slab, rate=s.rate, tax=s.tax) for s in r.bracket_steps],
        tax_before_cess=r.tax_before_cess,
        cess_rate=r.cess_rate,
        cess=r.cess,
        total_tax=r.total_tax,
        tds_paid=r.tds_paid,
        refund_or_payable=r.refund_or_payable,
        refund_or_payable_label=r.refund_or_payable_label,
    )


@router.post("/compute-tax/{session_id}", response_model=TaxComputationResponse)
async def compute_tax(session_id: str, regime: TaxRegime = TaxRegime.new, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.session_id == session_id)
    result = await db.execute(stmt)
    docs = result.scalars().all()

    if not docs:
        raise HTTPException(status_code=404, detail="Session not found")

    # Prefer form16, fallback to first available
    extraction = None
    for doc in docs:
        er_stmt = select(ExtractionResult).where(ExtractionResult.document_id == doc.id)
        er_result = await db.execute(er_stmt)
        er = er_result.scalar_one_or_none()
        if er:
            extraction = _db_to_extraction(er)
            if doc.doc_type == "form16":
                break

    if not extraction:
        raise HTTPException(status_code=422, detail="No extraction results; run /extract first")

    both = compute_both_regimes(extraction)
    chosen = both[regime.value]

    db_tax = TaxComputationDB(
        session_id=session_id,
        regime=regime.value,
        gross_income=chosen.gross_income,
        total_deductions=chosen.total_deductions,
        taxable_income=chosen.taxable_income,
        tax_liability=chosen.tax_before_cess,
        cess=chosen.cess,
        total_tax=chosen.total_tax,
        tds_paid=chosen.tds_paid,
        refund_or_payable=chosen.refund_or_payable,
        breakdown={"steps": [{"slab": s.slab, "rate": s.rate, "tax": s.tax} for s in chosen.bracket_steps]},
    )
    db.add(db_tax)

    comparison = {
        "old": {"total_tax": both["old"].total_tax, "refund_or_payable": both["old"].refund_or_payable, "label": both["old"].refund_or_payable_label},
        "new": {"total_tax": both["new"].total_tax, "refund_or_payable": both["new"].refund_or_payable, "label": both["new"].refund_or_payable_label},
        "recommended": "old" if both["old"].total_tax < both["new"].total_tax else "new",
    }

    return TaxComputationResponse(
        session_id=session_id,
        regime=regime.value,
        breakdown=_result_to_breakdown(chosen),
        comparison=comparison,
    )
