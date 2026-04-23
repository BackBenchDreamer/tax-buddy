"""
Pydantic request / response schemas for all API endpoints.

Every endpoint has a dedicated Request and Response model
to enforce strict validation at the API boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared / reusable
# ---------------------------------------------------------------------------

class EntityItem(BaseModel):
    label: str
    value: str
    confidence: float


class ValidationIssueSchema(BaseModel):
    type: str
    message: str
    severity: str
    field: str


class SlabBreakdown(BaseModel):
    range: str
    taxable_amount: float
    rate: float
    tax: float


# ---------------------------------------------------------------------------
# 1. POST /upload
# ---------------------------------------------------------------------------

class FileUploadResponse(BaseModel):
    file_id: str
    file_path: str


# ---------------------------------------------------------------------------
# 2. POST /extract
# ---------------------------------------------------------------------------

class ExtractRequest(BaseModel):
    file_path: str = Field(..., description="Absolute or relative path to the uploaded file.")


class ExtractResponse(BaseModel):
    text: str
    entities: List[EntityItem] = []


# ---------------------------------------------------------------------------
# 3. POST /validate
# ---------------------------------------------------------------------------

class ValidationRequest(BaseModel):
    form16_data: Dict[str, Any]
    form26as_data: Dict[str, Any]


class ValidationResponse(BaseModel):
    status: str
    score: int
    issues: List[ValidationIssueSchema] = []


# ---------------------------------------------------------------------------
# 4. POST /compute-tax
# ---------------------------------------------------------------------------

class TaxRequest(BaseModel):
    data: Dict[str, Any] = Field(
        ...,
        description=(
            "Keys: GrossSalary, Deductions, TDS, and optionally TaxableIncome."
        ),
    )
    regime: str = Field(
        "old",
        description="Tax regime: 'old' or 'new'.",
    )


class TaxResponse(BaseModel):
    regime: str
    gross_income: float
    deductions: float
    taxable_income: float
    base_tax: float
    rebate: float
    surcharge: float
    cess: float
    total_tax: float
    tds_paid: float
    refund_or_payable: float
    breakdown: List[SlabBreakdown] = []


# ---------------------------------------------------------------------------
# 5. POST /generate-itr
# ---------------------------------------------------------------------------

class ITRRequest(BaseModel):
    validated_data: Dict[str, Any]
    tax_result: Dict[str, Any]


class ITRResponse(BaseModel):
    itr_form: str = "ITR-1 (Sahaj)"
    assessment_year: str = ""
    pan: str = ""
    name: str = ""
    gross_total_income: float = 0
    deductions: float = 0
    total_income: float = 0
    tax_payable: float = 0
    tds: float = 0
    refund_or_payable: float = 0
    verification_status: str = "pending"


# ---------------------------------------------------------------------------
# 6. POST /process  (end-to-end pipeline)
# ---------------------------------------------------------------------------

class ProcessResponse(BaseModel):
    file_id: str
    text: str = ""
    entities: List[EntityItem] = []
    validation: Optional[ValidationResponse] = None
    tax: Optional[TaxResponse] = None


# ---------------------------------------------------------------------------
# Generic error wrapper (used in exception handlers)
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
    status_code: int = 500
