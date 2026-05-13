"""
Deterministic regex-based extraction for Indian tax documents (Form 16).

Architecture
------------
1. SECTION PARSING — Split OCR text into PART A and PART B.
2. FIELD EXTRACTION — Label-aware keyword matching, NOT random scanning.
3. FALLBACK — Line-by-line keyword search with nearest-number extraction.

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
from typing import Any, Dict, List, Optional, Tuple

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
AMOUNT_RE = re.compile(r"\b(\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d{4,}(?:\.\d{1,2})?)\b")


def _to_float(raw: str) -> float:
    return float(raw.replace(",", ""))


def _is_postal_code(raw: str, val: float) -> bool:
    """Return True if this looks like an Indian 6-digit postal code."""
    if "." in raw:
        return False
    if "," in raw:
        return False
    return 100000 <= val <= 999999 and val == int(val)


# ---------------------------------------------------------------------------
# Section Parsing — Split Form 16 into PART A / PART B
# ---------------------------------------------------------------------------

def split_sections(text: str) -> Tuple[str, str, str]:
    """Split Form 16 OCR text into (part_a, part_b, full_text).

    Looks for "PART A" and "PART B" markers.
    If not found, returns full text for both (fallback mode).
    """
    text_upper = text.upper()

    # Find PART B first (it's the more important section)
    part_b_markers = [
        r"PART\s*[-—]?\s*B\b",
        r"DETAILS\s+OF\s+SALARY",
        r"ANNEXURE.*PART\s*B",
    ]

    part_a_markers = [
        r"PART\s*[-—]?\s*A\b",
        r"CERTIFICATE.*SECTION\s+203",
        r"FORM\s+NO\.?\s*16",
    ]

    part_b_start = len(text)  # default: end of text
    for pat in part_b_markers:
        m = re.search(pat, text_upper)
        if m:
            part_b_start = m.start()
            log.info("[SECTION] Found PART B marker at char %d", part_b_start)
            break

    part_a_text = text[:part_b_start]
    part_b_text = text[part_b_start:]

    if part_b_start == len(text):
        log.warning("[SECTION] No PART B marker found — using full text for both sections")
        part_a_text = text
        part_b_text = text

    log.info("[SECTION] PART A: %d chars, PART B: %d chars", len(part_a_text), len(part_b_text))
    return part_a_text, part_b_text, text


# ---------------------------------------------------------------------------
# Amount extraction helpers
# ---------------------------------------------------------------------------

def _find_amount_on_same_line(text: str, *keywords, min_val: float = 1000) -> Optional[float]:
    """Find the first valid amount AFTER any keyword match on the same logical line."""
    for kw in keywords:
        m = re.search(kw, text, re.IGNORECASE)
        if not m:
            continue
        # Search in a window after the keyword (same line ~ 200 chars)
        window = text[m.end(): m.end() + 200].replace('|', ' ')
        for am in AMOUNT_RE.finditer(window):
            raw = am.group()
            try:
                val = _to_float(raw)
                if val >= min_val and not _is_postal_code(raw, val):
                    return val
            except ValueError:
                continue
    return None


def _find_amount_near(text: str, *keywords, window: int = 150, min_val: float = 1000) -> Optional[float]:
    """Find the first valid amount within `window` chars AFTER any keyword match."""
    for kw in keywords:
        m = re.search(kw, text, re.IGNORECASE)
        if m:
            snippet = text[m.end(): m.end() + window]
            for am in AMOUNT_RE.finditer(snippet):
                try:
                    val = _to_float(am.group())
                    if val >= min_val and not _is_postal_code(am.group(), val):
                        return val
                except ValueError:
                    continue
    return None


def _find_all_amounts_on_line(text: str, keyword: str) -> List[float]:
    """Find ALL valid amounts after a keyword match (for multi-column rows)."""
    results = []
    m = re.search(keyword, text, re.IGNORECASE)
    if not m:
        return results
    window = text[m.end(): m.end() + 300].replace('|', ' ')
    for am in AMOUNT_RE.finditer(window):
        raw = am.group()
        try:
            val = _to_float(raw)
            if val >= 100:  # lower threshold for tax amounts
                results.append(val)
        except ValueError:
            continue
    return results


# ---------------------------------------------------------------------------
# Individual extractors
# ---------------------------------------------------------------------------

def extract_pan(text: str, part_a: str) -> Optional[str]:
    """Extract PAN — look near 'PAN of Employee' label first (in PART A)."""
    # Try contextual match in PART A
    for pat in [
        r"PAN\s+of\s+(?:the\s+)?(?:Employee|Deductee)[^A-Z]*([A-Z]{5}[0-9]{4}[A-Z])",
        r"PAN\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])",
    ]:
        m = re.search(pat, part_a, re.IGNORECASE)
        if m:
            log.info("[EXTRACT] PAN (PART A contextual): %s", m.group(1))
            return m.group(1)

    # Fallback: search full text
    all_pans = PAN_RE.findall(text)
    if all_pans:
        log.info("[EXTRACT] PAN (fallback): %s", all_pans[0])
        return all_pans[0]
    return None


def extract_tan(text: str, part_a: str) -> Optional[str]:
    """Extract TAN — look near 'TAN of Employer/Deductor' label (in PART A)."""
    for pat in [
        r"TAN\s+of\s+(?:the\s+)?(?:Employer|Deductor)[^A-Z]*([A-Z]{4}[0-9]{5}[A-Z])",
        r"TAN\s*[:\-]?\s*([A-Z]{4}[0-9]{5}[A-Z])",
    ]:
        m = re.search(pat, part_a, re.IGNORECASE)
        if m:
            log.info("[EXTRACT] TAN (PART A contextual): %s", m.group(1))
            return m.group(1)

    all_tans = TAN_RE.findall(text)
    if all_tans:
        log.info("[EXTRACT] TAN (fallback): %s", all_tans[0])
        return all_tans[0]
    return None


def extract_assessment_year(text: str, part_a: str) -> Optional[str]:
    """Extract Assessment Year."""
    m = re.search(r"Assessment\s+Year\s*[:\-]?\s*(20\d{2}[-–]\d{2,4})", part_a, re.IGNORECASE)
    if m:
        log.info("[EXTRACT] AssessmentYear (PART A): %s", m.group(1))
        return m.group(1)
    all_ay = AY_RE.findall(text)
    if all_ay:
        log.info("[EXTRACT] AssessmentYear (fallback): %s", all_ay[0])
        return all_ay[0]
    return None


def extract_employer_name(text: str, part_a: str) -> Optional[str]:
    """Extract employer name from Form 16 PART A."""
    for pat in [
        r"Name\s+of\s+the\s+employer\s*[:\-]\s*([A-Za-z][A-Za-z0-9 &.,()'\-]{5,80})",
        r"employer\s*[:\-]\s*([A-Z][A-Za-z0-9 &.,()'\-]{5,80})",
    ]:
        m = re.search(pat, part_a, re.IGNORECASE)
        if m:
            name = m.group(1).strip().rstrip('.,').strip()
            if len(name) > 5:
                log.info("[EXTRACT] EmployerName (label): %s", name)
                return name

    # All-caps company name pattern
    m = re.search(
        r"([A-Z][A-Z &]{5,}(?:PRIVATE\s+LIMITED|LIMITED|PVT\.?\s*LTD|TECHNOLOGIES?|SERVICES?))",
        text
    )
    if m:
        name = m.group(1).strip()
        if len(name) > 8:
            log.info("[EXTRACT] EmployerName (all-caps pattern): %s", name)
            return name
    return None


def extract_employee_name(text: str, part_a: str) -> Optional[str]:
    """Extract employee name with enhanced disambiguation.
    
    Strategy:
    1. Look for "Name and address of the Employee" section
    2. Extract name from next line (not same line as employer)
    3. Avoid company keywords (LIMITED, PVT, LTD, TECHNOLOGIES, SERVICES, etc.)
    4. Prefer Title Case over ALL CAPS (employees rarely in all caps)
    5. Look near PAN number (employee's PAN)
    """
    # Company keywords to avoid
    COMPANY_KEYWORDS = [
        'LIMITED', 'LTD', 'PRIVATE', 'PVT', 'TECHNOLOGIES', 'TECHNOLOGY',
        'SERVICES', 'SERVICE', 'SOLUTIONS', 'SYSTEMS', 'CORPORATION',
        'ENTERPRISES', 'INDUSTRIES', 'COMPANY', 'CO.', 'INC', 'INCORPORATED'
    ]
    
    def is_company_name(name: str) -> bool:
        """Check if name contains company keywords."""
        name_upper = name.upper()
        return any(kw in name_upper for kw in COMPANY_KEYWORDS)
    
    def is_valid_person_name(name: str) -> bool:
        """Validate if this looks like a person's name."""
        if len(name) < 3 or len(name) > 60:
            return False
        if is_company_name(name):
            return False
        # Person names typically have 2-4 words
        words = name.split()
        if len(words) < 2 or len(words) > 4:
            return False
        return True
    
    # Pattern 1: After "Name and address of the Employee" label, next line
    # This is the most reliable pattern in Form 16
    patterns_priority = [
        r"Name\s+and\s+address\s+of\s+the\s+Employee[^\n]*\n\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        r"Name\s+of\s+(?:the\s+)?Employee\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
        r"Employee\s+Name\s*[:\-]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})",
    ]
    
    for pat in patterns_priority:
        m = re.search(pat, part_a, re.IGNORECASE)
        if m:
            name = m.group(1).strip()
            if is_valid_person_name(name):
                log.info("[EXTRACT] EmployeeName (priority pattern): %s", name)
                return name
    
    # Pattern 2: Look for name near PAN (employee's PAN is usually near their name)
    pan_match = re.search(r"PAN\s+of\s+(?:the\s+)?(?:Employee|Deductee)[^A-Z]*([A-Z]{5}[0-9]{4}[A-Z])", part_a, re.IGNORECASE)
    if pan_match:
        # Search backwards from PAN for a person name
        text_before_pan = part_a[:pan_match.start()]
        # Look in last 200 chars before PAN
        search_window = text_before_pan[-200:] if len(text_before_pan) > 200 else text_before_pan
        # Find Title Case names (typical for person names)
        name_pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})"
        matches = list(re.finditer(name_pattern, search_window))
        if matches:
            # Take the last match (closest to PAN)
            name = matches[-1].group(1).strip()
            if is_valid_person_name(name):
                log.info("[EXTRACT] EmployeeName (near PAN): %s", name)
                return name
    
    # Pattern 3: Fallback - look for any Title Case name that's not a company
    # Search in PART A only to avoid confusion with other sections
    name_pattern = r"\b([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    for match in re.finditer(name_pattern, part_a):
        name = match.group(1).strip()
        if is_valid_person_name(name):
            log.info("[EXTRACT] EmployeeName (fallback Title Case): %s", name)
            return name
    
    log.warning("[EXTRACT] EmployeeName not found")
    return None


def extract_gross_salary(text: str, part_b: str) -> Optional[float]:
    """Extract gross salary from Form 16 Part B.

    Priority:
    1. "Salary as per provisions contained in section 17(1)" — actual gross
    2. "Total amount of salary received from current employer"
    3. "Gross Salary" label
    4. Fallback: full text search
    """
    # Search in PART B first (where salary details live)
    keywords_b = [
        r"Salary\s+as\s+per\s+provisions\s+contained\s+in\s+section\s+17\(1\)",
        r"Total\s+amount\s+of\s+salary\s+received\s+from\s+current\s+employer",
        r"Gross\s+Salary",
    ]
    val = _find_amount_on_same_line(part_b, *keywords_b, min_val=10000)
    if val:
        log.info("[EXTRACT] GrossSalary (PART B line match): %.0f", val)
        return val

    val = _find_amount_near(part_b, *keywords_b, min_val=10000)
    if val:
        log.info("[EXTRACT] GrossSalary (PART B proximity): %.0f", val)
        return val

    # Fallback to full text
    val = _find_amount_on_same_line(text, *keywords_b, min_val=10000)
    if val:
        log.info("[EXTRACT] GrossSalary (full text fallback): %.0f", val)
        return val
    return None


def extract_gross_total_income(text: str, part_b: str) -> Optional[float]:
    """Extract gross total income (often used as the 'income' figure)."""
    keywords = [
        r"Gross\s+total\s+income",
        r"Income\s+chargeable\s+under\s+the\s+head\s+.{0,10}Salaries",
    ]
    val = _find_amount_on_same_line(part_b, *keywords, min_val=10000)
    if val:
        log.info("[EXTRACT] GrossTotalIncome (PART B): %.0f", val)
        return val
    val = _find_amount_on_same_line(text, *keywords, min_val=10000)
    if val:
        log.info("[EXTRACT] GrossTotalIncome (fallback): %.0f", val)
        return val
    return None


def extract_taxable_income(text: str, part_b: str) -> Optional[float]:
    """Extract total taxable income from PART B."""
    keywords = [
        r"Total\s+taxable\s+income",
        r"Net\s+taxable\s+income",
        r"Taxable\s+income",
    ]
    val = _find_amount_on_same_line(part_b, *keywords, min_val=10000)
    if val:
        log.info("[EXTRACT] TaxableIncome (PART B): %.0f", val)
        return val
    val = _find_amount_near(part_b, *keywords, window=100, min_val=10000)
    if val:
        log.info("[EXTRACT] TaxableIncome (PART B proximity): %.0f", val)
        return val
    # Fallback
    val = _find_amount_on_same_line(text, *keywords, min_val=10000)
    if val:
        log.info("[EXTRACT] TaxableIncome (fallback): %.0f", val)
        return val
    return None


def extract_tds(text: str, part_a: str, part_b: str) -> Optional[float]:
    """Extract TDS / tax deducted at source.

    Strategy (priority order):
    1. PART A table: "Total (Rs.)" row — last column is TDS amount
    2. PART B: "Tax deducted from salary u/s 192(1)"
    3. PART B: "Net tax payable" / "Tax payable"
    4. PART A: "Total amount of TDS"
    5. Fallback: full text
    """
    # Strategy 1: PART A table total row
    total_row_keywords = [
        r"Total\s*\(?\s*Rs\.?\s*\)?\s*",
    ]
    amounts = _find_all_amounts_on_line(part_a, r"Total\s*\(?\s*Rs\.?\s*\)?")
    if len(amounts) >= 2:
        # In PART A table, the last column in "Total (Rs.)" row is the TDS
        tds_val = amounts[-1]
        if tds_val >= 100:
            log.info("[EXTRACT] TDS (PART A table Total row, last amount): %.0f", tds_val)
            return tds_val

    # Strategy 2: Tax deducted from salary
    keywords_precise = [
        r"Tax\s+deducted\s+(?:from\s+salary\s+)?u/s\s+192",
        r"Tax\s+deducted\s+at\s+source\s+u/s\s+192",
    ]
    val = _find_amount_on_same_line(part_b, *keywords_precise, min_val=100)
    if val:
        log.info("[EXTRACT] TDS (192 match in PART B): %.0f", val)
        return val

    # Strategy 3: Net tax payable / Tax payable
    keywords_tax = [
        r"Net\s+tax\s+payable",
        r"Tax\s+payable\s*\(",
        r"Tax\s+payable\b",
    ]
    val = _find_amount_on_same_line(part_b, *keywords_tax, min_val=100)
    if val:
        log.info("[EXTRACT] TDS (tax payable match): %.0f", val)
        return val

    # Strategy 4: Total TDS
    keywords_total = [
        r"Total\s+(?:amount\s+of\s+)?(?:tax\s+)?(?:TDS|deducted\s+at\s+source)",
    ]
    val = _find_amount_on_same_line(part_a, *keywords_total, min_val=100)
    if val:
        log.info("[EXTRACT] TDS (Total TDS in PART A): %.0f", val)
        return val

    # Strategy 5: Full text fallback
    all_keywords = keywords_precise + keywords_tax + keywords_total
    val = _find_amount_on_same_line(text, *all_keywords, min_val=100)
    if val:
        log.info("[EXTRACT] TDS (full text fallback): %.0f", val)
        return val

    return None


def extract_all_deductions(text: str, part_b: str) -> Dict[str, float]:
    """Extract ALL deduction sections with comprehensive aggregation.
    
    Returns a structured dict with section-wise breakdown:
    {
        "Section80C": float,
        "Section80CCD1B": float,
        "Section80D": float,
        "Section80E": float,
        "Section80G": float,
        "Section80TTA": float,
        "TotalDeductions": float
    }
    
    Strategy:
    1. For Section 80C: aggregate all sub-items (LIC, PPF, PF, ELSS, etc.)
    2. Look for both individual line items AND aggregate totals
    3. Use the aggregate total if available, otherwise sum line items
    4. Extract all other 80-series sections
    """
    deductions: Dict[str, float] = {}
    
    # ========== SECTION 80C ==========
    # Try to find the aggregate total first (most reliable)
    total_80c = _find_amount_on_same_line(
        part_b,
        r"Total\s+deduction\s+under\s+section\s+80C",
        r"Aggregate.*80C",
        r"Deduction\s+under\s+section\s+80C",
        min_val=1000,
    )
    
    if total_80c:
        deductions["Section80C"] = total_80c
        log.info("[EXTRACT] Section80C (aggregate total): %.0f", total_80c)
    else:
        # Fallback: aggregate individual 80C sub-items
        section_80c_items = []
        keywords_80c = [
            r"Life\s+Insurance\s+Premium",
            r"Provident\s+Fund",
            r"PPF",
            r"ELSS",
            r"NSC",
            r"National\s+Savings\s+Certificate",
            r"Tax\s+[Ss]aving\s+(?:Fixed\s+)?Deposit",
            r"Tuition\s+[Ff]ees",
            r"Principal\s+repayment.*housing\s+loan",
            r"Home\s+Loan\s+Principal",
            r"Sukanya\s+Samriddhi",
        ]
        
        for kw in keywords_80c:
            amounts = _find_all_amounts_on_line(part_b, kw)
            if amounts:
                log.info("[EXTRACT] Section80C sub-item (%s): %s", kw, amounts)
                section_80c_items.extend(amounts)
        
        if section_80c_items:
            total = sum(section_80c_items)
            deductions["Section80C"] = total
            log.info("[EXTRACT] Section80C (sum of %d items): %.0f", len(section_80c_items), total)
        else:
            # Last resort: generic 80C search
            val = _find_amount_on_same_line(text, r"section\s+80C\b", r"\b80C\b", min_val=1000)
            if val:
                deductions["Section80C"] = val
                log.info("[EXTRACT] Section80C (generic fallback): %.0f", val)
    
    # ========== SECTION 80CCD(1B) ==========
    # NPS additional deduction (up to ₹50,000)
    val = _find_amount_on_same_line(
        part_b,
        r"80CCD\(1B\)",
        r"80CCD\s*\(?\s*1\s*B\s*\)?",
        r"NPS.*additional",
        min_val=100,
    )
    if val:
        deductions["Section80CCD1B"] = val
        log.info("[EXTRACT] Section80CCD1B (NPS additional): %.0f", val)
    
    # ========== SECTION 80D ==========
    # Health insurance premium
    val = _find_amount_on_same_line(
        part_b,
        r"health\s+insurance\s+premia\s+under\s+section\s+80D",
        r"Medical\s+insurance.*80D",
        r"section\s+80D\b",
        r"\b80D\b",
        min_val=100,
    )
    if val:
        deductions["Section80D"] = val
        log.info("[EXTRACT] Section80D (health insurance): %.0f", val)
    
    # ========== SECTION 80E ==========
    # Education loan interest
    val = _find_amount_on_same_line(
        part_b,
        r"Interest.*education\s+loan.*80E",
        r"section\s+80E\b",
        r"\b80E\b",
        min_val=100,
    )
    if val:
        deductions["Section80E"] = val
        log.info("[EXTRACT] Section80E (education loan): %.0f", val)
    
    # ========== SECTION 80G ==========
    # Donations
    val = _find_amount_on_same_line(
        part_b,
        r"Donation.*80G",
        r"section\s+80G\b",
        r"\b80G\b",
        min_val=100,
    )
    if val:
        deductions["Section80G"] = val
        log.info("[EXTRACT] Section80G (donations): %.0f", val)
    
    # ========== SECTION 80TTA ==========
    # Interest on savings account
    val = _find_amount_on_same_line(
        part_b,
        r"Interest.*savings.*80TTA",
        r"section\s+80TTA\b",
        r"\b80TTA\b",
        min_val=100,
    )
    if val:
        deductions["Section80TTA"] = val
        log.info("[EXTRACT] Section80TTA (savings interest): %.0f", val)
    
    # Calculate total deductions
    total = sum(deductions.values())
    if total > 0:
        deductions["TotalDeductions"] = total
        log.info("[EXTRACT] TotalDeductions (sum of all sections): %.0f", total)
    
    return deductions


def extract_section80c(text: str, part_b: str) -> Optional[float]:
    """Extract Section 80C deduction from PART B.
    
    DEPRECATED: Use extract_all_deductions() for comprehensive extraction.
    Kept for backward compatibility.
    """
    deductions = extract_all_deductions(text, part_b)
    return deductions.get("Section80C")


def extract_section80d(text: str, part_b: str) -> Optional[float]:
    """Extract Section 80D deduction (health insurance) from PART B.
    
    DEPRECATED: Use extract_all_deductions() for comprehensive extraction.
    Kept for backward compatibility.
    """
    deductions = extract_all_deductions(text, part_b)
    return deductions.get("Section80D")


def extract_tax_on_income(text: str, part_b: str) -> Optional[float]:
    """Extract 'Tax on total income' — the pre-cess computed tax."""
    keywords = [
        r"Tax\s+on\s+total\s+income",
        r"Income\s+tax\s+thereon",
    ]
    val = _find_amount_on_same_line(part_b, *keywords, min_val=100)
    if val:
        log.info("[EXTRACT] TaxOnIncome (PART B): %.0f", val)
        return val
    val = _find_amount_on_same_line(text, *keywords, min_val=100)
    return val


def extract_cess(text: str, part_b: str) -> Optional[float]:
    """Extract Health & Education Cess."""
    keywords = [
        r"Health\s+and\s+[Ee]ducation\s+[Cc]ess",
        r"education\s+cess",
    ]
    val = _find_amount_on_same_line(part_b, *keywords, min_val=10)
    if val:
        log.info("[EXTRACT] Cess (PART B): %.0f", val)
        return val
    val = _find_amount_on_same_line(text, *keywords, min_val=10)
    return val


# ---------------------------------------------------------------------------
# Flat dict extractor (primary interface)
# ---------------------------------------------------------------------------

def extract_fields(text: str) -> Dict[str, Any]:
    """Run all extractors and return a flat dict with exact validation keys.

    This is the PRIMARY extraction interface. Returns only non-None values.
    Uses section-based parsing for higher accuracy.
    
    Enhanced in Phase 1:
    - Fixed employee name extraction with company keyword filtering
    - Comprehensive deduction extraction (all 80-series sections)
    - Structured deductions with section-wise breakdown
    """
    log.info("[NER-Regex] Running section-aware field extraction …")

    # Step 1: Section parsing
    part_a, part_b, full = split_sections(text)

    # Step 2: Extract from appropriate sections
    pan            = extract_pan(full, part_a)
    tan            = extract_tan(full, part_a)
    ay             = extract_assessment_year(full, part_a)
    employer       = extract_employer_name(full, part_a)
    employee       = extract_employee_name(full, part_a)  # Fixed: now passes part_a
    gross_salary   = extract_gross_salary(full, part_b)
    gross_total    = extract_gross_total_income(full, part_b)
    taxable_income = extract_taxable_income(full, part_b)
    tds            = extract_tds(full, part_a, part_b)
    
    # Enhanced: Extract ALL deductions with section-wise breakdown
    all_deductions = extract_all_deductions(full, part_b)
    
    tax_on_income  = extract_tax_on_income(full, part_b)
    cess           = extract_cess(full, part_b)

    fields: Dict[str, Any] = {}
    if pan:            fields["PAN"]             = pan
    if tan:            fields["TAN"]             = tan
    if ay:             fields["AssessmentYear"]   = ay
    if employer:       fields["EmployerName"]     = employer
    if employee:       fields["EmployeeName"]     = employee
    if gross_salary:   fields["GrossSalary"]      = gross_salary
    if gross_total:    fields["GrossTotalIncome"]  = gross_total
    if taxable_income: fields["TaxableIncome"]    = taxable_income
    if tds:            fields["TDS"]              = tds
    
    # Add all deduction sections
    for section, amount in all_deductions.items():
        if amount > 0:
            fields[section] = amount
    
    # Maintain backward compatibility: also set individual section fields
    if "Section80C" in all_deductions:
        fields["Section80C"] = all_deductions["Section80C"]
    if "Section80D" in all_deductions:
        fields["Section80D"] = all_deductions["Section80D"]
    
    # Set total deductions for tax computation
    if "TotalDeductions" in all_deductions:
        fields["Deductions"] = all_deductions["TotalDeductions"]
    
    if tax_on_income:  fields["TaxOnIncome"]      = tax_on_income
    if cess:           fields["Cess"]             = cess

    # Step 3: Validation guards
    _validate_extraction(fields)

    log.info(
        "[NER-Regex] Extracted %d fields: %s",
        len(fields),
        list(fields.keys()),
    )
    return fields


def _validate_extraction(fields: Dict[str, Any]) -> None:
    """Post-extraction sanity checks."""
    gross = fields.get("GrossSalary")
    taxable = fields.get("TaxableIncome")
    gti = fields.get("GrossTotalIncome")

    # If GrossSalary is missing but GrossTotalIncome exists, use it as GrossSalary
    if not gross and gti:
        log.info("[NER-Regex] GrossSalary not found, using GrossTotalIncome (%.0f) as GrossSalary", gti)
        fields["GrossSalary"] = gti
        gross = gti

    if gross and taxable and taxable > gross:
        log.warning(
            "[NER-Regex] ANOMALY: TaxableIncome (%.0f) > GrossSalary (%.0f) — "
            "possible extraction error. Swapping to use GrossTotalIncome if available.",
            taxable, gross,
        )
        # Try to resolve: if GrossTotalIncome is present and between them, use it
        if gti and gti >= taxable:
            log.info("[NER-Regex] Resolved: using GrossTotalIncome (%.0f) as GrossSalary", gti)
            fields["GrossSalary"] = gti


# ---------------------------------------------------------------------------
# Legacy list-based interface (for NERService merge)
# ---------------------------------------------------------------------------

def extract_all(text: str) -> List[Dict[str, Any]]:
    """Return entities as a list of {label, value, confidence, source} dicts."""
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
