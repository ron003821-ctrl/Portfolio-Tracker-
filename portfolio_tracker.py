import streamlit as st
from supabase import create_client
import yfinance as yf
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, time, date, timezone, tzinfo
from zoneinfo import ZoneInfo
import importlib
import finance_utils, ui_components
# Streamlit Cloud reruns this file after a git push but keeps helper modules
# cached in memory, so new functions would be missing until a reboot.
# Reloading them on every run picks up the latest code (they are small and fast).
importlib.reload(finance_utils)
importlib.reload(ui_components)
from finance_utils import (xirr, investment_cashflows, benchmark_value, plan_deposit,
                           deposit_needed_without_selling, box3_base, next_peildatum, thresholds_for,
                           diff_cashflow, change_from_closes, daily_moves)
from ui_components import eur, pct, heat_color, stat_card, stat_row, holdings_table

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

def normalize_ticker(ticker: str) -> str:
    """One canonical form per asset: uppercase, trimmed, known aliases mapped.
    Prevents 'VUSA', 'Vusa' and 'VUSA.AS' from showing up as three assets."""
    t = str(ticker).strip().upper()
    _ALIASES = {
        'VUSA': 'VUSA.AS',
        'VWRL': 'VWRL.AS',
        'QDVE': 'QDVE.DE',
    }
    return _ALIASES.get(t, t)

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
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

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
        color: #4D7CFE;
        margin-right: 0.35rem;
    }

    /* ═══════════════════════════════════════════
       BRAND TOKENS — dark app with blue accent
       Ink    #0C0D10 (bg)  #14161C (card)  #121419 (sidebar)
       Lines  #1F2229 (card border)  #262A33 (control border)
       Blue   #4D7CFE  rgba(77,124,254,x)
       Text   #EDEFF3 (primary)  #A4A9B4 (secondary)  #8D93A0 (muted)
       Up     #3DDC84   Down #FF6B6B   (only for gains / losses)
       Categories: ETF #4D7CFE  Stock #22C3B5  Crypto #F5A623  Cash #5B6170
       Font   Manrope · tabular numbers
       Radius controls 10–12px · cards 16px
    ═══════════════════════════════════════════ */

    html, body, .stApp, .main {
        font-family: 'Manrope', sans-serif !important;
        background-color: #0C0D10 !important;
        color: #EDEFF3 !important;
        font-variant-numeric: tabular-nums;
    }
    .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th {
        font-family: 'Manrope', sans-serif !important;
    }

    .main .block-container, [data-testid="stMainBlockContainer"] {
        padding-top: 3.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1320px !important;
    }

    /* ── Typography ── */
    h1, h2, h3, h4 { font-family: 'Manrope', sans-serif !important; }
    h1 {
        color: #EDEFF3 !important;
        font-size: 1.65rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.02em !important;
        margin-bottom: 0 !important;
        padding: 0 !important;
        border: none !important;
    }
    h2 {
        color: #EDEFF3 !important;
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        letter-spacing: -0.01em !important;
        -webkit-text-fill-color: unset !important;
        background: none !important;
        margin-bottom: 0.6rem !important;
    }
    h3 {
        color: #A4A9B4 !important;
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #121419 !important;
        border-right: 1px solid #1F2229 !important;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding-top: 1rem !important; }

    /* Sidebar navigation (the radio with key "nav") as a menu list.
       Covers both radio markups: newer Streamlit (stRadioOption) and older (baseweb). */
    .st-key-nav [role="radiogroup"] { gap: 2px !important; width: 100% !important; }
    .st-key-nav, .st-key-nav [data-testid="stRadio"], .st-key-nav [role="radiogroup"] > div { width: 100% !important; }
    .st-key-nav [data-testid="stRadioOption"], .st-key-nav label[data-baseweb="radio"] { display: flex !important; }
    .st-key-nav [data-testid="stRadioOption"], .st-key-nav label[data-baseweb="radio"] {
        width: 100% !important;
        margin: 0 !important;
        padding: 0.65rem 0.8rem !important;
        border-radius: 10px !important;
        cursor: pointer !important;
        transition: background 0.12s !important;
        box-sizing: border-box !important;
    }
    .st-key-nav [data-testid="stRadioOption"] > div > div:not([data-testid="stMarkdownContainer"]),
    .st-key-nav label[data-baseweb="radio"] > div:first-child { display: none !important; }
    .st-key-nav [data-testid="stRadioOption"] p, .st-key-nav label[data-baseweb="radio"] p {
        font-size: 0.92rem !important; font-weight: 500 !important; color: #A4A9B4 !important;
    }
    .st-key-nav [data-testid="stRadioOption"] p [role="img"], .st-key-nav label[data-baseweb="radio"] p [role="img"] {
        margin-right: 0.55rem !important; font-size: 1.15rem !important; vertical-align: -3px !important;
    }
    .st-key-nav [data-testid="stRadioOption"]:hover, .st-key-nav label[data-baseweb="radio"]:hover {
        background: rgba(255,255,255,0.04) !important;
    }
    .st-key-nav [data-testid="stRadioOption"][data-selected="true"],
    .st-key-nav label[data-baseweb="radio"]:has(input:checked) { background: rgba(77,124,254,0.14) !important; }
    .st-key-nav [data-testid="stRadioOption"][data-selected="true"] p,
    .st-key-nav label[data-baseweb="radio"]:has(input:checked) p { color: #EDEFF3 !important; font-weight: 700 !important; }
    .st-key-nav [data-testid="stRadioOption"][data-selected="true"] p [role="img"],
    .st-key-nav label[data-baseweb="radio"]:has(input:checked) p [role="img"] { color: #4D7CFE !important; }

    .pf-side-label {
        font-size: 0.75rem; font-weight: 600; color: #8D93A0;
        margin: 1.2rem 0 0.5rem 0.2rem;
    }

    /* ── Expanders ── */
    [data-testid="stExpander"], [data-testid="stSidebar"] .st-expander {
        background-color: #14161C !important;
        border: 1px solid #1F2229 !important;
        border-radius: 12px !important;
        box-shadow: none !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] { margin-bottom: 0.4rem !important; }
    [data-testid="stExpander"] details { border: none !important; border-radius: 12px !important; }
    [data-testid="stExpander"]:hover { border-color: #262A33 !important; }
    [data-testid="stExpander"] summary p { font-weight: 600 !important; font-size: 0.9rem !important; }

    /* ── Tabs (used inside some pages) ── */
    .stTabs [data-baseweb="tab-list"] { border-bottom: 1px solid #1F2229 !important; gap: 0.4rem !important; }
    .stTabs [role="tab"] {
        background: transparent !important;
        color: #8D93A0 !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 0.7rem 0.9rem !important;
    }
    .stTabs [aria-selected="true"] { color: #EDEFF3 !important; border-bottom: 2px solid #4D7CFE !important; }

    /* ── Buttons ── */
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        background-color: transparent !important;
        color: #EDEFF3 !important;
        border: 1px solid #262A33 !important;
        border-radius: 12px !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
        min-height: 44px !important;
        padding: 0.45rem 1rem !important;
        box-shadow: none !important;
        transition: background 0.12s, border-color 0.12s !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
        background-color: rgba(77,124,254,0.10) !important;
        border-color: #4D7CFE !important;
        color: #EDEFF3 !important;
    }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primaryFormSubmit"] {
        background-color: #4D7CFE !important;
        border-color: #4D7CFE !important;
        color: #FFFFFF !important;
    }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primaryFormSubmit"]:hover {
        background-color: #3F6CEB !important;
    }
    button:focus-visible { outline: 2px solid #4D7CFE !important; outline-offset: 2px !important; }

    /* ── Metric cards ── */
    [data-testid="stMetric"] {
        background-color: #14161C !important;
        border: 1px solid #1F2229 !important;
        border-radius: 16px !important;
        padding: 1rem 1.15rem !important;
        box-shadow: none !important;
    }
    [data-testid="stMetricLabel"] p {
        color: #8D93A0 !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        text-transform: none !important;
        letter-spacing: 0 !important;
    }
    [data-testid="stMetricValue"] {
        color: #EDEFF3 !important;
        font-family: 'Manrope', sans-serif !important;
        font-size: 1.5rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.02em !important;
    }

    /* ── Bordered containers become cards ── */
    [data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]),
    .st-key-pf-chart, .st-key-pf-map {
        background-color: #14161C !important;
        border: 1px solid #1F2229 !important;
        border-radius: 16px !important;
    }

    /* ── Segmented control (chart range) ── */
    [data-testid="stButtonGroup"] { justify-content: flex-end !important; }
    [data-testid="stButtonGroup"] button {
        min-height: 32px !important;
        border-radius: 8px !important;
        font-size: 0.78rem !important;
        font-weight: 700 !important;
        background: transparent !important;
        border: 1px solid transparent !important;
        color: #8D93A0 !important;
    }
    [data-testid="stButtonGroup"] button:hover { color: #EDEFF3 !important; background: rgba(255,255,255,0.04) !important; }
    [data-testid="stButtonGroup"] button[aria-checked="true"],
    [data-testid="stButtonGroup"] button[kind$="Active"],
    [data-testid="stButtonGroup"] button[data-testid$="Active"] {
        background: #4D7CFE !important; border-color: #4D7CFE !important; color: #FFFFFF !important;
    }
    [data-testid="stButtonGroup"] button[aria-checked="true"] p,
    [data-testid="stButtonGroup"] button[kind$="Active"] p,
    [data-testid="stButtonGroup"] button[data-testid$="Active"] p { color: #FFFFFF !important; }

    /* ── Inputs ── */
    [data-baseweb="input"], [data-baseweb="base-input"] {
        background-color: #0C0D10 !important;
        border: 1px solid #262A33 !important;
        border-radius: 10px !important;
    }
    [data-baseweb="input"]:focus-within, [data-baseweb="base-input"]:focus-within {
        border-color: #4D7CFE !important;
        box-shadow: 0 0 0 2px rgba(77,124,254,0.18) !important;
    }
    [data-baseweb="input"] [data-baseweb="base-input"] {
        border: none !important; box-shadow: none !important; background-color: transparent !important;
    }
    .stTextInput input, .stNumberInput input, .stDateInput input {
        background-color: transparent !important;
        border: none !important; outline: none !important; box-shadow: none !important;
        color: #EDEFF3 !important;
        font-size: 0.9rem !important;
    }
    .stTextInput [data-baseweb="input"] button, .stNumberInput button {
        background: transparent !important; border: none !important; box-shadow: none !important; color: #8D93A0 !important;
    }
    .stTextInput [data-baseweb="input"] button:hover, .stNumberInput button:hover { color: #4D7CFE !important; }
    [data-testid="InputInstructions"] { display: none !important; }
    .stSelectbox > div > div {
        background-color: #0C0D10 !important;
        border: 1px solid #262A33 !important;
        border-radius: 10px !important;
        color: #EDEFF3 !important;
    }

    /* ── DataFrames ── */
    .stDataFrame {
        border: 1px solid #1F2229 !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        box-shadow: none !important;
    }

    /* ── Misc ── */
    .stCaption, [data-testid="stCaptionContainer"] { color: #8D93A0 !important; font-size: 0.78rem !important; font-style: normal !important; }
    hr { border-color: #1F2229 !important; }
    .stAlert { border-radius: 12px !important; box-shadow: none !important; }

    /* ── Page header and Overview building blocks (HTML rendered by the app) ── */
    .pf-sub { color: #8D93A0; font-size: 0.85rem; margin: 0.15rem 0 1.3rem; }
    .pf-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; margin-bottom: 12px; }
    .pf-card { background: #14161C; border: 1px solid #1F2229; border-radius: 16px; padding: 16px 18px; }
    .pf-label { color: #8D93A0; font-size: 0.82rem; font-weight: 500; }
    .pf-value { font-size: 1.75rem; font-weight: 800; letter-spacing: -0.02em; margin-top: 2px; line-height: 1.2; }
    .pf-small { color: #8D93A0; font-size: 0.78rem; margin-top: 2px; }
    .pf-card-title { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; flex-wrap: wrap; }
    .pf-card-title h2 { margin: 0 !important; font-size: 0.95rem !important; }
    .pf-hint { color: #8D93A0; font-size: 0.75rem; }
    .pf-table-wrap { background: #14161C; border: 1px solid #1F2229; border-radius: 16px; padding: 16px 2px 6px; margin-top: 12px; }
    .pf-table-wrap .pf-card-title { padding: 0 16px 6px; }
    .pf-scroll { overflow-x: auto; }
    .pf-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
    .pf-table th { color: #8D93A0; font-size: 0.75rem; font-weight: 600; text-align: right; padding: 10px 16px; white-space: nowrap; }
    .pf-table td { text-align: right; padding: 11px 16px; border-top: 1px solid #1F2229 !important; border-bottom: none !important; white-space: nowrap; }
    .pf-table th:first-child, .pf-table td:first-child { text-align: left; }
    .pf-table, .pf-table tr, .pf-table th, .pf-table td { background: transparent !important; border-left: none !important; border-right: none !important; }
    .pf-table { border: none !important; margin: 0 !important; }
    .pf-table thead tr th { border-top: none !important; border-bottom: none !important; }
    .pf-table .pf-tk { font-weight: 700; }
    .pf-table .pf-cat { color: #8D93A0; margin-left: 6px; }
    .pf-up { color: #3DDC84 !important; }
    .pf-down { color: #FF6B6B !important; }
    .pf-muted { color: #8D93A0 !important; }

    /* ── Mobile ── */
    @media (max-width: 768px) {
        .main .block-container, [data-testid="stMainBlockContainer"] {
            padding-left: 0.9rem !important;
            padding-right: 0.9rem !important;
            padding-top: 3.5rem !important;
        }
        [data-testid="stMetricValue"] { font-size: 1.15rem !important; }
        .pf-value { font-size: 1.35rem; }
        .pf-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
        .pf-card { padding: 12px 14px; }
        .stNumberInput, .stTextInput, .stSelectbox { width: 100% !important; }
        h1 { font-size: 1.3rem !important; }
    }
</style>
""", unsafe_allow_html=True)

# -------------------------
# Supabase
# -------------------------
def _is_public_key(key: str) -> bool:
    """True if `key` is a public (anon / publishable) Supabase key rather than the secret key."""
    if key.startswith("sb_publishable_"):
        return True
    if key.startswith("sb_secret_"):
        return False
    try:  # legacy JWT keys: read the role claim
        import base64, json
        payload = key.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role") == "anon"
    except Exception:
        return False

@st.cache_resource
def init_supabase():
    url = st.secrets["supabase"]["url"]
    key = st.secrets["supabase"]["key"].strip()
    if _is_public_key(key):
        raise ValueError(
            "supabase.key is the public anon/publishable key. The database only accepts the "
            "SECRET key (Supabase > Project Settings > API Keys)."
        )
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
            'date': date_str, 'time': time_str, 'type': trans_type, 'ticker': normalize_ticker(ticker),
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
            'date': date_str, 'time': time_str, 'type': trans_type, 'ticker': normalize_ticker(ticker),
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

_TARGET_DEFAULTS = {'cash_pct': 20.0, 'etf_pct': 56.0, 'stocks_pct': 8.0, 'crypto_pct': 16.0,
                    'max_single_pct': 5.0}
_TARGET_PARTS = ('cash_pct', 'etf_pct', 'stocks_pct', 'crypto_pct')

def load_allocation_targets():
    """Target split of your TOTAL (cash + investments): Cash + ETF + Stocks + Crypto = 100%."""
    default = dict(_TARGET_DEFAULTS)
    try:
        res = supabase.table('allocation_targets').select('*').eq('id', 1).execute()
        if res.data:
            row = res.data[0]
            out = {k: float(row.get(k) if row.get(k) is not None else v) for k, v in default.items()}
            if abs(sum(out[k] for k in _TARGET_PARTS) - 100) > 0.5:
                # legacy row whose parts don't add up — fall back to defaults for the split
                out.update({k: default[k] for k in _TARGET_PARTS})
            return out
        supabase.table('allocation_targets').insert({'id': 1, **default}).execute()
        return default
    except Exception:
        return default

def save_allocation_targets(targets: dict):
    try:
        supabase.table('allocation_targets').upsert(
            {'id': 1, **{k: float(targets[k]) for k in _TARGET_DEFAULTS}}
        ).execute()
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

def calc_loan_balance_at(at_date, principal: float, annual_rate: float,
                         monthly_payment: float, start_date,
                         loan_type: str = 'standard', monthly_borrow: float = 0.0,
                         study_end_date=None) -> float:
    """Loan balance at an arbitrary date — handles both standard and student loans.

    Student loan model (simplified):
      - During borrowing (no end_date set, or at_date <= end_date):
          balance = FV of annuity (monthly borrows accumulate with interest)
      - After borrowing stopped (at_date > end_date):
          balance = FV-at-end-date, then compounded with interest only (no repayment)
    """
    _at = pd.to_datetime(str(at_date)).date()
    r   = annual_rate / 100 / 12

    if loan_type == 'student':
        # Determine whether borrowing has stopped
        _end_date = None
        if study_end_date is not None and str(study_end_date) not in ('None', '', 'NaT'):
            try:
                _end_date = pd.to_datetime(str(study_end_date)).date()
            except Exception:
                _end_date = None

        if _end_date is None or _at <= _end_date:
            # Still borrowing: accumulate FV of annuity to at_date
            return _student_balance_at(monthly_borrow, r, start_date, _at)
        else:
            # Borrowing stopped: FV at end_date, then compound interest only
            balance_at_end = _student_balance_at(monthly_borrow, r, start_date, _end_date)
            n_after = max((_at.year - _end_date.year) * 12
                          + (_at.month - _end_date.month), 0)
            return balance_at_end * (1 + r) ** n_after

    # Standard loan
    _start  = pd.to_datetime(str(start_date)).date()
    months  = max((_at.year - _start.year) * 12 + (_at.month - _start.month), 0)
    if r == 0:
        return max(float(principal) - float(monthly_payment) * months, 0.0)
    factor  = (1 + r) ** months
    balance = float(principal) * factor - float(monthly_payment) * (factor - 1) / r
    return max(balance, 0.0)

def calc_loan_balance(principal: float, annual_rate: float, monthly_payment: float,
                      start_date, loan_type: str = 'standard',
                      monthly_borrow: float = 0.0, study_end_date=None,
                      repayment_years: float = 10.0) -> float:
    """Remaining loan balance today (see calc_loan_balance_at)."""
    _today = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
    return calc_loan_balance_at(_today, principal, annual_rate, monthly_payment,
                                start_date, loan_type=loan_type,
                                monthly_borrow=monthly_borrow,
                                study_end_date=study_end_date)

def _loan_current_monthly_payment(row) -> float:
    """The actual monthly cash outflow for this loan today.
    Student loans never require repayment (interest-only accumulation model)."""
    if row.get('Loan Type') == 'student':
        return 0.0  # no repayments — balance just grows
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
    # Login-specific styling: card around the form + filled submit button
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        [data-testid="stForm"] {
            background: #14161C !important;
            border: 1px solid #1F2229 !important;
            border-radius: 14px !important;
            padding: 1.8rem 1.8rem 1.2rem !important;
            box-shadow: 0 24px 60px rgba(0,0,0,0.45) !important;
        }
        [data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, #4D7CFE 0%, #6366f1 100%) !important;
            color: #0C0D10 !important;
            border: none !important;
            border-radius: 8px !important;
            font-family: 'Manrope', sans-serif !important;
            font-weight: 600 !important;
            font-size: 0.8rem !important;
            !important;
            !important;
            padding: 0.55rem 1rem !important;
            box-shadow: none !important;
            transition: opacity 0.15s !important;
        }
        [data-testid="stFormSubmitButton"] > button:hover,
        [data-testid="stFormSubmitButton"] > button:focus,
        [data-testid="stFormSubmitButton"] > button:active {
            opacity: 0.88 !important;
            color: #0C0D10 !important;
            outline: none !important;
            box-shadow: 0 0 24px rgba(77,124,254,0.35) !important;
        }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<div style='height:13vh;'></div>", unsafe_allow_html=True)
        st.markdown("""
        <div style='text-align:center; margin-bottom:1.8rem;'>
            <div style='width:54px; height:54px; margin:0 auto 1.1rem; border-radius:14px;
                        background:linear-gradient(135deg,#4D7CFE 0%,#6366f1 100%);
                        display:flex; align-items:center; justify-content:center;
                        font-family:"Manrope",sans-serif; font-size:1.55rem; font-weight:600;
                        color:#0C0D10; box-shadow:0 0 40px rgba(77,124,254,0.35);'>P</div>
            <div style='font-family:"Manrope",sans-serif; font-size:1.8rem; color:#EDEFF3; font-weight:500;'>PORTFOLIO</div>
            <div style='font-family:"Manrope",sans-serif; font-size:0.62rem; color:#8D93A0; margin-top:0.45rem;'>Wealth Dashboard</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            password = st.text_input("Password", type="password",
                                     label_visibility="collapsed", placeholder="Wachtwoord")
            submitted = st.form_submit_button("Inloggen", use_container_width=True)

        if submitted:
            if password == st.secrets["auth"]["password"]:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Onjuist wachtwoord")

        st.markdown(
            "<div style='text-align:center; font-family:Manrope; font-size:0.62rem; "
            "color:#8D93A0; margin-top:1.1rem;'>"
            "🔒 Beveiligde persoonlijke omgeving</div>",
            unsafe_allow_html=True
        )
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
<div style='display:flex; align-items:center; gap:10px; padding:0.2rem 0.2rem 1.2rem;'>
    <div style='width:32px; height:32px; border-radius:10px; background:#4D7CFE; display:flex; align-items:center; justify-content:center;'>
        <svg aria-hidden='true' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='#FFFFFF' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'><path d='M3 17l6-6 4 4 8-8'></path></svg>
    </div>
    <span style='font-weight:800; font-size:1.05rem; letter-spacing:-0.01em; color:#EDEFF3;'>Portfolio</span>
</div>
""", unsafe_allow_html=True)

# Page navigation (replaces the old tab bar; only the chosen page is rendered)
_PAGES = {
    "Overview":   ":material/dashboard:",
    "History":    ":material/schedule:",
    "Cashflow":   ":material/swap_horiz:",
    "Allocation": ":material/donut_large:",
    "Charts":     ":material/candlestick_chart:",
    "Planning":   ":material/insights:",
}
_page = st.sidebar.radio(
    "Navigation", list(_PAGES), key="nav", label_visibility="collapsed",
    format_func=lambda p: f"{_PAGES[p]} {p}",
)
if st.sidebar.button("Refresh prices", icon=":material/refresh:", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
st.sidebar.markdown("<div class='pf-side-label'>Manage</div>", unsafe_allow_html=True)

with st.sidebar.expander("Balances", expanded=False, icon=":material/account_balance_wallet:"):
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
with st.sidebar.expander("Add transaction", expanded=False, icon=":material/add_circle:"):
    trans_type = st.selectbox("Transaction Type", ['Buy', 'Sell', 'Dividend', 'Staking', 'Staking Reward', 'Transfer'], key="add_trans_type")
    transaction_date = st.date_input("Transaction Date", value=datetime.now(ZoneInfo("Europe/Amsterdam")).date(), key="add_date")

    if trans_type != 'Dividend':
        transaction_time_str = st.text_input("Transaction Time (HH:MM, 24-hour format)", value="12:00", placeholder="e.g., 09:30", key="add_time")
        try:
            transaction_time = datetime.strptime(transaction_time_str, "%H:%M").time()
        except ValueError:
            st.error("Please enter time in HH:MM format (e.g., 09:30).")
            transaction_time = time(12, 0)
    else:
        transaction_time = time(12, 0)

    ticker = st.text_input(
        "Ticker Symbol (e.g., VWRL.AS, META, MSFT, BTC-EUR, TAO-EUR)",
        key="add_ticker_input"
    ) if trans_type != '' else ''

    if trans_type in ['Buy', 'Sell', 'Staking']:
        _price_label = "Sell Price per Unit (EUR)" if trans_type == 'Sell' else "Price per Unit (EUR)"
        quantity = st.number_input("Quantity", min_value=0.0, value=0.0, step=1e-12, format="%.12f", key="add_quantity_input")
        purchase_price = st.number_input(_price_label, min_value=0.0, value=0.0, step=0.01, format="%.2f", key="add_price_input")
        # Show currency hint when ticker is a USD stock
        if ticker:
            _t_ccy = _ticker_currency(ticker.upper())
            if _t_ccy == 'USD':
                st.caption(
                    "💡 US aandeel — vul de prijs in **EUR** in (niet USD). "
                    "Kijk op je broker-bevestiging voor de EUR aankoopprijs, "
                    "of deel de USD-prijs door de wisselkoers op de aankoopdatum."
                )
            elif _t_ccy == 'GBP':
                st.caption("💡 Brits aandeel — vul de prijs in EUR in (omrekenen van GBP/pence).")
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
with st.sidebar.expander("Edit / delete transaction", expanded=False, icon=":material/edit:"):
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
# ─── Loans sidebar ───
with st.sidebar.expander("Loans / debt", expanded=False, icon=":material/credit_card:"):
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
        loan_monthly_borrow = st.number_input("Maandelijks leenbedrag (€)", min_value=0.0,
                                               step=50.0, format="%.2f", key="loan_mb_in")
        st.caption("💡 Bedrag verandert elk jaar? Voeg elke jaarschijf als aparte lening toe.")
        _use_end = st.checkbox("Einddatum instellen (stop met lenen)", key="loan_use_end")
        loan_study_end = (
            st.date_input("Einddatum lening", value=date(2028, 7, 1),
                          min_value=date(2000, 1, 1), max_value=date(2100, 12, 31),
                          key="loan_send_in")
            if _use_end else None
        )
        loan_repay_years = 10.0
        loan_principal   = 0.0
        loan_payment     = 0.0
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
        _today_sb = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
        for _, loan_row in st.session_state.loans.iterrows():
            remaining = calc_loan_balance(
                loan_row.get('Principal', 0.0), loan_row.get('Annual Rate', 0.0),
                loan_row.get('Monthly Payment', 0.0), loan_row.get('Start Date'),
                loan_type=str(loan_row.get('Loan Type', 'standard')),
                monthly_borrow=float(loan_row.get('Monthly Borrow', 0.0)),
                study_end_date=loan_row.get('Study End Date'),
                repayment_years=float(loan_row.get('Repayment Years', 10.0)),
            )
            _is_st = str(loan_row.get('Loan Type')) == 'student'
            if _is_st:
                _mb  = float(loan_row.get('Monthly Borrow', 0.0))
                _sed = loan_row.get('Study End Date')
                _has_end = _sed and str(_sed) not in ('None', '', 'NaT')
                _still_borrowing = (not _has_end
                                    or _today_sb <= pd.to_datetime(str(_sed)).date())
                _status_tag = "📈 Aan het lenen" if _still_borrowing else "⏸ Gestopt met lenen"
                _detail = f"€{_mb:,.0f}/mo · {_status_tag} · {loan_row['Annual Rate']:.2f}% rente"
                _lbl    = "opgebouwd"
            else:
                _pmt   = float(loan_row.get('Monthly Payment', 0.0))
                _detail = f"€{_pmt:,.0f}/mo aflossing · {loan_row['Annual Rate']:.2f}% rente"
                _lbl    = "resterend"
            st.markdown(
                f"**{loan_row['Name']}** — €{remaining:,.0f} {_lbl}  \n"
                f"<span style='font-size:0.78rem; color:#8D93A0;'>{_detail}</span>",
                unsafe_allow_html=True
            )
            if st.button("Verwijderen", key=f"loan_del_{loan_row['id']}"):
                if delete_loan_db(int(loan_row['id'])):
                    st.session_state.loans = load_loans()
                    st.rerun()

# -------------------------
# Crypto price sources
# CoinGecko (may need key) → Kraken (free, no key) → Yahoo Finance
# -------------------------
COINGECKO_IDS = {
    'TAO-EUR': 'bittensor',
    'TAO':     'bittensor',
}

# Kraken public API pairs (free, no API key needed)
KRAKEN_PAIRS = {
    'TAO-EUR': 'TAOEUR',
    'TAO':     'TAOEUR',
    'BTC-EUR': 'XBTEUR',
    'ETH-EUR': 'ETHEUR',
    'SOL-EUR': 'SOLEUR',
    'BTC':     'XBTEUR',
    'ETH':     'ETHEUR',
    'SOL':     'SOLEUR',
}

@st.cache_data(ttl=300)
def _kraken_price(pair: str) -> float:
    """Fetch last trade price from Kraken public API (no key needed)."""
    try:
        import requests
        r = requests.get(
            f"https://api.kraken.com/0/public/Ticker?pair={pair}",
            timeout=10
        )
        if r.status_code == 200:
            result = r.json().get('result', {})
            if result and not r.json().get('error'):
                data = next(iter(result.values()))
                return float(data['c'][0])  # last trade closed price
    except Exception:
        pass
    return 0.0

@st.cache_data(ttl=3600)
def _kraken_history(pair: str, period: str = '1y') -> pd.DataFrame:
    """Fetch OHLC history from Kraken public API."""
    _days = {'6mo': 180, '1y': 365, '2y': 730, '5y': 1825, 'max': 1825}
    days = _days.get(period, 365)
    try:
        import requests, time as _time
        since = int(_time.time()) - days * 86400
        r = requests.get(
            f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440&since={since}",
            timeout=15
        )
        if r.status_code == 200 and not r.json().get('error'):
            result = r.json().get('result', {})
            ohlc = result.get(pair, result.get(next(
                (k for k in result if k != 'last'), None), []))
            if ohlc:
                df = pd.DataFrame(ohlc, columns=[
                    'time', 'open', 'high', 'low', 'close', 'vwap', 'volume', 'count'])
                df['Date'] = pd.to_datetime(df['time'], unit='s').dt.date
                df['Close'] = df['close'].astype(float)
                return df[['Date', 'Close']]
    except Exception:
        pass
    return pd.DataFrame()

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

# European cross-listings → US ticker fallback
# When the EU-listed ticker returns no data, fall back to US ticker + USD→EUR conversion.
_EU_FALLBACK = {
    # Meta
    'FB2A': 'META', 'FB2A.DE': 'META', 'FB2A.AS': 'META', 'FB2A.F': 'META',
    # Microsoft
    'MSF.DE': 'MSFT', 'MSF.AS': 'MSFT', 'MSFT.DE': 'MSFT', 'MSFT.AS': 'MSFT',
    # Apple
    'APC.DE': 'AAPL', 'APC.AS': 'AAPL', 'AAPL.DE': 'AAPL', 'AAPL.AS': 'AAPL',
    # Amazon
    'AMZ.DE': 'AMZN', 'AMZ.AS': 'AMZN', 'AMZN.DE': 'AMZN', 'AMZN.AS': 'AMZN',
    # Alphabet
    'ABEC.DE': 'GOOGL', 'ABEC.AS': 'GOOGL', 'GOOGL.DE': 'GOOGL', 'GOOG.DE': 'GOOGL',
    # NVIDIA
    'NVDA.DE': 'NVDA', 'NVDA.AS': 'NVDA', 'NVD.DE': 'NVDA',
    # Tesla
    'TL0.DE': 'TSLA', 'TL0.AS': 'TSLA', 'TSLA.DE': 'TSLA', 'TSLA.AS': 'TSLA',
    # Netflix
    'NFC.DE': 'NFLX', 'NFLX.DE': 'NFLX',
}

# -------------------------
# Price fetching functions
# -------------------------
@st.cache_data(ttl=300)
def get_price(ticker):
    # 1. CoinGecko (may be rate-limited without API key)
    if ticker in COINGECKO_IDS:
        price = _coingecko_price(COINGECKO_IDS[ticker])
        if price > 0:
            return price

    # 2. Kraken public API (reliable, no key needed)
    if ticker in KRAKEN_PAIRS:
        price = _kraken_price(KRAKEN_PAIRS[ticker])
        if price > 0:
            return price

    # 3. Yahoo Finance — try EU ticker + common variants
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
    # For EU cross-listings: also try .F (Frankfurt) and .DE (XETRA) variants
    if ticker.endswith('.DE'):
        tickers_to_try.append(ticker[:-3] + '.F')
    elif ticker.endswith('.F'):
        tickers_to_try.append(ticker[:-2] + '.DE')

    for t in tickers_to_try:
        try:
            data = yf.Ticker(t).history(period='1d', interval='1d')['Close']
            if not data.empty:
                return _price_to_eur(float(data.iloc[-1]), t)
        except Exception:
            continue

    # 4. EU cross-listing fallback → US ticker with USD→EUR conversion
    if ticker in _EU_FALLBACK:
        us = _EU_FALLBACK[ticker]
        try:
            data = yf.Ticker(us).history(period='1d', interval='1d')['Close']
            if not data.empty:
                return _price_to_eur(float(data.iloc[-1]), us)
        except Exception:
            pass

    return 0.0

@st.cache_data(ttl=3600)
def get_historical_data(ticker, period='1y'):
    # 1. CoinGecko (may be rate-limited without API key)
    if ticker in COINGECKO_IDS:
        df = _coingecko_history(COINGECKO_IDS[ticker], period=period)
        if not df.empty:
            return df

    # 2. Kraken (reliable free history source)
    if ticker in KRAKEN_PAIRS:
        df = _kraken_history(KRAKEN_PAIRS[ticker], period=period)
        if not df.empty:
            return df

    tickers_to_try = [ticker]
    if ticker in ['BTC', 'ETH', 'SOL', 'TAO']:
        tickers_to_try.extend([f"{ticker}-EUR", f"{ticker}-USD"])
    elif '-EUR' in ticker:
        tickers_to_try.append(ticker.replace('-EUR', '-USD'))
    if ticker.endswith('.DE'):
        tickers_to_try.append(ticker[:-3] + '.F')
    elif ticker.endswith('.F'):
        tickers_to_try.append(ticker[:-2] + '.DE')
    # EU fallback: also try the US ticker
    if ticker in _EU_FALLBACK:
        tickers_to_try.append(_EU_FALLBACK[ticker])

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
                rate = _fx_to_eur('GBP')
                data['Close'] = data['Close'] / 100 * rate
            else:  # USD or CHF etc.
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


@st.cache_data(ttl=300)
def _kraken_recent_closes(pair: str) -> pd.Series:
    """Last few daily candles from Kraken (00:00 UTC). The last one is today's, still moving."""
    try:
        import requests, time as _time
        r = requests.get(
            f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval=1440"
            f"&since={int(_time.time()) - 5 * 86400}",
            timeout=10
        )
        if r.status_code == 200 and not r.json().get('error'):
            result = r.json().get('result', {})
            ohlc = next((v for k, v in result.items() if k != 'last'), [])
            if ohlc:
                return pd.Series([float(c[4]) for c in ohlc],
                                 index=pd.to_datetime([c[0] for c in ohlc], unit='s'))
    except Exception:
        pass
    return pd.Series(dtype=float)


@st.cache_data(ttl=300)
def get_recent_closes(ticker) -> pd.Series:
    """Daily closes of the last few days (the last one is today's, still moving).

    Crypto: Kraken daily candles (00:00 UTC). Stocks/ETFs: Yahoo daily closes, with the
    same ticker fallbacks as get_price. Empty Series if nothing is found.
    """
    if ticker in KRAKEN_PAIRS:
        closes = _kraken_recent_closes(KRAKEN_PAIRS[ticker])
        if closes.dropna().size >= 2:
            return closes

    tickers_to_try = [ticker]
    if ticker in ['VUSA', 'VUSA.AS']:
        tickers_to_try.extend(['VUSA.AS', 'VOO'])
    elif ticker in ['VWRL', 'VWRL.AS']:
        tickers_to_try.append('VWRL.AS')
    elif ticker in ['QDVE', 'QDVE.DE']:
        tickers_to_try.append('QDVE.DE')
    elif ticker in ['BTC', 'ETH', 'SOL', 'TAO']:
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
            closes = yf.Ticker(t).history(period='7d', interval='1d')['Close']
            if closes.dropna().size >= 2:
                return closes
        except Exception:
            continue
    return pd.Series(dtype=float)


def get_daily_change(ticker):
    """Price change since the previous close, as (fraction, date of the latest price).

    Crypto: today (UTC) vs. yesterday's 00:00 UTC close. Stocks/ETFs: latest trading
    day vs. the one before (on weekends that is Friday vs. Thursday). Both prices come
    from the same source and currency, so the % is not affected by EUR conversion.
    Returns (None, None) if no history is found.
    """
    return change_from_closes(get_recent_closes(ticker))

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
    for idx, row in trans.iterrows():
        ticker = normalize_ticker(row['Ticker'])
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
            # Buy fee is part of the cost basis only — it shows up once,
            # as a lower unrealized P/L (not also as a realized expense).
            fee_eur = fee_amount if fee_unit == 'EUR' else 0.0
            c += quantity * purchase_price + fee_eur
            s += quantity * purchase_price
            q += quantity
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
                # Cash expense — hits realized once, cost basis untouched
                realized -= fee_amount
            elif fee_unit == 'Asset':
                # Fee paid in tokens: holdings shrink, cost basis stays.
                # The loss shows up once, as a smaller position value.
                q -= fee_amount
        aggregated[ticker]['Quantity'] = max(q, 0.0)
        aggregated[ticker]['Cost Basis'] = max(c, 0.0)
        aggregated[ticker]['Total Share Cost'] = max(s, 0.0)

    portfolio_list = []
    unrealized_total = 0.0
    total_invested = 0.0
    _zero_price_tickers = []
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
            if current_price == 0.0:
                _zero_price_tickers.append(ticker)
    portfolio_df = pd.DataFrame(portfolio_list)
    total_profit = realized + unrealized_total
    profit_percentage = (total_profit / total_invested * 100) if total_invested > 0 else 0.0
    if _zero_price_tickers:
        st.warning(
            f"Geen prijs gevonden voor: {', '.join(_zero_price_tickers)}. "
            f"Waarde en P/L van deze posities staan tijdelijk op €0 — "
            f"controleer de ticker of probeer Refresh."
        )
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

# ─── Money-weighted return (XIRR) of the investments ───
_today_local      = datetime.now(ZoneInfo("Europe/Amsterdam")).date()
_invest_value_now = float(portfolio_df['Value'].sum()) if not portfolio_df.empty else 0.0
_inv_flows        = investment_cashflows(st.session_state.transactions)
_xirr             = xirr(_inv_flows + [(_today_local, _invest_value_now)]) if _inv_flows else None
_xirr_pct         = _xirr * 100 if _xirr is not None else None
_today_label = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%A %-d %B")
_PAGE_SUBTITLES = {
    "Overview":   "Stocks and ETFs at their latest close, crypto since 00:00 UTC",
    "History":    "How your portfolio value developed",
    "Cashflow":   "Monthly income and expenses",
    "Allocation": "How your money is spread, and your targets",
    "Charts":     "Price history per asset",
    "Planning":   "Goals, deposits and projections",
}
st.markdown(
    f"<h1>{_page}</h1><div class='pf-sub'>{_today_label} · {_PAGE_SUBTITLES.get(_page, '')}</div>",
    unsafe_allow_html=True,
)

# Category colors (used by Overview dashboard and Allocation tab)
_CAT_COLORS = {'ETF': '#4D7CFE', 'Stock': '#22C3B5', 'Crypto': '#F5A623', 'Cash & Banks': '#5B6170'}

# Shared Plotly chart layout (used by History and Charts tabs)
_CHART_LAYOUT = dict(
    plot_bgcolor="#0C0D10",
    paper_bgcolor="#0C0D10",
    font=dict(family="Manrope", color="#8D93A0", size=11),
    xaxis=dict(gridcolor="#1F2229", linecolor="#1F2229", tickfont=dict(color="#8D93A0"), zeroline=False),
    yaxis=dict(gridcolor="#1F2229", linecolor="#1F2229", tickfont=dict(color="#8D93A0"), zeroline=False),
    margin=dict(l=10, r=10, t=100, b=10),
    hovermode="x unified",
    hoverlabel=dict(bgcolor="#14161C", bordercolor="#1F2229", font=dict(family="Manrope", color="#EDEFF3", size=12)),
    legend=dict(orientation="h", yanchor="bottom", y=1.06, xanchor="left", x=0,
                font=dict(family="Manrope", color="#A4A9B4", size=11), bgcolor="rgba(0,0,0,0)", borderwidth=0),
)

# -------------------------
# Navigation tabs
# -------------------------
def _card(title: str, body_html: str, accent: str = "#4D7CFE") -> str:
    return (
        f"<div style='background:#14161C; border:1px solid #1F2229; "
        f"border-radius:16px; padding:1rem 1.2rem; height:100%;'>"
        f"<div style='font-family:Manrope; font-size:0.78rem; "
        f"color:#8D93A0; margin-bottom:0.45rem;'>{title}</div>{body_html}</div>"
    )


@st.cache_data(ttl=6 * 3600)
def _benchmark_prices(ticker: str) -> pd.DataFrame:
    return get_historical_data(ticker, period='max')


def _benchmark_diff():
    """Your investments now minus the same euros put into a world ETF (VWCE) on the same dates."""
    b_flows = investment_cashflows(st.session_state.transactions, include_dividends=False)
    b_val = benchmark_value(b_flows, _benchmark_prices('VWCE.DE')) if b_flows else None
    return (_invest_value_now - b_val) if b_val is not None else None


def _net_worth_figure(hist: pd.DataFrame) -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=hist['date'], y=hist['total_value'], mode="lines",
        line=dict(color="#4D7CFE", width=2.5, shape="spline", smoothing=0.6),
        fill="tozeroy", fillcolor="rgba(77,124,254,0.14)",
        hovertemplate="%{x|%d %b %Y}<br><b>€%{y:,.0f}</b><extra></extra>",
    ))
    lo, hi = float(hist['total_value'].min()), float(hist['total_value'].max())
    pad = (hi - lo) * 0.15 or hi * 0.05 or 1
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Manrope", color="#8D93A0", size=11),
        xaxis=dict(showgrid=False, linecolor="#1F2229", zeroline=False, tickformat="%b"),
        yaxis=dict(gridcolor="#1F2229", zeroline=False, side="right", tickprefix="€",
                   tickformat=",.0f", range=[lo - pad, hi + pad]),
        margin=dict(l=0, r=0, t=6, b=0), height=280, showlegend=False, hovermode="x",
        hoverlabel=dict(bgcolor="#14161C", bordercolor="#262A33",
                        font=dict(family="Manrope", color="#EDEFF3", size=12)),
    )
    return fig


def _today_map_figure(df: pd.DataFrame) -> go.Figure:
    """Treemap: tile size = position value, tile color = today's move."""
    labels = df['Ticker'].tolist()
    text = [pct(c) if c is not None and not pd.isna(c) else "—" for c in df['Change']]
    moves = [eur(m, 2, sign=True) if not pd.isna(m) else "" for m in df['Move']]
    fig = go.Figure(go.Treemap(
        labels=labels, parents=[""] * len(labels), values=df['Value'].tolist(),
        marker=dict(colors=[heat_color(c) for c in df['Change']], line=dict(color="#14161C", width=3),
                    pad=dict(t=0, l=0, r=0, b=0)),
        customdata=list(zip(text, moves)),
        texttemplate="<b>%{label}</b><br>%{customdata[0]}",
        textfont=dict(family="Manrope", color="#FFFFFF", size=14),
        textposition="top left",
        hovertemplate="<b>%{label}</b><br>%{customdata[0]} · %{customdata[1]}<br>€%{value:,.0f}<extra></extra>",
        tiling=dict(packing="squarify", pad=3), root=dict(color="rgba(0,0,0,0)"),
        sort=True,
    ))
    fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=0, b=0), height=300,
                      hoverlabel=dict(bgcolor="#14161C", bordercolor="#262A33",
                                      font=dict(family="Manrope", color="#EDEFF3", size=12)))
    return fig


def render_overview_top(portfolio_df: pd.DataFrame):
    """Stat cards, net worth chart, today's map and the holdings table."""
    cash_total = _cash + _credit + _cic
    closes, changes = {}, {}
    if not portfolio_df.empty:
        for t in portfolio_df['Ticker']:
            s_ = get_recent_closes(t)
            closes[t] = s_
            changes[t] = change_from_closes(s_)[0]
    moves, today_move, today_change = (daily_moves(portfolio_df[['Ticker', 'Value']], changes)
                                       if not portfolio_df.empty else (pd.DataFrame(), 0.0, None))
    n_up = int((moves['Move'] > 0).sum()) if not moves.empty else 0
    n_down = int((moves['Move'] < 0).sum()) if not moves.empty else 0

    # ── Stat cards ──
    nw_sub = f"invested {eur(_invest_value_now)} · cash {eur(cash_total)}"
    if _total_debt > 0:
        nw_sub += f" · debt {eur(_total_debt)}"
    today_cls = "pf-up" if today_move > 0 else "pf-down" if today_move < 0 else ""
    today_sub = (f"{pct(today_change)} · {n_up} up, {n_down} down" if today_change is not None
                 else "no price history right now")
    invested = float(portfolio_df['Cost Basis'].sum()) if not portfolio_df.empty else 0.0
    bench = _benchmark_diff() if not portfolio_df.empty else None
    xirr_sub = (f"{eur(bench, sign=True)} vs world ETF" if bench is not None
                else "money-weighted (XIRR)")
    st.markdown(stat_row([
        stat_card("Net worth", eur(_net_worth), nw_sub),
        stat_card("Today", eur(today_move, 2, sign=True), today_sub, today_cls),
        stat_card("Total profit", eur(total_profit, sign=True),
                  f"{profit_percentage:+.1f}% on {eur(invested)}"),
        stat_card("Return per year", f"{_xirr_pct:+.1f}%" if _xirr_pct is not None else "—", xirr_sub),
    ]), unsafe_allow_html=True)

    # ── Net worth chart + today's map ──
    left, right = st.columns([1.75, 1], gap="small")
    with left:
        with st.container(border=True, key="pf-chart"):
            h1c, h2c = st.columns([1, 1])
            h1c.markdown("<div class='pf-card-title'><h2>Net worth</h2></div>", unsafe_allow_html=True)
            rng = h2c.segmented_control("Range", ["1M", "3M", "6M", "1Y", "All"], default="6M",
                                        key="nw_range", label_visibility="collapsed")
            hist = load_portfolio_value_history()
            if not hist.empty:
                hist = hist.copy()
                hist['date'] = pd.to_datetime(hist['date'])
                days = {"1M": 31, "3M": 92, "6M": 183, "1Y": 366}.get(rng or "All")
                if days:
                    hist = hist[hist['date'] >= pd.Timestamp(_today_local) - pd.Timedelta(days=days)]
            if len(hist) >= 2:
                st.plotly_chart(_net_worth_figure(hist), use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.markdown("<div class='pf-muted' style='height:280px; display:flex; align-items:center; "
                            "justify-content:center;'>The chart appears after a few days of history.</div>",
                            unsafe_allow_html=True)
    with right:
        with st.container(border=True, key="pf-map"):
            st.markdown("<div class='pf-card-title'><h2>Today's map</h2>"
                        "<span class='pf-hint'>size = position · color = move</span></div>",
                        unsafe_allow_html=True)
            if not moves.empty:
                st.plotly_chart(_today_map_figure(moves), use_container_width=True,
                                config={"displayModeBar": False})
            else:
                st.markdown("<div class='pf-muted'>No positions yet.</div>", unsafe_allow_html=True)

    # ── Holdings table with 5-day sparklines ──
    if portfolio_df.empty:
        return
    inv_total = float(portfolio_df['Value'].sum()) or 1.0
    rows = []
    for _, r in portfolio_df.sort_values('Value', ascending=False).iterrows():
        cb = float(r['Cost Basis'])
        rows.append(dict(
            ticker=r['Ticker'], category=get_category(r['Ticker']),
            closes=closes.get(r['Ticker'], pd.Series(dtype=float)).dropna().tail(6).tolist(),
            change=changes.get(r['Ticker']), value=float(r['Value']),
            weight=float(r['Value']) / inv_total,
            profit=float(r['Unrealized Profit/Loss']),
            profit_pct=(float(r['Unrealized Profit/Loss']) / cb) if cb > 0 else None,
        ))
    hint = f"{len(rows)} positions · {eur(inv_total)}"
    st.markdown(holdings_table(rows, "Holdings", hint), unsafe_allow_html=True)


def render_year_start_check():
    """Box 3 base on the next 1 January vs. toeslagen asset limits and the Box 3 allowance."""
    peil = next_peildatum(_today_local)
    thr_year, thr = thresholds_for(peil.year)
    loans = st.session_state.get('loans', pd.DataFrame())
    debt_peil = 0.0
    if not loans.empty:
        for _, r in loans.iterrows():
            try:
                debt_peil += calc_loan_balance_at(
                    peil, float(r.get('Principal', 0.0)), float(r.get('Annual Rate', 0.0)),
                    float(r.get('Monthly Payment', 0.0)), r.get('Start Date'),
                    loan_type=str(r.get('Loan Type', 'standard')),
                    monthly_borrow=float(r.get('Monthly Borrow', 0.0)),
                    study_end_date=r.get('Study End Date'))
            except Exception:
                continue
    base = box3_base(_total_value, debt_peil, thr['debt_threshold'])

    # Monthly toeslag amounts from the Cashflow tab (matched on category name)
    cf = st.session_state.get('cashflow', pd.DataFrame())
    def _monthly(word):
        if cf is None or cf.empty:
            return 0.0
        m = cf['Category'].astype(str).str.lower().str.contains(word)
        return float(cf.loc[m & (cf['Amount'] > 0), 'Amount'].sum())

    rows = [
        ("Huurtoeslag", thr['huurtoeslag'], _monthly('huurtoeslag')),
        ("Zorgtoeslag", thr['zorgtoeslag'], _monthly('zorgtoeslag')),
        ("Box 3 tax-free allowance", thr['box3_free'], None),
    ]
    days = (peil - _today_local).days
    worst = min(lim - base for _, lim, _m in rows)
    accent = "#FF6B6B" if worst < 0 else ("#f5a524" if worst < 5000 else "#3DDC84")

    with st.expander(f"1 January check — {peil:%d %b %Y} ({days} days)", expanded=worst < 5000):
        yr_note = "" if thr_year == peil.year else f" Limits shown are {thr_year}'s; {peil.year}'s aren't in the app yet."
        st.markdown(
            "<p style='font-family:Manrope; font-size:0.78rem; color:#A4A9B4;'>"
            f"Your assets on 1 January decide toeslagen and Box 3 for the whole year. "
            f"Assets today <b style='color:#EDEFF3;'>€{_total_value:,.0f}</b> − debts above the "
            f"€{thr['debt_threshold']:,.0f} threshold (loans on {peil:%d-%m-%Y}: €{debt_peil:,.0f}) "
            f"= <b style='color:#EDEFF3;'>€{base:,.0f}</b>.{yr_note}</p>",
            unsafe_allow_html=True)
        cols = st.columns(3)
        for col, (label, lim, monthly) in zip(cols, rows):
            room = lim - base
            if room >= 0:
                val, colr = f"€{room:,.0f} room", ("#f5a524" if room < 5000 else "#3DDC84")
            else:
                val, colr = f"€{-room:,.0f} over", "#FF6B6B"
            sub = f"Limit €{lim:,.0f}"
            if monthly:
                sub += f" · at stake ≈ €{monthly * 12:,.0f}/yr"
            col.markdown(_card(label,
                f"<div style='font-family:Manrope; font-size:1.3rem; color:{colr};'>{val}</div>"
                f"<div style='font-family:Manrope; font-size:0.7rem; color:#A4A9B4;'>{sub}</div>", colr),
                unsafe_allow_html=True)
        st.markdown(
            "<p style='font-family:Manrope; font-size:0.68rem; color:#8D93A0; margin-top:0.6rem;'>"
            "Estimate using today's prices, single-person limits, and every account you track. "
            "Confirm with the proefberekening on toeslagen.nl. Update the limits yearly in finance_utils.py.</p>",
            unsafe_allow_html=True)



# -------------------------
# Tab: Cashflow
# -------------------------
if _page == "Cashflow":

    _cf = st.session_state.cashflow.copy()
    if _cf.empty:
        _cf = pd.DataFrame(columns=['id'] + CF_DISPLAY_COLS)

    # ── Summary ──
    total_income   = float(_cf.loc[_cf['Amount'] > 0, 'Amount'].sum()) if not _cf.empty else 0.0
    total_expenses = float(-_cf.loc[_cf['Amount'] < 0, 'Amount'].sum()) if not _cf.empty else 0.0
    net_cashflow   = total_income - total_expenses
    _net_col = "#3DDC84" if net_cashflow >= 0 else "#FF6B6B"
    _sc = st.columns(3)
    _sc[0].markdown(_card("Income / month",
        f"<div style='font-family:Manrope; font-size:1.4rem; color:#3DDC84;'>€{total_income:,.2f}</div>", "#3DDC84"),
        unsafe_allow_html=True)
    _sc[1].markdown(_card("Expenses / month",
        f"<div style='font-family:Manrope; font-size:1.4rem; color:#FF6B6B;'>€{total_expenses:,.2f}</div>", "#FF6B6B"),
        unsafe_allow_html=True)
    _sc[2].markdown(_card("Left over / month",
        f"<div style='font-family:Manrope; font-size:1.4rem; color:{_net_col};'>{'−' if net_cashflow < 0 else ''}€{abs(net_cashflow):,.2f}</div>", "#4D7CFE"),
        unsafe_allow_html=True)

    st.markdown("<div style='height:1rem;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-family:Manrope; font-size:0.8rem; color:#A4A9B4;'>"
        "Edit directly in the table: click a cell to change it, use the <b>+</b> row at the bottom to add, "
        "select a row and press <b>Delete</b> (or the bin icon) to remove. Amounts are per month, always positive "
        "— the Type decides income or expense. Nothing is saved until you press <b>Save changes</b>.</p>",
        unsafe_allow_html=True)

    _view = _cf[['id'] + CF_DISPLAY_COLS].copy()
    _view['Amount'] = _view['Amount'].abs()
    _view['Notes'] = _view['Notes'].fillna('')
    _view = _view.sort_values(['Type', 'Amount'], ascending=[False, False]).reset_index(drop=True)

    _edited = st.data_editor(
        _view,
        key=f"cashflow_editor_{st.session_state.get('cf_editor_ver', 0)}",
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_order=['Type', 'Category', 'Amount', 'Notes'],
        column_config={
            'id': None,
            'Type': st.column_config.SelectboxColumn("Type", options=['Income', 'Expense'],
                                                     required=True, default='Expense', width="small"),
            'Category': st.column_config.TextColumn("Name", required=True, help="e.g. Huur, Boodschappen, DUO"),
            'Amount': st.column_config.NumberColumn("€ / month", min_value=0.0, step=0.01, format="€%.2f",
                                                    required=True),
            'Notes': st.column_config.TextColumn("Notes"),
        },
    )

    _ins, _upd, _dels, _errs = diff_cashflow(_view, _edited)
    _n_changes = len(_ins) + len(_upd) + len(_dels)
    for _e in _errs:
        st.warning(_e)
    _bc1, _bc2 = st.columns([1, 4])
    with _bc1:
        _save = st.button(f"Save changes ({_n_changes})" if _n_changes else "Save changes",
                          key="cashflow_save", disabled=_n_changes == 0, type="primary")
    with _bc2:
        if _n_changes:
            st.markdown(
                f"<p style='font-family:Manrope; font-size:0.75rem; color:#f5a524; padding-top:0.55rem;'>"
                f"Unsaved: {len(_ins)} new · {len(_upd)} changed · {len(_dels)} deleted</p>",
                unsafe_allow_html=True)
    if _save:
        _ok = all(add_cashflow_db(r['category'], r['type'], r['amount'], r['notes']) for r in _ins)
        _ok &= all(update_cashflow_db(i, r['category'], r['type'], r['amount'], r['notes']) for i, r in _upd)
        _ok &= all(delete_cashflow_db(i) for i in _dels)
        st.session_state.cashflow = load_cashflow()
        st.session_state.cf_editor_ver = st.session_state.get('cf_editor_ver', 0) + 1  # fresh table
        if _ok:
            st.toast("Cashflow saved ✓")
        st.rerun()

# -------------------------
# Tab: Historical Portfolio Value
# -------------------------
if _page == "History":
    st.caption("Logs total portfolio value daily (assets + broker cash + bank balances), compared with a "
               "no-investment baseline: what your wealth would be if you had kept everything in cash.")

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
        dividends = trans_df.loc[trans_df["Type"] == "Dividend", "Income"].sum() if "Income" in trans_df.columns else 0.0
    else:
        dividends = 0.0

    # Baseline: what you'd have if the invested money had stayed cash.
    # Buy fees are already inside the cost basis, so no separate fee term.
    no_investment_total = total_invested + bank_total + broker_cash - dividends

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

        fig_total = go.Figure()
        fig_total.add_trace(go.Scatter(
            x=plot_df["Date"], y=plot_df["Total Portfolio Value (€)"],
            mode="lines", name="Portfolio Value",
            line=dict(color="#4D7CFE", width=2.5),
            hovertemplate="€%{y:,.2f}<extra></extra>"
        ))
        fig_total.add_trace(go.Scatter(
            x=plot_df["Date"], y=plot_df["No Investment (€)"],
            mode="lines", name="No Investment",
            line=dict(color="#A4A9B4", width=2, dash="dot"),
            hovertemplate="€%{y:,.2f}<extra></extra>"
        ))
        fig_total.update_layout(
            title=dict(text="Portfolio Value vs. No Investment", font=dict(family="Manrope", color="#EDEFF3", size=15), x=0),
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

        _delta_col = "#3DDC84" if delta_vs_baseline >= 0 else "#FF6B6B"
        _delta_sign = "+" if delta_vs_baseline >= 0 else ""
        st.markdown(
            f"<div style='font-family:Manrope; font-size:0.62rem; color:#8D93A0; margin:0.75rem 0 0.25rem;'>vs. No Investment &nbsp;"
            f"<span style='color:{_delta_col}; font-family:\"Manrope\"; font-size:1.2rem; font-weight:400; letter-spacing:0.03em;'>{_delta_sign}€{delta_vs_baseline:,.2f} ({pct_vs_baseline:.2f}%)</span></div>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("<h3 style='margin-bottom:0.5rem;'><span class='material-symbols-outlined' style='font-size:16px; color:#8D93A0;'>savings</span> Compare With Bank Savings</h3>", unsafe_allow_html=True)

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
            <div style="background:#14161C; border:1px solid #1F2229; border-radius:8px; padding:1.2rem 1.4rem;">
                <div style="font-family:Manrope; font-size:0.78rem; color:#8D93A0; margin-bottom:0.4rem;">
                    At {bank_interest_rate:.2f}% annual interest
                </div>
                <div style="font-family:'Manrope'; font-size:1.6rem; color:#3DDC84; letter-spacing:0.03em; margin-bottom:0.2rem;">
                    €{total_with_interest:,.2f}
                </div>
                <div style="font-family:Manrope; font-size:0.78rem; color:#8D93A0;">Interest gain: +€{interest_gain:,.2f}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

# -------------------------
# Tab: Portfolio Overview
# -------------------------
if _page == "Overview":
    portfolio_df, realized, unrealized, total_profit, profit_percentage = compute_portfolio()
    render_overview_top(portfolio_df)
    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
    render_year_start_check()

    if not portfolio_df.empty:
        portfolio_df['Category'] = portfolio_df['Ticker'].apply(get_category)
        with st.expander("Position details", icon=":material/table_rows:"):
            # ═══ Positions table ═══
            display_df = portfolio_df.copy()

            # Per-position % return and portfolio weight
            _inv_total_w = display_df['Value'].sum()
            display_df['P/L %'] = display_df.apply(
                lambda r: (r['Unrealized Profit/Loss'] / r['Cost Basis'] * 100)
                if r['Cost Basis'] > 0 else 0.0, axis=1)
            display_df['Weight %'] = (
                display_df['Value'] / _inv_total_w * 100 if _inv_total_w > 0 else 0.0
            )

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
                portfolio_df_display[["Asset","Type","Qty","GIP(€)","Invested(€)","Price(€)","Value(€)","Unrealized P/L (€)","P/L %","Weight %"]].style.format({
                    "Qty": "{:.8f}",
                    "GIP(€)": "€{:.4f}",
                    "Invested(€)": "€{:.2f}",
                    "Price(€)": "€{:.2f}",
                    "Value(€)": "€{:.2f}",
                    "Unrealized P/L (€)": "€{:.2f}",
                    "P/L %": "{:+.1f}%",
                    "Weight %": "{:.1f}%"
                }).map(
                    lambda v: 'color:#3DDC84' if isinstance(v, (int, float)) and v > 0
                    else ('color:#FF6B6B' if isinstance(v, (int, float)) and v < 0 else ''),
                    subset=['P/L %']
                ),
                use_container_width=True
            )

        with st.expander("Breakdown of totals", icon=":material/calculate:"):
            # ═══ Key metrics ═══
            st.markdown("<div style='height:0.6rem'></div>", unsafe_allow_html=True)
            _view = st.radio("View", ["Total Portfolio", "Investments Only"],
                             horizontal=True, key="overview_view", label_visibility="collapsed")

            investments_value = portfolio_df["Value"].sum()
            total_invested    = portfolio_df["Cost Basis"].sum()
            total_bank = (
                st.session_state.balances.get("credit_mutuel_balance", 0.0)
                + st.session_state.balances.get("cic_balance", 0.0)
            )
            cash_broker = st.session_state.balances.get("cash_balance", 0.0)
            total_value = investments_value + cash_broker + total_bank

            if _view == "Investments Only":
                # P&L for investments only (excl. cash)
                inv_pct = (total_profit / total_invested * 100) if total_invested > 0 else 0.0
                r1c1, r1c2, r1c3 = st.columns(3)
                r1c1.metric("Total Invested (cost basis)", f"€{total_invested:,.2f}")
                r1c2.metric("Investments Value", f"€{investments_value:,.2f}")
                r1c3.metric("Return on Investments", f"{inv_pct:.2f}%", delta_color="normal")
                r2c1, r2c2, r2c3 = st.columns(3)
                r2c1.metric("Realized Income/Expenses", f"€{realized:,.2f}", delta_color="normal")
                r2c2.metric("Unrealized Profit/Loss", f"€{unrealized:,.2f}", delta_color="normal")
                r2c3.metric("Total Profit", f"€{total_profit:,.2f}", delta_color="normal")
            else:
                r1c1, r1c2, r1c3, r1c4 = st.columns(4)
                r1c1.metric("Total Invested", f"€{total_invested:,.2f}")
                r1c2.metric("Total Portfolio Value", f"€{total_value:,.2f}")
                r1c3.metric("Broker Cash", f"€{cash_broker:,.2f}")
                r1c4.metric("Total Bank Balance", f"€{total_bank:,.2f}")
                r2c1, r2c2, r2c3, r2c4 = st.columns(4)
                r2c1.metric("Realized Income/Expenses", f"€{realized:,.2f}", delta_color="normal")
                r2c2.metric("Unrealized Profit/Loss", f"€{unrealized:,.2f}", delta_color="normal")
                r2c3.metric("Total Profit", f"€{total_profit:,.2f}", delta_color="normal")
                r2c4.metric("Profit Percentage", f"{profit_percentage:.2f}%", delta_color="normal")

    else:
        st.warning("Portfolio is empty. Add transactions to view portfolio details.")

    # ── Staking Rewards Summary ──
    staking_rewards_df = st.session_state.transactions[
        st.session_state.transactions['Type'] == 'Staking Reward'
    ].copy()

    if not staking_rewards_df.empty:
        st.markdown("<h2 style='margin-top:1.5rem;'><span class='material-symbols-outlined' style='font-size:20px;'>toll</span> Staking Rewards</h2>", unsafe_allow_html=True)

        staking_rewards_df['Ticker'] = staking_rewards_df['Ticker'].apply(normalize_ticker)
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
            <div style='flex:1; min-width:150px; background:#14161C; border:1px solid #1F2229; border-radius:8px; padding:0.9rem 1.1rem;'>
                <div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0; margin-bottom:0.25rem;'>Total Rewards Logged</div>
                <div style='font-family:"Manrope"; font-size:1.3rem; color:#EDEFF3;'>{int(rewards_summary["# Rewards"].sum())} entries</div>
            </div>
            <div style='flex:1; min-width:150px; background:#14161C; border:1px solid #1F2229; border-radius:8px; padding:0.9rem 1.1rem;'>
                <div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0; margin-bottom:0.25rem;'>Current Value (pure gain)</div>
                <div style='font-family:"Manrope"; font-size:1.3rem; color:#3DDC84;'>€{total_rewards_current:,.2f}</div>
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

    # ── Dividend Overview ──
    _div_tx = st.session_state.transactions[
        st.session_state.transactions['Type'] == 'Dividend'
    ].copy()
    if not _div_tx.empty:
        st.markdown("<h2 style='margin-top:1.5rem;'><span class='material-symbols-outlined' style='font-size:20px;'>payments</span> Dividends</h2>", unsafe_allow_html=True)

        _div_tx['Ticker'] = _div_tx['Ticker'].apply(normalize_ticker)
        _div_tx['Year'] = pd.to_datetime(_div_tx['Date'], errors='coerce').dt.year
        _total_div = float(_div_tx['Income'].sum())
        _12m_ago = datetime.now(ZoneInfo("Europe/Amsterdam")).date() - timedelta(days=365)
        _div_12m = float(_div_tx.loc[
            pd.to_datetime(_div_tx['Date'], errors='coerce').dt.date >= _12m_ago, 'Income'
        ].sum())

        dv1, dv2 = st.columns(2)
        dv1.metric("Totaal ontvangen dividend", f"€{_total_div:,.2f}")
        dv2.metric("Laatste 12 maanden", f"€{_div_12m:,.2f}")

        dcol1, dcol2 = st.columns(2)
        with dcol1:
            st.markdown("### Per asset")
            _div_by_ticker = _div_tx.groupby('Ticker').agg(
                Totaal=('Income', 'sum'),
                Uitkeringen=('Income', 'count'),
            ).reset_index().sort_values('Totaal', ascending=False)
            st.dataframe(
                _div_by_ticker.style.format({'Totaal': '€{:.2f}'}),
                use_container_width=True, hide_index=True
            )
        with dcol2:
            st.markdown("### Per jaar")
            _div_by_year = _div_tx.groupby('Year')['Income'].sum().reset_index()
            _div_by_year.columns = ['Jaar', 'Totaal']
            _div_by_year = _div_by_year.sort_values('Jaar', ascending=False)
            st.dataframe(
                _div_by_year.style.format({'Totaal': '€{:.2f}', 'Jaar': '{:.0f}'}),
                use_container_width=True, hide_index=True
            )

    st.markdown("<div style='height:0.8rem'></div>", unsafe_allow_html=True)
    with st.expander(f"All Transactions ({len(st.session_state.transactions)})", expanded=False):
        if not st.session_state.transactions.empty:
            _tx_view = st.session_state.transactions[TRANS_DISPLAY_COLS].copy()
            _tx_view['Ticker'] = _tx_view['Ticker'].apply(normalize_ticker)
            st.dataframe(_tx_view.style.format({
                'Quantity': '{:.8f}',
                'Purchase Price': '€{:.2f}',
                'Fee Amount': '{:.6f}',
                'Income': '€{:.2f}'
            }), use_container_width=True)
        else:
            st.info("No transactions available. Add transactions using the sidebar.")

# -------------------------
# Tab: Asset Allocation
# -------------------------
if _page == "Allocation":

    # ── Build category-aware allocation data ──
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
        chart_colors = [_CAT_COLORS.get(c, '#A4A9B4') for c in chart_df['Category']]

        col1, col2 = st.columns([2.2, 1])
        with col1:
            fig = go.Figure(data=[go.Pie(
                labels=chart_df['Category'],
                values=chart_df['Value'],
                hole=0.55,
                marker=dict(colors=chart_colors, line=dict(color="#0C0D10", width=2)),
                textposition="outside",
                textinfo="label+percent",
                textfont=dict(family="Manrope", size=11, color="#A4A9B4"),
                hovertemplate="%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>",
                pull=[0.02] * len(chart_df),
            )])
            fig.update_layout(
                showlegend=False,
                margin=dict(l=20, r=20, t=40, b=20),
                font=dict(family="Manrope", size=12, color="#8D93A0"),
                paper_bgcolor="#0C0D10", plot_bgcolor="#0C0D10",
                height=480,
                annotations=[dict(
                    text=f"<b>€{total_value:,.0f}</b><br><span style='font-size:10px;color:#8D93A0;'>NET WORTH</span>",
                    x=0.5, y=0.5, font=dict(family="Manrope", size=22, color="#EDEFF3"),
                    showarrow=False, align="center"
                )]
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            def _breakdown_row(label, value, pct, color, border=True):
                border_style = "border-bottom:1px solid #1F2229;" if border else ""
                return (
                    f"<div style='display:flex; justify-content:space-between; align-items:center; {border_style} padding:0.65rem 0;'>"
                    f"<span style='color:#A4A9B4; display:flex; align-items:center; gap:0.5rem;'>"
                    f"<span style='width:8px; height:8px; border-radius:2px; background:{color}; display:inline-block;'></span>{label}</span>"
                    f"<div style='text-align:right;'>"
                    f"<div style='font-family:Manrope; font-size:1rem; color:#EDEFF3;'>{pct:.1f}%</div>"
                    f"<div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0;'>€{value:,.0f}</div>"
                    f"</div></div>"
                )
            breakdown_html = (
                "<div style='height:480px; display:flex; align-items:center; justify-content:center;'>"
                "<div style='width:100%; padding-left:12px;'>"
                "<div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0; font-weight:600; margin-bottom:1.2rem;'>Category Breakdown</div>"
                + _breakdown_row("ETF",          etf_value,    pct_etf,    _CAT_COLORS['ETF'])
                + _breakdown_row("Individual Stock", stock_value, pct_stock, _CAT_COLORS['Stock'])
                + _breakdown_row("Crypto",        crypto_value, pct_crypto, _CAT_COLORS['Crypto'])
                + _breakdown_row("Cash & Banks",  cash_value,   pct_cash,   _CAT_COLORS['Cash & Banks'], border=False)
                + f"<div style='margin-top:1.2rem; padding-top:0.8rem; border-top:1px solid rgba(77,124,254,0.3);'>"
                f"<div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0; margin-bottom:0.3rem;'>Total Net Worth</div>"
                f"<div style='font-family:Manrope; font-size:1.5rem; color:#4D7CFE; letter-spacing:0.03em;'>€{total_value:,.2f}</div>"
                f"</div></div></div>"
            )
            st.markdown(breakdown_html, unsafe_allow_html=True)

        # ── Category Overrides ──
        st.markdown("---")
        st.markdown("<h2><span class='material-symbols-outlined' style='font-size:20px;'>category</span> Asset Category Overrides</h2>", unsafe_allow_html=True)
        st.markdown("<p style='font-family:Manrope; font-size:0.8rem; color:#A4A9B4; margin-bottom:0.75rem;'>Auto-detected categories based on ticker. Override if incorrect.</p>", unsafe_allow_html=True)

        if not portfolio_df.empty:
            for _, asset_row in portfolio_df.iterrows():
                tk = str(asset_row['Ticker'])
                detected = auto_detect_category(tk)
                current_cat = get_category(tk)
                ov_col1, ov_col2, ov_col3 = st.columns([2, 2, 1])
                ov_col1.markdown(f"<div style='padding:0.45rem 0; font-family:Manrope; font-size:0.85rem; color:#EDEFF3;'>{tk}</div>", unsafe_allow_html=True)
                ov_col2.markdown(f"<div style='padding:0.45rem 0; font-family:Manrope; font-size:0.75rem; color:#8D93A0;'>Auto: {detected}</div>", unsafe_allow_html=True)
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

        # Monthly expenses from cashflow (for the emergency-buffer hint)
        monthly_expenses = 0.0
        if not st.session_state.cashflow.empty:
            monthly_expenses = abs(float(
                st.session_state.cashflow.loc[st.session_state.cashflow['Amount'] < 0, 'Amount'].sum()
            ))
        buffer_6m = monthly_expenses * 6

        st.markdown("<p style='font-family:Manrope; font-size:0.78rem; color:#A4A9B4; margin-bottom:0.75rem;'>"
                    "Target split of your <b style='color:#EDEFF3;'>total</b> (cash + investments). "
                    "The four must add up to 100%.</p>", unsafe_allow_html=True)

        _keys   = ['Cash', 'ETF', 'Stock', 'Crypto']
        _tkeys  = {'Cash': 'cash_pct', 'ETF': 'etf_pct', 'Stock': 'stocks_pct', 'Crypto': 'crypto_pct'}
        _labels = {'Cash': 'Cash & Banks', 'ETF': 'ETFs', 'Stock': 'Stocks', 'Crypto': 'Crypto'}
        _colors = {'Cash': '#5B6170', 'ETF': '#4D7CFE', 'Stock': '#22C3B5', 'Crypto': '#F5A623'}

        tcols = st.columns(5)
        _tgt_split = {}
        for _col, _k in zip(tcols, _keys):
            with _col:
                _tgt_split[_k] = st.number_input(f"{_labels[_k]} %", min_value=0.0, max_value=100.0,
                    value=float(tgt.get(_tkeys[_k], _TARGET_DEFAULTS[_tkeys[_k]])), step=1.0, format="%.0f",
                    key=f"tgt_{_tkeys[_k]}")
        with tcols[4]:
            max_single_pct = st.number_input("Max % per stock / crypto", min_value=0.5, max_value=50.0,
                value=float(tgt.get('max_single_pct', 5.0)), step=0.5, format="%.1f", key="tgt_max_single",
                help="No individual stock or crypto should exceed this % of your investments (excl. cash)")

        _tgt_sum = sum(_tgt_split.values())
        _cash_tgt_eur = total_value * _tgt_split['Cash'] / 100
        _hint = (f"Your cash target is <b style='color:#EDEFF3;'>€{_cash_tgt_eur:,.0f}</b> "
                 f"= {(_cash_tgt_eur / monthly_expenses if monthly_expenses else 0):.1f} months of expenses "
                 f"(€{monthly_expenses:,.0f}/month from Cashflow).")
        if monthly_expenses and _cash_tgt_eur < buffer_6m:
            _hint += (f" <span style='color:#f5a524;'>That's below a 6-month buffer (€{buffer_6m:,.0f}).</span>")
        st.markdown(f"<p style='font-family:Manrope; font-size:0.78rem; color:#A4A9B4;'>{_hint}</p>",
                    unsafe_allow_html=True)

        if abs(_tgt_sum - 100) > 0.5:
            st.warning(f"Cash + ETF + Stocks + Crypto = {_tgt_sum:.0f}%. Make them add up to 100% before saving.")
        elif st.button("Save Targets", key="save_targets_btn"):
            _new_t = {_tkeys[k]: v for k, v in _tgt_split.items()}
            _new_t['max_single_pct'] = max_single_pct
            if save_allocation_targets(_new_t):
                st.session_state.allocation_targets = _new_t
                st.success("Targets saved!")

        allow_selling = st.toggle("Allow selling to rebalance", value=False, key="allow_selling",
            help="Off: overweight categories are simply paused and new money goes to what is underweight.")

        # ── Rebalancing Plan ──
        st.markdown("<h3 style='margin-top:1.2rem;'>Rebalancing Plan</h3>", unsafe_allow_html=True)

        def _rebal_card(col, key, current, target_val, diff, subtitle):
            is_cash = key == 'Cash'
            if abs(diff) <= 1:
                action, action_col = "✓  OK", "#8D93A0"
            elif diff > 0:
                action = f"ADD  €{diff:,.0f}" if is_cash else f"BUY  €{diff:,.0f}"
                action_col = "#3DDC84"
            elif is_cash:
                action, action_col = f"SURPLUS  €{-diff:,.0f}", "#A4A9B4"
            elif allow_selling:
                action, action_col = f"SELL  €{-diff:,.0f}", "#FF6B6B"
            else:
                action, action_col = f"PAUSE  (+€{-diff:,.0f})", "#f5a524"
            pct_now = current / total_value * 100 if total_value > 0 else 0
            col.markdown(
                f"<div style='background:#14161C; border:1px solid #1F2229; border-radius:8px; padding:1rem 1.2rem;'>"
                f"<div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0; margin-bottom:0.3rem;'>{_labels[key]}</div>"
                f"<div style='font-family:Manrope; font-size:0.78rem; color:#EDEFF3; margin-bottom:0.1rem;'>Now: <b>€{current:,.0f}</b> &nbsp;·&nbsp; {pct_now:.0f}%</div>"
                f"<div style='font-family:Manrope; font-size:0.72rem; color:#A4A9B4; margin-bottom:0.45rem;'>Target: €{target_val:,.0f} {subtitle}</div>"
                f"<div style='font-family:Manrope, sans-serif; font-size:1.3rem; color:{action_col}; letter-spacing:0.03em;'>{action}</div>"
                f"</div>",
                unsafe_allow_html=True
            )

        _cur_split = {'Cash': cash_value, 'ETF': etf_value, 'Stock': stock_value, 'Crypto': crypto_value}
        rb = st.columns(4)
        for _i, _k in enumerate(_keys):
            _t = total_value * _tgt_split[_k] / 100
            _rebal_card(rb[_i], _k, _cur_split[_k], _t, _t - _cur_split[_k], f"({_tgt_split[_k]:.0f}%)")

        # ── Next deposit planner (buy-only) ──
        if abs(_tgt_sum - 100) <= 0.5 and total_value > 0:
            st.markdown("<h3 style='margin-top:1.4rem;'>Next deposit</h3>", unsafe_allow_html=True)
            _need = deposit_needed_without_selling(_cur_split, _tgt_split)
            if _need == float('inf'):
                _need_txt = "A category with a 0% target still holds value, so adding money alone can't reach target."
            elif _need <= 1:
                _need_txt = "You're on target — split new money by the target percentages."
            else:
                _need_txt = (f"Without selling, about <b style='color:#EDEFF3;'>€{_need:,.0f}</b> of new money "
                             f"(into the underweight categories) brings everything back to target at today's prices.")
            st.markdown(f"<p style='font-family:Manrope; font-size:0.8rem; color:#A4A9B4;'>{_need_txt}</p>",
                        unsafe_allow_html=True)
            _dep = st.number_input("New money this month (€)", min_value=0.0, value=500.0, step=50.0,
                                   format="%.0f", key="next_deposit_amt")
            _plan = plan_deposit(_cur_split, _tgt_split, _dep)
            _pc = st.columns(4)
            for _i, _k in enumerate(_keys):
                _after = (_cur_split[_k] + _plan[_k]) / (total_value + _dep) * 100 if (total_value + _dep) > 0 else 0
                _verb = "Keep as cash" if _k == 'Cash' else "Invest"
                _pc[_i].markdown(
                    f"<div style='background:#14161C; border:1px solid #1F2229; border-radius:8px; padding:0.8rem 1.1rem;'>"
                    f"<div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0;'>{_labels[_k]} · {_verb}</div>"
                    f"<div style='font-family:Manrope, sans-serif; font-size:1.3rem; color:#EDEFF3;'>€{_plan[_k]:,.0f}</div>"
                    f"<div style='font-family:Manrope; font-size:0.7rem; color:#A4A9B4;'>→ {_after:.0f}% after (target {_tgt_split[_k]:.0f}%)</div>"
                    f"</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

        # ── Concentration alerts ──
        if not portfolio_df.empty and investments_value > 0:
            st.markdown("<h3>Concentration Check</h3>", unsafe_allow_html=True)
            st.markdown(
                f"<p style='font-family:Manrope; font-size:0.78rem; color:#A4A9B4; margin-bottom:0.75rem;'>"
                f"Max allowed per individual stock or crypto: <b style='color:#4D7CFE;'>{max_single_pct:.1f}%</b> "
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
                        'Status':         ((f"⚠ TRIM €{over:,.0f}" if allow_selling else f"⚠ Over by €{over:,.0f} — pause buying")
                                           if over > 1 else "✓ OK"),
                    })
            if conc_rows:
                conc_df = pd.DataFrame(conc_rows)
                st.dataframe(
                    conc_df.style
                    .format({'Value (€)': '€{:.2f}', '% of Investments': '{:.1f}%',
                             'Limit (€)': '€{:.2f}', 'Over limit (€)': '€{:.2f}'})
                    .map(lambda v: 'color:#FF6B6B' if isinstance(v, str) and '⚠' in v else '',
                         subset=['Status']),
                    use_container_width=True
                )

# -------------------------
# Tab: Historical Price Charts
# -------------------------
if _page == "Charts":
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
                              color_discrete_sequence=["#4D7CFE"])
                fig.update_traces(line=dict(width=2.5))
                fig.add_hline(y=avg_purchase, line_dash="dash", line_color="rgba(77,124,254,0.5)",
                              annotation_text=f"Avg: €{avg_purchase:.2f}",
                              annotation_position="top left",
                              annotation_font=dict(family="Manrope", color="#4D7CFE", size=11))
                fig.update_layout(
                    title=dict(font=dict(family="Manrope", color="#EDEFF3", size=15), x=0),
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
if _page == "Planning":

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
        "<span style='font-family:Manrope; font-size:0.7rem; color:#8D93A0; margin-left:0.8rem;'>auto-saved</span>",
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
        _pg_col = "#3DDC84" if progress >= 80 else "#4D7CFE" if progress >= 40 else "#FF6B6B"
        st.markdown(
            f"<div style='margin-bottom:1.5rem;'>"
            f"<div style='display:flex; justify-content:space-between; font-family:Manrope; font-size:0.72rem; color:#A4A9B4; margin-bottom:0.4rem;'>"
            f"<span>Net Worth Progress</span><span style='color:{_pg_col};'>{progress:.1f}%</span></div>"
            f"<div style='background:#1F2229; border-radius:4px; height:10px;'>"
            f"<div style='background:{_pg_col}; width:{progress:.1f}%; height:10px; border-radius:4px; transition:width 0.3s;'></div>"
            f"</div>"
            f"<div style='display:flex; justify-content:space-between; font-family:Manrope; font-size:0.68rem; color:#8D93A0; margin-top:0.3rem;'>"
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
                _exp_tag  = f"<span style='color:#3DDC84;'>✓ €{monthly_expenses:,.0f} expenses fully covered</span>"
                _surplus  = other_monthly_income - monthly_expenses
                _inv_tag  = (
                    f"<span style='color:#3DDC84;'>+ €{_surplus:,.0f} toward investments</span>"
                    if _surplus > 0 else ""
                )
            else:
                _exp_tag = (
                    f"<span style='color:#4D7CFE;'>€{covered_expenses:,.0f} of €{monthly_expenses:,.0f} expenses "
                    f"(€{work_for_expenses:,.0f} still needs work)</span>"
                )
                _inv_tag = ""
            st.markdown(
                f"<div style='background:#14161C; border:1px solid #1F2229; border-radius:8px; "
                f"padding:0.8rem 1.1rem; margin:0.5rem 0 0.2rem; font-family:Manrope; font-size:0.78rem;'>"
                f"<span style='color:#8D93A0; font-size:0.62rem;'>Your other income (€{other_monthly_income:,.0f}/mo) covers →</span><br>"
                f"<span style='color:#A4A9B4;'>{_exp_tag}"
                f"{('&nbsp;&nbsp;·&nbsp;&nbsp;' + _inv_tag) if _inv_tag else ''}</span>"
                f"</div>",
                unsafe_allow_html=True
            )

        # ── Net worth projection ──
        st.markdown("<h3 style='margin-top:1.2rem;'>Net Worth Projectie</h3>", unsafe_allow_html=True)

        _assets_now_total = _assets + _cb + _cr + _ci
        _proj_dates, _proj_with, _proj_without = [], [], []
        for _m in range(months_remaining + 1):
            _d = (pd.Timestamp(_today) + pd.DateOffset(months=_m)).date()
            _growth = (1 + r) ** _m
            _contrib_fv = (monthly_invest_needed * ((_growth - 1) / r) if r > 0
                           else monthly_invest_needed * _m)
            # Debt at this future month (student loans keep growing!)
            _debt_m = 0.0
            if not st.session_state.loans.empty:
                _debt_m = sum(
                    calc_loan_balance_at(
                        _d, float(lrow.get('Principal', 0.0)),
                        float(lrow.get('Annual Rate', 0.0)),
                        float(lrow.get('Monthly Payment', 0.0)), lrow.get('Start Date'),
                        loan_type=str(lrow.get('Loan Type', 'standard')),
                        monthly_borrow=float(lrow.get('Monthly Borrow', 0.0)),
                        study_end_date=lrow.get('Study End Date'),
                    )
                    for _, lrow in st.session_state.loans.iterrows()
                )
            _proj_dates.append(_d)
            _proj_with.append(_assets_now_total * _growth + _contrib_fv - _debt_m)
            _proj_without.append(_assets_now_total * _growth - _debt_m)

        _fig_proj = go.Figure()
        _fig_proj.add_trace(go.Scatter(
            x=_proj_dates, y=_proj_with, mode="lines",
            name=f"Met €{monthly_invest_needed:,.0f}/mo inleg",
            line=dict(color="#4D7CFE", width=2.5),
            hovertemplate="€%{y:,.0f}<extra>Met inleg</extra>"
        ))
        _fig_proj.add_trace(go.Scatter(
            x=_proj_dates, y=_proj_without, mode="lines",
            name="Zonder extra inleg",
            line=dict(color="#A4A9B4", width=2, dash="dot"),
            hovertemplate="€%{y:,.0f}<extra>Zonder inleg</extra>"
        ))
        _fig_proj.add_hline(
            y=goal_amount, line_dash="dash", line_color="#3DDC84",
            annotation_text=f"Doel €{goal_amount:,.0f}",
            annotation_position="top left",
            annotation_font=dict(family="Manrope", color="#3DDC84", size=11)
        )
        _fig_proj.update_layout(
            title=dict(text="Verwacht vermogen tot je doeldatum",
                       font=dict(family="Manrope", color="#EDEFF3", size=15), x=0),
            yaxis_title="Net worth (€)",
            **_CHART_LAYOUT
        )
        st.plotly_chart(_fig_proj, use_container_width=True)
        st.caption(
            f"Aannames: {expected_return:.1f}% jaarrendement op al je vermogen, "
            f"vaste maandelijkse inleg van €{monthly_invest_needed:,.0f}, "
            f"leningen groeien/dalen volgens hun eigen rente en aflossing."
        )

        # ── Work hours breakdown ──
        st.markdown("<h3 style='margin-top:1.2rem;'>How much do you need to work this month?</h3>", unsafe_allow_html=True)

        def _hour_card(col, label, hours, euros, border_color, detail="", covered=False):
            days = hours / 8
            if covered:
                col.markdown(
                    f"<div style='background:#14161C; border:1px solid #1F2229; border-radius:8px; padding:1rem 1.2rem;'>"
                    f"<div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0; margin-bottom:0.3rem;'>{label}</div>"
                    f"<div style='font-family:Manrope, sans-serif; font-size:1.6rem; color:#3DDC84; letter-spacing:0.03em;'>Covered ✓</div>"
                    f"<div style='font-family:Manrope; font-size:0.75rem; color:#A4A9B4; margin-top:0.1rem;'>€{euros:,.0f} by other income</div>"
                    f"{'<div style=\"font-family:Manrope; font-size:0.68rem; color:#8D93A0; margin-top:0.2rem;\">' + detail + '</div>' if detail else ''}"
                    f"</div>",
                    unsafe_allow_html=True
                )
            else:
                col.markdown(
                    f"<div style='background:#14161C; border:1px solid #1F2229; border-radius:8px; padding:1rem 1.2rem;'>"
                    f"<div style='font-family:Manrope; font-size:0.78rem; color:#8D93A0; margin-bottom:0.3rem;'>{label}</div>"
                    f"<div style='font-family:Manrope, sans-serif; font-size:1.6rem; color:#EDEFF3; letter-spacing:0.03em;'>{hours:.0f} hrs</div>"
                    f"<div style='font-family:Manrope; font-size:0.75rem; color:#A4A9B4; margin-top:0.1rem;'>≈ {days:.1f} days &nbsp;·&nbsp; €{euros:,.0f}</div>"
                    f"{'<div style=\"font-family:Manrope; font-size:0.68rem; color:#8D93A0; margin-top:0.2rem;\">' + detail + '</div>' if detail else ''}"
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
                       monthly_expenses, "#3DDC84",
                       f"Paid by your €{other_monthly_income:,.0f} other income", covered=True)
        else:
            _hour_card(h1, "For expenses (from work)", hours_expenses,
                       work_for_expenses, "#FF6B6B",
                       f"€{covered_expenses:,.0f} covered by income · €{work_for_expenses:,.0f} gap")

        # Loan repayment card (only if loans exist)
        if h4 is not None:
            if work_for_repay == 0:
                _hour_card(h2, "Loan repayments", 0,
                           _plan_repay, "#3DDC84",
                           f"€{_plan_repay:,.0f}/mo covered by other income", covered=True)
            else:
                _hour_card(h2, "Loan repayments (from work)", hours_repay,
                           work_for_repay, "#FF6B6B",
                           f"€{_plan_repay:,.0f}/mo across {len(st.session_state.loans)} loan(s)")
            _hour_card(h3, "For investment (from work)", hours_investment,
                       work_for_investment, "#3DDC84",
                       f"€{monthly_invest_needed:,.0f} needed · {expected_return:.1f}% return assumed")
            _hour_card(h4, "Total work hours needed", hours_total,
                       work_income_needed, "#4D7CFE",
                       f"€{hourly_rate:.0f}/hr × {hours_total:.0f} hrs = €{work_income_needed:,.0f}")
        else:
            _hour_card(h2, "For investment (from work)", hours_investment,
                       work_for_investment, "#3DDC84",
                       f"€{monthly_invest_needed:,.0f} needed · {expected_return:.1f}% return assumed")
            _hour_card(h3, "Total work hours needed", hours_total,
                       work_income_needed, "#4D7CFE",
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
                    _mb  = float(lr.get('Monthly Borrow', 0.0))
                    _sed = lr.get('Study End Date')
                    _has_end = _sed and str(_sed) not in ('None', '', 'NaT')
                    _still_borrowing = (not _has_end
                                        or _today_l <= pd.to_datetime(str(_sed)).date())
                    # Balance at end_date (if set), else current balance
                    if _has_end:
                        _bal_end = _student_balance_at(_mb, _r, lr.get('Start Date'), _sed)
                        _end_str = str(pd.to_datetime(str(_sed)).date())
                    else:
                        _bal_end = rem
                        _end_str = "–"
                    _status = "📈 Leent nog" if _still_borrowing else "⏸ Gestopt"
                    loan_rows.append({
                        'Naam': lr['Name'],
                        'Type': 'Studentenlening',
                        'Status': _status,
                        'Huidig saldo (€)': rem,
                        'Maandbedrag (€)': _mb,
                        'Einddatum': _end_str,
                        'Saldo op einddatum (€)': _bal_end if _has_end else None,
                        'Rente': f"{lr.get('Annual Rate', 0.0):.2f}%",
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
                        'Status': f"{_mo_left} maanden",
                        'Huidig saldo (€)': rem,
                        'Maandbedrag (€)': _pmt,
                        'Einddatum': "–",
                        'Saldo op einddatum (€)': None,
                        'Rente': f"{lr.get('Annual Rate', 0.0):.2f}%",
                    })
            _loan_df = pd.DataFrame(loan_rows)
            # Only show "Saldo op einddatum" column if at least one row has it
            _has_end_col = _loan_df['Saldo op einddatum (€)'].notna().any()
            _show_cols = ['Naam', 'Type', 'Status', 'Huidig saldo (€)',
                          'Maandbedrag (€)', 'Einddatum', 'Rente']
            if _has_end_col:
                _show_cols.insert(_show_cols.index('Einddatum') + 1, 'Saldo op einddatum (€)')
            _show_cols = [c for c in _show_cols if c in _loan_df.columns]
            _fmt = {'Huidig saldo (€)': '€{:,.0f}', 'Maandbedrag (€)': '€{:,.0f}'}
            if _has_end_col:
                _fmt['Saldo op einddatum (€)'] = '€{:,.0f}'
            st.dataframe(
                _loan_df[_show_cols].style.format(_fmt, na_rep="–"),
                use_container_width=True, hide_index=True
            )

        # ── Leverage Analysis ──
        if not st.session_state.loans.empty:
            st.markdown("---")
            st.markdown("<h3>Leverage Analysis</h3>", unsafe_allow_html=True)
            st.markdown(
                "<p style='font-family:Manrope; font-size:0.8rem; color:#A4A9B4; margin-bottom:1rem;'>"
                "Is het rendabel om geleend geld te beleggen? "
                "Je portfolio moet meer opleveren dan de rente die je betaalt.</p>",
                unsafe_allow_html=True
            )

            # Annualised portfolio return
            _ann_pct = _xirr_pct if _xirr_pct is not None else calc_annualized_return(profit_percentage, st.session_state.transactions)

            # Accumulate totals across loans (used in the summary below)
            _sum_interest_y = 0.0
            _sum_gain_y     = 0.0

            for _, _lr in st.session_state.loans.iterrows():
                _rate    = float(_lr['Annual Rate'])
                _ltype_l = str(_lr.get('Loan Type', 'standard'))
                _rem     = calc_loan_balance(
                    float(_lr.get('Principal', 0.0)), _rate,
                    float(_lr.get('Monthly Payment', 0.0)), _lr['Start Date'],
                    loan_type=_ltype_l,
                    monthly_borrow=float(_lr.get('Monthly Borrow', 0.0)),
                    study_end_date=_lr.get('Study End Date'),
                    repayment_years=float(_lr.get('Repayment Years', 10.0)),
                )
                # For student loans, use current accumulated balance as the "invested amount"
                _principal = _rem if _ltype_l == 'student' else float(_lr['Principal'])

                # Interest cost on remaining balance
                _annual_interest   = _rem * _rate / 100
                _monthly_interest  = _annual_interest / 12

                # Investment return on the borrowed amount
                _annual_gain   = _principal * _ann_pct / 100
                _monthly_gain  = _annual_gain / 12

                _sum_interest_y += _annual_interest
                _sum_gain_y     += _annual_gain

                # Net and spread
                _net_annual = _annual_gain - _annual_interest
                _spread     = _ann_pct - _rate
                _profitable = _spread > 0
                _status_col = "#3DDC84" if _profitable else "#FF6B6B"
                _status_ico = "✓" if _profitable else "✗"
                _spread_sign = "+" if _spread >= 0 else ""

                # Card header
                _ltype_label = "studentenlening" if _ltype_l == 'student' else "lening"
                st.markdown(
                    f"<div style='font-family:Manrope; font-size:0.78rem; "
                    f"color:#8D93A0; margin-bottom:0.5rem;'>"
                    f"{_lr['Name']} &nbsp;·&nbsp; €{_principal:,.0f} {_ltype_label} @ {_rate:.2f}%</div>",
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
                    _verdict_col = "#8D93A0"
                elif _profitable:
                    _verdict = (
                        f"{_status_ico} Winstgevend — je portfolio ({_ann_pct:.1f}%) "
                        f"rendert {_spread:.1f}% meer dan de rente ({_rate:.2f}%). "
                        f"Netto winst: €{_net_annual:,.0f}/jaar."
                    )
                    _verdict_col = "#3DDC84"
                else:
                    _verdict = (
                        f"{_status_ico} Niet winstgevend — je portfolio ({_ann_pct:.1f}%) "
                        f"rendert {abs(_spread):.1f}% minder dan de rente ({_rate:.2f}%). "
                        f"Je verliest €{abs(_net_annual):,.0f}/jaar door deze lening."
                    )
                    _verdict_col = "#FF6B6B"

                st.markdown(
                    f"<div style='background:#14161C; border:1px solid #1F2229; "
                    f"border-radius:8px; "
                    f"padding:0.7rem 1rem; margin:0.4rem 0 1.2rem; "
                    f"font-family:Manrope; font-size:0.78rem; color:{_verdict_col};'>"
                    f"{_verdict}</div>",
                    unsafe_allow_html=True
                )

            # Overall summary if multiple loans — uses per-loan accumulated
            # totals so student loans (Principal = 0) are counted correctly
            if len(st.session_state.loans) > 1:
                _total_interest_y = _sum_interest_y
                _total_gain_y     = _sum_gain_y
                _total_net_y      = _total_gain_y - _total_interest_y
                _tc = "#3DDC84" if _total_net_y >= 0 else "#FF6B6B"
                st.markdown(
                    f"<div style='background:#14161C; border:1px solid #1F2229; border-radius:8px; "
                    f"padding:0.8rem 1.1rem; font-family:Manrope; font-size:0.78rem;'>"
                    f"<span style='color:#8D93A0; font-size:0.62rem; '>Totaal alle leningen</span><br>"
                    f"<span style='color:{_tc}; font-size:1rem;'>Netto {'+' if _total_net_y >= 0 else ''}€{_total_net_y:,.0f}/jaar</span>"
                    f"<span style='color:#8D93A0; font-size:0.75rem;'> &nbsp;(rendement €{_total_gain_y:,.0f} − rente €{_total_interest_y:,.0f})</span>"
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
                    name='Invested', marker_color='#4D7CFE',
                    hovertemplate='%{x|%b %Y}<br>€%{y:,.0f}<extra></extra>'
                ))
                _fig_dca.add_hline(
                    y=monthly_invest_needed, line_dash="dash", line_color="#3DDC84",
                    annotation_text=f"Target €{monthly_invest_needed:,.0f}/mo",
                    annotation_font=dict(family="Manrope", color="#3DDC84", size=11),
                    annotation_position="top left"
                )
                _fig_dca.update_layout(
                    plot_bgcolor="#0C0D10", paper_bgcolor="#0C0D10",
                    font=dict(family="Manrope", color="#8D93A0", size=11),
                    xaxis=dict(gridcolor="#1F2229", linecolor="#1F2229", tickfont=dict(color="#8D93A0")),
                    yaxis=dict(gridcolor="#1F2229", linecolor="#1F2229", tickfont=dict(color="#8D93A0"), title="€ Invested"),
                    margin=dict(l=10, r=10, t=40, b=10),
                    hovermode="x unified",
                    hoverlabel=dict(bgcolor="#14161C", bordercolor="#1F2229", font=dict(family="Manrope", color="#EDEFF3", size=12)),
                    title=dict(text="Monthly Investments vs Target", font=dict(family="Manrope", color="#EDEFF3", size=15), x=0),
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

    # ── Box 3 indicatie (NL vermogensbelasting) ──
    st.markdown("---")
    st.markdown("<h3>Box 3 Indicatie (NL)</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='font-family:Manrope; font-size:0.78rem; color:#A4A9B4; margin-bottom:0.75rem;'>"
        "Schatting van je vermogensbelasting volgens de overbruggingswet, op basis van je "
        "huidige vermogen als benadering van de peildatum (1 januari). "
        "Indicatie — geen fiscaal advies; controleer de actuele percentages op belastingdienst.nl.</p>",
        unsafe_allow_html=True
    )

    b3c1, b3c2, b3c3 = st.columns(3)
    with b3c1:
        _b3_vrij = st.number_input("Heffingsvrij vermogen (€)", min_value=0.0,
                                    value=57684.0, step=100.0, format="%.0f", key="b3_vrij")
        _b3_tarief = st.number_input("Tarief (%)", min_value=0.0, max_value=100.0,
                                      value=36.0, step=1.0, format="%.0f", key="b3_tarief")
    with b3c2:
        _b3_r_spaar = st.number_input("Forfait sparen (%)", min_value=0.0, max_value=20.0,
                                       value=1.44, step=0.01, format="%.2f", key="b3_rs")
        _b3_r_beleg = st.number_input("Forfait beleggen (%)", min_value=0.0, max_value=20.0,
                                       value=5.88, step=0.01, format="%.2f", key="b3_rb")
    with b3c3:
        _b3_r_schuld = st.number_input("Forfait schulden (%)", min_value=0.0, max_value=20.0,
                                        value=2.62, step=0.01, format="%.2f", key="b3_rd")
        _b3_drempel = st.number_input("Schuldendrempel (€)", min_value=0.0,
                                       value=3800.0, step=100.0, format="%.0f", key="b3_drempel")

    _b3_spaar  = _cash + _credit + _cic                       # banktegoeden + broker cash
    _b3_beleg  = _total_assets                                # beleggingen (huidige waarde)
    _b3_schuld = max(_total_debt - _b3_drempel, 0.0)          # schulden boven drempel

    _b3_rendement = (_b3_spaar * _b3_r_spaar / 100
                     + _b3_beleg * _b3_r_beleg / 100
                     - _b3_schuld * _b3_r_schuld / 100)
    _b3_grondslag = _b3_spaar + _b3_beleg - _b3_schuld
    _b3_belastbaar_grondslag = max(_b3_grondslag - _b3_vrij, 0.0)

    if _b3_grondslag > 0 and _b3_belastbaar_grondslag > 0 and _b3_rendement > 0:
        _b3_aandeel  = _b3_belastbaar_grondslag / _b3_grondslag
        _b3_voordeel = _b3_rendement * _b3_aandeel
        _b3_tax      = _b3_voordeel * _b3_tarief / 100
    else:
        _b3_voordeel = 0.0
        _b3_tax      = 0.0

    b3m1, b3m2, b3m3, b3m4 = st.columns(4)
    b3m1.metric("Grondslag (bezit − schuld)", f"€{_b3_grondslag:,.0f}",
                help=f"Sparen €{_b3_spaar:,.0f} + beleggen €{_b3_beleg:,.0f} − schuld €{_b3_schuld:,.0f}")
    b3m2.metric("Boven heffingsvrij", f"€{_b3_belastbaar_grondslag:,.0f}")
    b3m3.metric("Belastbaar rendement", f"€{_b3_voordeel:,.0f}",
                help="Forfaitair rendement × aandeel boven het heffingsvrij vermogen")
    b3m4.metric("Geschatte Box 3 belasting", f"€{_b3_tax:,.0f}")

    if _b3_belastbaar_grondslag == 0:
        st.caption(f"✓ Je vermogen (€{_b3_grondslag:,.0f}) zit onder het heffingsvrij "
                   f"vermogen van €{_b3_vrij:,.0f} — geen Box 3 belasting verschuldigd.")

# -------------------------
# Footer
# -------------------------
st.markdown("---")
