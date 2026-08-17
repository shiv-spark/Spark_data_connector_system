import { FormEvent, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Table2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, RowSkeleton } from "@/components/console/Panel";

interface ColumnInfo {
  name: string;
  type: string;
}

export const DataPreview = () => {
  const [table, setTable] = useState("");
  const [activeTable, setActiveTable] = useState("");
  const [filterCol, setFilterCol] = useState("");
  const [filterVal, setFilterVal] = useState("");
  const [offset, setOffset] = useState(0);
  const limit = 50;

  // ── Table list — populates the table dropdown so nobody has to type/
  // remember an exact table name. ─────────────────────────────────────
  const { data: tablesData, isFetching: tablesLoading } = useQuery({
    queryKey: ["preview-tables"],
    queryFn: async () => (await api.get("/tables")).data,
  });
  const tables: string[] = tablesData?.tables ?? [];

  // ── Column list for the currently selected table — populates the
  // filter-column dropdown so filter_col can never be mistyped/mis-cased. ─
  const { data: columnsData } = useQuery({
    queryKey: ["preview-table-columns", table],
    enabled: !!table,
    queryFn: async () => (await api.get(`/table/${table}/columns`)).data,
  });
  const columns: ColumnInfo[] = columnsData?.columns ?? [];

  // ── Distinct values for the selected filter column. The backend only
  // supports exact (case-insensitive) matching — there's no "contains"
  // mode — so instead of free text, we let the user pick from real values
  // that actually exist in that column. ────────────────────────────────
  const { data: valuesData, isFetching: valuesLoading } = useQuery({
    queryKey: ["preview-column-values", table, filterCol],
    enabled: !!table && !!filterCol,
    queryFn: async () => (await api.get(`/table/${table}/columns/${filterCol}/values`)).data,
  });
  const filterValues: string[] = valuesData?.values ?? [];

  // Reset the filter column if it no longer belongs to the newly picked table.
  // Depends on `columns` too, so it re-checks once the new table's columns
  // actually arrive (fixes the stale-closure race on fast table switching).
  useEffect(() => {
    if (filterCol && columns.length > 0 && !columns.some((c) => c.name === filterCol)) {
      setFilterCol("");
    }
  }, [table, columns, filterCol]);

  // Clear a stale picked value whenever the filter column changes.
  useEffect(() => {
    setFilterVal("");
  }, [filterCol]);

  // Any time the effective filter changes (column, value) or the active
  // table changes, jump back to page 1. Otherwise a stale offset can point
  // past the end of the new filtered result set and the table appears to
  // be "empty"/broken.
  useEffect(() => {
    setOffset(0);
  }, [activeTable, filterCol, filterVal]);

  const { data, isFetching, error } = useQuery({
    queryKey: ["table-preview", activeTable, filterCol, filterVal, offset],
    enabled: !!activeTable,
    queryFn: async () => {
      const response = await api.get(`/table/${activeTable}`, {
        params: {
          limit,
          offset,
          // Backend expects filter_col/filter_val as matched pairs — only send
          // filter_col once a value has actually been picked, otherwise it
          // arrives alone and the backend rejects it as a length mismatch.
          filter_col: filterCol && filterVal ? filterCol : undefined,
          filter_val: filterCol && filterVal ? filterVal : undefined,
        },
      });
      return response.data;
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setOffset(0);
    setActiveTable(table.trim());
  };

  const rows = data?.data ?? [];
  const previewColumns: string[] = data?.columns ?? (rows[0] ? Object.keys(rows[0]) : []);

  return (
    <div className="space-y-5">
      <PageHeader
        icon={Table2}
        eyebrow="Data"
        title="Data Preview"
        description="Inspect rows from any connected source before you build against it."
      />
      <Card>
        <CardHeader><CardTitle className="text-sm">Table Browser</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-[1fr_220px_220px_auto]">
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={table}
                onChange={(e) => setTable(e.target.value)}
                required
              >
                <option value="" disabled>
                  {tablesLoading ? "Loading tables…" : "Select a table"}
                </option>
                {tables.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>

              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm disabled:opacity-50"
                value={filterCol}
                onChange={(e) => setFilterCol(e.target.value)}
                disabled={!table}
              >
                <option value="">No filter column</option>
                {columns.map((c) => (
                  <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                ))}
              </select>

              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm disabled:opacity-50"
                value={filterVal}
                onChange={(e) => setFilterVal(e.target.value)}
                disabled={!filterCol}
              >
                <option value="">
                  {!filterCol ? "No filter value" : valuesLoading ? "Loading values…" : "Any value"}
                </option>
                {filterValues.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </select>

              <Button type="submit"><Search /> Load</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950"><CardContent className="p-4 text-sm text-rose-700 dark:text-rose-400">{(error as any)?.response?.data?.detail ?? (error as Error).message}</CardContent></Card>
      )}

      {activeTable && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">{activeTable} {data?.pagination ? `(${data.pagination.total} rows)` : ""}</CardTitle>
          </CardHeader>
          <CardContent>
            {isFetching ? <RowSkeleton rows={4} /> : rows.length ? (
              <>
                <div className="overflow-auto rounded-md border border-border">
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>{previewColumns.map((column) => <th key={column} className="whitespace-nowrap px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">{column}</th>)}</tr>
                    </thead>
                    <tbody>
                      {rows.map((row: any, index: number) => (
                        <tr key={index} className="border-t border-border">
                          {previewColumns.map((column) => <td key={column} className="max-w-72 truncate px-3 py-2 text-foreground">{String(row[column] ?? "")}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 flex items-center justify-between">
                  <Button variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))}>Previous</Button>
                  <span className="text-sm text-muted-foreground">Page {data.pagination.page} of {data.pagination.pages}</span>
                  <Button variant="outline" disabled={!data.pagination.has_more} onClick={() => setOffset(offset + limit)}>Next</Button>
                </div>
              </>
            ) : (
              <EmptyState
                icon={Table2}
                title="No rows to show"
                body="Pick a connection and table above, or run a pipeline to load data into one."
              />
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
