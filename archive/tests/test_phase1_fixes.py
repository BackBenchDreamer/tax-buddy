#!/usr/bin/env python3
"""
Test script for Phase 1 fixes:
1. Employee name extraction (avoiding employer name confusion)
2. Comprehensive deduction extraction (all 80-series sections)
3. Structured deductions in tax computation
"""

import sys
import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s"
)

# Import our modules
from ml.ner.regex_utils import extract_fields, extract_all_deductions
from app.services.tax_service import compute_tax

def test_employee_name_extraction():
    """Test that employee name is correctly extracted (not employer name)."""
    print("\n" + "="*70)
    print("TEST 1: Employee Name Extraction")
    print("="*70)
    
    # Sample Form 16 text with both employee and employer names
    sample_text = """
    FORM NO. 16
    PART A
    
    Name and address of the Employer:
    SIEMENS TECHNOLOGY AND SERVICES PRIVATE LIMITED
    
    TAN of the Deductor: MUMS15654C
    
    Name and address of the Employee:
    Rajesh Kumar Sharma
    
    PAN of the Employee: BIGPP1846N
    
    PART B
    Details of Salary paid and any other income
    """
    
    fields = extract_fields(sample_text)
    
    employee_name = fields.get("EmployeeName", "NOT FOUND")
    employer_name = fields.get("EmployerName", "NOT FOUND")
    
    print(f"\n✓ Extracted Employee Name: {employee_name}")
    print(f"✓ Extracted Employer Name: {employer_name}")
    
    # Validation
    is_correct = (
        "SIEMENS" not in employee_name.upper() and
        "LIMITED" not in employee_name.upper() and
        "PRIVATE" not in employee_name.upper()
    )
    
    if is_correct:
        print("\n✅ PASS: Employee name correctly extracted (no company keywords)")
    else:
        print("\n❌ FAIL: Employee name contains company keywords")
        return False
    
    return True


def test_deduction_extraction():
    """Test comprehensive deduction extraction."""
    print("\n" + "="*70)
    print("TEST 2: Comprehensive Deduction Extraction")
    print("="*70)
    
    # Sample Form 16 Part B with multiple deduction sections
    sample_text = """
    PART B
    
    Deductions under Chapter VI-A:
    
    Section 80C:
    Life Insurance Premium: 25,000
    Provident Fund: 50,000
    PPF: 30,000
    ELSS: 42,305
    Total deduction under section 80C: 1,47,305
    
    Section 80CCD(1B):
    NPS additional contribution: 50,000
    
    Section 80D:
    Health Insurance Premium: 15,000
    
    Section 80E:
    Education Loan Interest: 8,500
    
    Total Deductions: 2,20,805
    """
    
    # Extract deductions
    part_a = ""
    part_b = sample_text
    deductions = extract_all_deductions(sample_text, part_b)
    
    print("\n✓ Extracted Deductions:")
    for section, amount in deductions.items():
        print(f"  {section}: ₹{amount:,.0f}")
    
    # Validation
    expected_80c = 147305
    expected_total = 220805
    
    actual_80c = deductions.get("Section80C", 0)
    actual_total = deductions.get("TotalDeductions", 0)
    
    print(f"\n✓ Section 80C: Expected ₹{expected_80c:,}, Got ₹{actual_80c:,.0f}")
    print(f"✓ Total Deductions: Expected ₹{expected_total:,}, Got ₹{actual_total:,.0f}")
    
    # Allow small tolerance for rounding
    is_80c_correct = abs(actual_80c - expected_80c) < 100
    is_total_correct = abs(actual_total - expected_total) < 100
    
    if is_80c_correct and is_total_correct:
        print("\n✅ PASS: All deductions correctly extracted and aggregated")
    else:
        print("\n❌ FAIL: Deduction amounts don't match expected values")
        return False
    
    return True


def test_structured_deductions_in_tax_computation():
    """Test that tax service handles structured deductions correctly."""
    print("\n" + "="*70)
    print("TEST 3: Structured Deductions in Tax Computation")
    print("="*70)
    
    # Test data with structured deductions
    test_data = {
        "GrossSalary": 873898,
        "Section80C": 147305,
        "Section80CCD1B": 50000,
        "Section80D": 15000,
        "Section80E": 8500,
        "TotalDeductions": 220805,
        "TDS": 34690,
        "Regime": "old"
    }
    
    result = compute_tax(test_data)
    
    print(f"\n✓ Gross Salary: ₹{result['gross_income']:,.0f}")
    print(f"✓ Total Deductions: ₹{result['deductions']:,.0f}")
    print(f"✓ Taxable Income: ₹{result['taxable_income']:,.0f}")
    print(f"✓ Total Tax: ₹{result['total_tax']:,.0f}")
    
    if "deduction_breakdown" in result:
        print("\n✓ Deduction Breakdown:")
        for section, amount in result["deduction_breakdown"].items():
            print(f"  {section}: ₹{amount:,.0f}")
    
    # Validation
    expected_deductions = 220805
    actual_deductions = result["deductions"]
    
    is_correct = abs(actual_deductions - expected_deductions) < 100
    
    if is_correct:
        print("\n✅ PASS: Tax computation correctly uses structured deductions")
    else:
        print(f"\n❌ FAIL: Expected deductions ₹{expected_deductions:,}, got ₹{actual_deductions:,.0f}")
        return False
    
    return True


def test_backward_compatibility():
    """Test that old format (single Deductions field) still works."""
    print("\n" + "="*70)
    print("TEST 4: Backward Compatibility")
    print("="*70)
    
    # Old format test data
    old_format_data = {
        "GrossSalary": 873898,
        "Deductions": 269618,
        "TDS": 34690,
        "Regime": "old"
    }
    
    result = compute_tax(old_format_data)
    
    print(f"\n✓ Using old format (single Deductions field)")
    print(f"✓ Gross Salary: ₹{result['gross_income']:,.0f}")
    print(f"✓ Deductions: ₹{result['deductions']:,.0f}")
    print(f"✓ Total Tax: ₹{result['total_tax']:,.0f}")
    
    # Should match the example in tax_service.py
    expected_tax = 34690
    actual_tax = result["total_tax"]
    
    is_correct = abs(actual_tax - expected_tax) < 2
    
    if is_correct:
        print("\n✅ PASS: Backward compatibility maintained")
    else:
        print(f"\n❌ FAIL: Expected tax ₹{expected_tax:,}, got ₹{actual_tax:,.0f}")
        return False
    
    return True


def main():
    """Run all Phase 1 tests."""
    print("\n" + "="*70)
    print("PHASE 1 IMPLEMENTATION TESTS")
    print("="*70)
    print("\nTesting fixes for:")
    print("1. Employee name extraction (avoiding employer confusion)")
    print("2. Comprehensive deduction extraction (all 80-series sections)")
    print("3. Structured deductions in tax computation")
    print("4. Backward compatibility")
    
    tests = [
        test_employee_name_extraction,
        test_deduction_extraction,
        test_structured_deductions_in_tax_computation,
        test_backward_compatibility,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Phase 1 implementation is successful.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

# Made with Bob
