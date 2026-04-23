from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from app.schemas import EntitySpan, ValidationIssue, ValidationResult


@dataclass
class ValidationContext:
    form16: dict[str, Any]
    form26as: dict[str, Any]
    extracted_entities: list[EntitySpan]


class ValidationService:
    def validate(self, context: ValidationContext) -> ValidationResult:
        issues: list[ValidationIssue] = []
        reconciled: dict[str, Any] = {}

        pan_16 = self._first(context.form16, "PAN")
        pan_26 = self._first(context.form26as, "PAN")
        pan_ml = self._first_entity(context.extracted_entities, "PAN")
        reconciled["PAN"] = pan_ml or pan_16 or pan_26
        self._compare(issues, "PAN", pan_16, pan_26, severity="high")
        self._compare(issues, "PAN", pan_ml, pan_16 or pan_26, severity="high")

        tan_16 = self._first(context.form16, "TAN")
        tan_26 = self._first(context.form26as, "TAN")
        reconciled["TAN"] = tan_16 or tan_26
        self._compare(issues, "TAN", tan_16, tan_26, severity="high")

        tds_16 = self._as_float(self._first(context.form16, "TDS"))
        tds_26 = self._as_float(self._first(context.form26as, "TDS"))
        if tds_16 is not None and tds_26 is not None:
            delta = abs(tds_16 - tds_26)
            reconciled["TDS_delta"] = delta
            if delta > 100:
                issues.append(
                    ValidationIssue(
                        severity="medium",
                        field="TDS",
                        message="Form 16 and Form 26AS TDS values differ beyond tolerance.",
                        expected=f"{tds_26:.2f}",
                        observed=f"{tds_16:.2f}",
                        source_documents=["form16", "form26as"],
                    )
                )

        salary_16 = self._as_float(self._first(context.form16, "GrossIncome"))
        salary_ml = self._as_float(self._first_entity(context.extracted_entities, "GrossIncome"))
        if salary_16 is not None and salary_ml is not None and abs(salary_16 - salary_ml) > max(1000.0, salary_16 * 0.02):
            issues.append(
                ValidationIssue(
                    severity="low",
                    field="GrossIncome",
                    message="Extracted salary appears inconsistent with Form 16.",
                    expected=f"{salary_16:.2f}",
                    observed=f"{salary_ml:.2f}",
                    source_documents=["form16", "ml_extraction"],
                )
            )

        deduction_80c = self._as_float(self._first(context.form16, "Section80C"))
        deduction_80d = self._as_float(self._first(context.form16, "Section80D"))
        reconciled["deductions"] = {
            "80C": deduction_80c,
            "80D": deduction_80d,
        }

        is_valid = not any(issue.severity == "high" for issue in issues)
        return ValidationResult(is_valid=is_valid, issues=issues, reconciled_fields=reconciled)

    def _first(self, payload: dict[str, Any], key: str) -> Any:
        value = payload.get(key)
        if value is None and isinstance(payload.get("entities"), list):
            for entity in payload["entities"]:
                if entity.get("label") == key:
                    return entity.get("value")
        return value

    def _first_entity(self, entities: list[EntitySpan], key: str) -> str | None:
        for entity in entities:
            if entity.label == key:
                return entity.value
        return None

    def _compare(self, issues: list[ValidationIssue], field: str, first: Any, second: Any, severity: str) -> None:
        if first is None or second is None:
            return
        if str(first).strip().upper() != str(second).strip().upper():
            issues.append(
                ValidationIssue(
                    severity=severity,
                    field=field,
                    message=f"{field} does not match across sources.",
                    expected=str(second),
                    observed=str(first),
                    source_documents=["form16", "form26as"],
                )
            )

    def _as_float(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        match = re.search(r"[0-9]+(?:\.[0-9]+)?", str(value).replace(",", ""))
        return float(match.group(0)) if match else None
