
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, PlusCircle, Link2, Link2Off, Check, ChevronLeft, ChevronRight, CheckCircle2, XCircle, Network, Plus, Trash2 } from "lucide-react";
// import { Loader2, Network, Plus, Trash2, Link2, Link2Off, Check, ChevronLeft, ChevronRight } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SchedulerFields } from "@/components/SchedulerFields";
import { FolderUpload } from "@/pages/FolderUpload";
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

const CONNECTOR_LABELS: Record<string, string> = {
  csv: "CSV",
  excel: "Excel",
  google_sheets: "Google Sheets",
  api: "API",
  postgres: "Postgres",
  s3: "S3",
  snowflake: "Snowflake",
};

const SUPPORTS_CONNECTIONS = ["csv", "excel", "google_sheets", "api", "postgres", "s3", "snowflake"];

const SECRET_FIELDS: Array<keyof Source> = ["src_pg_password", "sf_password"];

const STEPS = [
  { id: 1, label: "Basic Info" },
  { id: 2, label: "Sources" },
  { id: 3, label: "Schedule" },
  { id: 4, label: "Review & Create" },
];

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

export const MultiSource = () => {
  const qc = useQueryClient();
  const [pipelineName, setPipelineName] = useState("");
  const [tableName, setTableName] = useState("");
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [option, setOption] = useState("1");
  const [sources, setSources] = useState<Source[]>([blankSource()]);
  const [sourceConnectionStates, setSourceConnectionStates] = useState<Record<number, SourceConnectionState>>({});
  const [apiConfigErrors, setApiConfigErrors] = useState<Record<number, string>>({});
  const [result, setResult] = useState<any>(null);

  const [currentStep, setCurrentStep] = useState(1);
  const [stepError, setStepError] = useState("");
  const [activeSourceTab, setActiveSourceTab] = useState(0);

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
      const existingState = current[index] ?? { useExisting: false, selectedConnectionId: "", connectionError: "" };
      return { ...current, [index]: { ...existingState, [key]: value } };
    });
  };

  const populateFromConnection = (index: number, connId: string) => {
    const conn = getFilteredConnections(sources[index].connector_type).find((c: any) => String(c.id) === connId);
    if (conn?.config) {
      const cfg = conn.config;
      const connectorType = sources[index].connector_type;

      if (connectorType === "postgres") {
        updateSource(index, "src_pg_host", cfg.host || "");
        updateSource(index, "src_pg_db", cfg.database || "");
        updateSource(index, "src_pg_user", cfg.user || "");
        updateSource(index, "src_pg_password", "");
        updateSource(index, "src_pg_port", cfg.port || "5432");
      } else if (connectorType === "s3") {
        updateSource(index, "s3_bucket", cfg.bucket || "");
        updateSource(index, "s3_key", cfg.prefix || "");
        updateSource(index, "s3_file_type", cfg.file_type || "csv");
      } else if (connectorType === "snowflake") {
        updateSource(index, "sf_account", cfg.account || "");
        updateSource(index, "sf_user", cfg.user || "");
        updateSource(index, "sf_password", "");
        updateSource(index, "sf_warehouse", cfg.warehouse || "");
        updateSource(index, "sf_database", cfg.database || "");
        updateSource(index, "sf_schema", cfg.schema || "PUBLIC");
        updateSource(index, "sf_role", cfg.role || "");
      } else if (connectorType === "api") {
        updateSource(index, "api_url", cfg.base_url || "");
      } else if (connectorType === "google_sheets") {
        updateSource(index, "sheet_url", cfg.sheet_url || "");
      } else if (connectorType === "csv" || connectorType === "excel") {
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

  const addSource = () => {
    setSources((current) => [...current, blankSource()]);
    setActiveSourceTab(sources.length); // jump to the new tab
  };

  const removeSource = (index: number) => {
    setSources((current) => current.filter((_, i) => i !== index));
    setSourceConnectionStates((current) => {
      const next: Record<number, SourceConnectionState> = {};
      Object.entries(current).forEach(([key, val]) => {
        const i = Number(key);
        if (i < index) next[i] = val;
        else if (i > index) next[i - 1] = val;
      });
      return next;
    });
    setActiveSourceTab((current) => Math.max(0, current >= index ? current - 1 : current));
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

      // Reset the whole form so the user can immediately create another
      // pipeline without manually going Back through every step, and
      // without accidentally resubmitting the same pipeline_name (which
      // the backend rejects as "already exists").
      setPipelineName("");
      setTableName("");
      setSchedule(defaultSchedule);
      setOption("1");
      setSources([blankSource()]);
      setSourceConnectionStates({});
      setApiConfigErrors({});
      setStepError("");
      setCurrentStep(1);
      setActiveSourceTab(0);
    },
  });

  // ── Step + per-source validation ──────────────────────────────────────
  const validateSource = (index: number): string => {
    const source = sources[index];
    const connState = sourceConnectionStates[index];
    const label = `Source ${index + 1}`;

    if (SUPPORTS_CONNECTIONS.includes(source.connector_type) && connState?.useExisting) {
      if (!connState.selectedConnectionId) return `${label}: select a saved connection, or switch to New Connection.`;
      return "";
    }

    if (["csv", "excel"].includes(source.connector_type) && !source.file_path && !source.folder_path) {
      return `${label}: provide a file path or folder path.`;
    }
    if (source.connector_type === "google_sheets" && !source.sheet_url.trim()) return `${label}: sheet URL is required.`;
    if (source.connector_type === "api" && !source.api_url.trim()) return `${label}: API URL is required.`;
    if (source.connector_type === "api" && source.api_config.trim()) {
      try { JSON.parse(source.api_config); } catch { return `${label}: Advanced Config has invalid JSON.`; }
    }
    if (source.connector_type === "postgres" && (!source.src_pg_host || !source.src_pg_db || !source.src_pg_user || !source.pg_query)) {
      return `${label}: host, database, user, and query are required.`;
    }
    if (source.connector_type === "s3" && (!source.s3_bucket || !source.s3_key)) return `${label}: bucket and key are required.`;
    if (source.connector_type === "snowflake" && (!source.sf_account || !source.sf_user || !source.sf_warehouse || !source.sf_database || !source.sf_query)) {
      return `${label}: account, user, warehouse, database, and query are required.`;
    }
    return "";
  };

  const validateStep = (step: number): string => {
    if (step === 1) {
      if (!pipelineName.trim()) return "Pipeline name is required.";
      if (!tableName.trim()) return "Target table is required.";
      return "";
    }
    if (step === 2) {
      if (sources.length === 0) return "At least one source is required.";
      for (let i = 0; i < sources.length; i++) {
        const err = validateSource(i);
        if (err) {
          setActiveSourceTab(i);
          return err;
        }
      }
      return "";
    }
    return "";
  };

  const goNext = () => {
    const err = validateStep(currentStep);
    if (err) { setStepError(err); return; }
    setStepError("");
    setCurrentStep((s) => Math.min(s + 1, STEPS.length));
  };

  const goBack = () => {
    setStepError("");
    setCurrentStep((s) => Math.max(s - 1, 1));
  };

  const goToStep = (step: number) => {
    if (step < currentStep) { setStepError(""); setCurrentStep(step); return; }
    for (let s = currentStep; s < step; s++) {
      const err = validateStep(s);
      if (err) { setStepError(err); return; }
    }
    setStepError("");
    setCurrentStep(step);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setResult(null);
    setStepError("");

    const err = validateStep(2);
    if (err) {
      setStepError(err);
      setCurrentStep(2);
      return;
    }

    create.mutate();
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><Network className="h-5 w-5" /> Multi-Source Pipeline</h2>

      {/* ── Stepper ─────────────────────────────────────────────────── */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center">
            {STEPS.map((step, idx) => (
              <div key={step.id} className="flex flex-1 items-center last:flex-none">
                  <button type="button" onClick={() => goToStep(step.id)} className="flex items-center gap-2 group">
                   <span
                     className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border-2 text-sm font-medium transition-colors ${
                       step.id === currentStep
                         ? "border-emerald-600 bg-emerald-600 text-white"
                         : step.id < currentStep
                         ? "border-emerald-600 bg-emerald-50 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400"
                         : "border-border bg-background text-muted-foreground group-hover:border-muted-foreground"
                     }`}
                   >
                     {step.id < currentStep ? <Check className="h-4 w-4" /> : step.id}
                   </span>
                   <span className={`hidden text-sm font-medium sm:block ${step.id === currentStep ? "text-foreground" : step.id < currentStep ? "text-emerald-700 dark:text-emerald-400" : "text-muted-foreground"}`}>
                     {step.label}
                   </span>
                 </button>
                 {idx < STEPS.length - 1 && <div className={`mx-3 h-0.5 flex-1 ${step.id < currentStep ? "bg-emerald-600" : "bg-border"}`} />}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Step {currentStep} of {STEPS.length}: {STEPS[currentStep - 1].label}</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">

            {/* ══════════════════ STEP 1 — BASIC INFO ══════════════════ */}
            {currentStep === 1 && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <label className="space-y-1 text-sm font-medium">
                  Pipeline name
                  <Input value={pipelineName} onChange={(e) => setPipelineName(e.target.value)} placeholder="e.g. combined_sales_pipeline" required />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  Target table
                  <Input value={tableName} onChange={(e) => setTableName(e.target.value)} placeholder="e.g. combined_sales" required />
                </label>
                <label className="space-y-1 text-sm font-medium">
                  Load option (first source)
                  <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={option} onChange={(e) => setOption(e.target.value)}>
                    <option value="1">Append</option>
                    <option value="2">Overwrite</option>
                    <option value="3">Create new</option>
                  </select>
                </label>
                <p className="text-xs text-muted-foreground md:col-span-3">
                  Note: only the first source uses this load option. Every subsequent source always appends, so it can't overwrite rows from earlier sources.
                </p>
              </div>
            )}

            {/* ══════════════════ STEP 2 — SOURCES (tabs) ══════════════════ */}
            {currentStep === 2 && (
              <div className="space-y-4">
                {/* Tab bar */}
                <div className="flex flex-wrap items-center gap-2 border-b border-border pb-2">
                   {sources.map((source, index) => (
                     <button
                       key={index}
                       type="button"
                       onClick={() => setActiveSourceTab(index)}
                       className={`flex items-center gap-2 rounded-t-md px-3 py-1.5 text-sm font-medium transition-colors ${
                         activeSourceTab === index
                           ? "bg-muted text-foreground"
                           : "text-muted-foreground hover:bg-muted/50"
                       }`}
                     >
                       Source {index + 1}
                       <span className="rounded bg-muted px-1.5 py-0.5 text-xs">{CONNECTOR_LABELS[source.connector_type]}</span>
                      {sources.length > 1 && (
                        <Trash2
                          className="h-3 w-3 text-muted-foreground hover:text-destructive"
                          onClick={(e) => { e.stopPropagation(); removeSource(index); }}
                        />
                      )}
                    </button>
                  ))}
                  <Button type="button" variant="outline" size="sm" onClick={addSource}>
                    <Plus className="h-3.5 w-3.5" /> Add Source
                  </Button>
                </div>

                {/* Active source's config panel */}
                {sources.map((source, index) => {
                  if (index !== activeSourceTab) return null;
                  const connState = sourceConnectionStates[index] || { useExisting: false, selectedConnectionId: "", connectionError: "" };
                  const filteredConnections = getFilteredConnections(source.connector_type);
                  const fieldsRequired = !connState.useExisting;

                  return (
                    <div key={index} className="space-y-4">
                      <label className="space-y-1 text-sm font-medium block max-w-xs">
                        Connector type
                        <select
                          className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                          value={source.connector_type}
                          onChange={(e) => handleConnectorTypeChange(index, e.target.value)}
                        >
                          {Object.keys(CONNECTOR_LABELS).map((c) => (
                            <option key={c} value={c}>{CONNECTOR_LABELS[c]}</option>
                          ))}
                        </select>
                      </label>

                      {SUPPORTS_CONNECTIONS.includes(source.connector_type) && (
                         <div className="rounded-md border border-border bg-muted/50 p-3">
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
                              <Link2Off className="h-4 w-4" /> New Connection
                            </label>
                            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
                              <input
                                type="radio"
                                name={`connectionMode-${index}`}
                                checked={connState.useExisting}
                                onChange={() => updateConnectionState(index, "useExisting", true)}
                              />
                              <Link2 className="h-4 w-4" /> Use Saved Connection
                            </label>
                          </div>
                          {connState.useExisting && (
                            <div className="mt-3">
                              {connections.isLoading ? (
                                <p className="text-sm text-muted-foreground">Loading connections...</p>
                              ) : filteredConnections.length === 0 ? (
                                <p className="text-sm text-destructive">No saved connections for this connector type. Please create a new connection.</p>
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
                                    <option key={conn.id} value={conn.id}>{conn.name}</option>
                                  ))}
                                </select>
                              )}
                              {connState.connectionError && <p className="mt-2 text-sm text-destructive">{connState.connectionError}</p>}
                            </div>
                          )}
                        </div>
                      )}

                      {["csv", "excel"].includes(source.connector_type) && (
                        connState.useExisting ? (
                          <Input placeholder="Folder path (from saved connection)" value={source.folder_path} readOnly disabled />
                        ) : (
                          <div className="space-y-3">
                            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                              <Input placeholder="File path" value={source.file_path} onChange={(e) => updateSource(index, "file_path", e.target.value)} />
                              <Input placeholder="Folder path (all files in it)" value={source.folder_path} onChange={(e) => updateSource(index, "folder_path", e.target.value)} />
                            </div>
                            <FolderUpload
                              connectorType={source.connector_type as "csv" | "excel"}
                              onFolderResolved={(folderPath) => { updateSource(index, "folder_path", folderPath); updateSource(index, "file_path", ""); }}
                              onFileResolved={(filePath) => { updateSource(index, "file_path", filePath); updateSource(index, "folder_path", ""); }}
                            />
                          </div>
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
                              placeholder='{"method": "GET", "records_path": "products"}'
                              value={source.api_config}
                              onChange={(e) => {
                                updateSource(index, "api_config", e.target.value);
                                setApiConfigErrors((current) => ({ ...current, [index]: "" }));
                              }}
                            />
                          </label>
                           {apiConfigErrors[index] && <p className="text-sm text-destructive">{apiConfigErrors[index]}</p>}
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
                          <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={source.pg_query} onChange={(e) => updateSource(index, "pg_query", e.target.value)} required />
                        </div>
                      )}
                      {source.connector_type === "snowflake" && (
                        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                          <Input placeholder="Account" value={source.sf_account} onChange={(e) => updateSource(index, "sf_account", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
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
                          <Input placeholder="Schema" value={source.sf_schema} onChange={(e) => updateSource(index, "sf_schema", e.target.value)} required={fieldsRequired} disabled={connState.useExisting} />
                          <Input placeholder="Role (optional)" value={source.sf_role} onChange={(e) => updateSource(index, "sf_role", e.target.value)} disabled={connState.useExisting} />
                          <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={source.sf_query} onChange={(e) => updateSource(index, "sf_query", e.target.value)} required />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}

            {/* ══════════════════ STEP 3 — SCHEDULE ══════════════════ */}
            {currentStep === 3 && <SchedulerFields value={schedule} onChange={setSchedule} />}

            {/* ══════════════════ STEP 4 — REVIEW ══════════════════ */}
            {currentStep === 4 && (
              <div className="space-y-4">
                 <div className="rounded-md border border-border bg-muted/50 p-4 text-sm">
                   <h3 className="mb-3 font-semibold text-foreground">Pipeline overview</h3>
                  <dl className="grid grid-cols-1 gap-x-6 gap-y-2 md:grid-cols-2">
                    <div><dt className="text-muted-foreground">Pipeline name</dt><dd className="font-medium">{pipelineName || "—"}</dd></div>
                    <div><dt className="text-muted-foreground">Target table</dt><dd className="font-medium">{tableName || "—"}</dd></div>
                    <div><dt className="text-muted-foreground">Load option</dt><dd className="font-medium">{{ "1": "Append", "2": "Overwrite", "3": "Create new" }[option]}</dd></div>
                    <div><dt className="text-muted-foreground">Schedule</dt><dd className="font-medium">{buildCron(schedule)} ({schedule.timezone})</dd></div>
                  </dl>
                </div>

                 <div className="space-y-2">
                   <h3 className="text-sm font-semibold text-foreground">Sources ({sources.length})</h3>
                   {sources.map((source, index) => {
                     const connState = sourceConnectionStates[index];
                     return (
                       <div key={index} className="rounded-md border border-border bg-card p-3 text-sm">
                        <div className="flex items-center justify-between">
                          <span className="font-medium">Source {index + 1}: {CONNECTOR_LABELS[source.connector_type]}</span>
                          {index === 0 && <span className="text-xs text-muted-foreground">uses pipeline load option</span>}
                        </div>
                        <p className="mt-1 text-muted-foreground">
                          {connState?.useExisting
                            ? `Saved connection: ${getFilteredConnections(source.connector_type).find((c: any) => String(c.id) === connState.selectedConnectionId)?.name || connState.selectedConnectionId}`
                            : source.file_path || source.folder_path || source.sheet_url || source.api_url || source.src_pg_host || source.s3_bucket || source.sf_account || "—"}
                        </p>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {stepError && <p className="text-sm text-destructive">{stepError}</p>}

            {/* ══════════════════ NAVIGATION ══════════════════ */}
            <div className="flex items-center justify-between border-t border-border pt-4">
              <Button type="button" variant="outline" onClick={goBack} disabled={currentStep === 1}>
                <ChevronLeft className="h-4 w-4" /> Back
              </Button>

              {currentStep < STEPS.length ? (
                <Button type="button" onClick={goNext}>
                  Next <ChevronRight className="h-4 w-4" />
                </Button>
              ) : (
                <Button type="submit" disabled={create.isPending}>
                  {create.isPending ? <Loader2 className="animate-spin" /> : <Network />} Create Multi-Source Pipeline
                </Button>
              )}
            </div>
          </form>
        </CardContent>
      </Card>

      {result && (
         <Card className="border-emerald-200 bg-emerald-50 dark:border-emerald-900 dark:bg-emerald-950">
           <CardContent className="flex items-start gap-3 p-4">
             <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600 dark:text-emerald-400" />
             <div className="space-y-1">
               <p className="font-medium text-emerald-900 dark:text-emerald-100">Pipeline created successfully</p>
               <p className="text-sm text-emerald-800 dark:text-emerald-200">
                 <span className="font-medium">{result.dag_id}</span> is set up and will start running on schedule.
               </p>
               {result.message && <p className="text-xs text-emerald-700 dark:text-emerald-300">{result.message}</p>}
             </div>
           </CardContent>
         </Card>
       )}

{create.error && (
         <Card className="border-rose-200 bg-rose-50 dark:border-rose-900 dark:bg-rose-950">
           <CardContent className="flex items-start gap-3 p-4">
             <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600 dark:text-rose-400" />
             <div className="space-y-1">
               <p className="font-medium text-rose-900 dark:text-rose-100">Couldn\'t create pipeline</p>
               <p className="text-sm text-rose-800 dark:text-rose-200">
                 {(create.error as any)?.response?.data?.detail?.error
                   || (create.error as any)?.response?.data?.detail
                   || (create.error as Error).message}
               </p>
             </div>
           </CardContent>
         </Card>
       )}
    </div>
  );
};