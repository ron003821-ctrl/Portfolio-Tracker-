import streamlit as st
from supabase import create_client
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, time, date, timezone, tzinfo
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Portfolio Tracker", page_icon="", layout="wide")

# -------------------------
# Asset Category Detection
# -------------------------
_KNOWN_CRYPTO = {
    'BTC','ETH','SOL','TAO','XMR','LTC','ADA','DOGE','BNB','XRP','AVAX','DOT',
    'BTC-EUR','BTC-USD','ETH-EUR','ETH-USD','SOL-EUR','SOL-USD',
    'TAO-EUR','TAO-USD','XMR-EUR','ADA-EUR','DOGE-EUR','BNB-EUR','XRP-EUR',
}

# Exchange suffixes → pricing currency (NOT asset type — .AS can be ETF or Stock)
# GBP: London Stock Exchange (prices in pence → divide by 100 → convert to EUR)
# CHF: Swiss Exchange
# EUR: all Euronext / Xetra / Borsa Italiana exchanges
_SUFFIX_CURRENCY = {
    '.AS': 'EUR', '.DE': 'EUR', '.PA': 'EUR', '.MI': 'EUR', '.MC': 'EUR',
    '.BR': 'EUR', '.CO': 'EUR', '.HE': 'EUR', '.OL': 'EUR', '.ST': 'EUR',
    '.L':  'GBP',  # London (pence)
    '.SW': 'CHF',
}

# Well-known ETF tickers (exchange suffix is NOT a reliable ETF signal)
_KNOWN_ETFS = {
    # iShares / BlackRock
    'IWDA','IWDA.AS','CSPX','CSPX.AS','IEMG','IEMG.AS','AGGH','AGGH.AS',
    'IUSQ','IUSQ.AS','ISAC','ISAC.AS','MEUD','MEUD.AS','IQQQ','IQQQ.DE',
    # Vanguard
    'VWRL','VWRL.AS','VUSA','VUSA.AS','VUAA','VUAA.AS','SWRD','SWRD.AS',
    'VWCE','VWCE.DE','VGWL','VGWL.SW',
    # Invesco / Xtrackers / Amundi / Lyxor
    'EQQQ','EQQQ.AS','QDVE','QDVE.DE','SLMC','SLMC.DE','DAXEX','DAXEX.DE',
    'PAEEM','PAEEM.AS','LCUW','LCUW.DE',
    # US ETFs
    'VOO','VTI','QQQ','SPY','IVV','VEA','VWO','GLD','TLT','SHY','AGG',
    'ARKK','XLK','XLF','VNQ','SCHD',
}

def auto_detect_category(ticker: str) -> str:
    """Crypto → known list. ETF → known ETF set. Everything else → Stock.
    Exchange suffixes (.AS, .DE …) are NOT used to detect ETFs because those
    suffixes only indicate which exchange a security trades on."""
    t = ticker.upper()
    base = t.split('-')[0]
    if t in _KNOWN_CRYPTO or base in _KNOWN_CRYPTO:
        return 'Crypto'
    if t in _KNOWN_ETFS:
        return 'ETF'
    return 'Stock'

@st.cache_data(ttl=3600)
def _fx_to_eur(from_currency: str) -> float:
    """Return 1 unit of `from_currency` in EUR. Falls back to 1.0 on error."""
    if from_currency == 'EUR':
        return 1.0
    pair = f"{from_currency}EUR=X"
    try:
        data = yf.Ticker(pair).history(period='2d', interval='1d')['Close']
        if not data.empty:
            return float(data.iloc[-1])
    except Exception:
        pass
    return 1.0

def _ticker_currency(ticker: str) -> str:
    """Infer the pricing currency from the ticker format."""
    t = ticker.upper()
    if t.endswith('-EUR') or t.endswith('EUR=X'):
        return 'EUR'
    if t.endswith('-USD') or t.endswith('USD=X'):
        return 'USD'
    for suffix, ccy in _SUFFIX_CURRENCY.items():
        if t.endswith(suffix):
            return ccy
    # No recognised suffix → assume US stock → USD
    return 'USD'

def _price_to_eur(raw_price: float, ticker: str) -> float:
    """Convert a raw yfinance price to EUR."""
    ccy = _ticker_currency(ticker)
    if ccy == 'EUR':
        return raw_price
    if ccy == 'GBP':
        # London prices are in pence → divide by 100 first
        return (raw_price / 100) * _fx_to_eur('GBP')
    return raw_price * _fx_to_eur(ccy)

# -------------------------
# Styling
# -------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Ropa+Sans&family=Inter:wght@300;400;500;600;700&family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

    .material-symbols-outlined {
        font-family: 'Material Symbols Outlined';
        font-weight: normal;
        font-style: normal;
        font-size: 18px;
        line-height: 1;
        letter-spacing: normal;
        text-transform: none;
        display: inline-block;
        white-space: nowrap;
        word-wrap: normal;
        direction: ltr;
        -webkit-font-feature-settings: 'liga';
        -webkit-font-smoothing: antialiased;
        vertical-align: middle;
        color: #c9a84c;
        margin-right: 0.35rem;
    }

    /* ═══════════════════════════════════════════
       BRAND TOKENS
       Navy   #080c18  #0c1120  #101828  #192138
       Gold   #c9a84c  rgba(201,168,76,x)
       Cream  #f0ece0  #a8a49a  #5c5a54
       Green  #27ae7a  Red  #c94c4c
       Radius buttons: 4px  cards/inputs: 6px
    ═══════════════════════════════════════════ */

    html, body, .stApp, .main {
        font-family: 'Inter', sans-serif !important;
        background-color: #080c18 !important;
        color: #f0ece0 !important;
    }

    .main .block-container {
        padding-top: 0 !important;
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
        max-width: 1280px !important;
    }

    /* ── Typography ── */
    h1, h2, h3, h4 { font-family: 'Ropa Sans', sans-serif !important; }

    h1 {
        color: #f0ece0 !important;
        font-size: 1.8rem !important;
        font-weight: 400 !important;
        letter-spacing: 0.04em !important;
        margin-bottom: 0 !important;
        border: none !important;
    }

    h2 {
        color: #f0ece0 !important;
        font-size: 1.1rem !important;
        font-weight: 400 !important;
        letter-spacing: 0.05em !important;
        -webkit-text-fill-color: unset !important;
        background: none !important;
        margin-bottom: 0.75rem !important;
    }

    h3 {
        color: #a8a49a !important;
        font-size: 0.72rem !important;
        font-weight: 400 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.14em !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #0a0d1a !important;
        border-right: 1px solid #192138 !important;
    }

    [data-testid="stSidebar"] .st-expander {
        background-color: #0c1120 !important;
        border: 1px solid #192138 !important;
        border-radius: 6px !important;
        margin-bottom: 0.4rem !important;
        box-shadow: none !important;
        transition: border-color 0.15s !important;
    }

    [data-testid="stSidebar"] .st-expander:hover {
        border-color: rgba(201,168,76,0.4) !important;
        transform: none !important;
        box-shadow: none !important;
    }

    /* ── Navigation Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background-color: #080c18 !important;
        border-bottom: 1px solid #192138 !important;
        gap: 0 !important;
        padding: 0 !important;
    }

    .stTabs [role="tab"] {
        background: transparent !important;
        border: none !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 0 !important;
        color: #5c5a54 !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.78rem !important;
        letter-spacing: 0.07em !important;
        text-transform: uppercase !important;
        padding: 0.9rem 1.3rem !important;
        transition: color 0.15s !important;
        box-shadow: none !important;
    }

    .stTabs [role="tab"]:hover {
        color: #a8a49a !important;
        background: rgba(201,168,76,0.03) !important;
        transform: none !important;
        box-shadow: none !important;
    }

    .stTabs [aria-selected="true"] {
        color: #c9a84c !important;
        border-bottom: 2px solid #c9a84c !important;
        background: transparent !important;
        font-weight: 600 !important;
    }

    /* ── Buttons — 4px radius, gold on hover ── */
    .stButton > button {
        background-color: transparent !important;
        color: #a8a49a !important;
        border: 1px solid #1f2d4a !important;
        border-radius: 4px !important;
        font-family: 'Inter', sans-serif !important;
        font-weight: 500 !important;
        font-size: 0.75rem !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
        padding: 0.42rem 0.9rem !important;
        box-shadow: none !important;
        transition: all 0.15s !important;
    }

    .stButton > button:hover {
        background-color: rgba(201,168,76,0.08) !important;
        border-color: #c9a84c !important;
        color: #c9a84c !important;
        transform: none !important;
        box-shadow: none !important;
    }

    /* ── Metric Cards — 6px radius ── */
    [data-testid="stMetric"] {
        background-color: #0c1120 !important;
        border: 1px solid #192138 !important;
        border-left: 3px solid #c9a84c !important;
        border-radius: 6px !important;
        padding: 1.1rem 1.3rem !important;
        box-shadow: none !important;
    }

    [data-testid="stMetricLabel"] p {
        color: #5c5a54 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.63rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.11em !important;
    }

    [data-testid="stMetricValue"] {
        color: #f0ece0 !important;
        font-family: 'Ropa Sans', sans-serif !important;
        font-size: 1.55rem !important;
        font-weight: 400 !important;
        letter-spacing: 0.02em !important;
    }

    [data-testid="stMetricDelta"] {
        font-size: 0.78rem !important;
        font-weight: 500 !important;
    }

    /* ── Inputs — 6px radius ── */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stDateInput > div > div > input {
        background-color: #080c18 !important;
        border: 1px solid #192138 !important;
        border-radius: 6px !important;
        color: #f0ece0 !important;
        font-family: 'Inter', sans-serif !important;
        font-size: 0.85rem !important;
    }

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: #c9a84c !important;
        box-shadow: 0 0 0 2px rgba(201,168,76,0.15) !important;
        transform: none !important;
    }

    .stSelectbox > div > div {
        background-color: #080c18 !important;
        border: 1px solid #192138 !important;
        border-radius: 6px !important;
        color: #f0ece0 !important;
    }

    /* ── DataFrames — 6px radius ── */
    .stDataFrame {
        border: 1px solid #192138 !important;
        border-radius: 6px !important;
        overflow: hidden !important;
        box-shadow: none !important;
    }
    .stDataFrame:hover { box-shadow: none !important; }

    /* ── Misc ── */
    .stCaption {
        color: #5c5a54 !important;
        font-size: 0.72rem !important;
        font-style: normal !important;
    }
    hr { border-color: #192138 !important; }
    .stAlert { border-radius: 6px !important; box-shadow: none !important; }

    /* ── Mobile ── */
    @media (max-width: 768px) {
        .main .block-container {
            padding-left: 0.6rem !important;
            padding-right: 0.6rem !important;
        }
        [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
        [data-testid="stMetricLabel"] p { font-size: 0.56rem !important; }
        [data-testid="stMetric"] { padding: 0.7rem 0.8rem !important; }
        .stTabs [role="tab"] {
            font-size: 0.6rem !important;
            padding: 0.65rem 0.4rem !important;
            letter-spacing: 0.04em !important;
        }
        /* Header bar: stack vertically on mobile */
        .main .block-container > div:first-child div[style*="display:flex"] {
            flex-direction: column !important;
            align-items: flex-start !important;
        }
        /* Sidebar inputs full width */
        .stNumberInput, .stTextInput, .stSelectbox { width: 100% !important; }
        /* Reduce h1/h2 sizes */
        h1 { font-size: 1.3rem !important; }
        h2 { font-size: 0.95rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Supabase
# -------------------------
@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error(f"Cannot connect to Supabase. Make sure your secrets are configured. Error: {e}")
    st.stop()

# -------------------------
# Balances
# -------------------------
def load_balances():
    default = {'cash_balance': 0.0, 'credit_mutuel_balance': 0.0, 'cic_balance': 0.0}
    try:
        res = supabase.table('balances').select('*').eq('id', 1).execute()
        if res.data:
            row = res.data[0]
            return {
                'cash_balance': float(row.get('cash_balance', 0.0)),
                'credit_mutuel_balance': float(row.get('credit_mutuel_balance', 0.0)),
                'cic_balance': float(row.get('cic_balance', 0.0))
            }
        supabase.table('balances').insert({'id': 1, **default}).execute()
        return default
    except Exception as e:
        st.error(f"Error loading balances: {e}")
        return default

def save_balances(cash, credit, cic):
    try:
        supabase.table('balances').upsert({
            'id': 1,
            'cash_balance': float(cash),
            'credit_mutuel_balance': float(credit),
            'cic_balance': float(cic)
        }).execute()
        st.session_state.balances_saved = True
    except Exception as e:
        st.error(f"Error saving balances: {e}")

def load_balances_history():
    try:
        res = supabase.table('balances_history').select('*').order('date').execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['date'] = pd.to_datetime(df['date']).dt.date
            return df.sort_values('date').reset_index(drop=True)
        return pd.DataFrame(columns=['date', 'cash', 'credit_mutuel', 'cic'])
    except Exception as e:
        st.error(f"Error loading balances history: {e}")
        return pd.DataFrame(columns=['date', 'cash', 'credit_mutuel', 'cic'])

def save_balance_history_entry(entry_date: date, cash: float, credit: float, cic: float):
    try:
        supabase.table('balances_history').upsert({
            'date': entry_date.isoformat(),
            'cash': float(cash),
            'credit_mutuel': float(credit),
            'cic': float(cic)
        }, on_conflict='date').execute()
    except Exception as e:
        st.error(f"Error saving balance history: {e}")

# -------------------------
# Portfolio value history
# -------------------------
def load_portfolio_value_history():
    try:
        res = supabase.table('portfolio_value_history').select('*').order('date').execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df['date'] = pd.to_datetime(df['date']).dt.date
            return df.sort_values('date').reset_index(drop=True)
        return pd.DataFrame(columns=['date', 'total_value', 'no_investment_value'])
    except Exception as e:
        st.error(f"Error loading portfolio value history: {e}")
        return pd.DataFrame(columns=['date', 'total_value', 'no_investment_value'])

def save_portfolio_value_entry(entry_date: date, total_value: float, no_investment_value: float = None):
    try:
        entry = {'date': entry_date.isoformat(), 'total_value': float(total_value)}
        if no_investment_value is not None:
            entry['no_investment_value'] = float(no_investment_value)
        supabase.table('portfolio_value_history').upsert(entry, on_conflict='date').execute()
    except Exception as e:
        st.error(f"Error saving portfolio value entry: {e}")

# -------------------------
# Transactions
# -------------------------
TRANS_DISPLAY_COLS = ['Date', 'Time', 'Type', 'Ticker', 'Quantity', 'Purchase Price', 'Fee Amount', 'Fee Unit', 'Income']

def load_transactions():
    try:
        res = supabase.table('transactions').select('*').order('date').order('time').execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df = df.rename(columns={
                'date': 'Date', 'time': 'Time', 'type': 'Type', 'ticker': 'Ticker',
                'quantity': 'Quantity', 'purchase_price': 'Purchase Price',
                'fee_amount': 'Fee Amount', 'fee_unit': 'Fee Unit', 'income': 'Income'
            })
            df['Date'] = pd.to_datetime(df['Date']).dt.date
            for col in ['Quantity', 'Purchase Price', 'Fee Amount', 'Income']:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            return df
        return pd.DataFrame(columns=['id'] + TRANS_DISPLAY_COLS)
    except Exception as e:
        st.error(f"Error loading transactions: {e}")
        return pd.DataFrame(columns=['id'] + TRANS_DISPLAY_COLS)

def add_transaction_db(trans_date, trans_time, trans_type, ticker, quantity, purchase_price, fee_amount, fee_unit, income):
    try:
        date_str = trans_date.isoformat() if hasattr(trans_date, 'isoformat') else str(trans_date)
        time_str = trans_time.strftime("%H:%M") if hasattr(trans_time, 'strftime') else str(trans_time)
        supabase.table('transactions').insert({
            'date': date_str, 'time': time_str, 'type': trans_type, 'ticker': ticker,
            'quantity': float(quantity), 'purchase_price': float(purchase_price),
            'fee_amount': float(fee_amount), 'fee_unit': fee_unit, 'income': float(income)
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error adding transaction: {e}")
        return False

def update_transaction_db(trans_id, trans_date, trans_time, trans_type, ticker, quantity, purchase_price, fee_amount, fee_unit, income):
    try:
        date_str = trans_date.isoformat() if hasattr(trans_date, 'isoformat') else str(trans_date)
        time_str = trans_time.strftime("%H:%M") if hasattr(trans_time, 'strftime') else str(trans_time)
        supabase.table('transactions').update({
            'date': date_str, 'time': time_str, 'type': trans_type, 'ticker': ticker,
            'quantity': float(quantity), 'purchase_price': float(purchase_price),
            'fee_amount': float(fee_amount), 'fee_unit': fee_unit, 'income': float(income)
        }).eq('id', int(trans_id)).execute()
        return True
    except Exception as e:
        st.error(f"Error updating transaction: {e}")
        return False

def delete_transaction_db(trans_id):
    try:
        supabase.table('transactions').delete().eq('id', int(trans_id)).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting transaction: {e}")
        return False

# -------------------------
# Cashflow
# -------------------------
CF_DISPLAY_COLS = ['Category', 'Type', 'Amount', 'Notes']

def load_cashflow():
    try:
        res = supabase.table('cashflow').select('*').execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df = df.rename(columns={
                'category': 'Category', 'type': 'Type', 'amount': 'Amount', 'notes': 'Notes'
            })
            df['Amount'] = pd.to_numeric(df['Amount'], errors='coerce').fillna(0.0)
            df['Notes'] = df['Notes'].fillna('')
            return df
        return pd.DataFrame(columns=['id'] + CF_DISPLAY_COLS)
    except Exception as e:
        st.error(f"Error loading cashflow: {e}")
        return pd.DataFrame(columns=['id'] + CF_DISPLAY_COLS)

def add_cashflow_db(category, cf_type, amount, notes):
    try:
        supabase.table('cashflow').insert({
            'category': category, 'type': cf_type, 'amount': float(amount), 'notes': notes
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error adding cashflow entry: {e}")
        return False

def update_cashflow_db(cf_id, category, cf_type, amount, notes):
    try:
        supabase.table('cashflow').update({
            'category': category, 'type': cf_type, 'amount': float(amount), 'notes': notes
        }).eq('id', int(cf_id)).execute()
        return True
    except Exception as e:
        st.error(f"Error updating cashflow entry: {e}")
        return False

def delete_cashflow_db(cf_id):
    try:
        supabase.table('cashflow').delete().eq('id', int(cf_id)).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting cashflow entry: {e}")
        return False

# -------------------------
# Allocation Targets
# -------------------------
# -------------------------
# Planning Settings
# -------------------------
def load_planning_settings():
    default = {'hourly_rate': 0.0, 'goal_amount': 100000.0, 'target_date': '2030-01-01', 'expected_return': 7.0}
    try:
        res = supabase.table('planning_settings').select('*').eq('id', 1).execute()
        if res.data:
            row = res.data[0]
            return {
                'hourly_rate':     float(row.get('hourly_rate', 0.0)),
                'goal_amount':     float(row.get('goal_amount', 100000.0)),
                'target_date':     str(row.get('target_date', '2030-01-01')),
                'expected_return': float(row.get('expected_return', 7.0)),
            }
        supabase.table('planning_settings').insert({'id': 1, **default}).execute()
        return default
    except Exception:
        return default

def save_planning_settings(hourly_rate, goal_amount, target_date, expected_return):
    _td = target_date.isoformat() if hasattr(target_date, 'isoformat') else str(target_date)
    full_data = {
        'id': 1,
        'hourly_rate':     float(hourly_rate),
        'goal_amount':     float(goal_amount),
        'target_date':     _td,
        'expected_return': float(expected_return),
    }
    try:
        supabase.table('planning_settings').upsert(full_data).execute()
        return True
    except Exception:
        # Fallback: expected_return column may not exist yet — save without it
        try:
            supabase.table('planning_settings').upsert({
                k: v for k, v in full_data.items() if k != 'expected_return'
            }).execute()
            return True
        except Exception as e:
            st.error(f"Error saving planning settings: {e}")
            return False

def load_allocation_targets():
    default = {'etf_pct': 50.0, 'max_single_pct': 5.0}
    try:
        res = supabase.table('allocation_targets').select('*').eq('id', 1).execute()
        if res.data:
            row = res.data[0]
            return {
                'etf_pct':        float(row.get('etf_pct', 50.0)),
                'max_single_pct': float(row.get('max_single_pct', 5.0)),
            }
        supabase.table('allocation_targets').insert({'id': 1, **default}).execute()
        return default
    except Exception:
        return default

def save_allocation_targets(etf_pct, max_single_pct):
    try:
        supabase.table('allocation_targets').upsert({
            'id': 1,
            'etf_pct':        float(etf_pct),
            'max_single_pct': float(max_single_pct),
        }).execute()
        return True
    except Exception as e:
        st.error(f"Error saving allocation targets: {e}")
        return False

# -------------------------
# Asset Category Overrides
# -------------------------
def load_asset_categories() -> dict:
    try:
        res = supabase.table('asset_categories').select('*').execute()
        return {r['ticker']: r['category'] for r in (res.data or [])}
    except Exception:
        return {}

def save_asset_category(ticker: str, category: str) -> bool:
    try:
        supabase.table('asset_categories').upsert(
            {'ticker': ticker, 'category': category}
        ).execute()
        return True
    except Exception as e:
        st.error(f"Error saving category: {e}")
        return False

def get_category(ticker: str) -> str:
    overrides = st.session_state.get('asset_categories', {})
    return overrides.get(ticker, auto_detect_category(ticker))

# -------------------------
# Loans (Liabilities)
# -------------------------
def load_loans() -> pd.DataFrame:
    try:
        res = supabase.table('loans').select('*').order('id').execute()
        if res.data:
            df = pd.DataFrame(res.data)
            df = df.rename(columns={
                'id': 'id', 'name': 'Name', 'principal': 'Principal',
                'annual_rate': 'Annual Rate', 'monthly_payment': 'Monthly Payment',
                'start_date': 'Start Date', 'notes': 'Notes',
                'loan_type': 'Loan Type', 'monthly_borrow': 'Monthly Borrow',
                'study_end_date': 'Study End Date', 'repayment_years': 'Repayment Years',
            })
            for col in ['Principal', 'Annual Rate', 'Monthly Payment', 'Monthly Borrow', 'Repayment Years']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
            if 'Loan Type' not in df.columns:
                df['Loan Type'] = 'standard'
            else:
                df['Loan Type'] = df['Loan Type'].fillna('standard')
            if 'Monthly Borrow' not in df.columns:
                df['Monthly Borrow'] = 0.0
            if 'Study End Date' not in df.columns:
                df['Study End Date'] = None
            if 'Repayment Years' not in df.columns:
                df['Repayment Years'] = 10.0
            return df
    except Exception:
        pass
    return pd.DataFrame(columns=[
        'id', 'Name', 'Principal', 'Annual Rate', 'Monthly Payment',
        'Start Date', 'Notes', 'Loan Type', 'Monthly Borrow',
        'Study End Date', 'Repayment Years',
    ])

def add_loan_db(name, principal, annual_rate, monthly_payment, start_date, notes='',
                loan_type='standard', monthly_borrow=0.0, study_end_date=None,
                repayment_years=10.0) -> bool:
    row = {
        'name': str(name),
        'principal': float(principal),
        'annual_rate': float(annual_rate),
        'monthly_payment': float(monthly_payment),
        'start_date': str(start_date),
        'notes': str(notes),
        'loan_type': str(loan_type),
        'monthly_borrow': float(monthly_borrow),
        'repayment_years': float(repayment_years),
    }
    if study_end_date is not None:
        row['study_end_date'] = str(study_end_date)
    try:
        supabase.table('loans').insert(row).execute()
        return True
    except Exception as e:
        st.error(f"Error adding loan: {e}")
        return False

def delete_loan_db(loan_id: int) -> bool:
    try:
        supabase.table('loans').delete().eq('id', int(loan_id)).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting loan: {e}")
        return False

def _student_balance_at(monthly_borrow: float, r_monthly: float,
                         start_date, cutoff_date) -> float:
    """Accumulated student loan balance at cutoff_date (FV of annuity)."""
    _start   = pd.to_datetime(str(start_date)).date()
    _cutoff  = pd.to_datetime(str(cutoff_date)).date()
    months   = max((_cutoff.year - _start.year) * 12 + (_cutoff.month - _start.month), 0)
    if r_monthly == 0:
        return float(monthly_borrow) * months
    return float(monthly_borrow) * ((1 + r_monthly) ** months - 1) / r_monthly

def calc_student_monthly_payment(monthly_borrow: float, annual_rate: float,
                                  start_date, study_end_date, repayment_years: float) -> float:
    """Monthly repayment after study based on balance accumulated at study end."""
    r = annual_rate / 100 / 12
    balance_at_end = _student_balance_at(monthly_borrow, r, start_date, study_end_date)
    n = max(int(repayment_years * 12), 1)
    if balance_at_end == 0:
        return 0.0
    if r == 0:
        return balance_at_end / n
    return balance_at_end * r * (1 + r) ** n / ((1 + r) ** n - 1)

def calc_loan_balance(principal: float, annual_rate: float, monthly_payment: float,
                      start_date, loan_type: str = 'standard',
                      monthly_borrow: float = 0.0, study_end_date=None,
                      repayment_years: float = 10.0) -> float:
    """Remaining loan balance today — handles both standard and student loans."""
    _today = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
    r      = annual_rate / 100 / 12

    if loan_type == 'student' and study_end_date is not None:
        _study_end = pd.to_datetime(str(study_end_date)).date()

        if _today <= _study_end:
            # Still in study: balance = FV of monthly borrows so far
            return _student_balance_at(monthly_borrow, r, start_date, _today)
        else:
            # Study done: amortise from balance-at-study-end
            balance_at_end = _student_balance_at(monthly_borrow, r, start_date, _study_end)
            n_repay = max(int(repayment_years * 12), 1)
            pmt = (balance_at_end * r * (1 + r) ** n_repay / ((1 + r) ** n_repay - 1)
                   if r > 0 else balance_at_end / n_repay)
            n_paid = max((_today.year - _study_end.year) * 12
                         + (_today.month - _study_end.month), 0)
            if r == 0:
                return max(balance_at_end - pmt * n_paid, 0.0)
            factor = (1 + r) ** n_paid
            return max(balance_at_end * factor - pmt * (factor - 1) / r, 0.0)

    # Standard loan
    _start  = pd.to_datetime(str(start_date)).date()
    months  = max((_today.year - _start.year) * 12 + (_today.month - _start.month), 0)
    if r == 0:
        return max(float(principal) - float(monthly_payment) * months, 0.0)
    factor  = (1 + r) ** months
    balance = float(principal) * factor - float(monthly_payment) * (factor - 1) / r
    return max(balance, 0.0)

def _loan_current_monthly_payment(row) -> float:
    """The actual monthly cash outflow for this loan today."""
    _today = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
    if row.get('Loan Type') == 'student':
        _sed = row.get('Study End Date')
        if _sed is None or _sed == 'None' or pd.isnull(_sed):
            return 0.0   # still in study, no payments
        _study_end = pd.to_datetime(str(_sed)).date()
        if _today <= _study_end:
            return 0.0   # still in study
        # After study: computed payment
        return calc_student_monthly_payment(
            row.get('Monthly Borrow', 0.0), row.get('Annual Rate', 0.0),
            row.get('Start Date'), _sed, row.get('Repayment Years', 10.0)
        )
    return float(row.get('Monthly Payment', 0.0))

def get_loans_summary() -> dict:
    """Total remaining debt and current total monthly repayments."""
    loans = st.session_state.get('loans', pd.DataFrame())
    if loans.empty:
        return {'total_debt': 0.0, 'monthly_repayments': 0.0}
    total_debt = sum(
        calc_loan_balance(
            row.get('Principal', 0.0), row.get('Annual Rate', 0.0),
            row.get('Monthly Payment', 0.0), row.get('Start Date'),
            loan_type=str(row.get('Loan Type', 'standard')),
            monthly_borrow=float(row.get('Monthly Borrow', 0.0)),
            study_end_date=row.get('Study End Date'),
            repayment_years=float(row.get('Repayment Years', 10.0)),
        )
        for _, row in loans.iterrows()
    )
    monthly = sum(_loan_current_monthly_payment(row) for _, row in loans.iterrows())
    return {'total_debt': total_debt, 'monthly_repayments': monthly}

def calc_annualized_return(total_profit_pct: float, transactions_df: pd.DataFrame) -> float:
    """Convert total P&L % to an annualised % based on the age of the portfolio."""
    if transactions_df.empty or total_profit_pct == 0:
        return 0.0
    try:
        _today = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
        _first = pd.to_datetime(transactions_df['Date'], errors='coerce').min().date()
        years  = max((_today - _first).days / 365.25, 1 / 12)  # minimum 1 month
        r_total  = total_profit_pct / 100
        r_annual = (1 + r_total) ** (1 / years) - 1
        return r_annual * 100
    except Exception:
        return total_profit_pct  # fallback: use as-is

# -------------------------
# Login
# -------------------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 1.1, 1])
    with col2:
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        st.markdown("""
        <div style='text-align:center; margin-bottom:2.5rem;'>
            <div style='font-family:"Ropa Sans",sans-serif; font-size:2rem; letter-spacing:0.12em; color:#f0ece0; font-weight:400;'>PORTFOLIO</div>
            <div style='width:40px; height:2px; background:#c9a84c; margin:0.5rem auto 0;'></div>
            <div style='font-family:"Inter",sans-serif; font-size:0.65rem; letter-spacing:0.22em; color:#5c5a54; text-transform:uppercase; margin-top:0.6rem;'>Wealth Dashboard</div>
        </div>
        """, unsafe_allow_html=True)
        password = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
        if st.button("Sign In", use_container_width=True):
            if password == st.secrets["auth"]["password"]:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Invalid password")
    st.stop()

# -------------------------
# App title
# -------------------------

# -------------------------
# Session State
# -------------------------
if 'balances' not in st.session_state:
    st.session_state.balances = load_balances()
    st.session_state.balances_saved = False

if 'balances_history' not in st.session_state:
    st.session_state.balances_history = load_balances_history()

if "transactions" not in st.session_state:
    st.session_state.transactions = load_transactions()

if "cashflow" not in st.session_state:
    st.session_state.cashflow = load_cashflow()

if "allocation_targets" not in st.session_state:
    st.session_state.allocation_targets = load_allocation_targets()

if "asset_categories" not in st.session_state:
    st.session_state.asset_categories = load_asset_categories()

if "planning_settings" not in st.session_state:
    st.session_state.planning_settings = load_planning_settings()

if "loans" not in st.session_state:
    st.session_state.loans = load_loans()

# -------------------------
# Sidebar - Balances
# -------------------------
st.sidebar.markdown("""
<div style='padding:1.25rem 0 1rem 0;'>
    <div style='font-family:"Ropa Sans",sans-serif; font-size:1.1rem; letter-spacing:0.1em; color:#f0ece0;'>PORTFOLIO</div>
    <div style='width:32px; height:2px; background:#c9a84c; margin-top:0.35rem; margin-bottom:0.4rem;'></div>
    <div style='font-family:"Inter",sans-serif; font-size:0.6rem; letter-spacing:0.18em; color:#5c5a54; text-transform:uppercase;'>Wealth Dashboard</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar.expander("Balances", expanded=False):
    st.header("Broker Cash Balance")
    cash_balance_input = st.number_input(
        "Cash Balance (EUR)",
        value=st.session_state.balances.get('cash_balance', 0.0),
        step=0.01,
        format="%.2f",
        key="balance_cash_input"
    )
    st.caption("Enter your EUR cash balance from DEGIRO ('Account Overview') or Kraken ('Balances'). Can be negative (e.g., margin in DEGIRO).")

    st.header("Bank Balances")
    credit_mutuel_balance_input = st.number_input(
        "Credit Mutuel Balance (EUR)",
        value=st.session_state.balances.get('credit_mutuel_balance', 0.0),
        step=0.01,
        format="%.2f",
        key="balance_credit_input"
    )
    cic_balance_input = st.number_input(
        "CIC Balance (EUR)",
        value=st.session_state.balances.get('cic_balance', 0.0),
        step=0.01,
        format="%.2f",
        key="balance_cic_input"
    )
    st.caption("Enter your EUR balances for each bank account. Total bank balance is added to the total portfolio value for overall net worth.")

balances_changed = False
if (
    st.session_state.balances.get('cash_balance', 0.0) != cash_balance_input or
    st.session_state.balances.get('credit_mutuel_balance', 0.0) != credit_mutuel_balance_input or
    st.session_state.balances.get('cic_balance', 0.0) != cic_balance_input
):
    st.session_state.balances['cash_balance'] = cash_balance_input
    st.session_state.balances['credit_mutuel_balance'] = credit_mutuel_balance_input
    st.session_state.balances['cic_balance'] = cic_balance_input
    save_balances(cash_balance_input, credit_mutuel_balance_input, cic_balance_input)
    today = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
    save_balance_history_entry(today, cash_balance_input, credit_mutuel_balance_input, cic_balance_input)
    st.session_state.balances_history = load_balances_history()
    balances_changed = True

# -------------------------
# Sidebar - Add Transaction
# -------------------------
with st.sidebar.expander("Add Transaction", expanded=False):
    trans_type = st.selectbox("Transaction Type", ['Buy', 'Sell', 'Dividend', 'Staking', 'Staking Reward', 'Transfer'], key="add_trans_type")
    transaction_date = st.date_input("Transaction Date", value=datetime.today(), key="add_date")

    if trans_type != 'Dividend':
        transaction_time_str = st.text_input("Transaction Time (HH:MM, 24-hour format)", value="12:00", placeholder="e.g., 09:30", key="add_time")
        try:
            transaction_time = datetime.strptime(transaction_time_str, "%H:%M").time()
        except ValueError:
            st.error("Please enter time in HH:MM format (e.g., 09:30).")
            transaction_time = time(12, 0)
    else:
        transaction_time = time(12, 0)

    ticker = st.text_input("Ticker Symbol (e.g., VWRL.AS, BTC-EUR)", key="add_ticker_input") if trans_type != '' else ''

    if trans_type in ['Buy', 'Sell', 'Staking']:
        _price_label = "Sell Price per Unit (EUR)" if trans_type == 'Sell' else "Price per Unit (EUR)"
        quantity = st.number_input("Quantity", min_value=0.0, value=0.0, step=1e-12, format="%.12f", key="add_quantity_input")
        purchase_price = st.number_input(_price_label, min_value=0.0, value=0.0, step=0.01, format="%.2f", key="add_price_input")
        if trans_type in ['Buy', 'Sell']:
            fee_unit = st.selectbox("Fee Unit", options=['None', 'EUR'], key="add_fee_unit_select")
            fee_amount = st.number_input("Transaction Fee (EUR)", min_value=0.0, value=0.0, step=1e-12, format="%.12f", key="add_fee_amount_input") if fee_unit != 'None' else 0.0
        else:
            fee_unit = 'None'
            fee_amount = 0.0
    elif trans_type == 'Staking Reward':
        quantity = st.number_input("Quantity received", min_value=0.0, value=0.0, step=1e-12, format="%.12f", key="add_quantity_input")
        purchase_price = 0.0
        fee_unit = 'None'
        fee_amount = 0.0
        st.caption("Free tokens earned from staking (e.g. TAO from Bittensor subnets). Cost basis is zero — full current value shows as gain.")
    elif trans_type == 'Dividend':
        income = st.number_input("Dividend Income (EUR)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="add_income_input")
        quantity = 0.0
        purchase_price = 0.0
        fee_unit = 'None'
        fee_amount = 0.0
    elif trans_type == 'Transfer':
        fee_unit = st.selectbox("Fee Unit", options=['EUR', 'Asset'], key="add_fee_unit_transfer")
        fee_amount = st.number_input("Transaction Fee Amount", min_value=0.0, value=0.0, step=1e-12, format="%.12f", key="add_fee_amount_transfer")
        quantity = 0.0
        purchase_price = 0.0

    add_button = st.button("Add Transaction", key="add_transaction_button")

# -------------------------
# Sidebar - Edit/Delete Transaction
# -------------------------
with st.sidebar.expander("Edit / Delete Transaction", expanded=False):
    if not st.session_state.get('transactions', pd.DataFrame()).empty:
        trans_index = st.selectbox(
            "Select Transaction to Edit/Delete",
            options=range(len(st.session_state.transactions)),
            format_func=lambda i: f"{st.session_state.transactions.iloc[i]['Date']} {st.session_state.transactions.iloc[i]['Type']} {st.session_state.transactions.iloc[i]['Ticker']}",
            key="edit_index_select"
        )
        if trans_index is not None:
            trans = st.session_state.transactions.iloc[trans_index]
            _type_options = ['Buy', 'Sell', 'Dividend', 'Staking', 'Staking Reward', 'Transfer']
            edit_trans_type = st.selectbox("Transaction Type", _type_options, index=_type_options.index(trans['Type']) if trans['Type'] in _type_options else 0, key="edit_trans_type_select")
            edit_date = st.date_input("Transaction Date", value=pd.to_datetime(trans['Date']).date(), key="edit_date_input")

            if edit_trans_type != 'Dividend':
                edit_time_str = st.text_input("Transaction Time (HH:MM, 24-hour format)", value=str(trans['Time']), placeholder="e.g., 09:30", key="edit_time_input")
                try:
                    edit_time = datetime.strptime(edit_time_str, "%H:%M").time()
                except ValueError:
                    st.error("Please enter time in HH:MM format (e.g., 09:30).")
                    edit_time = time(12, 0)
            else:
                edit_time = time(12, 0)

            edit_ticker = st.text_input("Ticker Symbol", value=trans['Ticker'], key="edit_ticker_input") if edit_trans_type != '' else ''

            if edit_trans_type in ['Buy', 'Sell', 'Staking']:
                _edit_price_label = "Sell Price per Unit (EUR)" if edit_trans_type == 'Sell' else "Price per Unit (EUR)"
                edit_quantity = st.number_input("Quantity", min_value=0.0, value=float(trans['Quantity']), step=1e-12, format="%.12f", key="edit_quantity_input")
                edit_purchase_price = st.number_input(_edit_price_label, min_value=0.0, value=float(trans['Purchase Price']), step=0.01, format="%.2f", key="edit_price_input")
                if edit_trans_type in ['Buy', 'Sell']:
                    edit_fee_unit = st.selectbox("Fee Unit", options=['None', 'EUR'], index=['None', 'EUR'].index(trans['Fee Unit']) if trans['Fee Unit'] in ['None', 'EUR'] else 0, key="edit_fee_unit_select")
                    edit_fee_amount = st.number_input("Transaction Fee (EUR)", min_value=0.0, value=float(trans['Fee Amount']), step=1e-12, format="%.12f", key="edit_fee_amount_input") if edit_fee_unit != 'None' else 0.0
                else:
                    edit_fee_unit = 'None'
                    edit_fee_amount = 0.0
            elif edit_trans_type == 'Staking Reward':
                edit_quantity = st.number_input("Quantity received", min_value=0.0, value=float(trans['Quantity']), step=1e-12, format="%.12f", key="edit_quantity_input")
                edit_purchase_price = 0.0
                edit_fee_unit = 'None'
                edit_fee_amount = 0.0
                st.caption("Free tokens — cost basis is zero.")
            elif edit_trans_type == 'Dividend':
                edit_income = st.number_input("Dividend Income (EUR)", min_value=0.0, value=float(trans['Income']), step=0.01, format="%.2f", key="edit_income_input")
                edit_quantity = 0.0
                edit_purchase_price = 0.0
                edit_fee_unit = 'None'
                edit_fee_amount = 0.0
            elif edit_trans_type == 'Transfer':
                edit_fee_unit = st.selectbox("Fee Unit", options=['EUR', 'Asset'], index=['EUR', 'Asset'].index(trans['Fee Unit']) if trans['Fee Unit'] in ['EUR', 'Asset'] else 0, key="edit_fee_unit_transfer")
                edit_fee_amount = st.number_input("Transaction Fee Amount", min_value=0.0, value=float(trans['Fee Amount']), step=1e-12, format="%.12f", key="edit_fee_amount_transfer")
                edit_quantity = 0.0
                edit_purchase_price = 0.0

            col1, col2 = st.columns(2)
            with col1:
                edit_button = st.button("Update Transaction", key="edit_transaction_button")
            with col2:
                delete_button = st.button("Delete Transaction", key="delete_transaction_button")
    else:
        st.info("No transactions available yet.")

# -------------------------
# Sidebar - Cashflow
# -------------------------
with st.sidebar.expander("Cashflow Tracker", expanded=False):
    st.subheader("Add Cashflow Entry")
    new_category = st.text_input("Category", key="cashflow_new_category_cf")
    new_type = st.selectbox("Type", ["Income", "Expense"], key="cashflow_new_type_cf")
    new_amount = st.number_input("Amount (EUR)", min_value=0.0, step=0.01, key="cashflow_new_amount_cf")
    new_notes = st.text_input("Notes", key="cashflow_new_notes_cf")

    if st.button("Add Cashflow Entry", key="cashflow_add_button_cf"):
        if new_category and new_amount > 0:
            cf_amount = new_amount if new_type == "Income" else -new_amount
            if add_cashflow_db(new_category, new_type, cf_amount, new_notes):
                st.session_state.cashflow = load_cashflow()
                st.success(f"Added new {new_type.lower()} entry for {new_category}.")
                st.rerun()
        else:
            st.warning("Please provide a category and a positive amount.")

    st.markdown("---")

    st.subheader("Edit / Delete Entries")
    if not st.session_state.cashflow.empty:
        cf_index = st.selectbox(
            "Select Entry",
            options=range(len(st.session_state.cashflow)),
            format_func=lambda i: f"{st.session_state.cashflow.iloc[i]['Category']} | {st.session_state.cashflow.iloc[i]['Amount']}€",
            key="cashflow_select_entry_cf"
        )

        cf_selected = st.session_state.cashflow.iloc[cf_index]

        edit_cat = st.text_input("Category", value=cf_selected["Category"], key="cashflow_edit_category_cf")
        edit_type = st.selectbox("Type", ["Income", "Expense"], index=0 if cf_selected["Amount"] > 0 else 1, key="cashflow_edit_type_cf")
        edit_amount = st.number_input("Amount (EUR)", value=abs(float(cf_selected["Amount"])), step=0.01, key="cashflow_edit_amount_cf")
        edit_notes = st.text_input("Notes", value=str(cf_selected.get("Notes", "") or ""), key="cashflow_edit_notes_cf")

        colA, colB = st.columns(2)
        with colA:
            update_cf = st.button("Update Cashflow", key="cashflow_update_button_cf")
        with colB:
            delete_cf = st.button("Delete Cashflow", key="cashflow_delete_button_cf")

        if update_cf:
            cf_id = st.session_state.cashflow.iloc[cf_index]['id']
            cf_amount = edit_amount if edit_type == "Income" else -edit_amount
            if update_cashflow_db(cf_id, edit_cat, edit_type, cf_amount, edit_notes):
                st.session_state.cashflow = load_cashflow()
                st.success("Entry updated.")
                st.rerun()

        if delete_cf:
            cf_id = st.session_state.cashflow.iloc[cf_index]['id']
            if delete_cashflow_db(cf_id):
                st.session_state.cashflow = load_cashflow()
                st.success("Entry deleted.")
                st.rerun()
    else:
        st.info("No entries yet. Add one above.")

# ─── Loans sidebar ───
with st.sidebar.expander("Loans / Debt", expanded=False):
    st.subheader("Add a Loan")
    loan_type_sel = st.selectbox(
        "Type lening", ["Studentenlening (maandelijks)", "Standaard lening"],
        key="loan_type_sel"
    )
    _is_student = loan_type_sel.startswith("Student")

    loan_name  = st.text_input("Naam", placeholder="DUO Lening 2025", key="loan_name_in")
    loan_rate  = st.number_input("Jaarlijkse rente (%)", min_value=0.0, max_value=30.0,
                                  step=0.01, format="%.2f", key="loan_rate_in")
    loan_start = st.date_input("Startdatum", value=datetime.now(ZoneInfo("Europe/Amsterdam")).date(),
                                key="loan_start_in")

    if _is_student:
        loan_monthly_borrow  = st.number_input("Maandelijks leenbedrag (€)", min_value=0.0,
                                                step=50.0, format="%.2f", key="loan_mb_in")
        loan_study_end       = st.date_input("Einde studie (start terugbetaling)",
                                              value=date(2028, 7, 1), key="loan_send_in")
        loan_repay_years     = st.number_input("Terugbetalingsperiode (jaren)", min_value=1.0,
                                                max_value=40.0, value=15.0, step=1.0,
                                                format="%.0f", key="loan_ry_in")
        loan_principal = 0.0
        loan_payment   = 0.0
    else:
        loan_principal = st.number_input("Totaal geleend bedrag (€)", min_value=0.0,
                                          step=100.0, format="%.2f", key="loan_principal_in")
        loan_payment   = st.number_input("Maandelijkse aflossing (€)", min_value=0.0,
                                          step=10.0, format="%.2f", key="loan_payment_in")
        loan_monthly_borrow = 0.0
        loan_study_end      = None
        loan_repay_years    = 10.0

    loan_notes = st.text_input("Notities (optioneel)", key="loan_notes_in")

    if st.button("Lening toevoegen", key="loan_add_btn"):
        _ok = False
        if _is_student:
            _ok = bool(loan_name and loan_monthly_borrow > 0)
        else:
            _ok = bool(loan_name and loan_principal > 0 and loan_payment > 0)

        if _ok:
            _ltype = 'student' if _is_student else 'standard'
            if add_loan_db(loan_name, loan_principal, loan_rate, loan_payment, loan_start,
                           loan_notes, loan_type=_ltype,
                           monthly_borrow=loan_monthly_borrow,
                           study_end_date=loan_study_end,
                           repayment_years=loan_repay_years):
                st.session_state.loans = load_loans()
                st.success(f"Lening '{loan_name}' toegevoegd.")
                st.rerun()
        else:
            st.warning("Vul naam en bedrag(en) in.")

    if not st.session_state.loans.empty:
        st.markdown("---")
        st.subheader("Actieve leningen")
        for _, loan_row in st.session_state.loans.iterrows():
            remaining = calc_loan_balance(
                loan_row.get('Principal', 0.0), loan_row.get('Annual Rate', 0.0),
                loan_row.get('Monthly Payment', 0.0), loan_row.get('Start Date'),
                loan_type=str(loan_row.get('Loan Type', 'standard')),
                monthly_borrow=float(loan_row.get('Monthly Borrow', 0.0)),
                study_end_date=loan_row.get('Study End Date'),
                repayment_years=float(loan_row.get('Repayment Years', 10.0)),
            )
            _pmt  = _loan_current_monthly_payment(loan_row)
            _lbl  = "opgebouwd" if str(loan_row.get('Loan Type')) == 'student' else "resterend"
            _mb   = float(loan_row.get('Monthly Borrow', 0.0))
            _borrow_tag = f"€{_mb:,.0f}/mo lening" if str(loan_row.get('Loan Type')) == 'student' else ""
            _repay_tag  = f"€{_pmt:,.0f}/mo aflossing" if _pmt > 0 else "geen aflossing nu"
            _detail = " · ".join(x for x in [_borrow_tag, _repay_tag] if x)
            st.markdown(
                f"**{loan_row['Name']}** — €{remaining:,.0f} {_lbl}  \n"
                f"<span style='font-size:0.78rem; color:#5c5a54;'>"
                f"{_detail} · {loan_row['Annual Rate']:.2f}% rente</span>",
                unsafe_allow_html=True
            )
            if st.button("Verwijderen", key=f"loan_del_{loan_row['id']}"):
                if delete_loan_db(int(loan_row['id'])):
                    st.session_state.loans = load_loans()
                    st.rerun()

# -------------------------
# CoinGecko helpers (for tokens not on Yahoo Finance)
# -------------------------
COINGECKO_IDS = {
    'TAO-EUR': 'bittensor',
    'TAO':     'bittensor',
}

@st.cache_data(ttl=300)
def _coingecko_price(coin_id: str, vs_currency: str = 'eur') -> float:
    try:
        import requests
        url = (f"https://api.coingecko.com/api/v3/simple/price"
               f"?ids={coin_id}&vs_currencies={vs_currency}")
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return float(r.json().get(coin_id, {}).get(vs_currency, 0.0))
    except Exception:
        pass
    return 0.0

@st.cache_data(ttl=3600)
def _coingecko_history(coin_id: str, vs_currency: str = 'eur', period: str = '1y') -> pd.DataFrame:
    _days = {'6mo': 180, '1y': 365, '2y': 730, '5y': 1825, 'max': 'max'}
    days = _days.get(period, 365)
    try:
        import requests
        url = (f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
               f"?vs_currency={vs_currency}&days={days}&interval=daily")
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            prices = r.json().get('prices', [])
            if prices:
                df = pd.DataFrame(prices, columns=['ts', 'Close'])
                df['Date'] = pd.to_datetime(df['ts'], unit='ms').dt.date
                df = df.groupby('Date')['Close'].last().reset_index()
                return df
    except Exception:
        pass
    return pd.DataFrame()

# -------------------------
# Price fetching functions
# -------------------------
@st.cache_data(ttl=300)
def get_price(ticker):
    # Use CoinGecko for known tokens not reliably on Yahoo Finance
    if ticker in COINGECKO_IDS:
        price = _coingecko_price(COINGECKO_IDS[ticker])
        if price > 0:
            return price

    tickers_to_try = [ticker]
    if ticker in ['VUSA', 'VUSA.AS']:
        tickers_to_try.extend(['VUSA.AS', 'VOO'])
    elif ticker in ['VWRL', 'VWRL.AS']:
        tickers_to_try.extend(['VWRL.AS'])
    elif ticker in ['QDVE', 'QDVE.DE']:
        tickers_to_try.extend(['QDVE.DE'])
    elif ticker == 'SLMC.DE':
        tickers_to_try.extend(['SLMC.DE'])
    elif ticker in ['BTC', 'ETH', 'SOL', 'TAO']:
        tickers_to_try.extend([f"{ticker}-EUR", f"{ticker}-USD"])
    elif '-EUR' in ticker:
        tickers_to_try.append(ticker.replace('-EUR', '-USD'))

    for t in tickers_to_try:
        try:
            data = yf.Ticker(t).history(period='1d', interval='1d')['Close']
            if not data.empty:
                return _price_to_eur(float(data.iloc[-1]), t)
        except Exception:
            continue
    return 0.0

@st.cache_data(ttl=3600)
def get_historical_data(ticker, period='1y'):
    # Use CoinGecko for known tokens not reliably on Yahoo Finance
    if ticker in COINGECKO_IDS:
        df = _coingecko_history(COINGECKO_IDS[ticker], period=period)
        if not df.empty:
            return df

    tickers_to_try = [ticker]
    if ticker in ['BTC', 'ETH', 'SOL', 'TAO']:
        tickers_to_try.extend([f"{ticker}-EUR", f"{ticker}-USD"])
    elif '-EUR' in ticker:
        tickers_to_try.append(ticker.replace('-EUR', '-USD'))

    for t in tickers_to_try:
        try:
            raw = yf.download(t, period=period, progress=False)
            if raw.empty:
                continue
            data = raw['Close'].reset_index()
            data.columns = ['Date', 'Close']
            ccy = _ticker_currency(t)
            if ccy == 'EUR':
                pass  # already EUR
            elif ccy == 'GBP':
                # pence → GBP → EUR (use scalar rate, good enough for charts)
                rate = _fx_to_eur('GBP')
                data['Close'] = data['Close'] / 100 * rate
            else:  # USD or CHF etc.
                # Download the FX series for proper daily conversion
                fx_pair = f"{ccy}EUR=X"
                fx_raw = yf.download(fx_pair, period=period, progress=False)
                if not fx_raw.empty:
                    fx = fx_raw['Close'].reindex(raw.index, method='ffill')
                    data['Close'] = data['Close'].values * fx.values
                else:
                    rate = _fx_to_eur(ccy)
                    data['Close'] = data['Close'] * rate
            return data
        except Exception:
            continue

    return pd.DataFrame()

# -------------------------
# Add / Edit / Delete transactions
# -------------------------
if add_button and ticker:
    if trans_type in ['Buy', 'Sell', 'Staking', 'Staking Reward'] and quantity <= 0:
        st.sidebar.error("Quantity must be positive.")
    elif trans_type in ['Buy', 'Sell', 'Staking'] and purchase_price <= 0:
        st.sidebar.error("Price per unit must be positive.")
    elif trans_type == 'Dividend' and income <= 0:
        st.sidebar.error("Income must be positive for Dividend.")
    elif trans_type == 'Transfer' and fee_amount <= 0:
        st.sidebar.error("Fee amount must be positive for Transfer.")
    else:
        income_value = income if trans_type == 'Dividend' else 0.0
        if add_transaction_db(transaction_date, transaction_time, trans_type, ticker, quantity, purchase_price, fee_amount, fee_unit, income_value):
            st.session_state.transactions = load_transactions()
            st.sidebar.success(f"Added {trans_type} for {ticker}.")
            st.rerun()

if 'edit_button' in locals() and edit_button and trans_index is not None:
    if edit_trans_type in ['Buy', 'Sell', 'Staking', 'Staking Reward'] and edit_quantity <= 0:
        st.sidebar.error("Quantity must be positive.")
    elif edit_trans_type in ['Buy', 'Sell', 'Staking'] and edit_purchase_price <= 0:
        st.sidebar.error("Price per unit must be positive.")
    elif edit_trans_type == 'Dividend' and edit_income <= 0:
        st.sidebar.error("Income must be positive for Dividend.")
    elif edit_trans_type == 'Transfer' and edit_fee_amount <= 0:
        st.sidebar.error("Fee amount must be positive for Transfer.")
    else:
        trans_id = st.session_state.transactions.iloc[trans_index]['id']
        edit_income_value = edit_income if edit_trans_type == 'Dividend' else 0.0
        if update_transaction_db(trans_id, edit_date, edit_time, edit_trans_type, edit_ticker, edit_quantity, edit_purchase_price, edit_fee_amount, edit_fee_unit, edit_income_value):
            st.session_state.transactions = load_transactions()
            st.sidebar.success("Updated transaction.")
            st.rerun()

if 'delete_button' in locals() and delete_button and trans_index is not None:
    trans_id = st.session_state.transactions.iloc[trans_index]['id']
    if delete_transaction_db(trans_id):
        st.session_state.transactions = load_transactions()
        st.sidebar.success("Deleted transaction.")
        st.rerun()

# -------------------------
# Compute portfolio
# -------------------------
def compute_portfolio(transactions_df=None, cash_balance_local=None):
    if transactions_df is None:
        trans = st.session_state.transactions.copy()
    else:
        trans = transactions_df.copy()

    if cash_balance_local is None:
        cash_balance_local = st.session_state.balances.get('cash_balance', 0.0)

    if trans.empty:
        return pd.DataFrame(), 0.0, 0.0, 0.0, 0.0

    if pd.api.types.is_categorical_dtype(trans.get('Date', pd.Series())):
        trans['Date'] = trans['Date'].astype(str)
    if pd.api.types.is_categorical_dtype(trans.get('Time', pd.Series())):
        trans['Time'] = trans['Time'].astype(str)

    trans['Date'] = pd.to_datetime(trans['Date'], errors='coerce', format='mixed').dt.date
    trans['Time'] = pd.to_datetime(trans['Time'], errors='coerce').dt.time
    trans = trans.sort_values(['Date', 'Time'])

    aggregated = {}
    realized = 0.0
    tao_present = 'TAO-EUR' in trans['Ticker'].values if 'Ticker' in trans.columns else False
    for idx, row in trans.iterrows():
        ticker = row['Ticker']
        ticker = 'VUSA.AS' if ticker == 'VUSA' else 'VWRL.AS' if ticker == 'VWRL' else ticker
        if ticker not in aggregated:
            aggregated[ticker] = {'Quantity': 0.0, 'Cost Basis': 0.0, 'Total Share Cost': 0.0}
        q = aggregated[ticker]['Quantity']
        c = aggregated[ticker]['Cost Basis']
        s = aggregated[ticker]['Total Share Cost']
        trans_type = row['Type']
        try:
            quantity = float(row['Quantity'])
            purchase_price = float(row['Purchase Price'])
            fee_amount = float(row['Fee Amount'])
            income = float(row['Income'])
        except (ValueError, TypeError):
            continue
        fee_unit = row['Fee Unit'] if pd.notnull(row.get('Fee Unit', 'None')) else 'None'

        if trans_type == 'Buy':
            fee_eur = fee_amount if fee_unit == 'EUR' else 0.0
            c += quantity * purchase_price + fee_eur
            s += quantity * purchase_price
            q += quantity
            if fee_unit == 'EUR':
                realized -= fee_amount
        elif trans_type == 'Sell':
            fee_eur = fee_amount if fee_unit == 'EUR' else 0.0
            if q > 0:
                avg_cost_per_unit  = c / q
                avg_share_per_unit = s / q
                proceeds           = quantity * purchase_price - fee_eur
                cost_of_sold       = quantity * avg_cost_per_unit
                realized          += proceeds - cost_of_sold
                c = max(c - quantity * avg_cost_per_unit,  0.0)
                s = max(s - quantity * avg_share_per_unit, 0.0)
            q = max(q - quantity, 0.0)
        elif trans_type == 'Dividend':
            realized += income
        elif trans_type == 'Staking':
            c += quantity * purchase_price
            s += quantity * purchase_price
            q += quantity
        elif trans_type == 'Staking Reward':
            # Free tokens earned from staking — zero cost basis
            # Full current value shows as unrealized gain
            q += quantity
        elif trans_type == 'Transfer':
            if fee_unit == 'EUR':
                realized -= fee_amount
                c -= fee_amount
            elif fee_unit == 'Asset':
                current_price = get_price(ticker)
                if current_price == 0.0:
                    current_price = s / q if q > 0 else purchase_price
                fee_eur = fee_amount * current_price
                realized -= fee_eur
                c -= fee_eur
        aggregated[ticker]['Quantity'] = max(q, 0.0)
        aggregated[ticker]['Cost Basis'] = max(c, 0.0)
        aggregated[ticker]['Total Share Cost'] = max(s, 0.0)

    portfolio_list = []
    unrealized_total = 0.0
    total_invested = 0.0
    tao_excluded_reason = None
    for ticker, data in aggregated.items():
        if data['Quantity'] > 0:
            current_price = get_price(ticker)
            value = data['Quantity'] * current_price
            unrealized = value - data['Cost Basis']
            unrealized_total += unrealized
            average_purchase = data['Total Share Cost'] / data['Quantity'] if data['Quantity'] > 0 else 0.0
            total_invested += data['Cost Basis']
            portfolio_list.append({
                'Ticker': ticker,
                'Quantity': data['Quantity'],
                'Average Purchase Price': average_purchase,
                'Cost Basis': data['Cost Basis'],
                'Current Price': current_price,
                'Value': value,
                'Unrealized Profit/Loss': unrealized
            })
            if current_price == 0.0 and ticker == 'TAO-EUR':
                tao_excluded_reason = "Price = 0.0 (Yahoo Finance failed to fetch price)"
        elif ticker == 'TAO-EUR':
            tao_excluded_reason = f"Quantity <= 0 ({data['Quantity']:.12f}) after processing all transactions"
    portfolio_df = pd.DataFrame(portfolio_list)
    total_profit = realized + unrealized_total
    profit_percentage = (total_profit / total_invested * 100) if total_invested > 0 else 0.0
    if tao_present and (portfolio_df.empty or 'TAO-EUR' not in portfolio_df['Ticker'].values):
        st.error(f"TAO-EUR is present in transactions but missing from portfolio. Reason: {tao_excluded_reason or 'Unknown error in processing'}.")
    return portfolio_df, realized, unrealized_total, total_profit, profit_percentage

portfolio_df, realized, unrealized, total_profit, profit_percentage = compute_portfolio()

# ─── Compute header stats ───
_total_assets = portfolio_df["Value"].sum() if not portfolio_df.empty else 0.0
_cash = st.session_state.balances.get("cash_balance", 0.0)
_credit = st.session_state.balances.get("credit_mutuel_balance", 0.0)
_cic = st.session_state.balances.get("cic_balance", 0.0)
_total_value = _total_assets + _cash + _credit + _cic
_loans_summary = get_loans_summary()
_total_debt    = _loans_summary['total_debt']
_net_worth     = _total_value - _total_debt
_profit_color = "#27ae7a" if total_profit >= 0 else "#c94c4c"
_profit_sign  = "+" if total_profit >= 0 else ""
_pct_sign     = "+" if profit_percentage >= 0 else ""
_today_str    = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d %b %Y").upper()

# Use CSS display to show/hide the debt block — avoids injecting HTML into the f-string
_debt_display  = 'block' if _total_debt > 0 else 'none'
_debt_str      = f"-€{_total_debt:,.0f}"   # unicode minus + euro sign, no curly braces

_header_parts = [
    "<div style='background:#0c1120; border-bottom:1px solid #192138; padding:1.4rem 1.5rem 1.2rem; margin:-0 -1.5rem 0; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:1rem;'>",
    "  <div>",
    "    <div style='font-family:\"Ropa Sans\",sans-serif; font-size:1.6rem; letter-spacing:0.08em; color:#f0ece0; line-height:1;'>PORTFOLIO</div>",
    "    <div style='width:36px; height:2px; background:#c9a84c; margin:0.4rem 0 0.3rem;'></div>",
    f"    <div style='font-family:\"Inter\",sans-serif; font-size:0.6rem; letter-spacing:0.2em; color:#5c5a54; text-transform:uppercase;'>{_today_str}</div>",
    "  </div>",
    "  <div style='display:flex; gap:2.5rem; flex-wrap:wrap;'>",
    # Total Assets
    "    <div style='text-align:right;'>",
    "      <div style='font-family:\"Inter\",sans-serif; font-size:0.6rem; letter-spacing:0.14em; color:#5c5a54; text-transform:uppercase; margin-bottom:0.25rem;'>Total Assets</div>",
    f"      <div style='font-family:\"Ropa Sans\",sans-serif; font-size:1.5rem; color:#f0ece0; letter-spacing:0.03em;'>€{_total_value:,.0f}</div>",
    "    </div>",
    # Debt (hidden with CSS when no loans)
    f"    <div style='text-align:right; display:{_debt_display};'>",
    "      <div style='font-family:\"Inter\",sans-serif; font-size:0.6rem; letter-spacing:0.14em; color:#5c5a54; text-transform:uppercase; margin-bottom:0.25rem;'>Debt</div>",
    f"      <div style='font-family:\"Ropa Sans\",sans-serif; font-size:1.5rem; color:#c94c4c; letter-spacing:0.03em;'>{_debt_str}</div>",
    "    </div>",
    # Net Worth
    "    <div style='text-align:right;'>",
    "      <div style='font-family:\"Inter\",sans-serif; font-size:0.6rem; letter-spacing:0.14em; color:#5c5a54; text-transform:uppercase; margin-bottom:0.25rem;'>Net Worth</div>",
    f"      <div style='font-family:\"Ropa Sans\",sans-serif; font-size:1.5rem; color:#f0ece0; letter-spacing:0.03em;'>€{_net_worth:,.0f}</div>",
    "    </div>",
    # Total P&L
    "    <div style='text-align:right;'>",
    "      <div style='font-family:\"Inter\",sans-serif; font-size:0.6rem; letter-spacing:0.14em; color:#5c5a54; text-transform:uppercase; margin-bottom:0.25rem;'>Total P&amp;L</div>",
    f"      <div style='font-family:\"Ropa Sans\",sans-serif; font-size:1.5rem; color:{_profit_color}; letter-spacing:0.03em;'>{_profit_sign}€{total_profit:,.0f}</div>",
    "    </div>",
    # Return
    "    <div style='text-align:right;'>",
    "      <div style='font-family:\"Inter\",sans-serif; font-size:0.6rem; letter-spacing:0.14em; color:#5c5a54; text-transform:uppercase; margin-bottom:0.25rem;'>Return</div>",
    f"      <div style='font-family:\"Ropa Sans\",sans-serif; font-size:1.5rem; color:{_profit_color}; letter-spacing:0.03em;'>{_pct_sign}{profit_percentage:.1f}%</div>",
    "    </div>",
    "  </div>",
    "</div>",
    "<div style='height:3px; background:linear-gradient(90deg,#c9a84c 0%,rgba(201,168,76,0.15) 60%,transparent 100%);'></div>",
]
st.markdown("\n".join(_header_parts), unsafe_allow_html=True)

st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
_rcol1, _rcol2 = st.columns([6, 1])
with _rcol2:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# -------------------------
# Navigation tabs
# -------------------------
tab_overview, tab_history, tab_cashflow, tab_allocation, tab_charts, tab_planning = st.tabs([
    "Overview",
    "History",
    "Cashflow",
    "Allocation",
    "Charts",
    "Planning"
])

# -------------------------
# Tab: Cashflow
# -------------------------
with tab_cashflow:
    st.markdown("<h2><span class='material-symbols-outlined' style='font-size:20px;'>account_balance_wallet</span> Cashflow</h2>", unsafe_allow_html=True)

    if not st.session_state.cashflow.empty:
        income_df = st.session_state.cashflow[st.session_state.cashflow["Amount"] > 0].sort_values(by="Amount", ascending=False)
        expense_df = st.session_state.cashflow[st.session_state.cashflow["Amount"] < 0].sort_values(by="Amount", ascending=True)

        total_income = income_df["Amount"].sum()
        total_expenses = expense_df["Amount"].sum()
        net_cashflow = total_income + total_expenses
        _net_col = "#27ae7a" if net_cashflow >= 0 else "#c94c4c"
        st.markdown(f"""
        <div style='display:flex; gap:1.5rem; flex-wrap:wrap; margin-bottom:1.5rem;'>
            <div style='flex:1; min-width:160px; background:#0c1120; border:1px solid #192138; border-left:3px solid #27ae7a; border-radius:6px; padding:1rem 1.2rem;'>
                <div style='font-family:"Inter",sans-serif; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase; color:#5c5a54; margin-bottom:0.3rem;'>Total Income</div>
                <div style='font-family:"Ropa Sans",sans-serif; font-size:1.4rem; color:#27ae7a; letter-spacing:0.03em;'>€{total_income:,.2f}</div>
            </div>
            <div style='flex:1; min-width:160px; background:#0c1120; border:1px solid #192138; border-left:3px solid #c94c4c; border-radius:6px; padding:1rem 1.2rem;'>
                <div style='font-family:"Inter",sans-serif; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase; color:#5c5a54; margin-bottom:0.3rem;'>Total Expenses</div>
                <div style='font-family:"Ropa Sans",sans-serif; font-size:1.4rem; color:#c94c4c; letter-spacing:0.03em;'>€{abs(total_expenses):,.2f}</div>
            </div>
            <div style='flex:1; min-width:160px; background:#0c1120; border:1px solid #192138; border-left:3px solid #c9a84c; border-radius:6px; padding:1rem 1.2rem;'>
                <div style='font-family:"Inter",sans-serif; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase; color:#5c5a54; margin-bottom:0.3rem;'>Net Monthly</div>
                <div style='font-family:"Ropa Sans",sans-serif; font-size:1.4rem; color:{_net_col}; letter-spacing:0.03em;'>€{net_cashflow:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Income")
            if not income_df.empty:
                st.dataframe(
                    income_df[CF_DISPLAY_COLS]
                    .style.format({"Amount": "€{:.2f}"})
                    .set_properties(**{"text-align": "left"})
                    .set_table_styles(
                        [{"selector": "thead th", "props": [("background-color", "#0c1120"), ("color", "#a8a49a"), ("border-bottom", "1px solid #192138")]}]
                    ),
                    use_container_width=True
                )
            else:
                st.info("No income entries yet.")

        with col2:
            st.markdown("### Expenses")
            if not expense_df.empty:
                expense_display = expense_df[CF_DISPLAY_COLS].copy()
                expense_display["Amount"] = expense_display["Amount"].abs()
                st.dataframe(
                    expense_display
                    .style.format({"Amount": "€{:.2f}"})
                    .set_properties(**{"text-align": "left"})
                    .set_table_styles(
                        [{"selector": "thead th", "props": [("background-color", "#0c1120"), ("color", "#a8a49a"), ("border-bottom", "1px solid #192138")]}]
                    ),
                    use_container_width=True
                )
            else:
                st.info("No expenses yet.")

    else:
        st.info("No cashflow data available yet.")

# -------------------------
# Tab: Historical Portfolio Value
# -------------------------
with tab_history:
    st.markdown(
        "<h2 style='margin-bottom:0.5rem;'>"
        "<span class='material-symbols-outlined' style='font-size:20px;'>trending_up</span> Portfolio History"
        "&nbsp;<span class='material-symbols-outlined' style='font-size:15px; color:#5c5a54; cursor:help; vertical-align:middle;' "
        "title='Logs total portfolio value daily (assets + broker cash + bank balances). Compares to a No Investment baseline — what your wealth would be if you kept everything in cash.'>help</span>"
        "</h2>",
        unsafe_allow_html=True
    )

    portfolio_df_current, _, _, _, _ = compute_portfolio()
    assets_total = portfolio_df_current["Value"].sum() if not portfolio_df_current.empty else 0.0
    cash_now = st.session_state.balances.get("cash_balance", 0.0)
    credit_now = st.session_state.balances.get("credit_mutuel_balance", 0.0)
    cic_now = st.session_state.balances.get("cic_balance", 0.0)
    total_now = assets_total + cash_now + credit_now + cic_now

    total_invested = portfolio_df_current["Cost Basis"].sum() if not portfolio_df_current.empty else 0.0
    bank_total = credit_now + cic_now
    broker_cash = cash_now

    trans_df = st.session_state.get("transactions", pd.DataFrame())
    if not trans_df.empty:
        fees = trans_df.loc[trans_df["Fee Unit"] == "EUR", "Fee Amount"].sum() if "Fee Unit" in trans_df.columns else trans_df["Fee Amount"].sum()
        dividends = trans_df.loc[trans_df["Type"] == "Dividend", "Income"].sum() if "Income" in trans_df.columns else 0.0
    else:
        fees = dividends = 0.0

    no_investment_total = total_invested + bank_total + broker_cash + fees - dividends

    today = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
    save_portfolio_value_entry(today, total_now, no_investment_total)

    pv_hist_df = load_portfolio_value_history()

    if pv_hist_df.empty:
        st.info("No daily history yet. Today's total has been logged; come back tomorrow for another point.")
    else:
        plot_df = pv_hist_df.copy()
        plot_df = plot_df.sort_values("date")
        plot_df = plot_df.rename(columns={
            "date": "Date",
            "total_value": "Total Portfolio Value (€)",
            "no_investment_value": "No Investment (€)"
        })

        _CHART_LAYOUT = dict(
            plot_bgcolor="#080c18",
            paper_bgcolor="#080c18",
            font=dict(family="Inter", color="#5c5a54", size=11),
            xaxis=dict(gridcolor="#192138", linecolor="#192138", tickfont=dict(color="#5c5a54"), zeroline=False),
            yaxis=dict(gridcolor="#192138", linecolor="#192138", tickfont=dict(color="#5c5a54"), zeroline=False),
            margin=dict(l=10, r=10, t=100, b=10),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#0c1120", bordercolor="#192138", font=dict(family="Inter", color="#f0ece0", size=12)),
            legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="left", x=0,
                        font=dict(family="Inter", color="#a8a49a", size=11), bgcolor="rgba(0,0,0,0)", borderwidth=0),
        )

        fig_total = go.Figure()
        fig_total.add_trace(go.Scatter(
            x=plot_df["Date"], y=plot_df["Total Portfolio Value (€)"],
            mode="lines", name="Portfolio Value",
            line=dict(color="#c9a84c", width=2.5),
            hovertemplate="€%{y:,.2f}<extra></extra>"
        ))
        fig_total.add_trace(go.Scatter(
            x=plot_df["Date"], y=plot_df["No Investment (€)"],
            mode="lines", name="No Investment",
            line=dict(color="#a8a49a", width=2, dash="dot"),
            hovertemplate="€%{y:,.2f}<extra></extra>"
        ))
        fig_total.update_layout(
            title=dict(text="Portfolio Value vs. No Investment", font=dict(family="Ropa Sans", color="#f0ece0", size=15), x=0),
            yaxis_title="Value (€)",
            **_CHART_LAYOUT
        )
        st.plotly_chart(fig_total, use_container_width=True)

        latest = plot_df["Total Portfolio Value (€)"].iloc[-1]
        baseline = plot_df["No Investment (€)"].iloc[-1]
        delta_vs_baseline = latest - baseline
        pct_vs_baseline = (delta_vs_baseline / baseline) * 100 if baseline != 0 else 0

        col1, col2 = st.columns(2)
        col1.metric("Current Portfolio Value", f"€{latest:,.2f}")
        col2.metric("No Investment (Cash Equivalent)", f"€{baseline:,.2f}")

        _delta_col = "#27ae7a" if delta_vs_baseline >= 0 else "#c94c4c"
        _delta_sign = "+" if delta_vs_baseline >= 0 else ""
        st.markdown(
            f"<div style='font-family:Inter; font-size:0.62rem; text-transform:uppercase; letter-spacing:0.12em; color:#5c5a54; margin:0.75rem 0 0.25rem;'>vs. No Investment &nbsp;"
            f"<span style='color:{_delta_col}; font-family:\"Ropa Sans\"; font-size:1.2rem; font-weight:400; letter-spacing:0.03em;'>{_delta_sign}€{delta_vs_baseline:,.2f} ({pct_vs_baseline:.2f}%)</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("<h3 style='margin-bottom:0.5rem;'><span class='material-symbols-outlined' style='font-size:16px; color:#5c5a54;'>savings</span> Compare With Bank Savings</h3>", unsafe_allow_html=True)

    bank_interest_rate = st.number_input(
        "Annual Interest Rate (%)",
        min_value=0.0,
        max_value=100.0,
        step=0.01,
        format="%.2f",
        value=0.0,
        help="Enter an annual interest rate (e.g., 3 for 3%) to estimate what you'd have if your cash earned interest instead of being invested.",
        key="bank_interest_simple"
    )

    if bank_interest_rate > 0 and not pv_hist_df.empty:
        latest_no_investment = float(plot_df["No Investment (€)"].iloc[-1])
        interest_gain = latest_no_investment * (bank_interest_rate / 100)
        total_with_interest = latest_no_investment + interest_gain

        st.markdown(
            f"""
            <div style="background:#0c1120; border:1px solid #192138; border-left:3px solid #c9a84c; border-radius:6px; padding:1.2rem 1.4rem;">
                <div style="font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.14em; color:#5c5a54; margin-bottom:0.4rem;">
                    At {bank_interest_rate:.2f}% annual interest
                </div>
                <div style="font-family:'Ropa Sans'; font-size:1.6rem; color:#27ae7a; letter-spacing:0.03em; margin-bottom:0.2rem;">
                    €{total_with_interest:,.2f}
                </div>
                <div style="font-family:Inter; font-size:0.78rem; color:#5c5a54;">Interest gain: +€{interest_gain:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

# -------------------------
# Tab: Portfolio Overview
# -------------------------
with tab_overview:
    st.markdown("<h2><span class='material-symbols-outlined' style='font-size:20px;'>dashboard</span> Portfolio Overview</h2>", unsafe_allow_html=True)

    _view = st.radio("View", ["Total Portfolio", "Investments Only"], horizontal=True, key="overview_view")
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    portfolio_df, realized, unrealized, total_profit, profit_percentage = compute_portfolio()

    if not portfolio_df.empty:
        # Tag each asset with its category
        portfolio_df['Category'] = portfolio_df['Ticker'].apply(get_category)

        if _view == "Investments Only":
            display_df = portfolio_df.copy()
        else:
            display_df = portfolio_df.copy()

        portfolio_df_display = display_df.rename(columns={
            "Ticker": "Asset",
            "Category": "Type",
            "Quantity": "Qty",
            "Average Purchase Price": "GIP(€)",
            "Cost Basis": "Invested(€)",
            "Current Price": "Price(€)",
            "Value": "Value(€)",
            "Unrealized Profit/Loss": "Unrealized P/L (€)"
        })

        st.dataframe(
            portfolio_df_display[["Asset","Type","Qty","GIP(€)","Invested(€)","Price(€)","Value(€)","Unrealized P/L (€)"]].style.format({
                "Qty": "{:.8f}",
                "GIP(€)": "€{:.4f}",
                "Invested(€)": "€{:.2f}",
                "Price(€)": "€{:.2f}",
                "Value(€)": "€{:.2f}",
                "Unrealized P/L (€)": "€{:.2f}"
            }),
            use_container_width=True
        )

        st.markdown("<br>", unsafe_allow_html=True)

        investments_value = portfolio_df["Value"].sum()
        total_invested    = portfolio_df["Cost Basis"].sum()
        total_bank = (
            st.session_state.balances.get("credit_mutuel_balance", 0.0)
            + st.session_state.balances.get("cic_balance", 0.0)
        )
        cash_broker = st.session_state.balances.get("cash_balance", 0.0)
        total_value = investments_value + cash_broker + total_bank

        if _view == "Investments Only":
            # Recalculate P&L for investments only (exclude cash)
            inv_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0.0
            col1, col2 = st.columns(2)
            col1.metric("Total Invested (cost basis)", f"€{total_invested:,.2f}")
            col2.metric("Investments Value", f"€{investments_value:,.2f}")
            col5, col6 = st.columns(2)
            col5.metric("Realized Income/Expenses", f"€{realized:,.2f}", delta_color="normal")
            col6.metric("Unrealized Profit/Loss", f"€{unrealized:,.2f}", delta_color="normal")
            col7, col8 = st.columns(2)
            col7.metric("Total Profit", f"€{total_profit:,.2f}", delta_color="normal")
            col8.metric("Return on Investments", f"{inv_pct:.2f}%", delta_color="normal")
        else:
            col1, col2 = st.columns(2)
            col1.metric("Total Invested", f"€{total_invested:,.2f}")
            col2.metric("Total Portfolio Value", f"€{total_value:,.2f}")
            col3, col4 = st.columns(2)
            col3.metric("Broker Cash", f"€{cash_broker:,.2f}")
            col4.metric("Total Bank Balance", f"€{total_bank:,.2f}")
            col5, col6 = st.columns(2)
            col5.metric("Realized Income/Expenses", f"€{realized:,.2f}", delta_color="normal")
            col6.metric("Unrealized Profit/Loss", f"€{unrealized:,.2f}", delta_color="normal")
            col7, col8 = st.columns(2)
            col7.metric("Total Profit", f"€{total_profit:,.2f}", delta_color="normal")
            col8.metric("Profit Percentage", f"{profit_percentage:.2f}%", delta_color="normal")

    else:
        st.warning("Portfolio is empty. Add transactions to view portfolio details.")

    # ── Staking Rewards Summary ──
    staking_rewards_df = st.session_state.transactions[
        st.session_state.transactions['Type'] == 'Staking Reward'
    ].copy()

    if not staking_rewards_df.empty:
        st.markdown("<h2 style='margin-top:1.5rem;'><span class='material-symbols-outlined' style='font-size:20px;'>toll</span> Staking Rewards</h2>", unsafe_allow_html=True)

        rewards_summary = staking_rewards_df.groupby('Ticker').agg(
            Tokens_Earned=('Quantity', 'sum'),
            Num_Rewards=('Quantity', 'count')
        ).reset_index()
        rewards_summary.columns = ['Ticker', 'Tokens Earned', '# Rewards']

        # Add current value (pure gain since cost basis = 0)
        if not portfolio_df.empty:
            def current_val(row):
                match = portfolio_df[portfolio_df['Ticker'] == row['Ticker']]
                if not match.empty:
                    return row['Tokens Earned'] * match['Current Price'].iloc[0]
                return 0.0
            rewards_summary['Current Value (€)'] = rewards_summary.apply(current_val, axis=1)
        else:
            rewards_summary['Current Value (€)'] = 0.0

        total_rewards_tokens = rewards_summary['Tokens Earned'].sum()
        total_rewards_current = rewards_summary['Current Value (€)'].sum()

        st.markdown(f"""
        <div style='display:flex; gap:1.2rem; flex-wrap:wrap; margin-bottom:1.2rem;'>
            <div style='flex:1; min-width:150px; background:#0c1120; border:1px solid #192138; border-left:3px solid #c9a84c; border-radius:6px; padding:0.9rem 1.1rem;'>
                <div style='font-family:Inter; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase; color:#5c5a54; margin-bottom:0.25rem;'>Total Rewards Logged</div>
                <div style='font-family:"Ropa Sans"; font-size:1.3rem; color:#f0ece0;'>{int(rewards_summary["# Rewards"].sum())} entries</div>
            </div>
            <div style='flex:1; min-width:150px; background:#0c1120; border:1px solid #192138; border-left:3px solid #27ae7a; border-radius:6px; padding:0.9rem 1.1rem;'>
                <div style='font-family:Inter; font-size:0.6rem; letter-spacing:0.12em; text-transform:uppercase; color:#5c5a54; margin-bottom:0.25rem;'>Current Value (pure gain)</div>
                <div style='font-family:"Ropa Sans"; font-size:1.3rem; color:#27ae7a;'>€{total_rewards_current:,.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.dataframe(
            rewards_summary.style.format({
                'Tokens Earned': '{:.8f}',
                'Current Value (€)': '€{:.2f}'
            }),
            use_container_width=True
        )

    st.markdown("<h2 style='margin-top:1.5rem;'><span class='material-symbols-outlined' style='font-size:20px;'>receipt_long</span> All Transactions</h2>", unsafe_allow_html=True)
    if not st.session_state.transactions.empty:
        st.dataframe(st.session_state.transactions[TRANS_DISPLAY_COLS].style.format({
            'Quantity': '{:.8f}',
            'Purchase Price': '€{:.2f}',
            'Fee Amount': '{:.6f}',
            'Income': '€{:.2f}'
        }))
    else:
        st.info("No transactions available. Add transactions using the sidebar.")

# -------------------------
# Tab: Asset Allocation
# -------------------------
with tab_allocation:
    st.markdown("<h2><span class='material-symbols-outlined' style='font-size:20px;'>donut_large</span> Asset Allocation</h2>", unsafe_allow_html=True)

    # ── Build category-aware allocation data ──
    _CAT_COLORS = {'ETF': '#27ae7a', 'Stock': '#7a9fc4', 'Crypto': '#c9a84c', 'Cash & Banks': '#5c5a54'}

    cash_broker = float(st.session_state.balances.get("cash_balance", 0.0) or 0.0)
    cash_credit = float(st.session_state.balances.get("credit_mutuel_balance", 0.0) or 0.0)
    cash_cic    = float(st.session_state.balances.get("cic_balance", 0.0) or 0.0)
    total_cash  = cash_broker + cash_credit + cash_cic

    alloc_rows = []
    if not portfolio_df.empty:
        portfolio_df['Value'] = pd.to_numeric(portfolio_df['Value'], errors='coerce').fillna(0.0)
        for _, row in portfolio_df.iterrows():
            if row['Value'] > 0:
                alloc_rows.append({
                    'Asset': str(row['Ticker']),
                    'Category': get_category(str(row['Ticker'])),
                    'Value': float(row['Value'])
                })
    alloc_rows.append({'Asset': 'Cash & Banks', 'Category': 'Cash & Banks', 'Value': float(total_cash)})
    alloc_df = pd.DataFrame(alloc_rows)
    alloc_df['Value'] = pd.to_numeric(alloc_df['Value'], errors='coerce').fillna(0.0)

    if alloc_df['Value'].sum() == 0:
        st.warning("No positive values found. Add transactions or balances to see allocation.")
    else:
        total_value   = alloc_df['Value'].sum()
        etf_value     = float(alloc_df.loc[alloc_df['Category'] == 'ETF',          'Value'].sum())
        stock_value   = float(alloc_df.loc[alloc_df['Category'] == 'Stock',        'Value'].sum())
        crypto_value  = float(alloc_df.loc[alloc_df['Category'] == 'Crypto',       'Value'].sum())
        cash_value    = float(alloc_df.loc[alloc_df['Category'] == 'Cash & Banks', 'Value'].sum())
        investments_value = etf_value + stock_value + crypto_value

        pct_etf    = etf_value    / total_value * 100 if total_value > 0 else 0
        pct_stock  = stock_value  / total_value * 100 if total_value > 0 else 0
        pct_crypto = crypto_value / total_value * 100 if total_value > 0 else 0
        pct_cash   = cash_value   / total_value * 100 if total_value > 0 else 0

        # ── Pie chart ──
        # Group by category for the chart
        chart_df = alloc_df.groupby('Category')['Value'].sum().reset_index()
        cat_order  = ['ETF', 'Stock', 'Crypto', 'Cash & Banks']
        chart_df['sort'] = chart_df['Category'].apply(lambda c: cat_order.index(c) if c in cat_order else 99)
        chart_df = chart_df.sort_values('sort').drop('sort', axis=1)
        chart_colors = [_CAT_COLORS.get(c, '#a8a49a') for c in chart_df['Category']]

        col1, col2 = st.columns([2.2, 1])
        with col1:
            fig = go.Figure(data=[go.Pie(
                labels=chart_df['Category'],
                values=chart_df['Value'],
                hole=0.55,
                marker=dict(colors=chart_colors, line=dict(color="#080c18", width=2)),
                textposition="outside",
                textinfo="label+percent",
                textfont=dict(family="Inter", size=11, color="#a8a49a"),
                hovertemplate="%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>",
                pull=[0.02] * len(chart_df),
            )])
            fig.update_layout(
                showlegend=False,
                margin=dict(l=20, r=20, t=40, b=20),
                font=dict(family="Inter", size=12, color="#5c5a54"),
                paper_bgcolor="#080c18", plot_bgcolor="#080c18",
                height=480,
                annotations=[dict(
                    text=f"<b>€{total_value:,.0f}</b><br><span style='font-size:10px;color:#5c5a54;'>NET WORTH</span>",
                    x=0.5, y=0.5, font=dict(family="Ropa Sans", size=22, color="#f0ece0"),
                    showarrow=False, align="center"
                )]
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            def _breakdown_row(label, value, pct, color, border=True):
                border_style = "border-bottom:1px solid #192138;" if border else ""
                return (
                    f"<div style='display:flex; justify-content:space-between; align-items:center; {border_style} padding:0.65rem 0;'>"
                    f"<span style='color:#a8a49a; display:flex; align-items:center; gap:0.5rem;'>"
                    f"<span style='width:8px; height:8px; border-radius:2px; background:{color}; display:inline-block;'></span>{label}</span>"
                    f"<div style='text-align:right;'>"
                    f"<div style='font-family:Ropa Sans; font-size:1rem; color:#f0ece0;'>{pct:.1f}%</div>"
                    f"<div style='font-family:Inter; font-size:0.65rem; color:#5c5a54;'>€{value:,.0f}</div>"
                    f"</div></div>"
                )
            breakdown_html = (
                "<div style='height:480px; display:flex; align-items:center; justify-content:center;'>"
                "<div style='width:100%; padding-left:12px;'>"
                "<div style='font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.14em; color:#5c5a54; font-weight:600; margin-bottom:1.2rem;'>Category Breakdown</div>"
                + _breakdown_row("ETF",          etf_value,    pct_etf,    "#27ae7a")
                + _breakdown_row("Individual Stock", stock_value, pct_stock, "#7a9fc4")
                + _breakdown_row("Crypto",        crypto_value, pct_crypto, "#c9a84c")
                + _breakdown_row("Cash & Banks",  cash_value,   pct_cash,   "#5c5a54", border=False)
                + f"<div style='margin-top:1.2rem; padding-top:0.8rem; border-top:1px solid rgba(201,168,76,0.3);'>"
                f"<div style='font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.14em; color:#5c5a54; margin-bottom:0.3rem;'>Total Net Worth</div>"
                f"<div style='font-family:Ropa Sans; font-size:1.5rem; color:#c9a84c; letter-spacing:0.03em;'>€{total_value:,.2f}</div>"
                f"</div></div></div>"
            )
            st.markdown(breakdown_html, unsafe_allow_html=True)

        # ── Category Overrides ──
        st.markdown("---")
        st.markdown("<h2><span class='material-symbols-outlined' style='font-size:20px;'>category</span> Asset Category Overrides</h2>", unsafe_allow_html=True)
        st.markdown("<p style='font-family:Inter; font-size:0.8rem; color:#a8a49a; margin-bottom:0.75rem;'>Auto-detected categories based on ticker. Override if incorrect.</p>", unsafe_allow_html=True)

        if not portfolio_df.empty:
            for _, asset_row in portfolio_df.iterrows():
                tk = str(asset_row['Ticker'])
                detected = auto_detect_category(tk)
                current_cat = get_category(tk)
                ov_col1, ov_col2, ov_col3 = st.columns([2, 2, 1])
                ov_col1.markdown(f"<div style='padding:0.45rem 0; font-family:Inter; font-size:0.85rem; color:#f0ece0;'>{tk}</div>", unsafe_allow_html=True)
                ov_col2.markdown(f"<div style='padding:0.45rem 0; font-family:Inter; font-size:0.75rem; color:#5c5a54;'>Auto: {detected}</div>", unsafe_allow_html=True)
                new_cat = ov_col3.selectbox("", ['ETF', 'Stock', 'Crypto'],
                    index=['ETF','Stock','Crypto'].index(current_cat) if current_cat in ['ETF','Stock','Crypto'] else 1,
                    key=f"cat_{tk}", label_visibility="collapsed")
                if new_cat != current_cat:
                    if save_asset_category(tk, new_cat):
                        st.session_state.asset_categories[tk] = new_cat
                        st.rerun()

        # ── Target Allocation & Rebalancing ──
        st.markdown("---")
        st.markdown("<h2><span class='material-symbols-outlined' style='font-size:20px;'>tune</span> Target Allocation & Rebalancing</h2>", unsafe_allow_html=True)

        tgt = st.session_state.allocation_targets

        # Monthly expenses from cashflow
        monthly_expenses = 0.0
        if not st.session_state.cashflow.empty:
            monthly_expenses = abs(float(
                st.session_state.cashflow.loc[st.session_state.cashflow['Amount'] < 0, 'Amount'].sum()
            ))
        cash_target = monthly_expenses * 6

        st.markdown(
            f"<p style='font-family:Inter; font-size:0.8rem; color:#a8a49a; margin-bottom:0.25rem;'>"
            f"💰 Monthly expenses (from Cashflow): <b style='color:#f0ece0;'>€{monthly_expenses:,.2f}</b> "
            f"→ Cash safety target (×6): <b style='color:#c9a84c;'>€{cash_target:,.2f}</b></p>",
            unsafe_allow_html=True
        )

        st.markdown("<p style='font-family:Inter; font-size:0.75rem; color:#5c5a54; margin-bottom:0.75rem;'>Adjust the investment split and max concentration below.</p>", unsafe_allow_html=True)

        tc1, tc2 = st.columns(2)
        with tc1:
            etf_pct = st.number_input("ETF % of investments", min_value=0.0, max_value=100.0,
                value=tgt.get('etf_pct', 50.0), step=1.0, format="%.0f", key="tgt_etf_pct",
                help="Target % of your invested money (excl. cash) to hold in ETFs")
        with tc2:
            max_single_pct = st.number_input("Max % per stock / crypto", min_value=0.5, max_value=50.0,
                value=tgt.get('max_single_pct', 5.0), step=0.5, format="%.1f", key="tgt_max_single",
                help="No individual stock or crypto should exceed this % of total investments")

        stock_crypto_pct = 100.0 - etf_pct
        st.markdown(
            f"<p style='font-family:Inter; font-size:0.78rem; color:#a8a49a;'>"
            f"→ ETF: <b style='color:#27ae7a;'>{etf_pct:.0f}%</b> of investments &nbsp;|&nbsp; "
            f"Stocks + Crypto: <b style='color:#7a9fc4;'>{stock_crypto_pct:.0f}%</b> of investments &nbsp;|&nbsp; "
            f"Max per asset: <b style='color:#c9a84c;'>{max_single_pct:.1f}%</b></p>",
            unsafe_allow_html=True
        )

        if st.button("Save Targets", key="save_targets_btn"):
            if save_allocation_targets(etf_pct, max_single_pct):
                st.session_state.allocation_targets = {'etf_pct': etf_pct, 'max_single_pct': max_single_pct}
                st.success("Targets saved!")

        # ── Rebalancing Plan ──
        st.markdown("<h3 style='margin-top:1.2rem;'>Rebalancing Plan</h3>", unsafe_allow_html=True)

        # Cash card
        cash_diff = cash_target - cash_value
        def _rebal_card(col, label, current, target_val, diff, border_color, subtitle, is_cash=False):
            if abs(diff) <= 1:
                action, action_col = "✓  OK", "#5c5a54"
            elif is_cash:
                action = f"ADD  €{abs(diff):,.0f}" if diff > 0 else f"WITHDRAW  €{abs(diff):,.0f}"
                action_col = "#27ae7a" if diff > 0 else "#c94c4c"
            else:
                action = f"BUY  €{abs(diff):,.0f}" if diff > 0 else f"SELL  €{abs(diff):,.0f}"
                action_col = "#27ae7a" if diff > 0 else "#c94c4c"
            col.markdown(
                f"<div style='background:#0c1120; border:1px solid #192138; border-left:3px solid {border_color}; border-radius:6px; padding:1rem 1.2rem;'>"
                f"<div style='font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.12em; color:#5c5a54; margin-bottom:0.3rem;'>{label}</div>"
                f"<div style='font-family:Inter; font-size:0.78rem; color:#f0ece0; margin-bottom:0.1rem;'>Now: <b>€{current:,.0f}</b></div>"
                f"<div style='font-family:Inter; font-size:0.72rem; color:#a8a49a; margin-bottom:0.45rem;'>Target: €{target_val:,.0f} {subtitle}</div>"
                f"<div style='font-family:Ropa Sans, sans-serif; font-size:1.3rem; color:{action_col}; letter-spacing:0.03em;'>{action}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        rb1, rb2, rb3 = st.columns(3)
        _rebal_card(rb1, "Cash & Banks", cash_value, cash_target, cash_diff, "#5c5a54", "(6 months expenses)", is_cash=True)

        etf_target         = investments_value * etf_pct / 100
        stock_crypto_target = investments_value * stock_crypto_pct / 100
        etf_diff           = etf_target - etf_value
        stock_crypto_diff  = stock_crypto_target - (stock_value + crypto_value)

        _rebal_card(rb2, "ETFs", etf_value, etf_target, etf_diff, "#27ae7a",
                    f"({etf_pct:.0f}% of investments)")
        _rebal_card(rb3, "Stocks + Crypto", stock_value + crypto_value, stock_crypto_target, stock_crypto_diff, "#7a9fc4",
                    f"({stock_crypto_pct:.0f}% of investments)")

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        # ── Concentration alerts ──
        if not portfolio_df.empty and investments_value > 0:
            st.markdown("<h3>Concentration Check</h3>", unsafe_allow_html=True)
            st.markdown(
                f"<p style='font-family:Inter; font-size:0.78rem; color:#a8a49a; margin-bottom:0.75rem;'>"
                f"Max allowed per individual stock or crypto: <b style='color:#c9a84c;'>{max_single_pct:.1f}%</b> "
                f"of investments (= €{investments_value * max_single_pct / 100:,.0f})</p>",
                unsafe_allow_html=True
            )
            conc_rows = []
            for _, row in portfolio_df.iterrows():
                cat = get_category(str(row['Ticker']))
                if cat in ('Stock', 'Crypto'):
                    pct_of_inv = row['Value'] / investments_value * 100 if investments_value > 0 else 0
                    limit_val  = investments_value * max_single_pct / 100
                    over       = row['Value'] - limit_val
                    conc_rows.append({
                        'Ticker':         row['Ticker'],
                        'Category':       cat,
                        'Value (€)':      row['Value'],
                        '% of Investments': pct_of_inv,
                        'Limit (€)':      limit_val,
                        'Over limit (€)': max(over, 0.0),
                        'Status':         f"⚠ TRIM €{over:,.0f}" if over > 1 else "✓ OK",
                    })
            if conc_rows:
                conc_df = pd.DataFrame(conc_rows)
                st.dataframe(
                    conc_df.style
                    .format({'Value (€)': '€{:.2f}', '% of Investments': '{:.1f}%',
                             'Limit (€)': '€{:.2f}', 'Over limit (€)': '€{:.2f}'})
                    .map(lambda v: 'color:#c94c4c' if isinstance(v, str) and '⚠' in v else '',
                         subset=['Status']),
                    use_container_width=True
                )

# -------------------------
# Tab: Historical Price Charts
# -------------------------
with tab_charts:
    st.markdown("<h2><span class='material-symbols-outlined' style='font-size:20px;'>candlestick_chart</span> Price Charts</h2>", unsafe_allow_html=True)
    if not portfolio_df.empty:
        selected_ticker = st.selectbox("Select a Ticker for Historical Chart", options=portfolio_df['Ticker'].tolist(), key="hist_ticker")
        period = st.selectbox("Time Period", options=['6mo', '1y', '2y', '5y', 'max'], key="hist_period")

        if selected_ticker:
            with st.spinner("Fetching historical data..."):
                hist_data = get_historical_data(selected_ticker, period=period)

            if not hist_data.empty:
                avg_purchase = portfolio_df[portfolio_df['Ticker'] == selected_ticker]['Average Purchase Price'].iloc[0]

                fig = px.line(hist_data, x='Date', y='Close', title=f"{selected_ticker} — {period}",
                              labels={'Close': 'Price (EUR)', 'Date': ''},
                              color_discrete_sequence=["#c9a84c"])
                fig.update_traces(line=dict(width=2.5))
                fig.add_hline(y=avg_purchase, line_dash="dash", line_color="rgba(201,168,76,0.5)",
                              annotation_text=f"Avg: €{avg_purchase:.2f}",
                              annotation_position="top left",
                              annotation_font=dict(family="Inter", color="#c9a84c", size=11))
                fig.update_layout(
                    title=dict(font=dict(family="Ropa Sans", color="#f0ece0", size=15), x=0),
                    xaxis_title="", yaxis_title="Price (EUR)",
                    **_CHART_LAYOUT
                )
                st.plotly_chart(fig, use_container_width=True)

                col1, col2, col3 = st.columns(3)
                current_price = hist_data['Close'].iloc[-1]
                avg_purchase = portfolio_df[portfolio_df['Ticker'] == selected_ticker]['Average Purchase Price'].iloc[0]

                with col1:
                    st.metric("Current Price", f"€{current_price:,.2f}")

                with col2:
                    pnl_percent = ((current_price - avg_purchase) / avg_purchase) * 100 if avg_purchase != 0 else 0.0
                    st.metric("Win/Loss (%)", f"{pnl_percent:.2f}%", delta=f"{pnl_percent:.2f}%")

                with col3:
                    volatility = hist_data['Close'].pct_change().std() * (252 ** 0.5) * 100
                    st.metric("Volatility (Ann.)", f"{volatility:.1f}%")
            else:
                st.warning(f"No historical data available for {selected_ticker}. Check ticker symbol or Yahoo Finance support.")
    else:
        st.info("Add transactions to your portfolio to view historical charts.")

# -------------------------
# Tab: Planning
# -------------------------
with tab_planning:
    st.markdown("<h2><span class='material-symbols-outlined' style='font-size:20px;'>rocket_launch</span> Planning</h2>", unsafe_allow_html=True)

    plan = st.session_state.planning_settings

    # ── Auto-save callback (fires when any widget value changes) ──
    def _autosave_plan():
        _hr = float(st.session_state.get('plan_rate', 0.0))
        _ga = float(st.session_state.get('plan_goal', 100000.0))
        _td = st.session_state.get('plan_date', date(2030, 1, 1))
        _er = float(st.session_state.get('plan_return', 7.0))
        if save_planning_settings(_hr, _ga, _td, _er):
            st.session_state.planning_settings = {
                'hourly_rate': _hr, 'goal_amount': _ga,
                'target_date': str(_td), 'expected_return': _er,
            }

    # ── Settings (auto-saved on change — no button needed) ──
    st.markdown(
        "<h3 style='display:inline;'>Your Settings</h3>"
        "<span style='font-family:Inter; font-size:0.7rem; color:#5c5a54; margin-left:0.8rem;'>auto-saved</span>",
        unsafe_allow_html=True
    )
    pc1, pc2, pc3, pc4 = st.columns(4)
    with pc1:
        hourly_rate = st.number_input("Hourly Rate (€/hr)", min_value=0.0,
            value=float(plan.get('hourly_rate', 0.0)), step=0.5, format="%.2f",
            key="plan_rate", on_change=_autosave_plan)
    with pc2:
        goal_amount = st.number_input("Net Worth Goal (€)", min_value=0.0,
            value=float(plan.get('goal_amount', 100000.0)), step=1000.0, format="%.0f",
            key="plan_goal", on_change=_autosave_plan)
    with pc3:
        _td_default = pd.to_datetime(plan.get('target_date', '2030-01-01')).date()
        target_date = st.date_input("Target Date", value=_td_default,
            min_value=date(2024, 1, 1), max_value=date(2100, 12, 31),
            key="plan_date", on_change=_autosave_plan)
    with pc4:
        expected_return = st.number_input("Expected Annual Return (%)", min_value=0.0, max_value=50.0,
            value=float(plan.get('expected_return', 7.0)), step=0.5, format="%.1f",
            key="plan_return", on_change=_autosave_plan,
            help="Expected yearly growth of your investments (e.g. 7% for a typical ETF portfolio)")

    if hourly_rate > 0 and goal_amount > 0:
        st.markdown("---")

        # ── Current net worth (assets − loans) ──
        _pf, _, _, _, _ = compute_portfolio()
        _assets = _pf["Value"].sum() if not _pf.empty else 0.0
        _cb = st.session_state.balances.get("cash_balance", 0.0)
        _cr = st.session_state.balances.get("credit_mutuel_balance", 0.0)
        _ci = st.session_state.balances.get("cic_balance", 0.0)
        _plan_loans = get_loans_summary()
        _plan_debt  = _plan_loans['total_debt']
        _plan_repay = _plan_loans['monthly_repayments']
        current_nw = _assets + _cb + _cr + _ci - _plan_debt
        remaining  = max(goal_amount - current_nw, 0.0)
        progress   = min(current_nw / goal_amount * 100, 100.0) if goal_amount > 0 else 0.0

        # ── Months remaining ──
        _today = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
        _td    = pd.to_datetime(str(target_date)).date()
        months_remaining = max((_td.year - _today.year) * 12 + (_td.month - _today.month), 1)

        # ── Cashflow: expenses and other income ──
        monthly_expenses    = 0.0
        other_monthly_income = 0.0
        if not st.session_state.cashflow.empty:
            monthly_expenses     = abs(float(
                st.session_state.cashflow.loc[st.session_state.cashflow['Amount'] < 0, 'Amount'].sum()
            ))
            other_monthly_income = float(
                st.session_state.cashflow.loc[st.session_state.cashflow['Amount'] > 0, 'Amount'].sum()
            )

        # ── Monthly investment needed (with compound interest) ──
        r = expected_return / 100 / 12  # monthly rate
        if r > 0:
            n = months_remaining
            growth_factor = (1 + r) ** n
            # PMT = (FV - PV*(1+r)^n) * r / ((1+r)^n - 1)
            monthly_invest_needed = max(
                (goal_amount - current_nw * growth_factor) * r / (growth_factor - 1), 0.0
            )
        else:
            monthly_invest_needed = remaining / months_remaining

        # ── Work hours calculation ──
        # Total needed: expenses + loan repayments + investment target
        # Other income (from cashflow) already covers part of it
        total_monthly_needed  = monthly_expenses + _plan_repay + monthly_invest_needed
        work_income_needed    = max(total_monthly_needed - other_monthly_income, 0.0)
        hours_total           = work_income_needed / hourly_rate if hourly_rate > 0 else 0.0
        # Breakdown: what's covered vs what needs work
        # Priority order: expenses → loan repayments → investment
        _income_left          = other_monthly_income
        covered_expenses      = min(_income_left, monthly_expenses)
        work_for_expenses     = max(monthly_expenses - covered_expenses, 0.0)
        _income_left          = max(_income_left - monthly_expenses, 0.0)
        covered_repay         = min(_income_left, _plan_repay)
        work_for_repay        = max(_plan_repay - covered_repay, 0.0)
        _income_left          = max(_income_left - _plan_repay, 0.0)
        work_for_investment   = max(monthly_invest_needed - _income_left, 0.0)
        hours_expenses        = work_for_expenses  / hourly_rate if hourly_rate > 0 else 0.0
        hours_repay           = work_for_repay     / hourly_rate if hourly_rate > 0 else 0.0
        hours_investment      = work_for_investment / hourly_rate if hourly_rate > 0 else 0.0

        # ── Progress bar ──
        _pg_col = "#27ae7a" if progress >= 80 else "#c9a84c" if progress >= 40 else "#c94c4c"
        st.markdown(
            f"<div style='margin-bottom:1.5rem;'>"
            f"<div style='display:flex; justify-content:space-between; font-family:Inter; font-size:0.72rem; color:#a8a49a; margin-bottom:0.4rem;'>"
            f"<span>Net Worth Progress</span><span style='color:{_pg_col};'>{progress:.1f}%</span></div>"
            f"<div style='background:#192138; border-radius:4px; height:10px;'>"
            f"<div style='background:{_pg_col}; width:{progress:.1f}%; height:10px; border-radius:4px; transition:width 0.3s;'></div>"
            f"</div>"
            f"<div style='display:flex; justify-content:space-between; font-family:Inter; font-size:0.68rem; color:#5c5a54; margin-top:0.3rem;'>"
            f"<span>€{current_nw:,.0f} now</span><span>€{goal_amount:,.0f} goal</span></div>"
            f"</div>",
            unsafe_allow_html=True
        )

        # ── Key metrics ──
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Remaining to goal", f"€{remaining:,.0f}")
        m2.metric("Months to target", str(months_remaining))
        m3.metric("Monthly investment needed", f"€{monthly_invest_needed:,.0f}",
                  help=f"With {expected_return:.1f}% annual return (compound interest)")
        m4.metric("Other monthly income", f"€{other_monthly_income:,.0f}",
                  help="Positive entries in your Cashflow tab (excl. work income)")

        # ── Income covers breakdown ──
        if other_monthly_income > 0 or monthly_expenses > 0:
            net_after_income = other_monthly_income - monthly_expenses  # positive = surplus
            if other_monthly_income >= monthly_expenses:
                _exp_tag  = f"<span style='color:#27ae7a;'>✓ €{monthly_expenses:,.0f} expenses fully covered</span>"
                _surplus  = other_monthly_income - monthly_expenses
                _inv_tag  = (
                    f"<span style='color:#27ae7a;'>+ €{_surplus:,.0f} toward investments</span>"
                    if _surplus > 0 else ""
                )
            else:
                _exp_tag = (
                    f"<span style='color:#c9a84c;'>€{covered_expenses:,.0f} of €{monthly_expenses:,.0f} expenses "
                    f"(€{work_for_expenses:,.0f} still needs work)</span>"
                )
                _inv_tag = ""
            st.markdown(
                f"<div style='background:#0c1120; border:1px solid #192138; border-radius:6px; "
                f"padding:0.8rem 1.1rem; margin:0.5rem 0 0.2rem; font-family:Inter; font-size:0.78rem;'>"
                f"<span style='color:#5c5a54; text-transform:uppercase; letter-spacing:0.1em; font-size:0.62rem;'>Your other income (€{other_monthly_income:,.0f}/mo) covers →</span><br>"
                f"<span style='color:#a8a49a;'>{_exp_tag}"
                f"{('&nbsp;&nbsp;·&nbsp;&nbsp;' + _inv_tag) if _inv_tag else ''}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        # ── Work hours breakdown ──
        st.markdown("<h3 style='margin-top:1.2rem;'>How much do you need to work this month?</h3>", unsafe_allow_html=True)

        def _hour_card(col, label, hours, euros, border_color, detail="", covered=False):
            days = hours / 8
            if covered:
                col.markdown(
                    f"<div style='background:#0c1120; border:1px solid #192138; border-left:3px solid #27ae7a; border-radius:6px; padding:1rem 1.2rem;'>"
                    f"<div style='font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.12em; color:#5c5a54; margin-bottom:0.3rem;'>{label}</div>"
                    f"<div style='font-family:Ropa Sans, sans-serif; font-size:1.6rem; color:#27ae7a; letter-spacing:0.03em;'>Covered ✓</div>"
                    f"<div style='font-family:Inter; font-size:0.75rem; color:#a8a49a; margin-top:0.1rem;'>€{euros:,.0f} by other income</div>"
                    f"{'<div style=\"font-family:Inter; font-size:0.68rem; color:#5c5a54; margin-top:0.2rem;\">' + detail + '</div>' if detail else ''}"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                col.markdown(
                    f"<div style='background:#0c1120; border:1px solid #192138; border-left:3px solid {border_color}; border-radius:6px; padding:1rem 1.2rem;'>"
                    f"<div style='font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.12em; color:#5c5a54; margin-bottom:0.3rem;'>{label}</div>"
                    f"<div style='font-family:Ropa Sans, sans-serif; font-size:1.6rem; color:#f0ece0; letter-spacing:0.03em;'>{hours:.0f} hrs</div>"
                    f"<div style='font-family:Inter; font-size:0.75rem; color:#a8a49a; margin-top:0.1rem;'>≈ {days:.1f} days &nbsp;·&nbsp; €{euros:,.0f}</div>"
                    f"{'<div style=\"font-family:Inter; font-size:0.68rem; color:#5c5a54; margin-top:0.2rem;\">' + detail + '</div>' if detail else ''}"
                    f"</div>",
                    unsafe_allow_html=True
                )

        # Cards: show loan repayment card only if user has active loans
        if _plan_repay > 0:
            h1, h2, h3, h4 = st.columns(4)
        else:
            h1, h2, h3 = st.columns(3)
            h4 = None

        # Expenses card
        if work_for_expenses == 0 and monthly_expenses > 0:
            _hour_card(h1, "Monthly expenses", hours_expenses,
                       monthly_expenses, "#27ae7a",
                       f"Paid by your €{other_monthly_income:,.0f} other income", covered=True)
        else:
            _hour_card(h1, "For expenses (from work)", hours_expenses,
                       work_for_expenses, "#c94c4c",
                       f"€{covered_expenses:,.0f} covered by income · €{work_for_expenses:,.0f} gap")

        # Loan repayment card (only if loans exist)
        if h4 is not None:
            if work_for_repay == 0:
                _hour_card(h2, "Loan repayments", 0,
                           _plan_repay, "#27ae7a",
                           f"€{_plan_repay:,.0f}/mo covered by other income", covered=True)
            else:
                _hour_card(h2, "Loan repayments (from work)", hours_repay,
                           work_for_repay, "#c94c4c",
                           f"€{_plan_repay:,.0f}/mo across {len(st.session_state.loans)} loan(s)")
            _hour_card(h3, "For investment (from work)", hours_investment,
                       work_for_investment, "#27ae7a",
                       f"€{monthly_invest_needed:,.0f} needed · {expected_return:.1f}% return assumed")
            _hour_card(h4, "Total work hours needed", hours_total,
                       work_income_needed, "#c9a84c",
                       f"€{hourly_rate:.0f}/hr × {hours_total:.0f} hrs = €{work_income_needed:,.0f}")
        else:
            _hour_card(h2, "For investment (from work)", hours_investment,
                       work_for_investment, "#27ae7a",
                       f"€{monthly_invest_needed:,.0f} needed · {expected_return:.1f}% return assumed")
            _hour_card(h3, "Total work hours needed", hours_total,
                       work_income_needed, "#c9a84c",
                       f"€{hourly_rate:.0f}/hr × {hours_total:.0f} hrs = €{work_income_needed:,.0f}")

        # ── Active loans detail (if any) ──
        import math as _math
        if not st.session_state.loans.empty:
            st.markdown("<h3 style='margin-top:1.2rem;'>Leningen</h3>", unsafe_allow_html=True)
            _today_l = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
            loan_rows = []
            for _, lr in st.session_state.loans.iterrows():
                _ltype = str(lr.get('Loan Type', 'standard'))
                _r     = float(lr.get('Annual Rate', 0.0)) / 100 / 12
                rem    = calc_loan_balance(
                    lr.get('Principal', 0.0), lr.get('Annual Rate', 0.0),
                    lr.get('Monthly Payment', 0.0), lr.get('Start Date'),
                    loan_type=_ltype,
                    monthly_borrow=float(lr.get('Monthly Borrow', 0.0)),
                    study_end_date=lr.get('Study End Date'),
                    repayment_years=float(lr.get('Repayment Years', 10.0)),
                )

                if _ltype == 'student':
                    _sed = lr.get('Study End Date')
                    _mb  = float(lr.get('Monthly Borrow', 0.0))
                    _ry  = float(lr.get('Repayment Years', 10.0))
                    _studying = (_sed is None or _sed == 'None'
                                 or _today_l <= pd.to_datetime(str(_sed)).date())
                    _bal_end  = (_student_balance_at(_mb, _r, lr.get('Start Date'), _sed)
                                 if _sed and _sed != 'None' else rem)
                    _pmt_after = (calc_student_monthly_payment(
                        _mb, float(lr.get('Annual Rate', 0.0)),
                        lr.get('Start Date'), _sed, _ry) if _sed and _sed != 'None' else 0.0)
                    _total_repay = _pmt_after * _ry * 12 if _pmt_after > 0 else 0.0
                    _total_interest = max(_total_repay - _bal_end, 0.0)
                    loan_rows.append({
                        'Naam': lr['Name'],
                        'Type': 'Studentenlening',
                        'Huidig saldo (€)': rem,
                        'Saldo bij afstuderen (€)': _bal_end,
                        'Aflossing na studie': f"€{_pmt_after:,.0f}/mo" if _pmt_after > 0 else "–",
                        'Status': "📚 Studie loopt" if _studying else "💼 Terugbetaling",
                        'Rente': f"{lr.get('Annual Rate', 0.0):.2f}%",
                        'Totale rente (€)': _total_interest,
                    })
                else:
                    _pmt = float(lr.get('Monthly Payment', 0.0))
                    if _r > 0 and _pmt > 0 and rem * _r / _pmt < 1:
                        try:
                            _mo_left = _math.ceil(
                                -_math.log(1 - rem * _r / _pmt) / _math.log(1 + _r))
                        except Exception:
                            _mo_left = 0
                    else:
                        _mo_left = int(rem / _pmt) if _pmt > 0 else 0
                    loan_rows.append({
                        'Naam': lr['Name'],
                        'Type': 'Standaard',
                        'Huidig saldo (€)': rem,
                        'Saldo bij afstuderen (€)': 0.0,
                        'Aflossing na studie': f"€{_pmt:,.0f}/mo",
                        'Status': f"{_mo_left} maanden",
                        'Rente': f"{lr.get('Annual Rate', 0.0):.2f}%",
                        'Totale rente (€)': max(_pmt * _mo_left - rem, 0.0),
                    })
            _loan_df = pd.DataFrame(loan_rows)
            _show_cols = ['Naam', 'Type', 'Status', 'Huidig saldo (€)',
                          'Saldo bij afstuderen (€)', 'Aflossing na studie',
                          'Rente', 'Totale rente (€)']
            _show_cols = [c for c in _show_cols if c in _loan_df.columns]
            st.dataframe(
                _loan_df[_show_cols].style.format({
                    'Huidig saldo (€)': '€{:,.0f}',
                    'Saldo bij afstuderen (€)': '€{:,.0f}',
                    'Totale rente (€)': '€{:,.0f}',
                }),
                use_container_width=True, hide_index=True
            )

        # ── Leverage Analysis ──
        if not st.session_state.loans.empty:
            st.markdown("---")
            st.markdown("<h3>Leverage Analysis</h3>", unsafe_allow_html=True)
            st.markdown(
                "<p style='font-family:Inter; font-size:0.8rem; color:#a8a49a; margin-bottom:1rem;'>"
                "Is het rendabel om geleend geld te beleggen? "
                "Je portfolio moet meer opleveren dan de rente die je betaalt.</p>",
                unsafe_allow_html=True
            )

            # Annualised portfolio return
            _ann_pct = calc_annualized_return(profit_percentage, st.session_state.transactions)

            for _, _lr in st.session_state.loans.iterrows():
                _principal  = float(_lr['Principal'])
                _rate       = float(_lr['Annual Rate'])
                _rem        = calc_loan_balance(_principal, _rate,
                                                float(_lr['Monthly Payment']), _lr['Start Date'])

                # Interest cost on remaining balance
                _annual_interest   = _rem * _rate / 100
                _monthly_interest  = _annual_interest / 12

                # Investment return on the original principal
                _annual_gain   = _principal * _ann_pct / 100
                _monthly_gain  = _annual_gain / 12

                # Net and spread
                _net_annual = _annual_gain - _annual_interest
                _spread     = _ann_pct - _rate
                _profitable = _spread > 0
                _status_col = "#27ae7a" if _profitable else "#c94c4c"
                _status_ico = "✓" if _profitable else "✗"
                _spread_sign = "+" if _spread >= 0 else ""

                # Card header
                st.markdown(
                    f"<div style='font-family:Inter; font-size:0.65rem; text-transform:uppercase; "
                    f"letter-spacing:0.1em; color:#5c5a54; margin-bottom:0.5rem;'>"
                    f"{_lr['Name']} &nbsp;·&nbsp; €{_principal:,.0f} geleend @ {_rate:.2f}%</div>",
                    unsafe_allow_html=True
                )

                la1, la2, la3, la4 = st.columns(4)

                la1.metric(
                    "Jaarlijkse rentekost",
                    f"€{_annual_interest:,.0f}",
                    help=f"{_rate:.2f}% × €{_rem:,.0f} resterend saldo · €{_monthly_interest:,.0f}/maand"
                )
                la2.metric(
                    f"Rendement op €{_principal:,.0f}",
                    f"€{_annual_gain:,.0f}",
                    delta=f"{_ann_pct:+.1f}% per jaar (huidig portfolio)",
                    help=f"Jouw portfolio rendement geannualiseerd · €{_monthly_gain:,.0f}/maand"
                )
                la3.metric(
                    "Netto winst/verlies",
                    f"€{_net_annual:,.0f}",
                    delta=f"{_spread_sign}{_spread:.1f}% spread",
                    delta_color="normal" if _profitable else "inverse"
                )
                la4.metric(
                    "Break-even rendement",
                    f"{_rate:.2f}%",
                    help="Minimum jaarrendement om de rente te dekken"
                )

                # Verdict bar
                if _ann_pct == 0:
                    _verdict = "Nog geen portfolio data beschikbaar voor berekening."
                    _verdict_col = "#5c5a54"
                elif _profitable:
                    _verdict = (
                        f"{_status_ico} Winstgevend — je portfolio ({_ann_pct:.1f}%) "
                        f"rendert {_spread:.1f}% meer dan de rente ({_rate:.2f}%). "
                        f"Netto winst: €{_net_annual:,.0f}/jaar."
                    )
                    _verdict_col = "#27ae7a"
                else:
                    _verdict = (
                        f"{_status_ico} Niet winstgevend — je portfolio ({_ann_pct:.1f}%) "
                        f"rendert {abs(_spread):.1f}% minder dan de rente ({_rate:.2f}%). "
                        f"Je verliest €{abs(_net_annual):,.0f}/jaar door deze lening."
                    )
                    _verdict_col = "#c94c4c"

                st.markdown(
                    f"<div style='background:#0c1120; border:1px solid #192138; "
                    f"border-left:3px solid {_verdict_col}; border-radius:6px; "
                    f"padding:0.7rem 1rem; margin:0.4rem 0 1.2rem; "
                    f"font-family:Inter; font-size:0.78rem; color:{_verdict_col};'>"
                    f"{_verdict}</div>",
                    unsafe_allow_html=True
                )

            # Overall summary if multiple loans
            if len(st.session_state.loans) > 1:
                _total_principal  = float(st.session_state.loans['Principal'].sum())
                _total_interest_y = sum(
                    calc_loan_balance(r['Principal'], r['Annual Rate'],
                                      r['Monthly Payment'], r['Start Date']) * r['Annual Rate'] / 100
                    for _, r in st.session_state.loans.iterrows()
                )
                _total_gain_y  = _total_principal * _ann_pct / 100
                _total_net_y   = _total_gain_y - _total_interest_y
                _tc = "#27ae7a" if _total_net_y >= 0 else "#c94c4c"
                st.markdown(
                    f"<div style='background:#0c1120; border:1px solid #192138; border-radius:6px; "
                    f"padding:0.8rem 1.1rem; font-family:Inter; font-size:0.78rem;'>"
                    f"<span style='color:#5c5a54; font-size:0.62rem; text-transform:uppercase; letter-spacing:0.1em;'>Totaal alle leningen</span><br>"
                    f"<span style='color:{_tc}; font-size:1rem;'>Netto {'+' if _total_net_y >= 0 else ''}€{_total_net_y:,.0f}/jaar</span>"
                    f"<span style='color:#5c5a54; font-size:0.75rem;'> &nbsp;(rendement €{_total_gain_y:,.0f} − rente €{_total_interest_y:,.0f})</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

        # ── Monthly investment history ──
        st.markdown("---")
        st.markdown("<h3>Monthly Investment History</h3>", unsafe_allow_html=True)

        if not st.session_state.transactions.empty:
            _buy_tx = st.session_state.transactions[
                st.session_state.transactions['Type'] == 'Buy'
            ].copy()
            if not _buy_tx.empty:
                _buy_tx['Date'] = pd.to_datetime(_buy_tx['Date'], errors='coerce')
                _buy_tx['YearMonth'] = _buy_tx['Date'].dt.to_period('M')
                _buy_tx['Invested'] = _buy_tx['Quantity'] * _buy_tx['Purchase Price'] + _buy_tx['Fee Amount'].clip(lower=0)
                _monthly = _buy_tx.groupby('YearMonth')['Invested'].sum().reset_index()
                _monthly['Month'] = _monthly['YearMonth'].dt.to_timestamp()
                _monthly = _monthly.sort_values('Month')

                _fig_dca = go.Figure()
                _fig_dca.add_trace(go.Bar(
                    x=_monthly['Month'], y=_monthly['Invested'],
                    name='Invested', marker_color='#c9a84c',
                    hovertemplate='%{x|%b %Y}<br>€%{y:,.0f}<extra></extra>'
                ))
                _fig_dca.add_hline(
                    y=monthly_invest_needed, line_dash="dash", line_color="#27ae7a",
                    annotation_text=f"Target €{monthly_invest_needed:,.0f}/mo",
                    annotation_font=dict(family="Inter", color="#27ae7a", size=11),
                    annotation_position="top left"
                )
                _fig_dca.update_layout(
                    plot_bgcolor="#080c18", paper_bgcolor="#080c18",
                    font=dict(family="Inter", color="#5c5a54", size=11),
                    xaxis=dict(gridcolor="#192138", linecolor="#192138", tickfont=dict(color="#5c5a54")),
                    yaxis=dict(gridcolor="#192138", linecolor="#192138", tickfont=dict(color="#5c5a54"), title="€ Invested"),
                    margin=dict(l=10, r=10, t=40, b=10),
                    hovermode="x unified",
                    hoverlabel=dict(bgcolor="#0c1120", bordercolor="#192138", font=dict(family="Inter", color="#f0ece0", size=12)),
                    title=dict(text="Monthly Investments vs Target", font=dict(family="Ropa Sans", color="#f0ece0", size=15), x=0),
                    showlegend=False,
                )
                st.plotly_chart(_fig_dca, use_container_width=True)

                # summary row
                _avg_monthly = _monthly['Invested'].mean()
                _on_target   = int((_monthly['Invested'] >= monthly_invest_needed).sum())
                _total_months = len(_monthly)
                s1, s2, s3 = st.columns(3)
                s1.metric("Avg monthly invested", f"€{_avg_monthly:,.0f}")
                s2.metric("Months on target", f"{_on_target} / {_total_months}")
                s3.metric("Total invested (Buy)", f"€{_monthly['Invested'].sum():,.0f}")
            else:
                st.info("No Buy transactions yet.")
        else:
            st.info("No transactions yet.")
    else:
        st.info("Set your hourly rate and goal above to see your plan.")

# -------------------------
# Footer
# -------------------------
st.markdown("---")
