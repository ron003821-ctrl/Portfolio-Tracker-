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
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
        }
        [data-testid="stMetricValue"] { font-size: 1.2rem !important; }
        .stTabs [role="tab"] {
            font-size: 0.66rem !important;
            padding: 0.7rem 0.55rem !important;
        }
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
    trans_type = st.selectbox("Transaction Type", ['Buy', 'Dividend', 'Staking', 'Transfer'], key="add_trans_type")
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

    if trans_type in ['Buy', 'Staking']:
        quantity = st.number_input("Quantity", min_value=0.0, value=0.0, step=1e-12, format="%.12f", key="add_quantity_input")
        purchase_price = st.number_input("Price per Unit (EUR)", min_value=0.0, value=0.0, step=0.01, format="%.2f", key="add_price_input")
        if trans_type == 'Buy':
            fee_unit = st.selectbox("Fee Unit", options=['None', 'EUR'], key="add_fee_unit_select")
            fee_amount = st.number_input("Transaction Fee (EUR)", min_value=0.0, value=0.0, step=1e-12, format="%.12f", key="add_fee_amount_input") if fee_unit != 'None' else 0.0
        else:
            fee_unit = 'None'
            fee_amount = 0.0
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
            edit_trans_type = st.selectbox("Transaction Type", ['Buy', 'Dividend', 'Staking', 'Transfer'], index=['Buy', 'Dividend', 'Staking', 'Transfer'].index(trans['Type']), key="edit_trans_type_select")
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

            if edit_trans_type in ['Buy', 'Staking']:
                edit_quantity = st.number_input("Quantity", min_value=0.0, value=float(trans['Quantity']), step=1e-12, format="%.12f", key="edit_quantity_input")
                edit_purchase_price = st.number_input("Price per Unit (EUR)", min_value=0.0, value=float(trans['Purchase Price']), step=0.01, format="%.2f", key="edit_price_input")
                if edit_trans_type == 'Buy':
                    edit_fee_unit = st.selectbox("Fee Unit", options=['None', 'EUR'], index=['None', 'EUR'].index(trans['Fee Unit']) if trans['Fee Unit'] in ['None', 'EUR'] else 0, key="edit_fee_unit_select")
                    edit_fee_amount = st.number_input("Transaction Fee (EUR)", min_value=0.0, value=float(trans['Fee Amount']), step=1e-12, format="%.12f", key="edit_fee_amount_input") if edit_fee_unit != 'None' else 0.0
                else:
                    edit_fee_unit = 'None'
                    edit_fee_amount = 0.0
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

# -------------------------
# Price fetching functions
# -------------------------
@st.cache_data(ttl=300)
def get_price(ticker):
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
    elif ticker == 'TAO-EUR':
        tickers_to_try.extend(['TAO22974-USD', 'TAO-USD', 'TAO/USD', 'TAO-EUR'])
    elif '-EUR' in ticker:
        tickers_to_try.append(ticker.replace('-EUR', '-USD'))

    for t in tickers_to_try:
        try:
            data = yf.Ticker(t).history(period='1d', interval='1d')['Close']
            if not data.empty:
                price = data.iloc[-1]
                if t.endswith('-USD') or t in ['VOO', 'TAO22974-USD', 'TAO-USD', 'TAO/USD']:
                    eur_usd = yf.Ticker('EURUSD=X').history(period='1d', interval='1d')['Close']
                    if not eur_usd.empty:
                        return price / eur_usd.iloc[-1]
                return price
        except Exception:
            continue
    if ticker == 'TAO-EUR':
        tao_trans = st.session_state.transactions[st.session_state.transactions['Ticker'] == 'TAO-EUR']
        if not tao_trans.empty:
            valid_trans = tao_trans[tao_trans['Purchase Price'] > 0]
            if not valid_trans.empty:
                avg_price = valid_trans['Purchase Price'].mean()
                st.warning(f"TAO-EUR price not found on Yahoo Finance. Using average purchase price: €{avg_price:.2f}")
                return avg_price
    return 0.0

@st.cache_data(ttl=3600)
def get_historical_data(ticker, period='1y'):
    tickers_to_try = [ticker]
    if ticker == 'TAO-EUR':
        tickers_to_try.extend(['TAO22974-USD', 'TAO-USD', 'TAO/USD', 'TAO-EUR'])
    elif ticker in ['VUSA', 'VUSA.AS']:
        tickers_to_try.extend(['VUSA.AS', 'VOO'])
    elif ticker in ['VWRL', 'VWRL.AS']:
        tickers_to_try.extend(['VWRL.AS'])
    elif ticker in ['QDVE', 'QDVE.DE']:
        tickers_to_try.extend(['QDVE.DE'])
    elif ticker == 'SLMC.DE':
        tickers_to_try.extend(['SLMC.'])
    elif ticker in ['BTC', 'ETH', 'SOL', 'TAO']:
        tickers_to_try.extend([f"{ticker}-EUR", f"{ticker}-USD"])
    elif '-EUR' in ticker:
        tickers_to_try.append(ticker.replace('-EUR', '-USD'))

    for t in tickers_to_try:
        try:
            data = yf.download(t, period=period)
            if not data.empty:
                data = data['Close'].reset_index()
                data.columns = ['Date', 'Close']
                if t.endswith('-USD') or t in ['VOO', 'TAO22974-USD', 'TAO-USD', 'TAO/USD']:
                    eur_usd = yf.download('EURUSD=X', period=period)
                    if not eur_usd.empty:
                        eur_usd = eur_usd['Close'].reindex(data.index, method='ffill')
                        data['Close'] = data['Close'] / eur_usd
                return data
        except Exception:
            continue

    if ticker == 'TAO-EUR':
        tao_trans = st.session_state.transactions[st.session_state.transactions['Ticker'] == 'TAO-EUR']
        if not tao_trans.empty:
            valid_trans = tao_trans[tao_trans['Purchase Price'] > 0]
            if not valid_trans.empty:
                avg_price = valid_trans['Purchase Price'].mean()
                dates = pd.date_range(end=datetime.today(), periods=252, freq='B')
                synthetic_data = pd.DataFrame({
                    'Date': dates,
                    'Close': [avg_price] * len(dates)
                })
                st.warning(f"TAO-EUR historical data not available. Using synthetic data with average purchase price: €{avg_price:.2f}")
                return synthetic_data
    return pd.DataFrame()

# -------------------------
# Add / Edit / Delete transactions
# -------------------------
if add_button and ticker:
    if trans_type in ['Buy', 'Staking'] and quantity <= 0:
        st.sidebar.error("Quantity must be positive for Buy or Staking.")
    elif trans_type in ['Buy', 'Staking'] and purchase_price <= 0:
        st.sidebar.error("Price per unit must be positive for Buy or Staking.")
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
    if edit_trans_type in ['Buy', 'Staking'] and edit_quantity <= 0:
        st.sidebar.error("Quantity must be positive for Buy or Staking.")
    elif edit_trans_type in ['Buy', 'Staking'] and edit_purchase_price <= 0:
        st.sidebar.error("Price per unit must be positive for Buy or Staking.")
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
        elif trans_type == 'Dividend':
            realized += income
        elif trans_type == 'Staking':
            c += quantity * purchase_price
            s += quantity * purchase_price
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
_profit_color = "#27ae7a" if total_profit >= 0 else "#c94c4c"
_profit_sign  = "+" if total_profit >= 0 else ""
_pct_sign     = "+" if profit_percentage >= 0 else ""
_today_str    = datetime.now(ZoneInfo("Europe/Amsterdam")).strftime("%d %b %Y").upper()

st.markdown(f"""
<div style='background:#0c1120; border-bottom:1px solid #192138; padding:1.4rem 1.5rem 1.2rem; margin:-0 -1.5rem 0; display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:1rem;'>
    <div>
        <div style='font-family:"Ropa Sans",sans-serif; font-size:1.6rem; letter-spacing:0.08em; color:#f0ece0; line-height:1;'>PORTFOLIO</div>
        <div style='width:36px; height:2px; background:#c9a84c; margin:0.4rem 0 0.3rem;'></div>
        <div style='font-family:"Inter",sans-serif; font-size:0.6rem; letter-spacing:0.2em; color:#5c5a54; text-transform:uppercase;'>{_today_str}</div>
    </div>
    <div style='display:flex; gap:2.5rem; flex-wrap:wrap;'>
        <div style='text-align:right;'>
            <div style='font-family:"Inter",sans-serif; font-size:0.6rem; letter-spacing:0.14em; color:#5c5a54; text-transform:uppercase; margin-bottom:0.25rem;'>Total Value</div>
            <div style='font-family:"Ropa Sans",sans-serif; font-size:1.5rem; color:#f0ece0; letter-spacing:0.03em;'>€{_total_value:,.0f}</div>
        </div>
        <div style='text-align:right;'>
            <div style='font-family:"Inter",sans-serif; font-size:0.6rem; letter-spacing:0.14em; color:#5c5a54; text-transform:uppercase; margin-bottom:0.25rem;'>Total P&L</div>
            <div style='font-family:"Ropa Sans",sans-serif; font-size:1.5rem; color:{_profit_color}; letter-spacing:0.03em;'>{_profit_sign}€{total_profit:,.0f}</div>
        </div>
        <div style='text-align:right;'>
            <div style='font-family:"Inter",sans-serif; font-size:0.6rem; letter-spacing:0.14em; color:#5c5a54; text-transform:uppercase; margin-bottom:0.25rem;'>Return</div>
            <div style='font-family:"Ropa Sans",sans-serif; font-size:1.5rem; color:{_profit_color}; letter-spacing:0.03em;'>{_pct_sign}{profit_percentage:.1f}%</div>
        </div>
    </div>
</div>
<div style='height:3px; background:linear-gradient(90deg,#c9a84c 0%,rgba(201,168,76,0.15) 60%,transparent 100%);'></div>
""", unsafe_allow_html=True)

st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
_rcol1, _rcol2 = st.columns([6, 1])
with _rcol2:
    if st.button("Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# -------------------------
# Navigation tabs
# -------------------------
tab_overview, tab_history, tab_cashflow, tab_allocation, tab_charts = st.tabs([
    "Overview",
    "History",
    "Cashflow",
    "Allocation",
    "Charts"
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

    portfolio_df, realized, unrealized, total_profit, profit_percentage = compute_portfolio()

    if not portfolio_df.empty:
        portfolio_df_display = portfolio_df.rename(columns={
            "Ticker": "Asset",
            "Quantity": "Qty",
            "Average Purchase Price": "GIP(€)",
            "Cost Basis": "Invested(€)",
            "Current Price": "Price(€)",
            "Value": "Value(€)",
            "Unrealized Profit/Loss": "Unrealized P/L (€)"
        })

        st.dataframe(
            portfolio_df_display.style.format({
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

        total_invested = portfolio_df["Cost Basis"].sum()
        total_bank = (
            st.session_state.balances.get("credit_mutuel_balance", 0.0)
            + st.session_state.balances.get("cic_balance", 0.0)
        )
        total_value = (
            portfolio_df["Value"].sum()
            + st.session_state.balances.get("cash_balance", 0.0)
            + total_bank
        )

        col1, col2 = st.columns(2)
        col1.metric("Total Invested", f"€{total_invested:,.2f}")
        col2.metric("Total Portfolio Value", f"€{total_value:,.2f}")

        col3, col4 = st.columns(2)
        col3.metric("Broker Cash", f"€{st.session_state.balances.get('cash_balance', 0.0):,.2f}")
        col4.metric("Total Bank Balance", f"€{total_bank:,.2f}")

        col5, col6 = st.columns(2)
        col5.metric("Realized Income/Expenses", f"€{realized:,.2f}", delta_color="normal")
        col6.metric("Unrealized Profit/Loss", f"€{unrealized:,.2f}", delta_color="normal")

        col7, col8 = st.columns(2)
        col7.metric("Total Profit", f"€{total_profit:,.2f}", delta_color="normal")
        col8.metric("Profit Percentage", f"{profit_percentage:.2f}%", delta_color="normal")

    else:
        st.warning("Portfolio is empty. Add transactions to view portfolio details.")

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
    custom_colors = ['#c9a84c', '#27ae7a', '#7a9fc4', '#d4b86a', '#c94c4c', '#a8a49a']

    allocation_rows = []

    if not portfolio_df.empty:
        portfolio_df['Value'] = pd.to_numeric(portfolio_df['Value'], errors='coerce').fillna(0.0)
        for _, row in portfolio_df.iterrows():
            if row['Value'] > 0:
                allocation_rows.append({
                    "Asset": str(row["Ticker"]),
                    "Value": float(row["Value"])
                })

    cash_broker = float(st.session_state.balances.get("cash_balance", 0.0) or 0.0)
    cash_credit = float(st.session_state.balances.get("credit_mutuel_balance", 0.0) or 0.0)
    cash_cic = float(st.session_state.balances.get("cic_balance", 0.0) or 0.0)
    total_cash = cash_broker + cash_credit + cash_cic

    allocation_rows.append({"Asset": "Cash & Banks", "Value": float(total_cash)})

    alloc_df = pd.DataFrame(allocation_rows)
    if 'Value' in alloc_df.columns:
        alloc_df['Value'] = pd.to_numeric(alloc_df['Value'], errors='coerce').fillna(0.0)
    else:
        alloc_df['Value'] = 0.0

    if alloc_df['Value'].sum() == 0:
        st.warning("No positive values found. Add transactions or balances to see allocation.")
    else:
        known_crypto = {"BTC", "BTC-EUR", "BTC-USD", "ETH", "ETH-EUR", "ETH-USD",
                        "SOL", "SOL-EUR", "SOL-USD", "TAO", "TAO-EUR", "XMR", "LTC",
                        "ADA", "DOGE", "BNB"}
        crypto_pattern = r"\b(BTC|ETH|SOL|TAO|XMR|LTC|ADA|DOGE|BNB)\b"

        total_value = alloc_df["Value"].sum()

        crypto_mask = alloc_df["Asset"].str.upper().isin({k.upper() for k in known_crypto}) | alloc_df["Asset"].str.contains(crypto_pattern, case=False, na=False)
        crypto_value = alloc_df.loc[crypto_mask, "Value"].sum()
        cash_value = alloc_df.loc[alloc_df["Asset"] == "Cash & Banks", "Value"].sum()
        stock_value = total_value - crypto_value - cash_value

        crypto_value = float(max(crypto_value, 0.0))
        cash_value = float(max(cash_value, 0.0))
        stock_value = float(max(stock_value, 0.0))

        pct_crypto = (crypto_value / total_value * 100) if total_value > 0 else 0.0
        pct_stocks = (stock_value / total_value * 100) if total_value > 0 else 0.0
        pct_cash = (cash_value / total_value * 100) if total_value > 0 else 0.0

        col1, col2 = st.columns([2.2, 1])

        with col1:
            fig = go.Figure(data=[go.Pie(
                labels=alloc_df["Asset"],
                values=alloc_df["Value"],
                hole=0.55,
                marker=dict(colors=custom_colors, line=dict(color="#080c18", width=2)),
                textposition="outside",
                textinfo="label+percent",
                textfont=dict(family="Inter", size=11, color="#a8a49a"),
                hovertemplate="%{label}<br>€%{value:,.2f}<br>%{percent}<extra></extra>",
                pull=[0.02] * len(alloc_df),
            )])
            fig.update_layout(
                showlegend=False,
                margin=dict(l=20, r=20, t=40, b=20),
                font=dict(family="Inter", size=12, color="#5c5a54"),
                paper_bgcolor="#080c18",
                plot_bgcolor="#080c18",
                title=dict(text="", font=dict(family="Ropa Sans", color="#f0ece0", size=15), x=0),
                height=480,
                annotations=[dict(
                    text=f"<b>€{total_value:,.0f}</b><br><span style='font-size:10px;color:#5c5a54;'>NET WORTH</span>",
                    x=0.5, y=0.5, font=dict(family="Ropa Sans", size=22, color="#f0ece0"),
                    showarrow=False, align="center"
                )]
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown(
                f"""
                <div style="height:480px; display:flex; align-items:center; justify-content:center;">
                    <div style="width:100%; padding-left:12px;">
                        <div style="font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.14em; color:#5c5a54; font-weight:600; margin-bottom:1.2rem;">Category Breakdown</div>
                        <div style="font-family:Inter; font-size:0.85rem; line-height:1;">
                            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #192138; padding:0.65rem 0;">
                                <span style="color:#a8a49a; display:flex; align-items:center; gap:0.5rem;">
                                    <span style="width:8px; height:8px; border-radius:2px; background:#c9a84c; display:inline-block;"></span>Crypto
                                </span>
                                <div style="text-align:right;">
                                    <div style="font-family:'Ropa Sans'; font-size:1rem; color:#f0ece0;">{pct_crypto:.1f}%</div>
                                    <div style="font-family:Inter; font-size:0.65rem; color:#5c5a54;">€{crypto_value:,.0f}</div>
                                </div>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #192138; padding:0.65rem 0;">
                                <span style="color:#a8a49a; display:flex; align-items:center; gap:0.5rem;">
                                    <span style="width:8px; height:8px; border-radius:2px; background:#27ae7a; display:inline-block;"></span>Stocks / ETF
                                </span>
                                <div style="text-align:right;">
                                    <div style="font-family:'Ropa Sans'; font-size:1rem; color:#f0ece0;">{pct_stocks:.1f}%</div>
                                    <div style="font-family:Inter; font-size:0.65rem; color:#5c5a54;">€{stock_value:,.0f}</div>
                                </div>
                            </div>
                            <div style="display:flex; justify-content:space-between; align-items:center; padding:0.65rem 0;">
                                <span style="color:#a8a49a; display:flex; align-items:center; gap:0.5rem;">
                                    <span style="width:8px; height:8px; border-radius:2px; background:#7a9fc4; display:inline-block;"></span>Cash & Banks
                                </span>
                                <div style="text-align:right;">
                                    <div style="font-family:'Ropa Sans'; font-size:1rem; color:#f0ece0;">{pct_cash:.1f}%</div>
                                    <div style="font-family:Inter; font-size:0.65rem; color:#5c5a54;">€{cash_value:,.0f}</div>
                                </div>
                            </div>
                        </div>
                        <div style="margin-top:1.2rem; padding-top:0.8rem; border-top:1px solid rgba(201,168,76,0.3);">
                            <div style="font-family:Inter; font-size:0.6rem; text-transform:uppercase; letter-spacing:0.14em; color:#5c5a54; margin-bottom:0.3rem;">Total Net Worth</div>
                            <div style="font-family:'Ropa Sans'; font-size:1.5rem; color:#c9a84c; letter-spacing:0.03em;">€{total_value:,.2f}</div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
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
# Footer
# -------------------------
st.markdown("---")
