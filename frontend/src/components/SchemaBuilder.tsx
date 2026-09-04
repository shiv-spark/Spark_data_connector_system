import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Braces, ListPlus, Loader2, Table2, Trash2, TriangleAlert } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { PreviewConnector } from "@/components/DataQualityBuilder";

// ── Types returned by POST /preview_source ──────────────────────────────
interface PreviewColumn {
  name: string;
  type: "numeric" | "date" | "boolean" | "text";
  null_pct: number;
}
interface PreviewResponse {
  columns: PreviewColumn[];
  rows: Record<string, string>[];
  total_rows: number;
  sample_row_count: number;
}

// The canonical types the backend understands (see utils/schema_applier.py).
// "numeric"/"date"/"boolean" from the preview map onto sensible defaults;
// everything else defaults to "text".
const SCHEMA_TYPES = [
  { value: "integer", label: "Integer" },
  { value: "float", label: "Float / decimal" },
  { value: "boolean", label: "Boolean" },
  { value: "date", label: "Date" },
  { value: "timestamp", label: "Timestamp (date + time)" },
  { value: "text", label: "Text" },
  { value: "json", label: "JSON" },
] as const;

type SchemaType = (typeof SCHEMA_TYPES)[number]["value"];

const guessedTypeToSchemaType = (guessed: PreviewColumn["type"]): SchemaType => {
  if (guessed === "numeric") return "float";
  if (guessed === "date") return "timestamp";
  if (guessed === "boolean") return "boolean";
  return "text";
};

export interface BuiltSchema {
  schema: Record<string, string>; // { column_name: type } — only columns the user actually set a type for
  hasAnyCustomType: boolean;
}

interface Props {
  connector: PreviewConnector;
  // Same shape as DataQualityBuilder's `params` — the exact body to POST to
  // /preview_source (minus connector_type). `null` means not enough info yet.
  params: Record<string, unknown> | null;
  auto?: boolean;
  initialSchema?: Record<string, string> | null;
  onChange: (result: BuiltSchema) => void;
}

interface Row {
  column: string;
  type: SchemaType;
  enabled: boolean; // only "enabled" rows are sent as part of custom_schema
}

// Lets a user override the auto-detected schema for any connector/source —
// pick a type per column (or add columns that aren't even in this
// particular source yet), and that's enforced on ingest instead of
// whatever pandas/polars would have guessed. See utils/schema_applier.py.
export const SchemaBuilder = ({ connector, params, auto = true, initialSchema, onChange }: Props) => {
  const [rows, setRows] = useState<Row[]>(() =>
    Object.entries(initialSchema ?? {}).map(([column, type]) => ({
      column,
      type: (SCHEMA_TYPES.some((t) => t.value === type) ? type : "text") as SchemaType,
      enabled: true,
    })),
  );
  const [manualTrigger, setManualTrigger] = useState(false);
  const [mode, setMode] = useState<"form" | "json">("form");
  const [jsonText, setJsonText] = useState(() => JSON.stringify(initialSchema ?? {}, null, 2));
  const [jsonError, setJsonError] = useState("");

  const paramsKey = params ? JSON.stringify(params) : "";
  const shouldFetch = !!params && (auto || manualTrigger);

  // Deliberately the SAME query key shape DataQualityBuilder uses for the
  // same params — react-query dedupes identical in-flight/cached requests,
  // so rendering both components side by side doesn't double the network
  // calls to /preview_source.
  const preview = useQuery({
    queryKey: ["source-preview", connector, paramsKey],
    enabled: shouldFetch,
    queryFn: async () => (await api.post<PreviewResponse>("/preview_source", {
      connector_type: connector,
      sample_rows: 15,
      ...(params ?? {}),
    })).data,
  });

  const previewColumns = preview.data?.columns ?? [];

  // Once a preview arrives, seed any not-yet-seen columns into the row list
  // (unchecked by default) so the user just has to tick + pick a type
  // instead of typing every column name by hand.
  useEffect(() => {
    if (!previewColumns.length) return;
    setRows((cur) => {
      const known = new Set(cur.map((r) => r.column));
      const additions = previewColumns
        .filter((c) => !known.has(c.name))
        .map((c) => ({ column: c.name, type: guessedTypeToSchemaType(c.type), enabled: false }));
      return additions.length ? [...cur, ...additions] : cur;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewColumns.map((c) => c.name).join(",")]);

  // ── form <-> JSON sync ──────────────────────────────────────────────
  const schemaFromRows = useMemo(() => {
    const out: Record<string, string> = {};
    for (const r of rows) {
      if (r.enabled && r.column.trim()) out[r.column.trim()] = r.type;
    }
    return out;
  }, [rows]);

  useEffect(() => {
    if (mode === "form") setJsonText(JSON.stringify(schemaFromRows, null, 2));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, JSON.stringify(schemaFromRows)]);

  const applyJsonToRows = (text: string) => {
    setJsonText(text);
    try {
      const parsed = text.trim() ? JSON.parse(text) : {};
      if (typeof parsed !== "object" || Array.isArray(parsed) || parsed === null) {
        throw new Error("Must be a JSON object of {\"column\": \"type\"}");
      }
      setJsonError("");
      setRows(
        Object.entries(parsed).map(([column, type]) => ({
          column,
          type: (SCHEMA_TYPES.some((t) => t.value === type) ? type : "text") as SchemaType,
          enabled: true,
        })),
      );
    } catch (e) {
      setJsonError(e instanceof Error ? e.message : "Invalid JSON");
    }
  };

  const built = useMemo<BuiltSchema>(() => {
    const schema = mode === "json" && !jsonError
      ? (() => {
          try {
            return JSON.parse(jsonText || "{}");
          } catch {
            return {};
          }
        })()
      : schemaFromRows;
    return { schema, hasAnyCustomType: Object.keys(schema).length > 0 };
  }, [mode, jsonText, jsonError, schemaFromRows]);

  useEffect(() => {
    onChange(built);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [built.hasAnyCustomType, JSON.stringify(built.schema)]);

  if (!params) return null;

  if (!shouldFetch) {
    return (
      <button
        type="button"
        onClick={() => setManualTrigger(true)}
        className="flex w-full items-center gap-2 rounded-lg border border-dashed border-border px-4 py-3 text-sm font-medium text-muted-foreground hover:border-foreground/30 hover:text-foreground"
      >
        <Table2 className="h-4 w-4" /> Define your own schema (optional)
      </button>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border shadow-sm">
      <div className="flex items-center gap-2 border-b border-border bg-muted/50 px-4 py-2.5">
        <Table2 className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-semibold text-foreground">Define your own schema (optional)</span>
        <div className="ml-auto flex items-center gap-1 rounded-md bg-background p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setMode("form")}
            className={`rounded px-2 py-1 font-medium ${mode === "form" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            <ListPlus className="mr-1 inline h-3 w-3" /> Builder
          </button>
          <button
            type="button"
            onClick={() => setMode("json")}
            className={`rounded px-2 py-1 font-medium ${mode === "json" ? "bg-primary text-primary-foreground" : "text-muted-foreground"}`}
          >
            <Braces className="mr-1 inline h-3 w-3" /> JSON
          </button>
        </div>
      </div>

      <p className="border-b border-border bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
        When you select a data type for a column from the dropdown, that column is automatically
        added to your custom schema and its checkbox is selected. During ingestion, the column
        will be converted to the selected data type. You can uncheck the checkbox to remove
        a column from the schema without deleting the data rows. If a value cannot be converted,
        it will become NULL instead of failing the pipeline. If a column is missing from the source,
        it will be added with NULL values.
      </p>

      {preview.isFetching && (
        <div className="flex items-center gap-2 p-5 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Fetching a preview…
        </div>
      )}

      {mode === "form" ? (
        <div className="divide-y divide-border">
          {rows.map((row, i) => (
            <div key={i} className="flex items-center gap-2 px-4 py-2">
              <input
                type="checkbox"
                checked={row.enabled}
                onChange={(e) =>
                  setRows((cur) => cur.map((r, idx) => (idx === i ? { ...r, enabled: e.target.checked } : r)))
                }
                className="h-4 w-4 shrink-0"
              />
              <Input
                placeholder="column_name"
                value={row.column}
                onChange={(e) =>
                  setRows((cur) => cur.map((r, idx) => (idx === i ? { ...r, column: e.target.value } : r)))
                }
                className="h-8 flex-1"
              />
              <select
                value={row.type}
                onChange={(e) =>
                  setRows((cur) =>
                    cur.map((r, idx) =>
                      // Picking a type is the natural "I want this column
                      // in my schema" action — auto-enable it instead of
                      // silently requiring a separate checkbox tick too
                      // (that was confusing: the type looked "set" in the
                      // dropdown but never actually made it into the
                      // payload unless the checkbox was also ticked).
                      idx === i ? { ...r, type: e.target.value as SchemaType, enabled: true } : r,
                    ),
                  )
                }
                className="h-8 rounded-md border border-input bg-background px-2 text-sm text-foreground dark:bg-background dark:text-foreground"
              >
                {SCHEMA_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
              <button
                type="button"
                onClick={() => setRows((cur) => cur.filter((_, idx) => idx !== i))}
                className="shrink-0 text-muted-foreground hover:text-rose-600"
                aria-label="Remove column"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
          <div className="px-4 py-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setRows((cur) => [...cur, { column: "", type: "text", enabled: true }])}
            >
              <ListPlus className="h-3.5 w-3.5" /> Add column
            </Button>
          </div>
        </div>
      ) : (
        <div className="p-4">
          <textarea
            className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs text-foreground dark:bg-background dark:text-foreground"
            placeholder='{"customer_id": "integer", "signup_date": "date", "is_active": "boolean"}'
            value={jsonText}
            onChange={(e) => applyJsonToRows(e.target.value)}
          />
          {jsonError && (
            <p className="mt-1.5 flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400">
              <TriangleAlert className="h-3.5 w-3.5" /> {jsonError}
            </p>
          )}
          <p className="mt-1.5 text-xs text-muted-foreground">
            Types: {SCHEMA_TYPES.map((t) => t.value).join(", ")}
          </p>
        </div>
      )}
    </div>
  );
};
