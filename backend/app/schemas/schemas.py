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


# ---------------------------------------------------------------------------
# AI Validation Schemas (Phase 2)
# ---------------------------------------------------------------------------

class AIValidationResult(BaseModel):
    """Result of AI validation for a single field."""
    field_name: str
    original_value: Any
    suggested_value: Optional[Any] = None
    confidence: float
    reasoning: str
    action: str = Field(..., description="Action to take: 'keep', 'correct', or 'flag'")


class AIValidationSummary(BaseModel):
    """Summary of AI validation results."""
    total_fields: int
    validated: int
    corrected: int
    flagged: int


class AIValidationResponse(BaseModel):
    """Complete AI validation response."""
    validations: List[AIValidationResult] = []
    corrections_applied: List[AIValidationResult] = []
    flags: List[AIValidationResult] = []
    summary: AIValidationSummary


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
    ai_validation: Optional[AIValidationResponse] = None
    optimization: Optional["TaxOptimizationResponse"] = Field(None, description="Tax optimization suggestions (Phase 3)")


# ---------------------------------------------------------------------------
# 7. POST /api/v1/validate-with-ai (AI validation endpoint)
# ---------------------------------------------------------------------------

class AIValidationRequest(BaseModel):
    extracted_fields: Dict[str, Any] = Field(..., description="Fields extracted by NER")
    ocr_text: str = Field(..., description="Original OCR text for context")
    enable_ai: bool = Field(True, description="Enable/disable AI validation")


# ---------------------------------------------------------------------------
# Generic error wrapper (used in exception handlers)
# ---------------------------------------------------------------------------

class ErrorResponse(BaseModel):
    detail: str
    status_code: int = 500


# ---------------------------------------------------------------------------
# 8. Tax Optimization Schemas (Phase 3)
# ---------------------------------------------------------------------------

class TaxOptimizationSuggestion(BaseModel):
    """Individual tax optimization suggestion."""
    category: str = Field(..., description="Category: 'deduction', 'investment', or 'regime'")
    section: Optional[str] = Field(None, description="Tax section (e.g., '80C', '80D')")
    priority: str = Field(..., description="Priority: 'high', 'medium', or 'low'")
    suggestion: str = Field(..., description="Human-readable suggestion text")
    reasoning: str = Field(..., description="Explanation of why this suggestion is beneficial")
    potential_savings: float = Field(..., description="Estimated tax savings in rupees")
    current_amount: Optional[float] = Field(None, description="Current amount claimed (if applicable)")
    max_limit: Optional[float] = Field(None, description="Maximum limit for this section")
    investment_type: Optional[str] = Field(None, description="Type of investment (ELSS, PPF, etc.)")
    amount: Optional[float] = Field(None, description="Recommended investment amount")


class RegimeComparison(BaseModel):
    """Comparison between old and new tax regimes."""
    old_regime_tax: float = Field(..., description="Total tax under old regime")
    new_regime_tax: float = Field(..., description="Total tax under new regime")
    recommended_regime: str = Field(..., description="Recommended regime: 'old' or 'new'")
    savings_amount: float = Field(..., description="Savings by choosing recommended regime")
    reasoning: str = Field(..., description="AI-generated reasoning for recommendation")
    comparison_details: Optional[Dict[str, Any]] = Field(None, description="Detailed breakdown of both regimes")


class TaxOptimizationResponse(BaseModel):
    """Complete tax optimization response."""
    regime_comparison: RegimeComparison
    suggestions: List[TaxOptimizationSuggestion] = []
    potential_savings: float = Field(..., description="Total potential savings from all suggestions")
    priority_actions: List[TaxOptimizationSuggestion] = Field([], description="Top priority actions")
    error: Optional[str] = Field(None, description="Error message if optimization partially failed")


class OptimizeTaxRequest(BaseModel):
    """Request for tax optimization endpoint."""
    validated_data: Dict[str, Any] = Field(..., description="Validated extracted data")
    tax_result: Dict[str, Any] = Field(..., description="Tax computation result")
    ocr_text: Optional[str] = Field("", description="Original OCR text for context")


# ---------------------------------------------------------------------------
# 9. API Key Management Schemas
# ---------------------------------------------------------------------------

class ApiKeyRequest(BaseModel):
    """Request to set user's API key."""
    api_key: str = Field(..., min_length=20, description="Groq API key")


class ApiKeyStatusResponse(BaseModel):
    """Response for API key status check."""
    configured: bool = Field(..., description="Whether an API key is configured")
    source: str = Field(..., description="Source of API key: 'user', 'server', or 'none'")
    model: Optional[str] = Field(None, description="Current Groq model being used")


class ApiKeyTestResponse(BaseModel):
    """Response for API key test."""
    valid: bool = Field(..., description="Whether the API key is valid")
    message: str = Field(..., description="Status message")
    model: Optional[str] = Field(None, description="Model used for testing")
