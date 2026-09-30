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
