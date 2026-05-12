"""
Deterministic regex-based extraction for Form 26AS.

Form 26AS Structure
-------------------
- Part A: TDS on Salary (Section 192)
- Part B: TDS on Other Income
- Part C: TDS on Sale of Property
- Part D: Tax Paid (Advance Tax, Self-Assessment Tax)
- Part E: Refund Information

This module extracts:
- PAN, TAN, Assessment Year
- TDS deducted at source (per deductor)
- Advance tax / self-assessment tax payments
- Refund details
"""

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

PAN_RE = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
TAN_RE = re.compile(r"\b([A-Z]{4}[0-9]{5}[A-Z])\b")
AY_RE = re.compile(r"\b(20\d{2}-(?:20)?\d{2})\b")
AMOUNT_RE = re.compile(r"\b(\d{1,3}(?:,\d{2,3})*(?:\.\d{1,2})?|\d{4,}(?:\.\d{1,2})?)\b")


def _to_float(raw: str) -> float:
    """Convert Indian number format to float."""
    return float(raw.replace(",", ""))


def _is_postal_code(raw: str, val: float) -> bool:
    """Return True if this looks like a 6-digit postal code."""
    if "." in raw or "," in raw:
        return False
    return 100000 <= val <= 999999 and val == int(val)


# ---------------------------------------------------------------------------
# Section parsing
# ---------------------------------------------------------------------------

def split_sections_26as(text: str) -> Dict[str, str]:
    """Split Form 26AS into parts A, B, C, D, E."""
    text_upper = text.upper()
    
    sections = {
        "full": text,
        "part_a": "",
        "part_b": "",
        "part_c": "",
        "part_d": "",
        "part_e": "",
    }
    
    # Find section markers
    markers = {
        "part_a": [r"PART\s*[-—]?\s*A\b", r"TDS\s+ON\s+SALARY", r"SECTION\s+192"],
        "part_b": [r"PART\s*[-—]?\s*B\b", r"TDS\s+ON\s+OTHER\s+(?:THAN\s+)?SALARY"],
        "part_c": [r"PART\s*[-—]?\s*C\b", r"TDS\s+ON\s+SALE\s+OF\s+PROPERTY"],
        "part_d": [r"PART\s*[-—]?\s*D\b", r"TAX\s+PAID", r"ADVANCE\s+TAX"],
        "part_e": [r"PART\s*[-—]?\s*E\b", r"REFUND"],
    }
    
    positions = {}
    for part, patterns in markers.items():
        for pat in patterns:
            m = re.search(pat, text_upper)
            if m:
                positions[part] = m.start()
                log.info(f"[26AS] Found {part.upper()} at position {m.start()}")
                break
    
    # Extract sections based on positions
    sorted_parts = sorted(positions.items(), key=lambda x: x[1])
    for i, (part, start) in enumerate(sorted_parts):
        end = sorted_parts[i + 1][1] if i + 1 < len(sorted_parts) else len(text)
        sections[part] = text[start:end]
    
    return sections


# ---------------------------------------------------------------------------
# Field extractors
# ---------------------------------------------------------------------------

def extract_pan_26as(text: str) -> Optional[str]:
    """Extract PAN from Form 26AS."""
    # Look for "PAN" label
    m = re.search(r"PAN\s*[:\-]?\s*([A-Z]{5}[0-9]{4}[A-Z])", text, re.IGNORECASE)
    if m:
        log.info("[26AS] PAN (contextual): %s", m.group(1))
        return m.group(1)
    
    # Fallback: first PAN found
    all_pans = PAN_RE.findall(text)
    if all_pans:
        log.info("[26AS] PAN (fallback): %s", all_pans[0])
        return all_pans[0]
    return None


def extract_tan_26as(text: str, part_a: str) -> Optional[str]:
    """Extract TAN of deductor from Part A."""
    # Look for TAN in Part A (salary section)
    m = re.search(r"TAN\s+of\s+(?:the\s+)?(?:Deductor|Employer)[^A-Z]*([A-Z]{4}[0-9]{5}[A-Z])", part_a, re.IGNORECASE)
    if m:
        log.info("[26AS] TAN (Part A): %s", m.group(1))
        return m.group(1)
    
    # Fallback: first TAN in full text
    all_tans = TAN_RE.findall(text)
    if all_tans:
        log.info("[26AS] TAN (fallback): %s", all_tans[0])
        return all_tans[0]
    return None


def extract_assessment_year_26as(text: str) -> Optional[str]:
    """Extract Assessment Year."""
    m = re.search(r"Assessment\s+Year\s*[:\-]?\s*(20\d{2}[-–]\d{2,4})", text, re.IGNORECASE)
    if m:
        log.info("[26AS] AssessmentYear: %s", m.group(1))
        return m.group(1)
    
    all_ay = AY_RE.findall(text)
    if all_ay:
        log.info("[26AS] AssessmentYear (fallback): %s", all_ay[0])
        return all_ay[0]
    return None


def extract_tds_entries_26as(part_a: str) -> List[Dict[str, Any]]:
    """Extract TDS entries from Part A (salary TDS).
    
    Returns list of:
    {
        "deductor_name": str,
        "tan": str,
        "amount_credited": float,
        "tds_deducted": float,
        "tds_deposited": float,
    }
    """
    entries = []
    
    # Look for table rows with TAN, amounts
    # Pattern: TAN followed by multiple amounts on same line
    lines = part_a.split('\n')
    for line in lines:
        tan_match = TAN_RE.search(line)
        if not tan_match:
            continue
        
        tan = tan_match.group(1)
        amounts = []
        for am in AMOUNT_RE.finditer(line):
            try:
                val = _to_float(am.group())
                if val >= 100 and not _is_postal_code(am.group(), val):
                    amounts.append(val)
            except ValueError:
                continue
        
        if len(amounts) >= 2:
            # Typically: amount_credited, tds_deducted, tds_deposited
            entry = {
                "tan": tan,
                "deductor_name": "",  # Would need more context to extract
                "amount_credited": amounts[0] if len(amounts) > 0 else 0,
                "tds_deducted": amounts[1] if len(amounts) > 1 else 0,
                "tds_deposited": amounts[2] if len(amounts) > 2 else amounts[1],
            }
            entries.append(entry)
            log.info("[26AS] TDS entry: TAN=%s, credited=%.0f, deducted=%.0f", 
                    tan, entry["amount_credited"], entry["tds_deducted"])
    
    return entries


def extract_total_tds_26as(part_a: str, text: str) -> Optional[float]:
    """Extract total TDS from Part A or summary."""
    keywords = [
        r"Total\s+(?:TDS\s+)?(?:deducted|deposited)",
        r"Total\s+tax\s+deducted",
        r"Aggregate\s+TDS",
    ]
    
    # Try Part A first
    for kw in keywords:
        m = re.search(kw, part_a, re.IGNORECASE)
        if m:
            # Look for amount after keyword
            window = part_a[m.end():m.end() + 200]
            for am in AMOUNT_RE.finditer(window):
                try:
                    val = _to_float(am.group())
                    if val >= 100:
                        log.info("[26AS] Total TDS (Part A): %.0f", val)
                        return val
                except ValueError:
                    continue
    
    # Fallback: full text
    for kw in keywords:
        m = re.search(kw, text, re.IGNORECASE)
        if m:
            window = text[m.end():m.end() + 200]
            for am in AMOUNT_RE.finditer(window):
                try:
                    val = _to_float(am.group())
                    if val >= 100:
                        log.info("[26AS] Total TDS (fallback): %.0f", val)
                        return val
                except ValueError:
                    continue
    
    return None


def extract_advance_tax_26as(part_d: str) -> Optional[float]:
    """Extract advance tax paid from Part D."""
    keywords = [
        r"Advance\s+[Tt]ax",
        r"Tax\s+paid\s+by\s+challan",
    ]
    
    for kw in keywords:
        m = re.search(kw, part_d, re.IGNORECASE)
        if m:
            window = part_d[m.end():m.end() + 200]
            for am in AMOUNT_RE.finditer(window):
                try:
                    val = _to_float(am.group())
                    if val >= 100:
                        log.info("[26AS] Advance Tax: %.0f", val)
                        return val
                except ValueError:
                    continue
    
    return None


def extract_self_assessment_tax_26as(part_d: str) -> Optional[float]:
    """Extract self-assessment tax from Part D."""
    keywords = [
        r"Self[-\s]assessment\s+[Tt]ax",
        r"Tax\s+paid.*self[-\s]assessment",
    ]
    
    for kw in keywords:
        m = re.search(kw, part_d, re.IGNORECASE)
        if m:
            window = part_d[m.end():m.end() + 200]
            for am in AMOUNT_RE.finditer(window):
                try:
                    val = _to_float(am.group())
                    if val >= 100:
                        log.info("[26AS] Self-Assessment Tax: %.0f", val)
                        return val
                except ValueError:
                    continue
    
    return None


def extract_refund_26as(part_e: str, text: str) -> Optional[float]:
    """Extract refund amount from Part E."""
    keywords = [
        r"Refund\s+(?:amount|issued)",
        r"Amount\s+refunded",
    ]
    
    # Try Part E first
    for kw in keywords:
        m = re.search(kw, part_e, re.IGNORECASE)
        if m:
            window = part_e[m.end():m.end() + 200]
            for am in AMOUNT_RE.finditer(window):
                try:
                    val = _to_float(am.group())
                    if val >= 100:
                        log.info("[26AS] Refund: %.0f", val)
                        return val
                except ValueError:
                    continue
    
    # Fallback: full text
    for kw in keywords:
        m = re.search(kw, text, re.IGNORECASE)
        if m:
            window = text[m.end():m.end() + 200]
            for am in AMOUNT_RE.finditer(window):
                try:
                    val = _to_float(am.group())
                    if val >= 100:
                        log.info("[26AS] Refund (fallback): %.0f", val)
                        return val
                except ValueError:
                    continue
    
    return None


# ---------------------------------------------------------------------------
# Main extraction interface
# ---------------------------------------------------------------------------

def extract_fields_26as(text: str) -> Dict[str, Any]:
    """Extract all fields from Form 26AS.
    
    Returns dict with keys:
        PAN, TAN, AssessmentYear, TDS, TDSEntries,
        AdvanceTax, SelfAssessmentTax, Refund
    """
    log.info("[26AS] Running field extraction...")
    
    # Split into sections
    sections = split_sections_26as(text)
    part_a = sections["part_a"]
    part_d = sections["part_d"]
    part_e = sections["part_e"]
    full = sections["full"]
    
    # Extract fields
    pan = extract_pan_26as(full)
    tan = extract_tan_26as(full, part_a)
    ay = extract_assessment_year_26as(full)
    tds_entries = extract_tds_entries_26as(part_a)
    total_tds = extract_total_tds_26as(part_a, full)
    advance_tax = extract_advance_tax_26as(part_d)
    self_assessment_tax = extract_self_assessment_tax_26as(part_d)
    refund = extract_refund_26as(part_e, full)
    
    fields: Dict[str, Any] = {}
    if pan:
        fields["PAN"] = pan
    if tan:
        fields["TAN"] = tan
    if ay:
        fields["AssessmentYear"] = ay
    if total_tds:
        fields["TDS"] = total_tds
    if tds_entries:
        fields["TDSEntries"] = tds_entries
    if advance_tax:
        fields["AdvanceTax"] = advance_tax
    if self_assessment_tax:
        fields["SelfAssessmentTax"] = self_assessment_tax
    if refund:
        fields["Refund"] = refund
    
    log.info("[26AS] Extracted %d fields: %s", len(fields), list(fields.keys()))
    return fields

# Made with Bob
