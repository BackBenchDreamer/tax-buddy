from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.schemas import ExtractionResult, PipelineResponse, Regime, TaxComputationRequest
from app.services.extraction import ExtractionService
from app.services.output import OutputService
from app.services.tax import IndianTaxEngine, TaxComputationContext
from app.services.validation import ValidationContext, ValidationService


@dataclass
class PipelineInputs:
    document_id: int
    file_path: Path
    form16: dict[str, Any]
    form26as: dict[str, Any]
    tax_request: TaxComputationRequest


class TaxFilingPipeline:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.extractor = ExtractionService(model_path=settings.ml_model_path)
        self.validator = ValidationService()
        self.tax_engine = IndianTaxEngine()
        self.output_service = OutputService()

    def run(self, inputs: PipelineInputs) -> PipelineResponse:
        extraction_artifact = self.extractor.extract(inputs.document_id, inputs.file_path)
        validation = self.validator.validate(
            ValidationContext(
                form16=inputs.form16,
                form26as=inputs.form26as,
                extracted_entities=extraction_artifact.extraction.entities,
            )
        )
        tax = self.tax_engine.compute(
            TaxComputationContext(
                request=self._build_tax_request(inputs.tax_request, extraction_artifact.extraction),
                validated_fields=validation.reconciled_fields,
            )
        )
        itr = self.output_service.generate(
            document_id=inputs.document_id,
            output_dir=self.settings.output_dir,
            extraction=extraction_artifact.extraction.model_dump(),
            validation=validation.model_dump(),
            tax=tax,
        )
        upload_response = {
            "document_id": inputs.document_id,
            "filename": inputs.file_path.name,
            "document_type": inputs.form16.get("document_type", "mixed"),
            "storage_path": str(inputs.file_path),
        }
        return PipelineResponse(
            upload=upload_response,  # type: ignore[arg-type]
            extraction=extraction_artifact.extraction,
            validation=validation,
            tax=tax,
            itr=itr,
        )

    def _build_tax_request(self, request: TaxComputationRequest, extraction: ExtractionResult) -> TaxComputationRequest:
        values = {entity.label: entity.value for entity in extraction.entities}
        gross_income = request.gross_income or self._as_float(values.get("GrossIncome")) or self._as_float(values.get("TaxableIncome")) or 0.0
        tds = request.tds or self._as_float(values.get("TDS")) or 0.0
        deduction_80c = request.deductions_80c or self._as_float(values.get("Section80C")) or 0.0
        deduction_80d = request.deductions_80d or self._as_float(values.get("Section80D")) or 0.0
        return request.model_copy(
            update={
                "gross_income": gross_income,
                "tds": tds,
                "deductions_80c": deduction_80c,
                "deductions_80d": deduction_80d,
            }
        )

    def _as_float(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", ""))
        except Exception:
            return None
