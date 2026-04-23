"""
Smoke tests for the core pipeline services.

Run with:  cd backend && python -m pytest tests/ -v
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from ml.ner.regex_utils import extract_fields

SAMPLE_TEXT = """
Certificate Number: FBRCELA
TAN of Employer: MUMS15654C
PAN of Employee: BIGPP1846N
Assessment Year: 2023-24
SIEMENS TECHNOLOGY AND SERVICES PRIVATE LIMITED
Gross total income (6+8) | 751585.00
Total taxable income (9-11) 604280.00
Net tax payable (17-18) 34690.00
Total deduction under section 80C, 80CCC and 80CCD(1) 147305.00
"""


def test_pan_extraction():
    fields = extract_fields(SAMPLE_TEXT)
    assert fields.get("PAN") == "BIGPP1846N"


def test_tan_extraction():
    fields = extract_fields(SAMPLE_TEXT)
    assert fields.get("TAN") == "MUMS15654C"


def test_assessment_year():
    fields = extract_fields(SAMPLE_TEXT)
    assert fields.get("AssessmentYear") == "2023-24"


def test_gross_salary():
    fields = extract_fields(SAMPLE_TEXT)
    assert fields.get("GrossSalary") == 751585.0


def test_taxable_income():
    fields = extract_fields(SAMPLE_TEXT)
    assert fields.get("TaxableIncome") == 604280.0


def test_tds():
    fields = extract_fields(SAMPLE_TEXT)
    assert fields.get("TDS") == 34690.0


def test_section80c():
    fields = extract_fields(SAMPLE_TEXT)
    assert fields.get("Section80C") == 147305.0


def test_tax_engine():
    from app.services.tax_service import compute_tax
    result = compute_tax({
        "GrossSalary": 751585.0,
        "Deductions": 147305.0,
        "TDS": 34690.0,
        "Regime": "old",
    })
    assert result["total_tax"] >= 0
    assert result["taxable_income"] == 604280.0
