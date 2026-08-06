import { useMemo, useState } from "react";
import { useQuery, useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import { ListChecks, Pause, Play, Plus, Save, Trash2, RefreshCw, Search, X, Settings2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Link } from "react-router-dom";
import { Panel, PanelBar, PanelSearch, Row, Meta, EmptyState, RowSkeleton } from "@/components/console/Panel";
import { StatusBadge } from "@/components/StatusBadge";
import { fdt } from "@/lib/format";
import { SchedulerFields } from "@/components/SchedulerFields";
import { buildCron, scheduleFromCron, ScheduleState } from "@/lib/schedule";
import { PageHeader } from "@/components/PageHeader";
import { StatTile } from "@/components/StatTile";

type Pipeline = {
  dag_id: string;
  size_kb?: number;
  schedule?: string;
  timezone?: string;
  connector_type?: string;
  table_name?: string;
  option?: string;
  after_first_run?: string | null;
  sync_mode?: string;
  incremental_column?: string | null;
  folder_path?: string | null;
  file_path?: string | null;
  sheet_url?: string | null;
  api_url?: string | null;
  src_pg_host?: string | null;
  src_pg_db?: string | null;
  src_pg_user?: string | null;
  src_pg_port?: string | null;
  pg_query?: string | null;
  s3_bucket?: string | null;
  s3_key?: string | null;
  s3_file_type?: string | null;
  sf_account?: string | null;
  sf_user?: string | null;
  sf_warehouse?: string | null;
  sf_database?: string | null;
  sf_schema?: string | null;
  sf_role?: string | null;
  sf_query?: string | null;
  has_src_pg_password?: boolean;
  has_sf_password?: boolean;
};

type EditState = {
  schedule: ScheduleState;
  table_name: string;
  option: string;
  after_first_run: string;
  sync_mode: string;
  incremental_column: string;
  folder_path: string;
  file_path: string;
  sheet_url: string;
  api_url: string;
  src_pg_host: string;
  src_pg_db: string;
  src_pg_user: string;
  src_pg_password: string;
  src_pg_port: string;
  pg_query: string;
  s3_bucket: string;
  s3_key: string;
  s3_file_type: string;
  sf_account: string;
  sf_user: string;
  sf_password: string;
  sf_warehouse: string;
  sf_database: string;
  sf_schema: string;
  sf_role: string;
  sf_query: string;
};

const fetchPipelines = async (): Promise<Pipeline[]> => {
  const r = await api.get("/pipelines");
  return r.data?.pipelines ?? [];
};

const fetchStatus = async (name: string) => {
  const r = await api.get(`/pipeline/${name}/status`);
  return r.data;
};

const buildEditState = (pipeline: Pipeline): EditState => ({
  schedule: scheduleFromCron(pipeline.schedule ?? "*/5 * * * *", pipeline.timezone ?? "Asia/Kolkata"),
  table_name: pipeline.table_name ?? "",
  option: pipeline.option ?? "1",
  after_first_run: pipeline.after_first_run ?? "",
  sync_mode: pipeline.sync_mode ?? "full",
  incremental_column: pipeline.incremental_column ?? "",
  folder_path: pipeline.folder_path ?? "",
  file_path: pipeline.file_path ?? "",
  sheet_url: pipeline.sheet_url ?? "",
  api_url: pipeline.api_url ?? "",
  src_pg_host: pipeline.src_pg_host ?? "",
  src_pg_db: pipeline.src_pg_db ?? "",
  src_pg_user: pipeline.src_pg_user ?? "",
  src_pg_password: "",
  src_pg_port: pipeline.src_pg_port ?? "5432",
  pg_query: pipeline.pg_query ?? "",
  s3_bucket: pipeline.s3_bucket ?? "",
  s3_key: pipeline.s3_key ?? "",
  s3_file_type: pipeline.s3_file_type ?? "csv",
  sf_account: pipeline.sf_account ?? "",
  sf_user: pipeline.sf_user ?? "",
  sf_password: "",
  sf_warehouse: pipeline.sf_warehouse ?? "",
  sf_database: pipeline.sf_database ?? "",
  sf_schema: pipeline.sf_schema ?? "PUBLIC",
  sf_role: pipeline.sf_role ?? "",
  sf_query: pipeline.sf_query ?? "",
});

export const Pipelines = () => {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Record<string, EditState>>({});

  const { data: pipes = [], isLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: fetchPipelines,
  });

  const statusQueries = useQueries({
    queries: pipes.map((pipeline) => ({
      queryKey: ["pipeline-status", pipeline.dag_id],
      queryFn: () => fetchStatus(pipeline.dag_id.replace(/^pipeline_/, "")),
      staleTime: 15_000,
    })),
  });

  const rows = useMemo(
    () =>
      pipes.map((pipeline, index) => {
        const name = pipeline.dag_id.replace(/^pipeline_/, "");
        const statusData = statusQueries[index]?.data;
        return {
          ...pipeline,
          name,
          status: statusData?.status ?? "UNKNOWN",
          next_run: statusData?.next_run ?? null,
          size_kb: pipeline.size_kb,
          schedule: pipeline.schedule ?? "*/5 * * * *",
          timezone: pipeline.timezone ?? "Asia/Kolkata",
        };
      }),
    [pipes, statusQueries],
  );

  const filtered = rows.filter((row) =>
    !search ? true : row.dag_id.toLowerCase().includes(search.toLowerCase()),
  );

  const pauseM = useMutation({
    mutationFn: (name: string) => api.patch(`/pipeline/${name}/pause`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline-status"] }),
  });
  const resumeM = useMutation({
    mutationFn: (name: string) => api.patch(`/pipeline/${name}/unpause`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline-status"] }),
  });
  const deleteM = useMutation({
    mutationFn: (name: string) => api.delete(`/delete_pipeline/${name}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["pipeline-status"] });
    },
  });

  const editM = useMutation({
    mutationFn: ({ name, state }: { name: string; state: EditState }) => {
      // Build payload — only send non-empty string fields, so untouched
      // password fields (left blank) never overwrite the stored secret.
      const payload: Record<string, any> = {
        schedule: buildCron(state.schedule),
        timezone: state.schedule.timezone,
        table_name: state.table_name || null,
        option: state.option,
        after_first_run: state.option === "3" ? (state.after_first_run || null) : null,
        sync_mode: state.sync_mode,
        incremental_column: state.sync_mode === "incremental" ? (state.incremental_column || null) : null,
        folder_path: state.folder_path || null,
        file_path: state.file_path || null,
        sheet_url: state.sheet_url || null,
        api_url: state.api_url || null,
        src_pg_host: state.src_pg_host || null,
        src_pg_db: state.src_pg_db || null,
        src_pg_user: state.src_pg_user || null,
        src_pg_port: state.src_pg_port || null,
        pg_query: state.pg_query || null,
        s3_bucket: state.s3_bucket || null,
        s3_key: state.s3_key || null,
        s3_file_type: state.s3_file_type || null,
        sf_account: state.sf_account || null,
        sf_user: state.sf_user || null,
        sf_warehouse: state.sf_warehouse || null,
        sf_database: state.sf_database || null,
        sf_schema: state.sf_schema || null,
        sf_role: state.sf_role || null,
        sf_query: state.sf_query || null,
      };
      // Only include passwords if the user actually typed something new
      if (state.src_pg_password) payload.src_pg_password = state.src_pg_password;
      if (state.sf_password) payload.sf_password = state.sf_password;

      return api.patch(`/edit_pipeline/${name}`, payload);
    },
    onSuccess: (_, variables) => {
      setEditing((current) => {
        const next = { ...current };
        delete next[variables.name];
        return next;
      });
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["pipeline-status"] });
    },
  });

  const counts = {
    total: rows.length,
    active: rows.filter((row) => row.status === "ACTIVE").length,
    paused: rows.filter((row) => row.status === "PAUSED").length,
  };

  const updateEdit = (name: string, patch: Partial<EditState>) =>
    setEditing((current) => ({ ...current, [name]: { ...current[name], ...patch } }));

  return (
    <div className="space-y-5">
      <PageHeader
        icon={ListChecks}
        eyebrow="Build"
        title="Pipelines"
        description="Every scheduled job in this workspace, with the result of its last run."
      />

      <div className="grid grid-cols-3 gap-3">
        <StatTile label="Total pipelines" value={counts.total} icon={ListChecks} />
        <StatTile label="Active" value={counts.active} tone="positive" icon={Play} />
        <StatTile label="Paused" value={counts.paused} tone="warning" icon={Pause} />
      </div>

      <Panel>
        <PanelBar title="Pipelines" count={filtered.length}>
          <PanelSearch
            label="Search pipelines"
            value={search}
            onChange={setSearch}
            placeholder="Search by name…"
          />
          <Button
            variant="outline"
            size="sm"
            onClick={() => qc.invalidateQueries({ queryKey: ["pipelines"] })}
          >
            <RefreshCw /> Refresh
          </Button>
        </PanelBar>

        {isLoading ? (
          <RowSkeleton rows={4} />
        ) : pipes.length === 0 ? (
          <EmptyState
            icon={ListChecks}
            title="No pipelines yet"
            body="A pipeline pulls from a source on a schedule and loads the result into a table. Build your first one to see it here."
            action={
              <Link to="/app/create">
                <Button size="sm"><Plus /> Create pipeline</Button>
              </Link>
            }
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No matches"
            body={`Nothing matches "${search}". Clear the search to see all ${pipes.length} pipelines.`}
            action={<Button variant="outline" size="sm" onClick={() => setSearch("")}>Clear search</Button>}
          />
        ) : (
          <div>
            {filtered.map((row) => {
              const state = editing[row.name];
              const connectorType = row.connector_type ?? "";

              return (
                <Row key={row.dag_id} state={row.status}>
                  <div className="space-y-3">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className="truncate text-[13.5px] font-semibold text-foreground"
                            style={{ fontFamily: "var(--font-mono)" }}
                          >
                            {row.dag_id}
                          </span>
                          <StatusBadge status={row.status} />
                          {connectorType && <span className="chip">{connectorType}</span>}
                        </div>

                        <div className="mt-2">
                          <Meta
                            items={[
                              ["schedule", `${row.schedule} · ${row.timezone}`],
                              ["next run", fdt(row.next_run)],
                              ...(row.table_name
                                ? ([["table", row.table_name]] as [string, React.ReactNode][])
                                : []),
                              ["size", row.size_kb ? `${row.size_kb} KB` : "—"],
                            ]}
                          />
                        </div>
                      </div>

                      <div className="flex shrink-0 gap-1.5">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => setEditing((current) => ({
                            ...current,
                            [row.name]: buildEditState(row),
                          }))}
                        >
                          <Settings2 /> Edit
                        </Button>
                        {row.status === "ACTIVE" ? (
                          <Button variant="outline" size="sm" onClick={() => pauseM.mutate(row.name)}>
                            <Pause /> Pause
                          </Button>
                        ) : (
                          <Button variant="outline" size="sm" onClick={() => resumeM.mutate(row.name)}>
                            <Play /> Resume
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          aria-label={`Delete ${row.name}`}
                          className="hover:border-destructive hover:bg-red-50 hover:text-destructive dark:hover:bg-red-950/30"
                          onClick={() => {
                            if (confirm(`Delete pipeline "${row.name}"? This cannot be undone.`)) {
                              deleteM.mutate(row.name);
                            }
                          }}
                        >
                          <Trash2 />
                        </Button>
                      </div>
                    </div>

                    {state && (
                      <div className="space-y-4 rounded-lg bg-muted/40 p-4 ring-1 ring-inset ring-border">
                        <div>
                          <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Schedule</p>
                          <SchedulerFields
                            compact
                            value={state.schedule}
                            onChange={(next) => updateEdit(row.name, { schedule: next })}
                          />
                        </div>

                        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                          <label className="space-y-1 text-sm font-medium text-foreground">
                            Table name
                            <Input value={state.table_name} onChange={(e) => updateEdit(row.name, { table_name: e.target.value })} />
                          </label>
                          <label className="space-y-1 text-sm font-medium text-foreground">
                            Load option
                            <select
                              className="select-control"
                              value={state.option}
                              onChange={(e) => updateEdit(row.name, { option: e.target.value })}
                            >
                              <option value="1">Append</option>
                              <option value="2">Overwrite</option>
                              <option value="3">Create new</option>
                            </select>
                          </label>
                          <label className="space-y-1 text-sm font-medium text-foreground">
                            Sync mode
                            <select
                              className="select-control"
                              value={state.sync_mode}
                              onChange={(e) => updateEdit(row.name, { sync_mode: e.target.value })}
                            >
                              <option value="full">Full</option>
                              <option value="incremental">Incremental</option>
                            </select>
                          </label>
                        </div>

                        {state.option === "3" && (
                          <label className="block max-w-md space-y-1 text-sm font-medium text-foreground">
                            After first run
                            <Input
                              placeholder="1 append, 2 overwrite"
                              value={state.after_first_run}
                              onChange={(e) => updateEdit(row.name, { after_first_run: e.target.value })}
                            />
                          </label>
                        )}
                        {state.sync_mode === "incremental" && (
                          <label className="block max-w-md space-y-1 text-sm font-medium text-foreground">
                            Incremental column
                            <Input
                              value={state.incremental_column}
                              onChange={(e) => updateEdit(row.name, { incremental_column: e.target.value })}
                            />
                          </label>
                        )}

                        {(connectorType === "csv" || connectorType === "excel") && (
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <Input
                              placeholder="File path"
                              value={state.file_path}
                              onChange={(e) => updateEdit(row.name, { file_path: e.target.value })}
                            />
                            <Input
                              placeholder="Folder path"
                              value={state.folder_path}
                              onChange={(e) => updateEdit(row.name, { folder_path: e.target.value })}
                            />
                          </div>
                        )}

                        {connectorType === "google_sheets" && (
                          <Input
                            placeholder="Sheet URL"
                            value={state.sheet_url}
                            onChange={(e) => updateEdit(row.name, { sheet_url: e.target.value })}
                          />
                        )}

                        {connectorType === "api" && (
                          <Input
                            placeholder="API URL"
                            value={state.api_url}
                            onChange={(e) => updateEdit(row.name, { api_url: e.target.value })}
                          />
                        )}

                        {connectorType === "postgres" && (
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <Input placeholder="Host" value={state.src_pg_host} onChange={(e) => updateEdit(row.name, { src_pg_host: e.target.value })} />
                            <Input placeholder="Database" value={state.src_pg_db} onChange={(e) => updateEdit(row.name, { src_pg_db: e.target.value })} />
                            <Input placeholder="User" value={state.src_pg_user} onChange={(e) => updateEdit(row.name, { src_pg_user: e.target.value })} />
                            <Input
                              placeholder={row.has_src_pg_password ? "Password (leave blank to keep current)" : "Password"}
                              type="password"
                              value={state.src_pg_password}
                              onChange={(e) => updateEdit(row.name, { src_pg_password: e.target.value })}
                            />
                            <Input placeholder="Port" value={state.src_pg_port} onChange={(e) => updateEdit(row.name, { src_pg_port: e.target.value })} />
                            <textarea
                              className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground md:col-span-2"
                              placeholder="SQL query"
                              value={state.pg_query}
                              onChange={(e) => updateEdit(row.name, { pg_query: e.target.value })}
                            />
                          </div>
                        )}

                        {connectorType === "s3" && (
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                            <Input placeholder="Bucket" value={state.s3_bucket} onChange={(e) => updateEdit(row.name, { s3_bucket: e.target.value })} />
                            <Input placeholder="Key" value={state.s3_key} onChange={(e) => updateEdit(row.name, { s3_key: e.target.value })} />
                            <Input placeholder="File type" value={state.s3_file_type} onChange={(e) => updateEdit(row.name, { s3_file_type: e.target.value })} />
                          </div>
                        )}

                        {connectorType === "snowflake" && (
                          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                            <Input placeholder="Account" value={state.sf_account} onChange={(e) => updateEdit(row.name, { sf_account: e.target.value })} />
                            <Input placeholder="User" value={state.sf_user} onChange={(e) => updateEdit(row.name, { sf_user: e.target.value })} />
                            <Input
                              placeholder={row.has_sf_password ? "Password (leave blank to keep current)" : "Password"}
                              type="password"
                              value={state.sf_password}
                              onChange={(e) => updateEdit(row.name, { sf_password: e.target.value })}
                            />
                            <Input placeholder="Warehouse" value={state.sf_warehouse} onChange={(e) => updateEdit(row.name, { sf_warehouse: e.target.value })} />
                            <Input placeholder="Database" value={state.sf_database} onChange={(e) => updateEdit(row.name, { sf_database: e.target.value })} />
                            <Input placeholder="Schema" value={state.sf_schema} onChange={(e) => updateEdit(row.name, { sf_schema: e.target.value })} />
                            <Input placeholder="Role (optional)" value={state.sf_role} onChange={(e) => updateEdit(row.name, { sf_role: e.target.value })} />
                            <textarea
                              className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground md:col-span-2"
                              placeholder="SQL query"
                              value={state.sf_query}
                              onChange={(e) => updateEdit(row.name, { sf_query: e.target.value })}
                            />
                          </div>
                        )}

                        <div className="flex justify-end gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => setEditing((current) => {
                              const next = { ...current };
                              delete next[row.name];
                              return next;
                            })}
                          >
                            <X /> Cancel
                          </Button>
                          <Button
                            type="button"
                            disabled={editM.isPending}
                            onClick={() => editM.mutate({ name: row.name, state })}
                          >
                            <Save /> Save Changes
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </Row>
              );
            })}
          </div>
        )}
      </Panel>
    </div>
  );
};