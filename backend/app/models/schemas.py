from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum

class DocType(str, Enum):
    form16 = "form16"
    form26as = "form26as"
    other = "other"

class TaxRegime(str, Enum):
    old = "old"
    new = "new"

class UploadResponse(BaseModel):
    session_id: str
    document_id: int
    filename: str
    doc_type: str
    status: str

class EntityField(BaseModel):
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = "ner"  # ner | regex | heuristic

class ExtractedEntities(BaseModel):
    pan: Optional[EntityField] = None
    tan: Optional[EntityField] = None
    employee_name: Optional[EntityField] = None
    employer_name: Optional[EntityField] = None
    assessment_year: Optional[EntityField] = None
    financial_year: Optional[EntityField] = None
    gross_salary: Optional[EntityField] = None
    basic_salary: Optional[EntityField] = None
    hra: Optional[EntityField] = None
    special_allowance: Optional[EntityField] = None
    section_80c: Optional[EntityField] = None
    section_80d: Optional[EntityField] = None
    section_80e: Optional[EntityField] = None
    section_80g: Optional[EntityField] = None
    standard_deduction: Optional[EntityField] = None
    tds_deducted: Optional[EntityField] = None
    tds_deposited: Optional[EntityField] = None
    net_taxable_income: Optional[EntityField] = None
    extra_fields: dict[str, EntityField] = {}

class ExtractionResponse(BaseModel):
    document_id: int
    session_id: str
    ocr_confidence: float
    ner_confidence: float
    entities: ExtractedEntities
    raw_text_preview: str

class MismatchItem(BaseModel):
    field: str
    doc1_value: Any
    doc2_value: Any
    severity: str  # error | warning
    message: str

class ValidationResponse(BaseModel):
    session_id: str
    status: str
    mismatches: list[MismatchItem]
    warnings: list[str]
    is_valid: bool

class TaxBracketStep(BaseModel):
    slab: str
    income_in_slab: float
    rate: float
    tax: float

class DeductionDetail(BaseModel):
    section: str
    amount: float
    capped_at: Optional[float] = None
    allowed: float

class TaxBreakdown(BaseModel):
    gross_income: float
    deductions: list[DeductionDetail]
    total_deductions: float
    taxable_income: float
    surcharge: float
    rebate_87a: float
    bracket_steps: list[TaxBracketStep]
    tax_before_cess: float
    cess_rate: float
    cess: float
    total_tax: float
    tds_paid: float
    refund_or_payable: float
    refund_or_payable_label: str

class TaxComputationResponse(BaseModel):
    session_id: str
    regime: str
    breakdown: TaxBreakdown
    comparison: Optional[dict] = None  # old vs new comparison

class ITRGenerateResponse(BaseModel):
    session_id: str
    itr_type: str
    json_url: str
    xml_url: str
    pdf_url: str
