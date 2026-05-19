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

-- RLS
ALTER TABLE public.allocation_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_categories ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS "Allow all" ON public.asset_categories FOR ALL TO anon USING (true) WITH CHECK (true);
