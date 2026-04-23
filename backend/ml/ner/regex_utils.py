"""
Deterministic regex-based extraction for Indian tax documents (Form 16).

Design principles
-----------------
* Every critical field has its own function — easy to tune independently.
* Contextual patterns: look for the VALUE *near* a keyword, not just anywhere.
* Returns a flat dict with EXACT keys expected by the validation service.
* Acts as the primary extraction layer; ML model results are supplementary.

Required output keys
--------------------
PAN, TAN, EmployerName, EmployeeName, GrossSalary, TaxableIncome,
TDS, AssessmentYear, Section80C, Section80D
"""

import re
import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Low-level compiled patterns
# ---------------------------------------------------------------------------

# PAN: 5 uppercase letters, 4 digits, 1 uppercase letter  e.g. ABCDE1234F
PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")

# TAN: 4 uppercase letters, 5 digits, 1 uppercase letter  e.g. MUMS15654C
TAN_RE = re.compile(r"\b([A-Z]{4}[0-9]{5}[A-Z])\b")

# Assessment year: YYYY-YY or YYYY-YYYY  e.g. 2023-24  2023-2024
AY_RE = re.compile(r"\b(20\d{2}-(?:20)?\d{2})\b")

# Indian numeric amount: handles 8,73,898 or 873898 or 873898.00
AMOUNT_RE = re.compile(r"\b(\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d{5,}(?:\.\d{1,2})?)\b")

def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def _is_postal_code(raw: str, val: float) -> bool:
    """Return True if this looks like an Indian 6-digit postal code.

    Key distinction: financial amounts always have decimals (751585.00),
    postal codes are whole numbers (410210, 560075).
    """
    if "." in raw:          # has decimal → it's a financial figure, not a postal code
        return False
    if "," in raw:          # comma-formatted (e.g. 1,50,000) → financial
        return False
    return 100000 <= val <= 999999 and val == int(val)


def _find_amount_near(text: str, *keywords, window: int = 120) -> Optional[float]:
    """Find the first valid large amount within `window` chars AFTER any keyword match."""
    for kw in keywords:
        m = re.search(kw, text, re.IGNORECASE)
        if m:
            # Search in a window AFTER the keyword (not before)
            snippet = text[m.end(): m.end() + window]
            for am in AMOUNT_RE.finditer(snippet):
                try:
                    val = _to_float(am.group())
                    if val >= 10000 and not _is_postal_code(am.group(), val):
                        return val
                except ValueError:
                    continue
    return None


def _find_amount_on_same_line(text: str, *keywords) -> Optional[float]:
    """Find the first valid large amount within 150 chars AFTER any keyword match."""
    for kw in keywords:
        m = re.search(kw, text, re.IGNORECASE)
        if not m:
            continue
        window = text[m.end(): m.end() + 150].replace('|', ' ')
        for am in AMOUNT_RE.finditer(window):
            raw = am.group()
            try:
                val = _to_float(raw)
                if val >= 10000 and not _is_postal_code(raw, val):
                    return val
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Individual extractors
# ---------------------------------------------------------------------------

def extract_pan(text: str) -> Optional[str]:
    """Extract PAN — look near 'PAN of Employee' label first."""
    # Try contextual match near label
    m = re.search(r"PAN\s+of\s+(?:the\s+)?(?:Employee|Deductee)[^\w]*([A-Z]{5}[0-9]{4}[A-Z])", text, re.IGNORECASE)
    if m:
        log.debug("PAN (contextual): %s", m.group(1))
        return m.group(1)

    # Try PAN of Employee: VALUE pattern
    m = re.search(r"PAN\s+of\s+Employee\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])", text, re.IGNORECASE)
    if m:
        return m.group(1)

    # Fallback: first PAN-pattern match anywhere
    all_pans = PAN_RE.findall(text)
    # Filter out TAN-like patterns (TAN starts with 4 alpha + 5 digit + 1 alpha)
    # A PAN with 4th char being 'P' (person) is typical but not mandated — just return first
    if all_pans:
        log.debug("PAN (regex fallback): %s", all_pans[0])
        return all_pans[0]
    return None


def extract_tan(text: str) -> Optional[str]:
    """Extract TAN — look near 'TAN of Employer/Deductor' label first."""
    m = re.search(r"TAN\s+of\s+(?:Employer|Deductor)[^\w]*([A-Z]{4}[0-9]{5}[A-Z])", text, re.IGNORECASE)
    if m:
        log.debug("TAN (contextual): %s", m.group(1))
        return m.group(1)

    m = re.search(r"TAN\s*[:\-]?\s*([A-Z]{4}[0-9]{5}[A-Z])", text, re.IGNORECASE)
    if m:
        return m.group(1)

    all_tans = TAN_RE.findall(text)
    if all_tans:
        log.debug("TAN (regex fallback): %s", all_tans[0])
        return all_tans[0]
    return None


def extract_assessment_year(text: str) -> Optional[str]:
    """Extract Assessment Year."""
    m = re.search(r"Assessment\s+Year\s*[:\-]?\s*(20\d{2}[-–]\d{2,4})", text, re.IGNORECASE)
    if m:
        return m.group(1)
    all_ay = AY_RE.findall(text)
    if all_ay:
        return all_ay[0]
    return None


def extract_employer_name(text: str) -> Optional[str]:
    """Extract employer name from Form 16."""
    # Try explicit label pattern
    for pat in [
        r"Name\s+of\s+the\s+employer\s*[:\-]\s*([A-Za-z][A-Za-z0-9 &.,()\-]{5,80})",
        r"employer\s*[:\-]\s*([A-Z][A-Za-z0-9 &.,()\-]{5,80})",
    ]:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip().rstrip('.,').strip()
            if len(name) > 5:
                log.debug("EmployerName (label): %s", name)
                return name

    # Look for all-caps company name patterns (common in Form 16)
    # Must contain at least 2 words and end with PRIVATE/LIMITED/LTD/SERVICES/TECHNOLOGIES
    m = re.search(
        r"([A-Z][A-Z &]{5,}(?:PRIVATE\s+LIMITED|LIMITED|PVT\.?\s*LTD|TECHNOLOGIES?|SERVICES?))",
        text
    )
    if m:
        name = m.group(1).strip()
        if len(name) > 8:
            log.debug("EmployerName (all-caps pattern): %s", name)
            return name

    return None


def extract_employee_name(text: str) -> Optional[str]:
    """Extract employee name."""
    patterns = [
        r"Name\s+and\s+address\s+of\s+the\s+Employee[^\n]*\n\s*([A-Z][A-Za-z ]{5,60})",
        r"Name.*?(?:Employee|Deductee)\s*[:\-]\s*([A-Za-z][A-Za-z ]{5,60})",
        r"employee\s*[:\-]\s*([A-Za-z][A-Za-z ]{5,60})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if len(name) > 3:
                return name
    return None


def extract_gross_salary(text: str) -> Optional[float]:
    """Extract gross salary from Form 16 Part B.

    Actual OCR patterns seen:
      'Gross total income (6+8) | 751585.00'
      'Total amount of salary received from current employer  803985.00'
      'Income chargeable under the head "Salaries" ... 751585.00'
      'Salary as per provisions contained in section 17(1) 872769.00'
    """
    keywords = [
        r"Gross\s+total\s+income",
        r"Total\s+amount\s+of\s+salary\s+received\s+from\s+current\s+employer",
        r"Income\s+chargeable\s+under\s+the\s+head\s+.{0,10}Salaries",
        r"Salary\s+as\s+per\s+provisions\s+contained\s+in\s+section\s+17\(1\)",
        r"Gross\s+Salary",
    ]
    val = _find_amount_on_same_line(text, *keywords)
    if val:
        log.debug("GrossSalary (line match): %s", val)
        return val
    val = _find_amount_near(text, *keywords, window=150)
    if val:
        log.debug("GrossSalary (proximity): %s", val)
        return val
    return None


def extract_taxable_income(text: str) -> Optional[float]:
    """Extract total taxable income.

    Actual OCR patterns seen:
      'Total taxable income (9-11) 604280.00'
    """
    keywords = [
        r"Total\s+taxable\s+income",
        r"Net\s+taxable\s+income",
        r"Taxable\s+income",
    ]
    val = _find_amount_on_same_line(text, *keywords)
    if val:
        log.debug("TaxableIncome (line match): %s", val)
        return val
    val = _find_amount_near(text, *keywords, window=100)
    if val:
        log.debug("TaxableIncome (proximity): %s", val)
        return val
    return None


def extract_tds(text: str) -> Optional[float]:
    """Extract TDS / tax payable.

    Actual OCR patterns seen:
      'Tax payable (13+15+16-14) 34690.00'
      'Net tax payable (17-18) 34690.00'
    """
    keywords = [
        r"Net\s+tax\s+payable",
        r"Tax\s+payable\s*\(",
        r"Total\s+tax\s+deducted\s+at\s+source",
        r"Total\s+(?:amount\s+of\s+)?TDS",
        r"Tax\s+deducted\s+at\s+source",
    ]
    val = _find_amount_on_same_line(text, *keywords)
    if val:
        log.debug("TDS (line match): %s", val)
        return val
    val = _find_amount_near(text, *keywords, window=100)
    if val:
        log.debug("TDS (proximity): %s", val)
        return val
    return None


def extract_section80c(text: str) -> Optional[float]:
    """Extract Section 80C deduction.

    Actual OCR patterns seen:
      'Total deduction under section 80C, 80CCC and 80CCD(1) 147305.00'
    """
    # Prefer the total deduction line
    val = _find_amount_on_same_line(
        text,
        r"Total\s+deduction\s+under\s+section\s+80C",
        r"Aggregate.*80C",
    )
    if val:
        return val
    # Fallback: 80C line
    val = _find_amount_on_same_line(text, r"section\s+80C\b", r"\b80C\b")
    return val


def extract_section80d(text: str) -> Optional[float]:
    """Extract Section 80D deduction (health insurance)."""
    val = _find_amount_on_same_line(
        text,
        r"health\s+insurance\s+premia\s+under\s+section\s+80D",
        r"section\s+80D\b",
        r"\b80D\b",
    )
    return val


# ---------------------------------------------------------------------------
# Flat dict extractor (primary interface)
# ---------------------------------------------------------------------------

def extract_fields(text: str) -> Dict[str, Any]:
    """Run all extractors and return a flat dict with exact validation keys.

    This is the PRIMARY extraction interface. Returns only non-None values.
    """
    log.info("[NER-Regex] Running deterministic field extraction …")

    pan           = extract_pan(text)
    tan           = extract_tan(text)
    ay            = extract_assessment_year(text)
    employer      = extract_employer_name(text)
    employee      = extract_employee_name(text)
    gross_salary  = extract_gross_salary(text)
    taxable_income = extract_taxable_income(text)
    tds           = extract_tds(text)
    s80c          = extract_section80c(text)
    s80d          = extract_section80d(text)

    fields: Dict[str, Any] = {}
    if pan:            fields["PAN"]            = pan
    if tan:            fields["TAN"]            = tan
    if ay:             fields["AssessmentYear"] = ay
    if employer:       fields["EmployerName"]   = employer
    if employee:       fields["EmployeeName"]   = employee
    if gross_salary:   fields["GrossSalary"]    = gross_salary
    if taxable_income: fields["TaxableIncome"]  = taxable_income
    if tds:            fields["TDS"]            = tds
    if s80c:           fields["Section80C"]     = s80c
    if s80d:           fields["Section80D"]     = s80d

    log.info(
        "[NER-Regex] Extracted %d fields: %s",
        len(fields),
        list(fields.keys()),
    )
    return fields


# ---------------------------------------------------------------------------
# Legacy list-based interface (for NERService merge)
# ---------------------------------------------------------------------------

def extract_all(text: str) -> List[Dict[str, Any]]:
    """Return entities as a list of {label, value, confidence, source} dicts.

    Used by NERService for merge with transformer output.
    Each entry uses the EXACT field names required by validation.
    """
    fields = extract_fields(text)
    entities: List[Dict[str, Any]] = []

    for label, value in fields.items():
        entities.append({
            "label": label,
            "value": str(value),
            "confidence": 1.0,
            "source": "regex",
            "start": 0,
            "end": 0,
        })

    return entities
