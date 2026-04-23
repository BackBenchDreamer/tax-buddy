from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.schemas import Regime, TaxBreakdownItem, TaxComputationRequest, TaxComputationResult


@dataclass
class TaxComputationContext:
    request: TaxComputationRequest
    validated_fields: dict[str, Any]


class IndianTaxEngine:
    cess_rate: float = 0.04

    def compute(self, context: TaxComputationContext) -> TaxComputationResult:
        gross_income = max(context.request.gross_income + context.request.other_income, 0.0)
        standard_deduction = max(context.request.standard_deduction, 0.0)
        deductions_80c = max(context.request.deductions_80c, 0.0)
        deductions_80d = max(context.request.deductions_80d, 0.0)

        if context.request.regime == Regime.old:
            total_deductions = min(standard_deduction + deductions_80c + deductions_80d, gross_income)
            slab_tax, breakdown = self._old_regime_tax(max(gross_income - total_deductions, 0.0))
            assumptions = [
                "Old regime deduction cap applied using provided inputs only.",
                "Section 87A rebate not applied automatically without age and total income context.",
            ]
        else:
            allowed_standard = min(standard_deduction, 50000.0)
            total_deductions = min(allowed_standard, gross_income)
            slab_tax, breakdown = self._new_regime_tax(max(gross_income - total_deductions, 0.0))
            assumptions = [
                "New regime computed using FY 2024-25 style slabs by default.",
                "No surcharge applied unless taxable income exceeds threshold.",
            ]

        cess = round(slab_tax * self.cess_rate, 2)
        tax_liability = round(slab_tax + cess, 2)
        tds = max(context.request.tds, 0.0)
        refund_payable = round(tds - tax_liability, 2)
        if refund_payable < 0:
            refund_payable = round(abs(refund_payable), 2) * -1

        breakdown.append(TaxBreakdownItem(label="Cess", amount=cess, explanation=f"Health and education cess at {self.cess_rate * 100:.0f}%"))
        breakdown.append(TaxBreakdownItem(label="Net liability", amount=tax_liability, explanation="Final tax after cess"))
        return TaxComputationResult(
            regime=context.request.regime,
            gross_income=round(gross_income, 2),
            total_deductions=round(total_deductions, 2),
            taxable_income=round(max(gross_income - total_deductions, 0.0), 2),
            tax_liability=tax_liability,
            cess=cess,
            refund_payable=refund_payable,
            breakdown=breakdown,
            assumptions=assumptions,
        )

    def _old_regime_tax(self, taxable_income: float) -> tuple[float, list[TaxBreakdownItem]]:
        slabs = [
            (250000.0, 0.0),
            (250000.0, 0.05),
            (500000.0, 0.20),
            (float("inf"), 0.30),
        ]
        remaining = taxable_income
        tax = 0.0
        breakdown: list[TaxBreakdownItem] = []
        lower_limit = 0.0
        for width, rate in slabs:
            if remaining <= 0:
                break
            taxable_slice = min(remaining, width)
            taxed_amount = taxable_slice * rate
            tax += taxed_amount
            breakdown.append(
                TaxBreakdownItem(
                    label=f"Old regime slab {lower_limit:,.0f} - {lower_limit + taxable_slice:,.0f}",
                    amount=round(taxed_amount, 2),
                    explanation=f"Rate {rate * 100:.0f}% applied to {taxable_slice:,.2f}",
                )
            )
            remaining -= taxable_slice
            lower_limit += taxable_slice
        return round(tax, 2), breakdown

    def _new_regime_tax(self, taxable_income: float) -> tuple[float, list[TaxBreakdownItem]]:
        slabs = [
            (300000.0, 0.0),
            (300000.0, 0.05),
            (300000.0, 0.10),
            (300000.0, 0.15),
            (300000.0, 0.20),
            (300000.0, 0.25),
            (float("inf"), 0.30),
        ]
        remaining = taxable_income
        tax = 0.0
        breakdown: list[TaxBreakdownItem] = []
        lower_limit = 0.0
        for width, rate in slabs:
            if remaining <= 0:
                break
            taxable_slice = min(remaining, width)
            taxed_amount = taxable_slice * rate
            tax += taxed_amount
            breakdown.append(
                TaxBreakdownItem(
                    label=f"New regime slab {lower_limit:,.0f} - {lower_limit + taxable_slice:,.0f}",
                    amount=round(taxed_amount, 2),
                    explanation=f"Rate {rate * 100:.0f}% applied to {taxable_slice:,.2f}",
                )
            )
            remaining -= taxable_slice
            lower_limit += taxable_slice
        return round(tax, 2), breakdown
