from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.db import DocumentRecord, get_session
from app.schemas import DocumentUploadResponse, Regime, TaxComputationRequest
from app.services.extraction import ExtractionService
from app.services.pipeline import PipelineInputs, TaxFilingPipeline
from app.services.tax import IndianTaxEngine, TaxComputationContext
from app.services.validation import ValidationContext, ValidationService

router = APIRouter(prefix="/api", tags=["tax-buddy"])
settings = get_settings()
extractor = ExtractionService(model_path=settings.ml_model_path)
validator = ValidationService()
tax_engine = IndianTaxEngine()
pipeline = TaxFilingPipeline()


class ValidationPayload(BaseModel):
    form16: dict[str, Any] = Field(default_factory=dict)
    form26as: dict[str, Any] = Field(default_factory=dict)


class GenerateITRPayload(BaseModel):
    form16: dict[str, Any] = Field(default_factory=dict)
    form26as: dict[str, Any] = Field(default_factory=dict)
    tax_request: TaxComputationRequest = Field(default_factory=TaxComputationRequest)


class DocumentReference(BaseModel):
    document_id: int


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(file: UploadFile = File(...), document_type: str = "unknown") -> DocumentUploadResponse:
    if file.content_type not in {"application/pdf", "image/png", "image/jpeg", "image/tiff", "application/octet-stream"} and not file.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff")):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    destination = settings.upload_dir / file.filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large")
    destination.write_bytes(content)

    with get_session() as session:
        record = DocumentRecord(
            original_name=file.filename,
            document_type=document_type,
            storage_path=str(destination),
            content_type=file.content_type or "application/octet-stream",
        )
        session.add(record)
        session.flush()
        session.refresh(record)
        return DocumentUploadResponse(
            document_id=record.id,
            filename=record.original_name,
            document_type=record.document_type,
            storage_path=record.storage_path,
        )


@router.post("/extract/{document_id}")
def extract_document(document_id: int) -> dict[str, Any]:
    record = _get_document(document_id)
    artifact = extractor.extract(document_id, Path(record.storage_path))
    _persist_record(record, extracted_json=artifact.extraction.model_dump(), ocr_text=artifact.extraction.text, confidence=artifact.extraction.confidence)
    return artifact.extraction.model_dump()


@router.post("/validate/{document_id}")
def validate_document(document_id: int, payload: ValidationPayload) -> dict[str, Any]:
    record = _get_document(document_id)
    extraction = record.extracted_json or {}
    context = ValidationContext(form16=payload.form16, form26as=payload.form26as, extracted_entities=[_entity_from_json(entity) for entity in extraction.get("entities", [])])
    result = validator.validate(context)
    _persist_record(record, validation_json=result.model_dump())
    return result.model_dump()


@router.post("/compute-tax/{document_id}")
def compute_tax(document_id: int, payload: TaxComputationRequest) -> dict[str, Any]:
    record = _get_document(document_id)
    validation = record.validation_json or {}
    extraction = record.extracted_json or {}
    validated_fields = validation.get("reconciled_fields", {})
    context = TaxComputationContext(request=payload, validated_fields=validated_fields)
    if payload.gross_income == 0:
        payload = payload.model_copy(update={"gross_income": _float_from_entities(extraction.get("entities", []), "GrossIncome") or 0.0})
        context = TaxComputationContext(request=payload, validated_fields=validated_fields)
    result = tax_engine.compute(context)
    _persist_record(record, tax_json=result.model_dump())
    return result.model_dump()


@router.post("/generate-itr/{document_id}")
def generate_itr(document_id: int, payload: GenerateITRPayload) -> dict[str, Any]:
    record = _get_document(document_id)
    if not record.extracted_json:
        artifact = extractor.extract(document_id, Path(record.storage_path))
        _persist_record(record, extracted_json=artifact.extraction.model_dump(), ocr_text=artifact.extraction.text, confidence=artifact.extraction.confidence)
    validation = validator.validate(
        ValidationContext(
            form16=payload.form16,
            form26as=payload.form26as,
            extracted_entities=[_entity_from_json(entity) for entity in (record.extracted_json or {}).get("entities", [])],
        )
    )
    _persist_record(record, validation_json=validation.model_dump())
    tax_result = tax_engine.compute(
        TaxComputationContext(
            request=payload.tax_request,
            validated_fields=validation.reconciled_fields,
        )
    )
    output = pipeline.output_service.generate(
        document_id=document_id,
        output_dir=settings.output_dir,
        extraction=record.extracted_json or {},
        validation=validation.model_dump(),
        tax=tax_result,
    )
    _persist_record(record, tax_json=tax_result.model_dump())
    return output.model_dump()


@router.post("/pipeline/{document_id}")
def run_pipeline(document_id: int, payload: GenerateITRPayload) -> dict[str, Any]:
    record = _get_document(document_id)
    pipeline_inputs = PipelineInputs(
        document_id=document_id,
        file_path=Path(record.storage_path),
        form16=payload.form16,
        form26as=payload.form26as,
        tax_request=payload.tax_request,
    )
    response = pipeline.run(pipeline_inputs)
    _persist_record(
        record,
        ocr_text=response.extraction.text,
        extracted_json=response.extraction.model_dump(),
        validation_json=response.validation.model_dump(),
        tax_json=response.tax.model_dump(),
        confidence=response.extraction.confidence,
    )
    return response.model_dump()


@router.get("/documents/{document_id}")
def get_document(document_id: int) -> dict[str, Any]:
    record = _get_document(document_id)
    return {
        "document_id": record.id,
        "original_name": record.original_name,
        "document_type": record.document_type,
        "storage_path": record.storage_path,
        "ocr_text": record.ocr_text,
        "extracted_json": record.extracted_json,
        "validation_json": record.validation_json,
        "tax_json": record.tax_json,
        "confidence": record.confidence,
    }


def _get_document(document_id: int) -> DocumentRecord:
    with get_session() as session:
        record = session.scalar(select(DocumentRecord).where(DocumentRecord.id == document_id))
        if record is None:
            raise HTTPException(status_code=404, detail="Document not found")
        session.expunge(record)
        return record


def _persist_record(record: DocumentRecord, **updates: Any) -> None:
    with get_session() as session:
        stored = session.scalar(select(DocumentRecord).where(DocumentRecord.id == record.id))
        if stored is None:
            raise HTTPException(status_code=404, detail="Document not found")
        for key, value in updates.items():
            setattr(stored, key, value)


def _entity_from_json(entity: dict[str, Any]):
    from app.schemas import EntitySpan

    return EntitySpan(
        label=str(entity.get("label", "")),
        value=str(entity.get("value", "")),
        confidence=float(entity.get("confidence", 0.0)),
        source=str(entity.get("source", "hybrid")),
        page=entity.get("page"),
        bbox=entity.get("bbox"),
    )


def _float_from_entities(entities: list[dict[str, Any]], label: str) -> float | None:
    for entity in entities:
        if entity.get("label") == label:
            try:
                return float(str(entity.get("value", "0")).replace(",", ""))
            except Exception:
                return None
    return None
