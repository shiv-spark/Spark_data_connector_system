import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpFromLine, History, Loader2, Play, Plus, Save, Settings2, Trash2, X } from "lucide-react";
import { api, fetchReverseEtlHistory, restoreReverseEtlVersion } from "@/lib/api";
import { HistoryPanel } from "@/components/console/HistoryPanel";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel, PanelBar, Row, Meta, EmptyState, RowSkeleton } from "@/components/console/Panel";
import { StatusBadge } from "@/components/StatusBadge";
import { PageHeader } from "@/components/PageHeader";
import { SchedulerFields } from "@/components/SchedulerFields";
import { buildCron, defaultSchedule, scheduleFromCron, ScheduleState } from "@/lib/schedule";

type Pipeline = {
  pipeline_name: string;
  source_table: string | null;
  source_query: string | null;
  destination_type: string;
  destination_object: string;
  connection_id: number | null;
  write_mode: string;
  upsert_key: string | null;
  sync_mode: string;
  incremental_column: string | null;
  schedule: string;
  timezone: string;
  status: string;
  updated_at: string;
};

type Connection = { id: number; name: string; source_type: string };

const DESTINATION_TYPES = [
  { value: "postgres", label: "Postgres" },
  { value: "mysql", label: "MySQL" },
  { value: "snowflake", label: "Snowflake" },
  { value: "oracle", label: "Oracle" },
  { value: "mongodb", label: "MongoDB" },
  { value: "salesforce", label: "Salesforce" },
  { value: "hubspot", label: "HubSpot" },
  { value: "zoho", label: "Zoho CRM" },
  { value: "s3", label: "Amazon S3" },
  { value: "google_sheets", label: "Google Sheets" },
  { value: "webhook", label: "Webhook / Generic API" },
];

const emptyForm = {
  pipeline_name: "",
  source_table: "",
  destination_type: "postgres",
  connection_id: "" as string | number,
  destination_object: "",
  upsert_key: "",
  write_mode: "upsert",
  sync_mode: "full",
  incremental_column: "",
  field_mapping: {},
};

type EditForm = {
  source_table: string;
  destination_type: string;
  connection_id: string | number;
  destination_object: string;
  upsert_key: string;
  write_mode: string;
  sync_mode: string;
  incremental_column: string;
  schedule: ScheduleState;
};

const buildEditForm = (p: Pipeline): EditForm => ({
  source_table: p.source_table ?? "",
  destination_type: p.destination_type,
  connection_id: p.connection_id ?? "",
  destination_object: p.destination_object,
  upsert_key: p.upsert_key ?? "",
  write_mode: p.write_mode,
  sync_mode: p.sync_mode,
  incremental_column: p.incremental_column ?? "",
  schedule: scheduleFromCron(p.schedule, p.timezone),
});

export function ReverseETL() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [schedule, setSchedule] = useState<ScheduleState>(defaultSchedule);
  const [historyPipeline, setHistoryPipeline] = useState<string | null>(null);
  const [editing, setEditing] = useState<Record<string, EditForm>>({});

  const { data: pipelines, isLoading, isError, error: listError } = useQuery({
    queryKey: ["reverse-etl-pipelines"],
    queryFn: async () => (await api.get("/reverse_etl/pipelines")).data?.pipelines as Pipeline[],
  });

  const { data: tables } = useQuery({
    queryKey: ["tables"],
    queryFn: async () => (await api.get("/tables")).data?.tables as string[] | undefined,
  });

  const { data: connections } = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data?.connections as Connection[] | undefined,
  });

  const relevantConnections = useMemo(
    () => (connections ?? []).filter((c) => c.source_type === form.destination_type),
    [connections, form.destination_type],
  );

  const createMutation = useMutation({
    mutationFn: async () =>
      api.post("/reverse_etl/pipelines", {
        pipeline_name: form.pipeline_name,
        source_table: form.source_table,
        destination_type: form.destination_type,
        connection_id: form.connection_id ? Number(form.connection_id) : null,
        destination_object: form.destination_object,
        field_mapping: form.field_mapping,
        upsert_key: form.upsert_key || null,
        write_mode: form.write_mode,
        sync_mode: form.sync_mode,
        incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
        schedule: buildCron(schedule),
        timezone: schedule.timezone,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reverse-etl-pipelines"] });
      setShowForm(false);
      setForm(emptyForm);
    },
  });

  const runMutation = useMutation({
    mutationFn: async (name: string) => api.post(`/reverse_etl/pipelines/${name}/run`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reverse-etl-pipelines"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: async (name: string) => api.delete(`/reverse_etl/pipelines/${name}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reverse-etl-pipelines"] }),
  });

  const updateEdit = (name: string, patch: Partial<EditForm>) =>
    setEditing((current) => ({ ...current, [name]: { ...current[name], ...patch } }));

  const editMutation = useMutation({
    mutationFn: async ({ name, state }: { name: string; state: EditForm }) =>
      api.put(`/reverse_etl/pipelines/${name}`, {
        pipeline_name: name,
        source_table: state.source_table || null,
        destination_type: state.destination_type,
        connection_id: state.connection_id ? Number(state.connection_id) : null,
        destination_object: state.destination_object,
        field_mapping: {},
        upsert_key: state.write_mode === "upsert" ? (state.upsert_key || null) : null,
        write_mode: state.write_mode,
        sync_mode: state.sync_mode,
        incremental_column: state.sync_mode === "incremental" ? (state.incremental_column || null) : null,
        schedule: buildCron(state.schedule),
        timezone: state.schedule.timezone,
      }),
    onSuccess: (_, variables) => {
      setEditing((current) => {
        const next = { ...current };
        delete next[variables.name];
        return next;
      });
      qc.invalidateQueries({ queryKey: ["reverse-etl-pipelines"] });
    },
  });

  return (
    <div className="flex h-full">
    <main className="min-w-0 flex-1">
      <PageHeader
        icon={ArrowUpFromLine}
        eyebrow="Sync data out"
        title="Reverse ETL"
        description="Push warehouse tables back out to Salesforce, HubSpot, Postgres, MySQL, Google Sheets, or any webhook — on a schedule."
        actions={
          <Button onClick={() => setShowForm((s) => !s)}>
            {showForm ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
            {showForm ? "Cancel" : "New Sync"}
          </Button>
        }
      />

      {showForm && (
        <Panel className="mb-6">
          <PanelBar title="New reverse ETL pipeline" />
          <div className="grid grid-cols-1 gap-4 p-4 md:grid-cols-2">
            <label className="space-y-1 text-sm font-medium text-foreground">
              Pipeline name
              <Input value={form.pipeline_name} onChange={(e) => setForm({ ...form, pipeline_name: e.target.value })} placeholder="sync_customers_to_salesforce" />
            </label>

            <label className="space-y-1 text-sm font-medium text-foreground">
              Source table (from your warehouse)
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.source_table}
                onChange={(e) => setForm({ ...form, source_table: e.target.value })}
              >
                <option value="">Select a table…</option>
                {(tables ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>

            <label className="space-y-1 text-sm font-medium text-foreground">
              Destination
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.destination_type}
                onChange={(e) => setForm({ ...form, destination_type: e.target.value, connection_id: "" })}
              >
                {DESTINATION_TYPES.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
              </select>
            </label>

            <label className="space-y-1 text-sm font-medium text-foreground">
              Destination connection
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.connection_id}
                onChange={(e) => setForm({ ...form, connection_id: e.target.value })}
              >
                <option value="">Select a saved connection…</option>
                {relevantConnections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>

            <label className="space-y-1 text-sm font-medium text-foreground">
              Destination object
              <Input
                value={form.destination_object}
                onChange={(e) => setForm({ ...form, destination_object: e.target.value })}
                placeholder={
                  form.destination_type === "salesforce" ? "Contact" :
                  form.destination_type === "hubspot" ? "contacts" :
                  form.destination_type === "zoho" ? "Leads" :
                  form.destination_type === "mongodb" ? "collection_name" :
                  form.destination_type === "s3" ? "exports/customers.csv" :
                  form.destination_type === "webhook" ? "https://example.com/webhook" :
                  "table_name"
                }
              />
            </label>

            <label className="space-y-1 text-sm font-medium text-foreground">
              Write mode
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.write_mode}
                onChange={(e) => setForm({ ...form, write_mode: e.target.value })}
              >
                <option value="upsert">Upsert</option>
                <option value="insert">Insert only</option>
                <option value="update">Update / overwrite</option>
              </select>
            </label>

            {form.write_mode === "upsert" && (
              <label className="space-y-1 text-sm font-medium text-foreground">
                Upsert key (destination field)
                <Input value={form.upsert_key} onChange={(e) => setForm({ ...form, upsert_key: e.target.value })} placeholder="email" />
              </label>
            )}

            <label className="space-y-1 text-sm font-medium text-foreground">
              Sync mode
              <select
                className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                value={form.sync_mode}
                onChange={(e) => setForm({ ...form, sync_mode: e.target.value })}
              >
                <option value="full">Full sync (every run)</option>
                <option value="incremental">Incremental (only new/changed rows)</option>
              </select>
            </label>

            {form.sync_mode === "incremental" && (
              <label className="space-y-1 text-sm font-medium text-foreground">
                Incremental column (on source table)
                <Input value={form.incremental_column} onChange={(e) => setForm({ ...form, incremental_column: e.target.value })} placeholder="updated_at" />
              </label>
            )}
          </div>

          <div className="border-t border-border p-4">
            <SchedulerFields value={schedule} onChange={setSchedule} compact />
          </div>

          <div className="flex justify-end gap-2 border-t border-border p-4">
            <Button variant="outline" onClick={() => setShowForm(false)}>Cancel</Button>
            <Button
              disabled={!form.pipeline_name || !form.source_table || !form.destination_object || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Create pipeline
            </Button>
          </div>
          {createMutation.isError && (
            <p className="px-4 pb-4 text-sm text-destructive">
              {(createMutation.error as any)?.response?.data?.detail?.toString?.() ?? "Failed to create pipeline"}
            </p>
          )}
        </Panel>
      )}

      <Panel>
        <PanelBar title="Reverse ETL pipelines" count={pipelines?.length} />
        {isLoading ? (
          <RowSkeleton />
        ) : isError ? (
          <p className="p-4 text-sm text-destructive">
            Failed to load pipelines — {(listError as any)?.response?.data?.detail?.toString?.() ?? (listError as any)?.message ?? "check backend"}.
          </p>
        ) : !pipelines?.length ? (
          <EmptyState
            icon={ArrowUpFromLine}
            title="No reverse ETL pipelines yet"
            body="Create one to start pushing a warehouse table out to Salesforce, HubSpot, another database, or a webhook."
            action={<Button onClick={() => setShowForm(true)}><Plus className="h-4 w-4" /> New Sync</Button>}
          />
        ) : (
          pipelines.map((p) => {
            const editState = editing[p.pipeline_name];
            const editConnections = editState
              ? (connections ?? []).filter((c) => c.source_type === editState.destination_type)
              : [];
            return (
            <Row key={p.pipeline_name} state={p.status}>
              <div className="space-y-3">
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0 flex-1 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <span className="text-[14px] font-semibold text-foreground">{p.pipeline_name}</span>
                    <StatusBadge status={p.status} />
                  </div>
                  <Meta
                    items={[
                      ["source", p.source_table ?? "custom query"],
                      ["→", `${p.destination_type}:${p.destination_object}`],
                      ["mode", p.write_mode],
                      ["sync", p.sync_mode],
                      ["schedule", p.schedule],
                    ]}
                  />
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Button size="sm" variant="outline" onClick={() => runMutation.mutate(p.pipeline_name)} disabled={runMutation.isPending}>
                    <Play className="h-3.5 w-3.5" /> Run now
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    aria-label={`Edit ${p.pipeline_name}`}
                    onClick={() => setEditing((current) => ({ ...current, [p.pipeline_name]: buildEditForm(p) }))}
                  >
                    <Settings2 className="h-3.5 w-3.5" /> Edit
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    aria-label={`Version history for ${p.pipeline_name}`}
                    onClick={() => setHistoryPipeline(p.pipeline_name)}
                  >
                    <History className="h-3.5 w-3.5" /> History
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => deleteMutation.mutate(p.pipeline_name)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              {editState && (
                <div className="space-y-4 rounded-lg bg-muted/40 p-4 ring-1 ring-inset ring-border">
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <label className="space-y-1 text-sm font-medium text-foreground">
                      Source table (from your warehouse)
                      <select
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={editState.source_table}
                        onChange={(e) => updateEdit(p.pipeline_name, { source_table: e.target.value })}
                      >
                        <option value="">Select a table…</option>
                        {(tables ?? []).map((t) => <option key={t} value={t}>{t}</option>)}
                      </select>
                    </label>

                    <label className="space-y-1 text-sm font-medium text-foreground">
                      Destination
                      <select
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={editState.destination_type}
                        onChange={(e) => updateEdit(p.pipeline_name, { destination_type: e.target.value, connection_id: "" })}
                      >
                        {DESTINATION_TYPES.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                      </select>
                    </label>

                    <label className="space-y-1 text-sm font-medium text-foreground">
                      Destination connection
                      <select
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={editState.connection_id}
                        onChange={(e) => updateEdit(p.pipeline_name, { connection_id: e.target.value })}
                      >
                        <option value="">Select a saved connection…</option>
                        {editConnections.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </label>

                    <label className="space-y-1 text-sm font-medium text-foreground">
                      Destination object
                      <Input
                        value={editState.destination_object}
                        onChange={(e) => updateEdit(p.pipeline_name, { destination_object: e.target.value })}
                        placeholder={
                          editState.destination_type === "salesforce" ? "Contact" :
                          editState.destination_type === "hubspot" ? "contacts" :
                          editState.destination_type === "zoho" ? "Leads" :
                          editState.destination_type === "mongodb" ? "collection_name" :
                          editState.destination_type === "s3" ? "exports/customers.csv" :
                          editState.destination_type === "webhook" ? "https://example.com/webhook" :
                          "table_name"
                        }
                      />
                    </label>

                    <label className="space-y-1 text-sm font-medium text-foreground">
                      Write mode
                      <select
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={editState.write_mode}
                        onChange={(e) => updateEdit(p.pipeline_name, { write_mode: e.target.value })}
                      >
                        <option value="upsert">Upsert</option>
                        <option value="insert">Insert only</option>
                        <option value="update">Update / overwrite</option>
                      </select>
                    </label>

                    {editState.write_mode === "upsert" && (
                      <label className="space-y-1 text-sm font-medium text-foreground">
                        Upsert key (destination field)
                        <Input value={editState.upsert_key} onChange={(e) => updateEdit(p.pipeline_name, { upsert_key: e.target.value })} placeholder="email" />
                      </label>
                    )}

                    <label className="space-y-1 text-sm font-medium text-foreground">
                      Sync mode
                      <select
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={editState.sync_mode}
                        onChange={(e) => updateEdit(p.pipeline_name, { sync_mode: e.target.value })}
                      >
                        <option value="full">Full sync (every run)</option>
                        <option value="incremental">Incremental (only new/changed rows)</option>
                      </select>
                    </label>

                    {editState.sync_mode === "incremental" && (
                      <label className="space-y-1 text-sm font-medium text-foreground">
                        Incremental column (on source table)
                        <Input value={editState.incremental_column} onChange={(e) => updateEdit(p.pipeline_name, { incremental_column: e.target.value })} placeholder="updated_at" />
                      </label>
                    )}
                  </div>

                  <div>
                    <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Schedule</p>
                    <SchedulerFields
                      compact
                      value={editState.schedule}
                      onChange={(next) => updateEdit(p.pipeline_name, { schedule: next })}
                    />
                  </div>

                  <div className="flex justify-end gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setEditing((current) => {
                        const next = { ...current };
                        delete next[p.pipeline_name];
                        return next;
                      })}
                    >
                      <X className="h-4 w-4" /> Cancel
                    </Button>
                    <Button
                      type="button"
                      disabled={editMutation.isPending}
                      onClick={() => editMutation.mutate({ name: p.pipeline_name, state: editState })}
                    >
                      <Save className="h-4 w-4" /> Save Changes
                    </Button>
                  </div>
                  {editMutation.isError && (
                    <p className="text-sm text-destructive">
                      {(editMutation.error as any)?.response?.data?.detail?.toString?.() ?? "Failed to save changes"}
                    </p>
                  )}
                </div>
              )}
              </div>
            </Row>
            );
          })
        )}
      </Panel>
    </main>

    {historyPipeline && (
      <HistoryPanel
        queryKey={["reverse-etl-history", historyPipeline]}
        fetchHistory={() => fetchReverseEtlHistory(historyPipeline)}
        restoreVersion={(versionId) => restoreReverseEtlVersion(historyPipeline, versionId)}
        onClose={() => setHistoryPipeline(null)}
        onRestored={() => qc.invalidateQueries({ queryKey: ["reverse-etl-pipelines"] })}
      />
    )}
    </div>
  );
}
