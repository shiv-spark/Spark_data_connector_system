import { FormEvent, useState, useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, Figma, Loader2, Pencil, Plus, Trash2, X, LayoutGrid, List, ChevronDown, ChevronRight, Wifi, CheckCircle, XCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { fdt } from "@/lib/format";
import { FolderUpload } from "@/pages/FolderUpload";   
type SourceType = "local_folder" | "s3" | "postgres" | "snowflake" | "api" | "google_sheet" | "figma_design";

const initial = {
  name: "",
  source_type: "local_folder" as SourceType,
  base_path: "",
  bucket: "",
  prefix: "",
  file_type: "csv",
  host: "",
  database: "",
  user: "",
  password: "",
  port: "5432",
  base_url: "",
  test_endpoint: "",
  auth_type: "none",
  api_key: "",
  header_name: "Authorization",
  method: "GET",
  query_param_name: "api_key",
  bearer_prefix: "Bearer",
  api_advanced_config: "",
  sheet_url: "",
  figma_file_url: "",
  figma_access_token: "",
  figma_node_id: "",
  aws_access_key_id: "",
  aws_secret_access_key: "",
  pg_schema: "",
  account: "",
  warehouse: "",
  schema: "PUBLIC",
  sf_role: "",
};

const sourceTypeLabels: Record<string, string> = {
  local_folder: "Local / mounted folder",
  s3: "S3 bucket",
  postgres: "Postgres database",
  snowflake: "Snowflake",
  api: "API base URL",
  google_sheet: "Google Sheet",
  figma_design: "Figma design",
};

const groupConnectionsByType = (connections: any[]): [string, any[]][] => {
  const grouped: Record<string, any[]> = {};
  connections.forEach((conn) => {
    const type = conn.source_type;
    if (!grouped[type]) {
      grouped[type] = [];
    }
    grouped[type].push(conn);
  });
  return Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b));
};

export const Connections = () => {
  const qc = useQueryClient();
  const [form, setForm] = useState(initial);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<"card" | "list">("card");
  const [expandedTypes, setExpandedTypes] = useState<Set<string>>(new Set());
  const [testResult, setTestResult] = useState<{success: boolean; message: string; category: string} | null>(null);
  const [testPassed, setTestPassed] = useState(false);
  const [apiAdvancedConfigError, setApiAdvancedConfigError] = useState<string>("");
  const update = (key: keyof typeof initial, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    if (key === "source_type") {
      setTestResult(null);
      setTestPassed(false);
    }
    setTestPassed(false);
  };
  const validateApiAdvancedConfig = (): boolean => {
    if (form.source_type !== "api" || !form.api_advanced_config.trim()) {
      setApiAdvancedConfigError("");
      return true;
    }
    try {
      JSON.parse(form.api_advanced_config);
      setApiAdvancedConfigError("");
      return true;
    } catch (e) {
      setApiAdvancedConfigError("Invalid JSON — please check the syntax.");
      return false;
    }
  };

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const buildConfig = () => {
    const config: Record<string, any> = {
      base_path: form.base_path.trim(),
      bucket: form.bucket.trim(),
      prefix: form.prefix.trim(),
      file_type: form.file_type.trim(),
      host: form.host.trim(),
      database: form.database.trim(),
      user: form.user.trim(),
      password: form.password,   // don't trim passwords — spaces could be intentional
      port: form.port.trim(),
      base_url: form.base_url.trim(),
      auth_type: form.auth_type,
      api_key: form.api_key,     // don't trim keys/tokens either
      header_name: form.header_name.trim(),
      sheet_url: form.sheet_url.trim(),
      figma_file_url: form.figma_file_url.trim(),
      figma_access_token: form.figma_access_token,
      figma_node_id: form.figma_node_id.trim(),
    };

    if (form.source_type === "s3") {
      config.access_key = form.aws_access_key_id;
      config.secret_key = form.aws_secret_access_key;
    }

    if (form.source_type === "postgres" && form.pg_schema) {
      config.schema = form.pg_schema;
    }

    if (form.source_type === "snowflake") {
      config.account = form.account;
      config.warehouse = form.warehouse;
      config.schema = form.schema;
      config.role = form.sf_role;
    }

    if (form.source_type === "api") {
      // Backend's /connectors/test requires config.test_endpoint for the
      // "api" source type. Default to base_url so the common case (the
      // base URL is itself a directly-callable endpoint, as with
      // https://dummyjson.com/products/search) needs no extra typing,
      // but let the user override with a lighter-weight path if their
      // API has a dedicated health-check endpoint instead.
      config.test_endpoint = form.test_endpoint.trim();   // backend defaults to base_url
      config.method = form.method || "GET";
      config.query_param_name = form.query_param_name || "api_key";
      config.bearer_prefix = form.bearer_prefix || "Bearer";

      // Advanced JSON (body, pagination_type, extra_headers, extra_params,
      // custom_fields, etc.) is stored under its own nested key so it can
      // be cleanly round-tripped back into the textarea on edit, and so
      // the backend can spread it directly into api_config when this
      // connection is later used to create a pipeline.
      if (form.api_advanced_config.trim()) {
        try {
          config.api_advanced = JSON.parse(form.api_advanced_config);
        } catch (e) {
          // already validated via validateApiAdvancedConfig() before
          // this is called — safe to ignore here
        }
      }
    }

    return config;
  };

  const groupedConnections = useMemo(() => groupConnectionsByType(connections.data ?? []), [connections.data]);

  const toggleTypeExpanded = (type: string) => {
    setExpandedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const save = useMutation({
    mutationFn: async () => {
      const config = buildConfig();
      return (await api.post("/connections", {
        name: form.name,
        source_type: form.source_type,
        config,
      })).data;
    },
    onSuccess: () => {
      setForm(initial);
      setTestResult(null);
      setTestPassed(false);
      qc.invalidateQueries({ queryKey: ["connections"] });
    },
  });

  const editConn = useMutation({
    mutationFn: async (id: number) => {
      const config = buildConfig();
      return (await api.put(`/connections/${id}`, {
        name: form.name,
        source_type: form.source_type,
        config,
      })).data;
    },
    onSuccess: () => {
      setForm(initial);
      setEditingId(null);
      qc.invalidateQueries({ queryKey: ["connections"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/connections/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["connections"] }),
  });

  const testConnection = useMutation({
    mutationFn: async () => {
      const config = buildConfig();
      return (await api.post("/connectors/test", {
        source_type: form.source_type,
        config,
        test_write: false,
      })).data;
    },
    onSuccess: (data) => {
      if (data.success) {
        setTestPassed(true);
      } else {
        setTestPassed(false);
      }
    },
    onError: () => {
      setTestPassed(false);
    },
  });

  // GET /connections masks every secret-looking field to "********" (see
  // backend _public_connection). Never prefill an edit form with that —
  // the PUT /connections/{id} endpoint treats a blank OR "********"
  // secret field as "leave the stored value alone", so leaving these
  // blank here is both accurate (we don't have the real value in hand)
  // and safe (saving without retyping them won't clobber what's stored).
  const startEdit = (connection: any) => {
    const cfg = connection.config || {};
    setForm({
      name: connection.name,
      source_type: connection.source_type,
      base_path: cfg.base_path || "",
      bucket: cfg.bucket || "",
      prefix: cfg.prefix || "",
      file_type: cfg.file_type || "csv",
      host: cfg.host || "",
      database: cfg.database || "",
      user: cfg.user || "",
      password: "",
      port: cfg.port || "5432",
      base_url: cfg.base_url || "",
      test_endpoint: cfg.test_endpoint || "",
      auth_type: cfg.auth_type || "none",
      api_key: "",
      header_name: cfg.header_name || "Authorization",
      method: cfg.method || "GET",
      query_param_name: cfg.query_param_name || "api_key",
      bearer_prefix: cfg.bearer_prefix || "Bearer",
      api_advanced_config: cfg.api_advanced ? JSON.stringify(cfg.api_advanced, null, 2) : "",
      sheet_url: cfg.sheet_url || "",
      figma_file_url: cfg.figma_file_url || "",
      figma_access_token: "",
      figma_node_id: cfg.figma_node_id || "",
      aws_access_key_id: "",
      aws_secret_access_key: "",
      pg_schema: cfg.schema || "",
      account: cfg.account || "",
      warehouse: cfg.warehouse || "",
      schema: cfg.schema || "PUBLIC",
      sf_role: cfg.role || "",
    });
    setEditingId(connection.id);
    setTestPassed(true);
  };

  const cancelEdit = () => {
    setForm(initial);
    setEditingId(null);
    setTestResult(null);
    setTestPassed(false);
  };

  const clearTestResult = () => {
    setTestResult(null);
    setTestPassed(false);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!validateApiAdvancedConfig()) return;
    if (editingId) {
      editConn.mutate(editingId);
    } else {
      save.mutate();
    }
  };

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="h-section flex items-center gap-2"><DatabaseZap className="h-5 w-5" /> Connections</h2>
            <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
              Save source details once. After that, dashboard creation only needs a file name, object key, table name, or endpoint path.
            </p>
          </div>
          <Badge variant="success">Reusable sources</Badge>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[430px_1fr]">
        <Card>
          <CardHeader><CardTitle className="text-sm">{editingId ? "Edit Connection" : "Create Connection"}</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4">
              <Input placeholder="Connection name" value={form.name} onChange={(e) => update("name", e.target.value)} required />
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.source_type} onChange={(e) => update("source_type", e.target.value)}>
                <option value="local_folder">Local / mounted folder</option>
                <option value="s3">S3 bucket</option>
                <option value="postgres">Postgres database</option>
                <option value="snowflake">Snowflake</option>
                <option value="api">API base URL</option>
                <option value="google_sheet">Google Sheet</option>
                <option value="figma_design">Figma design</option>
              </select>

              {form.source_type === "local_folder" && (
                <div className="space-y-3">
                  <Input placeholder="Base folder path, e.g. /app/data or D:/datasets" value={form.base_path} onChange={(e) => update("base_path", e.target.value)} />
                  <FolderUpload
                    connectorType="any"
                    onFolderResolved={(folderPath) => update("base_path", folderPath)}
                    onFileResolved={(filePath) => update("base_path", filePath)}
                  />
                </div>
              )}
              {form.source_type === "s3" && (
                <div className="space-y-3">
                  <Input
                    placeholder={editingId ? "AWS Access Key ID (leave blank to keep existing)" : "AWS Access Key ID"}
                    value={form.aws_access_key_id}
                    onChange={(e) => update("aws_access_key_id", e.target.value)}
                  />
                  <Input
                    placeholder={editingId ? "AWS Secret Access Key (leave blank to keep existing)" : "AWS Secret Access Key"}
                    type="password"
                    value={form.aws_secret_access_key}
                    onChange={(e) => update("aws_secret_access_key", e.target.value)}
                  />
                  <Input placeholder="Bucket" value={form.bucket} onChange={(e) => update("bucket", e.target.value)} />
                  <Input placeholder="Prefix/folder, e.g. raw/sales" value={form.prefix} onChange={(e) => update("prefix", e.target.value)} />
                  <Input placeholder="Default file type" value={form.file_type} onChange={(e) => update("file_type", e.target.value)} />
                </div>
              )}
              {form.source_type === "postgres" && (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <Input placeholder="Host" value={form.host} onChange={(e) => update("host", e.target.value)} />
                  <Input placeholder="Database" value={form.database} onChange={(e) => update("database", e.target.value)} />
                  <Input placeholder="User" value={form.user} onChange={(e) => update("user", e.target.value)} />
                  <Input
                    placeholder={editingId ? "Password (leave blank to keep existing)" : "Password"}
                    type="password"
                    value={form.password}
                    onChange={(e) => update("password", e.target.value)}
                  />
                  <Input placeholder="Port" value={form.port} onChange={(e) => update("port", e.target.value)} />
                  <Input placeholder="Schema (optional)" value={form.pg_schema || ""} onChange={(e) => update("pg_schema", e.target.value)} />
                </div>
              )}
              {form.source_type === "snowflake" && (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Input placeholder="Account (e.g., xy12345.us-east-1)" value={form.account} onChange={(e) => update("account", e.target.value)} />
                    <Input placeholder="Warehouse" value={form.warehouse} onChange={(e) => update("warehouse", e.target.value)} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Input placeholder="Database" value={form.database} onChange={(e) => update("database", e.target.value)} />
                    <Input placeholder="Schema" value={form.schema} onChange={(e) => update("schema", e.target.value)} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <Input placeholder="User" value={form.user} onChange={(e) => update("user", e.target.value)} />
                    <Input
                      placeholder={editingId ? "Password (leave blank to keep existing)" : "Password"}
                      type="password"
                      value={form.password}
                      onChange={(e) => update("password", e.target.value)}
                    />
                  </div>
                  <Input placeholder="Role (optional)" value={form.sf_role} onChange={(e) => update("sf_role", e.target.value)} />
                </div>
              )}
              {form.source_type === "api" && (
                <div className="space-y-3">
                  <Input placeholder="Base URL, e.g. https://api.company.com" value={form.base_url} onChange={(e) => update("base_url", e.target.value)} />
                  <Input
                    placeholder="Test endpoint (defaults to Base URL if left blank)"
                    value={form.test_endpoint}
                    onChange={(e) => update("test_endpoint", e.target.value)}
                  />
                  <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.method} onChange={(e) => update("method", e.target.value)}>
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="PATCH">PATCH</option>
                    <option value="DELETE">DELETE</option>
                  </select>
                  <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.auth_type} onChange={(e) => update("auth_type", e.target.value)}>
                    <option value="none">No auth</option>
                    <option value="bearer">Bearer token</option>
                    <option value="api_key_header">API key header</option>
                    <option value="basic">Basic auth (user/password)</option>
                    <option value="api_key_query">API key in query param</option>
                  </select>

                  {form.auth_type === "bearer" && (
                    <>
                      <Input placeholder="Bearer prefix (default: Bearer)" value={form.bearer_prefix} onChange={(e) => update("bearer_prefix", e.target.value)} />
                      <Input
                        placeholder={editingId ? "Bearer token (leave blank to keep existing)" : "Bearer token"}
                        type="password"
                        value={form.api_key}
                        onChange={(e) => update("api_key", e.target.value)}
                      />
                    </>
                  )}
                  {form.auth_type === "api_key_header" && (
                    <>
                      <Input placeholder="Header name, e.g. x-api-key" value={form.header_name} onChange={(e) => update("header_name", e.target.value)} />
                      <Input
                        placeholder={editingId ? "API key (leave blank to keep existing)" : "API key"}
                        type="password"
                        value={form.api_key}
                        onChange={(e) => update("api_key", e.target.value)}
                      />
                    </>
                  )}
                  {form.auth_type === "basic" && (
                    <>
                      <Input placeholder="Basic auth username" value={form.user} onChange={(e) => update("user", e.target.value)} />
                      <Input
                        placeholder={editingId ? "Basic auth password (leave blank to keep existing)" : "Basic auth password"}
                        type="password"
                        value={form.password}
                        onChange={(e) => update("password", e.target.value)}
                      />
                    </>
                  )}
                  {form.auth_type === "api_key_query" && (
                    <>
                      <Input placeholder="Query param name, e.g. api_key" value={form.query_param_name} onChange={(e) => update("query_param_name", e.target.value)} />
                      <Input
                        placeholder={editingId ? "API key (leave blank to keep existing)" : "API key"}
                        type="password"
                        value={form.api_key}
                        onChange={(e) => update("api_key", e.target.value)}
                      />
                    </>
                  )}

                  <label className="space-y-1 text-sm font-medium block">
                    Advanced Config (optional JSON — body, pagination_type, extra_headers, extra_params, etc.)
                    <textarea
                      className="min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                      placeholder={`{\n  "body": { "getpoEncumbranceInfo": { "pUserName": "dm_gsb_usr" } },\n  "pagination_type": "body_bounds",\n  "body_pagination_path": "getpoEncumbranceInfo",\n  "lower_bound_field": "lowerBound",\n  "higher_bound_field": "higherBound",\n  "initial_lower_bound": 0,\n  "step_size": 1000\n}`}
                      value={form.api_advanced_config}
                      onChange={(e) => {
                        update("api_advanced_config", e.target.value);
                        setApiAdvancedConfigError("");
                      }}
                    />
                  </label>
                  {apiAdvancedConfigError && <p className="text-sm text-red-500">{apiAdvancedConfigError}</p>}
                </div>
              )}

              {form.source_type === "google_sheet" && (
                <Input placeholder="Reusable Google Sheet URL" value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} />
              )}
              {form.source_type === "figma_design" && (
                <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                    <Figma className="h-4 w-4 text-pink-600" />
                    Figma design reference
                  </div>
                  <Input placeholder="Figma file/design URL" value={form.figma_file_url} onChange={(e) => update("figma_file_url", e.target.value)} required />
                  <Input
                    placeholder={editingId ? "Figma access token (leave blank to keep existing)" : "Figma access token"}
                    type="password"
                    value={form.figma_access_token}
                    onChange={(e) => update("figma_access_token", e.target.value)}
                  />
                  <Input placeholder="Optional node id, e.g. 12:34" value={form.figma_node_id} onChange={(e) => update("figma_node_id", e.target.value)} />
                  <p className="text-xs leading-5 text-muted-foreground">
                    Use this later as a design blueprint while generating a data dashboard.
                  </p>
                </div>
              )}

              <Button 
                type="submit" 
                disabled={save.isPending || editConn.isPending || (!editingId && !testPassed)} 
                className="w-full"
                title={!editingId && !testPassed ? "Test connection first to save" : ""}
              >
                {editConn.isPending || save.isPending ? <Loader2 className="animate-spin" /> : editingId ? <Pencil /> : <Plus />}
                {editingId ? "Update Connection" : "Save Connection"}
              </Button>
              {!editingId && !testPassed && form.name && (
                <p className="mt-1 text-xs text-muted-foreground text-center">Test connection first to enable save</p>
              )}
              <Button
                type="button"
                variant="outline"
                disabled={testConnection.isPending || !form.name}
                onClick={async () => {
                  if (!validateApiAdvancedConfig()) return;
                  setTestResult(null);
                  const result = await testConnection.mutateAsync();
                  setTestResult(result);
                }}
                className="w-full mt-2"
              >
                {testConnection.isPending ? <Loader2 className="animate-spin" /> : <Wifi />}
                Test Connection
              </Button>
              {testResult && (
                <div className={`mt-2 flex items-center gap-2 rounded-md p-3 text-sm ${
                  testResult.success 
                    ? "bg-green-50 text-green-800 border border-green-200" 
                    : "bg-red-50 text-red-800 border border-red-200"
                }`}>
                  {testResult.success ? (
                    <CheckCircle className="h-4 w-4 shrink-0" />
                  ) : (
                    <XCircle className="h-4 w-4 shrink-0" />
                  )}
                  <span>{testResult.message}</span>
                </div>
              )}
              {editingId && (
                <Button type="button" variant="outline" onClick={cancelEdit} className="w-full mt-2">
                  <X /> Cancel
                </Button>
              )}
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm">Saved Connections</CardTitle>
              <div className="flex items-center gap-1 rounded-md border border-slate-200 bg-slate-50 p-0.5">
                <Button
                  variant={viewMode === "card" ? "default" : "ghost"}
                  size="sm"
                  className="h-7 px-2"
                  onClick={() => setViewMode("card")}
                >
                  <LayoutGrid className="h-4 w-4" />
                </Button>
                <Button
                  variant={viewMode === "list" ? "default" : "ghost"}
                  size="sm"
                  className="h-7 px-2"
                  onClick={() => setViewMode("list")}
                >
                  <List className="h-4 w-4" />
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {connections.isLoading ? <p className="text-sm text-muted-foreground">Loading connections...</p> : viewMode === "card" ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {(connections.data ?? []).map((connection: any) => (
                  <div key={connection.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-950">{connection.name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{connection.source_type} / {fdt(connection.updated_at)}</p>
                      </div>
                      
                    </div>
                    <pre className="mt-3 max-h-28 overflow-auto rounded-md bg-slate-50 p-3 text-xs text-slate-600">{JSON.stringify(connection.config, null, 2)}</pre>
                    <div className="mt-3 flex gap-2">
                      <Button variant="outline" onClick={() => startEdit(connection)}>
                        <Pencil /> Edit
                      </Button>
                      <Button variant="outline" className="hover:border-destructive hover:bg-red-50 hover:text-destructive" onClick={() => remove.mutate(connection.id)}>
                        <Trash2 /> Delete
                      </Button>
                    </div>
                  </div>
                ))}
                {(connections.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">No connections saved yet.</p>}
              </div>
            ) : (
              <div className="space-y-2">
                {groupedConnections.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No connections saved yet.</p>
                ) : (
                  groupedConnections.map(([type, conns]: [string, any[]]) => (
                    <div key={type} className="rounded-lg border border-slate-200 bg-white">
                      <button
                        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-slate-50"
                        onClick={() => toggleTypeExpanded(type)}
                      >
                        <div className="flex items-center gap-2">
                          {expandedTypes.has(type) ? (
                            <ChevronDown className="h-4 w-4 text-slate-500" />
                          ) : (
                            <ChevronRight className="h-4 w-4 text-slate-500" />
                          )}
                          <span className="font-medium text-slate-950">{sourceTypeLabels[type] || type}</span>
                          <Badge variant="outline" className="ml-1">{conns.length}</Badge>
                        </div>
                      </button>
                      {expandedTypes.has(type) && (
                        <div className="border-t border-slate-200 bg-slate-50 px-4 pb-3">
                          {conns.map((connection: any) => (
                            <div key={connection.id} className="flex items-center justify-between border-b border-slate-200 py-3 last:border-0">
                              <div className="flex-1">
                                <p className="font-medium text-slate-900">{connection.name}</p>
                                <p className="text-xs text-muted-foreground">{fdt(connection.updated_at)}</p>
                              </div>
                              <div className="flex items-center gap-2">
                                
                                <Button variant="outline" size="sm" onClick={() => startEdit(connection)}>
                                  <Pencil className="h-3 w-3" />
                                </Button>
                                <Button variant="outline" size="sm" className="hover:border-destructive hover:bg-red-50 hover:text-destructive" onClick={() => remove.mutate(connection.id)}>
                                  <Trash2 className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};