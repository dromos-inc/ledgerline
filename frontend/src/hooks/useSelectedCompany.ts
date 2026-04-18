// Selected-company state. Persisted in localStorage so a reload keeps
// the user where they were.

import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "ledgerline.selected_company";

export function useSelectedCompany(): [
  string | null,
  (id: string | null) => void,
] {
  const [companyId, setCompanyId] = useState<string | null>(() => {
    if (typeof localStorage === "undefined") return null;
    return localStorage.getItem(STORAGE_KEY);
  });

  useEffect(() => {
    if (typeof localStorage === "undefined") return;
    if (companyId) {
      localStorage.setItem(STORAGE_KEY, companyId);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, [companyId]);

  const clear = useCallback(() => setCompanyId(null), []);

  return [companyId, (id) => (id ? setCompanyId(id) : clear())];
}
