ENTITY_LABELS = [
    "PAN",
    "TAN",
    "EmployerName",
    "EmployeeName",
    "SalaryBasic",
    "SalaryHRA",
    "SalarySpecialAllowance",
    "GrossIncome",
    "Section80C",
    "Section80D",
    "Section80CCD1B",
    "StandardDeduction",
    "TDS",
    "TaxableIncome",
    "HousePropertyIncome",
    "OtherIncome",
    "AssessmentYear",
    "FinancialYear",
]

FIELD_PATTERNS = {
    "PAN": r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    "TAN": r"\b[A-Z]{4}[0-9]{5}[A-Z]\b",
    "TDS": r"(?:TDS|TAX DEDUCTED AT SOURCE)[^\d]{0,20}([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})?)",
    "Section80C": r"(?:80C|SECTION 80C)[^\d]{0,20}([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})?)",
    "Section80D": r"(?:80D|SECTION 80D)[^\d]{0,20}([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})?)",
}
