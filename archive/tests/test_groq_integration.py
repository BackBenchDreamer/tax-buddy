"""
Groq AI Integration Test Script
================================

Tests all Groq AI features in the Tax Buddy application:
1. API key configuration and client initialization
2. Ambiguous field resolution
3. NER fallback extraction
4. Validation explanations
5. Tax regime recommendations
6. AI validation service
7. Tax optimization service

Run with: python backend/test_groq_integration.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import settings
from app.services import groq_service
from app.services import ai_validation_service
from app.services import tax_optimization_service


# Test data
SAMPLE_OCR_TEXT = """
FORM 16
PART A
Certificate under section 203 of the Income-tax Act, 1961
for tax deducted at source on salary

Name of Employee: RAJESH KUMAR SHARMA
PAN of Employee: ABCDE1234F
TAN of Employer: TECH0123456
Name of Employer: TECH SOLUTIONS PVT LTD

Assessment Year: 2023-24
Financial Year: 2022-23

Period: From 01/04/2022 To 31/03/2023

PART B
Details of Salary paid and any other income and tax deducted

1. Gross Salary: Rs. 12,00,000
2. Less: Allowances to the extent exempt u/s 10: Rs. 50,000
3. Balance (1-2): Rs. 11,50,000
4. Deductions:
   a) Standard Deduction u/s 16(ia): Rs. 50,000
   b) Entertainment Allowance u/s 16(ii): Rs. 0
   c) Tax on employment u/s 16(iii): Rs. 0
5. Income chargeable under the head 'Salaries': Rs. 11,00,000

6. Add: Any other income reported by the employee: Rs. 0

7. Gross total income (5+6): Rs. 11,00,000

8. Deductions under Chapter VI-A:
   a) Section 80C: Rs. 1,50,000
   b) Section 80CCD(1B): Rs. 50,000
   c) Section 80D: Rs. 25,000
   d) Section 80E: Rs. 0
   e) Section 80G: Rs. 10,000
   f) Total: Rs. 2,35,000

9. Total income (7-8): Rs. 8,65,000

10. Tax on total income: Rs. 82,500
11. Surcharge: Rs. 0
12. Health and Education Cess: Rs. 3,300
13. Tax payable (10+11+12): Rs. 85,800
14. Less: Relief under section 89: Rs. 0
15. Tax payable (13-14): Rs. 85,800
16. Tax deducted at source: Rs. 85,800
"""

SAMPLE_EXTRACTED_FIELDS = {
    "EmployeeName": "RAJESH KUMAR SHARMA",
    "PAN": "ABCDE1234F",
    "EmployerName": "TECH SOLUTIONS PVT LTD",
    "TAN": "TECH0123456",
    "GrossSalary": 1200000.0,
    "TaxableIncome": 865000.0,
    "TDS": 85800.0,
    "Section80C": 150000.0,
    "Section80CCD1B": 50000.0,
    "Section80D": 25000.0,
    "Section80E": 0.0,
    "Section80G": 10000.0,
    "TotalDeductions": 235000.0,
}


def print_header(title: str):
    """Print a formatted test section header."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_result(test_name: str, passed: bool, details: str = ""):
    """Print test result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"\n{status} - {test_name}")
    if details:
        print(f"  {details}")


async def test_1_configuration():
    """Test 1: Check Groq API configuration."""
    print_header("TEST 1: Configuration Check")
    
    print(f"\nGroq API Key: {'*' * 20}{settings.GROQ_API_KEY[-8:] if settings.GROQ_API_KEY else 'NOT SET'}")
    print(f"Groq Model: {settings.GROQ_MODEL}")
    print(f"Groq Timeout: {settings.GROQ_TIMEOUT}s")
    
    has_key = bool(settings.GROQ_API_KEY)
    print_result("API Key Configured", has_key, 
                 "API key is set" if has_key else "API key is missing in .env file")
    
    return has_key


async def test_2_client_initialization():
    """Test 2: Initialize Groq client."""
    print_header("TEST 2: Client Initialization")
    
    try:
        client = groq_service._get_groq_client()
        
        if client is None:
            print_result("Client Initialization", False, "Client returned None")
            return False
        
        print(f"\nClient Type: {type(client).__name__}")
        print(f"Client Module: {type(client).__module__}")
        
        print_result("Client Initialization", True, "Groq client created successfully")
        return True
        
    except Exception as e:
        print_result("Client Initialization", False, f"Error: {str(e)}")
        return False


async def test_3_resolve_ambiguous_field():
    """Test 3: Resolve ambiguous OCR field."""
    print_header("TEST 3: Ambiguous Field Resolution")
    
    try:
        # Test with a slightly garbled PAN
        result = await groq_service.resolve_ambiguous_field(
            ocr_snippet="PAN: ABCDE12B4F (might be ABCDE1234F)",
            field_name="PAN",
            expected_format="10-character alphanumeric (5 letters + 4 digits + 1 letter)"
        )
        
        print(f"\nInput: 'ABCDE12B4F (might be ABCDE1234F)'")
        print(f"Resolved: {result}")
        
        success = result is not None
        print_result("Ambiguous Field Resolution", success,
                     f"Resolved to: {result}" if success else "Failed to resolve")
        return success
        
    except Exception as e:
        print_result("Ambiguous Field Resolution", False, f"Error: {str(e)}")
        return False


async def test_4_extract_entity_fallback():
    """Test 4: NER fallback extraction."""
    print_header("TEST 4: NER Fallback Extraction")
    
    try:
        result = await groq_service.extract_entity_fallback(
            text_block="Employee PAN: ABCDE1234F, Name: Rajesh Kumar",
            entity_type="PAN"
        )
        
        print(f"\nInput: 'Employee PAN: ABCDE1234F, Name: Rajesh Kumar'")
        print(f"Extracted: {result}")
        
        success = result is not None and result.get("value") is not None
        print_result("NER Fallback Extraction", success,
                     f"Extracted: {result}" if success else "Failed to extract")
        return success
        
    except Exception as e:
        print_result("NER Fallback Extraction", False, f"Error: {str(e)}")
        return False


async def test_5_explain_validation_issues():
    """Test 5: Generate validation explanations."""
    print_header("TEST 5: Validation Issue Explanations")
    
    try:
        issues = [
            {
                "type": "salary_mismatch",
                "message": "Form 16 shows ₹12,00,000 but Form 26AS shows ₹11,50,000",
                "severity": "high",
                "field": "GrossSalary"
            },
            {
                "type": "tds_mismatch",
                "message": "TDS in Form 16 (₹85,800) differs from Form 26AS (₹82,500)",
                "severity": "medium",
                "field": "TDS"
            }
        ]
        
        result = await groq_service.explain_validation_issues(issues)
        
        print(f"\nInput: {len(issues)} validation issues")
        print(f"Explanations generated: {len(result)}")
        
        for issue_type, explanation in result.items():
            print(f"\n  {issue_type}:")
            print(f"    {explanation[:100]}...")
        
        success = len(result) > 0
        print_result("Validation Explanations", success,
                     f"Generated {len(result)} explanations" if success else "No explanations generated")
        return success
        
    except Exception as e:
        print_result("Validation Explanations", False, f"Error: {str(e)}")
        return False


async def test_6_recommend_tax_regime():
    """Test 6: Tax regime recommendation."""
    print_header("TEST 6: Tax Regime Recommendation")
    
    try:
        result = await groq_service.recommend_tax_regime(
            gross_income=1200000.0,
            deductions={
                "Section80C": 150000.0,
                "Section80CCD1B": 50000.0,
                "Section80D": 25000.0,
            },
            old_regime_tax=82500.0,
            new_regime_tax=95000.0,
        )
        
        print(f"\nInput:")
        print(f"  Gross Income: ₹12,00,000")
        print(f"  Deductions: ₹2,25,000")
        print(f"  Old Regime Tax: ₹82,500")
        print(f"  New Regime Tax: ₹95,000")
        
        if result:
            print(f"\nRecommendation:")
            print(f"  {result[:200]}...")
        
        success = result is not None and len(result) > 0
        print_result("Tax Regime Recommendation", success,
                     "Recommendation generated" if success else "Failed to generate recommendation")
        return success
        
    except Exception as e:
        print_result("Tax Regime Recommendation", False, f"Error: {str(e)}")
        return False


async def test_7_ai_validation_service():
    """Test 7: AI Validation Service."""
    print_header("TEST 7: AI Validation Service")
    
    try:
        result = await ai_validation_service.validate_extracted_fields(
            extracted_fields=SAMPLE_EXTRACTED_FIELDS,
            ocr_text=SAMPLE_OCR_TEXT,
            enable_ai=True
        )
        
        print(f"\nValidation Summary:")
        print(f"  Total Fields: {result['summary']['total_fields']}")
        print(f"  Validated: {result['summary']['validated']}")
        print(f"  Corrected: {result['summary']['corrected']}")
        print(f"  Flagged: {result['summary']['flagged']}")
        
        if result['validations']:
            print(f"\nValidation Results:")
            for val in result['validations'][:3]:  # Show first 3
                print(f"  - {val['field_name']}: {val['action']} (confidence: {val['confidence']:.2f})")
                print(f"    {val['reasoning'][:80]}...")
        
        success = result['summary']['validated'] > 0
        print_result("AI Validation Service", success,
                     f"Validated {result['summary']['validated']} fields" if success else "No validations performed")
        return success
        
    except Exception as e:
        print_result("AI Validation Service", False, f"Error: {str(e)}")
        return False


async def test_8_tax_optimization_service():
    """Test 8: Tax Optimization Service."""
    print_header("TEST 8: Tax Optimization Service")
    
    try:
        # Mock tax result
        tax_result = {
            "regime": "old",
            "total_tax": 82500.0,
            "taxable_income": 865000.0,
        }
        
        result = await tax_optimization_service.optimize_tax(
            validated_data=SAMPLE_EXTRACTED_FIELDS,
            tax_result=tax_result,
            ocr_text=SAMPLE_OCR_TEXT
        )
        
        print(f"\nOptimization Summary:")
        print(f"  Regime Comparison:")
        print(f"    Old Regime Tax: ₹{result['regime_comparison']['old_regime_tax']:,.0f}")
        print(f"    New Regime Tax: ₹{result['regime_comparison']['new_regime_tax']:,.0f}")
        print(f"    Recommended: {result['regime_comparison']['recommended_regime'].upper()}")
        print(f"    Savings: ₹{result['regime_comparison']['savings_amount']:,.0f}")
        
        print(f"\n  Suggestions: {len(result['suggestions'])}")
        print(f"  Potential Savings: ₹{result['potential_savings']:,.0f}")
        print(f"  Priority Actions: {len(result['priority_actions'])}")
        
        if result['priority_actions']:
            print(f"\n  Top Priority Actions:")
            for action in result['priority_actions'][:3]:
                print(f"    - {action['suggestion'][:80]}...")
        
        success = len(result['suggestions']) > 0
        print_result("Tax Optimization Service", success,
                     f"Generated {len(result['suggestions'])} suggestions" if success else "No suggestions generated")
        return success
        
    except Exception as e:
        print_result("Tax Optimization Service", False, f"Error: {str(e)}")
        return False


async def run_all_tests():
    """Run all Groq integration tests."""
    print("\n" + "=" * 80)
    print("  GROQ AI INTEGRATION TEST SUITE")
    print("  Tax Buddy Application")
    print("=" * 80)
    
    results = {}
    
    # Test 1: Configuration
    results['configuration'] = await test_1_configuration()
    
    if not results['configuration']:
        print("\n⚠️  WARNING: Groq API key not configured. Remaining tests will fail.")
        print("   Please set GROQ_API_KEY in backend/.env file")
        return results
    
    # Test 2: Client Initialization
    results['client_init'] = await test_2_client_initialization()
    
    if not results['client_init']:
        print("\n⚠️  WARNING: Client initialization failed. Remaining tests will fail.")
        return results
    
    # Test 3-8: Groq Features
    results['resolve_field'] = await test_3_resolve_ambiguous_field()
    results['extract_entity'] = await test_4_extract_entity_fallback()
    results['explain_validation'] = await test_5_explain_validation_issues()
    results['recommend_regime'] = await test_6_recommend_tax_regime()
    results['ai_validation'] = await test_7_ai_validation_service()
    results['tax_optimization'] = await test_8_tax_optimization_service()
    
    # Summary
    print_header("TEST SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {total_tests - passed_tests}")
    print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
    
    print("\nDetailed Results:")
    for test_name, passed in results.items():
        status = "✓" if passed else "✗"
        print(f"  {status} {test_name.replace('_', ' ').title()}")
    
    if passed_tests == total_tests:
        print("\n🎉 All tests passed! Groq AI integration is working correctly.")
    elif passed_tests > 0:
        print(f"\n⚠️  {total_tests - passed_tests} test(s) failed. Check the details above.")
    else:
        print("\n❌ All tests failed. Please check your Groq API configuration.")
    
    return results


if __name__ == "__main__":
    print("\nStarting Groq AI Integration Tests...")
    print("This will test all AI features in the Tax Buddy application.\n")
    
    try:
        results = asyncio.run(run_all_tests())
        
        # Exit with appropriate code
        all_passed = all(results.values()) if results else False
        sys.exit(0 if all_passed else 1)
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error running tests: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

# Made with Bob
