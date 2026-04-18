// Route definitions + typed helpers per resource.

import { api } from "./client";
import type {
  Account,
  AccountCreate,
  BalanceSheetReport,
  Basis,
  Company,
  CompanyCreate,
  JournalEntry,
  JournalEntryCreate,
  JournalEntryList,
  ProfitLossReport,
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
});
