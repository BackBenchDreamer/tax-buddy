from app.schemas import Regime, TaxComputationRequest
from app.services.tax import IndianTaxEngine, TaxComputationContext


def test_new_regime_tax_is_computed_with_cess() -> None:
    engine = IndianTaxEngine()
    request = TaxComputationRequest(
        regime=Regime.new,
        gross_income=1200000,
        deductions_80c=150000,
        deductions_80d=25000,
        tds=100000,
    )
    result = engine.compute(TaxComputationContext(request=request, validated_fields={}))

    assert result.regime == Regime.new
    assert result.taxable_income >= 0
    assert result.cess >= 0
    assert result.tax_liability >= result.cess
    assert result.breakdown[-1].label == "Net liability"


def test_old_regime_allows_deductions() -> None:
    engine = IndianTaxEngine()
    request = TaxComputationRequest(
        regime=Regime.old,
        gross_income=1000000,
        deductions_80c=150000,
        deductions_80d=25000,
        tds=150000,
    )
    result = engine.compute(TaxComputationContext(request=request, validated_fields={}))

    assert result.total_deductions > 0
    assert result.taxable_income < request.gross_income
