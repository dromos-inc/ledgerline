// Typed API client. Thin wrapper over fetch that extracts the JSON body,
// throws on non-2xx with the server's detail message, and takes care of
// JSON content headers.

const API_BASE = "/api/v1";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    const message =
      typeof detail === "string"
        ? detail
        : // @ts-expect-error — `detail` may be {detail: string} or other shape.
          (detail?.detail ?? `HTTP ${status}`);
    super(String(message));
    this.status = status;
    this.detail = detail;
  }
}

type Method = "GET" | "POST" | "PATCH" | "DELETE";

interface RequestOptions {
  method?: Method;
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
}

async function request<T>(
  path: string,
  { method = "GET", body, query }: RequestOptions = {},
): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  const init: RequestInit = { method };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
    init.headers = { "Content-Type": "application/json" };
  }
  const resp = await fetch(url.toString(), init);
  if (resp.status === 204) {
    return undefined as T;
  }
  const text = await resp.text();
  const parsed = text ? JSON.parse(text) : undefined;
  if (!resp.ok) {
    throw new ApiError(resp.status, parsed);
  }
  return parsed as T;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"]) =>
    request<T>(path, { query }),
  post: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    request<T>(path, { method: "POST", body, query }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

/** Build a CSV download URL for an /export endpoint. */
export function exportUrl(
  path: string,
  query?: Record<string, string | number | boolean | null | undefined>,
): string {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, String(value));
      }
    }
  }
  return url.toString();
}
