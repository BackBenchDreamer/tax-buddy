"""
Indian Income Tax Computation Engine
=====================================

Production-grade, data-driven tax calculator implementing:

* **Old Regime** slabs (Individual < 60 years)
* **New Regime** slabs (u/s 115BAC — FY 2024-25 structure)
* Section 87A rebate (both regimes)
* Health & Education Cess (4 %)
* Surcharge placeholder (structure ready, skip unless > 50 L)
* Full slab-wise breakdown for explainability

Reference
---------
https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Slab definitions (data-driven — never hard-code final tax values)
# ---------------------------------------------------------------------------

OLD_REGIME_SLABS: List[Dict[str, Any]] = [
    {"lower": 0,        "upper": 250_000,   "rate": 0.00},
    {"lower": 250_000,  "upper": 500_000,   "rate": 0.05},
    {"lower": 500_000,  "upper": 1_000_000, "rate": 0.20},
    {"lower": 1_000_000, "upper": math.inf, "rate": 0.30},
]

NEW_REGIME_SLABS: List[Dict[str, Any]] = [
    {"lower": 0,          "upper": 400_000,   "rate": 0.00},
    {"lower": 400_000,    "upper": 800_000,   "rate": 0.05},
    {"lower": 800_000,    "upper": 1_200_000, "rate": 0.10},
    {"lower": 1_200_000,  "upper": 1_600_000, "rate": 0.15},
    {"lower": 1_600_000,  "upper": 2_000_000, "rate": 0.20},
    {"lower": 2_000_000,  "upper": 2_400_000, "rate": 0.25},
    {"lower": 2_400_000,  "upper": math.inf,  "rate": 0.30},
]

# Rebate thresholds (Section 87A)
REBATE_CONFIG = {
    "old": {"income_limit": 500_000,   "max_rebate": 12_500},
    "new": {"income_limit": 1_200_000, "max_rebate": 60_000},
}

CESS_RATE = 0.04

# Standard deduction under new regime
NEW_REGIME_STD_DEDUCTION = 50_000


# ---------------------------------------------------------------------------
# Core computation functions
# ---------------------------------------------------------------------------

def _format_range(lower: float, upper: float) -> str:
    """Human-readable range label, e.g. '2.5L-5L' or '10L+'."""
    def _fmt(v: float) -> str:
        if v == math.inf:
            return "+"
        if v >= 1_00_000:
            return f"{v / 1_00_000:.1f}L".replace(".0L", "L")
        return f"{v:.0f}"

    if upper == math.inf:
        return f"{_fmt(lower)}+"
    return f"{_fmt(lower)}-{_fmt(upper)}"


def compute_tax_from_slabs(
    taxable_income: float,
    slabs: List[Dict[str, Any]],
) -> tuple[float, List[Dict[str, Any]]]:
    """Apply progressive slab rates to *taxable_income*.

    Returns
    -------
    (base_tax, breakdown)
        ``breakdown`` is a list of dicts, one per slab, showing the
        taxable amount, rate, and tax for that bracket.
    """
    base_tax = 0.0
    breakdown: List[Dict[str, Any]] = []

    for slab in slabs:
        lower = slab["lower"]
        upper = slab["upper"]
        rate = slab["rate"]

        if taxable_income <= lower:
            break

        taxable_in_slab = min(taxable_income, upper) - lower
        tax_in_slab = taxable_in_slab * rate

        breakdown.append({
            "range": _format_range(lower, upper),
            "taxable_amount": round(taxable_in_slab, 2),
            "rate": rate,
            "tax": round(tax_in_slab, 2),
        })

        base_tax += tax_in_slab

    return round(base_tax, 2), breakdown


def apply_rebate(
    taxable_income: float,
    base_tax: float,
    regime: str,
) -> float:
    """Apply Section 87A rebate.

    * Old regime: taxable ≤ ₹5,00,000 → rebate up to ₹12,500
    * New regime: taxable ≤ ₹12,00,000 → rebate up to ₹60,000

    Returns the rebate amount (always ≥ 0, never exceeds base_tax).
    """
    cfg = REBATE_CONFIG.get(regime)
    if cfg is None:
        log.warning("Unknown regime '%s' — no rebate applied.", regime)
        return 0.0

    if taxable_income <= cfg["income_limit"]:
        rebate = min(base_tax, cfg["max_rebate"])
        log.info(
            "Rebate applied (regime=%s): ₹%.0f (taxable ₹%.0f ≤ ₹%.0f)",
            regime, rebate, taxable_income, cfg["income_limit"],
        )
        return round(rebate, 2)

    return 0.0


def apply_surcharge(
    base_tax: float,
    taxable_income: float,
) -> float:
    """Apply surcharge for very high incomes.

    Currently returns 0 for incomes ≤ ₹50 L.  Structure is in place
    to add higher brackets later.
    """
    # Surcharge brackets (placeholder — extend as needed):
    #   > 50 L  → 10 %
    #   > 1 Cr  → 15 %
    #   > 2 Cr  → 25 %
    #   > 5 Cr  → 37 %  (old) / 25 % cap (new)
    if taxable_income > 5_000_000:
        surcharge = base_tax * 0.10
        log.info("Surcharge applied: ₹%.0f (10%% on ₹%.0f)", surcharge, base_tax)
        return round(surcharge, 2)

    return 0.0


def apply_cess(tax_after_surcharge: float) -> float:
    """Health & Education Cess — 4 % on (tax + surcharge)."""
    return round(tax_after_surcharge * CESS_RATE, 2)


# ---------------------------------------------------------------------------
# Regime-specific wrappers
# ---------------------------------------------------------------------------

def compute_old_regime(
    gross_income: float,
    deductions: float,
) -> Dict[str, Any]:
    """Compute tax under the **Old Regime**.

    taxable = gross - deductions  (caller supplies total deductions
    including Sec 80C, 80D, standard deduction, HRA, etc.)
    """
    taxable_income = max(gross_income - deductions, 0)
    base_tax, breakdown = compute_tax_from_slabs(taxable_income, OLD_REGIME_SLABS)

    rebate = apply_rebate(taxable_income, base_tax, "old")
    tax_after_rebate = max(base_tax - rebate, 0)

    surcharge = apply_surcharge(tax_after_rebate, taxable_income)
    tax_plus_surcharge = tax_after_rebate + surcharge

    cess = apply_cess(tax_plus_surcharge)
    total_tax = round(tax_plus_surcharge + cess, 2)

    return {
        "regime": "old",
        "gross_income": gross_income,
        "deductions": deductions,
        "taxable_income": taxable_income,
        "base_tax": base_tax,
        "rebate": rebate,
        "surcharge": surcharge,
        "cess": cess,
        "total_tax": total_tax,
        "breakdown": breakdown,
    }


def compute_new_regime(gross_income: float) -> Dict[str, Any]:
    """Compute tax under the **New Regime** (u/s 115BAC).

    Only the standard deduction of ₹50,000 is allowed.
    """
    taxable_income = max(gross_income - NEW_REGIME_STD_DEDUCTION, 0)
    base_tax, breakdown = compute_tax_from_slabs(taxable_income, NEW_REGIME_SLABS)

    rebate = apply_rebate(taxable_income, base_tax, "new")
    tax_after_rebate = max(base_tax - rebate, 0)

    surcharge = apply_surcharge(tax_after_rebate, taxable_income)
    tax_plus_surcharge = tax_after_rebate + surcharge

    cess = apply_cess(tax_plus_surcharge)
    total_tax = round(tax_plus_surcharge + cess, 2)

    return {
        "regime": "new",
        "gross_income": gross_income,
        "deductions": NEW_REGIME_STD_DEDUCTION,
        "taxable_income": taxable_income,
        "base_tax": base_tax,
        "rebate": rebate,
        "surcharge": surcharge,
        "cess": cess,
        "total_tax": total_tax,
        "breakdown": breakdown,
    }


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def compute_tax(data: Dict[str, Any]) -> Dict[str, Any]:
    """Unified tax computation entry point.

    Parameters
    ----------
    data : dict
        Expected keys::

            {
                "GrossSalary": float,
                "Deductions": float,        # total deductions (old regime)
                "TaxableIncome": float,      # optional — will recompute
                "TDS": float,
                "Regime": "old" | "new"
            }

    Returns
    -------
    dict
        Full computation result with breakdown, refund / payable, etc.
    """
    gross = float(data.get("GrossSalary", 0))
    deductions = float(data.get("Deductions", 0))
    tds = float(data.get("TDS", 0))
    regime = str(data.get("Regime", "old")).lower()

    log.info(
        "Computing tax — regime=%s, gross=%.0f, deductions=%.0f, TDS=%.0f",
        regime, gross, deductions, tds,
    )

    if regime == "new":
        result = compute_new_regime(gross)
    else:
        result = compute_old_regime(gross, deductions)

    # Refund vs. payable
    refund_or_payable = round(tds - result["total_tax"], 2)
    result["tds_paid"] = tds
    result["refund_or_payable"] = refund_or_payable

    label = "REFUND" if refund_or_payable >= 0 else "PAYABLE"
    log.info(
        "Result — total_tax=₹%.0f, TDS=₹%.0f → %s ₹%.0f",
        result["total_tax"], tds, label, abs(refund_or_payable),
    )

    return result


# ---------------------------------------------------------------------------
# Example usage & test case (Form 16 values)
# ---------------------------------------------------------------------------

def example_usage() -> None:
    """Run the real Form 16 test case and print a step-by-step breakdown.

    Form 16 values (BIGPP1846N, AY 2023-24):
        Gross Salary  ≈ 873,898
        Deductions    ≈ 269,618   (873898 − 604280)
        Taxable Income ≈ 604,280
        TDS           ≈  34,690
    """
    import json

    form16_input = {
        "GrossSalary": 873898,
        "Deductions": 269618,       # gross - taxable = 873898 - 604280
        "TDS": 34690,
        "Regime": "old",
    }

    print("=" * 60)
    print("  OLD REGIME — Form 16 Test Case")
    print("=" * 60)
    old_result = compute_tax(form16_input)
    print(json.dumps(old_result, indent=2))

    # Verify against Form 16 TDS
    diff = abs(old_result["total_tax"] - 34690)
    assert diff < 2, (
        f"Tax mismatch! Computed {old_result['total_tax']}, "
        f"expected ≈34690 (diff {diff})"
    )
    print(f"\n✅ Old regime total tax matches Form 16 TDS (diff ₹{diff:.2f})\n")

    # --- also show new regime for comparison ---
    print("=" * 60)
    print("  NEW REGIME — Same Gross Salary")
    print("=" * 60)
    form16_input["Regime"] = "new"
    new_result = compute_tax(form16_input)
    print(json.dumps(new_result, indent=2))

    savings = old_result["total_tax"] - new_result["total_tax"]
    if savings > 0:
        print(f"\n💡 New regime saves ₹{savings:.0f}")
    else:
        print(f"\n💡 Old regime saves ₹{abs(savings):.0f}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )
    example_usage()
