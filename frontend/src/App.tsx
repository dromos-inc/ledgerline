import { useQuery } from "@tanstack/react-query";
import { Layout } from "./components/Layout";

interface Health {
  status: string;
  version: string;
}

export function App() {
  const { data, isLoading, isError, error } = useQuery<Health>({
    queryKey: ["health"],
    queryFn: async () => {
      const resp = await fetch("/api/v1/../health");
      if (!resp.ok) {
        throw new Error(`/health returned ${resp.status}`);
      }
      return resp.json();
    },
  });

  return (
    <Layout>
      <div className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-3xl font-semibold tracking-tight">Ledgerline</h1>
        <p className="mt-3 text-ink-500">
          A lean, keyboard-first double-entry accounting platform.
        </p>
        <section className="mt-10 rounded border border-ink-200 bg-white p-5">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-400">
            Backend status
          </h2>
          {isLoading && (
            <p className="mt-2 font-mono text-sm text-ink-500">
              Connecting to localhost:8787…
            </p>
          )}
          {isError && (
            <p className="mt-2 font-mono text-sm text-danger">
              Error: {(error as Error)?.message ?? "unknown"}
            </p>
          )}
          {data && (
            <p className="mt-2 font-mono text-sm text-success">
              OK · v{data.version}
            </p>
          )}
          <p className="mt-4 text-sm text-ink-500">
            Route the browser to <code className="font-mono">/api/v1/docs</code> for
            the OpenAPI spec. Commands tables and the rest of the UI land in
            later commits.
          </p>
        </section>
      </div>
    </Layout>
  );
}
