from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from loguru import logger
from app.core.database import get_db
from app.core.config import settings
from app.models.db_models import Document, ExtractionResult
from app.models.schemas import ExtractionResponse, ExtractedEntities, EntityField
from app.pipeline.preprocessor import preprocess_document
from app.pipeline.ocr_engine import run_ocr_on_document
from app.pipeline.ner_extractor import HybridNERExtractor

router = APIRouter()

_extractor = HybridNERExtractor(
    model_path=settings.ner_model_path,
    model_name=settings.ner_model_name,
)


@router.post("/extract/{document_id}", response_model=ExtractionResponse)
async def extract_document(document_id: int, db: AsyncSession = Depends(get_db)):
    doc = await db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Preprocess
    pages, page_count = preprocess_document(doc.file_path)
    doc.page_count = page_count

    # OCR
    ocr_result = run_ocr_on_document(pages, settings.ocr_confidence_threshold)
    logger.info(f"OCR doc={document_id}: engine={ocr_result.engine_used}, conf={ocr_result.avg_confidence:.2f}")

    # NER
    ner_output = _extractor.extract(ocr_result.full_text)

    # Persist
    extraction = ExtractionResult(
        document_id=document_id,
        raw_text=ocr_result.full_text[:65535],
        entities={k: {"value": v.value, "confidence": v.confidence, "source": v.source}
                  for k, v in ner_output.entities.items()},
        ocr_confidence=ocr_result.avg_confidence,
        ner_confidence=ner_output.avg_ner_confidence,
    )
    db.add(extraction)
    doc.status = "processed"
    await db.flush()

    # Build response
    entities_dict = {}
    for k, v in ner_output.entities.items():
        ef = EntityField(value=v.value, confidence=v.confidence, source=v.source)
        entities_dict[k] = ef

    schema_entities = ExtractedEntities(
        pan=entities_dict.get("pan"),
        tan=entities_dict.get("tan"),
        employee_name=entities_dict.get("employee_name"),
        employer_name=entities_dict.get("employer_name"),
        assessment_year=entities_dict.get("assessment_year"),
        gross_salary=entities_dict.get("gross_salary"),
        basic_salary=entities_dict.get("basic_salary"),
        hra=entities_dict.get("hra"),
        special_allowance=entities_dict.get("special_allowance"),
        section_80c=entities_dict.get("section_80c"),
        section_80d=entities_dict.get("section_80d"),
        section_80e=entities_dict.get("section_80e"),
        section_80g=entities_dict.get("section_80g"),
        standard_deduction=entities_dict.get("standard_deduction"),
        tds_deducted=entities_dict.get("tds_deducted"),
        tds_deposited=entities_dict.get("tds_deposited"),
        net_taxable_income=entities_dict.get("net_taxable_income"),
        extra_fields={k: v for k, v in entities_dict.items()
                      if k not in ExtractedEntities.model_fields},
    )

    return ExtractionResponse(
        document_id=document_id,
        session_id=doc.session_id,
        ocr_confidence=ocr_result.avg_confidence,
        ner_confidence=ner_output.avg_ner_confidence,
        entities=schema_entities,
        raw_text_preview=ocr_result.full_text[:500],
    )
