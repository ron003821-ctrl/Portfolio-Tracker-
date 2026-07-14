"""Daily portfolio snapshot — runs headless in GitHub Actions.

Computes the current portfolio value + no-investment baseline from Supabase
data and upserts today's entry into portfolio_value_history, so the History
chart has a data point every day (not only on days you open the app).

Required environment variables: SUPABASE_URL, SUPABASE_KEY
The holdings / pricing logic mirrors portfolio_tracker.py.
"""
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf
from supabase import create_client

_url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
_key = (os.environ.get("SUPABASE_KEY") or "").strip()

if not _url or not _key:
    sys.exit("ERROR: SUPABASE_URL and/or SUPABASE_KEY secrets are missing.")
if "supabase.com/dashboard" in _url:
    sys.exit(
        "ERROR: SUPABASE_URL is the dashboard link. Use the Project URL instead "
        "(Supabase > Settings > API), it looks like: https://<project-ref>.supabase.co"
    )
if not _url.startswith("https://") or ".supabase.co" not in _url:
    sys.exit(
        f"ERROR: SUPABASE_URL looks wrong (got: {_url[:40]}...). "
        "Expected format: https://<project-ref>.supabase.co"
    )

supabase = create_client(_url, _key)

# ── Pricing (mirrors portfolio_tracker.py) ─────────────────────────────
_SUFFIX_CURRENCY = {
    '.AS': 'EUR', '.DE': 'EUR', '.PA': 'EUR', '.MI': 'EUR', '.MC': 'EUR',
    '.BR': 'EUR', '.CO': 'EUR', '.HE': 'EUR', '.OL': 'EUR', '.ST': 'EUR',
    '.L': 'GBP', '.SW': 'CHF',
}

KRAKEN_PAIRS = {
    'TAO-EUR': 'TAOEUR', 'TAO': 'TAOEUR',
    'BTC-EUR': 'XBTEUR', 'BTC': 'XBTEUR',
    'ETH-EUR': 'ETHEUR', 'ETH': 'ETHEUR',
    'SOL-EUR': 'SOLEUR', 'SOL': 'SOLEUR',
}

_EU_FALLBACK = {
    'FB2A': 'META', 'FB2A.DE': 'META', 'FB2A.AS': 'META', 'FB2A.F': 'META',
    'MSF.DE': 'MSFT', 'MSF.AS': 'MSFT', 'MSFT.DE': 'MSFT', 'MSFT.AS': 'MSFT',
    'APC.DE': 'AAPL', 'APC.AS': 'AAPL', 'AAPL.DE': 'AAPL', 'AAPL.AS': 'AAPL',
    'AMZ.DE': 'AMZN', 'AMZ.AS': 'AMZN', 'AMZN.DE': 'AMZN', 'AMZN.AS': 'AMZN',
    'ABEC.DE': 'GOOGL', 'ABEC.AS': 'GOOGL', 'GOOGL.DE': 'GOOGL', 'GOOG.DE': 'GOOGL',
    'NVDA.DE': 'NVDA', 'NVDA.AS': 'NVDA', 'NVD.DE': 'NVDA',
    'TL0.DE': 'TSLA', 'TL0.AS': 'TSLA', 'TSLA.DE': 'TSLA', 'TSLA.AS': 'TSLA',
    'NFC.DE': 'NFLX', 'NFLX.DE': 'NFLX',
}

_fx_cache = {}


def _fx_to_eur(ccy: str) -> float:
    if ccy == 'EUR':
        return 1.0
    if ccy not in _fx_cache:
        try:
            data = yf.Ticker(f"{ccy}EUR=X").history(period='2d')['Close']
            _fx_cache[ccy] = float(data.iloc[-1]) if not data.empty else 1.0
        except Exception:
            _fx_cache[ccy] = 1.0
    return _fx_cache[ccy]


def _ticker_currency(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith('-EUR'):
        return 'EUR'
    if t.endswith('-USD'):
        return 'USD'
    for suffix, ccy in _SUFFIX_CURRENCY.items():
        if t.endswith(suffix):
            return ccy
    return 'USD'


def _price_to_eur(raw: float, ticker: str) -> float:
    ccy = _ticker_currency(ticker)
    if ccy == 'EUR':
        return raw
    if ccy == 'GBP':
        return (raw / 100) * _fx_to_eur('GBP')
    return raw * _fx_to_eur(ccy)


def _kraken_price(pair: str) -> float:
    try:
        r = requests.get(f"https://api.kraken.com/0/public/Ticker?pair={pair}", timeout=10)
        if r.status_code == 200 and not r.json().get('error'):
            result = r.json().get('result', {})
            if result:
                return float(next(iter(result.values()))['c'][0])
    except Exception:
        pass
    return 0.0


def get_price(ticker: str) -> float:
    if ticker in KRAKEN_PAIRS:
        p = _kraken_price(KRAKEN_PAIRS[ticker])
        if p > 0:
            return p

    tickers_to_try = [ticker]
    if ticker in ['BTC', 'ETH', 'SOL', 'TAO']:
        tickers_to_try.extend([f"{ticker}-EUR", f"{ticker}-USD"])
    elif '-EUR' in ticker:
        tickers_to_try.append(ticker.replace('-EUR', '-USD'))
    if ticker.endswith('.DE'):
        tickers_to_try.append(ticker[:-3] + '.F')
    elif ticker.endswith('.F'):
        tickers_to_try.append(ticker[:-2] + '.DE')
    if ticker in _EU_FALLBACK:
        tickers_to_try.append(_EU_FALLBACK[ticker])

    for t in tickers_to_try:
        try:
            data = yf.Ticker(t).history(period='1d')['Close']
            if not data.empty:
                return _price_to_eur(float(data.iloc[-1]), t)
        except Exception:
            continue
    return 0.0


# ── Holdings (mirrors compute_portfolio) ───────────────────────────────
def main():
    trans = supabase.table('transactions').select('*').order('date').order('time').execute().data or []
    balances_rows = supabase.table('balances').select('*').eq('id', 1).execute().data or []
    balances = balances_rows[0] if balances_rows else {}

    aggregated = {}
    dividends = 0.0
    for row in trans:
        ticker = row['ticker']
        ticker = 'VUSA.AS' if ticker == 'VUSA' else 'VWRL.AS' if ticker == 'VWRL' else ticker
        agg = aggregated.setdefault(ticker, {'q': 0.0, 'c': 0.0})
        qty = float(row.get('quantity') or 0)
        price = float(row.get('purchase_price') or 0)
        fee = float(row.get('fee_amount') or 0)
        fee_unit = row.get('fee_unit') or 'None'
        ttype = row.get('type')

        if ttype == 'Buy':
            agg['c'] += qty * price + (fee if fee_unit == 'EUR' else 0.0)
            agg['q'] += qty
        elif ttype == 'Sell':
            if agg['q'] > 0:
                agg['c'] = max(agg['c'] - qty * (agg['c'] / agg['q']), 0.0)
            agg['q'] = max(agg['q'] - qty, 0.0)
        elif ttype == 'Staking':
            agg['c'] += qty * price
            agg['q'] += qty
        elif ttype == 'Staking Reward':
            agg['q'] += qty
        elif ttype == 'Transfer' and fee_unit == 'Asset':
            agg['q'] -= fee
        elif ttype == 'Dividend':
            dividends += float(row.get('income') or 0)

    assets_value = 0.0
    cost_basis = 0.0
    for ticker, agg in aggregated.items():
        if agg['q'] > 0:
            p = get_price(ticker)
            assets_value += agg['q'] * p
            cost_basis += agg['c']
            if p == 0.0:
                print(f"WARNING: no price for {ticker}")

    cash = float(balances.get('cash_balance') or 0)
    credit = float(balances.get('credit_mutuel_balance') or 0)
    cic = float(balances.get('cic_balance') or 0)

    total_value = assets_value + cash + credit + cic
    no_investment = cost_basis + cash + credit + cic - dividends

    today = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
    supabase.table('portfolio_value_history').upsert({
        'date': today.isoformat(),
        'total_value': total_value,
        'no_investment_value': no_investment,
    }, on_conflict='date').execute()

    print(f"Snapshot {today}: total €{total_value:,.2f} "
          f"(assets €{assets_value:,.2f} + cash €{cash + credit + cic:,.2f}), "
          f"baseline €{no_investment:,.2f}")


if __name__ == '__main__':
    main()
