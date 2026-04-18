// Hand-rolled types that mirror the FastAPI OpenAPI schema.
// Phase-2 TODO: generate from /openapi.json via openapi-typescript.

export type AccountType =
  | "asset"
  | "liability"
  | "equity"
  | "income"
  | "expense";

export type NormalBalance = "debit" | "credit";

export type EntityType = "schedule_c" | "s_corp";

export type TaxBasis = "cash" | "accrual";

export type JournalStatus = "draft" | "posted" | "void";

export type JournalSource = "manual" | "reversal";

export type Basis = "cash" | "accrual";

// --- Companies -------------------------------------------------------------

export interface Company {
  id: string;
  name: string;
  entity_type: EntityType;
  tax_basis: TaxBasis;
  base_currency: string;
  fiscal_year_start: string;
  created_at: string;
  updated_at: string;
}

export interface CompanyCreate {
  id: string;
  name: string;
  entity_type?: EntityType;
  tax_basis?: TaxBasis;
  base_currency?: string;
  fiscal_year_start?: string;
}

export interface TemplateInfo {
  key: string;
  label: string;
  description: string;
  account_count: number;
}

// --- Accounts --------------------------------------------------------------

export interface Account {
  id: number;
  code: string;
  name: string;
  type: AccountType;
  subtype: string | null;
  parent_id: number | null;
  is_active: boolean;
  description: string | null;
  normal_balance: NormalBalance;
}

export interface AccountCreate {
  code: string;
  name: string;
  type: AccountType;
  subtype?: string | null;
  parent_id?: number | null;
  description?: string | null;
}

// --- Journal entries -------------------------------------------------------

export interface JournalLine {
  id: number;
  line_number: number;
  account_id: number;
  debit_cents: number;
  credit_cents: number;
  memo: string | null;
}

export interface JournalEntry {
  id: number;
  entry_date: string;
  posting_date: string;
  reference: string | null;
  memo: string | null;
  source_type: JournalSource;
  source_id: number | null;
  status: JournalStatus;
  created_by: string | null;
  reversal_of_id: number | null;
  created_at: string;
  updated_at: string;
  lines: JournalLine[];
}

export interface JournalEntryList {
  entries: JournalEntry[];
  total: number;
}

export interface JournalLineCreate {
  account_id: number;
  debit_cents: number;
  credit_cents: number;
  memo?: string | null;
}

export interface JournalEntryCreate {
  entry_date: string;
  posting_date?: string | null;
  reference?: string | null;
  memo?: string | null;
  lines: JournalLineCreate[];
}

// --- Register --------------------------------------------------------------

export interface RegisterRow {
  entry_id: number;
  line_id: number;
  entry_date: string;
  posting_date: string;
  reference: string | null;
  memo: string | null;
  line_memo: string | null;
  debit_cents: number;
  credit_cents: number;
  running_balance_cents: number;
}

export interface Register {
  account_id: number;
  account_code: string;
  account_name: string;
  opening_balance_cents: number;
  rows: RegisterRow[];
  closing_balance_cents: number;
}

// --- Reports ---------------------------------------------------------------

export interface TrialBalanceRow {
  account_id: number;
  account_code: string;
  account_name: string;
  account_type: AccountType;
  debit_cents: number;
  credit_cents: number;
}

export interface TrialBalanceReport {
  as_of_date: string;
  basis: Basis;
  rows: TrialBalanceRow[];
  total_debit_cents: number;
  total_credit_cents: number;
  balanced: boolean;
}

export interface PLSectionRow {
  account_id: number;
  account_code: string;
  account_name: string;
  amount_cents: number;
  prior_amount_cents: number | null;
}

export interface PLSection {
  label: string;
  rows: PLSectionRow[];
  subtotal_cents: number;
  prior_subtotal_cents: number | null;
}

export interface ProfitLossReport {
  start_date: string;
  end_date: string;
  basis: Basis;
  income: PLSection;
  expenses: PLSection;
  net_income_cents: number;
  prior_net_income_cents: number | null;
}

export interface BSSectionRow {
  account_id: number;
  account_code: string;
  account_name: string;
  balance_cents: number;
}

export interface BSSection {
  label: string;
  rows: BSSectionRow[];
  subtotal_cents: number;
}

export interface BalanceSheetReport {
  as_of_date: string;
  basis: Basis;
  assets: BSSection;
  liabilities: BSSection;
  equity: BSSection;
  equation_difference_cents: number;
  balanced: boolean;
}
