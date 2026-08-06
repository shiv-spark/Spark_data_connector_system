import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChartNoAxesCombined, Search } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { fdt, fmtInt } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, RowSkeleton } from "@/components/console/Panel";

export const Metrics = () => {
  const [pipeline, setPipeline] = useState("");
  const [activePipeline, setActivePipeline] = useState("");

  const summary = useQuery({
    queryKey: ["metrics-summary"],
    queryFn: async () => (await api.get("/metrics/summary/all")).data.summary ?? [],
  });
  const details = useQuery({
    queryKey: ["metrics-detail", activePipeline],
    enabled: !!activePipeline,
    queryFn: async () => (await api.get(`/metrics/${activePipeline}`)).data,
  });

  const runs = details.data?.runs ?? [];
  const chartData = runs.slice().reverse().map((run: any, index: number) => ({
    run: index + 1,
    rows: run.rows_inserted ?? 0,
    duration: run.duration_sec ?? 0,
  }));

  return (
    <div className="space-y-5">
      <PageHeader
        icon={ChartNoAxesCombined}
        eyebrow="Observe"
        title="Metrics"
        description="Run counts, success rates, and throughput across every pipeline."
      />
      <Card>
        <CardHeader><CardTitle className="text-sm">Pipeline Drilldown</CardTitle></CardHeader>
        <CardContent>
          <form className="flex gap-3" onSubmit={(event) => { event.preventDefault(); setActivePipeline(pipeline.trim()); }}>
            <Input placeholder="Pipeline id or name" value={pipeline} onChange={(e) => setPipeline(e.target.value)} />
            <Button type="submit"><Search /> Load</Button>
          </form>
        </CardContent>
      </Card>

      {activePipeline && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader><CardTitle className="text-sm">Rows Inserted</CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid vertical={false} className="stroke-border dark:stroke-border" />
                  <XAxis dataKey="run" className="text-muted-foreground" />
                  <YAxis className="text-muted-foreground" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: "hsl(var(--popover))", 
                      color: "hsl(var(--popover-foreground))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)"
                    }}
                  />
                  <Bar dataKey="rows" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle className="text-sm">Duration Seconds</CardTitle></CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid vertical={false} className="stroke-border dark:stroke-border" />
                  <XAxis dataKey="run" className="text-muted-foreground" />
                  <YAxis className="text-muted-foreground" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: "hsl(var(--popover))", 
                      color: "hsl(var(--popover-foreground))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)"
                    }}
                  />
                  <Bar dataKey="duration" fill="hsl(var(--secondary))" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader><CardTitle className="text-sm">All Pipeline Summary</CardTitle></CardHeader>
        <CardContent>
          {summary.isLoading ? <RowSkeleton rows={3} /> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
                  <th className="py-3 pr-4">Pipeline</th><th className="py-3 pr-4">Connector</th><th className="py-3 pr-4">Runs</th><th className="py-3 pr-4">Rows</th><th className="py-3 pr-4">Avg duration</th><th className="py-3 pr-4">Success</th><th className="py-3 pr-4">Failed</th><th className="py-3 pr-4">Last run</th>
                </tr></thead>
                <tbody>
                  {(summary.data ?? []).map((row: any) => (
                    <tr key={`${row.pipeline_id}-${row.connector_type}`} className="border-b border-border">
                      <td className="py-3 pr-4 font-medium text-foreground">{row.pipeline_id}</td>
                      <td className="py-3 pr-4 text-foreground">{row.connector_type}</td>
                      <td className="py-3 pr-4 text-foreground">{row.total_runs}</td>
                      <td className="py-3 pr-4 text-foreground">{fmtInt(row.total_rows)}</td>
                      <td className="py-3 pr-4 text-foreground">{row.avg_duration_sec}s</td>
                      <td className="py-3 pr-4"><StatusBadge status={`${row.success_count} success`} /></td>
                      <td className="py-3 pr-4 text-foreground">{row.failed_count}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{fdt(row.last_run_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};



// import { useState } from "react";
// import { useQuery } from "@tanstack/react-query";
// import { ChartNoAxesCombined, Search } from "lucide-react";
// import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
// import { api } from "@/lib/api";
// import { Button } from "@/components/ui/button";
// import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
// import { Input } from "@/components/ui/input";
// import { fdt, fmtInt } from "@/lib/format";

// export const Metrics = () => {
//   const [pipeline, setPipeline] = useState("");
//   const [activePipeline, setActivePipeline] = useState("");

//   const summary = useQuery({
//     queryKey: ["metrics-summary"],
//     queryFn: async () => (await api.get("/metrics/summary/all")).data.summary ?? [],
//   });
//   const details = useQuery({
//     queryKey: ["metrics-detail", activePipeline],
//     enabled: !!activePipeline,
//     queryFn: async () => (await api.get(`/metrics/${activePipeline}`)).data,
//   });

//   const runs = details.data?.runs ?? [];
//   const chartData = runs.slice().reverse().map((run: any, index: number) => ({
//     run: index + 1,
//     rows: run.rows_inserted ?? 0,
//     duration: run.duration_sec ?? 0,
//   }));

//   // ── KPI summary calculations ──────────────────────────────────────────
//   const summaryRows = summary.data ?? [];
//   const totalPipelines = summaryRows.length;
//   const totalRuns = summaryRows.reduce((sum: number, r: any) => sum + Number(r.total_runs || 0), 0);
//   const totalSuccess = summaryRows.reduce((sum: number, r: any) => sum + Number(r.success_count || 0), 0);
//   const totalFailed = summaryRows.reduce((sum: number, r: any) => sum + Number(r.failed_count || 0), 0);
//   const overallSuccessRate = totalRuns ? Math.round((totalSuccess / totalRuns) * 1000) / 10 : 0;

//   const loadPipeline = (id: string) => {
//     setPipeline(id);
//     setActivePipeline(id);
//   };

//   return (
//     <div className="space-y-5">
//       <h2 className="h-section flex items-center gap-2 text-foreground"><ChartNoAxesCombined className="h-5 w-5" /> Metrics</h2>

//       {/* ── KPI summary cards ── */}
//       <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
//         <Card>
//           <CardContent className="pt-4">
//             <p className="text-xs font-medium uppercase text-muted-foreground">Pipelines</p>
//             <p className="mt-1 text-2xl font-bold text-foreground">{totalPipelines}</p>
//           </CardContent>
//         </Card>
//         <Card>
//           <CardContent className="pt-4">
//             <p className="text-xs font-medium uppercase text-muted-foreground">Total Runs</p>
//             <p className="mt-1 text-2xl font-bold text-foreground">{fmtInt(totalRuns)}</p>
//           </CardContent>
//         </Card>
//         <Card>
//           <CardContent className="pt-4">
//             <p className="text-xs font-medium uppercase text-muted-foreground">Success Rate</p>
//             <p className="mt-1 text-2xl font-bold text-emerald-600 dark:text-emerald-400">{overallSuccessRate}%</p>
//           </CardContent>
//         </Card>
//         <Card>
//           <CardContent className="pt-4">
//             <p className="text-xs font-medium uppercase text-muted-foreground">Failed Runs</p>
//             <p className="mt-1 text-2xl font-bold text-rose-600 dark:text-rose-400">{fmtInt(totalFailed)}</p>
//           </CardContent>
//         </Card>
//       </div>

//       <Card>
//         <CardHeader><CardTitle className="text-sm">Pipeline Drilldown</CardTitle></CardHeader>
//         <CardContent>
//           <form className="flex gap-3" onSubmit={(event) => { event.preventDefault(); setActivePipeline(pipeline.trim()); }}>
//             <Input placeholder="Pipeline id or name" value={pipeline} onChange={(e) => setPipeline(e.target.value)} />
//             <Button type="submit"><Search /> Load</Button>
//           </form>
//         </CardContent>
//       </Card>

//       {activePipeline && (
//         details.isLoading ? (
//           <p className="text-sm text-muted-foreground">Loading pipeline data…</p>
//         ) : runs.length === 0 ? (
//           <Card>
//             <CardContent className="py-8 text-center text-sm text-muted-foreground">
//               No runs found for "{activePipeline}". Check the pipeline name and try again.
//             </CardContent>
//           </Card>
//         ) : (
//           <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
//             <Card>
//               <CardHeader><CardTitle className="text-sm">Rows Inserted</CardTitle></CardHeader>
//               <CardContent>
//                 <ResponsiveContainer width="100%" height={260}>
//                   <BarChart data={chartData}>
//                     <CartesianGrid vertical={false} className="stroke-border dark:stroke-border" />
//                     <XAxis dataKey="run" className="text-muted-foreground" />
//                     <YAxis className="text-muted-foreground" />
//                     <Tooltip
//                       contentStyle={{
//                         backgroundColor: "hsl(var(--popover))",
//                         color: "hsl(var(--popover-foreground))",
//                         border: "1px solid hsl(var(--border))",
//                         borderRadius: "var(--radius)"
//                       }}
//                     />
//                     <Bar dataKey="rows" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
//                   </BarChart>
//                 </ResponsiveContainer>
//               </CardContent>
//             </Card>
//             <Card>
//               <CardHeader><CardTitle className="text-sm">Duration Seconds</CardTitle></CardHeader>
//               <CardContent>
//                 <ResponsiveContainer width="100%" height={260}>
//                   <BarChart data={chartData}>
//                     <CartesianGrid vertical={false} className="stroke-border dark:stroke-border" />
//                     <XAxis dataKey="run" className="text-muted-foreground" />
//                     <YAxis className="text-muted-foreground" />
//                     <Tooltip
//                       contentStyle={{
//                         backgroundColor: "hsl(var(--popover))",
//                         color: "hsl(var(--popover-foreground))",
//                         border: "1px solid hsl(var(--border))",
//                         borderRadius: "var(--radius)"
//                       }}
//                     />
//                     <Bar dataKey="duration" fill="hsl(var(--secondary))" radius={[4, 4, 0, 0]} />
//                   </BarChart>
//                 </ResponsiveContainer>
//               </CardContent>
//             </Card>
//           </div>
//         )
//       )}

//       <Card>
//         <CardHeader><CardTitle className="text-sm">All Pipeline Summary</CardTitle></CardHeader>
//         <CardContent>
//           {summary.isLoading ? (
//             <p className="text-sm text-muted-foreground">Loading metrics...</p>
//           ) : summaryRows.length === 0 ? (
//             <p className="text-sm text-muted-foreground">No pipeline metrics found yet. Run a pipeline to see data here.</p>
//           ) : (
//             <div className="overflow-x-auto">
//               <table className="w-full text-sm">
//                 <thead><tr className="border-b border-border text-left text-xs uppercase text-muted-foreground">
//                   <th className="py-3 pr-4">Pipeline</th><th className="py-3 pr-4">Connector</th><th className="py-3 pr-4">Runs</th><th className="py-3 pr-4">Rows</th><th className="py-3 pr-4">Avg duration</th><th className="py-3 pr-4">Success</th><th className="py-3 pr-4">Failed</th><th className="py-3 pr-4">Last run</th>
//                 </tr></thead>
//                 <tbody>
//                   {summaryRows.map((row: any) => (
//                     <tr key={`${row.pipeline_id}-${row.connector_type}`} className="border-b border-border transition hover:bg-muted/50">
//                       <td className="py-3 pr-4 font-medium text-foreground">
//                         <button
//                           type="button"
//                           onClick={() => loadPipeline(row.pipeline_id)}
//                           className="hover:text-emerald-700 hover:underline dark:hover:text-emerald-400"
//                         >
//                           {row.pipeline_id}
//                         </button>
//                       </td>
//                       <td className="py-3 pr-4 text-foreground">{row.connector_type}</td>
//                       <td className="py-3 pr-4 text-foreground">{row.total_runs}</td>
//                       <td className="py-3 pr-4 text-foreground">{fmtInt(row.total_rows)}</td>
//                       <td className="py-3 pr-4 text-foreground">{row.avg_duration_sec}s</td>
//                       <td className="py-3 pr-4">
//                         <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700 dark:bg-emerald-950 dark:text-emerald-400">
//                           {row.success_count}
//                         </span>
//                       </td>
//                       <td className="py-3 pr-4">
//                         {row.failed_count > 0 ? (
//                           <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 px-2 py-0.5 text-xs font-semibold text-rose-700 dark:bg-rose-950 dark:text-rose-400">
//                             {row.failed_count}
//                           </span>
//                         ) : (
//                           <span className="text-muted-foreground">0</span>
//                         )}
//                       </td>
//                       <td className="py-3 pr-4 text-muted-foreground">{fdt(row.last_run_at)}</td>
//                     </tr>
//                   ))}
//                 </tbody>
//               </table>
//             </div>
//           )}
//         </CardContent>
//       </Card>
//     </div>
//   );
// };