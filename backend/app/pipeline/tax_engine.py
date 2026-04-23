"""
Indian Income Tax computation engine.
Supports Old Regime (with deductions) and New Regime (2024-25 slabs).
Provides full explainable breakdown.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger
from app.pipeline.ner_extractor import ExtractionOutput


# ─── 2024-25 Tax Slabs ────────────────────────────────────────────────────────

OLD_REGIME_SLABS = [
    (250_000, 0.00),
    (500_000, 0.05),
    (1_000_000, 0.20),
    (float("inf"), 0.30),
]

NEW_REGIME_SLABS = [
    (300_000, 0.00),
    (600_000, 0.05),
    (900_000, 0.10),
    (1_200_000, 0.15),
    (1_500_000, 0.20),
    (float("inf"), 0.30),
]

CESS_RATE = 0.04
REBATE_87A_LIMIT = 500_000
REBATE_87A_AMOUNT = 12_500
STANDARD_DEDUCTION_SALARIED = 50_000

OLD_SECTION_LIMITS = {
    "section_80c": 150_000,
    "section_80d": 25_000,
    "section_80e": None,  # no limit
    "section_80g": None,  # 50% or 100% depending on org; simplified here
}


@dataclass
class SlabStep:
    slab: str
    income_in_slab: float
    rate: float
    tax: float


@dataclass
class DeductionLine:
    section: str
    claimed: float
    capped_at: Optional[float]
    allowed: float


@dataclass
class TaxResult:
    regime: str
    gross_income: float
    deductions: list[DeductionLine]
    total_deductions: float
    taxable_income: float
    bracket_steps: list[SlabStep]
    tax_before_cess: float
    surcharge: float
    rebate_87a: float
    cess_rate: float = CESS_RATE
    cess: float = 0.0
    total_tax: float = 0.0
    tds_paid: float = 0.0
    refund_or_payable: float = 0.0
    refund_or_payable_label: str = ""


def _compute_tax_on_slabs(taxable: float, slabs: list) -> tuple[float, list[SlabStep]]:
    tax = 0.0
    steps = []
    prev = 0.0
    for limit, rate in slabs:
        if taxable <= prev:
            break
        amount_in_slab = min(taxable, limit) - prev
        slab_tax = amount_in_slab * rate
        tax += slab_tax
        if amount_in_slab > 0:
            steps.append(SlabStep(
                slab=f"₹{int(prev):,} – ₹{int(min(taxable, limit)):,}",
                income_in_slab=amount_in_slab,
                rate=rate,
                tax=slab_tax,
            ))
        prev = limit
    return tax, steps


def _compute_surcharge(taxable: float, tax: float) -> float:
    if taxable <= 5_000_000:
        return 0.0
    elif taxable <= 10_000_000:
        return tax * 0.10
    elif taxable <= 20_000_000:
        return tax * 0.15
    elif taxable <= 50_000_000:
        return tax * 0.25
    else:
        return tax * 0.37


def compute_old_regime(income_data: dict, tds_paid: float = 0.0) -> TaxResult:
    gross = float(income_data.get("gross_salary", 0.0))
    deductions: list[DeductionLine] = []

    # Standard deduction (mandatory for salaried)
    std_ded = STANDARD_DEDUCTION_SALARIED
    deductions.append(DeductionLine("Standard Deduction (Sec 16)", std_ded, std_ded, std_ded))

    # Chapter VI-A deductions
    for section, cap in OLD_SECTION_LIMITS.items():
        claimed = float(income_data.get(section, 0.0))
        if claimed > 0:
            allowed = min(claimed, cap) if cap else claimed
            deductions.append(DeductionLine(section.replace("_", " ").title(), claimed, cap, allowed))

    total_ded = sum(d.allowed for d in deductions)
    taxable = max(0.0, gross - total_ded)

    tax, steps = _compute_tax_on_slabs(taxable, OLD_REGIME_SLABS)
    surcharge = _compute_surcharge(taxable, tax)
    tax += surcharge

    rebate = 0.0
    if taxable <= REBATE_87A_LIMIT:
        rebate = min(tax, REBATE_87A_AMOUNT)
        tax -= rebate

    cess = tax * CESS_RATE
    total = tax + cess
    diff = tds_paid - total

    return TaxResult(
        regime="old",
        gross_income=gross,
        deductions=deductions,
        total_deductions=total_ded,
        taxable_income=taxable,
        bracket_steps=steps,
        tax_before_cess=tax - cess,
        surcharge=surcharge,
        rebate_87a=rebate,
        cess=cess,
        total_tax=total,
        tds_paid=tds_paid,
        refund_or_payable=abs(diff),
        refund_or_payable_label="Refund" if diff > 0 else "Tax Payable",
    )


def compute_new_regime(income_data: dict, tds_paid: float = 0.0) -> TaxResult:
    gross = float(income_data.get("gross_salary", 0.0))
    std_ded = 50_000  # standard deduction allowed in new regime too (from FY 2023-24)
    deductions = [DeductionLine("Standard Deduction", std_ded, std_ded, std_ded)]
    taxable = max(0.0, gross - std_ded)

    tax, steps = _compute_tax_on_slabs(taxable, NEW_REGIME_SLABS)
    surcharge = _compute_surcharge(taxable, tax)
    tax += surcharge

    rebate = 0.0
    if taxable <= REBATE_87A_LIMIT:
        rebate = min(tax, REBATE_87A_AMOUNT)
        tax -= rebate

    cess = tax * CESS_RATE
    total = tax + cess
    diff = tds_paid - total

    return TaxResult(
        regime="new",
        gross_income=gross,
        deductions=deductions,
        total_deductions=std_ded,
        taxable_income=taxable,
        bracket_steps=steps,
        tax_before_cess=tax,
        surcharge=surcharge,
        rebate_87a=rebate,
        cess=cess,
        total_tax=total,
        tds_paid=tds_paid,
        refund_or_payable=abs(diff),
        refund_or_payable_label="Refund" if diff > 0 else "Tax Payable",
    )


def compute_both_regimes(extraction: ExtractionOutput) -> dict[str, TaxResult]:
    income_data = {k: v.value for k, v in extraction.entities.items()}
    tds = float(income_data.get("tds_deducted", 0.0))
    return {
        "old": compute_old_regime(income_data, tds),
        "new": compute_new_regime(income_data, tds),
    }
