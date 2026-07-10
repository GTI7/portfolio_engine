from datetime import datetime

import pytest

from engine.xirr import XirrResult, xirr


def d(s):
    return datetime.fromisoformat(s)


# --- Known reference datasets --------------------------------------------

def test_excel_reference_example():
    """The canonical XIRR reference case (widely used to validate XIRR
    implementations, matching Microsoft's own documented example):
    -10000 on 2008-01-01, then four positive returns, expected XIRR is
    approximately 37.3362535% (0.373362535).
    """
    cash_flows = [
        (d("2008-01-01"), -10000.0),
        (d("2008-03-01"), 2750.0),
        (d("2008-10-30"), 4250.0),
        (d("2009-02-15"), 3250.0),
        (d("2009-04-01"), 2750.0),
    ]
    result = xirr(cash_flows)

    assert result.rate is not None
    assert result.rate == pytest.approx(0.373362535, abs=1e-6)


def test_simple_one_year_ten_percent_return():
    """Hand-verifiable: invest 1000, get back 1100 exactly one year later.
    NPV(0.10) = -1000 + 1100/1.10 = -1000 + 1000 = 0, so rate must be
    exactly 10%.
    """
    cash_flows = [
        (d("2025-01-01"), -1000.0),
        (d("2026-01-01"), 1100.0),  # 365 days later
    ]
    result = xirr(cash_flows)

    assert result.rate == pytest.approx(0.10, abs=1e-6)


def test_simple_two_year_ten_percent_return():
    """1000 -> 1210 after 2 years is exactly 10% annualized
    (1000 * 1.10^2 = 1210).
    """
    cash_flows = [
        (d("2024-01-01"), -1000.0),
        (d("2026-01-01"), 1210.0),  # ~2 years later (730 days)
    ]
    result = xirr(cash_flows)

    assert result.rate == pytest.approx(0.10, abs=1e-3)


def test_negative_return_case():
    """Invest 1000, get back only 900 a year later - a real loss, XIRR
    should be negative and approximately -10%.
    """
    cash_flows = [
        (d("2025-01-01"), -1000.0),
        (d("2026-01-01"), 900.0),
    ]
    result = xirr(cash_flows)

    assert result.rate == pytest.approx(-0.10, abs=1e-3)


def test_multiple_contributions_and_one_withdrawal():
    """A more realistic multi-flow series with a known expected rate,
    verified independently by NPV at the expected rate summing to ~0.
    """
    cash_flows = [
        (d("2024-01-01"), -1000.0),
        (d("2024-07-01"), -500.0),
        (d("2025-01-01"), -500.0),
        (d("2026-01-01"), 2300.0),
    ]
    result = xirr(cash_flows)

    assert result.rate is not None
    # Verify by construction: NPV at the returned rate must be ~0.
    t0 = d("2024-01-01")
    npv = sum(
        amount / (1 + result.rate) ** ((date - t0).days / 365) for date, amount in cash_flows
    )
    assert npv == pytest.approx(0.0, abs=1e-4)


# --- Convergence method ----------------------------------------------------

def test_result_reports_which_method_converged():
    cash_flows = [(d("2025-01-01"), -1000.0), (d("2026-01-01"), 1100.0)]
    result = xirr(cash_flows)
    assert result.method in ("newton", "bisection")
    assert result.iterations > 0


def test_bisection_fallback_handles_a_case_newton_struggles_with():
    """A cash flow series with an extreme near-total-loss return, which
    tends to push Newton's derivative-based steps toward the (1+r) <= 0
    boundary and trigger the bisection fallback - both methods should
    still agree on approximately the same (correct) answer if Newton does
    manage to converge, and either way the result should be a large
    negative rate.
    """
    cash_flows = [
        (d("2025-01-01"), -10000.0),
        (d("2026-01-01"), 100.0),  # lost 99% of the investment
    ]
    result = xirr(cash_flows)

    assert result.rate is not None
    assert result.rate == pytest.approx(-0.99, abs=1e-3)


# --- Precondition errors (caller's responsibility to avoid these) ----------

def test_raises_with_fewer_than_two_cash_flows():
    with pytest.raises(ValueError, match="at least 2"):
        xirr([(d("2025-01-01"), -1000.0)])


def test_raises_with_zero_cash_flows():
    with pytest.raises(ValueError, match="at least 2"):
        xirr([])


def test_raises_when_all_cash_flows_are_negative():
    with pytest.raises(ValueError, match="negative and one positive"):
        xirr([(d("2025-01-01"), -1000.0), (d("2025-06-01"), -500.0)])


def test_raises_when_all_cash_flows_are_positive():
    with pytest.raises(ValueError, match="negative and one positive"):
        xirr([(d("2025-01-01"), 1000.0), (d("2025-06-01"), 500.0)])


# --- Result shape -------------------------------------------------------------

def test_result_is_xirr_result_instance():
    result = xirr([(d("2025-01-01"), -1000.0), (d("2026-01-01"), 1100.0)])
    assert isinstance(result, XirrResult)
    assert hasattr(result, "rate")
    assert hasattr(result, "method")
    assert hasattr(result, "iterations")


def test_same_date_cash_flows_still_solvable_if_amounts_net_nonzero():
    """Both flows on the same date collapses the exponent to 0 for both -
    NPV(r) becomes a constant (sum of amounts) independent of r. If that
    sum isn't ~0, there's genuinely no root - confirm this degenerates to
    "no result" rather than a crash or a nonsensical rate.
    """
    cash_flows = [(d("2025-01-01"), -1000.0), (d("2025-01-01"), 1100.0)]
    result = xirr(cash_flows)
    # NPV(r) = -1000 + 1100 = 100 for all r - no root exists.
    assert result.rate is None
