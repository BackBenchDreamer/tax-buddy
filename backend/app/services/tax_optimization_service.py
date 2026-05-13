"""
Tax Optimization Service with AI Suggestions
=============================================

Provides AI-powered tax optimization recommendations using Groq LLM:
- Old vs New regime comparison and recommendation
- Deduction optimization suggestions
- Investment recommendations for tax savings
- Potential savings calculations

Uses Indian tax law context (FY 2023-24) for accurate suggestions.
"""

import logging
import asyncio
import json
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.services.groq_service import _get_groq_client
from app.services.tax_service import (
    compute_old_regime,
    compute_new_regime,
    OLD_REGIME_SLABS,
    NEW_REGIME_SLABS,
    NEW_REGIME_STD_DEDUCTION,
)

log = logging.getLogger(__name__)

# Indian tax law limits (FY 2023-24)
TAX_LIMITS = {
    "Section80C": 150000,  # ₹1.5 lakh
    "Section80CCD1B": 50000,  # ₹50k additional NPS
    "Section80D": 25000,  # ₹25k (₹50k for senior citizens)
    "Section80D_SENIOR": 50000,
    "Section80E": float('inf'),  # No limit on education loan interest
    "Section80G": float('inf'),  # Varies by donation type
    "StandardDeduction": 50000,  # Old regime
    "NewRegimeStdDeduction": NEW_REGIME_STD_DEDUCTION,
}


# ---------------------------------------------------------------------------
# Core Optimization Functions
# ---------------------------------------------------------------------------

async def optimize_tax(
    validated_data: Dict[str, Any],
    tax_result: Dict[str, Any],
    ocr_text: str = "",
) -> Dict[str, Any]:
    """
    Main tax optimization function.
    
    Analyzes tax situation and provides AI-powered suggestions for:
    - Regime selection (old vs new)
    - Deduction optimization
    - Investment recommendations
    - Potential savings
    
    Parameters
    ----------
    validated_data : dict
        Validated extracted data with fields like GrossSalary, Deductions, etc.
    tax_result : dict
        Tax computation result from tax_service
    ocr_text : str, optional
        Original OCR text for additional context
    
    Returns
    -------
    dict
        {
            "regime_comparison": {...},
            "suggestions": [...],
            "potential_savings": float,
            "priority_actions": [...]
        }
    """
    log.info("[TaxOptimization] Starting optimization analysis")
    
    try:
        # Extract key data
        gross_income = float(validated_data.get("GrossSalary", 0))
        current_deductions = float(validated_data.get("TotalDeductions", 0) or 
                                   validated_data.get("Deductions", 0))
        tds = float(validated_data.get("TDS", 0))
        current_regime = tax_result.get("regime", "old")
        
        # Get deduction breakdown
        deduction_breakdown = _extract_deduction_breakdown(validated_data)
        
        # 1. Regime comparison
        regime_comparison = await recommend_regime(
            gross_income=gross_income,
            deductions=current_deductions,
            deduction_breakdown=deduction_breakdown,
            current_regime=current_regime,
        )
        
        # 2. Deduction suggestions
        deduction_suggestions = await suggest_deductions(
            gross_income=gross_income,
            deduction_breakdown=deduction_breakdown,
        )
        
        # 3. Investment suggestions
        investment_suggestions = await suggest_investments(
            gross_income=gross_income,
            deduction_breakdown=deduction_breakdown,
        )
        
        # 4. Calculate potential savings
        potential_savings = calculate_potential_savings(
            regime_comparison=regime_comparison,
            deduction_suggestions=deduction_suggestions,
            investment_suggestions=investment_suggestions,
        )
        
        # Combine all suggestions
        all_suggestions = (
            deduction_suggestions + 
            investment_suggestions
        )
        
        # Sort by priority
        priority_order = {"high": 0, "medium": 1, "low": 2}
        all_suggestions.sort(key=lambda x: priority_order.get(x["priority"], 3))
        
        # Get top priority actions
        priority_actions = [
            s for s in all_suggestions 
            if s["priority"] == "high"
        ][:3]  # Top 3 high-priority actions
        
        result = {
            "regime_comparison": regime_comparison,
            "suggestions": all_suggestions,
            "potential_savings": potential_savings,
            "priority_actions": priority_actions,
        }
        
        log.info("[TaxOptimization] Completed: %d suggestions, ₹%.0f potential savings",
                 len(all_suggestions), potential_savings)
        
        return result
        
    except Exception as exc:
        log.error("[TaxOptimization] Optimization failed: %s", exc)
        # Return basic fallback
        return {
            "regime_comparison": _basic_regime_comparison(validated_data, tax_result),
            "suggestions": [],
            "potential_savings": 0.0,
            "priority_actions": [],
            "error": str(exc),
        }


async def recommend_regime(
    gross_income: float,
    deductions: float,
    deduction_breakdown: Dict[str, float],
    current_regime: str,
) -> Dict[str, Any]:
    """
    Compare old vs new regime and provide AI-powered recommendation.
    
    Returns
    -------
    dict
        {
            "old_regime_tax": float,
            "new_regime_tax": float,
            "recommended_regime": str,
            "savings_amount": float,
            "reasoning": str,
            "comparison_details": {...}
        }
    """
    log.info("[RegimeRecommendation] Comparing regimes for gross=₹%.0f", gross_income)
    
    # Compute tax under both regimes
    old_result = compute_old_regime(gross_income, deductions)
    new_result = compute_new_regime(gross_income)
    
    old_tax = old_result["total_tax"]
    new_tax = new_result["total_tax"]
    
    # Determine better regime
    if old_tax < new_tax:
        recommended = "old"
        savings = new_tax - old_tax
    else:
        recommended = "new"
        savings = old_tax - new_tax
    
    # Get AI reasoning
    client = _get_groq_client()
    reasoning = None
    
    if client:
        try:
            reasoning = await _get_regime_reasoning(
                client=client,
                gross_income=gross_income,
                deductions=deductions,
                deduction_breakdown=deduction_breakdown,
                old_tax=old_tax,
                new_tax=new_tax,
                recommended=recommended,
            )
        except Exception as exc:
            log.warning("[RegimeRecommendation] AI reasoning failed: %s", exc)
    
    # Fallback reasoning if AI fails
    if not reasoning:
        if recommended == "old":
            reasoning = (
                f"The Old Regime is better for you, saving ₹{savings:,.0f}. "
                f"Your deductions of ₹{deductions:,.0f} significantly reduce your tax liability. "
                f"Continue maximizing deductions under Section 80C, 80D, and other applicable sections."
            )
        else:
            reasoning = (
                f"The New Regime is better for you, saving ₹{savings:,.0f}. "
                f"Even without deductions, the lower tax slabs result in less tax. "
                f"Consider the New Regime for simplicity and lower tax burden."
            )
    
    return {
        "old_regime_tax": round(old_tax, 2),
        "new_regime_tax": round(new_tax, 2),
        "recommended_regime": recommended,
        "savings_amount": round(savings, 2),
        "reasoning": reasoning,
        "comparison_details": {
            "old_regime": {
                "taxable_income": old_result["taxable_income"],
                "base_tax": old_result["base_tax"],
                "rebate": old_result["rebate"],
                "total_tax": old_result["total_tax"],
            },
            "new_regime": {
                "taxable_income": new_result["taxable_income"],
                "base_tax": new_result["base_tax"],
                "rebate": new_result["rebate"],
                "total_tax": new_result["total_tax"],
            },
        },
    }


async def suggest_deductions(
    gross_income: float,
    deduction_breakdown: Dict[str, float],
) -> List[Dict[str, Any]]:
    """
    Identify missing or underutilized deductions.
    
    Returns list of suggestions with:
    - category: "deduction"
    - priority: "high" | "medium" | "low"
    - suggestion: str
    - reasoning: str
    - potential_savings: float
    """
    suggestions = []
    
    # Check Section 80C
    section_80c = deduction_breakdown.get("Section80C", 0)
    if section_80c < TAX_LIMITS["Section80C"]:
        gap = TAX_LIMITS["Section80C"] - section_80c
        # Estimate tax savings (assume 20% bracket for simplicity)
        potential_savings = gap * 0.20
        
        suggestions.append({
            "category": "deduction",
            "section": "80C",
            "priority": "high" if gap > 50000 else "medium",
            "suggestion": f"You can claim ₹{gap:,.0f} more under Section 80C (current: ₹{section_80c:,.0f}, limit: ₹{TAX_LIMITS['Section80C']:,.0f})",
            "reasoning": "Section 80C offers tax deduction up to ₹1.5 lakh for investments in PPF, ELSS, life insurance, etc.",
            "potential_savings": round(potential_savings, 2),
            "current_amount": section_80c,
            "max_limit": TAX_LIMITS["Section80C"],
        })
    
    # Check Section 80CCD(1B) - NPS
    section_80ccd1b = deduction_breakdown.get("Section80CCD1B", 0)
    if section_80ccd1b < TAX_LIMITS["Section80CCD1B"]:
        gap = TAX_LIMITS["Section80CCD1B"] - section_80ccd1b
        potential_savings = gap * 0.20
        
        suggestions.append({
            "category": "deduction",
            "section": "80CCD(1B)",
            "priority": "high",
            "suggestion": f"Invest ₹{gap:,.0f} in NPS for additional deduction under Section 80CCD(1B)",
            "reasoning": "Additional ₹50,000 deduction over and above Section 80C limit. NPS is a retirement savings scheme.",
            "potential_savings": round(potential_savings, 2),
            "current_amount": section_80ccd1b,
            "max_limit": TAX_LIMITS["Section80CCD1B"],
        })
    
    # Check Section 80D - Health Insurance
    section_80d = deduction_breakdown.get("Section80D", 0)
    if section_80d < TAX_LIMITS["Section80D"]:
        gap = TAX_LIMITS["Section80D"] - section_80d
        potential_savings = gap * 0.20
        
        suggestions.append({
            "category": "deduction",
            "section": "80D",
            "priority": "medium",
            "suggestion": f"Claim ₹{gap:,.0f} more under Section 80D for health insurance premiums",
            "reasoning": "Deduction up to ₹25,000 for health insurance (₹50,000 for senior citizens). Covers self, spouse, children, and parents.",
            "potential_savings": round(potential_savings, 2),
            "current_amount": section_80d,
            "max_limit": TAX_LIMITS["Section80D"],
        })
    
    # Check Section 80E - Education Loan
    section_80e = deduction_breakdown.get("Section80E", 0)
    if section_80e == 0 and gross_income < 1000000:
        suggestions.append({
            "category": "deduction",
            "section": "80E",
            "priority": "low",
            "suggestion": "If you have an education loan, claim interest paid under Section 80E",
            "reasoning": "No upper limit on deduction for interest on education loan for higher studies.",
            "potential_savings": 0.0,  # Unknown without loan details
            "current_amount": 0,
            "max_limit": None,
        })
    
    # Check Section 80G - Donations
    section_80g = deduction_breakdown.get("Section80G", 0)
    if section_80g == 0:
        suggestions.append({
            "category": "deduction",
            "section": "80G",
            "priority": "low",
            "suggestion": "Consider donations to eligible charities for Section 80G deduction",
            "reasoning": "Donations to approved charitable institutions qualify for 50% or 100% deduction.",
            "potential_savings": 0.0,
            "current_amount": 0,
            "max_limit": None,
        })
    
    return suggestions


async def suggest_investments(
    gross_income: float,
    deduction_breakdown: Dict[str, float],
) -> List[Dict[str, Any]]:
    """
    Suggest specific investment options for tax savings.
    
    Returns list of investment suggestions with priority and potential savings.
    """
    suggestions = []
    
    # Get AI-powered investment suggestions
    client = _get_groq_client()
    
    if client:
        try:
            ai_suggestions = await _get_investment_suggestions(
                client=client,
                gross_income=gross_income,
                deduction_breakdown=deduction_breakdown,
            )
            if ai_suggestions:
                return ai_suggestions
        except Exception as exc:
            log.warning("[InvestmentSuggestions] AI suggestions failed: %s", exc)
    
    # Fallback: rule-based suggestions
    section_80c = deduction_breakdown.get("Section80C", 0)
    section_80ccd1b = deduction_breakdown.get("Section80CCD1B", 0)
    
    # ELSS suggestion
    if section_80c < TAX_LIMITS["Section80C"]:
        gap = min(50000, TAX_LIMITS["Section80C"] - section_80c)
        suggestions.append({
            "category": "investment",
            "section": "80C",
            "priority": "high",
            "suggestion": f"Invest ₹{gap:,.0f} in ELSS (Equity Linked Savings Scheme) mutual funds",
            "reasoning": "ELSS offers tax deduction under 80C with only 3-year lock-in period and potential for higher returns.",
            "potential_savings": round(gap * 0.20, 2),
            "investment_type": "ELSS",
            "amount": gap,
        })
    
    # PPF suggestion
    if section_80c < TAX_LIMITS["Section80C"]:
        gap = min(150000, TAX_LIMITS["Section80C"] - section_80c)
        suggestions.append({
            "category": "investment",
            "section": "80C",
            "priority": "medium",
            "suggestion": f"Invest ₹{gap:,.0f} in PPF (Public Provident Fund)",
            "reasoning": "PPF offers guaranteed returns (currently ~7.1%), tax-free interest, and EEE status. 15-year lock-in.",
            "potential_savings": round(gap * 0.20, 2),
            "investment_type": "PPF",
            "amount": gap,
        })
    
    # NPS suggestion
    if section_80ccd1b < TAX_LIMITS["Section80CCD1B"]:
        gap = TAX_LIMITS["Section80CCD1B"] - section_80ccd1b
        suggestions.append({
            "category": "investment",
            "section": "80CCD(1B)",
            "priority": "high",
            "suggestion": f"Invest ₹{gap:,.0f} in NPS (National Pension System)",
            "reasoning": "Additional ₹50,000 deduction over 80C. Good for retirement planning with market-linked returns.",
            "potential_savings": round(gap * 0.20, 2),
            "investment_type": "NPS",
            "amount": gap,
        })
    
    # Health insurance suggestion
    section_80d = deduction_breakdown.get("Section80D", 0)
    if section_80d < TAX_LIMITS["Section80D"]:
        gap = TAX_LIMITS["Section80D"] - section_80d
        suggestions.append({
            "category": "investment",
            "section": "80D",
            "priority": "medium",
            "suggestion": f"Purchase health insurance worth ₹{gap:,.0f} premium",
            "reasoning": "Health insurance provides both tax benefits and financial protection. Essential for medical emergencies.",
            "potential_savings": round(gap * 0.20, 2),
            "investment_type": "Health Insurance",
            "amount": gap,
        })
    
    return suggestions


def calculate_potential_savings(
    regime_comparison: Dict[str, Any],
    deduction_suggestions: List[Dict[str, Any]],
    investment_suggestions: List[Dict[str, Any]],
) -> float:
    """
    Calculate total potential tax savings from all suggestions.
    
    Returns
    -------
    float
        Total potential savings in rupees
    """
    total_savings = 0.0
    
    # Regime switch savings
    if regime_comparison.get("savings_amount"):
        total_savings += regime_comparison["savings_amount"]
    
    # Deduction optimization savings (avoid double counting)
    deduction_savings = sum(
        s.get("potential_savings", 0) 
        for s in deduction_suggestions
    )
    
    # Investment savings (avoid double counting with deductions)
    investment_savings = sum(
        s.get("potential_savings", 0) 
        for s in investment_suggestions
    )
    
    # Take max of deduction vs investment savings (they overlap)
    total_savings += max(deduction_savings, investment_savings)
    
    return round(total_savings, 2)


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _extract_deduction_breakdown(validated_data: Dict[str, Any]) -> Dict[str, float]:
    """Extract section-wise deduction breakdown from validated data."""
    breakdown = {}
    
    sections = [
        "Section80C", "Section80CCD1B", "Section80D", 
        "Section80E", "Section80G", "Section80TTA"
    ]
    
    for section in sections:
        value = validated_data.get(section, 0)
        if value:
            breakdown[section] = float(value)
    
    return breakdown


def _basic_regime_comparison(
    validated_data: Dict[str, Any],
    tax_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Basic regime comparison without AI (fallback)."""
    gross = float(validated_data.get("GrossSalary", 0))
    deductions = float(validated_data.get("Deductions", 0))
    
    old_result = compute_old_regime(gross, deductions)
    new_result = compute_new_regime(gross)
    
    old_tax = old_result["total_tax"]
    new_tax = new_result["total_tax"]
    
    if old_tax < new_tax:
        recommended = "old"
        savings = new_tax - old_tax
        reasoning = f"Old regime saves ₹{savings:,.0f} due to your deductions."
    else:
        recommended = "new"
        savings = old_tax - new_tax
        reasoning = f"New regime saves ₹{savings:,.0f} with lower tax slabs."
    
    return {
        "old_regime_tax": round(old_tax, 2),
        "new_regime_tax": round(new_tax, 2),
        "recommended_regime": recommended,
        "savings_amount": round(savings, 2),
        "reasoning": reasoning,
    }


async def _get_regime_reasoning(
    client,
    gross_income: float,
    deductions: float,
    deduction_breakdown: Dict[str, float],
    old_tax: float,
    new_tax: float,
    recommended: str,
) -> Optional[str]:
    """Get AI-powered reasoning for regime recommendation."""
    
    deductions_text = ", ".join([
        f"{k.replace('Section', '')}: ₹{v:,.0f}" 
        for k, v in deduction_breakdown.items()
    ]) or "None"
    
    prompt = f"""You are a tax advisor helping an Indian taxpayer choose between Old and New tax regimes for FY 2023-24.

Profile:
- Gross Income: ₹{gross_income:,.0f}
- Total Deductions: ₹{deductions:,.0f}
- Deduction Breakdown: {deductions_text}
- Tax (Old Regime): ₹{old_tax:,.0f}
- Tax (New Regime): ₹{new_tax:,.0f}

Analysis shows the {recommended.upper()} regime is better.

Provide a 2-3 sentence recommendation explaining:
1. Why this regime is better
2. The specific savings amount
3. One actionable tip

Keep it practical and specific to their situation.

Recommendation:"""
    
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=200,
            ),
            timeout=settings.GROQ_TIMEOUT,
        )
        
        reasoning = response.choices[0].message.content.strip()
        log.info("[RegimeReasoning] AI reasoning generated (%d chars)", len(reasoning))
        return reasoning
        
    except Exception as exc:
        log.warning("[RegimeReasoning] Failed: %s", exc)
        return None


async def _get_investment_suggestions(
    client,
    gross_income: float,
    deduction_breakdown: Dict[str, float],
) -> Optional[List[Dict[str, Any]]]:
    """Get AI-powered investment suggestions."""
    
    section_80c = deduction_breakdown.get("Section80C", 0)
    section_80ccd1b = deduction_breakdown.get("Section80CCD1B", 0)
    section_80d = deduction_breakdown.get("Section80D", 0)
    
    prompt = f"""You are a tax and investment advisor for Indian taxpayers (FY 2023-24).

Client Profile:
- Gross Income: ₹{gross_income:,.0f}
- Section 80C claimed: ₹{section_80c:,.0f} (limit: ₹1,50,000)
- Section 80CCD(1B) claimed: ₹{section_80ccd1b:,.0f} (limit: ₹50,000)
- Section 80D claimed: ₹{section_80d:,.0f} (limit: ₹25,000)

Suggest 3-4 specific investment options to maximize tax savings. For each suggestion, provide:
1. Investment type (ELSS, PPF, NPS, Health Insurance, etc.)
2. Recommended amount
3. Section (80C, 80CCD1B, 80D)
4. Priority (high/medium/low)
5. Brief reason (one sentence)

Return as JSON array:
[
  {{
    "investment_type": "ELSS",
    "amount": 50000,
    "section": "80C",
    "priority": "high",
    "reasoning": "Best for wealth creation with 3-year lock-in"
  }},
  ...
]

JSON:"""
    
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            ),
            timeout=settings.GROQ_TIMEOUT,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON
        suggestions_raw = json.loads(result_text)
        
        # Convert to our format
        suggestions = []
        for s in suggestions_raw:
            amount = float(s.get("amount", 0))
            suggestions.append({
                "category": "investment",
                "section": s.get("section", "80C"),
                "priority": s.get("priority", "medium"),
                "suggestion": f"Invest ₹{amount:,.0f} in {s.get('investment_type', 'tax-saving instrument')}",
                "reasoning": s.get("reasoning", ""),
                "potential_savings": round(amount * 0.20, 2),
                "investment_type": s.get("investment_type", ""),
                "amount": amount,
            })
        
        log.info("[InvestmentSuggestions] AI generated %d suggestions", len(suggestions))
        return suggestions
        
    except Exception as exc:
        log.warning("[InvestmentSuggestions] AI parsing failed: %s", exc)
        return None

# Made with Bob
