
import { FormEvent, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Database,
  DatabaseZap,
  ExternalLink,
  Figma,
  FileSpreadsheet,
  Loader2,
  Snowflake,
  Sparkles,
  Wand2,
  Workflow,
} from "lucide-react";
import { api, fetchDataGenTables } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { fdt } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState as ConsoleEmptyState } from "@/components/console/Panel";
import { StudioStage, SourceTile } from "@/components/console/StudioStage";
import { DatasetPreview } from "@/components/console/DatasetPreview";

// API, Google Sheets, and S3 sources are intentionally NOT offered here —
// only Pipeline, CSV, Excel, Postgres, and Snowflake.
type SourceType = "pipeline" | "csv" | "excel" | "postgres" | "snowflake";

const sourceOptions: { value: SourceType; label: string; icon: typeof Database }[] = [
  { value: "pipeline", label: "Pipeline", icon: Workflow },
  { value: "csv", label: "CSV", icon: FileSpreadsheet },
  { value: "excel", label: "Excel", icon: FileSpreadsheet },
  // { value: "postgres", label: "Postgres", icon: Database },
  // { value: "snowflake", label: "Snowflake", icon: Snowflake },
];

// Connection types allowed in the "Connection" dropdown. api / s3 /
// google_sheet connections are deliberately excluded — only local files,
// Postgres, and Snowflake connections are usable from this studio.
const ALLOWED_CONNECTION_TYPES = new Set(["local_folder", "postgres", "snowflake"]);

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
  const [pipelineName, setPipelineName] = useState("");
  const [selectedPipeline, setSelectedPipeline] = useState("");
  const [request, setRequest] = useState("");
  const [model, setModel] = useState("");
  const [customModel, setCustomModel] = useState("");
  const [dashboardName, setDashboardName] = useState("");
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

  const selectedConnectionObj = (connections.data ?? []).find(
    (c: any) => String(c.id) === connectionId,
  );

  // Only warehouse-style connections can enumerate tables; folders cannot.
  const canListTables =
    selectedConnectionObj?.source_type === "postgres" ||
    selectedConnectionObj?.source_type === "snowflake";
  const isSnowflakeSource = selectedConnectionObj?.source_type === "snowflake";
  const isPipelineSource = !connectionId && !!selectedPipeline;

  const tables = useQuery({
    queryKey: ["studio-tables", connectionId],
    queryFn: () => fetchDataGenTables(connectionId),
    enabled: !!connectionId && canListTables,
    retry: false,
  });

  const hasSource = !!connectionId || !!selectedPipeline;
  const hasDataset = isPipelineSource ? hasSource : !!datasetRef.trim();
  const pickedLabel = connectionId
    ? selectedConnectionObj?.name
    : selectedPipeline
      ? selectedPipeline.replace(/^pipeline_/, "")
      : "";

  /* Picking a source clears the other kind, so the two can never both be set. */
  const pickConnection = (connection: any) => {
    setConnectionId(String(connection.id));
    setSelectedPipeline("");
    setDatasetRef("");
    setSourceType(connection.source_type === "snowflake" ? "snowflake" : "postgres");
  };

  const pickPipeline = (pipeline: any) => {
    setSelectedPipeline(pipeline.dag_id);
    setConnectionId("");
    setDatasetRef("");
    setSourceType("pipeline");
  };

  const dashboards = useQuery({
    queryKey: ["agent-dashboards"],
    queryFn: async () => (await api.get("/agent/dashboards")).data.dashboards ?? [],
    refetchInterval: 15_000,
  });

  // Only local files / Postgres / Snowflake connections are selectable here.
  const dataConnections = (connections.data ?? []).filter((connection: any) =>
    ALLOWED_CONNECTION_TYPES.has(connection.source_type),
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
          display_name: dashboardName.trim(),
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
          : selectedType || sourceType;
      const joinedPath =
        cfg.base_path && datasetRef
          ? `${String(cfg.base_path).replace(/[\\/]+$/, "")}/${datasetRef.replace(/^[\\/]+/, "")}`
          : filePath || datasetRef;

      const isSnowflake = selectedType === "snowflake";
      const isPostgres = selectedType === "postgres";

      const response = await api.post("/agent/analyze", {
        source_type: effectiveSource,
        connection_id: connectionId ? Number(connectionId) : null,
        file_path: ["csv", "excel"].includes(effectiveSource)
          ? joinedPath || null
          : filePath || null,
        pipeline_name: isPostgres ? datasetRef || pipelineName || null : pipelineName || null,
        table_name: isPostgres ? datasetRef || null : null,
        sf_query: isSnowflake && /^\s*select\s/i.test(datasetRef) ? datasetRef : null,
        sf_table: isSnowflake && !/^\s*select\s/i.test(datasetRef) ? datasetRef || null : null,
        figma_connection_id: designConnectionId ? Number(designConnectionId) : null,
        request: effectiveRequest,
        model: effectiveModel || null,
        display_name: dashboardName.trim(),
      });
      return response.data;
    },
    onSuccess: (data) => {
      setResult(data);
      dashboards.refetch();
      if (data?.dashboard_id) {
        navigate(`/app/studio/${data.dashboard_id}`);
      }
    },
    onError: (err: any) => {
    const detail = err?.response?.data?.detail;
    if (detail?.error) {
      setResult({ error: detail.error, existing_name: detail.existing_name });
    } else if (typeof detail === "string") {
      setResult({ error: detail });                          // ← plain string 500 error bhi dikhao
    } else {
      setResult({ error: "Failed to create dashboard" });
    }
  },
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!dashboardName.trim()) {
      setResult({ error: "Please enter a dashboard name" });
      return;
    }
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
      <PageHeader
        icon={Sparkles}
        eyebrow="Overview"
        title="Dashboard Studio"
        description="Pick a dataset, look at what's actually in it, then say what you want — or leave it blank and the agent designs the whole board."
        actions={
          <span className="inline-flex items-center gap-2 text-[11.5px] text-muted-foreground">
            <span className="relative inline-flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[hsl(var(--accent-signal))] opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[hsl(var(--accent-signal))]" />
            </span>
            Agent ready
            <span className="mono-meta">{effectiveModel || "auto"}</span>
          </span>
        }
      />

      <form onSubmit={submit} className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-4">
          {/* Stage 1 — where the data lives ------------------------------- */}
          <StudioStage
            tag="source"
            title="Choose your data"
            hint={pickedLabel || undefined}
            done={hasSource}
          >
            {connections.isLoading || pipelines.isLoading ? (
              <div className="grid gap-2 sm:grid-cols-2">
                {[0, 1, 2, 3].map((i) => (
                  <div key={i} className="skel h-[52px]" />
                ))}
              </div>
            ) : dataConnections.length === 0 && (pipelines.data ?? []).length === 0 ? (
              <ConsoleEmptyState
                icon={DatabaseZap}
                title="No data to build from"
                body="Save a connection or run a pipeline first, then come back and the sources show up here."
                action={
                  <Link to="/app/connections">
                    <Button size="sm" variant="outline">Add a connection</Button>
                  </Link>
                }
              />
            ) : (
              <div className="space-y-4">
                {dataConnections.length > 0 && (
                  <div>
                    <p className="section-eyebrow mb-2">Connections</p>
                    <div className="grid gap-2 sm:grid-cols-2" role="listbox" aria-label="Connections">
                      {dataConnections.map((connection: any) => (
                        <SourceTile
                          key={connection.id}
                          icon={connection.source_type === "snowflake" ? Snowflake : connection.source_type === "postgres" ? Database : FileSpreadsheet}
                          name={connection.name}
                          detail={connection.source_type}
                          selected={String(connection.id) === connectionId}
                          onClick={() => pickConnection(connection)}
                        />
                      ))}
                    </div>
                  </div>
                )}

                {(pipelines.data ?? []).length > 0 && (
                  <div>
                    <p className="section-eyebrow mb-2">Pipelines</p>
                    <div className="grid gap-2 sm:grid-cols-2" role="listbox" aria-label="Pipelines">
                      {(pipelines.data ?? []).map((pipeline: any) => (
                        <SourceTile
                          key={pipeline.dag_id}
                          icon={Workflow}
                          name={pipeline.dag_id.replace(/^pipeline_/, "")}
                          detail={pipeline.table_name || "table from pipeline"}
                          selected={pipeline.dag_id === selectedPipeline}
                          onClick={() => pickPipeline(pipeline)}
                        />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </StudioStage>

          {/* Stage 2 — which table ---------------------------------------- */}
          <StudioStage
            tag="dataset"
            title={isPipelineSource ? "Confirm the table" : "Pick a table"}
            hint={datasetRef || undefined}
            done={hasDataset}
            locked={!hasSource}
            lockedReason="Choose a source above first."
          >
            {isPipelineSource ? (
              <div className="flex items-center gap-2.5 rounded-lg bg-muted/50 p-3">
                <Workflow className="h-4 w-4 shrink-0 text-[hsl(var(--accent-signal))]" />
                <div className="min-w-0">
                  <p className="mono-meta !text-[12.5px] !text-foreground">
                    {selectedPipelineObj?.table_name || selectedPipeline.replace(/^pipeline_/, "")}
                  </p>
                  <p className="field-hint !mt-0.5">Loaded by this pipeline. Nothing to choose.</p>
                </div>
              </div>
            ) : canListTables ? (
              <div className="space-y-2.5">
                {tables.isLoading ? (
                  <div className="skel h-9 w-full" />
                ) : tables.error ? (
                  <p className="field-hint !mt-0">
                    Couldn't list tables on this connection. Type the name below instead.
                  </p>
                ) : (
                  <div>
                    <label className="field-label" htmlFor="studio-table">Table</label>
                    <select
                      id="studio-table"
                      className="select-control"
                      value={(tables.data ?? []).includes(datasetRef) ? datasetRef : ""}
                      onChange={(e) => setDatasetRef(e.target.value)}
                    >
                      <option value="">
                        {(tables.data ?? []).length} tables found — pick one
                      </option>
                      {(tables.data ?? []).map((name: string) => (
                        <option key={name} value={name}>{name}</option>
                      ))}
                    </select>
                  </div>
                )}

                <details>
                  <summary className="meta-key cursor-pointer select-none hover:text-foreground">
                    Type a name or a query instead
                  </summary>
                  <Input
                    className="mt-2"
                    placeholder={isSnowflakeSource ? "Table name, or a full SELECT query…" : "Table name…"}
                    value={datasetRef}
                    onChange={(e) => setDatasetRef(e.target.value)}
                  />
                </details>
              </div>
            ) : (
              <div>
                <label className="field-label" htmlFor="studio-file">File name</label>
                <Input
                  id="studio-file"
                  placeholder="orders.csv"
                  value={datasetRef}
                  onChange={(e) => setDatasetRef(e.target.value)}
                />
                <p className="field-hint">
                  {selectedConnectionObj?.config?.base_path
                    ? `Relative to ${selectedConnectionObj.config.base_path}`
                    : "Relative to the connection's base folder."}
                </p>
              </div>
            )}
          </StudioStage>

          {/* Stage 3 — what you want -------------------------------------- */}
          <StudioStage
            tag="direction"
            title="Say what you want"
            hint={autoMode ? "agent decides" : "custom"}
            locked={!hasDataset}
            lockedReason="Pick a table above first."
          >
            <div className="space-y-4">
              <div>
                <label className="field-label" htmlFor="studio-name">Dashboard name</label>
                <Input
                  id="studio-name"
                  placeholder="Q3 revenue overview"
                  value={dashboardName}
                  onChange={(e) => setDashboardName(e.target.value)}
                />
              </div>

              <div>
                <label className="field-label" htmlFor="studio-prompt">
                  Direction <span className="font-normal text-muted-foreground">(optional)</span>
                </label>
                <textarea
                  id="studio-prompt"
                  className="min-h-[84px] w-full resize-y rounded-lg bg-background p-3 text-[13.5px] leading-6 text-foreground shadow-[inset_0_0_0_1px_hsl(var(--input))] outline-none transition placeholder:text-muted-foreground focus:shadow-[inset_0_0_0_1px_hsl(var(--accent-signal)),0_0_0_3px_hsl(var(--accent-signal)/0.15)]"
                  value={request}
                  onChange={(e) => setRequest(e.target.value)}
                  placeholder="Leave this blank and the agent profiles the data, picks the KPIs, chooses the chart types, and lays out the board itself."
                />

                <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                  <span className="meta-key">Add</span>
                  {ideas.map((idea) => (
                    <button
                      key={idea}
                      type="button"
                      onClick={() =>
                        setRequest((prev) => (prev.trim() ? `${prev.trim()} ${idea}` : idea))
                      }
                      className="chip transition hover:text-foreground"
                    >
                      {idea}
                    </button>
                  ))}
                </div>
              </div>

              <details>
                <summary className="meta-key cursor-pointer select-none hover:text-foreground">
                  Advanced — pick a model
                </summary>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <select
                    className="select-control !w-auto min-w-[240px]"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    aria-label="Model"
                  >
                    <option value="">Auto (recommended)</option>
                    {modelOptions
                      .filter((opt) => !opt.disabled)
                      .map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    <option value="custom">Custom…</option>
                  </select>
                  {model === "custom" && (
                    <Input
                      className="h-9 w-[200px]"
                      placeholder="exact model id"
                      value={customModel}
                      onChange={(e) => setCustomModel(e.target.value)}
                    />
                  )}
                </div>
              </details>

              <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
                <Button type="submit" disabled={analyze.isPending || !hasDataset} className="h-9">
                  {analyze.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : autoMode ? (
                    <Wand2 className="h-3.5 w-3.5" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5" />
                  )}
                  {analyze.isPending
                    ? "Building…"
                    : autoMode
                      ? "Auto-design dashboard"
                      : "Generate dashboard"}
                </Button>
                <span className="mono-meta hidden md:inline">⌘ ↵</span>
              </div>
            </div>
          </StudioStage>
        </div>

        <aside className="lg:sticky lg:top-24">
          <DatasetPreview
            connectionId={connectionId}
            table={datasetRef}
            supported={canListTables}
          />
        </aside>
      </form>

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
            {result?.error && (
              <div className="mt-2 rounded-md bg-red-50 p-3 text-[12px] text-red-700 dark:bg-red-950 dark:text-red-300">
                <p className="font-semibold">{result.error}</p>
                {result.existing_name && (
                  <p className="mt-1 text-red-600 dark:text-red-400">
                    A dashboard named "{result.existing_name}" already exists. Please use a different name.
                  </p>
                )}
              </div>
            )}
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
