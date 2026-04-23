"""
Cross-document validation engine.
Reconciles Form 16 vs Form 26AS data and detects mismatches.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from loguru import logger
from app.pipeline.ner_extractor import ExtractionOutput


@dataclass
class MismatchItem:
    field: str
    doc1_value: Any
    doc2_value: Any
    severity: str  # error | warning
    message: str


@dataclass
class ValidationResult:
    status: str  # passed | warnings | failed
    mismatches: list[MismatchItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not any(m.severity == "error" for m in self.mismatches)


TOLERANCE = 1.0  # ₹1 tolerance for float comparison


def _get_val(extraction: ExtractionOutput, field: str) -> Optional[Any]:
    e = extraction.entities.get(field)
    return e.value if e else None


def validate(extractions: dict[str, ExtractionOutput]) -> ValidationResult:
    """
    extractions: {"form16": ExtractionOutput, "form26as": ExtractionOutput, ...}
    """
    mismatches: list[MismatchItem] = []
    warnings: list[str] = []

    f16 = extractions.get("form16")
    f26 = extractions.get("form26as")

    if not f16:
        warnings.append("Form 16 not uploaded; partial validation only.")
    if not f26:
        warnings.append("Form 26AS not uploaded; partial validation only.")

    if f16 and f26:
        # PAN check
        pan16 = _get_val(f16, "pan")
        pan26 = _get_val(f26, "pan")
        if pan16 and pan26 and pan16 != pan26:
            mismatches.append(MismatchItem(
                field="pan",
                doc1_value=pan16,
                doc2_value=pan26,
                severity="error",
                message=f"PAN mismatch: Form 16 has {pan16}, Form 26AS has {pan26}.",
            ))

        # TAN check
        tan16 = _get_val(f16, "tan")
        tan26 = _get_val(f26, "tan")
        if tan16 and tan26 and tan16 != tan26:
            mismatches.append(MismatchItem(
                field="tan",
                doc1_value=tan16,
                doc2_value=tan26,
                severity="error",
                message=f"TAN mismatch: Form 16 has {tan16}, Form 26AS has {tan26}.",
            ))

        # TDS reconciliation
        tds16 = _get_val(f16, "tds_deducted")
        tds26 = _get_val(f26, "tds_deposited")
        if tds16 is not None and tds26 is not None:
            diff = abs(float(tds16) - float(tds26))
            if diff > TOLERANCE:
                severity = "error" if diff > 100 else "warning"
                mismatches.append(MismatchItem(
                    field="tds",
                    doc1_value=tds16,
                    doc2_value=tds26,
                    severity=severity,
                    message=f"TDS discrepancy of ₹{diff:.2f}: Form 16 shows ₹{tds16}, Form 26AS shows ₹{tds26}.",
                ))

        # Income check (gross salary)
        sal16 = _get_val(f16, "gross_salary")
        sal26 = _get_val(f26, "gross_salary")
        if sal16 is not None and sal26 is not None:
            diff = abs(float(sal16) - float(sal26))
            if diff > TOLERANCE:
                mismatches.append(MismatchItem(
                    field="gross_salary",
                    doc1_value=sal16,
                    doc2_value=sal26,
                    severity="warning",
                    message=f"Gross salary difference of ₹{diff:.2f} between Form 16 and Form 26AS.",
                ))

    # Single-document sanity checks
    for doc_type, extraction in extractions.items():
        if extraction is None:
            continue
        pan = _get_val(extraction, "pan")
        if pan and (len(pan) != 10 or not pan.isalnum()):
            warnings.append(f"[{doc_type}] PAN '{pan}' may be incorrectly extracted.")

        tds = _get_val(extraction, "tds_deducted")
        gross = _get_val(extraction, "gross_salary")
        if tds and gross:
            if float(tds) > float(gross) * 0.4:
                warnings.append(f"[{doc_type}] TDS (₹{tds}) appears unusually high relative to gross salary (₹{gross}).")

    errors = [m for m in mismatches if m.severity == "error"]
    if errors:
        status = "failed"
    elif mismatches or warnings:
        status = "warnings"
    else:
        status = "passed"

    return ValidationResult(status=status, mismatches=mismatches, warnings=warnings)
