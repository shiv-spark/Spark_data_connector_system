import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Database,
  ExternalLink,
  Figma,
  FileSpreadsheet,
  Globe,
  Loader2,
  PanelTop,
  Sparkles,
  Wand2,
  Workflow,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fdt } from "@/lib/format";
import { cn } from "@/lib/utils";

type SourceType = "pipeline" | "csv" | "excel" | "google_sheet" | "postgres" | "api" | "s3";

const sourceOptions: { value: SourceType; label: string; icon: typeof Database }[] = [
  { value: "pipeline", label: "Pipeline", icon: Workflow },
  { value: "csv", label: "CSV", icon: FileSpreadsheet },
  { value: "excel", label: "Excel", icon: FileSpreadsheet },
  { value: "google_sheet", label: "Sheets", icon: PanelTop },
  { value: "postgres", label: "Postgres", icon: Database },
  { value: "api", label: "API", icon: Globe },
  { value: "s3", label: "S3", icon: Database },
];

const ideas = [
  "Executive KPI dashboard",
  "Find data quality issues",
  "Revenue trends and top categories",
  "Explain outliers visually",
];

// Models available on Groq. Whisper models are speech-to-text only and
// cannot be used for chat completions (chart decisions / summaries), so
// they are listed but disabled in the dropdown.
const modelOptions: { value: string; label: string; disabled?: boolean }[] = [
  { value: "llama-3.1-8b-instant", label: "Groq · Llama 3.1 8B Instant" },
  { value: "llama-3.3-70b-versatile", label: "Groq · Llama 3.3 70B Versatile" },
  { value: "openai/gpt-oss-120b", label: "Groq · GPT-OSS 120B" },
  { value: "openai/gpt-oss-20b", label: "Groq · GPT-OSS 20B" },
  { value: "whisper-large-v3", label: "Whisper Large v3 (audio only — not usable here)", disabled: true },
  { value: "whisper-large-v3-turbo", label: "Whisper Large v3 Turbo (audio only — not usable here)", disabled: true },
];

export const DashboardStudio = () => {
  const navigate = useNavigate();
  const [sourceType, setSourceType] = useState<SourceType>("pipeline");
  const [connectionId, setConnectionId] = useState("");
  const [designConnectionId, setDesignConnectionId] = useState("");
  const [datasetRef, setDatasetRef] = useState("");
  const [filePath, setFilePath] = useState("");
  const [sheetUrl, setSheetUrl] = useState("");
  const [pipelineName, setPipelineName] = useState("");
  const [selectedPipeline, setSelectedPipeline] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [request, setRequest] = useState("");
  const [model, setModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [result, setResult] = useState<any>(null);

  const autoMode = request.trim().length === 0;
  const AUTO_PROMPT =
    "Profile this dataset end-to-end. Decide the best dashboard yourself: pick the most valuable KPIs, choose appropriate chart types (trend, breakdown, distribution, comparison), surface data-quality issues and outliers, and explain what matters. No further user input — design the best possible executive dashboard for this data.";
  const effectiveRequest = autoMode ? AUTO_PROMPT : request.trim();
  const effectiveModel = model === "custom" ? customModel.trim() : model;

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const pipelines = useQuery({
    queryKey: ["pipelines"],
    queryFn: async () => (await api.get("/pipelines")).data.pipelines ?? [],
  });

  const selectedPipelineObj = (pipelines.data ?? []).find(
    (p: any) => p.dag_id === selectedPipeline
  );

  const dashboards = useQuery({
    queryKey: ["agent-dashboards"],
    queryFn: async () => (await api.get("/agent/dashboards")).data.dashboards ?? [],
    refetchInterval: 15_000,
  });

  const dataConnections = (connections.data ?? []).filter(
    (connection: any) => connection.source_type !== "figma_design",
  );
  const figmaConnections = (connections.data ?? []).filter(
    (connection: any) => connection.source_type === "figma_design",
  );

  const analyze = useMutation({
    mutationFn: async () => {
      if (sourceType === "pipeline" && !connectionId) {
        const pipelineName = selectedPipeline.replace(/^pipeline_/, "");
        const actualTableName = selectedPipelineObj?.table_name || pipelineName;
        const response = await api.post("/agent/analyze", {
          source_type: "postgres",
          pipeline_name: pipelineName,
          table_name: actualTableName,
          request: effectiveRequest,
          figma_connection_id: designConnectionId ? Number(designConnectionId) : null,
          model: effectiveModel || null,
        });
        return response.data;
      }

      const selectedConnection = (connections.data ?? []).find(
        (item: any) => String(item.id) === connectionId,
      );
      const cfg = selectedConnection?.config ?? {};
      const selectedType = selectedConnection?.source_type as string | undefined;
      const effectiveSource =
        selectedType === "local_folder"
          ? datasetRef.toLowerCase().endsWith(".xlsx") ||
            datasetRef.toLowerCase().endsWith(".xls")
            ? "excel"
            : "csv"
          : selectedType === "s3"
            ? "s3"
            : selectedType || sourceType;
      const joinedPath =
        cfg.base_path && datasetRef
          ? `${String(cfg.base_path).replace(/[\\/]+$/, "")}/${datasetRef.replace(/^[\\/]+/, "")}`
          : filePath || datasetRef;
      const s3Path =
        selectedType === "s3"
          ? `s3://${cfg.bucket}/${[cfg.prefix, datasetRef].filter(Boolean).join("/")}`.replace(
              /([^:]\/)\/+/g,
              "$1",
            )
          : null;
      const apiResolvedUrl =
        selectedType === "api"
          ? `${String(cfg.base_url || "").replace(/\/+$/, "")}/${datasetRef.replace(/^\/+/, "")}`
          : apiUrl || null;
      const apiHeaders =
        selectedType === "api" && cfg.auth_type && cfg.auth_type !== "none"
          ? {
              [cfg.header_name || "Authorization"]:
                cfg.auth_type === "bearer" ? `Bearer ${cfg.api_key}` : cfg.api_key,
            }
          : null;

      const response = await api.post("/agent/analyze", {
        source_type: effectiveSource,
        file_path: ["csv", "excel"].includes(effectiveSource)
          ? joinedPath || null
          : filePath || null,
        sheet_url:
          selectedType === "google_sheet"
            ? cfg.sheet_url || datasetRef || null
            : sheetUrl || null,
        pipeline_name:
          selectedType === "postgres" ? datasetRef || pipelineName || null : pipelineName || null,
        table_name: selectedType === "postgres" ? datasetRef || null : null,
        s3_path: s3Path,
        api_url: apiResolvedUrl,
        api_headers: apiHeaders,
        figma_connection_id: designConnectionId ? Number(designConnectionId) : null,
        request: effectiveRequest,
        model: effectiveModel || null,
      });
      return response.data;
    },
    onSuccess: (data) => {
      setResult(data);
      dashboards.refetch();
      if (data?.dashboard_id) {
        navigate(`/studio/${data.dashboard_id}`);
      }
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setResult(null);
    analyze.mutate();
  };

  const dashboardList = dashboards.data ?? [];
  const total = dashboardList.length;
  const avgQuality = total
    ? Math.round(
        dashboardList.reduce((sum: number, d: any) => sum + Number(d.quality_score ?? 0), 0) /
          total,
      )
    : 0;
  const passing = dashboardList.filter((d: any) => Number(d.quality_score ?? 0) >= 80).length;

  return (
    <div className="space-y-6">
      <section className="relative overflow-hidden rounded-[14px] border border-border bg-card shadow-[0_1px_2px_rgba(15,23,42,0.04),0_12px_32px_-12px_rgba(15,23,42,0.08)] dark:shadow-[0_1px_2px_rgba(0,0,0,0.3),0_12px_32px_-12px_rgba(0,0,0,0.5)]">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 opacity-[0.55] dark:opacity-30"
          style={{
            background:
              "radial-gradient(60% 60% at 100% 0%, rgba(16,185,129,0.10) 0%, rgba(16,185,129,0) 60%), radial-gradient(40% 50% at 0% 0%, rgba(20,184,166,0.08) 0%, rgba(20,184,166,0) 65%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, rgba(16,185,129,0.4) 50%, transparent 100%)",
          }}
        />

        <div className="relative p-6 lg:p-7">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:ring-emerald-800">
                <Sparkles className="h-3 w-3" /> Agentic Studio
              </span>
              <span className="section-eyebrow">Generate · Profile · Visualize</span>
            </div>
            <div className="hidden items-center gap-3 text-[11px] text-muted-foreground md:flex">
              <span className="inline-flex items-center gap-1.5">
                <span className="relative inline-flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                </span>
                Agent ready
              </span>
              <span className="text-border dark:text-muted-foreground/30">·</span>
              <span className="font-mono text-[11px]">{effectiveModel || "auto"}</span>
            </div>
          </div>

          <h1 className="mt-4 max-w-3xl text-[28px] font-semibold leading-[1.15] tracking-tight text-foreground">
            From any dataset to a{" "}
            <span className="bg-gradient-to-br from-emerald-500 to-teal-700 bg-clip-text text-transparent dark:from-emerald-400 dark:to-teal-500">
              prompt-shaped dashboard
            </span>
            .
          </h1>
          <p className="mt-2 max-w-2xl text-[13.5px] leading-6 text-muted-foreground">
            Agents profile the data, infer KPIs, and ship charts. Refine in plain English — no SQL,
            no drag-and-drop fatigue.
          </p>

          <form
            onSubmit={submit}
            className="mt-6 rounded-[12px] border border-border bg-background shadow-[inset_0_1px_0_rgba(255,255,255,0.7),0_1px_2px_rgba(15,23,42,0.04)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.05),0_1px_2px_rgba(0,0,0,0.2)]"
          >
            <div className="flex flex-col gap-3 border-b border-border px-4 py-3 lg:flex-row lg:items-center lg:gap-4">
              <span className="section-eyebrow shrink-0">Source</span>
              <div className="flex flex-wrap items-center gap-1.5">
                {sourceOptions.map(({ value, label, icon: Icon }) => {
                  const active = !connectionId && sourceType === value;
                  return (
                    <button
                      key={value}
                      type="button"
                      disabled={!!connectionId}
                      onClick={() => setSourceType(value)}
                      className={cn(
                        "inline-flex h-7 items-center gap-1.5 rounded-full px-2.5 text-[12px] font-medium transition",
                        active
                          ? "bg-foreground text-background shadow-[inset_0_1px_0_rgba(255,255,255,0.12),0_1px_2px_rgba(15,23,42,0.25)] dark:shadow-[inset_0_1px_0_rgba(255,255,255,0.15),0_1px_2px_rgba(0,0,0,0.4)]"
                          : "bg-muted text-muted-foreground ring-1 ring-inset ring-border hover:bg-background hover:text-foreground",
                        connectionId && "opacity-40",
                      )}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {label}
                    </button>
                  );
                })}
              </div>

              <div className="flex-1" />

              <div className="flex items-center gap-2">
                <span className="section-eyebrow">Connection</span>
                <select
                  className="h-8 rounded-md border border-input bg-background px-2 pr-7 text-[12.5px] text-foreground shadow-[0_1px_0_rgba(15,23,42,0.02)] outline-none transition hover:border-muted-foreground focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 dark:shadow-[0_1px_0_rgba(0,0,0,0.1)]"
                  value={connectionId}
                  onChange={(event) => setConnectionId(event.target.value)}
                >
                  <option value="">— None —</option>
                  {dataConnections.map((connection: any) => (
                    <option key={connection.id} value={connection.id}>
                      {connection.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="section-eyebrow inline-flex items-center gap-1">
                  <Figma className="h-3.5 w-3.5 text-pink-600 dark:text-pink-500" />
                  Design
                </span>
                <select
                  className="h-8 rounded-md border border-input bg-background px-2 pr-7 text-[12.5px] text-foreground shadow-[0_1px_0_rgba(15,23,42,0.02)] outline-none transition hover:border-muted-foreground focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 dark:shadow-[0_1px_0_rgba(0,0,0,0.1)]"
                  value={designConnectionId}
                  onChange={(event) => setDesignConnectionId(event.target.value)}
                >
                  <option value="">No Figma reference</option>
                  {figmaConnections.map((connection: any) => (
                    <option key={connection.id} value={connection.id}>
                      {connection.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="section-eyebrow">Model</span>
                <select
                  className="h-8 rounded-md border border-input bg-background px-2 pr-7 text-[12.5px] text-foreground shadow-[0_1px_0_rgba(15,23,42,0.02)] outline-none transition hover:border-muted-foreground focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 dark:shadow-[0_1px_0_rgba(0,0,0,0.1)]"
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                >
                  <option value="">Auto (recommended)</option>
                  {modelOptions.map((opt) => (
                    <option key={opt.value} value={opt.value} disabled={opt.disabled}>
                      {opt.label}
                    </option>
                  ))}
                  <option value="custom">Custom…</option>
                </select>
                {model === "custom" && (
                  <Input
                    className="h-8 w-[200px] text-[12.5px]"
                    placeholder="exact model id"
                    value={customModel}
                    onChange={(event) => setCustomModel(event.target.value)}
                  />
                )}
              </div>
            </div>

            <div className="border-b border-border px-4 py-3">
              {connectionId ? (
                <Input
                  className="h-9 border-0 bg-transparent px-0 text-[13px] shadow-none focus-visible:ring-0"
                  placeholder="File name, S3 key, API path, or table name…"
                  value={datasetRef}
                  onChange={(event) => setDatasetRef(event.target.value)}
                />
              ) : sourceType === "pipeline" ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Workflow className="h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-500" />
                  {pipelines.isLoading ? (
                    <span className="text-[12.5px] text-muted-foreground">Loading pipelines…</span>
                  ) : (pipelines.data ?? []).length === 0 ? (
                    <span className="text-[12.5px] text-muted-foreground">
                      No pipelines yet — create one in <a className="font-medium text-emerald-700 hover:underline dark:text-emerald-500" href="/create">Create Pipeline</a>.
                    </span>
                  ) : (
                    <>
                      <select
                        className="h-9 min-w-[260px] rounded-md border border-input bg-background px-2 text-[13px] text-foreground shadow-[0_1px_0_rgba(15,23,42,0.02)] outline-none transition hover:border-muted-foreground focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 dark:shadow-[0_1px_0_rgba(0,0,0,0.1)]"
                        value={selectedPipeline}
                        onChange={(event) => setSelectedPipeline(event.target.value)}
                      >
                        <option value="">— Select a pipeline —</option>
                        {(pipelines.data ?? [])
                          .slice()
                          .sort((a: any, b: any) => a.dag_id.localeCompare(b.dag_id, undefined, { numeric: true }))
                          .map((p: any) => {
                            const rawName = p.dag_id.replace(/^pipeline_/, "");
                            return (
                              <option key={p.dag_id} value={p.dag_id}>
                                {rawName}
                              </option>
                            );
                          })}
                      </select>

                      {selectedPipeline ? (
                        <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 text-[10.5px] font-semibold text-muted-foreground font-mono">
                          table: {selectedPipeline.replace(/^pipeline_/, "")}
                        </span>
                      ) : null}
                    </>
                  )}
                </div>
              ) : (
                <>
                  {["csv", "excel"].includes(sourceType) && (
                    <Input
                      className="h-9 border-0 bg-transparent px-0 text-[13px] shadow-none focus-visible:ring-0"
                      placeholder="File path (e.g. /data/orders.csv)"
                      value={filePath}
                      onChange={(event) => setFilePath(event.target.value)}
                    />
                  )}
                  {sourceType === "google_sheet" && (
                    <Input
                      className="h-9 border-0 bg-transparent px-0 text-[13px] shadow-none focus-visible:ring-0"
                      placeholder="Google Sheet CSV export URL"
                      value={sheetUrl}
                      onChange={(event) => setSheetUrl(event.target.value)}
                    />
                  )}
                  {sourceType === "postgres" && (
                    <Input
                      className="h-9 border-0 bg-transparent px-0 text-[13px] shadow-none focus-visible:ring-0"
                      placeholder="Pipeline / table name"
                      value={pipelineName}
                      onChange={(event) => setPipelineName(event.target.value)}
                    />
                  )}
                  {sourceType === "api" && (
                    <Input
                      className="h-9 border-0 bg-transparent px-0 text-[13px] shadow-none focus-visible:ring-0"
                      placeholder="https://api.example.com/v1/orders"
                      value={apiUrl}
                      onChange={(event) => setApiUrl(event.target.value)}
                    />
                  )}
                  {sourceType === "s3" && (
                    <Input
                      className="h-9 border-0 bg-transparent px-0 text-[13px] shadow-none focus-visible:ring-0"
                      placeholder="s3://bucket/key"
                      value={filePath}
                      onChange={(event) => setFilePath(event.target.value)}
                    />
                  )}
                </>
              )}
            </div>

            <div className="px-4 pb-3 pt-3">
              <div className="mb-2 flex items-center justify-between">
                <span className="section-eyebrow">Direction</span>
                {autoMode ? (
                  <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2 py-0.5 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-emerald-700 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:ring-emerald-800">
                    <Sparkles className="h-3 w-3" /> Agent decides
                  </span>
                ) : (
                  <span className="text-[10.5px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                    Custom prompt
                  </span>
                )}
              </div>
              <div className="flex items-start gap-2">
                <Wand2
                  className={cn(
                    "mt-2 h-3.5 w-3.5 transition-colors",
                    autoMode ? "text-border dark:text-muted-foreground/40" : "text-emerald-600 dark:text-emerald-500",
                  )}
                />
                <textarea
                  className="min-h-[72px] w-full resize-none border-0 bg-transparent px-0 text-[13.5px] leading-6 text-foreground outline-none placeholder:text-muted-foreground"
                  value={request}
                  onChange={(event) => setRequest(event.target.value)}
                  placeholder="Optional — leave blank and the agent will pick the best KPIs, charts, and layout for this dataset on its own."
                />
              </div>
            </div>

            <div className="flex flex-col gap-3 rounded-b-[12px] border-t border-border bg-muted/40 px-4 py-3 lg:flex-row lg:items-center">
              <div className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5">
                <span className="section-eyebrow">Try</span>
                {ideas.map((idea) => (
                  <button
                    key={idea}
                    type="button"
                    onClick={() => setRequest(idea)}
                    className="inline-flex h-6 items-center rounded-full bg-background px-2 text-[11.5px] font-medium text-muted-foreground ring-1 ring-inset ring-border transition hover:text-foreground hover:ring-muted-foreground"
                  >
                    {idea}
                  </button>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <span className="hidden text-[11px] text-muted-foreground font-mono md:inline">
                  ⌘ ↵
                </span>
                <Button type="submit" disabled={analyze.isPending} className="h-8 px-3.5">
                  {analyze.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : autoMode ? (
                    <Wand2 className="h-3.5 w-3.5" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5" />
                  )}
                  {autoMode ? "Auto-design Dashboard" : "Generate Dashboard"}
                </Button>
              </div>
            </div>
          </form>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Dashboards" value={String(total)} hint="all-time" />
        <StatTile label="Avg quality" value={`${avgQuality}`} suffix="/100" hint="across runs" />
        <StatTile
          label="Passing"
          value={String(passing)}
          hint="≥ 80 score"
          tone={passing > 0 ? "good" : "neutral"}
        />
        <StatTile label="Model" value={effectiveModel || "Auto"} hint="selected" mono />
      </section>

      {analyze.isPending && (
        <div className="flex items-center gap-3 rounded-[10px] border border-emerald-200/70 bg-gradient-to-b from-emerald-50/80 to-card px-4 py-3 text-[13px] text-emerald-800 shadow-[0_1px_0_rgba(15,23,42,0.03)] dark:border-emerald-800/50 dark:from-emerald-950/60 dark:to-card dark:text-emerald-300">
          <span className="relative inline-flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <span className="font-medium">Profiling dataset, selecting charts, building dashboard…</span>
          <Loader2 className="ml-auto h-3.5 w-3.5 animate-spin text-emerald-600 dark:text-emerald-400" />
        </div>
      )}

      {(result || analyze.error) && (
        <div
          className={cn(
            "rounded-[10px] border px-4 py-3 text-[13px] shadow-[0_1px_0_rgba(15,23,42,0.03)]",
            analyze.error
              ? "border-rose-200 bg-rose-50/80 text-rose-800 dark:border-rose-800/50 dark:bg-rose-950/50 dark:text-rose-300"
              : "border-emerald-200 bg-emerald-50/70 text-emerald-900 dark:border-emerald-800/50 dark:bg-emerald-950/50 dark:text-emerald-100",
          )}
        >
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              {analyze.error ? null : <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />}
              <span className="font-semibold">
                {analyze.error ? "Generation failed" : "Dashboard ready"}
              </span>
            </div>
            {result?.dashboard_id ? (
              <a
                href={`/studio/${result.dashboard_id}`}
                className="inline-flex items-center gap-1 text-[12.5px] font-semibold text-emerald-700 hover:text-emerald-900 dark:text-emerald-500 dark:hover:text-emerald-400"
              >
                Open in studio <ArrowUpRight className="h-3.5 w-3.5" />
              </a>
            ) : null}
          </div>
          <pre className="mt-2 max-h-40 overflow-auto rounded-md bg-background/70 p-2 text-[11px] text-muted-foreground ring-1 ring-inset ring-border font-mono">
            {JSON.stringify(
              result ?? (analyze.error as any)?.response?.data ?? (analyze.error as Error).message,
              null,
              2,
            )}
          </pre>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_320px]">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between gap-2 border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <CardTitle className="text-[13.5px] font-semibold tracking-tight text-foreground">
                Generated Dashboards
              </CardTitle>
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10.5px] font-semibold text-muted-foreground font-mono">
                {total}
              </span>
            </div>
            <button
              type="button"
              onClick={() => dashboards.refetch()}
              className="text-[11.5px] font-medium text-muted-foreground hover:text-foreground"
            >
              Refresh
            </button>
          </CardHeader>
          <CardContent className="pt-4">
            {dashboards.isLoading ? (
              <SkeletonGrid />
            ) : dashboardList.length ? (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {dashboardList.map((dashboard: any) => (
                  <DashboardTile key={dashboard.dashboard_id} dashboard={dashboard} />
                ))}
              </div>
            ) : (
              <EmptyState />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b border-border pb-3">
            <CardTitle className="text-[13.5px] font-semibold tracking-tight text-foreground">
              Recipes
            </CardTitle>
            <p className="mt-1 text-[11.5px] text-muted-foreground">
              Pre-built prompts our agents do well.
            </p>
          </CardHeader>
          <CardContent className="space-y-1.5 pt-3">
            {ideas.map((idea, i) => (
              <button
                key={idea}
                type="button"
                onClick={() => setRequest(idea)}
                className="group flex w-full items-center gap-3 rounded-md border border-transparent px-2 py-2 text-left text-[12.5px] text-foreground transition hover:border-border hover:bg-card"
              >
                <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md bg-emerald-50 text-[10px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200 font-mono dark:bg-emerald-950/50 dark:text-emerald-400 dark:ring-emerald-800">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="flex-1">{idea}</span>
                <ArrowUpRight className="h-3.5 w-3.5 text-muted-foreground transition group-hover:translate-x-px group-hover:-translate-y-px group-hover:text-foreground" />
              </button>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const StatTile = ({
  label,
  value,
  suffix,
  hint,
  tone = "neutral",
  mono: useMono = false,
}: {
  label: string;
  value: string;
  suffix?: string;
  hint?: string;
  tone?: "good" | "neutral";
  mono?: boolean;
}) => (
  <div className="surface-tinted px-4 py-3">
    <div className="flex items-center justify-between">
      <span className="section-eyebrow">{label}</span>
      {tone === "good" ? (
        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
      ) : (
        <span className="inline-flex h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
      )}
    </div>
    <div className="mt-1.5 flex items-baseline gap-1">
      <span
        className={cn(
          "text-[22px] font-semibold leading-none tracking-tight text-foreground",
          useMono && "font-mono"
        )}
      >
        {value}
      </span>
      {suffix ? (
        <span className="text-[12px] font-medium text-muted-foreground font-mono">
          {suffix}
        </span>
      ) : null}
    </div>
    {hint ? <p className="mt-1 text-[11px] text-muted-foreground">{hint}</p> : null}
  </div>
);

const DashboardTile = ({ dashboard }: { dashboard: any }) => {
  const score = Math.min(Number(dashboard.quality_score ?? 0), 100);
  const grade = dashboard.grade ?? gradeFromScore(score);
  const tone = score >= 80 ? "good" : score >= 60 ? "warn" : "bad";
  return (
    <a
      href={`/studio/${dashboard.dashboard_id}`}
      className="group relative flex flex-col gap-3 overflow-hidden rounded-[10px] border border-border bg-card p-3.5 shadow-[0_1px_0_rgba(15,23,42,0.03)] transition hover:-translate-y-px hover:border-muted-foreground hover:shadow-[0_1px_2px_rgba(15,23,42,0.06),0_8px_20px_-12px_rgba(15,23,42,0.18)] dark:shadow-[0_1px_0_rgba(0,0,0,0.1)] dark:hover:shadow-[0_1px_2px_rgba(0,0,0,0.2),0_8px_20px_-12px_rgba(0,0,0,0.4)]"
    >
      <div
        aria-hidden
        className={cn(
          "absolute right-0 top-0 h-16 w-16 opacity-60 blur-2xl transition-opacity group-hover:opacity-90",
          tone === "good" && "bg-emerald-300/40 dark:bg-emerald-500/20",
          tone === "warn" && "bg-amber-300/40 dark:bg-amber-500/20",
          tone === "bad" && "bg-rose-300/40 dark:bg-rose-500/20",
        )}
      />
      <div className="relative flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[13.5px] font-semibold text-foreground">
            {dashboard.name || "Untitled"}
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
            <span className="rounded bg-muted px-1.5 py-0.5 font-medium text-muted-foreground">
              {dashboard.source_type}
            </span>
            <span className="text-border dark:text-muted-foreground/30">·</span>
            <span className="font-mono">{fdt(dashboard.last_updated)}</span>
          </p>
        </div>
        <span
          className={cn(
            "inline-flex h-6 min-w-[28px] items-center justify-center rounded-md px-1.5 text-[11px] font-bold tracking-tight ring-1 ring-inset font-mono",
            tone === "good" && "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:ring-emerald-800",
            tone === "warn" && "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950/50 dark:text-amber-400 dark:ring-amber-800",
            tone === "bad" && "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950/50 dark:text-rose-400 dark:ring-rose-800",
          )}
        >
          {grade}
        </span>
      </div>

      <div className="relative">
        <div className="flex items-center justify-between text-[10.5px] font-medium text-muted-foreground">
          <span className="section-eyebrow">Quality</span>
          <span className="text-foreground font-mono">
            {score}
          </span>
        </div>
        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              "h-full rounded-full",
              tone === "good" && "bg-gradient-to-r from-emerald-400 to-emerald-600",
              tone === "warn" && "bg-gradient-to-r from-amber-400 to-amber-600",
              tone === "bad" && "bg-gradient-to-r from-rose-400 to-rose-600",
            )}
            style={{ width: `${score}%` }}
          />
        </div>
      </div>

      <div className="relative flex items-center justify-between text-[11px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <BarChart3 className="h-3 w-3" />
          dashboard
        </span>
        <span className="inline-flex items-center gap-1 font-medium text-foreground group-hover:text-emerald-700 dark:group-hover:text-emerald-500">
          Open <ExternalLink className="h-3 w-3" />
        </span>
      </div>
    </a>
  );
};

const SkeletonGrid = () => (
  <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
    {Array.from({ length: 4 }).map((_, i) => (
      <div
        key={i}
        className="h-[112px] animate-pulse rounded-[10px] border border-border bg-gradient-to-b from-card to-muted/50"
      />
    ))}
  </div>
);

const EmptyState = () => (
  <div className="flex flex-col items-center justify-center gap-2 rounded-[10px] border border-dashed border-border bg-muted/30 px-4 py-10 text-center">
    <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-50 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950/50 dark:ring-emerald-800">
      <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />
    </div>
    <p className="text-[13px] font-semibold text-foreground">No dashboards yet</p>
    <p className="max-w-xs text-[11.5px] text-muted-foreground">
      Pick a source above and describe what you want — the agent does the rest.
    </p>
  </div>
);

const gradeFromScore = (score: number) => {
  if (score >= 90) return "A";
  if (score >= 80) return "B";
  if (score >= 70) return "C";
  if (score >= 60) return "D";
  return "F";
};
