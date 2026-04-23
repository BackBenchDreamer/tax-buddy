from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Regime(str, Enum):
    old = "old"
    new = "new"


class DocumentUploadResponse(BaseModel):
    document_id: int
    filename: str
    document_type: str
    storage_path: str


class EntitySpan(BaseModel):
    label: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "hybrid"
    page: int | None = None
    bbox: list[float] | None = None


class ExtractionResult(BaseModel):
    document_id: int
    text: str
    normalized_text: str
    confidence: float = Field(ge=0.0, le=1.0)
    entities: list[EntitySpan]
    layout_metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    severity: str
    field: str
    message: str
    expected: str | None = None
    observed: str | None = None
    source_documents: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    is_valid: bool
    issues: list[ValidationIssue]
    reconciled_fields: dict[str, Any] = Field(default_factory=dict)


class TaxBreakdownItem(BaseModel):
    label: str
    amount: float
    explanation: str


class TaxComputationRequest(BaseModel):
    regime: Regime = Regime.new
    gross_income: float = 0.0
    deductions_80c: float = 0.0
    deductions_80d: float = 0.0
    tds: float = 0.0
    other_income: float = 0.0
    standard_deduction: float = 50000.0


class TaxComputationResult(BaseModel):
    regime: Regime
    gross_income: float
    total_deductions: float
    taxable_income: float
    tax_liability: float
    cess: float
    refund_payable: float
    breakdown: list[TaxBreakdownItem]
    assumptions: list[str]


class ITRGenerationResult(BaseModel):
    document_id: int
    json_path: str
    xml_path: str
    report_path: str
    payload: dict[str, Any]


class PipelineResponse(BaseModel):
    upload: DocumentUploadResponse
    extraction: ExtractionResult
    validation: ValidationResult
    tax: TaxComputationResult
    itr: ITRGenerationResult
