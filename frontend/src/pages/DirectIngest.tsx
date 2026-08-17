import { FormEvent, useState, useEffect, useMemo } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { DownloadCloud, Loader2, ShieldCheck, Link2, Link2Off } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FolderUpload } from "@/pages/FolderUpload";
import { PageHeader } from "@/components/PageHeader";
import { DataQualityBuilder, BuiltQuality } from "@/components/DataQualityBuilder";

type Connector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "s3" | "snowflake";

const connectorLabels: Record<Connector, string> = {
  csv: "CSV",
  excel: "Excel",
  google_sheets: "Google Sheets",
  api: "API",
  postgres: "Postgres",
  s3: "S3",
  snowflake: "Snowflake",
};

// Maps a connector to the `source_type` saved connections are stored under —
// same mapping CreatePipeline uses to filter the "Use Saved Connection" list.
const CONNECTOR_TO_SOURCE_TYPE: Record<Connector, string> = {
  csv: "local_folder",
  excel: "local_folder",
  google_sheets: "google_sheet",
  api: "api",
  postgres: "postgres",
  s3: "s3",
  snowflake: "snowflake",
};

const initial = {
  connector: "csv" as Connector,
  table_name: "",
  option: "1",
  sync_mode: "full",
  incremental_column: "",
  file_path: "",
  sheet_url: "",
  url: "",
  api_config: "",
  host: "",
  database: "",
  user: "",
  password: "",
  port: "5432",
  query: "",
  bucket: "",
  key: "",
  file_type: "csv",
  s3_access_key: "",
  s3_secret_key: "",
  sf_account: "",
  sf_user: "",
  sf_password: "",
  sf_warehouse: "",
  sf_database: "",
  sf_schema: "PUBLIC",
  sf_role: "",
  sf_query: "",
};

export const DirectIngest = () => {
  const [form, setForm] = useState(initial);
  const [quality, setQuality] = useState<BuiltQuality | null>(null);
  const [result, setResult] = useState<any>(null);
  const [apiConfigError, setApiConfigError] = useState<string>("");

  // ── Saved connection support — same UX as CreatePipeline ──────────────
  const [useExistingConnection, setUseExistingConnection] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [connectionError, setConnectionError] = useState<string>("");
  // The folder a saved csv/excel connection resolves to, purely so we can
  // list the files inside it — never submitted to the backend directly.
  const [existingConnFolderPath, setExistingConnFolderPath] = useState<string>("");

  const update = (key: keyof typeof initial, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const filteredConnections = connections.data?.filter(
    (conn: any) => conn.source_type === CONNECTOR_TO_SOURCE_TYPE[form.connector]
  ) ?? [];

  // Saved-connection dropdown values are display-only (passwords/secrets
  // come back masked as "********") — the real credentials are resolved
  // server-side via connection_id at ingest/preview time. Here we only
  // pull the non-secret bits needed to drive the UI (e.g. which folder to
  // browse for csv/excel).
  const populateFromConnection = (connId: string) => {
    if (!connId) {
      setExistingConnFolderPath("");
      return;
    }
    const conn = filteredConnections.find((c: any) => String(c.id) === connId);
    if (conn?.config && ["csv", "excel"].includes(form.connector)) {
      setExistingConnFolderPath(conn.config.base_path || "");
    } else {
      setExistingConnFolderPath("");
    }
  };

  useEffect(() => {
    setUseExistingConnection(false);
    setSelectedConnectionId("");
    setConnectionError("");
    setExistingConnFolderPath("");
  }, [form.connector]);

  // A different saved connection means a different folder — the
  // previously-picked file no longer applies. Note: this only resets the
  // FILE pick, not the folder itself — populateFromConnection already sets
  // the new folder in the same event. (Bug fixed here: this effect used to
  // also clear the folder, and since it runs right after
  // populateFromConnection's setExistingConnFolderPath in the same render
  // cycle, it was wiping out the folder immediately — so the saved-connection
  // file picker for csv/excel, and therefore its preview, never appeared.)
  useEffect(() => {
    update("file_path", "");
  }, [selectedConnectionId]);

  // ── Files inside a saved csv/excel connection's folder — pick one to
  // ingest and to preview/build quality checks against. ────────────────
  const savedFolderFiles = useQuery({
    queryKey: ["saved-connection-files", existingConnFolderPath],
    enabled: useExistingConnection && ["csv", "excel"].includes(form.connector) && !!existingConnFolderPath,
    queryFn: async () => (await api.get("/list_folder_files", {
      params: { folder_path: existingConnFolderPath },
    })).data as { folder_path: string; files: string[] },
  });

  // ── What to preview / build quality checks against, for whichever
  // connector + connection mode is currently selected. `null` means we
  // don't have enough info yet, so DataQualityBuilder renders nothing. ──
  const previewParams = useMemo<Record<string, unknown> | null>(() => {
    const connId = useExistingConnection && selectedConnectionId ? parseInt(selectedConnectionId, 10) : undefined;

    if (["csv", "excel"].includes(form.connector)) {
      return form.file_path ? { file_path: form.file_path } : null;
    }

    if (form.connector === "postgres") {
      if (!form.query.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, pg_query: form.query } : null;
      if (!form.host || !form.database || !form.user) return null;
      return {
        src_pg_host: form.host, src_pg_db: form.database, src_pg_user: form.user,
        src_pg_password: form.password, src_pg_port: form.port, pg_query: form.query,
      };
    }

    if (form.connector === "snowflake") {
      if (!form.sf_query.trim()) return null;
      if (useExistingConnection) return connId ? { connection_id: connId, sf_query: form.sf_query } : null;
      if (!form.sf_account || !form.sf_user || !form.sf_warehouse || !form.sf_database) return null;
      return {
        sf_account: form.sf_account, sf_user: form.sf_user, sf_password: form.sf_password,
        sf_warehouse: form.sf_warehouse, sf_database: form.sf_database, sf_schema: form.sf_schema,
        sf_role: form.sf_role, sf_query: form.sf_query,
      };
    }

    if (form.connector === "s3") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      if (!form.bucket || !form.key) return null;
      return {
        s3_bucket: form.bucket, s3_key: form.key, s3_file_type: form.file_type,
        s3_access_key: form.s3_access_key, s3_secret_key: form.s3_secret_key,
      };
    }

    if (form.connector === "google_sheets") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      return form.sheet_url.trim() ? { sheet_url: form.sheet_url } : null;
    }

    if (form.connector === "api") {
      if (useExistingConnection) return connId ? { connection_id: connId } : null;
      if (!form.url.trim()) return null;
      if (!form.api_config.trim()) return { api_url: form.url };
      try {
        return { api_url: form.url, api_config: JSON.parse(form.api_config) };
      } catch {
        return null;
      }
    }

    return null;
  }, [
    form.connector, form.file_path,
    useExistingConnection, selectedConnectionId,
    form.query, form.host, form.database, form.user, form.password, form.port,
    form.sf_query, form.sf_account, form.sf_user, form.sf_password, form.sf_warehouse, form.sf_database, form.sf_schema, form.sf_role,
    form.bucket, form.key, form.file_type, form.s3_access_key, form.s3_secret_key,
    form.sheet_url, form.url, form.api_config,
  ]);

  const ingest = useMutation({
    mutationFn: async () => {
      if (useExistingConnection && !selectedConnectionId) {
        setConnectionError("Please select a saved connection");
        throw new Error("No connection selected");
      }
      if (useExistingConnection && ["csv", "excel"].includes(form.connector) && !form.file_path) {
        setConnectionError("Please pick a file from the connection's folder");
        throw new Error("No file selected");
      }

      const connectionId = useExistingConnection ? parseInt(selectedConnectionId, 10) : null;

      // Quality checks now work for every connector, not just csv/excel —
      // the friendly builder just needs a preview of the data first,
      // which /preview_source provides for any source type.
      const dfQualityFields = quality?.hasAnyCheck
        ? { df_quality_config: quality.config, df_quality_on_fail: quality.on_fail }
        : {};

      const common = {
        option: form.option,
        table_name: form.table_name,
        sync_mode: form.sync_mode,
        incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
        connection_id: connectionId,
        ...dfQualityFields,
      };

      let parsedApiConfig: Record<string, unknown> = {};
      if (form.connector === "api" && !useExistingConnection && form.api_config.trim()) {
        try {
          parsedApiConfig = JSON.parse(form.api_config);
        } catch (e) {
          setApiConfigError("Invalid JSON — please check the syntax.");
          throw new Error("Invalid api_config JSON");
        }
      }

      const payloads = {
        csv: { ...common, file_path: form.file_path },
        excel: { ...common, file_path: form.file_path },
        google_sheets: { ...common, sheet_url: form.sheet_url },
        api: { ...common, url: form.url, ...parsedApiConfig },
        postgres: { ...common, host: form.host, database: form.database, user: form.user, password: form.password, port: form.port, query: form.query },
        s3: {
          ...common,
          bucket: form.bucket,
          key: form.key,
          file_type: form.file_type,
          access_key: form.s3_access_key || null,
          secret_key: form.s3_secret_key || null,
        },
        snowflake: {
          ...common,
          account: form.sf_account,
          user: form.sf_user,
          password: form.sf_password,
          warehouse: form.sf_warehouse,
          database: form.sf_database,
          schema: form.sf_schema,
          role: form.sf_role || null,
          query: form.sf_query,
        },
      };
      const endpoints = {
        csv: "/ingest_csv",
        excel: "/ingest_excel",
        google_sheets: "/ingest_google_sheet",
        api: "/ingest_api",
        postgres: "/ingest_postgres",
        s3: "/ingest_s3",
        snowflake: "/ingest_snowflake",
      };
      const response = await api.post(endpoints[form.connector], payloads[form.connector]);
      return response.data;
    },
    onSuccess: setResult,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setConnectionError("");
    setApiConfigError("");
    setResult(null);
    ingest.mutate();
  };

  return (
    <div className="space-y-5">
      <PageHeader
        icon={DownloadCloud}
        eyebrow="Data"
        title="Direct Ingest"
        description="Load a file or endpoint straight into a table without building a pipeline."
      />
      <Card className="bg-card border-border">
        <CardHeader><CardTitle className="text-sm text-foreground">Run One-Time Ingestion</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <label className="space-y-1 text-sm font-medium text-foreground">
                Connector
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground dark:bg-background dark:text-foreground" value={form.connector} onChange={(e) => update("connector", e.target.value as Connector)}>
                  {Object.entries(connectorLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium text-foreground">Target table<Input value={form.table_name} onChange={(e) => update("table_name", e.target.value)} required /></label>
              <label className="space-y-1 text-sm font-medium text-foreground">
                Load option
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground dark:bg-background dark:text-foreground" value={form.option} onChange={(e) => update("option", e.target.value)}>
                  <option value="1">Append</option>
                  <option value="2">Overwrite</option>
                  <option value="3">Create new</option>
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium text-foreground">
                Sync mode
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground dark:bg-background dark:text-foreground" value={form.sync_mode} onChange={(e) => update("sync_mode", e.target.value)}>
                  <option value="full">Full</option>
                  <option value="incremental">Incremental</option>
                </select>
              </label>
            </div>

            {form.sync_mode === "incremental" && (
              <label className="block max-w-md space-y-1 text-sm font-medium text-foreground">Incremental column<Input value={form.incremental_column} onChange={(e) => update("incremental_column", e.target.value)} /></label>
            )}

            {/* ── New Connection / Use Saved Connection toggle — same UX as CreatePipeline ── */}
            <div className="rounded-md border border-border bg-card p-4 dark:border-border dark:bg-card">
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <input
                    type="radio"
                    name="directConnectionMode"
                    checked={!useExistingConnection}
                    onChange={() => {
                      setUseExistingConnection(false);
                      setSelectedConnectionId("");
                      setConnectionError("");
                      setExistingConnFolderPath("");
                    }}
                  />
                  <Link2Off className="h-4 w-4" />
                  New Connection
                </label>
                <label className="flex items-center gap-2 text-sm font-medium text-foreground">
                  <input
                    type="radio"
                    name="directConnectionMode"
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
                    <p className="text-sm text-red-500 dark:text-red-400">No saved connections for this connector type. Please create a new connection.</p>
                  ) : (
                    <select
                      className="select-control"
                      value={selectedConnectionId}
                      onChange={(e) => {
                        setSelectedConnectionId(e.target.value);
                        setConnectionError("");
                        populateFromConnection(e.target.value);
                      }}
                    >
                      <option value="">Select a connection</option>
                      {filteredConnections.map((conn: any) => (
                        <option key={conn.id} value={conn.id}>{conn.name}</option>
                      ))}
                    </select>
                  )}
                  {connectionError && <p className="mt-2 text-sm text-red-500 dark:text-red-400">{connectionError}</p>}

                  {/* ── Saved csv/excel connection → pick the exact file to ingest ── */}
                  {["csv", "excel"].includes(form.connector) && selectedConnectionId && existingConnFolderPath && (
                    <div className="mt-3 rounded-md border border-border bg-muted/50 p-3">
                      <p className="mb-2 text-xs font-medium text-muted-foreground">
                        Pick a file from this connection's folder to ingest and to preview & build quality checks.
                      </p>
                      {savedFolderFiles.isLoading ? (
                        <p className="text-sm text-muted-foreground">Loading files…</p>
                      ) : savedFolderFiles.isError ? (
                        <p className="text-sm text-rose-600 dark:text-rose-400">
                          {(savedFolderFiles.error as any)?.response?.data?.detail ?? "Couldn't list files in this folder."}
                        </p>
                      ) : (savedFolderFiles.data?.files.length ?? 0) === 0 ? (
                        <p className="text-sm text-muted-foreground">No files found in this connection's folder.</p>
                      ) : (
                        <select
                          className="select-control"
                          value={form.file_path}
                          onChange={(e) => update("file_path", e.target.value)}
                        >
                          <option value="">Select a file</option>
                          {savedFolderFiles.data!.files.map((fname) => (
                            <option key={fname} value={`${existingConnFolderPath}/${fname}`}>{fname}</option>
                          ))}
                        </select>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>

            {!useExistingConnection && (
              <>
                {["csv", "excel"].includes(form.connector) && (
                  <div className="space-y-3">
                    <label className="block space-y-1 text-sm font-medium text-foreground">
                      File path
                      <Input value={form.file_path} onChange={(e) => update("file_path", e.target.value)} placeholder="Type a path OR pick a folder below and upload" />
                    </label>
                    <FolderUpload
                      connectorType={form.connector as "csv" | "excel"}
                      onFolderResolved={() => {}}
                      onFileResolved={(filePath) => update("file_path", filePath)}
                    />
                  </div>
                )}
                {form.connector === "google_sheets" && (
                  <label className="block space-y-1 text-sm font-medium text-foreground">Sheet URL<Input value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} required /></label>
                )}
                {form.connector === "api" && (
                  <div className="space-y-2">
                    <label className="block space-y-1 text-sm font-medium text-foreground">API URL<Input value={form.url} onChange={(e) => update("url", e.target.value)} required /></label>
                    <label className="space-y-1 text-sm font-medium block text-foreground">
                      Advanced Config (optional JSON — method, auth_type, body, pagination, etc.)
                      <textarea
                        className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs text-foreground dark:bg-background dark:text-foreground"
                        placeholder='{"method": "POST", "auth_type": "bearer", "bearer_token": "...", "pagination_type": "page"}'
                        value={form.api_config}
                        onChange={(e) => {
                          update("api_config", e.target.value);
                          setApiConfigError("");
                        }}
                      />
                    </label>
                    {apiConfigError && <p className="text-sm text-red-500 dark:text-red-400">{apiConfigError}</p>}
                  </div>
                )}
                {form.connector === "postgres" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Input placeholder="Host" value={form.host} onChange={(e) => update("host", e.target.value)} required />
                    <Input placeholder="Database" value={form.database} onChange={(e) => update("database", e.target.value)} required />
                    <Input placeholder="User" value={form.user} onChange={(e) => update("user", e.target.value)} required />
                    <Input placeholder="Password" type="password" value={form.password} onChange={(e) => update("password", e.target.value)} required />
                    <Input placeholder="Port" value={form.port} onChange={(e) => update("port", e.target.value)} />
                  </div>
                )}
                {form.connector === "s3" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                    <Input placeholder="Bucket" value={form.bucket} onChange={(e) => update("bucket", e.target.value)} required />
                    <Input placeholder="Key" value={form.key} onChange={(e) => update("key", e.target.value)} required />
                    <Input placeholder="File type" value={form.file_type} onChange={(e) => update("file_type", e.target.value)} />
                    <Input placeholder="Access key ID" value={form.s3_access_key} onChange={(e) => update("s3_access_key", e.target.value)} />
                    <Input placeholder="Secret access key" type="password" value={form.s3_secret_key} onChange={(e) => update("s3_secret_key", e.target.value)} />
                  </div>
                )}
                {form.connector === "snowflake" && (
                  <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                    <Input placeholder="Account (e.g. XROJPNQ-RO43084)" value={form.sf_account} onChange={(e) => update("sf_account", e.target.value)} required />
                    <Input placeholder="User" value={form.sf_user} onChange={(e) => update("sf_user", e.target.value)} required />
                    <Input placeholder="Password" type="password" value={form.sf_password} onChange={(e) => update("sf_password", e.target.value)} required />
                    <Input placeholder="Warehouse" value={form.sf_warehouse} onChange={(e) => update("sf_warehouse", e.target.value)} required />
                    <Input placeholder="Database" value={form.sf_database} onChange={(e) => update("sf_database", e.target.value)} required />
                    <Input placeholder="Schema (default PUBLIC)" value={form.sf_schema} onChange={(e) => update("sf_schema", e.target.value)} />
                    <Input placeholder="Role (optional)" value={form.sf_role} onChange={(e) => update("sf_role", e.target.value)} />
                  </div>
                )}
              </>
            )}

            {/* ── Query fields — always shown regardless of new vs saved connection,
                 same as CreatePipeline's Postgres/Snowflake table/query toggle area. ── */}
            {form.connector === "postgres" && (
              <textarea className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:bg-background dark:text-foreground" placeholder="SQL query" value={form.query} onChange={(e) => update("query", e.target.value)} required />
            )}
            {form.connector === "snowflake" && (
              <textarea className="min-h-24 w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground dark:bg-background dark:text-foreground" placeholder="SQL query" value={form.sf_query} onChange={(e) => update("sf_query", e.target.value)} required />
            )}

            {/* ── Friendly data preview + quality checks — works for every
                 connector, and for both a brand-new and a saved connection,
                 via /preview_source. ── */}
            <DataQualityBuilder
              connector={form.connector}
              params={previewParams}
              auto={["csv", "excel"].includes(form.connector)}
              onChange={setQuality}
            />

            <Button type="submit" disabled={ingest.isPending}>
              {ingest.isPending ? <Loader2 className="animate-spin" /> : <DownloadCloud />} Run Ingest
            </Button>
          </form>
        </CardContent>
      </Card>

      {(result || ingest.error) && (
        <Card className={ingest.error ? "border-rose-200 bg-rose-50 dark:border-rose-800 dark:bg-rose-950" : "border-emerald-200 bg-emerald-50 dark:border-emerald-800 dark:bg-emerald-950"}>
          <CardContent className="p-4 space-y-3">
            {result?.df_quality && (
              <div className="flex items-center gap-2 text-sm font-medium">
                <ShieldCheck className="h-4 w-4" />
                Data quality: {result.df_quality.status} ({result.df_quality.passed}/{result.df_quality.total_checks} checks passed)
              </div>
            )}
            <pre className="max-h-80 overflow-auto text-xs text-foreground">{JSON.stringify(result ?? (ingest.error as any)?.response?.data ?? (ingest.error as Error).message, null, 2)}</pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
