import { FormEvent, useState, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, PlusCircle, Link2, Link2Off } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SchedulerFields } from "@/components/SchedulerFields";
import { buildCron, defaultSchedule } from "@/lib/schedule";
import { FolderUpload } from "@/pages/FolderUpload";

type Connector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "s3" | "snowflake";

const CONNECTOR_TO_SOURCE_TYPE: Record<Connector, string> = {
  csv: "local_folder",
  excel: "local_folder",
  google_sheets: "google_sheet",
  api: "api",
  postgres: "postgres",
  s3: "s3",
  snowflake: "snowflake",
};

const SUPPORTS_CONNECTIONS: Connector[] = ["csv", "excel", "google_sheets", "api", "postgres", "s3", "snowflake"];

const base = {
  pipeline_name: "",
  connector_type: "csv" as Connector,
  table_name: "",
  option: "1",
  after_first_run: "",
  sync_mode: "full",
  incremental_column: "",
  folder_path: "",
  file_path: "",
  sheet_url: "",
  api_url: "",
  api_config: "",
  src_pg_host: "",
  src_pg_db: "",
  src_pg_user: "",
  src_pg_password: "",
  src_pg_port: "5432",
  pg_query: "",
  s3_bucket: "",
  s3_key: "",
  s3_file_type: "csv",
  // ── Snowflake fields ──────────────────
  sf_account: "",
  sf_user: "",
  sf_password: "",
  sf_warehouse: "",
  sf_database: "",
  sf_schema: "PUBLIC",
  sf_role: "",
  sf_query: "",
};

export const CreatePipeline = () => {
  const qc = useQueryClient();
  const [form, setForm] = useState(base);
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [result, setResult] = useState<any>(null);
  const [apiConfigError, setApiConfigError] = useState<string>("");
  const [useExistingConnection, setUseExistingConnection] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [connectionError, setConnectionError] = useState<string>("");
  const update = (key: keyof typeof base, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const filteredConnections = connections.data?.filter(
    (conn: any) => conn.source_type === CONNECTOR_TO_SOURCE_TYPE[form.connector_type as Connector]
  ) ?? [];

  const populateFromConnection = (connId: string) => {
    if (!connId) return;
    const conn = filteredConnections.find((c: any) => String(c.id) === connId);
    if (conn?.config) {
      const cfg = conn.config;
      if (form.connector_type === "postgres") {
        update("src_pg_host", cfg.host || "");
        update("src_pg_db", cfg.database || "");
        update("src_pg_user", cfg.user || "");
        update("src_pg_password", cfg.password || "");
        update("src_pg_port", cfg.port || "5432");
      } else if (form.connector_type === "s3") {
        update("s3_bucket", cfg.bucket || "");
        update("s3_key", cfg.prefix || "");
        update("s3_file_type", cfg.file_type || "csv");
      } else if (form.connector_type === "snowflake") {
        update("sf_account", cfg.account || "");
        update("sf_user", cfg.user || "");
        update("sf_password", cfg.password || "");
        update("sf_warehouse", cfg.warehouse || "");
        update("sf_database", cfg.database || "");
        update("sf_schema", cfg.schema || "PUBLIC");
        update("sf_role", cfg.role || "");
      } else if (form.connector_type === "api") {
        update("api_url", cfg.base_url || "");
      } else if (form.connector_type === "google_sheets") {
        update("sheet_url", cfg.sheet_url || "");
      } else if (form.connector_type === "csv" || form.connector_type === "excel") {
        update("folder_path", cfg.base_path || "");
        update("s3_file_type", cfg.file_type || "csv");
      }
    }
  };

  useEffect(() => {
    setSelectedConnectionId("");
    setUseExistingConnection(false);
    setConnectionError("");
  }, [form.connector_type]);

  const create = useMutation({
    mutationFn: async () => {
      if (useExistingConnection && !selectedConnectionId) {
        setConnectionError("Please select a saved connection");
        throw new Error("No connection selected");
      }

      let parsedApiConfig: Record<string, unknown> | null = null;
      if (form.connector_type === "api" && form.api_config.trim()) {
        try {
          parsedApiConfig = JSON.parse(form.api_config);
        } catch (e) {
          setApiConfigError("Invalid JSON — please check the syntax.");
          throw new Error("Invalid api_config JSON");
        }
      }

      const payload = {
        ...form,
        api_config: parsedApiConfig,
        schedule: buildCron(schedule),
        timezone: schedule.timezone,
        incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
        after_first_run: form.option === "3" ? form.after_first_run || null : null,
        connection_id: useExistingConnection ? parseInt(selectedConnectionId) : null,
      };
      const response = await api.post("/create_pipeline", payload);
      return response.data;
    },
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setConnectionError("");
    setApiConfigError("");
    setResult(null);
    create.mutate();
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><PlusCircle className="h-5 w-5" /> Create Pipeline</h2>
      <Card>
        <CardHeader><CardTitle className="text-sm">Pipeline Configuration</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <label className="space-y-1 text-sm font-medium">Pipeline name<Input value={form.pipeline_name} onChange={(e) => update("pipeline_name", e.target.value)} required /></label>
              <label className="space-y-1 text-sm font-medium">
                Connector
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.connector_type} onChange={(e) => update("connector_type", e.target.value as Connector)}>
                  <option value="csv">CSV</option>
                  <option value="excel">Excel</option>
                  <option value="google_sheets">Google Sheets</option>
                  <option value="api">API</option>
                  <option value="postgres">Postgres</option>
                  <option value="s3">S3</option>
                  <option value="snowflake">Snowflake</option>
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium">Target table<Input value={form.table_name} onChange={(e) => update("table_name", e.target.value)} required /></label>
              <label className="space-y-1 text-sm font-medium">
                Load option
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.option} onChange={(e) => update("option", e.target.value)}>
                  <option value="1">Append</option>
                  <option value="2">Overwrite</option>
                  <option value="3">Create new</option>
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium">
                Sync mode
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.sync_mode} onChange={(e) => update("sync_mode", e.target.value)}>
                  <option value="full">Full</option>
                  <option value="incremental">Incremental</option>
                </select>
              </label>
            </div>

            <SchedulerFields value={schedule} onChange={setSchedule} />

            {SUPPORTS_CONNECTIONS.includes(form.connector_type) && (
              <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input
                      type="radio"
                      name="connectionMode"
                      checked={!useExistingConnection}
                      onChange={() => {
                        setUseExistingConnection(false);
                        setSelectedConnectionId("");
                        setConnectionError("");
                      }}
                    />
                    <Link2Off className="h-4 w-4" />
                    New Connection
                  </label>
                  <label className="flex items-center gap-2 text-sm font-medium">
                    <input
                      type="radio"
                      name="connectionMode"
                      checked={useExistingConnection}
                      onChange={() => setUseExistingConnection(true)}
                    />
                    <Link2 className="h-4 w-4" />
                    Use Saved Connection
                  </label>
                </div>
                {useExistingConnection && (
                  <div className="mt-3">
                    {connections.isLoading ? (
                      <p className="text-sm text-muted-foreground">Loading connections...</p>
                    ) : filteredConnections.length === 0 ? (
                      <p className="text-sm text-red-500">No saved connections for this connector type. Please create a new connection.</p>
                    ) : (
                      <select
                        className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                        value={selectedConnectionId}
                        onChange={(e) => {
                          setSelectedConnectionId(e.target.value);
                          setConnectionError("");
                          populateFromConnection(e.target.value);
                        }}
                      >
                        <option value="">Select a connection</option>
                        {filteredConnections.map((conn: any) => (
                          <option key={conn.id} value={conn.id}>
                            {conn.name}
                          </option>
                        ))}
                      </select>
                    )}
                    {connectionError && <p className="mt-2 text-sm text-red-500">{connectionError}</p>}
                  </div>
                )}
              </div>
            )}

            {form.option === "3" && (
              <label className="block max-w-md space-y-1 text-sm font-medium">After first run<Input placeholder="1 append, 2 overwrite" value={form.after_first_run} onChange={(e) => update("after_first_run", e.target.value)} /></label>
            )}
            {form.sync_mode === "incremental" && (
              <label className="block max-w-md space-y-1 text-sm font-medium">Incremental column<Input value={form.incremental_column} onChange={(e) => update("incremental_column", e.target.value)} /></label>
            )}

            {["csv", "excel"].includes(form.connector_type) && (
              <div className="space-y-3">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Input placeholder="File path (optional — single file)" value={form.file_path} onChange={(e) => update("file_path", e.target.value)} />
                  <Input placeholder="Folder path (auto-filled by upload below, or type manually)" value={form.folder_path} onChange={(e) => update("folder_path", e.target.value)} />
                </div>
                <FolderUpload
                  connectorType={form.connector_type as "csv" | "excel"}
                  onFolderResolved={(folderPath) => {
                    update("folder_path", folderPath);
                    update("file_path", "");   // "use whole folder" ka matlab single file_path clear ho
                  }}
                  onFileResolved={(filePath) => {
                    update("file_path", filePath);
                    update("folder_path", "");   // single file select/upload ka matlab folder_path clear ho
                  }}
                />
              </div>
            )}
            {form.connector_type === "google_sheets" && <Input placeholder="Sheet URL" value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} />}
            {form.connector_type === "api" && (
              <div className="space-y-2">
                <Input placeholder="API URL" value={form.api_url} onChange={(e) => update("api_url", e.target.value)} />
                <label className="space-y-1 text-sm font-medium block">
                  Advanced Config (optional JSON — method, auth_type, body, pagination, etc.)
                  <textarea
                    className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                    placeholder={`{\n  "method": "POST",\n  "auth_type": "api_key_header",\n  "header_name": "x-Gateway-APIKey",\n  "api_key": "xxxxx",\n  "body": { "getpoEncumbranceInfo": { "pUserName": "dm_gsb_usr" } },\n  "pagination_type": "body_bounds",\n  "body_pagination_path": "getpoEncumbranceInfo",\n  "lower_bound_field": "lowerBound",\n  "higher_bound_field": "higherBound",\n  "initial_lower_bound": 0,\n  "step_size": 1000\n}`}
                    value={form.api_config}
                    onChange={(e) => {
                      update("api_config", e.target.value);
                      setApiConfigError("");
                    }}
                  />
                </label>
                {apiConfigError && <p className="text-sm text-red-500">{apiConfigError}</p>}
              </div>
            )}
            {form.connector_type === "postgres" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input placeholder="Host" value={form.src_pg_host} onChange={(e) => update("src_pg_host", e.target.value)} />
                <Input placeholder="Database" value={form.src_pg_db} onChange={(e) => update("src_pg_db", e.target.value)} />
                <Input placeholder="User" value={form.src_pg_user} onChange={(e) => update("src_pg_user", e.target.value)} />
                <Input placeholder="Password" type="password" value={form.src_pg_password} onChange={(e) => update("src_pg_password", e.target.value)} />
                <Input placeholder="Port" value={form.src_pg_port} onChange={(e) => update("src_pg_port", e.target.value)} />
                <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.pg_query} onChange={(e) => update("pg_query", e.target.value)} />
              </div>
            )}
            {form.connector_type === "s3" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <Input placeholder="Bucket" value={form.s3_bucket} onChange={(e) => update("s3_bucket", e.target.value)} />
                <Input placeholder="Key" value={form.s3_key} onChange={(e) => update("s3_key", e.target.value)} />
                <Input placeholder="File type" value={form.s3_file_type} onChange={(e) => update("s3_file_type", e.target.value)} />
              </div>
            )}
            {form.connector_type === "snowflake" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input placeholder="Account (e.g. XROJPNQ-RO43084)" value={form.sf_account} onChange={(e) => update("sf_account", e.target.value)} />
                <Input placeholder="User" value={form.sf_user} onChange={(e) => update("sf_user", e.target.value)} />
                <Input placeholder="Password" type="password" value={form.sf_password} onChange={(e) => update("sf_password", e.target.value)} />
                <Input placeholder="Warehouse" value={form.sf_warehouse} onChange={(e) => update("sf_warehouse", e.target.value)} />
                <Input placeholder="Database" value={form.sf_database} onChange={(e) => update("sf_database", e.target.value)} />
                <Input placeholder="Schema (default PUBLIC)" value={form.sf_schema} onChange={(e) => update("sf_schema", e.target.value)} />
                <Input placeholder="Role (optional)" value={form.sf_role} onChange={(e) => update("sf_role", e.target.value)} />
                <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.sf_query} onChange={(e) => update("sf_query", e.target.value)} />
              </div>
            )}

            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? <Loader2 className="animate-spin" /> : <PlusCircle />} Create Pipeline
            </Button>
          </form>
        </CardContent>
      </Card>

      {(result || create.error) && (
        <Card className={create.error ? "border-rose-200 bg-rose-50" : "border-emerald-200 bg-emerald-50"}>
          <CardContent className="p-4">
            <pre className="max-h-80 overflow-auto text-xs">{JSON.stringify(result ?? (create.error as any)?.response?.data ?? (create.error as Error).message, null, 2)}</pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
};