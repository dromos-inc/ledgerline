// Route definitions + typed helpers per resource.

import { api } from "./client";
import type {
  Account,
  AccountCreate,
  ArAgingReport,
  BalanceSheetReport,
  Basis,
  Company,
  CompanyCreate,
  Customer,
  CustomerCreate,
  Invoice,
  InvoiceCreate,
  InvoiceStatus,
  JournalEntry,
  JournalEntryCreate,
  JournalEntryList,
  Payment,
  PaymentCreate,
  ProfitLossReport,
  ReconciliationReport,
  Register,
  TemplateInfo,
  TrialBalanceReport,
} from "./types";

// --- Companies -------------------------------------------------------------

export const companies = {
  list: () => api.get<Company[]>("/companies"),
  get: (id: string) => api.get<Company>(`/companies/${id}`),
  create: (payload: CompanyCreate, template?: string) =>
    api.post<Company>(
      "/companies",
      payload,
      template ? { template } : undefined,
    ),
  templates: () => api.get<TemplateInfo[]>("/companies/templates"),
};

// --- Accounts --------------------------------------------------------------

export const accounts = (companyId: string) => ({
  list: (includeInactive = false) =>
    api.get<Account[]>(`/companies/${companyId}/accounts`, {
      include_inactive: includeInactive,
    }),
  create: (payload: AccountCreate) =>
    api.post<Account>(`/companies/${companyId}/accounts`, payload),
  deactivate: (accountId: number) =>
    api.post<Account>(
      `/companies/${companyId}/accounts/${accountId}/deactivate`,
    ),
  reactivate: (accountId: number) =>
    api.post<Account>(
      `/companies/${companyId}/accounts/${accountId}/reactivate`,
    ),
});

// --- Journal entries -------------------------------------------------------

export interface JournalListQuery {
  start_date?: string;
  end_date?: string;
  account_id?: number;
  search?: string;
  limit?: number;
  offset?: number;
}

export const journal = (companyId: string) => ({
  list: (query?: JournalListQuery) =>
    api.get<JournalEntryList>(
      `/companies/${companyId}/journal-entries`,
      query as Record<string, string | number | undefined>,
    ),
  get: (entryId: number) =>
    api.get<JournalEntry>(`/companies/${companyId}/journal-entries/${entryId}`),
  create: (payload: JournalEntryCreate) =>
    api.post<JournalEntry>(`/companies/${companyId}/journal-entries`, payload),
  post: (entryId: number) =>
    api.post<JournalEntry>(
      `/companies/${companyId}/journal-entries/${entryId}/post`,
    ),
  voidEntry: (entryId: number, memo?: string) =>
    api.post<JournalEntry>(
      `/companies/${companyId}/journal-entries/${entryId}/void`,
      { memo: memo ?? null },
    ),
  deleteDraft: (entryId: number) =>
    api.delete<void>(`/companies/${companyId}/journal-entries/${entryId}`),
});

// --- Register --------------------------------------------------------------

export const register = (companyId: string) => ({
  get: (accountId: number, startDate?: string, endDate?: string) =>
    api.get<Register>(
      `/companies/${companyId}/accounts/${accountId}/register`,
      { start_date: startDate, end_date: endDate },
    ),
});

// --- Reports ---------------------------------------------------------------

export const reports = (companyId: string) => ({
  trialBalance: (asOfDate: string, basis: Basis = "accrual") =>
    api.get<TrialBalanceReport>(
      `/companies/${companyId}/reports/trial-balance`,
      { as_of_date: asOfDate, basis },
    ),
  profitLoss: (
    startDate: string,
    endDate: string,
    basis: Basis = "accrual",
    comparePriorPeriod = false,
  ) =>
    api.get<ProfitLossReport>(`/companies/${companyId}/reports/profit-loss`, {
      start_date: startDate,
      end_date: endDate,
      basis,
      compare_prior_period: comparePriorPeriod,
    }),
  balanceSheet: (asOfDate: string, basis: Basis = "accrual") =>
    api.get<BalanceSheetReport>(
      `/companies/${companyId}/reports/balance-sheet`,
      { as_of_date: asOfDate, basis },
    ),
  arAging: (asOfDate: string, includeZeroBalance = false) =>
    api.get<ArAgingReport>(`/companies/${companyId}/reports/ar-aging`, {
      as_of_date: asOfDate,
      include_zero_balance: includeZeroBalance,
    }),
  reconciliation: (asOfDate: string) =>
    api.get<ReconciliationReport>(
      `/companies/${companyId}/reports/sub-ledger-reconciliation`,
      { as_of_date: asOfDate },
    ),
});

// --- Customers -------------------------------------------------------------

export const customers = (companyId: string) => ({
  list: (includeInactive = false, query?: string) =>
    api.get<Customer[]>(`/companies/${companyId}/customers`, {
      include_inactive: includeInactive,
      q: query,
    }),
  get: (cid: number) =>
    api.get<Customer>(`/companies/${companyId}/customers/${cid}`),
  create: (payload: CustomerCreate) =>
    api.post<Customer>(`/companies/${companyId}/customers`, payload),
  update: (cid: number, payload: Partial<CustomerCreate>) =>
    api.patch<Customer>(`/companies/${companyId}/customers/${cid}`, payload),
  deactivate: (cid: number) =>
    api.post<Customer>(`/companies/${companyId}/customers/${cid}/deactivate`),
  reactivate: (cid: number) =>
    api.post<Customer>(`/companies/${companyId}/customers/${cid}/reactivate`),
});

// --- Invoices --------------------------------------------------------------

export interface InvoiceListQuery {
  customer_id?: number;
  status?: InvoiceStatus;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export const invoices = (companyId: string) => ({
  list: (query?: InvoiceListQuery) =>
    api.get<Invoice[]>(
      `/companies/${companyId}/invoices`,
      query as Record<string, string | number | undefined>,
    ),
  get: (iid: number) =>
    api.get<Invoice>(`/companies/${companyId}/invoices/${iid}`),
  create: (payload: InvoiceCreate) =>
    api.post<Invoice>(`/companies/${companyId}/invoices`, payload),
  update: (iid: number, payload: Partial<InvoiceCreate>) =>
    api.patch<Invoice>(`/companies/${companyId}/invoices/${iid}`, payload),
  post: (iid: number) =>
    api.post<Invoice>(`/companies/${companyId}/invoices/${iid}/post`),
  voidInvoice: (iid: number) =>
    api.post<Invoice>(`/companies/${companyId}/invoices/${iid}/void`),
  delete: (iid: number) =>
    api.delete<void>(`/companies/${companyId}/invoices/${iid}`),
});

// --- Payments --------------------------------------------------------------

export interface PaymentListQuery {
  customer_id?: number;
  start_date?: string;
  end_date?: string;
  limit?: number;
  offset?: number;
}

export const payments = (companyId: string) => ({
  list: (query?: PaymentListQuery) =>
    api.get<Payment[]>(
      `/companies/${companyId}/payments`,
      query as Record<string, string | number | undefined>,
    ),
  get: (pid: number) =>
    api.get<Payment>(`/companies/${companyId}/payments/${pid}`),
  create: (payload: PaymentCreate) =>
    api.post<Payment>(`/companies/${companyId}/payments`, payload),
  voidPayment: (pid: number) =>
    api.post<Payment>(`/companies/${companyId}/payments/${pid}/void`),
});
