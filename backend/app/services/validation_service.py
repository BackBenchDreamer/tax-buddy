"""
Tax Document Validation Engine
==============================

Production-grade, class-based rule engine that cross-validates data
extracted from Form 16 and Form 26AS.

Design principles
-----------------
* Each rule is a standalone method → easy to extend, test, and toggle.
* No field values are hard-coded; everything comes from the two input dicts.
* A numeric trust ``score`` (0–100) summarises overall document health.
* Every issue carries ``severity``, ``type``, ``field``, and a UI-friendly
  ``message`` so the frontend can render actionable cards directly.

Expected NER output (Step 2) schema
------------------------------------
{
    "PAN": str,
    "TAN": str,
    "EmployerName": str,
    "GrossSalary": float,
    "NetSalary": float,          # optional
    "TaxableIncome": float,
    "TDS": float,
    "Section80C": float,         # optional
    "Section80D": float,         # optional
    "AssessmentYear": str,       # e.g. "2023-24"
}
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ValidationIssue:
    """A single validation finding."""
    type: str
    message: str
    severity: str
    field: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass
class ValidationResult:
    """Aggregated validation response."""
    status: str = "ok"           # ok | warning | error
    score: int = 100
    issues: List[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "issues": [i.to_dict() for i in self.issues],
        }


# ---------------------------------------------------------------------------
# Penalty configuration (tweak these per business needs)
# ---------------------------------------------------------------------------

_PENALTY: Dict[str, int] = {
    Severity.HIGH:   25,
    Severity.MEDIUM: 10,
    Severity.LOW:    5,
}


# ---------------------------------------------------------------------------
# Validation Engine
# ---------------------------------------------------------------------------

class ValidationEngine:
    """Rule-based validation engine for tax document consistency.

    Usage::

        engine = ValidationEngine()
        result = engine.validate(form16_data, form26as_data)
        print(result.to_dict())

    Parameters
    ----------
    tds_tolerance : float
        Absolute tolerance (₹) for TDS reconciliation.
    income_anomaly_pct : float
        If taxable income exceeds gross salary by more than this fraction,
        flag as anomaly (should never happen — deductions reduce income).
    """

    def __init__(
        self,
        tds_tolerance: float = 5.0,
        income_anomaly_pct: float = 0.05,
    ):
        self.tds_tolerance = tds_tolerance
        self.income_anomaly_pct = income_anomaly_pct

    # ------------------------------------------------------------------ #
    # Helper
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        """Coerce a value to float, returning None on failure."""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------ #
    # Individual rules
    # ------------------------------------------------------------------ #

    def validate_pan(
        self,
        form16: Dict[str, Any],
        form26as: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Rule 1 — PAN must match across both documents."""
        pan_16 = form16.get("PAN")
        pan_26 = form26as.get("PAN")

        if not pan_16 or not pan_26:
            result.add(ValidationIssue(
                type="MISSING_PAN",
                message="PAN is missing from one or both documents.",
                severity=Severity.HIGH,
                field="PAN",
            ))
            return

        if pan_16.strip().upper() != pan_26.strip().upper():
            result.add(ValidationIssue(
                type="PAN_MISMATCH",
                message=(
                    f"PAN mismatch — Form 16: {pan_16}, "
                    f"Form 26AS: {pan_26}."
                ),
                severity=Severity.HIGH,
                field="PAN",
            ))
        else:
            log.info("PAN check passed: %s", pan_16)

    def validate_tan(
        self,
        form16: Dict[str, Any],
        form26as: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Rule 2 — TAN must match (employer consistency)."""
        tan_16 = form16.get("TAN")
        tan_26 = form26as.get("TAN")

        if not tan_16:
            result.add(ValidationIssue(
                type="MISSING_TAN",
                message="TAN is missing from Form 16.",
                severity=Severity.MEDIUM,
                field="TAN",
            ))
            return

        if tan_26 and tan_16.strip().upper() != tan_26.strip().upper():
            result.add(ValidationIssue(
                type="TAN_MISMATCH",
                message=(
                    f"TAN mismatch — Form 16: {tan_16}, "
                    f"Form 26AS: {tan_26}. Employer may differ."
                ),
                severity=Severity.HIGH,
                field="TAN",
            ))
        else:
            log.info("TAN check passed: %s", tan_16)

    def validate_tds(
        self,
        form16: Dict[str, Any],
        form26as: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Rule 3 — TDS reconciliation with configurable tolerance."""
        tds_16 = self._safe_float(form16.get("TDS"))
        tds_26 = self._safe_float(form26as.get("TDS"))

        if tds_16 is None or tds_26 is None:
            result.add(ValidationIssue(
                type="MISSING_TDS",
                message="TDS value is missing from one or both documents.",
                severity=Severity.HIGH,
                field="TDS",
            ))
            return

        diff = abs(tds_16 - tds_26)
        if diff > self.tds_tolerance:
            severity = Severity.HIGH if diff > 500 else Severity.MEDIUM
            result.add(ValidationIssue(
                type="TDS_MISMATCH",
                message=(
                    f"Form 16 TDS ({tds_16:.0f}) != "
                    f"Form 26AS TDS ({tds_26:.0f}). "
                    f"Difference: ₹{diff:.0f}."
                ),
                severity=severity,
                field="TDS",
            ))
        else:
            log.info(
                "TDS check passed — Form 16: %.0f, Form 26AS: %.0f (diff %.0f ≤ %.0f)",
                tds_16, tds_26, diff, self.tds_tolerance,
            )

    def validate_income(
        self,
        form16: Dict[str, Any],
        form26as: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Rule 4 — Income consistency (taxable ≤ gross; anomaly detection)."""
        gross = self._safe_float(form16.get("GrossSalary"))
        taxable = self._safe_float(form16.get("TaxableIncome"))

        if gross is None:
            result.add(ValidationIssue(
                type="MISSING_GROSS_SALARY",
                message="Gross Salary is missing from Form 16.",
                severity=Severity.MEDIUM,
                field="GrossSalary",
            ))
        if taxable is None:
            result.add(ValidationIssue(
                type="MISSING_TAXABLE_INCOME",
                message="Taxable Income is missing from Form 16.",
                severity=Severity.MEDIUM,
                field="TaxableIncome",
            ))

        if gross is not None and taxable is not None:
            if taxable > gross:
                result.add(ValidationIssue(
                    type="INCOME_ANOMALY",
                    message=(
                        f"Taxable Income ({taxable:.0f}) exceeds "
                        f"Gross Salary ({gross:.0f}). "
                        "This should never happen after deductions."
                    ),
                    severity=Severity.HIGH,
                    field="TaxableIncome",
                ))
            else:
                deduction = gross - taxable
                deduction_pct = deduction / gross if gross > 0 else 0
                log.info(
                    "Income check passed — Gross: %.0f, Taxable: %.0f, "
                    "Deductions: %.0f (%.1f%%)",
                    gross, taxable, deduction, deduction_pct * 100,
                )
                # Warn if deductions look unusually large (> 50 % of gross)
                if deduction_pct > 0.50:
                    result.add(ValidationIssue(
                        type="HIGH_DEDUCTIONS_WARNING",
                        message=(
                            f"Deductions account for {deduction_pct:.0%} of "
                            f"Gross Salary ({gross:.0f}). "
                            "Please verify Section 80C / 80D claims."
                        ),
                        severity=Severity.LOW,
                        field="TaxableIncome",
                    ))

    def validate_assessment_year(
        self,
        form16: Dict[str, Any],
        form26as: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Rule 5 — Assessment year must match exactly."""
        ay_16 = form16.get("AssessmentYear")
        ay_26 = form26as.get("AssessmentYear")

        if not ay_16 or not ay_26:
            result.add(ValidationIssue(
                type="MISSING_AY",
                message="Assessment Year is missing from one or both documents.",
                severity=Severity.MEDIUM,
                field="AssessmentYear",
            ))
            return

        if str(ay_16).strip() != str(ay_26).strip():
            result.add(ValidationIssue(
                type="AY_MISMATCH",
                message=(
                    f"Assessment Year mismatch — Form 16: {ay_16}, "
                    f"Form 26AS: {ay_26}."
                ),
                severity=Severity.HIGH,
                field="AssessmentYear",
            ))
        else:
            log.info("Assessment Year check passed: %s", ay_16)

    def validate_missing_fields(
        self,
        form16: Dict[str, Any],
        form26as: Dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Rule 6 — Detect null / missing critical entities in Form 16."""
        required_fields = [
            "PAN", "TAN", "EmployerName",
            "GrossSalary", "TDS", "TaxableIncome", "AssessmentYear",
        ]
        for fld in required_fields:
            val = form16.get(fld)
            if val is None or (isinstance(val, str) and not val.strip()):
                result.add(ValidationIssue(
                    type="MISSING_FIELD",
                    message=f"Required field '{fld}' is missing or empty in Form 16.",
                    severity=Severity.HIGH if fld in ("PAN", "TDS") else Severity.MEDIUM,
                    field=fld,
                ))

    # ------------------------------------------------------------------ #
    # Orchestrator
    # ------------------------------------------------------------------ #

    def validate(
        self,
        form16_data: Dict[str, Any],
        form26as_data: Dict[str, Any],
    ) -> ValidationResult:
        """Run every rule and return an aggregated :class:`ValidationResult`.

        Parameters
        ----------
        form16_data : dict
            Structured NER output from a Form 16 document.
        form26as_data : dict
            Structured NER output (or API data) from Form 26AS.

        Returns
        -------
        ValidationResult
            Contains ``status``, ``score`` (0–100), and ``issues`` list.
        """
        result = ValidationResult()

        # Run all rules sequentially
        log.info("── Starting validation ──")
        self.validate_missing_fields(form16_data, form26as_data, result)
        self.validate_pan(form16_data, form26as_data, result)
        self.validate_tan(form16_data, form26as_data, result)
        self.validate_tds(form16_data, form26as_data, result)
        self.validate_income(form16_data, form26as_data, result)
        self.validate_assessment_year(form16_data, form26as_data, result)

        # Compute score
        for issue in result.issues:
            penalty = _PENALTY.get(issue.severity, 5)
            result.score = max(0, result.score - penalty)

        # Derive top-level status
        if result.score >= 80:
            result.status = "ok"
        elif result.score >= 50:
            result.status = "warning"
        else:
            result.status = "error"

        log.info(
            "── Validation complete — status=%s, score=%d, issues=%d ──",
            result.status, result.score, len(result.issues),
        )
        return result


# ---------------------------------------------------------------------------
# Convenience wrapper
# ---------------------------------------------------------------------------

def validate(
    form16_data: Dict[str, Any],
    form26as_data: Dict[str, Any],
    tds_tolerance: float = 5.0,
) -> Dict[str, Any]:
    """One-call validation — returns a plain dict.

    Usage::

        from app.services.validation_service import validate
        result = validate(form16, form26as)
    """
    engine = ValidationEngine(tds_tolerance=tds_tolerance)
    return engine.validate(form16_data, form26as_data).to_dict()


# ---------------------------------------------------------------------------
# Example usage with real Form 16 values and mock Form 26AS
# ---------------------------------------------------------------------------

def example_usage() -> Dict[str, Any]:
    """
    Demonstrates validation using actual values extracted from the
    provided Form 16 (PAN: BIGPP1846N, AY: 2023-24) and a mock
    Form 26AS input with a deliberate TDS delta to trigger a mismatch.
    """

    # Data as it would come out of the NER pipeline (Step 2)
    form16_data = {
        "PAN": "BIGPP1846N",
        "TAN": "MUMS15654C",
        "EmployerName": "SIEMENS TECHNOLOGY AND SERVICES PRIVATE LIMITED",
        "GrossSalary": 873898,
        "TaxableIncome": 604280,
        "TDS": 34690,
        "Section80C": 150000,
        "Section80D": 25000,
        "NetSalary": None,          # not always on Form 16
        "AssessmentYear": "2023-24",
    }

    # Mock Form 26AS (TDS deliberately differs by ₹690)
    form26as_data = {
        "PAN": "BIGPP1846N",
        "TAN": "MUMS15654C",
        "TDS": 34000,
        "AssessmentYear": "2023-24",
    }

    result = validate(form16_data, form26as_data)

    # Pretty-print for quick inspection
    import json
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
    example_usage()
