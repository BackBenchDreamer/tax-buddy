"""
AI Validation Service
=====================

Provides AI-powered validation of extracted fields using Groq LLM.
This service validates NER extraction results against the original OCR text
to catch and correct common extraction errors.

Key Features:
- Field-specific validation (employee name, PAN, amounts, deductions)
- Confidence-based auto-correction (>0.85) and flagging (<0.40)
- Graceful fallback if Groq API fails
- Structured validation results with reasoning

Design Principles:
- Use AI for validation, not extraction (extraction is done by NER)
- Always provide original value alongside suggestions
- Include reasoning for transparency
- Fast response times (<2s per validation)
"""

import logging
import asyncio
import json
from typing import Any, Dict, List, Optional
from app.core.config import settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Confidence Thresholds
# ---------------------------------------------------------------------------

CONFIDENCE_AUTO_CORRECT = 0.85  # Auto-apply corrections above this
CONFIDENCE_SUGGEST = 0.60       # Suggest corrections between this and auto-correct
CONFIDENCE_FLAG = 0.40          # Flag for review below this


# ---------------------------------------------------------------------------
# Helper: Get Groq Client
# ---------------------------------------------------------------------------

def _get_groq_client():
    """Get Groq client instance. Returns None if API key not configured."""
    if not settings.GROQ_API_KEY:
        log.warning("[AIValidation] Groq API key not configured - AI validation disabled")
        return None
    
    try:
        from groq import AsyncGroq
        # Initialize with API key and timeout
        client = AsyncGroq(
            api_key=settings.GROQ_API_KEY,
            timeout=float(settings.GROQ_TIMEOUT)
        )
        return client
    except ImportError:
        log.error("[AIValidation] groq package not installed - run: pip install groq")
        return None
    except Exception as exc:
        log.error("[AIValidation] Failed to initialize Groq client: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Field-Specific Validation Functions
# ---------------------------------------------------------------------------

async def validate_employee_name(
    extracted_name: str,
    ocr_text: str,
    timeout: float = 5.0
) -> Dict[str, Any]:
    """
    Validate employee name - check if it's a person vs company.
    
    Returns:
    {
        "field_name": "EmployeeName",
        "original_value": str,
        "suggested_value": str or None,
        "confidence": float,
        "reasoning": str,
        "action": "keep" | "correct" | "flag"
    }
    """
    client = _get_groq_client()
    if not client:
        return {
            "field_name": "EmployeeName",
            "original_value": extracted_name,
            "suggested_value": None,
            "confidence": 0.5,
            "reasoning": "AI validation unavailable",
            "action": "keep"
        }
    
    prompt = f"""You are validating data extracted from an Indian Form 16 tax document.

EXTRACTED EMPLOYEE NAME: "{extracted_name}"

CONTEXT FROM OCR TEXT:
{ocr_text[:1500]}

TASK: Determine if the extracted name is the EMPLOYEE (individual person) or the EMPLOYER (company).

Common issues:
- Employee names are typically in Title Case (e.g., "Rajesh Kumar Sharma")
- Employer names contain keywords like LIMITED, PVT, TECHNOLOGIES, SERVICES
- Employee name should appear near "Name of Employee" or employee's PAN
- Employer name appears near "Name of Employer" or employer's TAN

Return JSON:
{{
  "is_employee": true/false,
  "confidence": 0.0-1.0,
  "correct_employee_name": "name if different, or null",
  "reasoning": "brief explanation"
}}

JSON:"""
    
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=200,
            ),
            timeout=timeout,
        )
        
        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)
        
        is_employee = result.get("is_employee", True)
        confidence = float(result.get("confidence", 0.5))
        correct_name = result.get("correct_employee_name")
        reasoning = result.get("reasoning", "AI validation completed")
        
        # Determine action based on confidence
        if not is_employee and confidence > CONFIDENCE_AUTO_CORRECT:
            action = "correct"
        elif not is_employee and confidence > CONFIDENCE_FLAG:
            action = "flag"
        else:
            action = "keep"
        
        log.info("[AIValidation] Employee name: is_employee=%s, confidence=%.2f, action=%s",
                 is_employee, confidence, action)
        
        return {
            "field_name": "EmployeeName",
            "original_value": extracted_name,
            "suggested_value": correct_name if not is_employee else None,
            "confidence": confidence,
            "reasoning": reasoning,
            "action": action
        }
        
    except asyncio.TimeoutError:
        log.error("[AIValidation] Timeout validating employee name")
        return {
            "field_name": "EmployeeName",
            "original_value": extracted_name,
            "suggested_value": None,
            "confidence": 0.5,
            "reasoning": "Validation timeout",
            "action": "keep"
        }
    except json.JSONDecodeError:
        log.warning("[AIValidation] Invalid JSON response for employee name")
        return {
            "field_name": "EmployeeName",
            "original_value": extracted_name,
            "suggested_value": None,
            "confidence": 0.5,
            "reasoning": "Invalid AI response",
            "action": "keep"
        }
    except Exception as exc:
        log.error("[AIValidation] Error validating employee name: %s", exc)
        return {
            "field_name": "EmployeeName",
            "original_value": extracted_name,
            "suggested_value": None,
            "confidence": 0.5,
            "reasoning": f"Validation error: {str(exc)}",
            "action": "keep"
        }


async def validate_pan(
    extracted_pan: str,
    ocr_text: str,
    timeout: float = 5.0
) -> Dict[str, Any]:
    """
    Validate PAN format and consistency.
    
    PAN format: 5 letters + 4 digits + 1 letter (e.g., ABCDE1234F)
    """
    client = _get_groq_client()
    if not client:
        return {
            "field_name": "PAN",
            "original_value": extracted_pan,
            "suggested_value": None,
            "confidence": 0.5,
            "reasoning": "AI validation unavailable",
            "action": "keep"
        }
    
    prompt = f"""You are validating a PAN (Permanent Account Number) extracted from an Indian tax document.

EXTRACTED PAN: "{extracted_pan}"

CONTEXT FROM OCR TEXT:
{ocr_text[:1500]}

TASK: Verify if the PAN is correct and properly formatted.

PAN Format Rules:
- Exactly 10 characters
- Format: AAAAA9999A (5 letters + 4 digits + 1 letter)
- All letters must be uppercase
- Example: ABCDE1234F

Check for:
- OCR errors (O vs 0, I vs 1, S vs 5)
- Missing or extra characters
- Incorrect format

Return JSON:
{{
  "is_valid_format": true/false,
  "confidence": 0.0-1.0,
  "corrected_pan": "corrected PAN if different, or null",
  "reasoning": "brief explanation"
}}

JSON:"""
    
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150,
            ),
            timeout=timeout,
        )
        
        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)
        
        is_valid = result.get("is_valid_format", True)
        confidence = float(result.get("confidence", 0.5))
        corrected_pan = result.get("corrected_pan")
        reasoning = result.get("reasoning", "AI validation completed")
        
        # Determine action
        if not is_valid and confidence > CONFIDENCE_AUTO_CORRECT:
            action = "correct"
        elif not is_valid and confidence > CONFIDENCE_FLAG:
            action = "flag"
        else:
            action = "keep"
        
        log.info("[AIValidation] PAN: is_valid=%s, confidence=%.2f, action=%s",
                 is_valid, confidence, action)
        
        return {
            "field_name": "PAN",
            "original_value": extracted_pan,
            "suggested_value": corrected_pan if not is_valid else None,
            "confidence": confidence,
            "reasoning": reasoning,
            "action": action
        }
        
    except Exception as exc:
        log.error("[AIValidation] Error validating PAN: %s", exc)
        return {
            "field_name": "PAN",
            "original_value": extracted_pan,
            "suggested_value": None,
            "confidence": 0.5,
            "reasoning": f"Validation error: {str(exc)}",
            "action": "keep"
        }


async def validate_amounts(
    extracted_fields: Dict[str, Any],
    ocr_text: str,
    timeout: float = 5.0
) -> List[Dict[str, Any]]:
    """
    Validate numerical amounts (GrossSalary, TaxableIncome, TDS).
    Cross-check that TaxableIncome = GrossSalary - Deductions.
    """
    client = _get_groq_client()
    if not client:
        return []
    
    gross = extracted_fields.get("GrossSalary", 0)
    taxable = extracted_fields.get("TaxableIncome", 0)
    tds = extracted_fields.get("TDS", 0)
    deductions = extracted_fields.get("TotalDeductions", 0)
    
    prompt = f"""You are validating financial amounts extracted from an Indian Form 16.

EXTRACTED VALUES:
- Gross Salary: ₹{gross:,.2f}
- Total Deductions: ₹{deductions:,.2f}
- Taxable Income: ₹{taxable:,.2f}
- TDS: ₹{tds:,.2f}

CONTEXT FROM OCR TEXT:
{ocr_text[:1500]}

TASK: Verify the amounts are consistent and correctly extracted.

Validation Rules:
1. Taxable Income should equal Gross Salary minus Deductions
2. All amounts should be positive
3. TDS should be less than Taxable Income
4. Check for OCR errors in numbers (comma placement, decimal points)

Return JSON array with validation results:
[
  {{
    "field_name": "GrossSalary" | "TaxableIncome" | "TDS",
    "is_correct": true/false,
    "confidence": 0.0-1.0,
    "corrected_value": number or null,
    "reasoning": "brief explanation"
  }}
]

JSON:"""
    
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=300,
            ),
            timeout=timeout,
        )
        
        result_text = response.choices[0].message.content.strip()
        results = json.loads(result_text)
        
        validations = []
        for result in results:
            field_name = result.get("field_name")
            is_correct = result.get("is_correct", True)
            confidence = float(result.get("confidence", 0.5))
            corrected_value = result.get("corrected_value")
            reasoning = result.get("reasoning", "AI validation completed")
            
            # Determine action
            if not is_correct and confidence > CONFIDENCE_AUTO_CORRECT:
                action = "correct"
            elif not is_correct and confidence > CONFIDENCE_FLAG:
                action = "flag"
            else:
                action = "keep"
            
            validations.append({
                "field_name": field_name,
                "original_value": extracted_fields.get(field_name, 0),
                "suggested_value": corrected_value if not is_correct else None,
                "confidence": confidence,
                "reasoning": reasoning,
                "action": action
            })
        
        log.info("[AIValidation] Amounts validated: %d fields", len(validations))
        return validations
        
    except Exception as exc:
        log.error("[AIValidation] Error validating amounts: %s", exc)
        return []


async def validate_deductions(
    extracted_fields: Dict[str, Any],
    ocr_text: str,
    timeout: float = 5.0
) -> Dict[str, Any]:
    """
    Validate deduction totals match breakdown.
    Verify Section 80C + 80D + 80E + etc. = TotalDeductions.
    """
    client = _get_groq_client()
    if not client:
        return {
            "field_name": "TotalDeductions",
            "original_value": extracted_fields.get("TotalDeductions", 0),
            "suggested_value": None,
            "confidence": 0.5,
            "reasoning": "AI validation unavailable",
            "action": "keep"
        }
    
    section_80c = extracted_fields.get("Section80C", 0)
    section_80d = extracted_fields.get("Section80D", 0)
    section_80e = extracted_fields.get("Section80E", 0)
    section_80g = extracted_fields.get("Section80G", 0)
    section_80ccd1b = extracted_fields.get("Section80CCD1B", 0)
    total_deductions = extracted_fields.get("TotalDeductions", 0)
    
    calculated_total = section_80c + section_80d + section_80e + section_80g + section_80ccd1b
    
    prompt = f"""You are validating deduction amounts from an Indian Form 16 Part B.

EXTRACTED DEDUCTIONS:
- Section 80C: ₹{section_80c:,.2f}
- Section 80D: ₹{section_80d:,.2f}
- Section 80E: ₹{section_80e:,.2f}
- Section 80G: ₹{section_80g:,.2f}
- Section 80CCD(1B): ₹{section_80ccd1b:,.2f}
- Total Deductions: ₹{total_deductions:,.2f}

CALCULATED TOTAL: ₹{calculated_total:,.2f}

CONTEXT FROM OCR TEXT (Part B):
{ocr_text[ocr_text.find("PART B"):ocr_text.find("PART B")+2000] if "PART B" in ocr_text else ocr_text[:1500]}

TASK: Verify if the total deductions match the sum of individual sections.

Check for:
- Missing deduction sections
- Incorrect aggregation
- OCR errors in amounts

Return JSON:
{{
  "is_correct": true/false,
  "confidence": 0.0-1.0,
  "corrected_total": number or null,
  "missing_sections": ["list of section names if any"],
  "reasoning": "brief explanation"
}}

JSON:"""
    
    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=250,
            ),
            timeout=timeout,
        )
        
        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)
        
        is_correct = result.get("is_correct", True)
        confidence = float(result.get("confidence", 0.5))
        corrected_total = result.get("corrected_total")
        reasoning = result.get("reasoning", "AI validation completed")
        
        # Determine action
        if not is_correct and confidence > CONFIDENCE_AUTO_CORRECT:
            action = "correct"
        elif not is_correct and confidence > CONFIDENCE_FLAG:
            action = "flag"
        else:
            action = "keep"
        
        log.info("[AIValidation] Deductions: is_correct=%s, confidence=%.2f, action=%s",
                 is_correct, confidence, action)
        
        return {
            "field_name": "TotalDeductions",
            "original_value": total_deductions,
            "suggested_value": corrected_total if not is_correct else None,
            "confidence": confidence,
            "reasoning": reasoning,
            "action": action
        }
        
    except Exception as exc:
        log.error("[AIValidation] Error validating deductions: %s", exc)
        return {
            "field_name": "TotalDeductions",
            "original_value": total_deductions,
            "suggested_value": None,
            "confidence": 0.5,
            "reasoning": f"Validation error: {str(exc)}",
            "action": "keep"
        }


# ---------------------------------------------------------------------------
# Main Validation Function
# ---------------------------------------------------------------------------

async def validate_extracted_fields(
    extracted_fields: Dict[str, Any],
    ocr_text: str,
    enable_ai: bool = True
) -> Dict[str, Any]:
    """
    Validate all extracted fields using AI.
    
    Parameters
    ----------
    extracted_fields : dict
        Fields extracted by NER service
    ocr_text : str
        Original OCR text for context
    enable_ai : bool
        Enable/disable AI validation (default: True)
    
    Returns
    -------
    dict
        {
            "validations": [list of validation results],
            "corrections_applied": [list of auto-corrected fields],
            "flags": [list of fields needing review],
            "summary": {
                "total_fields": int,
                "validated": int,
                "corrected": int,
                "flagged": int
            }
        }
    """
    if not enable_ai:
        log.info("[AIValidation] AI validation disabled")
        return {
            "validations": [],
            "corrections_applied": [],
            "flags": [],
            "summary": {
                "total_fields": len(extracted_fields),
                "validated": 0,
                "corrected": 0,
                "flagged": 0
            }
        }
    
    log.info("[AIValidation] Starting validation for %d fields", len(extracted_fields))
    
    validations = []
    corrections_applied = []
    flags = []
    
    try:
        # Run validations concurrently for speed
        tasks = []
        
        # Validate employee name
        if extracted_fields.get("EmployeeName"):
            tasks.append(validate_employee_name(
                extracted_fields["EmployeeName"],
                ocr_text
            ))
        
        # Validate PAN
        if extracted_fields.get("PAN"):
            tasks.append(validate_pan(
                extracted_fields["PAN"],
                ocr_text
            ))
        
        # Validate amounts
        if any(k in extracted_fields for k in ["GrossSalary", "TaxableIncome", "TDS"]):
            tasks.append(validate_amounts(extracted_fields, ocr_text))
        
        # Validate deductions
        if extracted_fields.get("TotalDeductions") or extracted_fields.get("Section80C"):
            tasks.append(validate_deductions(extracted_fields, ocr_text))
        
        # Wait for all validations with timeout
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=10.0  # Max 10 seconds for all validations
        )
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                log.error("[AIValidation] Validation task failed: %s", result)
                continue
            
            if isinstance(result, list):
                # Multiple validations (e.g., amounts)
                validations.extend(result)
                for val in result:
                    if val["action"] == "correct":
                        corrections_applied.append(val)
                    elif val["action"] == "flag":
                        flags.append(val)
            elif isinstance(result, dict):
                # Single validation
                validations.append(result)
                if result["action"] == "correct":
                    corrections_applied.append(result)
                elif result["action"] == "flag":
                    flags.append(result)
        
        log.info("[AIValidation] Completed: %d validations, %d corrections, %d flags",
                 len(validations), len(corrections_applied), len(flags))
        
        return {
            "validations": validations,
            "corrections_applied": corrections_applied,
            "flags": flags,
            "summary": {
                "total_fields": len(extracted_fields),
                "validated": len(validations),
                "corrected": len(corrections_applied),
                "flagged": len(flags)
            }
        }
        
    except asyncio.TimeoutError:
        log.error("[AIValidation] Overall validation timeout")
        return {
            "validations": validations,
            "corrections_applied": corrections_applied,
            "flags": flags,
            "summary": {
                "total_fields": len(extracted_fields),
                "validated": len(validations),
                "corrected": len(corrections_applied),
                "flagged": len(flags)
            }
        }
    except Exception as exc:
        log.error("[AIValidation] Validation failed: %s", exc)
        return {
            "validations": [],
            "corrections_applied": [],
            "flags": [],
            "summary": {
                "total_fields": len(extracted_fields),
                "validated": 0,
                "corrected": 0,
                "flagged": 0
            }
        }


# ---------------------------------------------------------------------------
# Apply Corrections
# ---------------------------------------------------------------------------

def apply_corrections(
    extracted_fields: Dict[str, Any],
    validation_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply high-confidence corrections to extracted fields.
    
    Parameters
    ----------
    extracted_fields : dict
        Original extracted fields
    validation_result : dict
        Result from validate_extracted_fields()
    
    Returns
    -------
    dict
        Corrected fields
    """
    corrected_fields = extracted_fields.copy()
    
    for correction in validation_result.get("corrections_applied", []):
        field_name = correction["field_name"]
        suggested_value = correction["suggested_value"]
        
        if suggested_value is not None:
            log.info("[AIValidation] Auto-correcting %s: %s → %s",
                     field_name, corrected_fields.get(field_name), suggested_value)
            corrected_fields[field_name] = suggested_value
    
    return corrected_fields


# Made with Bob