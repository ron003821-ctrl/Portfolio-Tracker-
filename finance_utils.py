"""Pure finance helpers (no Streamlit / Supabase) so they can be unit-tested.

- xirr / investment_cashflows / benchmark_*   money-weighted return + same-cash-flow benchmark
- plan_deposit / deposit_needed_without_selling   rebalancing with new money only
- box3_base / next_peildatum / thresholds_for     1 January check (toeslagen, Box 3)
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

import pandas as pd

# ─────────────────────────────────────────────────────────────
# Money-weighted return (XIRR)
# ─────────────────────────────────────────────────────────────

def xirr(cashflows: Iterable[tuple[date, float]]) -> float | None:
    """Annualised internal rate of return for dated cash flows.

    Convention: money you put in is negative, money you get back (sells,
    dividends, today's value) is positive. Returns a fraction (0.08 = 8 %/yr),
    or None when it can't be computed (no sign change, < 2 flows, …).
    """
    flows = sorted((pd.Timestamp(d).date(), float(a)) for d, a in cashflows if a)
    if len(flows) < 2:
        return None
    if not (any(a < 0 for _, a in flows) and any(a > 0 for _, a in flows)):
        return None
    t0 = flows[0][0]
    ts = [((d - t0).days / 365.25, a) for d, a in flows]

    def npv(r: float) -> float:
        return sum(a / (1 + r) ** t for t, a in ts)

    # Bisection on a bracket — robust (NPV is monotone for typical invest-then-value flows)
    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-7:
            break
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def investment_cashflows(trans: pd.DataFrame, include_dividends: bool = True) -> list[tuple[date, float]]:
    """External cash flows into/out of the investment portfolio.

    Buy / Staking(buy)  → −(qty × price + EUR fee)
    Sell                → +(qty × price − EUR fee)
    Dividend            → +income (skip with include_dividends=False, e.g. for a benchmark)
    Transfer (EUR fee)  → −fee
    Staking Reward      → nothing (free tokens show up in today's value)
    """
    out: list[tuple[date, float]] = []
    if trans is None or trans.empty:
        return out
    for _, r in trans.iterrows():
        d = pd.to_datetime(r.get('Date'), errors='coerce')
        if pd.isna(d):
            continue
        try:
            q = float(r.get('Quantity') or 0)
            p = float(r.get('Purchase Price') or 0)
            fee = float(r.get('Fee Amount') or 0)
            inc = float(r.get('Income') or 0)
        except (TypeError, ValueError):
            continue
        fee_eur = fee if r.get('Fee Unit') == 'EUR' else 0.0
        t = r.get('Type')
        if t in ('Buy', 'Staking'):
            out.append((d.date(), -(q * p + fee_eur)))
        elif t == 'Sell':
            out.append((d.date(), q * p - fee_eur))
        elif t == 'Dividend' and include_dividends:
            out.append((d.date(), inc))
        elif t == 'Transfer' and fee_eur:
            out.append((d.date(), -fee_eur))
    return out


def benchmark_value(flows: list[tuple[date, float]], prices: pd.DataFrame) -> float | None:
    """Value today if every euro had gone into one benchmark instead.

    `prices`: DataFrame with 'Date' and 'Close' (EUR). Money in (negative flow)
    buys benchmark units at that day's close; money out (positive flow, e.g. a
    sell) sells units. Dividends from the real portfolio are *not* reinvested
    here — use an accumulating benchmark (e.g. VWCE) so its own dividends are in the price.
    Returns None if any flow predates the price history.
    """
    if prices is None or prices.empty or not flows:
        return None
    px = prices[['Date', 'Close']].copy()
    px['Date'] = pd.to_datetime(px['Date']).dt.tz_localize(None).dt.normalize()
    px = px.dropna().sort_values('Date').set_index('Date')['Close']
    units = 0.0
    for d, amt in sorted(flows):
        ts = pd.Timestamp(d)
        hist = px.loc[:ts]
        if hist.empty:
            return None
        price = float(hist.iloc[-1])
        if price <= 0:
            return None
        units += -amt / price  # negative flow (money in) → buy units
    return max(units, 0.0) * float(px.iloc[-1])


# ─────────────────────────────────────────────────────────────
# Rebalancing with new money only (no selling)
# ─────────────────────────────────────────────────────────────

def plan_deposit(current: dict[str, float], targets_pct: dict[str, float],
                 deposit: float) -> dict[str, float]:
    """Split `deposit` over categories so the portfolio moves toward target
    WITHOUT selling anything. Underweight categories are filled first,
    proportionally to how far below target they are; anything left once all
    are on target is spread by target weight."""
    cats = list(targets_pct)
    deposit = max(float(deposit), 0.0)
    if deposit == 0 or not cats:
        return {c: 0.0 for c in cats}
    w = {c: max(float(targets_pct[c]), 0.0) / 100 for c in cats}
    total_after = sum(max(current.get(c, 0.0), 0.0) for c in cats) + deposit
    gaps = {c: max(w[c] * total_after - current.get(c, 0.0), 0.0) for c in cats}
    gap_sum = sum(gaps.values())
    if gap_sum <= 0:
        wsum = sum(w.values()) or 1.0
        return {c: deposit * w[c] / wsum for c in cats}
    if gap_sum >= deposit:
        return {c: deposit * gaps[c] / gap_sum for c in cats}
    leftover = deposit - gap_sum
    wsum = sum(w.values()) or 1.0
    return {c: gaps[c] + leftover * w[c] / wsum for c in cats}


def deposit_needed_without_selling(current: dict[str, float],
                                   targets_pct: dict[str, float]) -> float:
    """Extra money needed (buying only) until every category is at or below
    its target share — i.e. until the most overweight category is diluted
    back to target."""
    total = sum(max(v, 0.0) for v in current.values())
    needed_total = total
    for c, pct in targets_pct.items():
        v = max(current.get(c, 0.0), 0.0)
        if v <= 0:
            continue
        if pct <= 0:
            return float('inf')
        needed_total = max(needed_total, v / (pct / 100))
    return max(needed_total - total, 0.0)


# ─────────────────────────────────────────────────────────────
# 1 January check — Box 3 base and toeslagen asset limits (single person)
# Update these once a year (Belastingdienst / toeslagen.nl publishes them).
# ─────────────────────────────────────────────────────────────

NL_THRESHOLDS: dict[int, dict[str, float]] = {
    2026: {
        'huurtoeslag':    38_479,   # vermogensgrens huurtoeslag, alleenstaande
        'zorgtoeslag':   146_011,   # vermogensgrens zorgtoeslag, alleenstaande
        'box3_free':      59_357,   # heffingsvrij vermogen
        'debt_threshold':  3_800,   # schuldendrempel box 3
    },
}


def thresholds_for(year: int) -> tuple[int, dict[str, float]]:
    """Thresholds for `year`, or the most recent known year (returned too)."""
    if year in NL_THRESHOLDS:
        return year, NL_THRESHOLDS[year]
    known = max(y for y in NL_THRESHOLDS if y <= year) if any(y <= year for y in NL_THRESHOLDS) \
        else min(NL_THRESHOLDS)
    return known, NL_THRESHOLDS[known]


def next_peildatum(today: date) -> date:
    """The 1 January that counts next. On 1 Jan itself, that's today."""
    return today if (today.month, today.day) == (1, 1) else date(today.year + 1, 1, 1)


def box3_base(assets: float, debts: float, debt_threshold: float) -> float:
    """Rendementsgrondslag: assets minus the part of debts above the threshold.
    This is also the 'vermogen' used for the toeslagen asset limits."""
    deductible = max(float(debts) - float(debt_threshold), 0.0)
    return max(float(assets) - deductible, 0.0)
