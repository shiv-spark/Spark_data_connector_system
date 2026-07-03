import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Network, Plus, Trash2, Link2, Link2Off } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SchedulerFields } from "@/components/SchedulerFields";
import { buildCron, defaultSchedule } from "@/lib/schedule";

const CONNECTOR_TO_SOURCE_TYPE: Record<string, string> = {
  csv: "local_folder",
  excel: "local_folder",
  google_sheets: "google_sheet",
  api: "api",
  postgres: "postgres",
  s3: "s3",
  snowflake: "snowflake",
};

const SUPPORTS_CONNECTIONS = ["csv", "excel", "google_sheets", "api", "postgres", "s3", "snowflake"];

// Fields that hold secrets. These come back from GET /connections already
// masked as "********" (see backend _public_connection), so they must
// NEVER be copied from a saved connection into a submittable field —
// only the backend (which has the real, unmasked value) may resolve them,
// via connection_id.
const SECRET_FIELDS: Array<keyof Source> = ["src_pg_password", "sf_password"];

type Source = {
  connector_type: string;
  connection_id: number | null;
  file_path: string;
  folder_path: string;
  sheet_url: string;
  api_url: string;
  api_config: string;
  s3_bucket: string;
  s3_key: string;
  s3_file_type: string;
  src_pg_host: string;
  src_pg_db: string;
  src_pg_user: string;
  src_pg_password: string;
  src_pg_port: string;
  pg_query: string;
  sf_account: string;
  sf_user: string;
  sf_password: string;
  sf_warehouse: string;
  sf_database: string;
  sf_schema: string;
  sf_query: string;
  sf_role: string;
};

const blankSource = (): Source => ({
  connector_type: "csv",
  connection_id: null,
  file_path: "",
  folder_path: "",
  sheet_url: "",
  api_url: "",
  api_config: "",   
  s3_bucket: "",
  s3_key: "",
  s3_file_type: "csv",
  src_pg_host: "",
  src_pg_db: "",
  src_pg_user: "",
  src_pg_password: "",
  src_pg_port: "5432",
  pg_query: "",
  sf_account: "",
  sf_user: "",
  sf_password: "",
  sf_warehouse: "",
  sf_database: "",
  sf_schema: "PUBLIC",
  sf_query: "",
  sf_role: "",
});

type SourceConnectionState = {
  useExisting: boolean;
  selectedConnectionId: string;
  connectionError: string;
};

// export const MultiSource = () => {
//   const qc = useQueryClient();
//   const [pipelineName, setPipelineName] = useState("");
//   const [tableName, setTableName] = useState("");
//   const [schedule, setSchedule] = useState(defaultSchedule);
//   const [option, setOption] = useState("1");
//   const [sources, setSources] = useState<Source[]>([blankSource()]);
//   const [sourceConnectionStates, setSourceConnectionStates] = useState<Record<number, SourceConnectionState>>({});
//   const [result, setResult] = useState<any>(null);
export const MultiSource = () => {
  const qc = useQueryClient();
  const [pipelineName, setPipelineName] = useState("");
  const [tableName, setTableName] = useState("");
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [option, setOption] = useState("1");
  const [sources, setSources] = useState<Source[]>([blankSource()]);
  const [sourceConnectionStates, setSourceConnectionStates] = useState<Record<number, SourceConnectionState>>({});
  const [apiConfigErrors, setApiConfigErrors] = useState<Record<number, string>>({});   // ← NEW
  const [result, setResult] = useState<any>(null);

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const getFilteredConnections = (connectorType: string) => {
    const sourceType = CONNECTOR_TO_SOURCE_TYPE[connectorType];
    return connections.data?.filter((conn: any) => conn.source_type === sourceType) ?? [];
  };

  const updateSource = (index: number, key: keyof Source, value: string | number | null) =>
    setSources((current) => current.map((source, i) => i === index ? { ...source, [key]: value } : source));

  const updateConnectionState = (index: number, key: keyof SourceConnectionState, value: string | boolean) => {
    setSourceConnectionStates((current) => {
      const existingState = current[index] ?? {
        useExisting: false,
        selectedConnectionId: "",
        connectionError: "",
      };

      return {
        ...current,
        [index]: {
          ...existingState,
          [key]: value,
        },
      };
    });
  };

  // Fills the visible fields for a saved connection so the user gets a
  // preview of what will be used — EXCEPT secret fields, which the
  // backend returns masked and can only resolve safely itself from
  // connection_id at pipeline-creation time. Never widen this to include
  // SECRET_FIELDS.
  const populateFromConnection = (index: number, connId: string) => {
    const conn = getFilteredConnections(sources[index].connector_type).find((c: any) => String(c.id) === connId);
    if (conn?.config) {
      const cfg = conn.config;
      const connectorType = sources[index].connector_type;

      if (connectorType === "postgres") {
        updateSource(index, "src_pg_host", cfg.host || "");
        updateSource(index, "src_pg_db", cfg.database || "");
        updateSource(index, "src_pg_user", cfg.user || "");
        updateSource(index, "src_pg_password", ""); // never trust masked value — resolved server-side
        updateSource(index, "src_pg_port", cfg.port || "5432");
      } else if (connectorType === "s3") {
        updateSource(index, "s3_bucket", cfg.bucket || "");
        updateSource(index, "s3_key", cfg.prefix || "");
        updateSource(index, "s3_file_type", cfg.file_type || "csv");
      } else if (connectorType === "snowflake") {
        updateSource(index, "sf_account", cfg.account || "");
        updateSource(index, "sf_user", cfg.user || "");
        updateSource(index, "sf_password", ""); // never trust masked value — resolved server-side
        updateSource(index, "sf_warehouse", cfg.warehouse || "");
        updateSource(index, "sf_database", cfg.database || "");
        updateSource(index, "sf_schema", cfg.schema || "PUBLIC");
        updateSource(index, "sf_role", cfg.role || "");
      } else if (connectorType === "api") {
        updateSource(index, "api_url", cfg.base_url || "");
      } else if (connectorType === "google_sheets") {
        updateSource(index, "sheet_url", cfg.sheet_url || "");
      } else if (connectorType === "csv" || connectorType === "excel") {
        // A saved csv/excel connection's base_path is a DIRECTORY the
        // backend scans (see _resolve_connection_config on the backend,
        // which sets folder_path — not file_path — from base_path).
        // Mirror that here so single-source and multi-source pipelines
        // behave identically for the same saved connection.
        updateSource(index, "folder_path", cfg.base_path || "");
        updateSource(index, "file_path", "");
        updateSource(index, "s3_file_type", cfg.file_type || "csv");
      }
    }
  };

  const handleConnectorTypeChange = (index: number, newType: string) => {
    updateSource(index, "connector_type", newType);
    setSourceConnectionStates((current) => ({
      ...current,
      [index]: { useExisting: false, selectedConnectionId: "", connectionError: "" },
    }));
    setApiConfigErrors((current) => ({ ...current, [index]: "" }));
    updateSource(index, "connection_id", null);
    updateSource(index, "file_path", "");
    updateSource(index, "folder_path", "");
    updateSource(index, "sheet_url", "");
    updateSource(index, "api_url", "");
    updateSource(index, "api_config", "");
    updateSource(index, "s3_bucket", "");
    updateSource(index, "s3_key", "");
    updateSource(index, "s3_file_type", "csv");
    updateSource(index, "src_pg_host", "");
    updateSource(index, "src_pg_db", "");
    updateSource(index, "src_pg_user", "");
    updateSource(index, "src_pg_password", "");
    updateSource(index, "src_pg_port", "5432");
    updateSource(index, "pg_query", "");
    updateSource(index, "sf_account", "");
    updateSource(index, "sf_user", "");
    updateSource(index, "sf_password", "");
    updateSource(index, "sf_warehouse", "");
    updateSource(index, "sf_database", "");
    updateSource(index, "sf_schema", "PUBLIC");
    updateSource(index, "sf_query", "");
    updateSource(index, "sf_role", "");
  };
  const create = useMutation({
    mutationFn: async () => {
      const sourcesWithConnectionId = sources.map((source, index) => {
        const connState = sourceConnectionStates[index];
        const connectionId = connState?.useExisting && connState?.selectedConnectionId
          ? parseInt(connState.selectedConnectionId)
          : null;

        let parsedApiConfig: Record<string, unknown> | null = null;
        if (source.connector_type === "api" && source.api_config.trim()) {
          try {
            parsedApiConfig = JSON.parse(source.api_config);
          } catch (e) {
            throw new Error(`Source ${index + 1}: Invalid JSON in Advanced Config`);
          }
        }

        const cleaned: any = { ...source, connection_id: connectionId, api_config: parsedApiConfig };
        if (connectionId) {
          for (const field of SECRET_FIELDS) {
            cleaned[field] = "";
          }
        }
        return cleaned;
      });

      const response = await api.post("/create_multi_pipeline", {
        pipeline_name: pipelineName,
        table_name: tableName,
        option,
        schedule: buildCron(schedule),
        timezone: schedule.timezone,
        sync_mode: "full",
        sources: sourcesWithConnectionId,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  // const create = useMutation({
  //   mutationFn: async () => {
  //     const sourcesWithConnectionId = sources.map((source, index) => {
  //       const connState = sourceConnectionStates[index];
  //       const connectionId = connState?.useExisting && connState?.selectedConnectionId
  //         ? parseInt(connState.selectedConnectionId)
  //         : null;

  //       // When using a saved connection, strip any locally-held secret
  //       // values before sending — connection_id is the only thing the
  //       // backend needs to resolve real credentials. This is a belt-and-
  //       // suspenders guard on top of populateFromConnection() never
  //       // filling these fields in the first place.
  //       const cleaned = { ...source, connection_id: connectionId };
  //       if (connectionId) {
  //         for (const field of SECRET_FIELDS) {
  //           (cleaned as any)[field] = "";
  //         }
  //       }
  //       return cleaned;
  //     });

  //     const response = await api.post("/create_multi_pipeline", {
  //       pipeline_name: pipelineName,
  //       table_name: tableName,
  //       option,
  //       schedule: buildCron(schedule),
  //       timezone: schedule.timezone,
  //       sync_mode: "full",
  //       sources: sourcesWithConnectionId,
  //     });
  //     return response.data;
  //   },
  //   onSuccess: (data) => {
  //     setResult(data);
  //     qc.invalidateQueries({ queryKey: ["pipelines"] });
  //     qc.invalidateQueries({ queryKey: ["dashboard"] });
  //   },
  // });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setResult(null);

    let hasError = false;
    const nextStates = { ...sourceConnectionStates };
    const nextApiConfigErrors: Record<number, string> = {};

    sources.forEach((source, index) => {
      if (SUPPORTS_CONNECTIONS.includes(source.connector_type)) {
        const state = nextStates[index];
        if (state?.useExisting && !state?.selectedConnectionId) {
          nextStates[index] = { ...state, connectionError: "Please select a saved connection, or switch to New Connection." };
          hasError = true;
        }
      }
      if (source.connector_type === "api" && source.api_config.trim()) {
        try {
          JSON.parse(source.api_config);
        } catch (e) {
          nextApiConfigErrors[index] = "Invalid JSON — please check the syntax.";
          hasError = true;
        }
      }
    });

    if (hasError) {
      setSourceConnectionStates(nextStates);
      setApiConfigErrors(nextApiConfigErrors);
      return;
    }

    create.mutate();
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><Network className="h-5 w-5" /> Multi-Source Pipeline</h2>
      <Card>
        <CardHeader><CardTitle className="text-sm">Merge Multiple Sources Into One Pipeline</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Input placeholder="Pipeline name" value={pipelineName} onChange={(e) => setPipelineName(e.target.value)} required />
              <Input placeholder="Target table" value={tableName} onChange={(e) => setTableName(e.target.value)} required />
              <select className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={option} onChange={(e) => setOption(e.target.value)}>
                <option value="1">Append</option><option value="2">Overwrite</option><option value="3">Create new</option>
              </select>
            </div>

            <SchedulerFields value={schedule} onChange={setSchedule} />

            <div className="space-y-4">
              {sources.map((source, index) => {
                const connState = sourceConnectionStates[index] || { useExisting: false, selectedConnectionId: "", connectionError: "" };
                const filteredConnections = getFilteredConnections(source.connector_type);
                const fieldsRequired = !connState.useExisting;

                return (
                  <Card key={index} className="bg-slate-50">
                    <CardContent className="space-y-4 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <select className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={source.connector_type} onChange={(e) => handleConnectorTypeChange(index, e.target.value)}>
                          <option value="csv">CSV</option>
                          <option value="excel">Excel</option>
                          <option value="google_sheets">Google Sheets</option>
                          <option value="api">API</option>
                          <option value="postgres">Postgres</option>
                          <option value="s3">S3</option>
                          <option value="snowflake">Snowflake</option>
                        </select>
                        {sources.length > 1 && <Button type="button" variant="outline" onClick={() => setSources((current) => current.filter((_, i) => i !== index))}><Trash2 /> Remove</Button>}
                      </div>

                      {SUPPORTS_CONNECTIONS.includes(source.connector_type) && (
                        <div className="rounded-md border border-slate-200 bg-white p-3">
                          <div className="flex items-center gap-4">
                            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                              <input
                                type="radio"
                                name={`connectionMode-${index}`}
                                checked={!connState.useExisting}
                                onChange={() => {
                                  updateConnectionState(index, "useExisting", false);
                                  updateConnectionState(index, "selectedConnectionId", "");
                                  updateConnectionState(index, "connectionError", "");
                                  updateSource(index, "connection_id", null);
                                }}
                              />
                              <Link2Off className="h-4 w-4" />
                              New Connection
                            </label>
                            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                              <input
                                type="radio"
                                name={`connectionMode-${index}`}
                                checked={connState.useExisting}
                                onChange={() => updateConnectionState(index, "useExisting", true)}
                              />
                              <Link2 className="h-4 w-4" />
                              Use Saved Connection
                            </label>
                          </div>
                          {connState.useExisting && (
                            <div className="mt-3">
                              {connections.isLoading ? (
                                <p className="text-sm text-muted-foreground">Loading connections...</p>
                              ) : filteredConnections.length === 0 ? (
                                <p className="text-sm text-red-500">No saved connections for this connector type. Please create a new connection.</p>
                              ) : (
                                <select
                                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                                  value={connState.selectedConnectionId}
                                  onChange={(e) => {
                                    updateConnectionState(index, "selectedConnectionId", e.target.value);
                                    updateConnectionState(index, "connectionError", "");
                                    populateFromConnection(index, e.target.value);
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
                              {connState.connectionError && <p className="mt-2 text-sm text-red-500">{connState.connectionError}</p>}
                            </div>
                          )}
                        </div>
                      )}

                      {["csv", "excel"].includes(source.connector_type) && (
                        connState.useExisting ? (
                          <Input
                            placeholder="Folder path (from saved connection)"
                            value={source.folder_path}
                            readOnly
                            disabled
                          />
                        ) : (
                          <Input
                            placeholder="File path (e.g. /app/data/sales.csv)"
                            value={source.file_path}
                            onChange={(e) => updateSource(index, "file_path", e.target.value)}
                            required={fieldsRequired}
                          />
                        )
                      )}
                      {source.connector_type === "google_sheets" && (
                        <Input placeholder="Sheet URL" value={source.sheet_url} onChange={(e) => updateSource(index, "sheet_url", e.target.value)} required={fieldsRequired} />
                      )}
                      {source.connector_type === "api" && (
                        <div className="space-y-2">
                          <Input placeholder="API URL" value={source.api_url} onChange={(e) => updateSource(index, "api_url", e.target.value)} required={fieldsRequired} />
                          <label className="space-y-1 text-sm font-medium block">
                            Advanced Config (optional JSON)
                            <textarea
                              className="min-h-32 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                              placeholder='{"method": "POST", "auth_type": "bearer", "bearer_token": "..."}'
                              value={source.api_config}
                              onChange={(e) => {
                                updateSource(index, "api_config", e.target.value);
                                setApiConfigErrors((current) => ({ ...current, [index]: "" }));
                              }}
                            />
                          </label>
                          {apiConfigErrors[index] && <p className="text-sm text-red-500">{apiConfigErrors[index]}</p>}
                        </div>
                      )}
                      {source.connector_type === "s3" && (
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                          <Input placeholder="Bucket" value={source.s3_bucket} onChange={(e) => updateSource(index, "s3_bucket", e.target.value)} required={fieldsRequired} />
                          <Input placeholder="Key" value={source.s3_key} onChange={(e) => updateSource(index, "s3_key", e.target.value)} required={fieldsRequired} />
                          <Input placeholder="File type" value={source.s3_file_type} onChange={(e) => updateSource(index, "s3_file_type", e.target.value)} />
                        </div>
                      )}
                      {source.connector_type === "postgres" && (
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                          <Input placeholder="Host" value={source.src_pg_host} onChange={(e) => updateSource(index, "src_pg_host", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="Database" value={source.src_pg_db} onChange={(e) => updateSource(index, "src_pg_db", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="User" value={source.src_pg_user} onChange={(e) => updateSource(index, "src_pg_user", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input
                            type="password"
                            placeholder={connState.useExisting ? "(using saved connection)" : "Password"}
                            value={connState.useExisting ? "" : source.src_pg_password}
                            onChange={(e) => updateSource(index, "src_pg_password", e.target.value)}
                            required={fieldsRequired}
                            disabled={connState.useExisting}
                          />
                          <Input placeholder="Port" value={source.src_pg_port} onChange={(e) => updateSource(index, "src_pg_port", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={source.pg_query} onChange={(e) => updateSource(index, "pg_query", e.target.value)} required={true} />
                        </div>
                      )}
                      {source.connector_type === "snowflake" && (
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                          <Input placeholder="Account (e.g. XROJPNQ-RO43084)" value={source.sf_account} onChange={(e) => updateSource(index, "sf_account", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="User" value={source.sf_user} onChange={(e) => updateSource(index, "sf_user", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input
                            type="password"
                            placeholder={connState.useExisting ? "(using saved connection)" : "Password"}
                            value={connState.useExisting ? "" : source.sf_password}
                            onChange={(e) => updateSource(index, "sf_password", e.target.value)}
                            required={fieldsRequired}
                            disabled={connState.useExisting}
                          />
                          <Input placeholder="Warehouse" value={source.sf_warehouse} onChange={(e) => updateSource(index, "sf_warehouse", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="Database" value={source.sf_database} onChange={(e) => updateSource(index, "sf_database", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="Schema (default PUBLIC)" value={source.sf_schema} onChange={(e) => updateSource(index, "sf_schema", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="Role (optional)" value={source.sf_role} onChange={(e) => updateSource(index, "sf_role", e.target.value)} disabled={connState.useExisting} />
                          <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={source.sf_query} onChange={(e) => updateSource(index, "sf_query", e.target.value)} required={true} />
                        </div>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            <div className="flex gap-3">
              <Button type="button" variant="outline" onClick={() => setSources((current) => [...current, blankSource()])}><Plus /> Add Source</Button>
              <Button type="submit" disabled={create.isPending}>{create.isPending ? <Loader2 className="animate-spin" /> : <Network />} Create Multi-Source Pipeline</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {(result || create.error) && (
        <Card className={create.error ? "border-rose-200 bg-rose-50" : "border-emerald-200 bg-emerald-50"}>
          <CardContent className="p-4"><pre className="max-h-80 overflow-auto text-xs">{JSON.stringify(result ?? (create.error as any)?.response?.data ?? (create.error as Error).message, null, 2)}</pre></CardContent>
        </Card>
      )}
    </div>
  );
};
