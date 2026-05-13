"""
Phase 3 Implementation Tests: Tax Optimization Service
======================================================

Tests for AI-powered tax optimization features:
1. Regime recommendation (old vs new)
2. Deduction suggestions
3. Investment suggestions
4. Potential savings calculation
5. Error handling and fallbacks
6. End-to-end integration

Run with: python backend/test_phase3_tax_optimization.py
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.tax_optimization_service import (
    optimize_tax,
    recommend_regime,
    suggest_deductions,
    suggest_investments,
    calculate_potential_savings,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Data
# ---------------------------------------------------------------------------

# Test case 1: Low income, minimal deductions (New regime better)
TEST_CASE_1 = {
    "validated_data": {
        "GrossSalary": 600000,
        "Deductions": 50000,
        "TotalDeductions": 50000,
        "Section80C": 50000,
        "TDS": 12500,
    },
    "tax_result": {
        "regime": "old",
        "gross_income": 600000,
        "deductions": 50000,
        "taxable_income": 550000,
        "base_tax": 30000,
        "rebate": 12500,
        "total_tax": 18200,
    },
}

# Test case 2: High income, good deductions (Old regime better)
TEST_CASE_2 = {
    "validated_data": {
        "GrossSalary": 1200000,
        "Deductions": 200000,
        "TotalDeductions": 200000,
        "Section80C": 150000,
        "Section80D": 25000,
        "Section80CCD1B": 25000,
        "TDS": 95000,
    },
    "tax_result": {
        "regime": "old",
        "gross_income": 1200000,
        "deductions": 200000,
        "taxable_income": 1000000,
        "base_tax": 112500,
        "rebate": 0,
        "total_tax": 117000,
    },
}

# Test case 3: Medium income, underutilized deductions
TEST_CASE_3 = {
    "validated_data": {
        "GrossSalary": 900000,
        "Deductions": 80000,
        "TotalDeductions": 80000,
        "Section80C": 80000,
        "TDS": 45000,
    },
    "tax_result": {
        "regime": "old",
        "gross_income": 900000,
        "deductions": 80000,
        "taxable_income": 820000,
        "base_tax": 84000,
        "rebate": 0,
        "total_tax": 87360,
    },
}


# ---------------------------------------------------------------------------
# Test Functions
# ---------------------------------------------------------------------------

async def test_regime_recommendation():
    """Test 1: Regime recommendation with reasoning."""
    print("\n" + "=" * 70)
    print("TEST 1: Regime Recommendation")
    print("=" * 70)
    
    try:
        # Test case 1: Low income (new regime should be better)
        result1 = await recommend_regime(
            gross_income=600000,
            deductions=50000,
            deduction_breakdown={"Section80C": 50000},
            current_regime="old",
        )
        
        print(f"\n📊 Test Case 1: Low income (₹6L), minimal deductions")
        print(f"   Old Regime Tax: ₹{result1['old_regime_tax']:,.0f}")
        print(f"   New Regime Tax: ₹{result1['new_regime_tax']:,.0f}")
        print(f"   Recommended: {result1['recommended_regime'].upper()}")
        print(f"   Savings: ₹{result1['savings_amount']:,.0f}")
        print(f"   Reasoning: {result1['reasoning'][:150]}...")
        
        assert result1['recommended_regime'] in ['old', 'new'], "Invalid regime"
        assert result1['savings_amount'] >= 0, "Savings should be non-negative"
        
        # Test case 2: High income with good deductions (old regime should be better)
        result2 = await recommend_regime(
            gross_income=1200000,
            deductions=200000,
            deduction_breakdown={
                "Section80C": 150000,
                "Section80D": 25000,
                "Section80CCD1B": 25000,
            },
            current_regime="old",
        )
        
        print(f"\n📊 Test Case 2: High income (₹12L), good deductions")
        print(f"   Old Regime Tax: ₹{result2['old_regime_tax']:,.0f}")
        print(f"   New Regime Tax: ₹{result2['new_regime_tax']:,.0f}")
        print(f"   Recommended: {result2['recommended_regime'].upper()}")
        print(f"   Savings: ₹{result2['savings_amount']:,.0f}")
        print(f"   Reasoning: {result2['reasoning'][:150]}...")
        
        assert result2['recommended_regime'] in ['old', 'new'], "Invalid regime"
        
        print("\n✅ TEST 1 PASSED: Regime recommendations working correctly")
        return True
        
    except Exception as exc:
        print(f"\n❌ TEST 1 FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def test_deduction_suggestions():
    """Test 2: Deduction optimization suggestions."""
    print("\n" + "=" * 70)
    print("TEST 2: Deduction Suggestions")
    print("=" * 70)
    
    try:
        # Test with underutilized deductions
        suggestions = await suggest_deductions(
            gross_income=900000,
            deduction_breakdown={"Section80C": 80000},  # Can claim 70k more
        )
        
        print(f"\n💡 Generated {len(suggestions)} deduction suggestions:")
        
        for i, sugg in enumerate(suggestions, 1):
            print(f"\n   {i}. [{sugg['priority'].upper()}] {sugg['section']}")
            print(f"      {sugg['suggestion']}")
            print(f"      Potential Savings: ₹{sugg['potential_savings']:,.0f}")
            print(f"      Reasoning: {sugg['reasoning'][:100]}...")
        
        # Validate suggestions
        assert len(suggestions) > 0, "Should generate at least one suggestion"
        
        # Check for 80C suggestion (since only 80k claimed out of 150k)
        has_80c = any(s['section'] == '80C' for s in suggestions)
        assert has_80c, "Should suggest 80C optimization"
        
        # Check for 80CCD(1B) suggestion (NPS)
        has_nps = any(s['section'] == '80CCD(1B)' for s in suggestions)
        assert has_nps, "Should suggest NPS (80CCD1B)"
        
        # Validate priority levels
        for sugg in suggestions:
            assert sugg['priority'] in ['high', 'medium', 'low'], f"Invalid priority: {sugg['priority']}"
        
        print("\n✅ TEST 2 PASSED: Deduction suggestions working correctly")
        return True
        
    except Exception as exc:
        print(f"\n❌ TEST 2 FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def test_investment_suggestions():
    """Test 3: Investment recommendations."""
    print("\n" + "=" * 70)
    print("TEST 3: Investment Suggestions")
    print("=" * 70)
    
    try:
        # Test with room for investments
        suggestions = await suggest_investments(
            gross_income=900000,
            deduction_breakdown={"Section80C": 80000},
        )
        
        print(f"\n💰 Generated {len(suggestions)} investment suggestions:")
        
        for i, sugg in enumerate(suggestions, 1):
            print(f"\n   {i}. [{sugg['priority'].upper()}] {sugg.get('investment_type', 'N/A')}")
            print(f"      {sugg['suggestion']}")
            print(f"      Amount: ₹{sugg.get('amount', 0):,.0f}")
            print(f"      Potential Savings: ₹{sugg['potential_savings']:,.0f}")
            print(f"      Reasoning: {sugg['reasoning'][:100]}...")
        
        # Validate suggestions
        assert len(suggestions) > 0, "Should generate at least one investment suggestion"
        
        # Check for common investment types
        investment_types = [s.get('investment_type', '') for s in suggestions]
        
        # Should suggest at least one of: ELSS, PPF, NPS
        has_tax_saving = any(
            inv_type in ['ELSS', 'PPF', 'NPS', 'Health Insurance']
            for inv_type in investment_types
        )
        assert has_tax_saving, "Should suggest tax-saving investments"
        
        print("\n✅ TEST 3 PASSED: Investment suggestions working correctly")
        return True
        
    except Exception as exc:
        print(f"\n❌ TEST 3 FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def test_potential_savings_calculation():
    """Test 4: Potential savings calculation."""
    print("\n" + "=" * 70)
    print("TEST 4: Potential Savings Calculation")
    print("=" * 70)
    
    try:
        # Create mock data
        regime_comparison = {
            "savings_amount": 15000,
        }
        
        deduction_suggestions = [
            {"potential_savings": 14000},
            {"potential_savings": 10000},
        ]
        
        investment_suggestions = [
            {"potential_savings": 12000},
            {"potential_savings": 8000},
        ]
        
        total_savings = calculate_potential_savings(
            regime_comparison=regime_comparison,
            deduction_suggestions=deduction_suggestions,
            investment_suggestions=investment_suggestions,
        )
        
        print(f"\n💵 Savings Calculation:")
        print(f"   Regime Switch: ₹{regime_comparison['savings_amount']:,.0f}")
        print(f"   Deduction Optimization: ₹{sum(s['potential_savings'] for s in deduction_suggestions):,.0f}")
        print(f"   Investment Optimization: ₹{sum(s['potential_savings'] for s in investment_suggestions):,.0f}")
        print(f"   Total Potential Savings: ₹{total_savings:,.0f}")
        
        # Validate
        assert total_savings > 0, "Should calculate positive savings"
        assert isinstance(total_savings, float), "Should return float"
        
        # Total should be regime + max(deductions, investments) to avoid double counting
        expected = 15000 + max(24000, 20000)
        assert total_savings == expected, f"Expected {expected}, got {total_savings}"
        
        print("\n✅ TEST 4 PASSED: Savings calculation working correctly")
        return True
        
    except Exception as exc:
        print(f"\n❌ TEST 4 FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def test_end_to_end_optimization():
    """Test 5: End-to-end optimization flow."""
    print("\n" + "=" * 70)
    print("TEST 5: End-to-End Optimization")
    print("=" * 70)
    
    try:
        # Test with realistic data
        result = await optimize_tax(
            validated_data=TEST_CASE_3["validated_data"],
            tax_result=TEST_CASE_3["tax_result"],
            ocr_text="Sample OCR text",
        )
        
        print(f"\n🎯 Optimization Results:")
        print(f"\n   Regime Comparison:")
        print(f"      Old: ₹{result['regime_comparison']['old_regime_tax']:,.0f}")
        print(f"      New: ₹{result['regime_comparison']['new_regime_tax']:,.0f}")
        print(f"      Recommended: {result['regime_comparison']['recommended_regime'].upper()}")
        print(f"      Savings: ₹{result['regime_comparison']['savings_amount']:,.0f}")
        
        print(f"\n   Suggestions: {len(result['suggestions'])} total")
        print(f"   Priority Actions: {len(result['priority_actions'])}")
        print(f"   Total Potential Savings: ₹{result['potential_savings']:,.0f}")
        
        if result['priority_actions']:
            print(f"\n   Top Priority Actions:")
            for i, action in enumerate(result['priority_actions'][:3], 1):
                print(f"      {i}. {action['suggestion'][:80]}...")
        
        # Validate structure
        assert 'regime_comparison' in result, "Missing regime_comparison"
        assert 'suggestions' in result, "Missing suggestions"
        assert 'potential_savings' in result, "Missing potential_savings"
        assert 'priority_actions' in result, "Missing priority_actions"
        
        # Validate regime comparison
        assert 'old_regime_tax' in result['regime_comparison']
        assert 'new_regime_tax' in result['regime_comparison']
        assert 'recommended_regime' in result['regime_comparison']
        assert 'reasoning' in result['regime_comparison']
        
        # Validate suggestions
        if result['suggestions']:
            for sugg in result['suggestions']:
                assert 'category' in sugg
                assert 'priority' in sugg
                assert 'suggestion' in sugg
                assert 'reasoning' in sugg
                assert 'potential_savings' in sugg
        
        print("\n✅ TEST 5 PASSED: End-to-end optimization working correctly")
        return True
        
    except Exception as exc:
        print(f"\n❌ TEST 5 FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return False


async def test_error_handling():
    """Test 6: Error handling and fallbacks."""
    print("\n" + "=" * 70)
    print("TEST 6: Error Handling & Fallbacks")
    print("=" * 70)
    
    try:
        # Test with minimal/invalid data
        result = await optimize_tax(
            validated_data={"GrossSalary": 500000},
            tax_result={"regime": "old", "total_tax": 10000},
            ocr_text="",
        )
        
        print(f"\n🛡️ Fallback Results:")
        print(f"   Regime Comparison: {'Present' if result.get('regime_comparison') else 'Missing'}")
        print(f"   Suggestions: {len(result.get('suggestions', []))}")
        print(f"   Error: {result.get('error', 'None')}")
        
        # Should still return valid structure even with errors
        assert 'regime_comparison' in result, "Should have regime_comparison even on error"
        assert 'suggestions' in result, "Should have suggestions list even on error"
        assert 'potential_savings' in result, "Should have potential_savings even on error"
        
        print("\n✅ TEST 6 PASSED: Error handling working correctly")
        return True
        
    except Exception as exc:
        print(f"\n❌ TEST 6 FAILED: {exc}")
        import traceback
        traceback.print_exc()
        return False


# ---------------------------------------------------------------------------
# Main Test Runner
# ---------------------------------------------------------------------------

async def run_all_tests():
    """Run all Phase 3 tests."""
    print("\n" + "=" * 70)
    print("PHASE 3 IMPLEMENTATION TESTS: TAX OPTIMIZATION SERVICE")
    print("=" * 70)
    
    tests = [
        ("Regime Recommendation", test_regime_recommendation),
        ("Deduction Suggestions", test_deduction_suggestions),
        ("Investment Suggestions", test_investment_suggestions),
        ("Potential Savings Calculation", test_potential_savings_calculation),
        ("End-to-End Optimization", test_end_to_end_optimization),
        ("Error Handling & Fallbacks", test_error_handling),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as exc:
            print(f"\n❌ {test_name} crashed: {exc}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Phase 3 implementation is complete.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(run_all_tests())
    sys.exit(exit_code)

# Made with Bob
