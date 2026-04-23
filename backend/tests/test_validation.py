from app.schemas import EntitySpan
from app.services.validation import ValidationContext, ValidationService


def test_validation_detects_pan_mismatch() -> None:
    service = ValidationService()
    result = service.validate(
        ValidationContext(
            form16={"PAN": "ABCDE1234F", "TAN": "MUMA12345B", "TDS": 85000, "GrossIncome": 1200000},
            form26as={"PAN": "ABCDE1234X", "TAN": "MUMA12345B", "TDS": 84950},
            extracted_entities=[EntitySpan(label="PAN", value="ABCDE1234F", confidence=0.98, source="regex")],
        )
    )

    assert result.is_valid is False
    assert any(issue.field == "PAN" for issue in result.issues)


def test_validation_accepts_matching_values() -> None:
    service = ValidationService()
    result = service.validate(
        ValidationContext(
            form16={"PAN": "ABCDE1234F", "TAN": "MUMA12345B", "TDS": 85000, "GrossIncome": 1200000},
            form26as={"PAN": "ABCDE1234F", "TAN": "MUMA12345B", "TDS": 85020},
            extracted_entities=[EntitySpan(label="PAN", value="ABCDE1234F", confidence=0.98, source="regex")],
        )
    )

    assert result.issues
    assert result.reconciled_fields["PAN"] == "ABCDE1234F"
