import { useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { fetchLiveSourceTables, type ListSourceTablesPayload } from "@/lib/api";

type Mode = "table" | "query";

type Props = {
  /** Unique-ish key so multiple pickers on one page (Multi-Source) don't share radio groups. */
  fieldKey: string;
  /** Build the credentials payload fresh at fetch time — read from the caller's current form state. */
  buildPayload: () => ListSourceTablesPayload;
  /** True once enough fields are filled in to be worth trying a connection. */
  canFetch: boolean;
  buildQuery: (table: string) => string;
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  tableInput: string;
  onTableInputChange: (value: string) => void;
  queryValue: string;
  onQueryChange: (value: string) => void;
};

// Live "pick a table" for pipelines that don't exist yet — Create Pipeline,
// Multi-Source, and Direct Ingest all need to list the source's actual
// tables before there's any saved DAG to read credentials back out of, so
// this connects with whatever credentials are currently in the form
// (see POST /list_source_tables) instead of a pipeline name. Mirrors
// SourceTablePicker's UI, which does the same thing for the edit form.
export function LiveTablePicker({
  fieldKey,
  buildPayload,
  canFetch,
  buildQuery,
  mode,
  onModeChange,
  tableInput,
  onTableInputChange,
  queryValue,
  onQueryChange,
}: Props) {
  const {
    mutate: loadTables,
    data: tables,
    isPending,
    isError,
    error,
    reset,
  } = useMutation({
    mutationFn: () => fetchLiveSourceTables(buildPayload()),
  });

  // Auto-load the first time someone switches into "table" mode, as long as
  // there's enough entered to bother connecting. Doesn't re-fire on every
  // keystroke — only when mode flips or credentials go from incomplete to complete.
  useEffect(() => {
    if (mode === "table" && canFetch && tables === undefined && !isPending) {
      loadTables();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, canFetch]);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-4 text-sm font-medium text-foreground">
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="radio"
              name={`source-mode-${fieldKey}`}
              checked={mode === "table"}
              onChange={() => onModeChange("table")}
            />
            Pick a table
          </label>
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="radio"
              name={`source-mode-${fieldKey}`}
              checked={mode === "query"}
              onChange={() => onModeChange("query")}
            />
            Write custom SQL
          </label>
        </div>
        {mode === "table" && (
          <button
            type="button"
            onClick={() => {
              reset();
              loadTables();
            }}
            disabled={!canFetch}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
          >
            <RefreshCw className={`h-3 w-3 ${isPending ? "animate-spin" : ""}`} /> Load tables
          </button>
        )}
      </div>

      {mode === "table" ? (
        <div className="space-y-1.5">
          <select
            className="select-control w-full"
            value={tableInput}
            disabled={isPending}
            onChange={(e) => {
              const v = e.target.value;
              onTableInputChange(v);
              onQueryChange(buildQuery(v));
            }}
          >
            <option value="">
              {isPending
                ? "Loading tables…"
                : !canFetch
                ? "Enter connection details first…"
                : "Select a table…"}
            </option>
            {(tables ?? []).map((t: string) => (
              <option key={t} value={t}>{t}</option>
            ))}
            {tableInput && !(tables ?? []).includes(tableInput) && (
              <option value={tableInput}>{tableInput}</option>
            )}
          </select>
          {isPending && (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Connecting to the source to list its tables…
            </p>
          )}
          {isError && (
            <p className="text-xs text-destructive">
              Couldn't list tables — {(error as any)?.response?.data?.detail?.toString?.() ?? "check the connection details above"}. You can still type the table name below, or switch to custom SQL.
            </p>
          )}
          {!canFetch && !isPending && (
            <p className="text-xs text-muted-foreground">
              Fill in the connection details above, then tables will load automatically.
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            This will pull every column from the selected table. Need only some columns or a filter? Use "Write custom SQL" instead.
          </p>
        </div>
      ) : (
        <div className="space-y-1.5">
          <textarea
            className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground"
            placeholder="SQL query"
            value={queryValue}
            onChange={(e) => onQueryChange(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Runs exactly as written against the source database on every run.
          </p>
        </div>
      )}
    </div>
  );
}
