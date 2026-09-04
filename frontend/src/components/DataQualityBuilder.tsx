import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Calendar,
  CheckCircle2,
  ChevronDown,
  Hash,
  Loader2,
  ShieldCheck,
  Sigma,
  Table2,
  ToggleLeft,
  TriangleAlert,
  Type,
} from "lucide-react";
import { api } from "@/lib/api";

// ── Types returned by GET /preview_file ────────────────────────────────
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

// "Expected type" choices — these are the actual Postgres column types a
// user would recognize, since that's what the data eventually lands in.
// Several Postgres types map to the same underlying check (the backend
// only tells numbers / text / date / timestamp / boolean apart), but the
// dropdown still shows every real Postgres type name.
const POSTGRES_TYPE_GROUPS: { label: string; options: { value: string; pgType: string }[] }[] = [
  {
    label: "Numbers",
    options: [
      { value: "numeric", pgType: "smallint" },
      { value: "numeric", pgType: "integer" },
      { value: "numeric", pgType: "bigint" },
      { value: "numeric", pgType: "serial" },
      { value: "numeric", pgType: "bigserial" },
      { value: "numeric", pgType: "decimal" },
      { value: "numeric", pgType: "numeric" },
      { value: "numeric", pgType: "real" },
      { value: "numeric", pgType: "double precision" },
    ],
  },
  {
    label: "Text",
    options: [
      { value: "text", pgType: "text" },
      { value: "text", pgType: "varchar" },
      { value: "text", pgType: "char" },
      { value: "text", pgType: "uuid" },
      { value: "text", pgType: "json" },
      { value: "text", pgType: "jsonb" },
    ],
  },
  {
    label: "Date & time",
    options: [
      { value: "date", pgType: "date" },
      { value: "datetime", pgType: "timestamp" },
      { value: "datetime", pgType: "timestamptz" },
      { value: "text", pgType: "time" },
    ],
  },
  {
    label: "Boolean",
    options: [{ value: "boolean", pgType: "boolean" }],
  },
];

// ── Per-column check state — every field maps to plain language in the
// UI, never to a technical term like "regex" or "dtype". ───────────────
export interface ColumnCheckState {
  noEmpty: boolean;
  noDuplicates: boolean;
  typeCheck: string; // backend key: numeric | text | date | datetime | boolean | ""
  format: "" | "pattern";
  likePattern: string; // SQL LIKE-style pattern, e.g. "%@gmail.com" or "IN-____"
  min: string;
  max: string;
  allowedValues: string; // comma separated
}

const blankCheck: ColumnCheckState = {
  noEmpty: false,
  noDuplicates: false,
  typeCheck: "",
  format: "",
  likePattern: "",
  min: "",
  max: "",
  allowedValues: "",
};

// Inverse of buildQualityFromChecks — turns a previously-saved df_quality_config
// back into per-column UI state, so editing an existing pipeline starts from
// what's actually configured instead of a blank slate. One caveat: pattern_checks
// stores a compiled regex (not the original friendly "%"/"_" wildcard string), so
// that direction can't be perfectly inverted — the pattern format is restored but
// the LIKE-pattern text box is left for the user to re-enter if they touch it.
function checksFromConfig(
  config: Record<string, unknown> | null | undefined,
): Record<string, ColumnCheckState> {
  if (!config) return {};
  const checks: Record<string, ColumnCheckState> = {};
  const ensure = (col: string) => (checks[col] ??= { ...blankCheck });

  const nullThresholds = (config.null_thresholds ?? {}) as Record<string, number>;
  Object.keys(nullThresholds).forEach((col) => { ensure(col).noEmpty = true; });

  const duplicateSubset = (config.duplicate_subset ?? []) as string[];
  duplicateSubset.forEach((col) => { ensure(col).noDuplicates = true; });

  const expectedDtypes = (config.expected_dtypes ?? {}) as Record<string, string>;
  Object.entries(expectedDtypes).forEach(([col, t]) => { ensure(col).typeCheck = t; });

  const rangeChecks = (config.range_checks ?? {}) as Record<string, { min?: number; max?: number }>;
  Object.entries(rangeChecks).forEach(([col, bounds]) => {
    const c = ensure(col);
    if (bounds?.min !== undefined) c.min = String(bounds.min);
    if (bounds?.max !== undefined) c.max = String(bounds.max);
  });

  const patternChecks = (config.pattern_checks ?? {}) as Record<string, string>;
  Object.keys(patternChecks).forEach((col) => { ensure(col).format = "pattern"; });

  const allowedValues = (config.allowed_values ?? {}) as Record<string, string[]>;
  Object.entries(allowedValues).forEach(([col, vals]) => {
    ensure(col).allowedValues = (vals ?? []).join(", ");
  });

  return checks;
}

// Converts a friendly SQL-LIKE pattern ("%" = any characters, "_" = one
// character) into the regex the backend's pattern_checks actually runs,
// so users never have to type regex themselves.
export function likePatternToRegex(likePattern: string): string {
  const escaped = likePattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const withWildcards = escaped.replace(/%/g, ".*").replace(/_/g, ".");
  return `^${withWildcards}$`;
}

const typeMeta: Record<PreviewColumn["type"], { label: string; icon: typeof Hash }> = {
  numeric: { label: "Number", icon: Hash },
  date: { label: "Date", icon: Calendar },
  boolean: { label: "True/False", icon: ToggleLeft },
  text: { label: "Text", icon: Type },
};

export interface BuiltQuality {
  config: Record<string, unknown>;
  on_fail: "warn" | "block";
  hasAnyCheck: boolean;
}

// Builds the exact same payload shape the original "run checks before
// ingest" (in-memory, pre-write) feature sent — check_empty, null
// thresholds, duplicate subset, expected dtypes, range checks, pattern
// checks, allowed values — just assembled from friendly UI state instead
// of free-typed column:value strings.
export function buildQualityFromChecks(
  checks: Record<string, ColumnCheckState>,
  onFail: "warn" | "block",
): BuiltQuality {
  const config: Record<string, unknown> = { check_empty: true };
  const nullThresholds: Record<string, number> = {};
  const duplicateSubset: string[] = [];
  const expectedDtypes: Record<string, string> = {};
  const rangeChecks: Record<string, { min?: number; max?: number }> = {};
  const patternChecks: Record<string, string> = {};
  const allowedValues: Record<string, string[]> = {};
  let hasAnyCheck = false;

  Object.entries(checks).forEach(([col, c]) => {
    if (c.noEmpty) { nullThresholds[col] = 0; hasAnyCheck = true; }
    if (c.noDuplicates) { duplicateSubset.push(col); hasAnyCheck = true; }
    if (c.typeCheck) { expectedDtypes[col] = c.typeCheck; hasAnyCheck = true; }
    if (c.min.trim() || c.max.trim()) {
      const bounds: { min?: number; max?: number } = {};
      if (c.min.trim()) bounds.min = Number(c.min);
      if (c.max.trim()) bounds.max = Number(c.max);
      rangeChecks[col] = bounds;
      hasAnyCheck = true;
    }
    if (c.format === "pattern" && c.likePattern.trim()) {
      patternChecks[col] = likePatternToRegex(c.likePattern.trim());
      hasAnyCheck = true;
    }
    const allowed = c.allowedValues.split(",").map((v) => v.trim()).filter(Boolean);
    if (allowed.length) { allowedValues[col] = allowed; hasAnyCheck = true; }
  });

  if (Object.keys(nullThresholds).length) config.null_thresholds = nullThresholds;
  if (duplicateSubset.length) { config.check_duplicates = true; config.duplicate_subset = duplicateSubset; }
  if (Object.keys(expectedDtypes).length) config.expected_dtypes = expectedDtypes;
  if (Object.keys(rangeChecks).length) config.range_checks = rangeChecks;
  if (Object.keys(patternChecks).length) config.pattern_checks = patternChecks;
  if (Object.keys(allowedValues).length) config.allowed_values = allowedValues;

  return { config, on_fail: onFail, hasAnyCheck };
}

// Any connector type — the backend's /preview_source dispatches to the
// right connector function based on `connector` + whatever fields are in
// `params` (a saved connection_id, or freshly-typed credentials/query).
// export type PreviewConnector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "s3" | "snowflake";

export type PreviewConnector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "mysql" | "oracle" | "mongodb" | "s3" | "snowflake" | "salesforce" | "hubspot" | "zoho";

interface Props {
  connector: PreviewConnector;
  // The exact body to POST to /preview_source (minus connector_type, which
  // this component adds). `null` means "not enough info yet" — nothing
  // renders. Recomputed by the parent whenever the relevant fields change.
  params: Record<string, unknown> | null;
  // csv/excel: preview fires the moment a file is picked (a discrete
  // click, not per-keystroke) — auto=true keeps that instant feedback.
  // Every other connector types into `params` continuously (host, query,
  // url...), so auto=false waits for an explicit "Preview" click instead
  // of firing a real query/API call on every keystroke.
  auto?: boolean;
  // Pre-populate from a previously-saved df_quality_config — used when
  // editing an existing pipeline instead of creating a new one. Only read
  // once, on mount; the component owns the state after that (same as any
  // other "defaultValue"-style prop).
  initialConfig?: Record<string, unknown> | null;
  initialOnFail?: "warn" | "block";
  onChange: (result: BuiltQuality) => void;
  // When set (e.g. from "Fix in Configure" on a failed check), the matching
  // column's accordion opens and scrolls into view automatically instead of
  // making the person hunt through every collapsed column to find it. A
  // bump on `focusToken` re-triggers the open+scroll even if the same
  // column was already the target (so clicking "Fix in Configure" again
  // for the same failing column still scrolls back to it).
  focusColumn?: string | null;
  focusToken?: number;
}

// A friendly, no-jargon replacement for the old "pre-ingest / post-load"
// checkbox pair: upload → see your data → tick the checks you want, in
// plain language, right next to the column they apply to. Everything
// still runs before the data is written to the table, same as before.
export const DataQualityBuilder = ({ connector, params, auto = true, initialConfig, initialOnFail, onChange, focusColumn, focusToken }: Props) => {
  const [checks, setChecks] = useState<Record<string, ColumnCheckState>>(() => checksFromConfig(initialConfig));
  const [onFail, setOnFail] = useState<"warn" | "block">(initialOnFail ?? "warn");
  const [openColumn, setOpenColumn] = useState<string | null>(null);
  const [manualTrigger, setManualTrigger] = useState(false);
  const columnRefs = useRef<Record<string, HTMLDivElement | null>>({});

  const paramsKey = params ? JSON.stringify(params) : "";

  // Key used ONLY to decide whether the per-column checks should reset —
  // deliberately excludes password/token/secret fields. Editing an existing
  // pipeline never gets the real secret back from the backend (see the
  // "re-enter the credential above" note below), so the very first thing a
  // person does when fixing a failed check is often to re-type the
  // password just to get the preview working again. That's the *same*
  // source, not a new one — it must not be treated like switching to a
  // different table/query, or every already-configured check silently
  // vanishes the moment the password field is touched.
  const paramsResetKey = params
    ? JSON.stringify(
        Object.fromEntries(
          Object.entries(params).filter(([key]) => !/password|token|secret/i.test(key)),
        ),
      )
    : "";

  // Reset per-column checks — and require a fresh "Preview" click for
  // manual connectors — whenever the source *identity* actually changes
  // (host/db/table/query/url/...), so stale checks/preview data from a
  // previous file or query never carry over. Skipped on the very first run
  // so an initialConfig passed in on mount (editing an existing pipeline)
  // doesn't get wiped out immediately.
  const skippedFirstReset = useRef(false);
  useEffect(() => {
    if (!skippedFirstReset.current) {
      skippedFirstReset.current = true;
      return;
    }
    setChecks({});
    setOpenColumn(null);
    setManualTrigger(false);
  }, [connector, paramsResetKey]);

  const shouldFetch = !!params && (auto || manualTrigger);

  const preview = useQuery({
    queryKey: ["source-preview", connector, paramsKey],
    enabled: shouldFetch,
    queryFn: async () => (await api.post<PreviewResponse>("/preview_source", {
      connector_type: connector,
      sample_rows: 15,
      ...(params ?? {}),
    })).data,
  });

  const columns = preview.data?.columns ?? [];

  // Open + scroll to the column a failed check pointed at, once its preview
  // data has actually loaded (columns start empty while the preview query
  // is in flight, so this waits rather than firing against an empty list).
  useEffect(() => {
    if (!focusColumn) return;
    if (!columns.some((c) => c.name === focusColumn)) return;
    setOpenColumn(focusColumn);
    // Let the accordion render open before scrolling to it.
    requestAnimationFrame(() => {
      columnRefs.current[focusColumn]?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusColumn, focusToken, columns.length]);

  const updateCol = (col: string, patch: Partial<ColumnCheckState>) =>
    setChecks((cur) => ({ ...cur, [col]: { ...(cur[col] ?? blankCheck), ...patch } }));

  const built = useMemo(() => buildQualityFromChecks(checks, onFail), [checks, onFail]);

  useEffect(() => {
    onChange(built);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [built.hasAnyCheck, JSON.stringify(built.config), built.on_fail]);

  if (!params) return null;

  if (!shouldFetch) {
    return (
      <button
        type="button"
        onClick={() => setManualTrigger(true)}
        className="flex w-full items-center gap-2 rounded-lg border border-dashed border-border px-4 py-3 text-sm font-medium text-muted-foreground hover:border-foreground/30 hover:text-foreground"
      >
        <ShieldCheck className="h-4 w-4" /> Preview data & build quality checks (optional)
      </button>
    );
  }

  return (
    <div className="space-y-4">
      {/* ── Data preview ───────────────────────────────────────────── */}
      <div className="overflow-hidden rounded-lg border border-border shadow-sm">
        <div className="flex items-center gap-2 border-b border-border bg-muted/50 px-4 py-2.5">
          <Table2 className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">Here's a preview of your data</span>
          {preview.data && (
            <span className="ml-auto rounded-full bg-background px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
              {preview.data.total_rows.toLocaleString()} rows · {columns.length} columns
            </span>
          )}
        </div>

        {preview.isFetching && (
          <div className="flex items-center gap-2 p-5 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Fetching a preview…
          </div>
        )}

        {preview.isError && (
          <div className="flex items-center gap-2 p-5 text-sm text-rose-600 dark:text-rose-400">
            <TriangleAlert className="h-4 w-4 shrink-0" />
            {(preview.error as any)?.response?.data?.detail ?? "We couldn't preview this source."}
          </div>
        )}

        {preview.data && (
          <div>
            <div className="max-h-72 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-muted/80 backdrop-blur">
                  <tr>
                    {columns.map((c) => {
                      const Icon = typeMeta[c.type].icon;
                      return (
                        <th key={c.name} className="whitespace-nowrap border-b border-border px-3 py-2 text-left">
                          <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            <Icon className="h-3 w-3" /> {c.name}
                          </span>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {preview.data.rows.map((row, i) => (
                    <tr key={i} className={i % 2 ? "bg-muted/20" : ""}>
                      {columns.map((c) => (
                        <td key={c.name} className="max-w-56 truncate px-3 py-2 text-foreground">
                          {row[c.name] || <span className="text-muted-foreground">—</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="border-t border-border bg-muted/20 px-4 py-2 text-xs text-muted-foreground">
              Showing a sample of {preview.data.sample_row_count} row{preview.data.sample_row_count === 1 ? "" : "s"} — checks below run against the full data at ingest time.
            </p>
          </div>
        )}
      </div>

      {/* ── Friendly, per-column quality checks ───────────────────── */}
      {columns.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border shadow-sm">
          <div className="border-b border-border bg-muted/50 px-4 py-2.5">
            <p className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <ShieldCheck className="h-4 w-4" /> Want to check your data before it's saved? (optional)
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Click a column to add checks — everything here runs before the data is written to the table.
            </p>
          </div>

          <div className="divide-y divide-border">
            {columns.map((col) => {
              const c = checks[col.name] ?? blankCheck;
              const activeCount = [
                c.noEmpty, c.noDuplicates, !!c.typeCheck, !!c.format,
                !!c.min.trim(), !!c.max.trim(), !!c.allowedValues.trim(),
              ].filter(Boolean).length;
              const isOpen = openColumn === col.name;
              const Icon = typeMeta[col.type].icon;

              const isFocused = focusColumn === col.name;

              return (
                <div
                  key={col.name}
                  ref={(el) => { columnRefs.current[col.name] = el; }}
                  className={`${isOpen ? "bg-muted/10" : ""} ${isFocused ? "ring-2 ring-inset ring-indigo-400" : ""}`}
                >
                  <button
                    type="button"
                    onClick={() => setOpenColumn(isOpen ? null : col.name)}
                    className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/40"
                  >
                    <span className="flex min-w-0 items-center gap-2.5">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-medium text-foreground">{col.name}</span>
                        <span className="block text-[11px] text-muted-foreground">
                          {typeMeta[col.type].label}{col.null_pct > 0 ? ` · ${col.null_pct}% empty` : ""}
                        </span>
                      </span>
                    </span>
                    <span className="flex shrink-0 items-center gap-2">
                      {isFocused && (
                        <span className="flex items-center gap-1 rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950/40 dark:text-indigo-300">
                          <TriangleAlert className="h-3.5 w-3.5" /> Failing check
                        </span>
                      )}
                      {activeCount > 0 && (
                        <span className="flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
                          <CheckCircle2 className="h-3.5 w-3.5" /> {activeCount} check{activeCount > 1 ? "s" : ""}
                        </span>
                      )}
                      <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${isOpen ? "rotate-180" : ""}`} />
                    </span>
                  </button>

                  {isOpen && (
                    <div className="space-y-4 border-t border-border bg-muted/20 px-4 py-4">
                      <div className="flex flex-wrap gap-x-6 gap-y-2">
                        <label className="flex items-center gap-2 text-sm text-foreground">
                          <input type="checkbox" className="h-4 w-4 rounded border-input" checked={c.noEmpty} onChange={(e) => updateCol(col.name, { noEmpty: e.target.checked })} />
                          This column can't be empty
                        </label>
                        <label className="flex items-center gap-2 text-sm text-foreground">
                          <input type="checkbox" className="h-4 w-4 rounded border-input" checked={c.noDuplicates} onChange={(e) => updateCol(col.name, { noDuplicates: e.target.checked })} />
                          Values must be unique (no duplicates)
                        </label>
                      </div>

                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <label className="space-y-1 text-xs font-medium text-muted-foreground">
                          Expected type
                          <select
                            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                            value={c.typeCheck}
                            onChange={(e) => updateCol(col.name, { typeCheck: e.target.value })}
                          >
                            <option value="">No restriction</option>
                            {POSTGRES_TYPE_GROUPS.map((group) => (
                              <optgroup key={group.label} label={group.label}>
                                {group.options.map((opt) => (
                                  <option key={opt.pgType} value={opt.value}>{opt.pgType}</option>
                                ))}
                              </optgroup>
                            ))}
                          </select>
                        </label>

                        <label className="space-y-1 text-xs font-medium text-muted-foreground">
                          Format check
                          <select
                            className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                            value={c.format}
                            onChange={(e) => updateCol(col.name, { format: e.target.value as ColumnCheckState["format"] })}
                          >
                            <option value="">None</option>
                            <option value="pattern">Matches a pattern</option>
                          </select>
                        </label>
                      </div>

                      {c.format === "pattern" && (
                        <div className="space-y-2">
                          <label className="block space-y-1 text-xs font-medium text-muted-foreground">
                            Pattern — use % for "any characters" and _ for "any one character"
                            <input
                              className="h-9 w-full rounded-md border border-input bg-background px-2 font-mono text-sm text-foreground"
                              placeholder="e.g. %@gmail.com or INV-____"
                              value={c.likePattern}
                              onChange={(e) => updateCol(col.name, { likePattern: e.target.value })}
                            />
                          </label>
                          <div className="flex flex-wrap gap-1.5">
                            <button
                              type="button"
                              onClick={() => updateCol(col.name, { likePattern: "%@%.%" })}
                              className="rounded-full border border-input px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted"
                            >
                              Email — %@%.%
                            </button>
                            <button
                              type="button"
                              onClick={() => updateCol(col.name, { likePattern: "__________" })}
                              className="rounded-full border border-input px-2.5 py-1 text-xs text-muted-foreground hover:bg-muted"
                            >
                              10-digit phone — __________
                            </button>
                          </div>
                          <p className="text-xs text-muted-foreground">
                            Values that don't match this pattern will fail the check.
                          </p>
                        </div>
                      )}

                      {col.type === "numeric" && (
                        <div className="grid grid-cols-2 gap-3">
                          <label className="space-y-1 text-xs font-medium text-muted-foreground">
                            Minimum value
                            <input
                              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                              placeholder="e.g. 0"
                              value={c.min}
                              onChange={(e) => updateCol(col.name, { min: e.target.value })}
                            />
                          </label>
                          <label className="space-y-1 text-xs font-medium text-muted-foreground">
                            Maximum value
                            <input
                              className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                              placeholder="e.g. 120"
                              value={c.max}
                              onChange={(e) => updateCol(col.name, { max: e.target.value })}
                            />
                          </label>
                        </div>
                      )}

                      <label className="block space-y-1 text-xs font-medium text-muted-foreground">
                        <span className="flex items-center gap-1.5"><Sigma className="h-3.5 w-3.5" /> Only allow these values (comma-separated, optional)</span>
                        <input
                          className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm text-foreground"
                          placeholder="e.g. active, inactive, pending"
                          value={c.allowedValues}
                          onChange={(e) => updateCol(col.name, { allowedValues: e.target.value })}
                        />
                      </label>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          {built.hasAnyCheck && (
            <div className="border-t border-border bg-background px-4 py-3">
              <label className="mb-1 block text-xs font-medium text-muted-foreground">If a check fails</label>
              <select
                className="h-9 w-full max-w-sm rounded-md border border-input bg-background px-3 text-sm text-foreground"
                value={onFail}
                onChange={(e) => setOnFail(e.target.value as "warn" | "block")}
              >
                <option value="warn">Just warn me — save the data anyway</option>
                <option value="block">Don't save the data</option>
              </select>
            </div>
          )}
        </div>
      )}
    </div>
  );
};


// Backward-compat exports for pages not yet migrated to <DataQualityBuilder>
export const EXPECTED_TYPE_OPTIONS = POSTGRES_TYPE_GROUPS.flatMap((g) =>
  g.options.map((o) => ({ value: o.value, label: o.pgType }))
);
export const FORMAT_PATTERNS: Record<string, string> = {
  email: "^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$",
  phone: "^[0-9+()\\-\\s]{7,15}$",
};