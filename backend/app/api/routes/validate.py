from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from app.core.database import get_db
from app.models.db_models import Document, ExtractionResult, ValidationResult as ValidationResultDB
from app.models.schemas import ValidationResponse, MismatchItem
from app.pipeline.validator import validate, ExtractionOutput
from app.pipeline.ner_extractor import ExtractedEntity

router = APIRouter()


def _db_to_extraction(er: ExtractionResult) -> ExtractionOutput:
    output = ExtractionOutput()
    for k, v in er.entities.items():
        output.entities[k] = ExtractedEntity(
            value=v["value"], confidence=v["confidence"], source=v["source"]
        )
    return output


@router.post("/validate/{session_id}", response_model=ValidationResponse)
async def validate_session(session_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.session_id == session_id)
    result = await db.execute(stmt)
    docs = result.scalars().all()

    if not docs:
        raise HTTPException(status_code=404, detail="No documents found for session")

    extractions: dict[str, ExtractionOutput] = {}
    for doc in docs:
        er_stmt = select(ExtractionResult).where(ExtractionResult.document_id == doc.id)
        er_result = await db.execute(er_stmt)
        er = er_result.scalar_one_or_none()
        if er:
            extractions[doc.doc_type] = _db_to_extraction(er)

    if not extractions:
        raise HTTPException(status_code=422, detail="No extraction results found; run /extract first")

    val_result = validate(extractions)

    db_val = ValidationResultDB(
        session_id=session_id,
        status=val_result.status,
        mismatches=[{"field": m.field, "doc1_value": m.doc1_value, "doc2_value": m.doc2_value,
                     "severity": m.severity, "message": m.message} for m in val_result.mismatches],
        warnings=val_result.warnings,
    )
    db.add(db_val)

    return ValidationResponse(
        session_id=session_id,
        status=val_result.status,
        mismatches=[MismatchItem(**{"field": m.field, "doc1_value": m.doc1_value,
                                    "doc2_value": m.doc2_value, "severity": m.severity,
                                    "message": m.message}) for m in val_result.mismatches],
        warnings=val_result.warnings,
        is_valid=val_result.is_valid,
    )
