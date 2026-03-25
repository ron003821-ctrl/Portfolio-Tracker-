import streamlit as st
from supabase import create_client
import yfinance as yf
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, time, date

# -------------------------
# Styling
# -------------------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    body, .main {
        font-family: 'Inter', sans-serif;
        background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
        color: #f7fafc;
    }

    h1 {
        color: #f7fafc;
        font-weight: 700;
        font-size: 2.5rem;
        margin-bottom: 1rem;
        text-shadow: 0 2px 4px rgba(0,0,0,0.3);
    }

    h2 {
        color: #4fd1c5;
        font-weight: 600;
        font-size: 1.75rem;
        background: linear-gradient(90deg, #4fd1c5, #38b2ac);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #2d3748 0%, #4a5568 100%);
        border-right: 1px solid #4fd1c5;
        padding: 1.5rem;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        border-radius: 0 12px 12px 0;
        transition: box-shadow 0.3s ease-in-out;
    }

    .sidebar .sidebar-content:hover {
        box-shadow: 0 6px 25px rgba(0,0,0,0.5);
    }

    .stButton>button {
        background: linear-gradient(135deg, #4a5568 0%, #4fd1c5 100%);
        color: #f7fafc;
        border-radius: 12px;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease-in-out;
        border: none;
        box-shadow: 0 4px 15px rgba(0,0,0,0.4);
    }

    .stButton>button:hover {
        background: linear-gradient(135deg, #4fd1c5 0%, #38b2ac 100%);
        transform: translateY(-2px) scale(1.02);
        box-shadow: 0 6px 20px rgba(0,0,0,0.5);
    }

    .stMetric {
        background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
        border-radius: 16px;
        padding: 1.5rem;
        box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        margin-bottom: 1.5rem;
        transition: transform 0.2s ease-in-out, box-shadow 0.2s ease-in-out;
        border: 1px solid rgba(79,209,197,0.3);
        color: #f7fafc;
    }

    .stMetric:hover {
        transform: translateY(-1px);
        box-shadow: 0 8px 25px rgba(0,0,0,0.4);
    }

    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: box-shadow 0.3s ease-in-out;
        color: #f7fafc;
    }

    .stDataFrame:hover {
        box-shadow: 0 6px 20px rgba(0,0,0,0.4);
    }

    .st-expander {
        background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        transition: all 0.3s ease-in-out;
        border: 1px solid rgba(79,209,197,0.3);
        color: #f7fafc;
    }

    .st-expander:hover {
        box-shadow: 0 6px 20px rgba(0,0,0,0.4);
        transform: translateY(-1px);
    }

    .stTextInput, .stSelectbox, .stNumberInput, .stDateInput {
        background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
        border: 1px solid #4fd1c5;
        border-radius: 10px;
        padding: 0.75rem;
        transition: all 0.3s ease-in-out;
        color: #f7fafc;
    }

    .stTextInput>input:focus, .stNumberInput>input:focus, .stDateInput>input:focus {
        border-color: #4fd1c5;
        box-shadow: 0 0 0 3px rgba(79,209,197,0.2);
        transform: scale(1.02);
    }

    .stCaption {
        color: #a0aec0;
        font-size: 0.9rem;
        font-style: italic;
    }

    .stAlert {
        background: linear-gradient(135deg, #4b2e2e 0%, #3b1f1f 100%);
        color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 10px;
        padding: 1.25rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }

    .stTabs [role="tab"] {
        background: linear-gradient(135deg, #2d3748 0%, #4a5568 100%);
        border: 1px solid #4fd1c5;
        border-radius: 10px 10px 0 0;
        padding: 0.75rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s ease-in-out;
        margin-right: 0.5rem;
        color: #f7fafc;
    }

    .stTabs [role="tab"]:hover {
        background: linear-gradient(135deg, #4a5d70 0%, #2d3748 100%);
        transform: translateY(-1px);
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }

    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #4a5d70 0%, #2d3748 100%);
        border-bottom: 2px solid #4fd1c5;
        color: #4fd1c5;
    }

    .main .block-container {
        transition: opacity 0.3s ease-in-out;
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
    st.title("Portfolio Tracker")
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Login")
        password = st.text_input("Wachtwoord", type="password")
        if st.button("Inloggen", use_container_width=True):
            if password == st.secrets["auth"]["password"]:
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("Ongeldig wachtwoord")
    st.stop()

# -------------------------
# App title
# -------------------------
st.title("Portfolio Tracker Dashboard")

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
st.sidebar.title("📋 Portfolio Dashboard")
st.sidebar.markdown("---")

with st.sidebar.expander("💰 Broker & Bank Balances", expanded=False):
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
    today = datetime.today().date()
    save_balance_history_entry(today, cash_balance_input, credit_mutuel_balance_input, cic_balance_input)
    st.session_state.balances_history = load_balances_history()
    balances_changed = True

# -------------------------
# Sidebar - Add Transaction
# -------------------------
with st.sidebar.expander("🧾 Add Transaction", expanded=False):
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
with st.sidebar.expander("✏️ Edit/Delete Transaction", expanded=False):
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
with st.sidebar.expander("📊 Cashflow Tracker", expanded=False):
    st.subheader("➕ Add Cashflow Entry")
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

    st.subheader("✏️ Edit/Delete Existing Entries")
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

# -------------------------
# Refresh button
# -------------------------
if st.button("Refresh Prices"):
    st.cache_data.clear()
    st.rerun()

# -------------------------
# Navigation
# -------------------------
st.sidebar.title("📊 Navigation")

page = st.sidebar.radio(
    "Select a section:",
    [
        " Cashflow",
        " Historical Portfolio Value",
        " Portfolio Overview",
        " Asset Allocation",
        " Historical Price Charts"
    ],
)

portfolio_df, realized, unrealized, total_profit, profit_percentage = compute_portfolio()

# -------------------------
# Tab 1: Cashflow
# -------------------------
if page == " Cashflow":
    st.header(" Cashflow")

    if not st.session_state.cashflow.empty:
        income_df = st.session_state.cashflow[st.session_state.cashflow["Amount"] > 0].sort_values(by="Amount", ascending=False)
        expense_df = st.session_state.cashflow[st.session_state.cashflow["Amount"] < 0].sort_values(by="Amount", ascending=True)

        total_income = income_df["Amount"].sum()
        total_expenses = expense_df["Amount"].sum()
        net_cashflow = total_income + total_expenses
        net_color = "green" if net_cashflow >= 0 else "red"

        st.markdown(
            f"""
            <div style="text-align:center; font-size:22px; font-weight:600; line-height:1.6;">
                 Total Income: €{total_income:,.2f} &nbsp;&nbsp;|&nbsp;&nbsp;
                 Total Expenses: €{abs(total_expenses):,.2f}
            </div>
            <div style="text-align:center; font-size:30px; font-weight:700; margin-top:10px;">
                 Net Cashflow: <span style="color:{net_color};">€{net_cashflow:,.2f}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("###  Income")
            if not income_df.empty:
                st.dataframe(
                    income_df[CF_DISPLAY_COLS]
                    .style.format({"Amount": "€{:.2f}"})
                    .set_properties(**{"text-align": "left"})
                    .set_table_styles(
                        [{"selector": "thead th", "props": [("background-color", "#e6ffe6")]}]
                    ),
                    use_container_width=True
                )
            else:
                st.info("No income entries yet.")

        with col2:
            st.markdown("###  Expenses")
            if not expense_df.empty:
                expense_display = expense_df[CF_DISPLAY_COLS].copy()
                expense_display["Amount"] = expense_display["Amount"].abs()
                st.dataframe(
                    expense_display
                    .style.format({"Amount": "€{:.2f}"})
                    .set_properties(**{"text-align": "left"})
                    .set_table_styles(
                        [{"selector": "thead th", "props": [("background-color", "#ffe6e6")]}]
                    ),
                    use_container_width=True
                )
            else:
                st.info("No expenses yet.")

    else:
        st.info("No cashflow data available yet.")

# -------------------------
# Tab 2: Historical Portfolio Value
# -------------------------
elif page == " Historical Portfolio Value":
    st.header(" Historical Portfolio Value")
    st.markdown(
        """
        This chart logs the **total portfolio value** once per day (assets + broker cash + bank balances).
        It also compares it to a **'No Investment'** baseline — what your wealth would be
        if you had kept your initial money in cash instead of buying assets.
        """
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

    today = datetime.today().date()
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

        fig_total = px.line(
            plot_df,
            x="Date",
            y=["Total Portfolio Value (€)", "No Investment (€)"],
            title="Portfolio Value vs. No Investment (Daily)",
            labels={"Date": "Date", "value": "Total (€)", "variable": "Scenario"},
        )
        fig_total.update_traces(mode="lines+markers")
        fig_total.update_layout(
            hovermode="x unified",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(title="", orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig_total, use_container_width=True)

        latest = plot_df["Total Portfolio Value (€)"].iloc[-1]
        baseline = plot_df["No Investment (€)"].iloc[-1]
        delta_vs_baseline = latest - baseline
        pct_vs_baseline = (delta_vs_baseline / baseline) * 100 if baseline != 0 else 0

        col1, col2 = st.columns(2)
        col1.metric("Current Portfolio Value", f"€{latest:,.2f}")
        col2.metric("No Investment (Cash Equivalent)", f"€{baseline:,.2f}")

        st.markdown(
            f"<h3 style='text-align:center;'>Difference vs. No Investment: "
            f"<span style='color:{'green' if delta_vs_baseline >= 0 else 'red'};'>€{delta_vs_baseline:,.2f} ({pct_vs_baseline:.2f}%)</span></h3>",
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("🏦 Compare With Bank Savings")

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
            <div style="text-align:center;">
                <h4>If your money had earned <b>{bank_interest_rate:.2f}%</b> this year in a bank account:</h4>
                <h3>🏦 You would now have <span style="color:green;">€{total_with_interest:,.2f}</span></h3>
                <p>(Interest gain: +€{interest_gain:,.2f})</p>
            </div>
            """,
            unsafe_allow_html=True
        )

# -------------------------
# Tab 3: Portfolio Overview
# -------------------------
elif page == " Portfolio Overview":
    st.header(" Portfolio Overview")

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

    st.header("All Transactions")
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
# Tab 4: Asset Allocation
# -------------------------
elif page == " Asset Allocation":
    st.header(" Asset Allocation")
    custom_colors = ['#4fd1c5', '#81e6d9', '#a3bffa', '#f6ad55', '#ed8936', '#63b3ed']

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
            fig = px.pie(
                alloc_df,
                values="Value",
                names="Asset",
                title="Asset Allocation (Including Cash & Banks)",
                color_discrete_sequence=custom_colors
            )
            fig.update_traces(textposition="inside", textinfo="percent+label", hovertemplate="%{label}: €%{value:,.2f} (%{percent})")
            fig.update_layout(
                showlegend=True,
                legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="center", x=0.5),
                margin=dict(l=20, r=20, t=60, b=80),
                font=dict(size=12),
                paper_bgcolor="rgba(0,0,0,0)",
                width=None,
                height=520
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown(
                f"""
                <div style="height:520px; display:flex; align-items:center; justify-content:center;">
                    <div style="width:100%; padding-left:12px;">
                        <h3 style="margin-bottom:12px;">📊 Global Allocation</h3>
                        <div style="font-size:16px; line-height:1.8;">
                            <div><span style="font-weight:600;">Crypto :</span> {pct_crypto:.2f}% — €{crypto_value:,.2f}</div>
                            <div><span style="font-weight:600;">Actions / ETF :</span> {pct_stocks:.2f}% — €{stock_value:,.2f}</div>
                            <div><span style="font-weight:600;">Cash & Banks :</span> {pct_cash:.2f}% — €{cash_value:,.2f}</div>
                        </div>
                        <div style="margin-top:12px; color:#9aa4ad; font-size:13px;">
                            Total: €{total_value:,.2f}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

# -------------------------
# Tab 5: Historical Price Charts
# -------------------------
elif page == " Historical Price Charts":
    st.header(" Historical Price Charts")
    if not portfolio_df.empty:
        selected_ticker = st.selectbox("Select a Ticker for Historical Chart", options=portfolio_df['Ticker'].tolist(), key="hist_ticker")
        period = st.selectbox("Time Period", options=['6mo', '1y', '2y', '5y', 'max'], key="hist_period")

        if selected_ticker:
            with st.spinner("Fetching historical data..."):
                hist_data = get_historical_data(selected_ticker, period=period)

            if not hist_data.empty:
                avg_purchase = portfolio_df[portfolio_df['Ticker'] == selected_ticker]['Average Purchase Price'].iloc[0]

                fig = px.line(hist_data, x='Date', y='Close', title=f"{selected_ticker} Price History ({period})",
                              labels={'Close': 'Price (EUR)', 'Date': 'Date'})
                fig.add_hline(y=avg_purchase, line_dash="dash", line_color="red",
                              annotation_text=f"Avg Purchase: €{avg_purchase:.2f}", annotation_position="top left")
                fig.update_layout(xaxis_title="Date", yaxis_title="Price (EUR)", hovermode='x unified',
                                  font=dict(size=12), plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
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
