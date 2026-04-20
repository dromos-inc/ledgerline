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

export type JournalSource = "manual" | "reversal" | "invoice" | "payment";

export type Basis = "cash" | "accrual";

export type InvoiceStatus = "draft" | "sent" | "partial" | "paid" | "void";

export type BillStatus = "draft" | "open" | "partial" | "paid" | "void";

export type PaymentStatus = "posted" | "void";

export type PaymentMethod = "check" | "ach" | "card" | "wire" | "cash" | "other";

export type Terms = "net_15" | "net_30" | "net_60" | "due_on_receipt" | "custom";

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

// --- Customers -------------------------------------------------------------

export interface Customer {
  id: number;
  code: string;
  name: string;
  company: string | null;
  email: string | null;
  phone: string | null;
  tax_id: string | null;
  billing_address: string | null;
  shipping_address: string | null;
  default_terms: Terms;
  default_income_account_id: number | null;
  default_tax_code_id: number | null;
  is_active: boolean;
  notes: string | null;
}

export interface CustomerCreate {
  code: string;
  name: string;
  company?: string | null;
  email?: string | null;
  phone?: string | null;
  tax_id?: string | null;
  billing_address?: string | null;
  shipping_address?: string | null;
  default_terms?: Terms;
  default_income_account_id?: number | null;
  default_tax_code_id?: number | null;
  notes?: string | null;
}

// --- Invoices --------------------------------------------------------------

export interface InvoiceLine {
  id: number;
  line_number: number;
  item_id: number | null;
  account_id: number;
  description: string | null;
  quantity_milli: number;
  unit_price_cents: number;
  tax_code_id: number | null;
  tax_amount_cents: number;
  amount_cents: number;
}

export interface InvoiceLineCreate {
  item_id?: number | null;
  account_id?: number | null;
  description?: string | null;
  quantity_milli: number;
  unit_price_cents: number;
  tax_code_id?: number | null;
}

export interface Invoice {
  id: number;
  number: string;
  customer_id: number;
  invoice_date: string;
  due_date: string;
  terms: Terms;
  reference: string | null;
  memo: string | null;
  subtotal_cents: number;
  tax_total_cents: number;
  total_cents: number;
  amount_paid_cents: number;
  balance_cents: number;
  status: InvoiceStatus;
  journal_entry_id: number | null;
  sent_at: string | null;
  lines: InvoiceLine[];
}

export interface InvoiceCreate {
  number: string;
  customer_id: number;
  invoice_date: string;
  due_date: string;
  terms?: Terms;
  reference?: string | null;
  memo?: string | null;
  lines: InvoiceLineCreate[];
}

// --- Payments --------------------------------------------------------------

export interface PaymentApplication {
  id: number;
  payment_id: number;
  invoice_id: number;
  amount_cents: number;
  discount_cents: number;
  writeoff_cents: number;
}

export interface PaymentApplicationCreate {
  invoice_id: number;
  amount_cents: number;
  discount_cents?: number;
  writeoff_cents?: number;
}

export interface Payment {
  id: number;
  customer_id: number;
  payment_date: string;
  amount_cents: number;
  deposit_account_id: number;
  method: PaymentMethod | null;
  reference: string | null;
  memo: string | null;
  journal_entry_id: number;
  status: PaymentStatus;
  applied_cents: number;
  unapplied_cents: number;
  applications: PaymentApplication[];
}

export interface PaymentCreate {
  customer_id: number;
  payment_date: string;
  amount_cents: number;
  deposit_account_id: number;
  method?: PaymentMethod | null;
  reference?: string | null;
  memo?: string | null;
  applications?: PaymentApplicationCreate[];
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

// --- AR aging --------------------------------------------------------------

export interface AgingInvoiceDetail {
  invoice_id: number;
  number: string;
  invoice_date: string;
  due_date: string;
  days_overdue: number;
  bucket: string;
  balance_cents: number;
  total_cents: number;
  amount_paid_cents: number;
}

export interface AgingRow {
  customer_id: number;
  customer_code: string;
  customer_name: string;
  current_cents: number;
  d1_30_cents: number;
  d31_60_cents: number;
  d61_90_cents: number;
  over_90_cents: number;
  total_cents: number;
  invoices: AgingInvoiceDetail[];
}

export interface AgingTotals {
  current_cents: number;
  d1_30_cents: number;
  d31_60_cents: number;
  d61_90_cents: number;
  over_90_cents: number;
  total_cents: number;
}

export interface ArAgingReport {
  as_of_date: string;
  rows: AgingRow[];
  totals: AgingTotals;
}

export interface ReconciliationReport {
  as_of_date: string;
  ar_control_account_id: number | null;
  ar_control_account_code: string | null;
  ar_control_balance_cents: number;
  ar_sub_ledger_cents: number;
  ar_unapplied_credits_cents: number;
  ar_difference_cents: number;
  ap_control_account_id: number | null;
  ap_control_account_code: string | null;
  ap_control_balance_cents: number;
  ap_sub_ledger_cents: number;
  ap_unapplied_credits_cents: number;
  ap_difference_cents: number;
}

// --- Vendors --------------------------------------------------------------

export interface Vendor {
  id: number;
  code: string;
  name: string;
  company: string | null;
  email: string | null;
  phone: string | null;
  tax_id: string | null;
  billing_address: string | null;
  default_terms: Terms;
  default_expense_account_id: number | null;
  is_active: boolean;
  is_1099: boolean;
  notes: string | null;
}

export interface VendorCreate {
  code: string;
  name: string;
  company?: string | null;
  email?: string | null;
  phone?: string | null;
  tax_id?: string | null;
  billing_address?: string | null;
  default_terms?: Terms;
  default_expense_account_id?: number | null;
  is_1099?: boolean;
  notes?: string | null;
}

// --- Bills ----------------------------------------------------------------

export interface BillLine {
  id: number;
  line_number: number;
  item_id: number | null;
  account_id: number;
  description: string | null;
  quantity_milli: number;
  unit_price_cents: number;
  tax_code_id: number | null;
  tax_amount_cents: number;
  amount_cents: number;
}

export interface BillLineCreate {
  item_id?: number | null;
  account_id?: number | null;
  description?: string | null;
  quantity_milli: number;
  unit_price_cents: number;
  tax_code_id?: number | null;
}

export interface Bill {
  id: number;
  number: string;
  vendor_id: number;
  bill_date: string;
  due_date: string;
  terms: Terms;
  reference: string | null;
  memo: string | null;
  subtotal_cents: number;
  tax_total_cents: number;
  total_cents: number;
  amount_paid_cents: number;
  balance_cents: number;
  status: BillStatus;
  journal_entry_id: number | null;
  approved_at: string | null;
  approved_by: string | null;
  lines: BillLine[];
}

export interface BillCreate {
  number: string;
  vendor_id: number;
  bill_date: string;
  due_date: string;
  terms?: Terms;
  reference?: string | null;
  memo?: string | null;
  lines: BillLineCreate[];
}

// --- Bill payments --------------------------------------------------------

export interface BillPaymentApplication {
  id: number;
  bill_payment_id: number;
  bill_id: number;
  amount_cents: number;
  discount_cents: number;
  writeoff_cents: number;
}

export interface BillPaymentApplicationCreate {
  bill_id: number;
  amount_cents: number;
  discount_cents?: number;
  writeoff_cents?: number;
}

export interface BillPayment {
  id: number;
  vendor_id: number;
  payment_date: string;
  amount_cents: number;
  payout_account_id: number;
  method: PaymentMethod | null;
  reference: string | null;
  memo: string | null;
  journal_entry_id: number;
  status: PaymentStatus;
  applied_cents: number;
  unapplied_cents: number;
  applications: BillPaymentApplication[];
}

export interface BillPaymentCreate {
  vendor_id: number;
  payment_date: string;
  amount_cents: number;
  payout_account_id: number;
  method?: PaymentMethod | null;
  reference?: string | null;
  memo?: string | null;
  applications?: BillPaymentApplicationCreate[];
}

// --- AP aging -------------------------------------------------------------

export interface AgingBillDetail {
  bill_id: number;
  number: string;
  bill_date: string;
  due_date: string;
  days_overdue: number;
  bucket: string;
  balance_cents: number;
  total_cents: number;
  amount_paid_cents: number;
}

export interface ApAgingRow {
  vendor_id: number;
  vendor_code: string;
  vendor_name: string;
  current_cents: number;
  d1_30_cents: number;
  d31_60_cents: number;
  d61_90_cents: number;
  over_90_cents: number;
  total_cents: number;
  bills: AgingBillDetail[];
}

export interface ApAgingReport {
  as_of_date: string;
  rows: ApAgingRow[];
  totals: AgingTotals;
}