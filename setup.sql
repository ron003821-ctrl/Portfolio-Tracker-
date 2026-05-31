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
  notes TEXT DEFAULT '',
  loan_type TEXT DEFAULT 'standard',
  monthly_borrow FLOAT DEFAULT 0,
  study_end_date DATE,
  repayment_years FLOAT DEFAULT 10
);

-- If loans table already exists, add the new columns:
ALTER TABLE public.loans ADD COLUMN IF NOT EXISTS loan_type TEXT DEFAULT 'standard';
ALTER TABLE public.loans ADD COLUMN IF NOT EXISTS monthly_borrow FLOAT DEFAULT 0;
ALTER TABLE public.loans ADD COLUMN IF NOT EXISTS study_end_date DATE;
ALTER TABLE public.loans ADD COLUMN IF NOT EXISTS repayment_years FLOAT DEFAULT 10;

-- RLS (run for each table that gives "row-level security policy" errors)
ALTER TABLE public.allocation_targets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.loans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.planning_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cashflow ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.balances_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_value_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS "Allow all" ON public.asset_categories       FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all" ON public.loans                   FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all" ON public.planning_settings       FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all" ON public.cashflow                FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all" ON public.transactions            FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all" ON public.balances                FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all" ON public.balances_history        FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all" ON public.portfolio_value_history FOR ALL TO anon USING (true) WITH CHECK (true);
CREATE POLICY IF NOT EXISTS "Allow all" ON public.allocation_targets      FOR ALL TO anon USING (true) WITH CHECK (true);
