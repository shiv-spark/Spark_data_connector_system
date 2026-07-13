import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  Gauge,
  GitBranch,
  HardDrive,
  Rows3,
  ServerCog,
  Timer,
  Workflow,
  XCircle,
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  CartesianGrid,
} from "recharts";
import { api } from "@/lib/api";
import { Kpi } from "@/components/Kpi";
import { StatusBadge } from "@/components/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { fdt, fmtInt } from "@/lib/format";
import { cn } from "@/lib/utils";

const CLR = ["#2563eb", "#0891b2", "#059669", "#d97706", "#dc2626", "#7c3aed", "#db2777"];

type DashboardData = {
  metrics?: Record<string, number>;
  pipeline_health?: any[];
  daily?: { day: string; success?: number; failed?: number; skipped?: number; rows?: number }[];
  hourly?: any[];
  connectors?: { connector_type: string; runs: number }[];
  volume_trend?: { day: string; total_rows: number }[];
  recent_runs?: any[];
  top_failing?: any[];
  system_health?: string;
};

const fetchDashboard = async (): Promise<DashboardData> => {
  const r = await api.get("/dashboard/summary");
  return r.data;
};

const shortDate = (value: string) =>
  new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short" });

const chartText = {
  fill: "#64748b",
  fontSize: 12,
};

const EmptyChart = ({ label }: { label: string }) => (
  <div className="flex h-[260px] items-center justify-center rounded-md border border-dashed border-border bg-muted/50 text-sm text-muted-foreground">
    {label}
  </div>
);

const PanelTitle = ({ icon: Icon, title, detail }: { icon: typeof Activity; title: string; detail?: string }) => (
  <div className="flex items-center justify-between gap-3">
    <div className="flex items-center gap-2">
      <div className="flex h-8 w-8 items-center justify-center rounded-md bg-muted text-muted-foreground">
        <Icon className="h-4 w-4" />
      </div>
      <CardTitle className="text-sm text-foreground">{title}</CardTitle>
    </div>
    {detail ? <span className="text-xs font-medium text-muted-foreground">{detail}</span> : null}
  </div>
);

const PipelineFlow = ({ health }: { health: string }) => {
  const steps = [
    { label: "Sources", meta: "CSV / API / DB", icon: Database, tone: "text-cyan-600 dark:text-cyan-400" },
    { label: "Validate", meta: "Schema checks", icon: GitBranch, tone: "text-blue-600 dark:text-blue-400" },
    { label: "Transform", meta: "Quality rules", icon: ServerCog, tone: "text-violet-600 dark:text-violet-400" },
    { label: "Warehouse", meta: "Postgres load", icon: HardDrive, tone: "text-emerald-600 dark:text-emerald-400" },
  ];

  return (
    <Card className="figma-surface overflow-hidden">
      <CardContent className="p-0">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px]">
          <div className="relative min-h-[220px] p-5">
            <div className="absolute inset-x-10 top-[104px] hidden h-px bg-border md:block" />
            <div className="pipeline-flow-line hidden md:block" />
            <div className="relative grid grid-cols-1 gap-4 md:grid-cols-4">
              {steps.map(({ label, meta, icon: Icon, tone }, index) => (
                <div key={label} className="motion-card rounded-lg border border-border bg-card p-4 shadow-sm" style={{ animationDelay: `${index * 90}ms` }}>
                  <div className="mb-4 flex items-center justify-between">
                    <div className={cn("flex h-10 w-10 items-center justify-center rounded-md bg-muted", tone)}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <span className="text-xs font-semibold text-muted-foreground">0{index + 1}</span>
                  </div>
                  <p className="text-sm font-bold text-foreground">{label}</p>
                  <p className="mt-1 text-xs text-muted-foreground">{meta}</p>
                </div>
              ))}
            </div>
          </div>
          <div className="border-t border-border bg-slate-950 p-5 text-white lg:border-l lg:border-t-0 dark:bg-slate-900">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase text-slate-400">Automation state</p>
              <span className="live-ring" />
            </div>
            <p className="mt-6 text-3xl font-bold">{health}</p>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Pipelines are monitored continuously with live operational metrics, run history, failure tracking, and source-level visibility.
            </p>
            <div className="mt-6 grid grid-cols-2 gap-3">
              <div className="rounded-md border border-white/10 bg-white/5 p-3">
                <p className="text-xs text-slate-400">Refresh</p>
                <p className="mt-1 text-sm font-semibold">30 sec</p>
              </div>
              <div className="rounded-md border border-white/10 bg-white/5 p-3">
                <p className="text-xs text-slate-400">Mode</p>
                <p className="mt-1 text-sm font-semibold">Live</p>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export const Dashboard = () => {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: fetchDashboard,
    refetchInterval: 30_000,
  });

  const metrics = data?.metrics ?? {};
  const pipelines = data?.pipeline_health ?? [];
  const daily = data?.daily ?? [];
  const health = data?.system_health ?? "UNKNOWN";

  const totalRuns = metrics.total_runs || pipelines.reduce((sum, p) => sum + (p.total_runs ?? 0), 0);
  const success = metrics.success || pipelines.reduce((sum, p) => sum + (p.success ?? 0), 0);
  const failed = metrics.failed || pipelines.reduce((sum, p) => sum + (p.failed ?? 0), 0);
  const totalRows = metrics.total_rows || daily.reduce((sum, item) => sum + (item.rows ?? 0), 0);
  const rate = metrics.success_rate_pct ?? (totalRuns ? Math.round((success / totalRuns) * 1000) / 10 : 0);
  const failedRate = totalRuns ? Math.round((failed / totalRuns) * 1000) / 10 : 0;
  const avgDuration = metrics.avg_duration ?? 0;

  const healthTone = health === "HEALTHY" ? "text-emerald-600 dark:text-emerald-400" : health === "WARNING" ? "text-amber-600 dark:text-amber-400" : "text-rose-600 dark:text-rose-400";
  const healthColor = health === "HEALTHY" ? "#059669" : health === "WARNING" ? "#d97706" : health === "DEGRADED" ? "#dc2626" : "#64748b";

  const dailyChart = useMemo(
    () =>
      daily.map((item) => ({
        day: shortDate(item.day),
        success: item.success ?? 0,
        failed: item.failed ?? 0,
        skipped: item.skipped ?? 0,
      })),
    [daily],
  );

  const volumeChart = useMemo(
    () =>
      (data?.volume_trend ?? []).map((item) => ({
        day: shortDate(item.day),
        rows: item.total_rows,
      })),
    [data?.volume_trend],
  );

  const hourlyChart = useMemo(
    () =>
      (data?.hourly ?? []).map((item: any) => ({
        hour: new Date(item.hour).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
        success: item.success ?? 0,
        failed: item.failed ?? 0,
      })),
    [data?.hourly],
  );

  if (isLoading) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-28" />
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, index) => <Skeleton key={index} className="h-28" />)}
        </div>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => <Skeleton key={index} className="h-80" />)}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <Card className="border-rose-200 bg-rose-50 dark:border-rose-900/50 dark:bg-rose-950/50">
        <CardContent className="flex items-center gap-3 p-5 text-rose-700 dark:text-rose-400">
          <AlertTriangle className="h-5 w-5" />
          <span className="text-sm font-medium">Failed to load dashboard data.</span>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-border bg-card px-5 py-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-3 flex items-center gap-2">
              <span className={cn("flex h-2.5 w-2.5 rounded-full", healthTone.replace("text", "bg"))} />
              <span className="text-xs font-semibold uppercase text-muted-foreground">Data monitoring</span>
            </div>
            <h2 className="text-2xl font-bold text-foreground">Data Monitoring Dashboard</h2>
            <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
              Monitor ingested data health, pipeline runs, throughput, connector mix, failures, and recent activity from one control surface.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 rounded-lg border border-border bg-muted/50 p-3 text-center">
            <div className="min-w-24">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Health</p>
              <p className={cn("mt-1 text-sm font-bold", healthTone)}>{health}</p>
            </div>
            <div className="min-w-24 border-x border-border px-3">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Failure</p>
              <p className="mt-1 text-sm font-bold text-foreground">{failedRate}%</p>
            </div>
            <div className="min-w-24">
              <p className="text-xs font-semibold uppercase text-muted-foreground">Avg run</p>
              <p className="mt-1 text-sm font-bold text-foreground">{avgDuration}s</p>
            </div>
          </div>
        </div>
      </section>

      <PipelineFlow health={health} />

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi value={health} label="System Health" color={healthColor} icon={Gauge} detail="Live API summary" />
        <Kpi value={fmtInt(totalRuns)} label="Total Runs" icon={Workflow} detail="All tracked jobs" />
        <Kpi value={fmtInt(success)} label="Successful" color="#059669" icon={CheckCircle2} detail={`${rate}% success rate`} />
        <Kpi value={fmtInt(failed)} label="Failed" color="#dc2626" icon={XCircle} detail={`${failedRate}% failure rate`} />
        <Kpi value={`${rate}%`} label="Reliability" icon={Activity} detail="Completed successfully" />
        <Kpi value={fmtInt(totalRows)} label="Rows Loaded" color="#0891b2" icon={Rows3} detail="Rows processed" />
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <PanelTitle icon={Activity} title="Run Outcome Trend" detail="Last 7 days" />
          </CardHeader>
          <CardContent>
            {dailyChart.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={dailyChart}>
                  <CartesianGrid vertical={false} stroke="#e2e8f0" className="dark:stroke-slate-700" />
                  <XAxis dataKey="day" tick={chartText} tickLine={false} axisLine={false} />
                  <YAxis tick={chartText} tickLine={false} axisLine={false} />
                  <Tooltip cursor={{ fill: "#f1f5f9" }} contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }} />
                  <Legend />
                  <Bar dataKey="success" stackId="runs" fill="#059669" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="failed" stackId="runs" fill="#dc2626" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="skipped" stackId="runs" fill="#d97706" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart label="No run trend data yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <PanelTitle icon={Database} title="Connector Mix" detail="Runs by source" />
          </CardHeader>
          <CardContent>
            {(data?.connectors ?? []).length ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={data?.connectors ?? []}
                    dataKey="runs"
                    nameKey="connector_type"
                    outerRadius={92}
                    innerRadius={58}
                    paddingAngle={2}
                  >
                    {(data?.connectors ?? []).map((_, index) => (
                      <Cell key={index} fill={CLR[index % CLR.length]} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart label="No connector data yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <PanelTitle icon={Rows3} title="Row Volume" detail="30-day throughput" />
          </CardHeader>
          <CardContent>
            {volumeChart.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={volumeChart}>
                  <defs>
                    <linearGradient id="rowsFill" x1="0" x2="0" y1="0" y2="1">
                      <stop offset="5%" stopColor="#2563eb" stopOpacity={0.22} />
                      <stop offset="95%" stopColor="#2563eb" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid vertical={false} stroke="#e2e8f0" className="dark:stroke-slate-700" />
                  <XAxis dataKey="day" tick={chartText} tickLine={false} axisLine={false} />
                  <YAxis tick={chartText} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }} />
                  <Area type="monotone" dataKey="rows" stroke="#2563eb" strokeWidth={2} fill="url(#rowsFill)" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart label="No row volume data yet" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <PanelTitle icon={Timer} title="Hourly Activity" detail="Last 24 hours" />
          </CardHeader>
          <CardContent>
            {hourlyChart.length ? (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={hourlyChart}>
                  <CartesianGrid vertical={false} stroke="#e2e8f0" className="dark:stroke-slate-700" />
                  <XAxis dataKey="hour" tick={chartText} tickLine={false} axisLine={false} />
                  <YAxis tick={chartText} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }} />
                  <Legend />
                  <Area type="monotone" dataKey="success" stroke="#059669" strokeWidth={2} fill="#059669" fillOpacity={0.13} />
                  <Area type="monotone" dataKey="failed" stroke="#dc2626" strokeWidth={2} fill="#dc2626" fillOpacity={0.08} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <EmptyChart label="No hourly activity yet" />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_380px]">
        <Card>
          <CardHeader>
            <PanelTitle icon={Workflow} title="Pipeline Health" detail={`${pipelines.length} pipelines`} />
          </CardHeader>
          <CardContent>
            {pipelines.length === 0 ? (
              <p className="text-sm text-muted-foreground">No pipeline metrics found. Run a pipeline first.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
                      <th className="py-3 pr-4 font-semibold">Pipeline</th>
                      <th className="py-3 pr-4 font-semibold">Connector</th>
                      <th className="py-3 pr-4 font-semibold">Runs</th>
                      <th className="py-3 pr-4 font-semibold">Success</th>
                      <th className="py-3 pr-4 font-semibold">Last Status</th>
                      <th className="py-3 pr-4 font-semibold">Last Run</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pipelines.map((pipeline: any) => (
                      <tr key={pipeline.pipeline_id} className="border-b border-border last:border-0 hover:bg-muted/50">
                        <td className="max-w-[260px] truncate py-3 pr-4 font-medium text-foreground">{pipeline.pipeline_id}</td>
                        <td className="py-3 pr-4 text-muted-foreground">{pipeline.connector_type ?? "-"}</td>
                        <td className="py-3 pr-4 text-muted-foreground">{pipeline.total_runs}</td>
                        <td className="py-3 pr-4">
                          <div className="flex min-w-32 items-center gap-2">
                            <div className="h-2 flex-1 rounded-full bg-muted">
                              <div
                                className="h-2 rounded-full bg-emerald-600"
                                style={{ width: `${Math.min(Number(pipeline.success_rate ?? 0), 100)}%` }}
                              />
                            </div>
                            <span className="w-12 text-right text-xs font-semibold text-muted-foreground">
                              {pipeline.success_rate ?? "-"}%
                            </span>
                          </div>
                        </td>
                        <td className="py-3 pr-4"><StatusBadge status={pipeline.last_status} /></td>
                        <td className="py-3 pr-4 text-muted-foreground">{fdt(pipeline.last_run_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <PanelTitle icon={AlertTriangle} title="Top Failing" />
            </CardHeader>
            <CardContent className="space-y-3">
              {(data?.top_failing ?? []).length ? (
                (data?.top_failing ?? []).slice(0, 5).map((item: any) => (
                  <div key={item.pipeline_id} className="rounded-md border border-border bg-muted/50 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="truncate text-sm font-semibold text-foreground">{item.pipeline_id}</p>
                      <span className="rounded bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:bg-rose-900/50 dark:text-rose-400">
                        {item.fail_count ?? 0} fails
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">{item.last_error ?? "No error message captured"}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No recurring failures found.</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <PanelTitle icon={Activity} title="Recent Runs" />
            </CardHeader>
            <CardContent className="space-y-3">
              {(data?.recent_runs ?? []).length ? (
                (data?.recent_runs ?? []).slice(0, 6).map((run: any) => (
                  <div key={run.run_id ?? `${run.pipeline_id}-${run.logged_at}`} className="flex items-start justify-between gap-3 border-b border-border pb-3 last:border-0 last:pb-0">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground">{run.pipeline_id ?? run.connector_name ?? "Pipeline"}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{fmtInt(run.rows_inserted ?? run.records_count ?? 0)} rows / {run.duration_sec ?? 0}s</p>
                    </div>
                    <StatusBadge status={run.status} />
                  </div>
                ))
              ) : (
                <p className="text-sm text-muted-foreground">No recent runs available.</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};
