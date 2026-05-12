"""
ITR Form Generation Service
============================

Generates structured ITR forms based on extracted data and tax computation results.

Supported Forms:
- ITR-1 (Sahaj): For salaried individuals with income from salary, one house property, other sources
- ITR-4 (Sugam): For individuals/HUFs with presumptive income u/s 44AD, 44ADA, 44AE

Output Formats:
1. JSON (structured data matching ITR schema)
2. PDF (human-readable tax summary)
3. Plain text (pre-fill reference for portal)
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import json

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ITR Form Selection Logic
# ---------------------------------------------------------------------------

def select_itr_form(
    income_sources: Dict[str, float],
    total_income: float,
    has_business_income: bool = False,
    has_capital_gains: bool = False,
    has_foreign_assets: bool = False,
) -> str:
    """Auto-select appropriate ITR form based on income profile.
    
    Parameters
    ----------
    income_sources : dict
        Keys: "salary", "house_property", "other_sources", "business", "capital_gains"
    total_income : float
        Total income for the year
    has_business_income : bool
        Whether taxpayer has business/professional income
    has_capital_gains : bool
        Whether taxpayer has capital gains
    has_foreign_assets : bool
        Whether taxpayer has foreign assets/income
    
    Returns
    -------
    str
        "ITR-1", "ITR-2", "ITR-3", or "ITR-4"
    """
    # ITR-1 (Sahaj) eligibility:
    # - Resident individual
    # - Income from salary, one house property, other sources
    # - Total income ≤ ₹50 lakhs
    # - No capital gains, no business income, no foreign assets
    
    if (
        total_income <= 5_000_000
        and not has_business_income
        and not has_capital_gains
        and not has_foreign_assets
        and income_sources.get("salary", 0) > 0
    ):
        log.info("[ITR] Selected ITR-1 (Sahaj) - salaried individual, income ≤ ₹50L")
        return "ITR-1"
    
    # ITR-4 (Sugam) eligibility:
    # - Presumptive income u/s 44AD (business), 44ADA (professional), 44AE (goods carriage)
    # - Total income ≤ ₹50 lakhs
    # - No capital gains, no foreign assets
    
    if (
        total_income <= 5_000_000
        and has_business_income
        and not has_capital_gains
        and not has_foreign_assets
    ):
        log.info("[ITR] Selected ITR-4 (Sugam) - presumptive income, total ≤ ₹50L")
        return "ITR-4"
    
    # ITR-2: For individuals/HUFs not having business income
    if not has_business_income:
        log.info("[ITR] Selected ITR-2 - no business income")
        return "ITR-2"
    
    # ITR-3: For individuals/HUFs having business/professional income
    log.info("[ITR] Selected ITR-3 - business/professional income")
    return "ITR-3"


# ---------------------------------------------------------------------------
# ITR-1 (Sahaj) Generator
# ---------------------------------------------------------------------------

def generate_itr1_json(
    validated_data: Dict[str, Any],
    tax_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate ITR-1 (Sahaj) JSON structure.
    
    Parameters
    ----------
    validated_data : dict
        Extracted and validated data from Form 16/26AS
    tax_result : dict
        Tax computation result from tax_service
    
    Returns
    -------
    dict
        ITR-1 JSON structure
    """
    log.info("[ITR-1] Generating JSON for PAN=%s", validated_data.get("PAN", "?"))
    
    # Personal Information
    personal_info = {
        "pan": validated_data.get("PAN", ""),
        "name": validated_data.get("EmployeeName", validated_data.get("EmployerName", "")),
        "assessment_year": validated_data.get("AssessmentYear", ""),
        "filing_date": datetime.now().strftime("%Y-%m-%d"),
        "residential_status": "Resident",  # Default assumption
    }
    
    # Income Details (Schedule S - Salary)
    gross_salary = float(validated_data.get("GrossSalary", 0))
    deductions = float(tax_result.get("deductions", 0))
    
    schedule_s = {
        "gross_salary": gross_salary,
        "allowances_exempt": 0,  # Not extracted from Form 16
        "deductions_us_16": deductions,
        "net_salary": gross_salary - deductions,
    }
    
    # Income from House Property (Schedule HP)
    schedule_hp = {
        "annual_value": 0,
        "interest_on_loan": 0,
        "net_income": 0,
    }
    
    # Income from Other Sources (Schedule OS)
    schedule_os = {
        "interest_income": 0,
        "dividend_income": 0,
        "other_income": 0,
        "total": 0,
    }
    
    # Gross Total Income
    gross_total_income = schedule_s["net_salary"] + schedule_hp["net_income"] + schedule_os["total"]
    
    # Deductions (Chapter VI-A)
    chapter_via_deductions = {
        "section_80c": float(validated_data.get("Section80C", 0)),
        "section_80d": float(validated_data.get("Section80D", 0)),
        "section_80tta": 0,
        "section_80ttb": 0,
        "total": float(validated_data.get("Section80C", 0)) + float(validated_data.get("Section80D", 0)),
    }
    
    # Total Income
    total_income = float(tax_result.get("taxable_income", 0))
    
    # Tax Computation
    tax_computation = {
        "tax_on_total_income": float(tax_result.get("base_tax", 0)),
        "rebate_us_87a": float(tax_result.get("rebate", 0)),
        "surcharge": float(tax_result.get("surcharge", 0)),
        "health_education_cess": float(tax_result.get("cess", 0)),
        "total_tax_payable": float(tax_result.get("total_tax", 0)),
    }
    
    # Tax Paid
    tax_paid = {
        "tds": float(validated_data.get("TDS", 0)),
        "advance_tax": 0,
        "self_assessment_tax": 0,
        "total": float(validated_data.get("TDS", 0)),
    }
    
    # Refund or Tax Payable
    refund_or_payable = float(tax_result.get("refund_or_payable", 0))
    
    # Assemble ITR-1
    itr1 = {
        "form_name": "ITR-1 (Sahaj)",
        "form_version": "AY 2024-25",
        "personal_information": personal_info,
        "income_details": {
            "schedule_s_salary": schedule_s,
            "schedule_hp_house_property": schedule_hp,
            "schedule_os_other_sources": schedule_os,
            "gross_total_income": gross_total_income,
        },
        "deductions": {
            "chapter_via": chapter_via_deductions,
            "total_deductions": chapter_via_deductions["total"],
        },
        "total_income": total_income,
        "tax_computation": tax_computation,
        "tax_paid": tax_paid,
        "refund_or_payable": refund_or_payable,
        "verification": {
            "status": "pending",
            "declaration": "I declare that the information given above is correct and complete to the best of my knowledge and belief.",
        },
    }
    
    log.info("[ITR-1] JSON generated - Total Income: ₹%.0f, Tax: ₹%.0f, Refund/Payable: ₹%.0f",
             total_income, tax_computation["total_tax_payable"], refund_or_payable)
    
    return itr1


# ---------------------------------------------------------------------------
# ITR-4 (Sugam) Generator
# ---------------------------------------------------------------------------

def generate_itr4_json(
    validated_data: Dict[str, Any],
    tax_result: Dict[str, Any],
    presumptive_income: Dict[str, float],
) -> Dict[str, Any]:
    """Generate ITR-4 (Sugam) JSON structure.
    
    Parameters
    ----------
    validated_data : dict
        Extracted and validated data
    tax_result : dict
        Tax computation result
    presumptive_income : dict
        Keys: "business_44ad", "professional_44ada", "goods_carriage_44ae"
    
    Returns
    -------
    dict
        ITR-4 JSON structure
    """
    log.info("[ITR-4] Generating JSON for PAN=%s", validated_data.get("PAN", "?"))
    
    # Personal Information
    personal_info = {
        "pan": validated_data.get("PAN", ""),
        "name": validated_data.get("EmployeeName", validated_data.get("EmployerName", "")),
        "assessment_year": validated_data.get("AssessmentYear", ""),
        "filing_date": datetime.now().strftime("%Y-%m-%d"),
        "residential_status": "Resident",
        "nature_of_business": "Presumptive",
    }
    
    # Presumptive Income (Schedule BP)
    schedule_bp = {
        "business_44ad": presumptive_income.get("business_44ad", 0),
        "professional_44ada": presumptive_income.get("professional_44ada", 0),
        "goods_carriage_44ae": presumptive_income.get("goods_carriage_44ae", 0),
        "total_presumptive_income": sum(presumptive_income.values()),
    }
    
    # Other Income
    salary_income = float(validated_data.get("GrossSalary", 0))
    
    # Gross Total Income
    gross_total_income = schedule_bp["total_presumptive_income"] + salary_income
    
    # Deductions
    chapter_via_deductions = {
        "section_80c": float(validated_data.get("Section80C", 0)),
        "section_80d": float(validated_data.get("Section80D", 0)),
        "total": float(validated_data.get("Section80C", 0)) + float(validated_data.get("Section80D", 0)),
    }
    
    # Total Income
    total_income = float(tax_result.get("taxable_income", 0))
    
    # Tax Computation
    tax_computation = {
        "tax_on_total_income": float(tax_result.get("base_tax", 0)),
        "rebate_us_87a": float(tax_result.get("rebate", 0)),
        "surcharge": float(tax_result.get("surcharge", 0)),
        "health_education_cess": float(tax_result.get("cess", 0)),
        "total_tax_payable": float(tax_result.get("total_tax", 0)),
    }
    
    # Tax Paid
    tax_paid = {
        "tds": float(validated_data.get("TDS", 0)),
        "advance_tax": 0,
        "self_assessment_tax": 0,
        "total": float(validated_data.get("TDS", 0)),
    }
    
    # Refund or Tax Payable
    refund_or_payable = float(tax_result.get("refund_or_payable", 0))
    
    # Assemble ITR-4
    itr4 = {
        "form_name": "ITR-4 (Sugam)",
        "form_version": "AY 2024-25",
        "personal_information": personal_info,
        "income_details": {
            "schedule_bp_presumptive": schedule_bp,
            "salary_income": salary_income,
            "gross_total_income": gross_total_income,
        },
        "deductions": {
            "chapter_via": chapter_via_deductions,
            "total_deductions": chapter_via_deductions["total"],
        },
        "total_income": total_income,
        "tax_computation": tax_computation,
        "tax_paid": tax_paid,
        "refund_or_payable": refund_or_payable,
        "verification": {
            "status": "pending",
            "declaration": "I declare that the information given above is correct and complete to the best of my knowledge and belief.",
        },
    }
    
    log.info("[ITR-4] JSON generated - Total Income: ₹%.0f, Tax: ₹%.0f, Refund/Payable: ₹%.0f",
             total_income, tax_computation["total_tax_payable"], refund_or_payable)
    
    return itr4


# ---------------------------------------------------------------------------
# Plain Text Pre-fill Generator
# ---------------------------------------------------------------------------

def generate_prefill_text(itr_json: Dict[str, Any]) -> str:
    """Generate plain text pre-fill reference for portal submission.
    
    Parameters
    ----------
    itr_json : dict
        ITR JSON structure (ITR-1 or ITR-4)
    
    Returns
    -------
    str
        Plain text with field-by-field values
    """
    form_name = itr_json.get("form_name", "ITR")
    lines = [
        f"{'=' * 60}",
        f"{form_name} - Pre-fill Reference",
        f"{'=' * 60}",
        "",
        "PERSONAL INFORMATION",
        "-" * 60,
    ]
    
    personal = itr_json.get("personal_information", {})
    for key, value in personal.items():
        lines.append(f"{key.replace('_', ' ').title()}: {value}")
    
    lines.extend(["", "INCOME DETAILS", "-" * 60])
    income = itr_json.get("income_details", {})
    for section, data in income.items():
        lines.append(f"\n{section.replace('_', ' ').title()}:")
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, (int, float)):
                    lines.append(f"  {k.replace('_', ' ').title()}: ₹{v:,.2f}")
                else:
                    lines.append(f"  {k.replace('_', ' ').title()}: {v}")
        else:
            lines.append(f"  {data}")
    
    lines.extend(["", "DEDUCTIONS", "-" * 60])
    deductions = itr_json.get("deductions", {})
    for key, value in deductions.items():
        if isinstance(value, dict):
            lines.append(f"\n{key.replace('_', ' ').title()}:")
            for k, v in value.items():
                lines.append(f"  {k.replace('_', ' ').title()}: ₹{v:,.2f}")
        else:
            lines.append(f"{key.replace('_', ' ').title()}: ₹{value:,.2f}")
    
    lines.extend(["", f"Total Income: ₹{itr_json.get('total_income', 0):,.2f}", ""])
    
    lines.extend(["TAX COMPUTATION", "-" * 60])
    tax_comp = itr_json.get("tax_computation", {})
    for key, value in tax_comp.items():
        lines.append(f"{key.replace('_', ' ').title()}: ₹{value:,.2f}")
    
    lines.extend(["", "TAX PAID", "-" * 60])
    tax_paid = itr_json.get("tax_paid", {})
    for key, value in tax_paid.items():
        lines.append(f"{key.replace('_', ' ').title()}: ₹{value:,.2f}")
    
    refund = itr_json.get("refund_or_payable", 0)
    label = "REFUND" if refund >= 0 else "TAX PAYABLE"
    lines.extend(["", f"{label}: ₹{abs(refund):,.2f}", ""])
    
    lines.extend(["=" * 60, ""])
    
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Unified Entry Point
# ---------------------------------------------------------------------------

def generate_itr(
    validated_data: Dict[str, Any],
    tax_result: Dict[str, Any],
    form_type: Optional[str] = None,
    presumptive_income: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Generate ITR form with auto-selection if form_type not specified.
    
    Parameters
    ----------
    validated_data : dict
        Extracted and validated data
    tax_result : dict
        Tax computation result
    form_type : str, optional
        "ITR-1" or "ITR-4". If None, auto-select based on income profile.
    presumptive_income : dict, optional
        Required for ITR-4. Keys: "business_44ad", "professional_44ada", "goods_carriage_44ae"
    
    Returns
    -------
    dict
        {
            "form_type": str,
            "itr_json": dict,
            "prefill_text": str,
        }
    """
    # Auto-select form if not specified
    if form_type is None:
        income_sources = {
            "salary": float(validated_data.get("GrossSalary", 0)),
            "house_property": 0,
            "other_sources": 0,
            "business": sum(presumptive_income.values()) if presumptive_income else 0,
            "capital_gains": 0,
        }
        total_income = float(tax_result.get("taxable_income", 0))
        has_business = bool(presumptive_income and sum(presumptive_income.values()) > 0)
        
        form_type = select_itr_form(
            income_sources=income_sources,
            total_income=total_income,
            has_business_income=has_business,
            has_capital_gains=False,
            has_foreign_assets=False,
        )
    
    # Generate appropriate form
    if form_type == "ITR-4":
        if not presumptive_income:
            presumptive_income = {"business_44ad": 0, "professional_44ada": 0, "goods_carriage_44ae": 0}
        itr_json = generate_itr4_json(validated_data, tax_result, presumptive_income)
    else:
        # Default to ITR-1
        itr_json = generate_itr1_json(validated_data, tax_result)
    
    # Generate prefill text
    prefill_text = generate_prefill_text(itr_json)
    
    return {
        "form_type": form_type,
        "itr_json": itr_json,
        "prefill_text": prefill_text,
    }

# Made with Bob
