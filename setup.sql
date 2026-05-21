-- Run all of this in your Supabase SQL Editor (supabase.com > your project > SQL Editor)

CREATE TABLE IF NOT EXISTS balances (
  id INTEGER PRIMARY KEY DEFAULT 1,
  cash_balance FLOAT DEFAULT 0,
  credit_mutuel_balance FLOAT DEFAULT 0,
  cic_balance FLOAT DEFAULT 0,
  CONSTRAINT single_row CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS balances_history (
  id BIGSERIAL PRIMARY KEY,
  date DATE UNIQUE NOT NULL,
  cash FLOAT DEFAULT 0,
  credit_mutuel FLOAT DEFAULT 0,
  cic FLOAT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS transactions (
  id BIGSERIAL PRIMARY KEY,
  date DATE,
  time TEXT,
  type TEXT,
  ticker TEXT,
  quantity FLOAT DEFAULT 0,
  purchase_price FLOAT DEFAULT 0,
  fee_amount FLOAT DEFAULT 0,
  fee_unit TEXT DEFAULT 'None',
  income FLOAT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS portfolio_value_history (
  id BIGSERIAL PRIMARY KEY,
  date DATE UNIQUE NOT NULL,
  total_value FLOAT DEFAULT 0,
  no_investment_value FLOAT
);

CREATE TABLE IF NOT EXISTS cashflow (
  id BIGSERIAL PRIMARY KEY,
  category TEXT,
  type TEXT,
  amount FLOAT DEFAULT 0,
  notes TEXT DEFAULT ''
);

-- allocation_targets: run this to migrate existing table
ALTER TABLE public.allocation_targets
  ADD COLUMN IF NOT EXISTS etf_pct FLOAT DEFAULT 50,
  ADD COLUMN IF NOT EXISTS max_single_pct FLOAT DEFAULT 5;

-- OR if creating fresh:
CREATE TABLE IF NOT EXISTS allocation_targets (
  id INTEGER PRIMARY KEY DEFAULT 1,
  etf_pct FLOAT DEFAULT 50,
  max_single_pct FLOAT DEFAULT 5,
  CONSTRAINT single_row_alloc CHECK (id = 1)
);

CREATE TABLE IF NOT EXISTS asset_categories (
  ticker TEXT PRIMARY KEY,
  category TEXT NOT NULL CHECK (category IN ('ETF', 'Stock', 'Crypto'))
);

CREATE TABLE IF NOT EXISTS planning_settings (
  id INTEGER PRIMARY KEY DEFAULT 1,
  hourly_rate FLOAT DEFAULT 0,
  goal_amount FLOAT DEFAULT 100000,
  target_date DATE DEFAULT '2030-01-01',
  expected_return FLOAT DEFAULT 7,
  CONSTRAINT single_row_planning CHECK (id = 1)
);

-- If the table already exists, run this to add the new column:
ALTER TABLE public.planning_settings ADD COLUMN IF NOT EXISTS expected_return FLOAT DEFAULT 7;

CREATE TABLE IF NOT EXISTS loans (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL DEFAULT 'Loan',
  principal FLOAT DEFAULT 0,
  annual_rate FLOAT DEFAULT 0,
  monthly_payment FLOAT DEFAULT 0,
  start_date DATE NOT NULL DEFAULT CURRENT_DATE,
  notes TEXT DEFAULT ''
);

-- RLS
ALTER TABLE public.allocation_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "Allow all" ON public.asset_categories FOR ALL TO anon USING (true) WITH CHECK (true);
