import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Plus, Trash2, CheckCircle2, XCircle, RotateCcw } from "lucide-react";
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

interface BusinessRule {
  column: string;
  condition: string;
}

interface ForeignKeyRule {
  column: string;
  parent_table: string;
  parent_column: string;
}

interface DataTypeRule {
  column: string;
  type: string;
}

interface RangeRule {
  column: string;
  min: string;
  max: string;
}

interface SchemaColumnRule {
  column: string;
  type: string;
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

// ── Helpers ─────────────────────────────────────────────────────────────
const splitList = (value: string): string[] =>
  value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);

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
      {status}
    </span>
  );
};

// Small repeatable-row-list field used by several sections below (business
// rules, foreign keys, data types, range checks, expected schema columns).
function RuleRows<T extends object>({
  label,
  rows,
  fields,
  onAdd,
  onChange,
  onRemove,
}: {
  label: string;
  rows: T[];
  fields: { key: keyof T; placeholder: string }[];
  onAdd: () => void;
  onChange: (index: number, key: keyof T, value: string) => void;
  onRemove: (index: number) => void;
}) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <label className="text-xs font-medium text-muted-foreground">{label}</label>
        <Button type="button" variant="outline" size="sm" onClick={onAdd}>
          <Plus className="h-3.5 w-3.5" /> Add
        </Button>
      </div>
      {rows.map((row, index) => (
        <div
          key={index}
          className="mb-2 grid grid-cols-1 gap-2"
          style={{ gridTemplateColumns: `repeat(${fields.length}, 1fr) auto` }}
        >
          {fields.map((f) => (
            <Input
              key={String(f.key)}
              placeholder={f.placeholder}
              value={(row[f.key] as string) ?? ""}
              onChange={(e) => onChange(index, f.key, e.target.value)}
            />
          ))}
          <Button type="button" variant="ghost" size="icon" onClick={() => onRemove(index)}>
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
    </div>
  );
}

export const QualityChecks = () => {
  const queryClient = useQueryClient();

  // ── form state — table-level ───────────────────────────────────────
  const [connectionId, setConnectionId] = useState<string>("");
  const [tableName, setTableName] = useState("");
  const [primaryKey, setPrimaryKey] = useState("");           // Uniqueness
  const [businessKeys, setBusinessKeys] = useState("");       // Duplicate Detection
  const [nullColumns, setNullColumns] = useState("");         // Completeness
  const [expectedMinRows, setExpectedMinRows] = useState(""); // Record Count (threshold)
  const [freshnessColumn, setFreshnessColumn] = useState("");
  const [freshnessThresholdHours, setFreshnessThresholdHours] = useState("");
  const [businessRules, setBusinessRules] = useState<BusinessRule[]>([]);          // Validity
  const [foreignKeys, setForeignKeys] = useState<ForeignKeyRule[]>([]);            // Referential Integrity
  const [dataTypes, setDataTypes] = useState<DataTypeRule[]>([]);                  // Data Type Validation
  const [rangeRules, setRangeRules] = useState<RangeRule[]>([]);                   // Range Checks
  const [outlierColumns, setOutlierColumns] = useState("");                        // Outlier Detection
  const [expectedColumns, setExpectedColumns] = useState<SchemaColumnRule[]>([]);  // Schema Validation (manual)
  const [schemaBaseline, setSchemaBaseline] = useState(false);                     // Schema Validation (drift)

  // ── form state — cross-table (Consistency) ─────────────────────────
  const [consistencyRules, setConsistencyRules] = useState<ConsistencyRule[]>([]);

  const { data: connections, isFetching: connectionsLoading } = useQuery({
    queryKey: ["quality-connections"],
    queryFn: fetchQualityConnections,
  });

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

  const resetBaselineMutation = useMutation({
    mutationFn: resetSchemaBaseline,
  });

  // ── generic add/update/remove for the repeatable-row sections ──────
  const addRow = <T,>(setter: (fn: (prev: T[]) => T[]) => void, empty: T) =>
    setter((prev) => [...prev, empty]);
  const updateRow = <T,>(
    setter: (fn: (prev: T[]) => T[]) => void,
    index: number,
    key: keyof T,
    value: string
  ) => setter((prev) => prev.map((r, i) => (i === index ? { ...r, [key]: value } : r)));
  const removeRow = <T,>(setter: (fn: (prev: T[]) => T[]) => void, index: number) =>
    setter((prev) => prev.filter((_, i) => i !== index));

  const addConsistencyRule = () =>
    setConsistencyRules((prev) => [
      ...prev,
      { table_a: "", expr_a: "", table_b: "", expr_b: "", tolerance: "0" },
    ]);
  const updateConsistencyRule = (index: number, key: keyof ConsistencyRule, value: string) =>
    setConsistencyRules((prev) => prev.map((r, i) => (i === index ? { ...r, [key]: value } : r)));
  const removeConsistencyRule = (index: number) =>
    setConsistencyRules((prev) => prev.filter((_, i) => i !== index));

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!connectionId || !tableName.trim()) return;

    const tableSpec: Record<string, unknown> = { table_name: tableName.trim() };

    const pk = splitList(primaryKey);
    if (pk.length) tableSpec.primary_key = pk;

    const bk = splitList(businessKeys);
    if (bk.length) tableSpec.business_keys = bk;

    const nulls = splitList(nullColumns);
    if (nulls.length) tableSpec.null_columns = nulls;

    if (expectedMinRows.trim()) tableSpec.expected_min_rows = Number(expectedMinRows);

    if (freshnessColumn.trim() && freshnessThresholdHours.trim()) {
      tableSpec.freshness_column = freshnessColumn.trim();
      tableSpec.freshness_threshold_hours = Number(freshnessThresholdHours);
    }

    const rules = businessRules.filter((r) => r.column.trim() && r.condition.trim());
    if (rules.length) tableSpec.business_rules = rules;

    const fks = foreignKeys.filter((f) => f.column.trim() && f.parent_table.trim() && f.parent_column.trim());
    if (fks.length) tableSpec.foreign_keys = fks;

    const types = dataTypes.filter((d) => d.column.trim() && d.type.trim());
    if (types.length) {
      tableSpec.data_types = Object.fromEntries(types.map((d) => [d.column.trim(), d.type.trim()]));
    }

    const ranges = rangeRules.filter((r) => r.column.trim() && (r.min.trim() || r.max.trim()));
    if (ranges.length) {
      tableSpec.range_checks = Object.fromEntries(
        ranges.map((r) => [
          r.column.trim(),
          {
            ...(r.min.trim() ? { min: Number(r.min) } : {}),
            ...(r.max.trim() ? { max: Number(r.max) } : {}),
          },
        ])
      );
    }

    const outliers = splitList(outlierColumns);
    if (outliers.length) tableSpec.outlier_columns = outliers;

    const expectedCols = expectedColumns.filter((c) => c.column.trim() && c.type.trim());
    if (expectedCols.length) {
      tableSpec.expected_columns = Object.fromEntries(
        expectedCols.map((c) => [c.column.trim(), c.type.trim()])
      );
    }

    if (schemaBaseline) tableSpec.schema_baseline = true;

    const consistency_checks = consistencyRules
      .filter((c) => c.table_a.trim() && c.expr_a.trim() && c.table_b.trim() && c.expr_b.trim())
      .map((c) => ({
        table_a: c.table_a.trim(),
        expr_a: c.expr_a.trim(),
        table_b: c.table_b.trim(),
        expr_b: c.expr_b.trim(),
        tolerance: c.tolerance.trim() ? Number(c.tolerance) : 0,
      }));

    runMutation.mutate({
      connection_id: Number(connectionId),
      tables: [tableSpec],
      ...(consistency_checks.length ? { consistency_checks } : {}),
    });
  };

  const results = runMutation.data?.results ?? [];

  return (
    <div className="space-y-5">
      <PageHeader
        icon={ShieldCheck}
        eyebrow="Data"
        title="Data Quality"
        description="Completeness, uniqueness, validity, freshness, referential integrity, data types, ranges, outliers, schema drift, and cross-table consistency — all in one run."
      />

      <Card>
        <CardHeader><CardTitle className="text-sm">Run checks</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Connection</label>
                <select
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                  value={connectionId}
                  onChange={(e) => setConnectionId(e.target.value)}
                  required
                >
                  <option value="" disabled>
                    {connectionsLoading ? "Loading connections…" : "Select a connection"}
                  </option>
                  {connections?.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.source_type})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Table name</label>
                <Input placeholder="customers" value={tableName} onChange={(e) => setTableName(e.target.value)} required />
              </div>
            </div>

            {/* Completeness / Uniqueness / Duplicate Detection / Record Count */}
            <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Primary key (Uniqueness)</label>
                <Input placeholder="customer_id" value={primaryKey} onChange={(e) => setPrimaryKey(e.target.value)} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Business keys (Duplicate Detection)</label>
                <Input placeholder="email" value={businessKeys} onChange={(e) => setBusinessKeys(e.target.value)} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Null-check columns (Completeness)</label>
                <Input placeholder="customer_id, email" value={nullColumns} onChange={(e) => setNullColumns(e.target.value)} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Expected min rows (Record Count)</label>
                <Input type="number" placeholder="1" value={expectedMinRows} onChange={(e) => setExpectedMinRows(e.target.value)} />
              </div>
            </div>

            {/* Freshness */}
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Freshness column (optional)</label>
                <Input placeholder="updated_at" value={freshnessColumn} onChange={(e) => setFreshnessColumn(e.target.value)} />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted-foreground">Freshness threshold, hours (optional)</label>
                <Input type="number" placeholder="24" value={freshnessThresholdHours} onChange={(e) => setFreshnessThresholdHours(e.target.value)} />
              </div>
            </div>

            {/* Validity — Business Rules */}
            <RuleRows<BusinessRule>
              label="Business rules — Validity (condition should match ZERO rows)"
              rows={businessRules}
              fields={[
                { key: "column", placeholder: "column (e.g. price)" },
                { key: "condition", placeholder: "SQL condition, e.g. price <= 0" },
              ]}
              onAdd={() => addRow(setBusinessRules, { column: "", condition: "" })}
              onChange={(i, k, v) => updateRow(setBusinessRules, i, k, v)}
              onRemove={(i) => removeRow(setBusinessRules, i)}
            />

            {/* Referential Integrity */}
            <RuleRows<ForeignKeyRule>
              label="Foreign keys — Referential Integrity"
              rows={foreignKeys}
              fields={[
                { key: "column", placeholder: "child column (e.g. customer_id)" },
                { key: "parent_table", placeholder: "parent table (e.g. customers)" },
                { key: "parent_column", placeholder: "parent column (e.g. id)" },
              ]}
              onAdd={() => addRow(setForeignKeys, { column: "", parent_table: "", parent_column: "" })}
              onChange={(i, k, v) => updateRow(setForeignKeys, i, k, v)}
              onRemove={(i) => removeRow(setForeignKeys, i)}
            />

            {/* Data Type Validation */}
            <RuleRows<DataTypeRule>
              label="Expected data types — Data Type Validation"
              rows={dataTypes}
              fields={[
                { key: "column", placeholder: "column (e.g. age)" },
                { key: "type", placeholder: "expected type (e.g. integer)" },
              ]}
              onAdd={() => addRow(setDataTypes, { column: "", type: "" })}
              onChange={(i, k, v) => updateRow(setDataTypes, i, k, v)}
              onRemove={(i) => removeRow(setDataTypes, i)}
            />

            {/* Range Checks */}
            <RuleRows<RangeRule>
              label="Range checks (leave min or max blank to skip that bound)"
              rows={rangeRules}
              fields={[
                { key: "column", placeholder: "column (e.g. age)" },
                { key: "min", placeholder: "min (e.g. 0)" },
                { key: "max", placeholder: "max (e.g. 120)" },
              ]}
              onAdd={() => addRow(setRangeRules, { column: "", min: "", max: "" })}
              onChange={(i, k, v) => updateRow(setRangeRules, i, k, v)}
              onRemove={(i) => removeRow(setRangeRules, i)}
            />

            {/* Outlier Detection */}
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Outlier detection columns (IQR method, comma-separated)
              </label>
              <Input placeholder="order_amount, transaction_count" value={outlierColumns} onChange={(e) => setOutlierColumns(e.target.value)} />
            </div>

            {/* Schema Validation */}
            <div className="space-y-2 rounded-md border border-border p-3">
              <label className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
                <input type="checkbox" checked={schemaBaseline} onChange={(e) => setSchemaBaseline(e.target.checked)} />
                Schema Validation — capture/compare a baseline snapshot for this table
              </label>
              {schemaBaseline && tableName.trim() && connectionId && (
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
              <RuleRows<SchemaColumnRule>
                label="Or validate against a manually specified expected schema instead"
                rows={expectedColumns}
                fields={[
                  { key: "column", placeholder: "column (e.g. email)" },
                  { key: "type", placeholder: "expected type (e.g. varchar)" },
                ]}
                onAdd={() => addRow(setExpectedColumns, { column: "", type: "" })}
                onChange={(i, k, v) => updateRow(setExpectedColumns, i, k, v)}
                onRemove={(i) => removeRow(setExpectedColumns, i)}
              />
            </div>

            {/* Consistency — cross-table, same connection */}
            <div className="space-y-2 rounded-md border border-border p-3">
              <label className="text-xs font-medium text-muted-foreground">
                Consistency checks — compare an aggregate between two tables in this connection
              </label>
              {consistencyRules.map((rule, index) => (
                <div key={index} className="grid grid-cols-1 gap-2 md:grid-cols-[1fr_1fr_1fr_1fr_80px_auto]">
                  <Input placeholder="table A (e.g. orders)" value={rule.table_a} onChange={(e) => updateConsistencyRule(index, "table_a", e.target.value)} />
                  <Input placeholder="expr A (e.g. SUM(amount))" value={rule.expr_a} onChange={(e) => updateConsistencyRule(index, "expr_a", e.target.value)} />
                  <Input placeholder="table B (e.g. order_summary)" value={rule.table_b} onChange={(e) => updateConsistencyRule(index, "table_b", e.target.value)} />
                  <Input placeholder="expr B (e.g. SUM(total))" value={rule.expr_b} onChange={(e) => updateConsistencyRule(index, "expr_b", e.target.value)} />
                  <Input type="number" placeholder="tolerance" value={rule.tolerance} onChange={(e) => updateConsistencyRule(index, "tolerance", e.target.value)} />
                  <Button type="button" variant="ghost" size="icon" onClick={() => removeConsistencyRule(index)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm" onClick={addConsistencyRule}>
                <Plus className="h-3.5 w-3.5" /> Add consistency check
              </Button>
            </div>

            <Button type="submit" disabled={runMutation.isPending}>
              {runMutation.isPending ? "Running checks…" : "Run checks"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {runMutation.isError && (
        <Card className="border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950">
          <CardContent className="p-4 text-sm text-rose-700 dark:text-rose-400">
            {(runMutation.error as any)?.response?.data?.detail
              ? JSON.stringify((runMutation.error as any).response.data.detail)
              : (runMutation.error as Error).message}
          </CardContent>
        </Card>
      )}

      {runMutation.isSuccess && (
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">
              Results — <StatusBadge status={runMutation.data.status} /> ({runMutation.data.passed}/{runMutation.data.total_checks} passed)
            </CardTitle>
          </CardHeader>
          <CardContent>
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
                    <tr key={i} className="border-t border-border">
                      <td className="px-3 py-2 text-xs text-muted-foreground">{r.table_name}</td>
                      <td className="px-3 py-2 font-mono text-xs text-foreground">{r.check_name}</td>
                      <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
                      <td className="px-3 py-2 text-foreground">{r.failed_rows ?? "—"}</td>
                      <td className="px-3 py-2 text-muted-foreground">{r.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
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
