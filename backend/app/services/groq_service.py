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

# Thread-local storage for user API keys
import threading
_thread_local = threading.local()


def set_user_api_key(api_key: Optional[str]):
    """Set API key for current request context (thread-local)."""
    _thread_local.user_api_key = api_key


def get_user_api_key() -> Optional[str]:
    """Get API key from current request context."""
    return getattr(_thread_local, 'user_api_key', None)


def clear_user_api_key():
    """Clear API key from current request context."""
    if hasattr(_thread_local, 'user_api_key'):
        delattr(_thread_local, 'user_api_key')


def _get_groq_client(api_key: Optional[str] = None):
    """Get Groq client instance. Returns None if API key not configured.
    
    Parameters
    ----------
    api_key : str, optional
        User-provided API key. If None, checks thread-local storage, then falls back to settings.
    """
    # Priority: explicit parameter > thread-local > server config
    effective_key = api_key or get_user_api_key() or settings.GROQ_API_KEY
    
    if not effective_key:
        log.warning("[Groq] API key not configured - AI assistance disabled")
        return None
    
    try:
        from groq import AsyncGroq
        # Initialize with API key and timeout
        client = AsyncGroq(
            api_key=effective_key,
            timeout=float(settings.GROQ_TIMEOUT)
        )
        
        # Log source of API key (without exposing the key itself)
        if api_key:
            source = "user-provided"
        elif get_user_api_key():
            source = "session"
        else:
            source = "server-config"
        
        log.info("[Groq] Client initialized with model=%s (source=%s)", settings.GROQ_MODEL, source)
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
        
        content = response.choices[0].message.content
        if content is None:
            log.warning("[Groq] Empty response for field: %s", field_name)
            return None
        
        result = content.strip()
        
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

You must respond with ONLY a valid JSON object, nothing else. No markdown, no explanation.

Format:
{{"value": "extracted_value_or_null", "confidence": 0.95}}

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
        
        content = response.choices[0].message.content
        if content is None:
            log.warning("[Groq] Empty response for entity extraction: %s", entity_type)
            return None
        
        result_text = content.strip()
        
        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        # Parse JSON response
        try:
            result = json.loads(result_text)
            if result.get("value") and result.get("confidence", 0) > 0.5:
                log.info("[Groq] Extracted %s: %s (conf=%.2f)",
                        entity_type, result["value"], result["confidence"])
                return result
        except json.JSONDecodeError:
            log.warning("[Groq] Invalid JSON response for %s: %s", entity_type, result_text[:100])
        
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

For each issue, provide a simple explanation and what to do.

You must respond with ONLY a valid JSON object, nothing else. No markdown, no explanation.

Format:
{{"salary_mismatch": "Your Form 16 shows...", "tds_mismatch": "The TDS amount..."}}

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
        
        content = response.choices[0].message.content
        if content is None:
            log.warning("[Groq] Empty response for validation explanation")
            return {}
        
        result_text = content.strip()
        
        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        try:
            explanations = json.loads(result_text)
            log.info("[Groq] Generated explanations for %d issues", len(explanations))
            return explanations
        except json.JSONDecodeError:
            log.warning("[Groq] Invalid JSON response for explanations: %s", result_text[:100])
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
        
        content = response.choices[0].message.content
        if content is None:
            log.warning("[Groq] Empty response for tax recommendation")
            return "Unable to generate recommendation."
        
        recommendation = content.strip()
        log.info("[Groq] Generated regime recommendation (%d chars)", len(recommendation))
        return recommendation
        
    except asyncio.TimeoutError:
        log.error("[Groq] Timeout generating recommendation")
        return None
    except Exception as exc:
        log.error("[Groq] Error generating recommendation: %s", exc)
        return None


# ---------------------------------------------------------------------------
# 5. API Key Testing
# ---------------------------------------------------------------------------

async def test_api_key(api_key: str) -> Dict[str, Any]:
    """Test if an API key is valid by making a simple API call.
    
    Parameters
    ----------
    api_key : str
        The API key to test
    
    Returns
    -------
    dict
        {"valid": bool, "message": str, "model": str or None}
    """
    try:
        from groq import AsyncGroq
        
        client = AsyncGroq(
            api_key=api_key,
            timeout=10.0  # Short timeout for testing
        )
        
        # Make a minimal API call to test the key
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=5,
            ),
            timeout=10.0,
        )
        
        log.info("[Groq] API key test successful")
        return {
            "valid": True,
            "message": "API key is valid and working",
            "model": settings.GROQ_MODEL
        }
        
    except asyncio.TimeoutError:
        log.error("[Groq] API key test timeout")
        return {
            "valid": False,
            "message": "API request timed out",
            "model": None
        }
    except Exception as exc:
        error_msg = str(exc)
        log.error("[Groq] API key test failed: %s", error_msg)
        
        # Provide user-friendly error messages
        if "401" in error_msg or "authentication" in error_msg.lower():
            message = "Invalid API key - please check your Groq API key"
        elif "rate" in error_msg.lower() or "quota" in error_msg.lower():
            message = "API rate limit exceeded - please try again later"
        else:
            message = f"API key test failed: {error_msg}"
        
        return {
            "valid": False,
            "message": message,
            "model": None
        }


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
