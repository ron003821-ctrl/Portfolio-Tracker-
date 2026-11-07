from datetime import date
import math
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from finance_utils import (xirr, investment_cashflows, benchmark_value, plan_deposit,
                           deposit_needed_without_selling, box3_base, next_peildatum, thresholds_for)

def test_xirr_simple_year():
    r = xirr([(date(2024, 1, 1), -1000), (date(2025, 1, 1), 1100)])
    assert abs(r - 0.0997) < 0.002          # 10% over 366 days (leap year)

def test_xirr_dca_beats_naive():
    # 1000 in 2 years ago, 1000 in last month, now worth 2100
    flows = [(date(2024, 9, 1), -1000), (date(2026, 8, 30), -1000), (date(2026, 9, 30), 2100)]
    r = xirr(flows)
    assert 0.02 < r < 0.06

def test_xirr_none_without_sign_change():
    assert xirr([(date(2024, 1, 1), -1), (date(2025, 1, 1), -1)]) is None

def test_cashflows_types():
    df = pd.DataFrame([
        dict(Date='2025-01-01', Type='Buy', Quantity=2, **{'Purchase Price': 100, 'Fee Amount': 1, 'Fee Unit': 'EUR', 'Income': 0}),
        dict(Date='2025-06-01', Type='Dividend', Quantity=0, **{'Purchase Price': 0, 'Fee Amount': 0, 'Fee Unit': 'None', 'Income': 5}),
        dict(Date='2025-07-01', Type='Staking Reward', Quantity=1, **{'Purchase Price': 0, 'Fee Amount': 0, 'Fee Unit': 'None', 'Income': 0}),
        dict(Date='2025-08-01', Type='Sell', Quantity=1, **{'Purchase Price': 150, 'Fee Amount': 1, 'Fee Unit': 'EUR', 'Income': 0}),
    ])
    assert investment_cashflows(df) == [(date(2025,1,1), -201), (date(2025,6,1), 5), (date(2025,8,1), 149)]
    assert len(investment_cashflows(df, include_dividends=False)) == 2

def test_benchmark_value():
    px = pd.DataFrame({'Date': pd.to_datetime(['2025-01-01', '2025-06-01', '2025-12-31']), 'Close': [10, 20, 40]})
    # buy €100 at 10 (10 units), buy €200 at 20 (10 units) → 20 units × 40
    assert benchmark_value([(date(2025,1,1), -100), (date(2025,6,1), -200)], px) == 800
    assert benchmark_value([(date(2024,1,1), -100)], px) is None   # before history

def test_plan_deposit_fills_underweight_only():
    cur = {'ETF': 50, 'Stock': 10, 'Crypto': 40}
    tgt = {'ETF': 70, 'Stock': 10, 'Crypto': 20}
    p = plan_deposit(cur, tgt, 20)
    assert p['Crypto'] == 0 and abs(sum(p.values()) - 20) < 1e-9
    assert p['ETF'] > p['Stock']

def test_plan_deposit_leftover_by_weight():
    p = plan_deposit({'ETF': 70, 'Stock': 10, 'Crypto': 20}, {'ETF': 70, 'Stock': 10, 'Crypto': 20}, 100)
    assert abs(p['ETF'] - 70) < 1e-9 and abs(p['Crypto'] - 20) < 1e-9

def test_deposit_needed():
    # crypto 40 of 100 with 20% target → total must reach 200
    assert deposit_needed_without_selling({'ETF': 50, 'Stock': 10, 'Crypto': 40},
                                          {'ETF': 70, 'Stock': 10, 'Crypto': 20}) == 100
    assert deposit_needed_without_selling({'Crypto': 1}, {'Crypto': 0}) == math.inf

def test_box3_and_dates():
    assert box3_base(43_000, 7_600, 3_800) == 39_200
    assert box3_base(10_000, 2_000, 3_800) == 10_000
    assert next_peildatum(date(2026, 9, 30)) == date(2027, 1, 1)
    assert next_peildatum(date(2027, 1, 1)) == date(2027, 1, 1)
    assert thresholds_for(2027)[0] == 2026 and thresholds_for(2026)[0] == 2026

def test_diff_cashflow():
    from finance_utils import diff_cashflow
    orig = pd.DataFrame([
        dict(id=1, Category='huur', Type='Expense', Amount=500.0, Notes=''),
        dict(id=2, Category='DUO', Type='Income', Amount=545.8, Notes=''),
        dict(id=3, Category='gym', Type='Expense', Amount=30.0, Notes=''),
    ])
    edited = pd.DataFrame([
        dict(id=1, Category='huur', Type='Expense', Amount=520.0, Notes=''),      # update
        dict(id=2, Category='DUO', Type='Income', Amount=545.8, Notes=''),        # unchanged
        dict(id=None, Category='spotify', Type='Expense', Amount=11.0, Notes=''), # insert
        dict(id=None, Category='', Type=None, Amount=None, Notes=None),           # blank row
    ])                                                                            # id 3 deleted
    ins, upd, dels, errs = diff_cashflow(orig, edited)
    assert ins == [{'category': 'spotify', 'type': 'Expense', 'amount': -11.0, 'notes': ''}]
    assert upd == [(1, {'category': 'huur', 'type': 'Expense', 'amount': -520.0, 'notes': ''})]
    assert dels == [3] and errs == []

def test_diff_cashflow_invalid_row_not_deleted():
    from finance_utils import diff_cashflow
    orig = pd.DataFrame([dict(id=1, Category='huur', Type='Expense', Amount=500.0, Notes='')])
    edited = pd.DataFrame([dict(id=1, Category='', Type='Expense', Amount=500.0, Notes='')])
    ins, upd, dels, errs = diff_cashflow(orig, edited)
    assert not ins and not upd and not dels and len(errs) == 1


# ── Daily recap ──
from finance_utils import change_from_closes, daily_moves

def test_change_from_closes_uses_last_two_prices():
    s = pd.Series([100.0, 110.0, 99.0],
                  index=pd.to_datetime(['2026-11-04', '2026-11-05', '2026-11-06']))
    pct, d = change_from_closes(s)
    assert abs(pct - (-0.1)) < 1e-12
    assert d == date(2026, 11, 6)

def test_change_from_closes_skips_gaps_and_needs_two_prices():
    s = pd.Series([50.0, float('nan'), 55.0], index=[date(2026, 11, 3), date(2026, 11, 4), date(2026, 11, 5)])
    pct, d = change_from_closes(s)
    assert abs(pct - 0.1) < 1e-12 and d == date(2026, 11, 5)
    assert change_from_closes(pd.Series([42.0])) == (None, None)
    assert change_from_closes(pd.Series(dtype=float)) == (None, None)

def test_daily_moves_euros_totals_and_order():
    holdings = pd.DataFrame({'Ticker': ['VWCE', 'BTC', 'ASML', 'NEW'],
                             'Value': [1100.0, 450.0, 500.0, 200.0]})
    # VWCE +10% → was 1000, moved +100;  BTC −10% → was 500, moved −50;  ASML flat;  NEW unknown
    table, total, pct = daily_moves(holdings, {'VWCE': 0.10, 'BTC': -0.10, 'ASML': 0.0, 'NEW': None})
    assert list(table['Ticker']) == ['VWCE', 'BTC', 'ASML', 'NEW']
    assert abs(table.loc[0, 'Move'] - 100) < 1e-9
    assert abs(table.loc[1, 'Move'] - (-50)) < 1e-9
    assert math.isnan(table.loc[3, 'Move'])
    assert abs(total - 50) < 1e-9
    assert abs(pct - 50 / 2000) < 1e-12      # yesterday's value of known positions: 1000+500+500

def test_daily_moves_nothing_known():
    table, total, pct = daily_moves(pd.DataFrame({'Ticker': ['X'], 'Value': [10.0]}), {})
    assert total == 0 and pct is None and len(table) == 1


# ── Overview HTML building blocks ──
from ui_components import eur, pct, heat_color, sparkline_svg, holdings_table, change_class

def test_eur_and_pct_formatting():
    assert eur(1234.5) == "€1,234" and eur(-5.691, 2) == "−€5.69" and eur(5.69, 2, sign=True) == "+€5.69"
    assert pct(0.0123) == "+1.23%" and pct(-0.071, 1) == "−7.1%"

def test_heat_color_scales_with_size_and_direction():
    assert heat_color(None) == heat_color(float('nan')) == "#2A2E37"
    assert heat_color(0.001) != heat_color(0.05) and heat_color(-0.001) != heat_color(-0.05)
    assert heat_color(0.02) != heat_color(-0.02)

def test_sparkline_direction_and_short_input():
    assert "#3DDC84" in sparkline_svg([1, 2, 3]) and "#FF6B6B" in sparkline_svg([3, 2, 1])
    assert "<svg" not in sparkline_svg([5]) and "<svg" not in sparkline_svg([])

def test_holdings_table_escapes_tickers_and_handles_missing_change():
    html = holdings_table([dict(ticker="<b>X</b>", category="ETF", closes=[], change=None,
                                value=100.0, weight=0.5, profit=-3.0, profit_pct=None)], "Holdings")
    assert "<b>X</b>" not in html and "&lt;b&gt;X&lt;/b&gt;" in html
    assert "pf-down" in html and "50.0%" in html
    assert change_class(None) == "pf-muted"
