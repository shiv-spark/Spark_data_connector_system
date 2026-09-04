import { FormEvent, ReactNode, useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ShieldCheck,
  Plus,
  Trash2,
  CheckCircle2,
  XCircle,
  RotateCcw,
  ChevronDown,
  AlertTriangle,
  Loader2,
  DatabaseZap,
  Wifi,
  CheckCircle,
  X,
  Sparkles,
  Wrench,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, RowSkeleton } from "@/components/console/Panel";

// ── Types (mirror backend/quality/router.py request/response shapes) ──────
interface QualityConnection {
  id: number;
  name: string;
  source_type: string;
}

interface ColumnInfo {
  name: string;
  type: string;
}

interface BusinessRule {
  column: string;
  condition: string;
}

interface ForeignKeyRule {
  column: string;
  parent_table: string;
  parent_column: string;
}

interface RangeRule {
  column: string;
  min: string;
  max: string;
}

interface ConsistencyRule {
  table_a: string;
  expr_a: string;
  table_b: string;
  expr_b: string;
  tolerance: string;
}

interface CheckResult {
  table_name: string;
  check_name: string;
  status: "PASS" | "FAIL" | "ERROR";
  failed_rows: number | null;
  source_value: string | null;
  target_value: string | null;
  message: string;
  fix_suggestion?: string;
}

interface QualityRunResponse {
  run_id: string;
  status: "PASS" | "FAIL";
  total_checks: number;
  passed: number;
  failed: number;
  results: CheckResult[];
}

interface QualityRunSummary {
  run_id: string;
  connection_id: number;
  connection_name: string;
  started_at: string;
  completed_at: string | null;
  total_checks: number;
  passed_checks: number;
  failed_checks: number;
  status: string;
}

// ── API calls (thin wrappers over the existing `api` axios client) ────────
const fetchQualityConnections = async (): Promise<QualityConnection[]> => {
  const r = await api.get("/quality/connections");
  return r.data?.connections ?? [];
};

const fetchQualityTables = async (connectionId: string): Promise<string[]> => {
  const r = await api.get("/quality/tables", { params: { connection_id: connectionId } });
  return r.data?.tables ?? [];
};

const fetchQualityTableColumns = async (connectionId: string, tableName: string): Promise<ColumnInfo[]> => {
  const r = await api.get("/quality/table-columns", { params: { connection_id: connectionId, table_name: tableName } });
  return r.data?.columns ?? [];
};

const fetchQualityRuns = async (): Promise<QualityRunSummary[]> => {
  const r = await api.get("/quality/runs");
  return r.data?.runs ?? [];
};

const runQualityChecks = async (payload: Record<string, unknown>): Promise<QualityRunResponse> => {
  const r = await api.post("/quality/run", payload);
  return r.data;
};

const resetSchemaBaseline = async (payload: { connection_id: number; table_name: string }) => {
  const r = await api.post("/quality/schema-baseline/reset", payload);
  return r.data;
};

// Optional LLM-powered remediation help on top of the rule-based
// `fix_suggestion` every failed/errored result already carries.
const askAiFix = async (payload: { results: CheckResult[]; connection_id?: number }): Promise<{ advice: string; checks_analyzed?: number }> => {
  const r = await api.post("/quality/ai-fix", payload);
  return r.data;
};

// Create a Postgres/Snowflake connection right from this page (same
// /connections endpoint the Connections page uses), so someone doesn't
// have to leave Quality Checks just to point it at a database.
const createConnection = async (payload: { name: string; source_type: string; config: Record<string, unknown> }) => {
  const r = await api.post("/connections", payload);
  return r.data;
};

const testConnectionConfig = async (payload: { source_type: string; config: Record<string, unknown> }): Promise<{ success: boolean; message: string }> => {
  const r = await api.post("/connectors/test", { ...payload, test_write: false });
  return r.data;
};

// ── Helpers ─────────────────────────────────────────────────────────────
// Pydantic validation errors arrive as an array of {loc, msg, ...} objects;
// a plain string detail also happens for HTTPException(detail="..."). This
// turns either shape into short, readable lines instead of raw JSON.
const formatApiError = (error: unknown): string => {
  const detail = (error as any)?.response?.data?.detail;
  if (!detail) return (error as Error)?.message ?? "Something went wrong.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: any) => {
        const field = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : undefined;
        return field ? `${field}: ${d.msg}` : d.msg ?? JSON.stringify(d);
      })
      .join("; ");
  }
  return JSON.stringify(detail);
};

const isNumericType = (type: string) => /int|numeric|decimal|real|double|float|money/i.test(type);

// Turns a friendly "flag a row when column [operator] value" rule into the
// raw SQL boolean condition backend/quality/checks.py expects (a condition
// that matches ZERO rows to pass — i.e. it describes the violation, not the
// valid state). This is the one place SQL gets generated, so the rest of
// the form never needs the user to write or read SQL themselves.
const OPERATORS = [
  { value: "gt", label: "is greater than", needsValue: true },
  { value: "gte", label: "is greater than or equal to", needsValue: true },
  { value: "lt", label: "is less than", needsValue: true },
  { value: "lte", label: "is less than or equal to", needsValue: true },
  { value: "eq", label: "equals", needsValue: true },
  { value: "neq", label: "does not equal", needsValue: true },
  { value: "contains", label: "contains", needsValue: true },
  { value: "not_contains", label: "does not contain", needsValue: true },
  { value: "is_blank", label: "is blank / empty", needsValue: false },
  { value: "is_not_blank", label: "is not blank / empty", needsValue: false },
] as const;
type OperatorValue = (typeof OPERATORS)[number]["value"];

const buildCondition = (column: string, operator: OperatorValue, value: string, colType: string): string => {
  const numeric = isNumericType(colType);
  const sqlValue = numeric ? (value.trim() || "0") : `'${value.replace(/'/g, "''")}'`;
  switch (operator) {
    case "gt": return `${column} > ${sqlValue}`;
    case "gte": return `${column} >= ${sqlValue}`;
    case "lt": return `${column} < ${sqlValue}`;
    case "lte": return `${column} <= ${sqlValue}`;
    case "eq": return `${column} = ${sqlValue}`;
    case "neq": return `${column} != ${sqlValue}`;
    case "contains": return `${column}::text LIKE '%${value.replace(/'/g, "''")}%'`;
    case "not_contains": return `${column}::text NOT LIKE '%${value.replace(/'/g, "''")}%'`;
    case "is_blank": return `(${column} IS NULL OR ${column}::text = '')`;
    case "is_not_blank": return `(${column} IS NOT NULL AND ${column}::text != '')`;
  }
};

const readableCondition = (column: string, operator: OperatorValue, value: string): string => {
  const op = OPERATORS.find((o) => o.value === operator);
  if (!op) return "";
  return op.needsValue ? `Flag a row when ${column} ${op.label} "${value}"` : `Flag a row when ${column} ${op.label}`;
};

// Quality checks run SQL under the hood (information_schema queries, checks
// on live tables), so only dialects the backend's SQL executor registry
// understands can ever work here — see backend/sql_executors/__init__.py.
// Everything else (S3, API, local folder, Google Sheet, Figma) would just
// fail with a confusing 502 the moment a table is picked, so we keep those
// out of this page entirely and only surface Postgres / Snowflake.
const SQL_CAPABLE_TYPES = ["postgres", "postgresql", "snowflake"];
const isSqlCapable = (sourceType: string) => SQL_CAPABLE_TYPES.includes((sourceType || "").toLowerCase());

type NewConnectionType = "postgres" | "snowflake";

const emptyNewConnection = {
  name: "",
  source_type: "postgres" as NewConnectionType,
  // Postgres
  host: "",
  database: "",
  user: "",
  password: "",
  port: "5432",
  pg_schema: "",
  // Snowflake
  account: "",
  warehouse: "",
  sf_schema: "PUBLIC",
  sf_role: "",
};

const AGGREGATES = [
  { value: "SUM", label: "Sum of" },
  { value: "AVG", label: "Average of" },
  { value: "COUNT", label: "Count of non-empty" },
  { value: "MIN", label: "Minimum of" },
  { value: "MAX", label: "Maximum of" },
  { value: "COUNT_ROWS", label: "Total row count" },
] as const;
type AggregateValue = (typeof AGGREGATES)[number]["value"];

const buildAggExpr = (agg: AggregateValue, column: string): string =>
  agg === "COUNT_ROWS" ? "COUNT(*)" : `${agg}(${column})`;

const STATUS_LABEL: Record<string, string> = { PASS: "PASS", FAIL: "FAIL", ERROR: "ERROR" };

const StatusBadge = ({ status }: { status: string }) => {
  const pass = status === "PASS";
  const errored = status === "ERROR";
  const classes = pass
    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400"
    : errored
    ? "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-400"
    : "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-400";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${classes}`}>
      {pass ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
      {STATUS_LABEL[status] ?? status}
    </span>
  );
};

// Collapsible wrapper for the "advanced" check sections, so the form isn't
// a giant wall of inputs by default. Shows a small badge when the section
// already has content, so a collapsed section's state is never invisible.
const CollapsibleSection = ({
  title,
  hint,
  count,
  defaultOpen = false,
  children,
}: {
  title: string;
  hint?: string;
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
}) => {
  const [open, setOpen] = useState(defaultOpen || !!count);
  return (
    <div className="rounded-md border border-border">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-medium text-foreground">
          {title}
          {!!count && (
            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
              {count} set
            </span>
          )}
        </span>
        <ChevronDown className={`h-4 w-4 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="space-y-3 border-t border-border p-3">
          {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
          {children}
        </div>
      )}
    </div>
  );
};

// Click-to-toggle chips for picking one or more columns — replaces typing
// a comma-separated list of column names from memory.
const MultiColumnSelect = ({
  columns,
  selected,
  onToggle,
  emptyHint,
  onSelectAll,
  onClear,
}: {
  columns: ColumnInfo[];
  selected: string[];
  onToggle: (column: string) => void;
  emptyHint: string;
  onSelectAll?: () => void;
  onClear?: () => void;
}) => {
  if (!columns.length) {
    return <p className="text-xs text-muted-foreground">{emptyHint}</p>;
  }
  const allSelected = selected.length === columns.length;
  return (
    <div className="space-y-1.5">
      {(onSelectAll || onClear) && (
        <div className="flex gap-2 text-xs">
          {onSelectAll && (
            <button
              type="button"
              className="text-primary hover:underline disabled:pointer-events-none disabled:opacity-40"
              disabled={allSelected}
              onClick={onSelectAll}
            >
              Select all {columns.length} columns
            </button>
          )}
          {onClear && !!selected.length && (
            <>
              <span className="text-muted-foreground">·</span>
              <button type="button" className="text-muted-foreground hover:underline" onClick={onClear}>
                Clear
              </button>
            </>
          )}
        </div>
      )}
      <div className="flex flex-wrap gap-1.5">
        {columns.map((col) => {
          const active = selected.includes(col.name);
          return (
            <button
              key={col.name}
              type="button"
              onClick={() => onToggle(col.name)}
              className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                active
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-background text-muted-foreground hover:text-foreground"
              }`}
            >
              {col.name}
            </button>
          );
        })}
      </div>
    </div>
  );
};

// Plain <select> populated from a fixed list of {value,label} options.
const Select = ({
  value,
  onChange,
  options,
  placeholder,
  disabled,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  placeholder: string;
  disabled?: boolean;
}) => (
  <select
    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground disabled:opacity-50"
    value={value}
    disabled={disabled}
    onChange={(e) => onChange(e.target.value)}
  >
    <option value="">{placeholder}</option>
    {options.map((o) => (
      <option key={o.value} value={o.value}>{o.label}</option>
    ))}
  </select>
);

// A column dropdown for a specific (connectionId, tableName) — used inside
// foreign-key and consistency rows, where each row can reference a
// different table. React Query caches by (connectionId, tableName), so
// picking the same table in two rows doesn't refetch.
const RemoteColumnSelect = ({
  connectionId,
  tableName,
  value,
  onChange,
  placeholder,
}: {
  connectionId: string;
  tableName: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) => {
  const { data, isFetching } = useQuery({
    queryKey: ["quality-table-columns", connectionId, tableName],
    queryFn: () => fetchQualityTableColumns(connectionId, tableName),
    enabled: !!connectionId && !!tableName,
  });
  return (
    <Select
      value={value}
      onChange={onChange}
      disabled={!tableName}
      placeholder={isFetching ? "Loading columns…" : placeholder}
      options={(data ?? []).map((c) => ({ value: c.name, label: c.name }))}
    />
  );
};

const emptyForm = {
  connectionId: "",
  tableName: "",
  freshnessColumn: "",
  freshnessThresholdHours: "24",
};

const FRESHNESS_PRESETS = [
  { label: "1 hour", hours: "1" },
  { label: "6 hours", hours: "6" },
  { label: "24 hours", hours: "24" },
  { label: "48 hours", hours: "48" },
  { label: "7 days", hours: "168" },
];

export const QualityChecks = () => {
  const queryClient = useQueryClient();

  // ── connection + table — everything else is driven off these ───────
  const [connectionId, setConnectionId] = useState<string>(emptyForm.connectionId);
  const [tableName, setTableName] = useState(emptyForm.tableName);
  const [manualTableEntry, setManualTableEntry] = useState(false);

  // ── column-picking checks (Uniqueness / Duplicate Detection / Completeness) ──
  const [primaryKey, setPrimaryKey] = useState<string[]>([]);
  const [businessKeys, setBusinessKeys] = useState<string[]>([]);
  const [nullColumns, setNullColumns] = useState<string[]>([]);
  const [expectedMinRows, setExpectedMinRows] = useState("");

  // ── freshness ────────────────────────────────────────────────────
  const [freshnessColumn, setFreshnessColumn] = useState(emptyForm.freshnessColumn);
  const [freshnessThresholdHours, setFreshnessThresholdHours] = useState(emptyForm.freshnessThresholdHours);
  const [customFreshness, setCustomFreshness] = useState(false);

  // ── advanced checks ──────────────────────────────────────────────
  const [businessRules, setBusinessRules] = useState<
    { column: string; operator: OperatorValue; value: string }[]
  >([]);
  const [foreignKeys, setForeignKeys] = useState<ForeignKeyRule[]>([]);
  const [dataTypeColumns, setDataTypeColumns] = useState<string[]>([]); // lock in current type
  const [rangeRules, setRangeRules] = useState<RangeRule[]>([]);
  const [outlierColumns, setOutlierColumns] = useState<string[]>([]);
  const [expectedColumnsSelected, setExpectedColumnsSelected] = useState<string[]>([]); // snapshot type
  const [schemaBaseline, setSchemaBaseline] = useState(false);
  const [consistencyRules, setConsistencyRules] = useState<
    { table_a: string; agg_a: AggregateValue; col_a: string; table_b: string; agg_b: AggregateValue; col_b: string; tolerance: string }[]
  >([]);

  const [noChecksWarning, setNoChecksWarning] = useState(false);

  const { data: connections, isFetching: connectionsLoading } = useQuery({
    queryKey: ["quality-connections"],
    queryFn: fetchQualityConnections,
  });

  // Only Postgres/Snowflake connections can actually run quality checks —
  // see SQL_CAPABLE_TYPES above.
  const sqlConnections = (connections ?? []).filter((c) => isSqlCapable(c.source_type));
  const otherConnectionsCount = (connections?.length ?? 0) - sqlConnections.length;

  // ── inline "add a new connection" form — lets a non-technical user
  // point Quality Checks at a database without leaving this page ──────
  const [newConnOpen, setNewConnOpen] = useState(false);
  const [newConn, setNewConn] = useState(emptyNewConnection);
  const [newConnTestResult, setNewConnTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [newConnTestPassed, setNewConnTestPassed] = useState(false);

  const updateNewConn = (patch: Partial<typeof emptyNewConnection>) => {
    setNewConn((prev) => ({ ...prev, ...patch }));
    setNewConnTestResult(null);
    setNewConnTestPassed(false);
  };

  const buildNewConnConfig = (): Record<string, unknown> => {
    if (newConn.source_type === "postgres") {
      const config: Record<string, unknown> = {
        host: newConn.host.trim(),
        database: newConn.database.trim(),
        user: newConn.user.trim(),
        password: newConn.password,
        port: newConn.port.trim() || "5432",
      };
      if (newConn.pg_schema.trim()) config.schema = newConn.pg_schema.trim();
      return config;
    }
    return {
      account: newConn.account.trim(),
      warehouse: newConn.warehouse.trim(),
      database: newConn.database.trim(),
      schema: newConn.sf_schema.trim() || "PUBLIC",
      user: newConn.user.trim(),
      password: newConn.password,
      role: newConn.sf_role.trim(),
    };
  };

  const testNewConnMutation = useMutation({
    mutationFn: () => testConnectionConfig({ source_type: newConn.source_type, config: buildNewConnConfig() }),
    onSuccess: (data) => {
      setNewConnTestResult(data);
      setNewConnTestPassed(!!data.success);
    },
    onError: (error) => {
      setNewConnTestResult({ success: false, message: formatApiError(error) });
      setNewConnTestPassed(false);
    },
  });

  const createConnMutation = useMutation({
    mutationFn: () => createConnection({ name: newConn.name.trim(), source_type: newConn.source_type, config: buildNewConnConfig() }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["quality-connections"] });
      setConnectionId(String(data.id));
      setNewConnOpen(false);
      setNewConn(emptyNewConnection);
      setNewConnTestResult(null);
      setNewConnTestPassed(false);
    },
  });

  const cancelNewConn = () => {
    setNewConnOpen(false);
    setNewConn(emptyNewConnection);
    setNewConnTestResult(null);
    setNewConnTestPassed(false);
  };

  const { data: tables, isFetching: tablesLoading, isError: tablesErrored } = useQuery({
    queryKey: ["quality-tables", connectionId],
    queryFn: () => fetchQualityTables(connectionId),
    enabled: !!connectionId && !manualTableEntry,
  });

  const { data: columns, isFetching: columnsLoading } = useQuery({
    queryKey: ["quality-table-columns", connectionId, tableName],
    queryFn: () => fetchQualityTableColumns(connectionId, tableName),
    enabled: !!connectionId && !!tableName,
  });

  const columnList = columns ?? [];
  const columnTypeOf = (name: string) => columnList.find((c) => c.name === name)?.type ?? "";

  const { data: runs, isFetching: runsLoading } = useQuery({
    queryKey: ["quality-runs"],
    queryFn: fetchQualityRuns,
  });

  const runMutation = useMutation({
    mutationFn: runQualityChecks,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["quality-runs"] });
    },
  });

  // AI-assisted fix help for the checks that failed in the most recent run.
  const [aiFixAdvice, setAiFixAdvice] = useState<string | null>(null);
  const aiFixMutation = useMutation({
    mutationFn: askAiFix,
    onSuccess: (data) => setAiFixAdvice(data.advice),
    onError: () => setAiFixAdvice(null),
  });

  const askAiForFixHelp = () => {
    const failing = (runMutation.data?.results ?? []).filter((r) => r.status !== "PASS");
    if (!failing.length) return;
    setAiFixAdvice(null);
    aiFixMutation.mutate({ results: failing, connection_id: connectionId ? Number(connectionId) : undefined });
  };

  const resetBaselineMutation = useMutation({
    mutationFn: resetSchemaBaseline,
  });

  // A different connection or table means a different schema — every
  // column-based selection made so far no longer applies.
  useEffect(() => {
    setPrimaryKey([]);
    setBusinessKeys([]);
    setNullColumns([]);
    setFreshnessColumn(emptyForm.freshnessColumn);
    setBusinessRules([]);
    setForeignKeys([]);
    setDataTypeColumns([]);
    setRangeRules([]);
    setOutlierColumns([]);
    setExpectedColumnsSelected([]);
    setSchemaBaseline(false);
    setConsistencyRules([]);
    setNoChecksWarning(false);
    runMutation.reset();
    setAiFixAdvice(null);
  }, [connectionId, tableName]);

  useEffect(() => {
    setTableName("");
    setManualTableEntry(false);
  }, [connectionId]);

  const toggleInList = (setter: (fn: (prev: string[]) => string[]) => void, column: string) =>
    setter((prev) => (prev.includes(column) ? prev.filter((c) => c !== column) : [...prev, column]));

  const addRow = <T,>(setter: (fn: (prev: T[]) => T[]) => void, empty: T) =>
    setter((prev) => [...prev, empty]);
  const updateRow = <T,>(setter: (fn: (prev: T[]) => T[]) => void, index: number, patch: Partial<T>) =>
    setter((prev) => prev.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  const removeRow = <T,>(setter: (fn: (prev: T[]) => T[]) => void, index: number) =>
    setter((prev) => prev.filter((_, i) => i !== index));

  const resetForm = () => {
    setConnectionId(emptyForm.connectionId);
    setTableName(emptyForm.tableName);
    setManualTableEntry(false);
    setPrimaryKey([]);
    setBusinessKeys([]);
    setNullColumns([]);
    setExpectedMinRows("");
    setFreshnessColumn(emptyForm.freshnessColumn);
    setFreshnessThresholdHours(emptyForm.freshnessThresholdHours);
    setCustomFreshness(false);
    setBusinessRules([]);
    setForeignKeys([]);
    setDataTypeColumns([]);
    setRangeRules([]);
    setOutlierColumns([]);
    setExpectedColumnsSelected([]);
    setSchemaBaseline(false);
    setConsistencyRules([]);
    setNoChecksWarning(false);
    runMutation.reset();
  };

  const buildTableSpec = (): Record<string, unknown> => {
    const tableSpec: Record<string, unknown> = { table_name: tableName.trim() };

    if (primaryKey.length) tableSpec.primary_key = primaryKey;
    if (businessKeys.length) tableSpec.business_keys = businessKeys;
    if (nullColumns.length) tableSpec.null_columns = nullColumns;

    if (expectedMinRows.trim() && !Number.isNaN(Number(expectedMinRows))) {
      tableSpec.expected_min_rows = Number(expectedMinRows);
    }

    if (freshnessColumn.trim() && freshnessThresholdHours.trim() && !Number.isNaN(Number(freshnessThresholdHours))) {
      tableSpec.freshness_column = freshnessColumn.trim();
      tableSpec.freshness_threshold_hours = Number(freshnessThresholdHours);
    }

    const rules = businessRules
      .filter((r) => r.column && (OPERATORS.find((o) => o.value === r.operator)?.needsValue ? r.value.trim() : true))
      .map((r) => ({ column: r.column, condition: buildCondition(r.column, r.operator, r.value, columnTypeOf(r.column)) }));
    if (rules.length) tableSpec.business_rules = rules;

    const fks = foreignKeys.filter((f) => f.column.trim() && f.parent_table.trim() && f.parent_column.trim());
    if (fks.length) tableSpec.foreign_keys = fks;

    if (dataTypeColumns.length) {
      tableSpec.data_types = Object.fromEntries(dataTypeColumns.map((c) => [c, columnTypeOf(c)]));
    }

    const ranges = rangeRules.filter((r) => r.column.trim() && (r.min.trim() || r.max.trim()));
    if (ranges.length) {
      tableSpec.range_checks = Object.fromEntries(
        ranges.map((r) => [
          r.column.trim(),
          {
            ...(r.min.trim() && !Number.isNaN(Number(r.min)) ? { min: Number(r.min) } : {}),
            ...(r.max.trim() && !Number.isNaN(Number(r.max)) ? { max: Number(r.max) } : {}),
          },
        ])
      );
    }

    if (outlierColumns.length) tableSpec.outlier_columns = outlierColumns;

    if (expectedColumnsSelected.length) {
      tableSpec.expected_columns = Object.fromEntries(expectedColumnsSelected.map((c) => [c, columnTypeOf(c)]));
    }

    if (schemaBaseline) tableSpec.schema_baseline = true;

    return tableSpec;
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!connectionId || !tableName.trim()) return;

    const tableSpec = buildTableSpec();
    // table_name is always present — anything beyond that means at least
    // one real check was configured.
    const hasAnyCheck = Object.keys(tableSpec).length > 1;

    const consistency_checks = consistencyRules
      .filter((c) => c.table_a && c.col_a && c.table_b && c.col_b)
      .map((c) => ({
        table_a: c.table_a,
        expr_a: buildAggExpr(c.agg_a, c.col_a),
        table_b: c.table_b,
        expr_b: buildAggExpr(c.agg_b, c.col_b),
        tolerance: c.tolerance.trim() && !Number.isNaN(Number(c.tolerance)) ? Number(c.tolerance) : 0,
      }));

    if (!hasAnyCheck && !consistency_checks.length) {
      setNoChecksWarning(true);
      return;
    }
    setNoChecksWarning(false);

    runMutation.mutate({
      connection_id: Number(connectionId),
      tables: [tableSpec],
      ...(consistency_checks.length ? { consistency_checks } : {}),
    });
  };

  const results = runMutation.data?.results ?? [];
  const canResetBaseline = schemaBaseline && tableName.trim() && connectionId;
  const schemaReady = !!connectionId && !!tableName;

  return (
    <div className="space-y-5">
      <PageHeader
        icon={ShieldCheck}
        eyebrow="Data"
        title="Data Quality"
        description="Connect a Postgres or Snowflake database, pick a table, then click together the checks you want — no SQL or typing column names from memory required."
      />

      <Card>
        <CardHeader><CardTitle className="text-sm">Run checks</CardTitle></CardHeader>
        <CardContent>
          <fieldset disabled={runMutation.isPending} className="space-y-5">
            <form onSubmit={submit} className="space-y-5">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div>
                  <label htmlFor="qc-connection" className="mb-1 flex items-center justify-between text-xs font-medium text-muted-foreground">
                    <span>Connection</span>
                    <button
                      type="button"
                      className="flex items-center gap-1 text-primary hover:underline"
                      onClick={() => setNewConnOpen((v) => !v)}
                    >
                      {newConnOpen ? <X className="h-3 w-3" /> : <Plus className="h-3 w-3" />}
                      {newConnOpen ? "Cancel" : "New connection"}
                    </button>
                  </label>
                  <select
                    id="qc-connection"
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                    value={connectionId}
                    onChange={(e) => setConnectionId(e.target.value)}
                    disabled={newConnOpen}
                    required
                  >
                    <option value="" disabled>
                      {connectionsLoading ? "Loading connections…" : "Select a database"}
                    </option>
                    {sqlConnections.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.name} ({c.source_type})
                      </option>
                    ))}
                  </select>
                  {!connectionsLoading && !sqlConnections.length && !newConnOpen && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      No Postgres or Snowflake connections yet — add one with "New connection" above.
                    </p>
                  )}
                  {!!otherConnectionsCount && !newConnOpen && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {otherConnectionsCount} other saved connection{otherConnectionsCount === 1 ? "" : "s"} (S3, API, etc.) not shown — quality checks only run against Postgres or Snowflake.
                    </p>
                  )}
                </div>
                <div>
                  <label htmlFor="qc-table" className="mb-1 flex items-center justify-between text-xs font-medium text-muted-foreground">
                    <span>Table</span>
                    {!!connectionId && (tablesErrored || manualTableEntry) && (
                      <button
                        type="button"
                        className="text-primary hover:underline"
                        onClick={() => setManualTableEntry((v) => !v)}
                      >
                        {manualTableEntry ? "Pick from list instead" : "Type it manually"}
                      </button>
                    )}
                  </label>
                  {manualTableEntry || tablesErrored ? (
                    <Input
                      id="qc-table"
                      placeholder="customers"
                      value={tableName}
                      onChange={(e) => setTableName(e.target.value)}
                      required
                      disabled={!connectionId}
                    />
                  ) : (
                    <select
                      id="qc-table"
                      className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm disabled:opacity-50"
                      value={tableName}
                      onChange={(e) => setTableName(e.target.value)}
                      disabled={!connectionId}
                      required
                    >
                      <option value="" disabled>
                        {!connectionId ? "Pick a connection first" : tablesLoading ? "Loading tables…" : "Select a table"}
                      </option>
                      {tables?.map((t) => (
                        <option key={t} value={t}>{t}</option>
                      ))}
                    </select>
                  )}
                </div>
              </div>

              {newConnOpen && (
                <div className="space-y-3 rounded-md border border-border bg-muted/30 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <DatabaseZap className="h-4 w-4" />
                    Connect a database
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium text-muted-foreground">Database type</label>
                    <div className="flex gap-1.5">
                      {(["postgres", "snowflake"] as NewConnectionType[]).map((t) => (
                        <button
                          key={t}
                          type="button"
                          onClick={() => updateNewConn({ source_type: t })}
                          className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                            newConn.source_type === t
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-border bg-background text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {t === "postgres" ? "Postgres" : "Snowflake"}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label htmlFor="newconn-name" className="mb-1 block text-xs font-medium text-muted-foreground">
                      Connection name
                    </label>
                    <Input
                      id="newconn-name"
                      placeholder="e.g. Production analytics"
                      value={newConn.name}
                      onChange={(e) => updateNewConn({ name: e.target.value })}
                    />
                    <p className="mt-1 text-xs text-muted-foreground">How this shows up in the connection list above.</p>
                  </div>

                  {newConn.source_type === "postgres" ? (
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <Input placeholder="Host, e.g. db.company.com" value={newConn.host} onChange={(e) => updateNewConn({ host: e.target.value })} />
                      <Input placeholder="Database name" value={newConn.database} onChange={(e) => updateNewConn({ database: e.target.value })} />
                      <Input placeholder="Username" value={newConn.user} onChange={(e) => updateNewConn({ user: e.target.value })} />
                      <Input placeholder="Password" type="password" value={newConn.password} onChange={(e) => updateNewConn({ password: e.target.value })} />
                      <Input placeholder="Port (default 5432)" value={newConn.port} onChange={(e) => updateNewConn({ port: e.target.value })} />
                      <Input placeholder="Schema (optional, default public)" value={newConn.pg_schema} onChange={(e) => updateNewConn({ pg_schema: e.target.value })} />
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                      <Input placeholder="Account, e.g. xy12345.us-east-1" value={newConn.account} onChange={(e) => updateNewConn({ account: e.target.value })} />
                      <Input placeholder="Warehouse" value={newConn.warehouse} onChange={(e) => updateNewConn({ warehouse: e.target.value })} />
                      <Input placeholder="Database name" value={newConn.database} onChange={(e) => updateNewConn({ database: e.target.value })} />
                      <Input placeholder="Schema (default PUBLIC)" value={newConn.sf_schema} onChange={(e) => updateNewConn({ sf_schema: e.target.value })} />
                      <Input placeholder="Username" value={newConn.user} onChange={(e) => updateNewConn({ user: e.target.value })} />
                      <Input placeholder="Password" type="password" value={newConn.password} onChange={(e) => updateNewConn({ password: e.target.value })} />
                      <Input placeholder="Role (optional)" value={newConn.sf_role} onChange={(e) => updateNewConn({ sf_role: e.target.value })} />
                    </div>
                  )}

                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button
                      type="button"
                      variant="outline"
                      className="sm:w-auto"
                      disabled={testNewConnMutation.isPending || !newConn.name.trim()}
                      onClick={() => testNewConnMutation.mutate()}
                    >
                      {testNewConnMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Wifi className="h-4 w-4" />}
                      Test connection
                    </Button>
                    <Button
                      type="button"
                      className="sm:w-auto"
                      disabled={createConnMutation.isPending || !newConnTestPassed || !newConn.name.trim()}
                      title={!newConnTestPassed ? "Test the connection first" : ""}
                      onClick={() => createConnMutation.mutate()}
                    >
                      {createConnMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                      Save &amp; use this connection
                    </Button>
                    <Button type="button" variant="ghost" className="sm:w-auto" onClick={cancelNewConn}>
                      Cancel
                    </Button>
                  </div>

                  {!newConnTestPassed && newConn.name.trim() && (
                    <p className="text-xs text-muted-foreground">Test the connection first to enable saving.</p>
                  )}

                  {newConnTestResult && (
                    <div
                      className={`flex items-center gap-2 rounded-md p-3 text-sm ${
                        newConnTestResult.success
                          ? "border border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/30 dark:text-emerald-300"
                          : "border border-destructive/20 bg-destructive/10 text-destructive"
                      }`}
                    >
                      {newConnTestResult.success ? <CheckCircle className="h-4 w-4 shrink-0" /> : <XCircle className="h-4 w-4 shrink-0" />}
                      <span>{newConnTestResult.message}</span>
                    </div>
                  )}

                  {createConnMutation.isError && (
                    <p className="flex items-center gap-1 text-xs text-rose-700 dark:text-rose-400">
                      <XCircle className="h-3.5 w-3.5" /> {formatApiError(createConnMutation.error)}
                    </p>
                  )}
                </div>
              )}

              {!!connectionId && !!tableName && columnsLoading && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading this table's columns…
                </p>
              )}

              {schemaReady && !columnsLoading && (
                <>
                  {/* Completeness / Uniqueness / Duplicate Detection / Record Count — kept
                      always visible since these are the most commonly used checks. */}
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-muted-foreground">
                        No duplicate values in (Uniqueness)
                      </label>
                      <MultiColumnSelect
                        columns={columnList}
                        selected={primaryKey}
                        onToggle={(c) => toggleInList(setPrimaryKey, c)}
                        emptyHint="No columns found for this table."
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-muted-foreground">
                        No duplicate records on (Duplicate Detection)
                      </label>
                      <MultiColumnSelect
                        columns={columnList}
                        selected={businessKeys}
                        onToggle={(c) => toggleInList(setBusinessKeys, c)}
                        emptyHint="No columns found for this table."
                      />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-muted-foreground">
                        Must never be empty (Completeness)
                      </label>
                      <MultiColumnSelect
                        columns={columnList}
                        selected={nullColumns}
                        onToggle={(c) => toggleInList(setNullColumns, c)}
                        emptyHint="No columns found for this table."
                      />
                    </div>
                    <div>
                      <label htmlFor="qc-minrows" className="mb-1 block text-xs font-medium text-muted-foreground">
                        Table should have at least this many rows
                      </label>
                      <Input id="qc-minrows" type="number" placeholder="e.g. 1" value={expectedMinRows} onChange={(e) => setExpectedMinRows(e.target.value)} />
                    </div>
                  </div>

                  {/* Freshness */}
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <div>
                      <label className="mb-1 block text-xs font-medium text-muted-foreground">
                        Freshness — which column holds the last-updated date? (optional)
                      </label>
                      <Select
                        value={freshnessColumn}
                        onChange={setFreshnessColumn}
                        placeholder="No freshness check"
                        options={columnList.map((c) => ({ value: c.name, label: c.name }))}
                      />
                    </div>
                    {freshnessColumn && (
                      <div>
                        <label className="mb-1 block text-xs font-medium text-muted-foreground">
                          It should have been updated within
                        </label>
                        {customFreshness ? (
                          <div className="flex items-center gap-2">
                            <Input
                              type="number"
                              placeholder="hours"
                              value={freshnessThresholdHours}
                              onChange={(e) => setFreshnessThresholdHours(e.target.value)}
                            />
                            <span className="whitespace-nowrap text-xs text-muted-foreground">hours</span>
                            <button type="button" className="text-xs text-primary hover:underline" onClick={() => setCustomFreshness(false)}>
                              Use a preset
                            </button>
                          </div>
                        ) : (
                          <div className="flex flex-wrap items-center gap-1.5">
                            {FRESHNESS_PRESETS.map((p) => (
                              <button
                                key={p.hours}
                                type="button"
                                onClick={() => setFreshnessThresholdHours(p.hours)}
                                className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
                                  freshnessThresholdHours === p.hours
                                    ? "border-primary bg-primary/10 text-primary"
                                    : "border-border bg-background text-muted-foreground hover:text-foreground"
                                }`}
                              >
                                {p.label}
                              </button>
                            ))}
                            <button type="button" className="text-xs text-primary hover:underline" onClick={() => setCustomFreshness(true)}>
                              Custom…
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* ── Advanced checks — collapsed by default, auto-expand if they
                      already have content (e.g. after an error, or when editing). ── */}
                  <div className="space-y-3">
                    <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Advanced checks</p>

                    <CollapsibleSection
                      title="Validity — flag rows that break a rule"
                      hint="Pick a column, a comparison, and a value — we build the check for you."
                      count={businessRules.filter((r) => r.column).length}
                    >
                      {businessRules.map((rule, index) => {
                        const op = OPERATORS.find((o) => o.value === rule.operator);
                        const numeric = isNumericType(columnTypeOf(rule.column));
                        return (
                          <div key={index} className="mb-2 space-y-2 rounded-md border border-border p-2">
                            <div className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_1fr_1fr_auto]">
                              <Select
                                value={rule.column}
                                onChange={(v) => updateRow(setBusinessRules, index, { column: v })}
                                placeholder="Column"
                                options={columnList.map((c) => ({ value: c.name, label: c.name }))}
                              />
                              <Select
                                value={rule.operator}
                                onChange={(v) => updateRow(setBusinessRules, index, { operator: v as OperatorValue })}
                                placeholder="Comparison"
                                options={OPERATORS.map((o) => ({ value: o.value, label: o.label }))}
                              />
                              {op?.needsValue ? (
                                <Input
                                  type={numeric ? "number" : "text"}
                                  placeholder="value"
                                  value={rule.value}
                                  onChange={(e) => updateRow(setBusinessRules, index, { value: e.target.value })}
                                />
                              ) : (
                                <div />
                              )}
                              <Button type="button" variant="ghost" size="icon" onClick={() => removeRow(setBusinessRules, index)}>
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            </div>
                            {rule.column && rule.operator && (
                              <p className="text-xs text-muted-foreground">
                                {readableCondition(rule.column, rule.operator, rule.value)}
                              </p>
                            )}
                          </div>
                        );
                      })}
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => addRow(setBusinessRules, { column: "", operator: "gt" as OperatorValue, value: "" })}
                      >
                        <Plus className="h-3.5 w-3.5" /> Add rule
                      </Button>
                    </CollapsibleSection>

                    <CollapsibleSection
                      title="Referential integrity — must match another table"
                      hint="Every value in the column below should exist in the parent table's column."
                      count={foreignKeys.filter((f) => f.column && f.parent_table && f.parent_column).length}
                    >
                      {foreignKeys.map((fk, index) => (
                        <div key={index} className="mb-2 grid grid-cols-1 gap-2 md:grid-cols-[1fr_1fr_1fr_auto]">
                          <Select
                            value={fk.column}
                            onChange={(v) => updateRow(setForeignKeys, index, { column: v })}
                            placeholder="This table's column"
                            options={columnList.map((c) => ({ value: c.name, label: c.name }))}
                          />
                          <Select
                            value={fk.parent_table}
                            onChange={(v) => updateRow(setForeignKeys, index, { parent_table: v, parent_column: "" })}
                            placeholder="Parent table"
                            options={(tables ?? []).map((t) => ({ value: t, label: t }))}
                          />
                          <RemoteColumnSelect
                            connectionId={connectionId}
                            tableName={fk.parent_table}
                            value={fk.parent_column}
                            onChange={(v) => updateRow(setForeignKeys, index, { parent_column: v })}
                            placeholder="Parent column"
                          />
                          <Button type="button" variant="ghost" size="icon" onClick={() => removeRow(setForeignKeys, index)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => addRow(setForeignKeys, { column: "", parent_table: "", parent_column: "" })}
                      >
                        <Plus className="h-3.5 w-3.5" /> Add relationship
                      </Button>
                    </CollapsibleSection>

                    <CollapsibleSection
                      title="Data type — lock in a column's current type"
                      hint="Just click a column — we snapshot whatever type it currently is (text, number, date…) and flag it if that ever changes. No need to type or pick a type yourself."
                      count={dataTypeColumns.length}
                    >
                      <MultiColumnSelect
                        columns={columnList}
                        selected={dataTypeColumns}
                        onToggle={(c) => toggleInList(setDataTypeColumns, c)}
                        onSelectAll={() => setDataTypeColumns(columnList.map((c) => c.name))}
                        onClear={() => setDataTypeColumns([])}
                        emptyHint="No columns found for this table."
                      />
                      {/* Live preview — this is the exact type each selected column will be
                          locked to. Nothing "happens" visually on click otherwise, since the
                          real check only runs when "Run checks" is pressed below; this closes
                          that gap so the click has an immediate, visible effect. */}
                      {!!dataTypeColumns.length && (
                        <div className="mt-2 rounded-md border border-border bg-muted/30 p-2">
                          <p className="mb-1 text-xs font-medium text-muted-foreground">
                            Will be saved as the expected type — future runs FAIL if any of these change:
                          </p>
                          <div className="flex flex-wrap gap-x-4 gap-y-1">
                            {dataTypeColumns.map((c) => (
                              <span key={c} className="font-mono text-xs text-foreground">
                                {c} <span className="text-muted-foreground">→ {columnTypeOf(c) || "?"}</span>
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </CollapsibleSection>

                    <CollapsibleSection
                      title="Range checks — values must stay between two numbers"
                      hint="Leave min or max blank to skip that bound."
                      count={rangeRules.filter((r) => r.column.trim() && (r.min.trim() || r.max.trim())).length}
                    >
                      {rangeRules.map((rule, index) => (
                        <div key={index} className="mb-2 grid grid-cols-1 gap-2 md:grid-cols-[1fr_1fr_1fr_auto]">
                          <Select
                            value={rule.column}
                            onChange={(v) => updateRow(setRangeRules, index, { column: v })}
                            placeholder="Column"
                            options={columnList.map((c) => ({ value: c.name, label: c.name }))}
                          />
                          <Input placeholder="min (e.g. 0)" value={rule.min} onChange={(e) => updateRow(setRangeRules, index, { min: e.target.value })} />
                          <Input placeholder="max (e.g. 120)" value={rule.max} onChange={(e) => updateRow(setRangeRules, index, { max: e.target.value })} />
                          <Button type="button" variant="ghost" size="icon" onClick={() => removeRow(setRangeRules, index)}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      ))}
                      <Button type="button" variant="outline" size="sm" onClick={() => addRow(setRangeRules, { column: "", min: "", max: "" })}>
                        <Plus className="h-3.5 w-3.5" /> Add range
                      </Button>
                    </CollapsibleSection>

                    <CollapsibleSection
                      title="Outlier detection"
                      hint="Flags unusually high/low values (IQR method). Pick numeric columns."
                      count={outlierColumns.length}
                    >
                      <MultiColumnSelect
                        columns={columnList.filter((c) => isNumericType(c.type))}
                        selected={outlierColumns}
                        onToggle={(c) => toggleInList(setOutlierColumns, c)}
                        emptyHint="No numeric columns found for this table."
                      />
                    </CollapsibleSection>

                    <CollapsibleSection
                      title="Schema validation"
                      hint="Baseline drift and a manual snapshot can both be used together — they run as independent checks."
                      count={(schemaBaseline ? 1 : 0) + expectedColumnsSelected.length}
                    >
                      <div className="space-y-3">
                        <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                          <input type="checkbox" checked={schemaBaseline} onChange={(e) => setSchemaBaseline(e.target.checked)} />
                          Watch this table for any schema change (new/missing/changed columns)
                        </label>
                        {canResetBaseline && (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            onClick={() =>
                              resetBaselineMutation.mutate({ connection_id: Number(connectionId), table_name: tableName.trim() })
                            }
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                            {resetBaselineMutation.isPending ? "Resetting…" : "Reset baseline (after an intentional schema change)"}
                          </Button>
                        )}
                        {resetBaselineMutation.isSuccess && (
                          <p className="flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-400">
                            <CheckCircle2 className="h-3.5 w-3.5" /> Baseline reset — next run will capture a fresh snapshot.
                          </p>
                        )}
                        {resetBaselineMutation.isError && (
                          <p className="flex items-center gap-1 text-xs text-rose-700 dark:text-rose-400">
                            <XCircle className="h-3.5 w-3.5" /> {formatApiError(resetBaselineMutation.error)}
                          </p>
                        )}
                        <div>
                          <label className="mb-1 block text-xs font-medium text-muted-foreground">
                            Or list the exact columns this table must have
                          </label>
                          <p className="mb-1.5 text-xs text-amber-700 dark:text-amber-400">
                            ⚠️ Select every column you expect — any column NOT selected here will be flagged as
                            unexpected/new. If you just want to catch future changes without listing every column,
                            use "Watch this table" above instead.
                          </p>
                          <MultiColumnSelect
                            columns={columnList}
                            selected={expectedColumnsSelected}
                            onToggle={(c) => toggleInList(setExpectedColumnsSelected, c)}
                            onSelectAll={() => setExpectedColumnsSelected(columnList.map((c) => c.name))}
                            onClear={() => setExpectedColumnsSelected([])}
                            emptyHint="No columns found for this table."
                          />
                          {/* Live preview — makes the "everything else gets flagged" rule
                              concrete instead of abstract, right where the click happened. */}
                          {!!expectedColumnsSelected.length && (
                            <div className="mt-2 rounded-md border border-border bg-muted/30 p-2 text-xs">
                              <p className="text-emerald-700 dark:text-emerald-400">
                                ✓ {expectedColumnsSelected.length} of {columnList.length} columns required — will PASS as long as these exist.
                              </p>
                              {columnList.length > expectedColumnsSelected.length && (
                                <p className="mt-1 text-rose-700 dark:text-rose-400">
                                  ✗ These {columnList.length - expectedColumnsSelected.length} will be flagged as "new/unexpected" on every run:{" "}
                                  <span className="font-mono">
                                    {columnList
                                      .filter((c) => !expectedColumnsSelected.includes(c.name))
                                      .map((c) => c.name)
                                      .join(", ")}
                                  </span>
                                </p>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </CollapsibleSection>

                    <CollapsibleSection
                      title="Consistency — compare against another table"
                      hint="Compare an aggregate (sum, count, etc.) between two tables in this connection."
                      count={consistencyRules.filter((c) => c.table_a && c.col_a && c.table_b && c.col_b).length}
                    >
                      {consistencyRules.map((rule, index) => (
                        <div key={index} className="mb-3 space-y-2 rounded-md border border-border p-2">
                          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                            <Select
                              value={rule.table_a}
                              onChange={(v) => updateRow(setConsistencyRules, index, { table_a: v, col_a: "" })}
                              placeholder="First table"
                              options={(tables ?? []).map((t) => ({ value: t, label: t }))}
                            />
                            <Select
                              value={rule.agg_a}
                              onChange={(v) => updateRow(setConsistencyRules, index, { agg_a: v as AggregateValue })}
                              placeholder="Aggregate"
                              options={AGGREGATES.map((a) => ({ value: a.value, label: a.label }))}
                            />
                            {rule.agg_a !== "COUNT_ROWS" ? (
                              <RemoteColumnSelect
                                connectionId={connectionId}
                                tableName={rule.table_a}
                                value={rule.col_a}
                                onChange={(v) => updateRow(setConsistencyRules, index, { col_a: v })}
                                placeholder="Column"
                              />
                            ) : <div />}
                          </div>
                          <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                            <Select
                              value={rule.table_b}
                              onChange={(v) => updateRow(setConsistencyRules, index, { table_b: v, col_b: "" })}
                              placeholder="Second table"
                              options={(tables ?? []).map((t) => ({ value: t, label: t }))}
                            />
                            <Select
                              value={rule.agg_b}
                              onChange={(v) => updateRow(setConsistencyRules, index, { agg_b: v as AggregateValue })}
                              placeholder="Aggregate"
                              options={AGGREGATES.map((a) => ({ value: a.value, label: a.label }))}
                            />
                            {rule.agg_b !== "COUNT_ROWS" ? (
                              <RemoteColumnSelect
                                connectionId={connectionId}
                                tableName={rule.table_b}
                                value={rule.col_b}
                                onChange={(v) => updateRow(setConsistencyRules, index, { col_b: v })}
                                placeholder="Column"
                              />
                            ) : <div />}
                          </div>
                          <div className="flex items-center gap-2">
                            <label className="text-xs text-muted-foreground">Allowed difference (tolerance)</label>
                            <Input
                              type="number"
                              placeholder="0"
                              value={rule.tolerance}
                              onChange={(e) => updateRow(setConsistencyRules, index, { tolerance: e.target.value })}
                              className="max-w-[120px]"
                            />
                            <Button type="button" variant="ghost" size="icon" onClick={() => removeRow(setConsistencyRules, index)}>
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </div>
                      ))}
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                          addRow(setConsistencyRules, {
                            table_a: "", agg_a: "SUM" as AggregateValue, col_a: "",
                            table_b: "", agg_b: "SUM" as AggregateValue, col_b: "",
                            tolerance: "0",
                          })
                        }
                      >
                        <Plus className="h-3.5 w-3.5" /> Add comparison
                      </Button>
                    </CollapsibleSection>
                  </div>
                </>
              )}

              {noChecksWarning && (
                <p className="flex items-center gap-2 text-xs text-amber-700 dark:text-amber-400">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  Pick at least one check above before running — nothing is configured yet.
                </p>
              )}

              <div className="flex items-center gap-2">
                <Button type="submit" disabled={runMutation.isPending || !schemaReady}>
                  {runMutation.isPending ? "Running checks…" : "Run checks"}
                </Button>
                <Button type="button" variant="outline" onClick={resetForm} disabled={runMutation.isPending}>
                  Clear form
                </Button>
              </div>
            </form>
          </fieldset>
        </CardContent>
      </Card>

      {runMutation.isError && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950">
          <CardContent className="p-4 text-sm text-rose-700 dark:text-rose-400">
            {formatApiError(runMutation.error)}
          </CardContent>
        </Card>
      )}

      {runMutation.isSuccess && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-3">
            <CardTitle className="text-sm">
              Results — <StatusBadge status={runMutation.data.status} /> ({runMutation.data.passed}/{runMutation.data.total_checks} passed)
            </CardTitle>
            {runMutation.data.status === "FAIL" && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={askAiForFixHelp}
                disabled={aiFixMutation.isPending}
              >
                {aiFixMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                Ask AI to help fix
              </Button>
            )}
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="overflow-auto rounded-md border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Table</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Check</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Status</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Failed rows</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Message</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, i) => (
                    <tr key={i} className="border-t border-border align-top">
                      <td className="px-3 py-2 text-xs text-muted-foreground">{r.table_name}</td>
                      <td className="px-3 py-2 font-mono text-xs text-foreground">{r.check_name}</td>
                      <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                      <td className="px-3 py-2 text-foreground">{r.failed_rows ?? "—"}</td>
                      <td className="max-w-md whitespace-pre-wrap break-words px-3 py-2 text-muted-foreground">
                        <div>{r.message}</div>
                        {r.status !== "PASS" && r.fix_suggestion && (
                          <div className="mt-1.5 flex gap-1.5 rounded-md bg-amber-50 px-2 py-1.5 text-xs text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                            <Wrench className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                            <span>{r.fix_suggestion}</span>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {aiFixMutation.isError && (
              <div className="rounded-md border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-400">
                {formatApiError(aiFixMutation.error)}
              </div>
            )}

            {aiFixAdvice && (
              <div className="rounded-md border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-200">
                <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide">
                  <Sparkles className="h-3.5 w-3.5" /> AI fix suggestions
                </div>
                <div className="whitespace-pre-wrap">{aiFixAdvice}</div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-sm">Run history</CardTitle></CardHeader>
        <CardContent>
          {runsLoading ? (
            <RowSkeleton rows={3} />
          ) : runs?.length ? (
            <div className="overflow-auto rounded-md border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Connection</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Started</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Status</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-muted-foreground">Checks</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((run) => (
                    <tr key={run.run_id} className="border-t border-border">
                      <td className="px-3 py-2 text-foreground">{run.connection_name}</td>
                      <td className="px-3 py-2 text-muted-foreground">{new Date(run.started_at).toLocaleString()}</td>
                      <td className="px-3 py-2"><StatusBadge status={run.status} /></td>
                      <td className="px-3 py-2 text-foreground">{run.passed_checks}/{run.total_checks}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={ShieldCheck}
              title="No quality runs yet"
              body="Run your first check above to see history here."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
};
