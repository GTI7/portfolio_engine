"""XIRR (money-weighted return) numerical solver.

Pure numerics, HA-independent, no new external dependencies (no numpy/scipy
- Newton-Raphson plus a bisection fallback is entirely doable with stdlib
math). Deliberately separate from MwrCalculator, matching the established
pattern of engine/transaction_replay.py: domain logic (which transactions
count as external cash flows, what status to report) lives in the
calculator; this module only solves "given dated cash flows, what constant
periodic rate makes their NPV zero."
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

DAYS_PER_YEAR = 365.0
#: (1 + rate) must stay strictly positive for fractional-exponent
#: discounting to be real-valued - this is the floor Newton steps are
#: clamped against, one unit above the true (1+rate) > 0 boundary.
MIN_RATE = -0.9999
MAX_NEWTON_ITERATIONS = 100
NEWTON_TOLERANCE = 1e-7
BISECTION_TOLERANCE = 1e-7
MAX_BISECTION_ITERATIONS = 200
#: Search bounds for the bisection fallback's initial bracket, and the cap
#: on Newton's own steps - +/-10,000% is generously wide for any real
#: portfolio return while still bounding the search.
BRACKET_LOW = -0.9999
BRACKET_HIGH = 100.0


@dataclass
class XirrResult:
    """`rate` is None when no root could be found - see xirr()'s docstring
    for the specific conditions. `method`/`iterations` are diagnostic, not
    part of any entity contract - useful for a diagnostics dump, not a
    dashboard.
    """

    rate: float | None
    method: str | None  # "newton" | "bisection" | None (no result)
    iterations: int


def xirr(cash_flows: list[tuple[datetime, float]], guess: float = 0.1) -> XirrResult:
    """Solve for the annualized rate r such that the net present value of
    `cash_flows` (each a (date, signed amount) pair) is zero:

        NPV(r) = sum(amount_i / (1+r)^((date_i - date_0).days / 365))

    where date_0 is the earliest date among the cash flows. Sign
    convention is the caller's responsibility (MwrCalculator's): negative
    for money leaving the investor's pocket into the portfolio, positive
    for money returned - this function doesn't know or care what the
    amounts represent, only that they need a sign change to have a real
    solution.

    Preconditions this function does NOT check (callers - MwrCalculator -
    are expected to check these first and report a specific status rather
    than let this function fail silently or confusingly):
      - at least 2 cash flows
      - at least one negative and one positive amount (a necessary
        condition for NPV(r) to have a root at all, for any well-behaved
        cash flow series)
    Given fewer than 2 flows or no sign change, this function may raise
    ValueError rather than attempt to guess an answer.

    Tries Newton-Raphson first (fast, usually converges in single digits
    of iterations for realistic financial cash flow series); falls back to
    bisection (slower but far more robust - guaranteed to converge given a
    valid bracket) if Newton fails to converge, diverges, or a derivative
    of zero is hit. Returns `XirrResult(rate=None, ...)` if neither method
    finds a root - this is a legitimate, expected outcome for pathological
    cash flow series, not treated as an error.
    """
    if len(cash_flows) < 2:
        raise ValueError("xirr requires at least 2 cash flows")
    has_negative = any(amount < 0 for _, amount in cash_flows)
    has_positive = any(amount > 0 for _, amount in cash_flows)
    if not (has_negative and has_positive):
        raise ValueError("xirr requires at least one negative and one positive cash flow")

    t0 = min(date for date, _ in cash_flows)
    years = [(date - t0).days / DAYS_PER_YEAR for date, _ in cash_flows]
    amounts = [amount for _, amount in cash_flows]

    newton_result = _newton(years, amounts, guess)
    if newton_result is not None:
        rate, iterations = newton_result
        return XirrResult(rate=rate, method="newton", iterations=iterations)

    bisection_result = _bisection(years, amounts)
    if bisection_result is not None:
        rate, iterations = bisection_result
        return XirrResult(rate=rate, method="bisection", iterations=iterations)

    return XirrResult(rate=None, method=None, iterations=0)


def _npv(rate: float, years: list[float], amounts: list[float]) -> float:
    return float(
        sum(amount / (1 + rate) ** year for year, amount in zip(years, amounts, strict=True))
    )


def _npv_derivative(rate: float, years: list[float], amounts: list[float]) -> float:
    return float(
        sum(
            -year * amount / (1 + rate) ** (year + 1)
            for year, amount in zip(years, amounts, strict=True)
        )
    )


def _newton(years: list[float], amounts: list[float], guess: float) -> tuple[float, int] | None:
    rate = guess
    for iteration in range(1, MAX_NEWTON_ITERATIONS + 1):
        f = _npv(rate, years, amounts)
        if abs(f) < NEWTON_TOLERANCE:
            return rate, iteration

        fprime = _npv_derivative(rate, years, amounts)
        if fprime == 0:
            return None  # flat derivative - Newton can't proceed, let bisection handle it

        next_rate = rate - f / fprime
        if next_rate <= MIN_RATE or not _is_finite(next_rate):
            # stepped into (or past) invalid domain / diverged - Newton
            # isn't going to recover from here, hand off to bisection
            return None
        rate = next_rate

    return None  # exceeded MAX_NEWTON_ITERATIONS without converging


def _bisection(years: list[float], amounts: list[float]) -> tuple[float, int] | None:
    lo, hi = BRACKET_LOW, BRACKET_HIGH
    f_lo = _npv(lo, years, amounts)
    f_hi = _npv(hi, years, amounts)

    if f_lo == 0:
        return lo, 0
    if f_hi == 0:
        return hi, 0
    if (f_lo > 0) == (f_hi > 0):
        # no sign change across the whole search bracket - no root findable
        # in this range regardless of how long bisection runs
        return None

    for iteration in range(1, MAX_BISECTION_ITERATIONS + 1):
        mid = (lo + hi) / 2
        f_mid = _npv(mid, years, amounts)

        if abs(f_mid) < BISECTION_TOLERANCE or (hi - lo) / 2 < BISECTION_TOLERANCE:
            return mid, iteration

        if (f_mid > 0) == (f_lo > 0):
            lo, f_lo = mid, f_mid
        else:
            hi, f_hi = mid, f_mid

    return None  # exceeded MAX_BISECTION_ITERATIONS without converging


def _is_finite(value: float) -> bool:
    return not (math.isnan(value) or math.isinf(value))
