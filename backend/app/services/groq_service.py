"""
Groq API Integration Service
=============================

Provides targeted AI assistance for:
1. Ambiguous OCR field resolution
2. NER fallback for failed extractions
3. Validation mismatch explanations
4. Tax regime recommendations

Design Principles:
- Never use for bulk extraction (use only for specific edge cases)
- Always validate responses against expected formats
- Graceful fallbacks if API fails
- Async operations with timeouts
"""

import logging
import asyncio
from typing import Any, Dict, List, Optional
import json

from app.core.config import settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Groq Client Initialization
# ---------------------------------------------------------------------------

def _get_groq_client():
    """Get Groq client instance. Returns None if API key not configured."""
    if not settings.GROQ_API_KEY:
        log.warning("[Groq] API key not configured - AI assistance disabled")
        return None
    
    try:
        from groq import AsyncGroq
        client = AsyncGroq(
            api_key=settings.GROQ_API_KEY,
            timeout=settings.GROQ_TIMEOUT,
        )
        log.info("[Groq] Client initialized with model=%s", settings.GROQ_MODEL)
        return client
    except ImportError:
        log.error("[Groq] groq package not installed - run: pip install groq")
        return None
    except Exception as exc:
        log.error("[Groq] Failed to initialize client: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 1. Ambiguous OCR Field Resolution
# ---------------------------------------------------------------------------

async def resolve_ambiguous_field(
    ocr_snippet: str,
    field_name: str,
    expected_format: str,
) -> Optional[str]:
    """Ask Groq to resolve an ambiguous OCR extraction.
    
    Parameters
    ----------
    ocr_snippet : str
        The garbled or unclear text from OCR
    field_name : str
        The tax field we're trying to extract (e.g., "GrossSalary", "PAN")
    expected_format : str
        Description of expected format (e.g., "Indian currency amount", "10-character alphanumeric")
    
    Returns
    -------
    str or None
        Resolved value, or None if resolution failed
    """
    client = _get_groq_client()
    if not client:
        return None
    
    prompt = f"""You are a tax document OCR expert. The following text was extracted from an Indian tax form but is unclear:

OCR Text: "{ocr_snippet}"

Field: {field_name}
Expected Format: {expected_format}

Task: Identify the most likely correct value for this field. Return ONLY the extracted value, nothing else.
If you cannot determine the value with confidence, return "UNABLE_TO_RESOLVE".

Value:"""
    
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temperature for deterministic output
                max_tokens=100,
            ),
            timeout=settings.GROQ_TIMEOUT,
        )
        
        result = response.choices[0].message.content.strip()
        
        if result == "UNABLE_TO_RESOLVE" or not result:
            log.warning("[Groq] Could not resolve field: %s", field_name)
            return None
        
        log.info("[Groq] Resolved %s: %s", field_name, result)
        return result
        
    except asyncio.TimeoutError:
        log.error("[Groq] Timeout resolving field: %s", field_name)
        return None
    except Exception as exc:
        log.error("[Groq] Error resolving field %s: %s", field_name, exc)
        return None


# ---------------------------------------------------------------------------
# 2. NER Fallback Extraction
# ---------------------------------------------------------------------------

async def extract_entity_fallback(
    text_block: str,
    entity_type: str,
) -> Optional[Dict[str, Any]]:
    """Use Groq as NER fallback when regex/transformer fails.
    
    Parameters
    ----------
    text_block : str
        Relevant text block from OCR
    entity_type : str
        Entity to extract (e.g., "PAN", "TAN", "EmployerName")
    
    Returns
    -------
    dict or None
        {"value": str, "confidence": float} or None
    """
    client = _get_groq_client()
    if not client:
        return None
    
    prompt = f"""Extract the {entity_type} from this Indian tax document text:

Text: "{text_block}"

Return a JSON object with:
- "value": the extracted {entity_type} (or null if not found)
- "confidence": your confidence level (0.0 to 1.0)

JSON:"""
    
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=150,
            ),
            timeout=settings.GROQ_TIMEOUT,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Parse JSON response
        try:
            result = json.loads(result_text)
            if result.get("value") and result.get("confidence", 0) > 0.5:
                log.info("[Groq] Extracted %s: %s (conf=%.2f)", 
                        entity_type, result["value"], result["confidence"])
                return result
        except json.JSONDecodeError:
            log.warning("[Groq] Invalid JSON response for %s", entity_type)
        
        return None
        
    except asyncio.TimeoutError:
        log.error("[Groq] Timeout extracting entity: %s", entity_type)
        return None
    except Exception as exc:
        log.error("[Groq] Error extracting %s: %s", entity_type, exc)
        return None


# ---------------------------------------------------------------------------
# 3. Validation Mismatch Explanation
# ---------------------------------------------------------------------------

async def explain_validation_issues(
    issues: List[Dict[str, Any]],
) -> Dict[str, str]:
    """Generate plain-English explanations for validation mismatches.
    
    Parameters
    ----------
    issues : list of dict
        Validation issues from validation_service
        Each: {"type": str, "message": str, "severity": str, "field": str}
    
    Returns
    -------
    dict
        Maps issue type to friendly explanation
    """
    client = _get_groq_client()
    if not client or not issues:
        return {}
    
    # Limit to top 5 issues to avoid token limits
    issues_subset = issues[:5]
    
    issues_text = "\n".join([
        f"- {issue['type']}: {issue['message']} (severity: {issue['severity']})"
        for issue in issues_subset
    ])
    
    prompt = f"""You are a tax filing assistant helping an Indian taxpayer understand validation errors in their tax documents.

The following issues were found when cross-checking Form 16 and Form 26AS:

{issues_text}

For each issue, provide:
1. What it means in simple terms
2. What the user should do to fix it

Format as JSON: {{"issue_type": "explanation", ...}}

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
        
        try:
            explanations = json.loads(result_text)
            log.info("[Groq] Generated explanations for %d issues", len(explanations))
            return explanations
        except json.JSONDecodeError:
            log.warning("[Groq] Invalid JSON response for explanations")
            return {}
        
    except asyncio.TimeoutError:
        log.error("[Groq] Timeout generating explanations")
        return {}
    except Exception as exc:
        log.error("[Groq] Error generating explanations: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# 4. Tax Regime Recommendation
# ---------------------------------------------------------------------------

async def recommend_tax_regime(
    gross_income: float,
    deductions: Dict[str, float],
    old_regime_tax: float,
    new_regime_tax: float,
) -> Optional[str]:
    """Get AI recommendation on which tax regime is better.
    
    Parameters
    ----------
    gross_income : float
        Gross salary
    deductions : dict
        Deductions claimed (80C, 80D, etc.)
    old_regime_tax : float
        Tax under old regime
    new_regime_tax : float
        Tax under new regime
    
    Returns
    -------
    str or None
        2-3 sentence plain-language recommendation
    """
    client = _get_groq_client()
    if not client:
        return None
    
    deductions_text = ", ".join([f"{k}: ₹{v:,.0f}" for k, v in deductions.items()])
    
    prompt = f"""You are a tax advisor helping an Indian taxpayer choose between Old and New tax regimes.

Profile:
- Gross Income: ₹{gross_income:,.0f}
- Deductions: {deductions_text}
- Tax (Old Regime): ₹{old_regime_tax:,.0f}
- Tax (New Regime): ₹{new_regime_tax:,.0f}

Provide a 2-3 sentence recommendation on which regime is better for this taxpayer and why. Be specific about the savings.

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
        
        recommendation = response.choices[0].message.content.strip()
        log.info("[Groq] Generated regime recommendation (%d chars)", len(recommendation))
        return recommendation
        
    except asyncio.TimeoutError:
        log.error("[Groq] Timeout generating recommendation")
        return None
    except Exception as exc:
        log.error("[Groq] Error generating recommendation: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Convenience Wrapper for Sync Contexts
# ---------------------------------------------------------------------------

def run_async_groq(coro):
    """Run an async Groq function in a sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

# Made with Bob
