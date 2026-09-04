import { useQuery } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { fetchPipelineSourceTables } from "@/lib/api";
import { buildSelectQuery, buildSnowflakeSelectQuery } from "@/lib/sourceQuery";

type Mode = "table" | "query";

type Props = {
  pipelineName: string;
  connectorType: "postgres" | "snowflake";
  mode: Mode;
  onModeChange: (mode: Mode) => void;
  tableInput: string;
  onTableInputChange: (value: string) => void;
  queryValue: string;
  onQueryChange: (value: string) => void;
};

// Lets someone who doesn't know SQL pick a table from a dropdown instead of
// reading/writing a raw query — used in the Pipelines edit form for
// Postgres and Snowflake sources. Falls back to a free-text SQL box for
// people who do want a custom query (joins, filters, specific columns…).
export function SourceTablePicker({
  pipelineName,
  connectorType,
  mode,
  onModeChange,
  tableInput,
  onTableInputChange,
  queryValue,
  onQueryChange,
}: Props) {
  const buildQuery = connectorType === "snowflake" ? buildSnowflakeSelectQuery : buildSelectQuery;

  const { data: tables, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ["pipeline-source-tables", pipelineName],
    queryFn: () => fetchPipelineSourceTables(pipelineName),
    enabled: mode === "table",
    staleTime: 30_000,
    retry: false,
  });

  return (
    <div className="space-y-2 md:col-span-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-4 text-sm font-medium text-foreground">
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="radio"
              name={`source-mode-${pipelineName}`}
              checked={mode === "table"}
              onChange={() => onModeChange("table")}
            />
            Pick a table
          </label>
          <label className="flex cursor-pointer items-center gap-1.5">
            <input
              type="radio"
              name={`source-mode-${pipelineName}`}
              checked={mode === "query"}
              onChange={() => onModeChange("query")}
            />
            Write custom SQL
          </label>
        </div>
        {mode === "table" && (
          <button
            type="button"
            onClick={() => refetch()}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
          >
            <RefreshCw className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`} /> Refresh tables
          </button>
        )}
      </div>

      {mode === "table" ? (
        <div className="space-y-1.5">
          <select
            className="select-control w-full"
            value={tableInput}
            disabled={isLoading}
            onChange={(e) => {
              const v = e.target.value;
              onTableInputChange(v);
              onQueryChange(buildQuery(v));
            }}
          >
            <option value="">
              {isLoading ? "Loading tables…" : "Select a table…"}
            </option>
            {(tables ?? []).map((t: string) => (
              <option key={t} value={t}>{t}</option>
            ))}
            {/* Keep the currently-saved table selectable even if it wasn't
                returned by the list (e.g. a schema-qualified name, or the
                list call failed) so switching modes never blanks the value. */}
            {tableInput && !(tables ?? []).includes(tableInput) && (
              <option value={tableInput}>{tableInput}</option>
            )}
          </select>
          {isLoading && (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Connecting to the source to list its tables…
            </p>
          )}
          {isError && (
            <p className="text-xs text-destructive">
              Couldn't list tables — {(error as any)?.response?.data?.detail?.toString?.() ?? "check the connection details above"}. You can still type the table name below, or switch to custom SQL.
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
