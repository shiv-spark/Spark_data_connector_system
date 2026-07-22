// import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
// import { useParams, Link } from "react-router-dom";
// import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
// import GridLayout, { type Layout, type LayoutItem } from "react-grid-layout";
// import Plotly from "plotly.js-dist-min";

// // Make it globally available so the embedded chart <script> tags
// // (which call Plotly.newPlot(...)) can find it as window.Plotly
// if (typeof window !== "undefined") {
//   (window as any).Plotly = Plotly;
// }
// const TypedGrid = GridLayout as unknown as React.ComponentType<any>;
// import {
//   ArrowLeft,
//   ArrowUpRight,
//   AreaChart as AreaChartIcon,
//   BarChart3,
//   Bot,
//   ChevronDown,
//   Code2,
//   Copy,
//   Eraser,
//   ExternalLink,
//   Gauge,
//   GripVertical,
//   LineChart as LineChartIcon,
//   Loader2,
//   Maximize2,
//   MessageSquarePlus,
//   Minimize2,
//   Palette,
//   Pencil,
//   PieChart as PieChartIcon,
//   Plus,
//   RefreshCw,
//   Send,
//   Sparkles,
//   Table2,
//   Trash2,
//   User,
//   Wand2,
//   X,
// } from "lucide-react";
// import { api, updateDashboardName, deleteDashboard } from "@/lib/api";
// import { cn } from "@/lib/utils";
// import { fdt } from "@/lib/format";

// const mono = { fontFamily: "var(--font-mono)" } as const;

// type ChartMeta = {
//   slot: number;
//   title: string;
//   description?: string;
//   source?: string;
//   layout?: { x: number; y: number; w: number; h: number };
// };

// type DashboardData = {
//   display_name?: string;
//   source_type?: string;
//   source_config?: { table_name?: string; pipeline_name?: string };
//   kpis?: Array<{ label: string; value: string | number; hint?: string }>;
//   charts?: Record<string, string>;
//   chart_meta?: ChartMeta[];
//   ai_summary?: string;
//   quality_result?: { quality_score?: number; grade?: string };
//   last_updated?: string;
// };

// const COLS = 12;
// const ROW_HEIGHT = 36;
// const DEFAULT_W = 6;
// const DEFAULT_H = 8;

// type ChatMessage = { role: "user" | "assistant"; content: string };

// const STARTERS = [
//   "Add a chart of revenue by month",
//   "Show top 5 categories by total",
//   "Find columns with the most outliers",
//   "Replace chart 1 with a line trend",
// ];

// export const DashboardEditor = () => {
//   const { dashboardId = "" } = useParams<{ dashboardId: string }>();
//   const queryClient = useQueryClient();
//   const [input, setInput] = useState("");
//   const [history, setHistory] = useState<ChatMessage[]>([]);
//   const chatScrollRef = useRef<HTMLDivElement>(null);

//   const dashboardKey = ["agent-dashboard", dashboardId];

//   const dashboard = useQuery({
//     queryKey: dashboardKey,
//     queryFn: async () => (await api.get(`/agent/dashboard/${dashboardId}/data`)).data as DashboardData,
//     enabled: !!dashboardId,
//   });

//   const meta = useQuery({
//     queryKey: ["agent-dashboards"],
//     queryFn: async () => (await api.get("/agent/dashboards")).data.dashboards ?? [],
//   });
//   const summary = useMemo(
//     () => (meta.data ?? []).find((d: any) => d.dashboard_id === dashboardId),
//     [meta.data, dashboardId],
//   );

//   const [isEditingName, setIsEditingName] = useState(false);
//   const [editingNameValue, setEditingNameValue] = useState("");
//   const [renameError, setRenameError] = useState<string | null>(null);

//   const renameMutation = useMutation({
//     mutationFn: (name: string) => updateDashboardName(dashboardId, name),
//     onSuccess: (data) => {
//       queryClient.setQueryData(dashboardKey, (old: DashboardData | undefined) => 
//         old ? { ...old, display_name: data.display_name } : old
//       );
//       queryClient.invalidateQueries({ queryKey: ["agent-dashboards"] });
//       setIsEditingName(false);
//       setRenameError(null);
//     },
//     onError: (err: any) => {
//       const detail = err?.response?.data?.detail;
//       if (detail?.error) {
//         setRenameError(detail.error);
//       } else {
//         setRenameError("Failed to rename dashboard");
//       }
//     },
//   });

//   const startEditingName = () => {
//     setEditingNameValue(data?.display_name || summary?.name || dashboardId);
//     setIsEditingName(true);
//     setRenameError(null);
//   };

//   const saveName = () => {
//     if (editingNameValue.trim()) {
//       renameMutation.mutate(editingNameValue.trim());
//     } else {
//       setIsEditingName(false);
//     }
//   };

//   const handleNameKeyDown = (e: React.KeyboardEvent) => {
//     if (e.key === "Enter") saveName();
//     if (e.key === "Escape") setIsEditingName(false);
//   };

//   const deleteMutation = useMutation({
//     mutationFn: () => deleteDashboard(dashboardId),
//     onSuccess: () => {
//       queryClient.invalidateQueries({ queryKey: ["agent-dashboards"] });
//       window.location.href = "/";
//     },
//   });

//   const command = useMutation({
//     mutationFn: async (message: string) => {
//       const r = await api.post(`/agent/dashboard/${dashboardId}/command`, { message });
//       return r.data as {
//         status: string;
//         reply?: string;
//         action?: "chart_update" | string;
//         slot?: number;
//         chart_meta?: ChartMeta[];
//       };
//     },
//     onSuccess: (data, message) => {
//       setHistory((h) => [
//         ...h,
//         { role: "user", content: message },
//         { role: "assistant", content: data.reply || (data.status === "SUCCESS" ? "Done." : "No reply") },
//       ]);
//       if (data.action === "chart_update") {
//         queryClient.invalidateQueries({ queryKey: dashboardKey });
//       }
//     },
//     onError: (err: any, message) => {
//       setHistory((h) => [
//         ...h,
//         { role: "user", content: message },
//         {
//           role: "assistant",
//           content: err?.response?.data?.detail || err?.message || "Something went wrong.",
//         },
//       ]);
//     },
//   });

//   const clearChat = useMutation({
//     mutationFn: async () => api.delete(`/agent/dashboard/${dashboardId}/chat`),
//     onSuccess: () => setHistory([]),
//   });

//   useEffect(() => {
//     chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
//   }, [history.length, command.isPending]);

//   const submit = (event: FormEvent) => {
//     event.preventDefault();
//     const text = input.trim();
//     if (!text || command.isPending) return;
//     setInput("");
//     command.mutate(text);
//   };

//   const data = dashboard.data;
//   const charts = data?.charts ?? {};
//   const chartMeta = data?.chart_meta ?? [];
//   const orderedSlots = chartMeta
//     .map((m) => m.slot)
//     .concat(
//       Object.keys(charts)
//         .map((k) => Number(k.replace("chart_", "")))
//         .filter((n) => !chartMeta.some((m) => m.slot === n)),
//     );
//   const score = Number(data?.quality_result?.quality_score ?? summary?.quality_score ?? 0);
//   const grade = data?.quality_result?.grade || summary?.grade || gradeFromScore(score);
//   const tone = score >= 80 ? "good" : score >= 60 ? "warn" : "bad";

//   const canvasRef = useRef<HTMLDivElement>(null);
//   const [canvasWidth, setCanvasWidth] = useState(1024);
//   useEffect(() => {
//     const el = canvasRef.current;
//     if (!el) return;
//     const ro = new ResizeObserver((entries) => {
//       for (const entry of entries) setCanvasWidth(Math.floor(entry.contentRect.width));
//     });
//     ro.observe(el);
//     setCanvasWidth(el.getBoundingClientRect().width);
//     return () => ro.disconnect();
//   }, []);

//   const layout: LayoutItem[] = useMemo(() => {
//     return orderedSlots.map((slot, i) => {
//       const m = chartMeta.find((cm) => cm.slot === slot);
//       const saved = m?.layout;
//       if (saved) {
//         return { i: String(slot), x: saved.x, y: saved.y, w: saved.w, h: saved.h };
//       }
//       const x = (i % 2) * DEFAULT_W;
//       const y = Math.floor(i / 2) * DEFAULT_H;
//       return { i: String(slot), x, y, w: DEFAULT_W, h: DEFAULT_H };
//     });
//   }, [orderedSlots.join(","), chartMeta]);

//   const persistLayout = useMutation({
//     mutationFn: async (next: Layout) => {
//       const payload = {
//         layout: next.map((l) => ({
//           slot: Number(l.i),
//           x: l.x,
//           y: l.y,
//           w: l.w,
//           h: l.h,
//         })),
//       };
//       await api.post(`/agent/dashboard/${dashboardId}/layout`, payload);
//     },
//   });

//   const deleteChart = useMutation({
//     mutationFn: async (slot: number) => {
//       await api.delete(`/agent/dashboard/${dashboardId}/chart/${slot}`);
//     },
//     onSuccess: () => queryClient.invalidateQueries({ queryKey: dashboardKey }),
//   });

//   const sourceTable = data?.source_config?.table_name || data?.source_config?.pipeline_name;
//   const isPostgres = (data?.source_type || summary?.source_type) === "postgres";
//   const sql = isPostgres && sourceTable ? `SELECT *\nFROM ${sourceTable}\nLIMIT 50;` : null;
//   const [sqlOpen, setSqlOpen] = useState(false);

//   return (
//     <div className="-mx-6 -my-6 grid h-[calc(100vh-56px)] grid-cols-[360px_1fr]">
//       {/* Chat rail */}
//       <aside className="flex h-full flex-col border-r border-border bg-background/80 backdrop-blur dark:border-border">
//         <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
//           <div className="flex items-center gap-2">
//             <span className="grid h-7 w-7 place-items-center rounded-md bg-gradient-to-br from-emerald-500 via-teal-500 to-emerald-700 text-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]">
//               <Bot className="h-3.5 w-3.5" />
//             </span>
//             <div className="leading-tight">
//               <p className="text-[12.5px] font-semibold tracking-tight text-foreground">Dashboard agent</p>
//               <p className="text-[10.5px] text-muted-foreground" style={mono}>
//               </p>
//             </div>
//           </div>
//           <button
//             type="button"
//             onClick={() => clearChat.mutate()}
//             className="icon-btn !h-7 !w-7"
//             title="Clear conversation"
//           >
//             <Eraser className="h-3.5 w-3.5" />
//           </button>
//         </div>

//         <div ref={chatScrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
//           {history.length === 0 ? (
//             <EmptyChat onPick={(s) => setInput(s)} />
//           ) : (
//             history.map((m, i) => <ChatBubble key={i} message={m} />)
//           )}
//           {command.isPending && (
//             <div className="flex items-center gap-2 text-[11.5px] text-muted-foreground">
//               <Loader2 className="h-3 w-3 animate-spin" /> agent thinking…
//             </div>
//           )}
//         </div>

//         <form
//           onSubmit={submit}
//           className="border-t border-border bg-background px-3 py-3"
//         >
//           <div className="rounded-[10px] border border-input bg-background shadow-[inset_0_1px_0_rgba(255,255,255,0.7),0_1px_2px_rgba(15,23,42,0.04)] focus-within:border-emerald-400 focus-within:ring-4 focus-within:ring-emerald-500/15 dark:border-input dark:focus-within:border-emerald-500">
//             <textarea
//               rows={2}
//               value={input}
//               onChange={(e) => setInput(e.target.value)}
//               onKeyDown={(e) => {
//                 if (e.key === "Enter" && !e.shiftKey) {
//                   e.preventDefault();
//                   submit(e as unknown as FormEvent);
//                 }
//               }}
//               className="w-full resize-none rounded-[10px] bg-transparent px-3 py-2 text-[13px] leading-5 text-foreground outline-none placeholder:text-muted-foreground"
//               placeholder="Ask, add a chart, refine a metric…"
//             />
//             <div className="flex items-center justify-between gap-2 border-t border-border px-2 py-1.5">
//               <span className="text-[10.5px] text-muted-foreground" style={mono}>
//                 ⌘ ↵ to send · Shift + ↵ for new line
//               </span>
//               <button
//                 type="submit"
//                 disabled={!input.trim() || command.isPending}
//                 className="inline-flex h-7 items-center gap-1.5 rounded-md bg-gradient-to-b from-emerald-500 to-emerald-600 px-2.5 text-[12px] font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),inset_0_0_0_1px_rgba(4,120,87,0.55),0_1px_2px_rgba(4,120,87,0.3)] transition hover:brightness-[1.06] disabled:opacity-50"
//               >
//                 {command.isPending ? (
//                   <Loader2 className="h-3 w-3 animate-spin" />
//                 ) : (
//                   <Send className="h-3 w-3" />
//                 )}
//                 Send
//               </button>
//             </div>
//           </div>
//         </form>
//       </aside>

//       {/* Canvas */}
//       <main className="flex h-full flex-col overflow-hidden">
//         <div className="flex items-center justify-between gap-3 border-b border-border bg-background/80 px-6 py-3 backdrop-blur">
//           <div className="flex items-center gap-3 min-w-0">
//             <Link
//               to="/"
//               className="icon-btn !h-7 !w-7"
//               title="Back to studio"
//             >
//               <ArrowLeft className="h-3.5 w-3.5" />
//             </Link>
//             <div className="min-w-0 flex items-center gap-2">
//               {isEditingName ? (
//                 <div className="flex flex-col gap-0.5">
//                   <input
//                     type="text"
//                     value={editingNameValue}
//                     onChange={(e) => { setEditingNameValue(e.target.value); setRenameError(null); }}
//                     onBlur={saveName}
//                     onKeyDown={handleNameKeyDown}
//                     autoFocus
//                     className="truncate text-[14px] font-semibold tracking-tight text-foreground bg-background border border-border rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-primary"
//                   />
//                   {renameError && (
//                     <p className="text-[11px] text-red-500">{renameError}</p>
//                   )}
//                 </div>
//               ) : (
//                 <p 
//                   className="truncate text-[14px] font-semibold tracking-tight text-foreground flex items-center gap-1.5 cursor-pointer hover:text-primary transition-colors"
//                   onClick={startEditingName}
//                   title="Click to rename"
//                 >
//                   {data?.display_name || summary?.name || dashboardId}
//                   <Pencil className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
//                 </p>
//               )}
//               <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
//                 <span className="rounded bg-muted px-1.5 py-0.5 font-medium text-muted-foreground">
//                   {data?.source_type || summary?.source_type || "—"}
//                 </span>
//                 <span className="text-muted-foreground/50">·</span>
//                 <span style={mono}>{fdt(data?.last_updated || summary?.last_updated)}</span>
//               </p>
//             </div>
//           </div>
//           <div className="flex items-center gap-2">
//             <button
//               type="button"
//               disabled={command.isPending}
//               onClick={() =>
//                 command.mutate(
//                   "Add one new chart that reveals the most insightful pattern in this data — pick the best chart type yourself and pick a metric we don't already visualize.",
//                 )
//               }
//               className="inline-flex h-8 items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 text-[12px] font-semibold text-emerald-800 shadow-[0_1px_0_rgba(15,23,42,0.04)] transition hover:bg-emerald-100 disabled:opacity-50 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200 dark:hover:bg-emerald-900"
//               title="Ask the agent to add a new chart"
//             >
//               {command.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
//               Add chart
//             </button>
//             <button
//               type="button"
//               onClick={() => dashboard.refetch()}
//               className="icon-btn !h-8 !w-8"
//               title="Refresh"
//             >
//               <RefreshCw className={cn("h-3.5 w-3.5", dashboard.isFetching && "animate-spin")} />
//             </button>
//             <button
//               type="button"
//               onClick={() => {
//                 if (window.confirm(`Delete dashboard "${data?.display_name || summary?.name || dashboardId}"?`)) {
//                   deleteMutation.mutate();
//                 }
//               }}
//               disabled={deleteMutation.isPending}
//               className="icon-btn !h-8 !w-8 text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
//               title="Delete dashboard"
//             >
//               {deleteMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
//             </button>
//             <span
//               className={cn(
//                 "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
//                 tone === "good" && "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800",
//                 tone === "warn" && "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-800",
//                 tone === "bad" && "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950 dark:text-rose-300 dark:ring-rose-800",
//               )}
//             >
//               <Gauge className="h-3 w-3" />
//               <span style={mono}>{score}</span>/100
//               <span className="text-muted-foreground">·</span>
//               <span style={mono}>{grade}</span>
//             </span>
//             {sql ? (
//               <button
//                 type="button"
//                 onClick={() => setSqlOpen((v) => !v)}
//                 className={cn(
//                   "inline-flex h-8 items-center gap-1 rounded-md border px-2.5 text-[12px] font-semibold transition",
//                   sqlOpen
//                     ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
//                     : "border-input bg-background text-foreground hover:border-border hover:text-foreground",
//                 )}
//               >
//                 <Code2 className="h-3 w-3" /> SQL
//               </button>
//             ) : null}
//             <a
//               href={`/api/agent/dashboard/${dashboardId}`}
//               target="_blank"
//               rel="noopener noreferrer"
//               className="inline-flex h-8 items-center gap-1 rounded-md border border-input bg-background px-2.5 text-[12px] font-semibold text-foreground shadow-[0_1px_0_rgba(15,23,42,0.04)] transition hover:border-border hover:text-foreground"
//             >
//               Published view <ExternalLink className="h-3 w-3" />
//             </a>
//           </div>
//         </div>

//         <div ref={canvasRef} className="flex-1 overflow-y-auto px-6 py-5">
//           {sql && sqlOpen ? <SqlPreview sql={sql} /> : null}
//           {dashboard.isLoading ? (
//             <CanvasSkeleton />
//           ) : dashboard.isError ? (
//             <CanvasError onRetry={() => dashboard.refetch()} />
//           ) : (
//             <>
//               {/* KPIs */}
//               {(data?.kpis ?? []).length > 0 && (
//                 <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
//                   {(data?.kpis ?? []).slice(0, 4).map((kpi, i) => (
//                     <div key={i} className="surface-tinted px-4 py-3">
//                       <div className="section-eyebrow">{kpi.label}</div>
//                       <div
//                         className="mt-1 text-[20px] font-semibold leading-none tracking-tight text-foreground"
//                         style={mono}
//                       >
//                         {String(kpi.value)}
//                       </div>
//                       {kpi.hint ? (
//                         <p className="mt-1 text-[11px] text-muted-foreground">{kpi.hint}</p>
//                       ) : null}
//                     </div>
//                   ))}
//                 </section>
//               )}

//               {/* Summary */}
//               {data?.ai_summary ? (
//                 <section className="mb-5 rounded-[10px] border border-border bg-gradient-to-b from-emerald-50/30 to-background px-4 py-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] dark:from-emerald-950/30 dark:to-background">
//                   <div className="mb-1 flex items-center gap-1.5">
//                     <Sparkles className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
//                     <span className="section-eyebrow">Agent summary</span>
//                   </div>
//                   <p className="text-[13px] leading-6 text-foreground">{data.ai_summary}</p>
//                 </section>
//               ) : null}

//               {/* Charts canvas — drag/resize grid */}
//               {orderedSlots.length === 0 ? (
//                 <CanvasEmpty />
//               ) : (
//                 <section className="-mx-1">
//                   <TypedGrid
//                     className="layout"
//                     layout={layout}
//                     cols={COLS}
//                     rowHeight={ROW_HEIGHT}
//                     width={canvasWidth - 16}
//                     margin={[12, 12]}
//                     containerPadding={[4, 4]}
//                     draggableHandle=".chart-drag-handle"
//                     compactType="vertical"
//                     onDragStop={(next: Layout) => persistLayout.mutate(next)}
//                     onResizeStop={(next: Layout) => persistLayout.mutate(next)}
//                   >
//                     {orderedSlots.map((slot) => {
//                       const html = charts[`chart_${slot}`];
//                       const m = chartMeta.find((cm) => cm.slot === slot);
//                       if (!html) return null;
//                       return (
//                         <div key={String(slot)}>
//                           <ChartCard
//                             slot={slot}
//                             html={html}
//                             meta={m}
//                             onDelete={() => deleteChart.mutate(slot)}
//                             deleting={deleteChart.isPending && deleteChart.variables === slot}
//                             onCommand={(text) => command.mutate(text)}
//                             busy={command.isPending}
//                           />
//                         </div>
//                       );
//                     })}
//                   </TypedGrid>
//                 </section>
//               )}
//             </>
//           )}
//         </div>
//       </main>
//     </div>
//   );
// };

// const CHART_TYPES: { id: string; label: string; icon: typeof BarChart3 }[] = [
//   { id: "bar", label: "Bar", icon: BarChart3 },
//   { id: "line", label: "Line", icon: LineChartIcon },
//   { id: "area", label: "Area", icon: AreaChartIcon },
//   { id: "pie", label: "Pie", icon: PieChartIcon },
//   { id: "donut", label: "Donut", icon: PieChartIcon },
//   { id: "table", label: "Table", icon: Table2 },
// ];

// const PALETTES: { id: string; label: string; swatch: string[] }[] = [
//   { id: "emerald", label: "Emerald", swatch: ["#10b981", "#0d9488", "#047857"] },
//   { id: "ocean", label: "Ocean", swatch: ["#0ea5e9", "#2563eb", "#1d4ed8"] },
//   { id: "violet", label: "Violet", swatch: ["#8b5cf6", "#7c3aed", "#5b21b6"] },
//   { id: "sunset", label: "Sunset", swatch: ["#f59e0b", "#f97316", "#dc2626"] },
//   { id: "mono", label: "Mono", swatch: ["#475569", "#334155", "#0f172a"] },
// ];

// // const ChartCanvasMount = ({ html, className }: { html: string; className?: string }) => {
// //   const ref = useRef<HTMLDivElement>(null);
// //   useEffect(() => {
// //     const el = ref.current;
// //     if (!el) return;
// //     el.innerHTML = html;
// //     const scripts = Array.from(el.querySelectorAll("script"));
// //     scripts.forEach((old) => {
// //       const next = document.createElement("script");
// //       Array.from(old.attributes).forEach((a) => next.setAttribute(a.name, a.value));
// //       next.text = old.text;
// //       old.parentNode?.replaceChild(next, old);
// //     });
// //   }, [html]);
// //   return <div ref={ref} className={className} />;
// // };
// const ChartCanvasMount = ({ html, className }: { html: string; className?: string }) => {
//   const ref = useRef<HTMLDivElement>(null);

//   // Mount HTML + re-execute embedded <script> tags (Plotly init script)
//   useEffect(() => {
//     const el = ref.current;
//     if (!el) return;
//     el.innerHTML = html;
//     const scripts = Array.from(el.querySelectorAll("script"));
//     scripts.forEach((old) => {
//       const next = document.createElement("script");
//       Array.from(old.attributes).forEach((a) => next.setAttribute(a.name, a.value));
//       next.text = old.text;
//       old.parentNode?.replaceChild(next, old);
//     });
//   }, [html]);

//   // Resize Plotly chart whenever the container size changes — needed
//   // because react-grid-layout resizes/drags cards without a window resize
//   // event, so Plotly's own auto-resize never fires.
//   useEffect(() => {
//     const el = ref.current;
//     if (!el) return;

//     const resizePlots = () => {
//       const plotDivs = el.querySelectorAll<HTMLElement>(".js-plotly-plot");
//       plotDivs.forEach((div) => {
//         // @ts-ignore — Plotly is loaded globally via the embedded script
//         if (window.Plotly && div) {
//           try {
//             // @ts-ignore
//             window.Plotly.Plots.resize(div);
//           } catch {
//             /* noop — chart may not be fully initialized yet */
//           }
//         }
//       });
//     };

//     const ro = new ResizeObserver(() => {
//       // Slight delay so Plotly's own render finishes before we resize it
//       requestAnimationFrame(resizePlots);
//     });
//     ro.observe(el);

//     // Also resize once right after mount, in case initial width was wrong
//     const initialTimer = setTimeout(resizePlots, 50);

//     return () => {
//       ro.disconnect();
//       clearTimeout(initialTimer);
//     };
//   }, [html]);

//   return <div ref={ref} className={className} />;
// };

// const ChartCard = ({
//   slot,
//   html,
//   meta,
//   onDelete,
//   deleting,
//   onCommand,
//   busy,
// }: {
//   slot: number;
//   html: string;
//   meta?: ChartMeta;
//   onDelete?: () => void;
//   deleting?: boolean;
//   onCommand: (text: string) => void;
//   busy?: boolean;
// }) => {
//   const [open, setOpen] = useState<null | "type" | "theme" | "refine">(null);
//   const [refineText, setRefineText] = useState("");
//   const [expanded, setExpanded] = useState(false);
//   const wrapRef = useRef<HTMLDivElement>(null);

//   useEffect(() => {
//     if (!open) return;
//     const close = (e: MouseEvent) => {
//       if (!wrapRef.current?.contains(e.target as Node)) setOpen(null);
//     };
//     document.addEventListener("mousedown", close);
//     return () => document.removeEventListener("mousedown", close);
//   }, [open]);

//   useEffect(() => {
//     if (!expanded) return;
//     const onKey = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false);
//     window.addEventListener("keydown", onKey);
//     return () => window.removeEventListener("keydown", onKey);
//   }, [expanded]);

//   const fire = (text: string) => {
//     setOpen(null);
//     onCommand(text);
//   };

//   const titleLabel = meta?.title || `Chart ${slot}`;

//   return (
//     <>
//       <div
//         ref={wrapRef}
//         className="group/card relative flex h-full flex-col overflow-hidden rounded-[14px] border border-border bg-card shadow-[0_1px_2px_rgba(15,23,42,0.04),0_4px_12px_-6px_rgba(15,23,42,0.06)] transition hover:-translate-y-px hover:border-border hover:shadow-[0_1px_2px_rgba(15,23,42,0.06),0_12px_28px_-12px_rgba(15,23,42,0.16)]"
//       >
//         {/* Top accent strip */}
//         <div
//           aria-hidden
//           className="pointer-events-none absolute inset-x-0 top-0 h-px"
//           style={{
//             background:
//               "linear-gradient(90deg, transparent 0%, rgba(16,185,129,0.55) 50%, transparent 100%)",
//           }}
//         />

//         {/* Header */}
//         <div className="chart-drag-handle flex cursor-move items-center justify-between gap-2 border-b border-border bg-gradient-to-b from-card to-muted/60 px-3 py-2 select-none">
//           <div className="flex min-w-0 items-center gap-1.5">
//             <GripVertical className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50 transition group-hover/card:text-muted-foreground" />
//             <div className="min-w-0">
//               <p className="truncate text-[13px] font-semibold tracking-tight text-foreground">
//                 {titleLabel}
//               </p>
//               {meta?.description ? (
//                 <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{meta.description}</p>
//               ) : null}
//             </div>
//           </div>
//           <div className="flex items-center gap-1">
//             <span
//               className="rounded bg-muted px-1.5 py-0.5 text-[10.5px] font-semibold text-muted-foreground"
//               style={mono}
//             >
//               #{slot}
//             </span>
//           </div>
//         </div>

//         {/* Hover toolbar */}
//         <div
//           onMouseDown={(e) => e.stopPropagation()}
//           className="absolute right-2.5 top-11 z-20 flex items-center gap-1 rounded-md border border-border bg-card/95 p-1 opacity-0 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_8px_24px_-12px_rgba(15,23,42,0.18)] backdrop-blur transition-opacity duration-150 group-hover/card:opacity-100 focus-within:opacity-100"
//         >
//           {/* Type popover */}
//           <ToolbarButton
//             label="Chart type"
//             active={open === "type"}
//             onClick={() => setOpen(open === "type" ? null : "type")}
//             icon={BarChart3}
//             chevron
//           />
//           {/* Theme popover */}
//           <ToolbarButton
//             label="Color palette"
//             active={open === "theme"}
//             onClick={() => setOpen(open === "theme" ? null : "theme")}
//             icon={Palette}
//             chevron
//           />
//           {/* Refine popover */}
//           <ToolbarButton
//             label="Refine with AI"
//             active={open === "refine"}
//             onClick={() => setOpen(open === "refine" ? null : "refine")}
//             icon={MessageSquarePlus}
//           />
//           <span className="mx-0.5 h-4 w-px bg-border" />
//           {/* Regenerate */}
//           <ToolbarButton
//             label="Regenerate"
//             disabled={busy}
//             onClick={() =>
//               fire(
//                 `Regenerate chart ${slot} from scratch — pick the best chart type and metric for the underlying data, keep the same intent as "${titleLabel}".`,
//               )
//             }
//             icon={Wand2}
//           />
//           {/* Expand */}
//           <ToolbarButton
//             label="Expand"
//             onClick={() => setExpanded(true)}
//             icon={Maximize2}
//           />
//           {/* Delete */}
//           {onDelete ? (
//             <ToolbarButton
//               label="Delete"
//               tone="danger"
//               disabled={deleting}
//               onClick={onDelete}
//               icon={deleting ? Loader2 : Trash2}
//               spinning={deleting}
//             />
//           ) : null}
//         </div>

//         {/* Popover panels */}
//         {open === "type" && (
//           <PopoverPanel>
//             <div className="grid grid-cols-3 gap-1.5">
//               {CHART_TYPES.map(({ id, label, icon: Icon }) => (
//                 <button
//                   key={id}
//                   type="button"
//                   disabled={busy}
//                   onClick={() =>
//                     fire(`Change chart ${slot} to a ${id} chart. Keep the same metric and grouping.`)
//                   }
//                   className="group/pill flex flex-col items-center gap-1 rounded-md border border-border bg-card px-2 py-2 text-[11px] font-medium text-foreground transition hover:-translate-y-px hover:border-emerald-300 hover:text-emerald-800 hover:shadow-sm disabled:opacity-50 dark:hover:border-emerald-700 dark:hover:text-emerald-200"
//                 >
//                   <Icon className="h-3.5 w-3.5 text-muted-foreground group-hover/pill:text-emerald-600 dark:group-hover/pill:text-emerald-400" />
//                   {label}
//                 </button>
//               ))}
//             </div>
//             <p className="mt-2 text-[10.5px] text-muted-foreground" style={mono}>
//               the agent re-renders the chart
//             </p>
//           </PopoverPanel>
//         )}

//         {open === "theme" && (
//           <PopoverPanel>
//             <div className="space-y-1">
//               {PALETTES.map(({ id, label, swatch }) => (
//                 <button
//                   key={id}
//                   type="button"
//                   disabled={busy}
//                   onClick={() =>
//                     fire(`Recolor chart ${slot} using a ${label} palette (${swatch.join(", ")}).`)
//                   }
//                   className="flex w-full items-center justify-between gap-2 rounded-md border border-transparent px-2 py-1.5 text-[12px] font-medium text-foreground transition hover:border-border hover:bg-muted disabled:opacity-50"
//                 >
//                   <span className="flex items-center gap-2">
//                     <span className="flex">
//                       {swatch.map((c) => (
//                         <span
//                           key={c}
//                           className="-ml-1 h-3.5 w-3.5 rounded-full ring-2 ring-background first:ml-0"
//                           style={{ background: c }}
//                         />
//                       ))}
//                     </span>
//                     {label}
//                   </span>
//                   <ArrowUpRight className="h-3 w-3 text-muted-foreground" />
//                 </button>
//               ))}
//             </div>
//           </PopoverPanel>
//         )}

//         {open === "refine" && (
//           <PopoverPanel wide>
//             <form
//               onSubmit={(e) => {
//                 e.preventDefault();
//                 const t = refineText.trim();
//                 if (!t) return;
//                 fire(`For chart ${slot} ("${titleLabel}"): ${t}`);
//                 setRefineText("");
//               }}
//               className="space-y-2"
//             >
//               <textarea
//                 autoFocus
//                 rows={3}
//                 value={refineText}
//                 onChange={(e) => setRefineText(e.target.value)}
//                 placeholder="e.g. group by quarter, sort descending, add a moving average…"
//                 className="w-full resize-none rounded-md border border-input bg-background px-2 py-1.5 text-[12.5px] leading-5 text-foreground outline-none placeholder:text-muted-foreground focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 dark:border-input dark:focus:border-emerald-500"
//               />
//               <div className="flex items-center justify-between gap-2">
//                 <span className="text-[10.5px] text-muted-foreground" style={mono}>
//                   refines this chart only
//                 </span>
//                 <button
//                   type="submit"
//                   disabled={busy || !refineText.trim()}
//                   className="inline-flex h-7 items-center gap-1.5 rounded-md bg-gradient-to-b from-emerald-500 to-emerald-600 px-2.5 text-[12px] font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),inset_0_0_0_1px_rgba(4,120,87,0.55),0_1px_2px_rgba(4,120,87,0.3)] transition hover:brightness-[1.06] disabled:opacity-50"
//                 >
//                   <Sparkles className="h-3 w-3" />
//                   Apply
//                 </button>
//               </div>
//             </form>
//           </PopoverPanel>
//         )}

//         {/* Chart body */}
//         <ChartCanvasMount
//           html={html}
//           className="flex-1 w-full overflow-hidden p-2 [&_*]:max-w-full"
//         />
//       </div>

//       {/* Fullscreen overlay */}
//       {expanded && (
//         <div
//           className="fixed inset-0 z-50 flex items-center justify-center bg-background/40 p-6 backdrop-blur-sm"
//           onClick={() => setExpanded(false)}
//         >
//           <div
//             className="relative flex h-full max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-[14px] border border-border bg-card shadow-2xl"
//             onClick={(e) => e.stopPropagation()}
//           >
//             <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3">
//               <div className="min-w-0">
//                 <p className="truncate text-[14px] font-semibold tracking-tight text-foreground">
//                   {titleLabel}
//                 </p>
//                 {meta?.description ? (
//                   <p className="mt-0.5 truncate text-[11.5px] text-muted-foreground">
//                     {meta.description}
//                   </p>
//                 ) : null}
//               </div>
//               <button
//                 type="button"
//                 onClick={() => setExpanded(false)}
//                 className="icon-btn !h-8 !w-8"
//                 title="Close (Esc)"
//               >
//                 <X className="h-4 w-4" />
//               </button>
//             </div>
//             <ChartCanvasMount
//               html={html}
//               className="flex-1 w-full overflow-auto p-4 [&_*]:max-w-full"
//             />
//             <div className="flex items-center justify-end gap-1.5 border-t border-border bg-muted/60 px-3 py-2">
//               <button
//                 type="button"
//                 onClick={() => setExpanded(false)}
//                 className="inline-flex h-7 items-center gap-1 rounded-md border border-border bg-card px-2.5 text-[12px] font-semibold text-foreground hover:border-border"
//               >
//                 <Minimize2 className="h-3 w-3" /> Collapse
//               </button>
//             </div>
//           </div>
//         </div>
//       )}
//     </>
//   );
// };

// const ToolbarButton = ({
//   label,
//   icon: Icon,
//   onClick,
//   disabled,
//   active,
//   tone,
//   chevron,
//   spinning,
// }: {
//   label: string;
//   icon: typeof BarChart3;
//   onClick?: () => void;
//   disabled?: boolean;
//   active?: boolean;
//   tone?: "danger";
//   chevron?: boolean;
//   spinning?: boolean;
// }) => (
//   <button
//     type="button"
//     title={label}
//     aria-label={label}
//     disabled={disabled}
//     onClick={(e) => {
//       e.stopPropagation();
//       onClick?.();
//     }}
//     className={cn(
//       "inline-flex h-6 items-center gap-0.5 rounded px-1.5 text-[11px] font-medium transition",
//       "text-muted-foreground hover:bg-muted hover:text-foreground",
//       active && "bg-foreground text-background hover:bg-foreground hover:text-background",
//       tone === "danger" && "hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950 dark:hover:text-rose-400",
//       disabled && "opacity-50",
//     )}
//   >
//     <Icon className={cn("h-3 w-3", spinning && "animate-spin")} />
//     {chevron ? <ChevronDown className="h-2.5 w-2.5 opacity-70" /> : null}
//   </button>
// );

// const PopoverPanel = ({
//   children,
//   wide = false,
// }: {
//   children: React.ReactNode;
//   wide?: boolean;
// }) => (
//   <div
//     onMouseDown={(e) => e.stopPropagation()}
//     className={cn(
//       "absolute right-2.5 top-[78px] z-30 rounded-[10px] border border-border bg-card p-2 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_12px_32px_-12px_rgba(15,23,42,0.22)]",
//       wide ? "w-[320px]" : "w-[220px]",
//     )}
//   >
//     {children}
//   </div>
// );

// const SqlPreview = ({ sql }: { sql: string }) => {
//   const [copied, setCopied] = useState(false);
//   const copy = async () => {
//     try {
//       await navigator.clipboard.writeText(sql);
//       setCopied(true);
//       setTimeout(() => setCopied(false), 1200);
//     } catch {
//       /* noop */
//     }
//   };
//   return (
//     <section className="mb-5 overflow-hidden rounded-[10px] border border-border bg-card shadow-[0_1px_2px_rgba(15,23,42,0.06),0_4px_12px_-6px_rgba(15,23,42,0.18)]">
//       <div className="flex items-center justify-between border-b border-border px-3 py-2">
//         <div className="flex items-center gap-1.5">
//           <Code2 className="h-3.5 w-3.5 text-emerald-400" />
//           <span
//             className="text-[10.5px] font-semibold uppercase tracking-[0.16em] text-emerald-300"
//             style={mono}
//           >
//             Source SQL · readonly
//           </span>
//         </div>
//         <button
//           type="button"
//           onClick={copy}
//           className="inline-flex h-6 items-center gap-1 rounded bg-muted px-1.5 text-[11px] font-medium text-muted-foreground transition hover:bg-muted/80"
//         >
//           <Copy className="h-3 w-3" /> {copied ? "Copied" : "Copy"}
//         </button>
//       </div>
//       <pre
//         className="overflow-x-auto px-3 py-3 text-[12px] leading-5 text-emerald-100"
//         style={mono}
//       >
//         {sql}
//       </pre>
//     </section>
//   );
// };

// const ChatBubble = ({ message }: { message: ChatMessage }) => {
//   const isUser = message.role === "user";
//   return (
//     <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
//       <span
//         className={cn(
//           "mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full ring-1 ring-inset",
//           isUser
//             ? "bg-muted text-muted-foreground ring-border"
//             : "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800",
//         )}
//       >
//         {isUser ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
//       </span>
//       <div
//         className={cn(
//           "max-w-[78%] rounded-[10px] px-3 py-2 text-[12.5px] leading-5 ring-1 ring-inset",
//           isUser
//             ? "bg-muted text-foreground ring-border"
//             : "bg-card text-foreground ring-border shadow-[0_1px_0_rgba(15,23,42,0.03)]",
//         )}
//       >
//         {message.content}
//       </div>
//     </div>
//   );
// };

// const EmptyChat = ({ onPick }: { onPick: (s: string) => void }) => (
//   <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
//     <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-50 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950 dark:ring-emerald-800">
//       <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
//     </div>
//     <p className="text-[13px] font-semibold text-foreground">Refine your dashboard</p>
//     <p className="max-w-[260px] text-[11.5px] text-muted-foreground">
//       Ask the agent to add charts, replace metrics, explain anomalies — all in plain English.
//     </p>
//     <div className="mt-1 flex w-full flex-col gap-1.5">
//       {STARTERS.map((s) => (
//         <button
//           key={s}
//           type="button"
//           onClick={() => onPick(s)}
//           className="inline-flex items-center justify-between gap-2 rounded-md border border-border bg-card px-2.5 py-1.5 text-left text-[12px] text-foreground transition hover:border-border"
//         >
//           <span className="truncate">{s}</span>
//           <ArrowUpRight className="h-3 w-3 text-muted-foreground" />
//         </button>
//       ))}
//     </div>
//   </div>
// );

// const CanvasSkeleton = () => (
//   <div className="space-y-4">
//     <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
//       {Array.from({ length: 4 }).map((_, i) => (
//         <div key={i} className="h-[68px] animate-pulse rounded-[10px] bg-muted" />
//       ))}
//     </div>
//     <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
//       {Array.from({ length: 4 }).map((_, i) => (
//         <div key={i} className="h-[280px] animate-pulse rounded-[12px] bg-muted" />
//       ))}
//     </div>
//   </div>
// );

// const CanvasError = ({ onRetry }: { onRetry: () => void }) => (
//   <div className="flex flex-col items-center justify-center gap-3 rounded-[12px] border border-rose-200 bg-rose-50/40 px-6 py-12 text-center dark:border-rose-800 dark:bg-rose-950/40">
//     <p className="text-[13px] font-semibold text-rose-800 dark:text-rose-300">Couldn't load this dashboard</p>
//     <button
//       type="button"
//       onClick={onRetry}
//       className="inline-flex h-8 items-center gap-1.5 rounded-md bg-card px-3 text-[12px] font-semibold text-foreground ring-1 ring-inset ring-border hover:ring-border"
//     >
//       Try again
//     </button>
//   </div>
// );

// const CanvasEmpty = () => (
//   <div className="flex flex-col items-center justify-center gap-2 rounded-[12px] border border-dashed border-border bg-muted/40 px-6 py-16 text-center">
//     <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-50 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950 dark:ring-emerald-800">
//       <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
//     </div>
//     <p className="text-[13px] font-semibold text-foreground">No charts yet</p>
//     <p className="max-w-xs text-[11.5px] text-muted-foreground">
//       Ask the agent on the left to add the first chart.
//     </p>
//   </div>
// );

// const gradeFromScore = (score: number) => {
//   if (score >= 90) return "A";
//   if (score >= 80) return "B";
//   if (score >= 70) return "C";
//   if (score >= 60) return "D";
//   return "F";
// };




import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import GridLayout, { type Layout, type LayoutItem } from "react-grid-layout";
import Plotly from "plotly.js-dist-min";

// Make it globally available so the embedded chart <script> tags
// (which call Plotly.newPlot(...)) can find it as window.Plotly
if (typeof window !== "undefined") {
  (window as any).Plotly = Plotly;
}
const TypedGrid = GridLayout as unknown as React.ComponentType<any>;
import {
  ArrowLeft,
  ArrowUpRight,
  AreaChart as AreaChartIcon,
  BarChart3,
  Bot,
  ChevronDown,
  Code2,
  Copy,
  Eraser,
  ExternalLink,
  Gauge,
  GripVertical,
  LineChart as LineChartIcon,
  Loader2,
  Maximize2,
  PanelRightClose,
  PanelRightOpen,
  MessageSquarePlus,
  Minimize2,
  Palette,
  Pencil,
  PieChart as PieChartIcon,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Table2,
  Trash2,
  User,
  Wand2,
  X,
} from "lucide-react";
import { api, updateDashboardName, deleteDashboard } from "@/lib/api";
import { cn } from "@/lib/utils";
import { fdt } from "@/lib/format";

const mono = { fontFamily: "var(--font-mono)" } as const;

type ChartMeta = {
  slot: number;
  title: string;
  description?: string;
  source?: string;
  layout?: { x: number; y: number; w: number; h: number };
};

type DashboardData = {
  display_name?: string;
  source_type?: string;
  source_config?: { table_name?: string; pipeline_name?: string };
  kpis?: Array<{ label: string; value: string | number; hint?: string }>;
  charts?: Record<string, string>;
  chart_meta?: ChartMeta[];
  ai_summary?: string;
  quality_result?: { quality_score?: number; grade?: string };
  last_updated?: string;
};

const COLS = 12;
const ROW_HEIGHT = 36;
const DEFAULT_W = 6;
const DEFAULT_H = 8;

type ChatMessage = { role: "user" | "assistant"; content: string };

const STARTERS = [
  "Add a chart of revenue by month",
  "Show top 5 categories by total",
  "Find columns with the most outliers",
  "Replace chart 1 with a line trend",
];

export const DashboardEditor = () => {
  const { dashboardId = "" } = useParams<{ dashboardId: string }>();
  const queryClient = useQueryClient();
  const [input, setInput] = useState("");
  const [chatVisible, setChatVisible] = useState(true);
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const chatScrollRef = useRef<HTMLDivElement>(null);

  const dashboardKey = ["agent-dashboard", dashboardId];

  const dashboard = useQuery({
    queryKey: dashboardKey,
    queryFn: async () => (await api.get(`/agent/dashboard/${dashboardId}/data`)).data as DashboardData,
    enabled: !!dashboardId,
  });

  const meta = useQuery({
    queryKey: ["agent-dashboards"],
    queryFn: async () => (await api.get("/agent/dashboards")).data.dashboards ?? [],
  });
  const summary = useMemo(
    () => (meta.data ?? []).find((d: any) => d.dashboard_id === dashboardId),
    [meta.data, dashboardId],
  );

  const [isEditingName, setIsEditingName] = useState(false);
  const [editingNameValue, setEditingNameValue] = useState("");
  const [renameError, setRenameError] = useState<string | null>(null);

  const renameMutation = useMutation({
    mutationFn: (name: string) => updateDashboardName(dashboardId, name),
    onSuccess: (data) => {
      queryClient.setQueryData(dashboardKey, (old: DashboardData | undefined) => 
        old ? { ...old, display_name: data.display_name } : old
      );
      queryClient.invalidateQueries({ queryKey: ["agent-dashboards"] });
      setIsEditingName(false);
      setRenameError(null);
    },
    onError: (err: any) => {
      const detail = err?.response?.data?.detail;
      if (detail?.error) {
        setRenameError(detail.error);
      } else {
        setRenameError("Failed to rename dashboard");
      }
    },
  });

  const startEditingName = () => {
    setEditingNameValue(data?.display_name || summary?.name || dashboardId);
    setIsEditingName(true);
    setRenameError(null);
  };

  const saveName = () => {
    if (editingNameValue.trim()) {
      renameMutation.mutate(editingNameValue.trim());
    } else {
      setIsEditingName(false);
    }
  };

  const handleNameKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") saveName();
    if (e.key === "Escape") setIsEditingName(false);
  };

  const deleteMutation = useMutation({
    mutationFn: () => deleteDashboard(dashboardId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["agent-dashboards"] });
      window.location.href = "/";
    },
  });

  const command = useMutation({
    mutationFn: async (message: string) => {
      const r = await api.post(`/agent/dashboard/${dashboardId}/command`, { message });
      return r.data as {
        status: string;
        reply?: string;
        action?: "chart_update" | string;
        slot?: number;
        chart_meta?: ChartMeta[];
      };
    },
    onSuccess: (data, message) => {
      setHistory((h) => [
        ...h,
        { role: "user", content: message },
        { role: "assistant", content: data.reply || (data.status === "SUCCESS" ? "Done." : "No reply") },
      ]);
      if (data.action === "chart_update") {
        queryClient.invalidateQueries({ queryKey: dashboardKey });
      }
    },
    onError: (err: any, message) => {
      setHistory((h) => [
        ...h,
        { role: "user", content: message },
        {
          role: "assistant",
          content: err?.response?.data?.detail || err?.message || "Something went wrong.",
        },
      ]);
    },
  });

  const clearChat = useMutation({
    mutationFn: async () => api.delete(`/agent/dashboard/${dashboardId}/chat`),
    onSuccess: () => setHistory([]),
  });

  useEffect(() => {
    chatScrollRef.current?.scrollTo({ top: chatScrollRef.current.scrollHeight, behavior: "smooth" });
  }, [history.length, command.isPending]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const text = input.trim();
    if (!text || command.isPending) return;
    setInput("");
    command.mutate(text);
  };

  const data = dashboard.data;
  const charts = data?.charts ?? {};
  const chartMeta = data?.chart_meta ?? [];
  const orderedSlots = chartMeta
    .map((m) => m.slot)
    .concat(
      Object.keys(charts)
        .map((k) => Number(k.replace("chart_", "")))
        .filter((n) => !chartMeta.some((m) => m.slot === n)),
    );
  const score = Number(data?.quality_result?.quality_score ?? summary?.quality_score ?? 0);
  const grade = data?.quality_result?.grade || summary?.grade || gradeFromScore(score);
  const tone = score >= 80 ? "good" : score >= 60 ? "warn" : "bad";

  const canvasRef = useRef<HTMLDivElement>(null);
  const [canvasWidth, setCanvasWidth] = useState(1024);
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) setCanvasWidth(Math.floor(entry.contentRect.width));
    });
    ro.observe(el);
    setCanvasWidth(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  const layout: LayoutItem[] = useMemo(() => {
    return orderedSlots.map((slot, i) => {
      const m = chartMeta.find((cm) => cm.slot === slot);
      const saved = m?.layout;
      if (saved) {
        return { i: String(slot), x: saved.x, y: saved.y, w: saved.w, h: saved.h };
      }
      const x = (i % 2) * DEFAULT_W;
      const y = Math.floor(i / 2) * DEFAULT_H;
      return { i: String(slot), x, y, w: DEFAULT_W, h: DEFAULT_H };
    });
  }, [orderedSlots.join(","), chartMeta]);

  const persistLayout = useMutation({
    mutationFn: async (next: Layout) => {
      const payload = {
        layout: next.map((l) => ({
          slot: Number(l.i),
          x: l.x,
          y: l.y,
          w: l.w,
          h: l.h,
        })),
      };
      await api.post(`/agent/dashboard/${dashboardId}/layout`, payload);
    },
  });

  const deleteChart = useMutation({
    mutationFn: async (slot: number) => {
      await api.delete(`/agent/dashboard/${dashboardId}/chart/${slot}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: dashboardKey }),
  });

  const sourceTable = data?.source_config?.table_name || data?.source_config?.pipeline_name;
  const isPostgres = (data?.source_type || summary?.source_type) === "postgres";
  const sql = isPostgres && sourceTable ? `SELECT *\nFROM ${sourceTable}\nLIMIT 50;` : null;
  const [sqlOpen, setSqlOpen] = useState(false);

  return (
    <div className={cn("-mx-6 -my-6 grid h-[calc(100vh-56px)]", chatVisible ? "grid-cols-[360px_1fr]" : "grid-cols-[0px_1fr]")}>
      {/* Chat rail */}
      <aside className={cn("flex h-full flex-col border-r border-border bg-background/80 backdrop-blur dark:border-border overflow-hidden transition-all duration-200", !chatVisible && "border-r-0")}>
        <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="grid h-7 w-7 place-items-center rounded-md bg-gradient-to-br from-emerald-500 via-teal-500 to-emerald-700 text-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]">
              <Bot className="h-3.5 w-3.5" />
            </span>
            <div className="leading-tight">
              <p className="text-[12.5px] font-semibold tracking-tight text-foreground">Dashboard agent</p>
              <p className="text-[10.5px] text-muted-foreground" style={mono}>
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => clearChat.mutate()}
            className="icon-btn !h-7 !w-7"
            title="Clear conversation"
          >
            <Eraser className="h-3.5 w-3.5" />
          </button>
        </div>

        <div ref={chatScrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
          {history.length === 0 ? (
            <EmptyChat onPick={(s) => setInput(s)} />
          ) : (
            history.map((m, i) => <ChatBubble key={i} message={m} />)
          )}
          {command.isPending && (
            <div className="flex items-center gap-2 text-[11.5px] text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> agent thinking…
            </div>
          )}
        </div>

        <form
          onSubmit={submit}
          className="border-t border-border bg-background px-3 py-3"
        >
          <div className="rounded-[10px] border border-input bg-background shadow-[inset_0_1px_0_rgba(255,255,255,0.7),0_1px_2px_rgba(15,23,42,0.04)] focus-within:border-emerald-400 focus-within:ring-4 focus-within:ring-emerald-500/15 dark:border-input dark:focus-within:border-emerald-500">
            <textarea
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit(e as unknown as FormEvent);
                }
              }}
              className="w-full resize-none rounded-[10px] bg-transparent px-3 py-2 text-[13px] leading-5 text-foreground outline-none placeholder:text-muted-foreground"
              placeholder="Ask, add a chart, refine a metric…"
            />
            <div className="flex items-center justify-between gap-2 border-t border-border px-2 py-1.5">
              <span className="text-[10.5px] text-muted-foreground" style={mono}>
                ⌘ ↵ to send · Shift + ↵ for new line
              </span>
              <button
                type="submit"
                disabled={!input.trim() || command.isPending}
                className="inline-flex h-7 items-center gap-1.5 rounded-md bg-gradient-to-b from-emerald-500 to-emerald-600 px-2.5 text-[12px] font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),inset_0_0_0_1px_rgba(4,120,87,0.55),0_1px_2px_rgba(4,120,87,0.3)] transition hover:brightness-[1.06] disabled:opacity-50"
              >
                {command.isPending ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Send className="h-3 w-3" />
                )}
                Send
              </button>
            </div>
          </div>
        </form>
      </aside>

      {/* Canvas */}
      <main className="flex h-full flex-col overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-border bg-background/80 px-6 py-3 backdrop-blur">
          <div className="flex items-center gap-3 min-w-0">
            <Link
              to="/"
              className="icon-btn !h-7 !w-7"
              title="Back to studio"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
            </Link>
            <div className="min-w-0 flex items-center gap-2">
              {isEditingName ? (
                <div className="flex flex-col gap-0.5">
                  <input
                    type="text"
                    value={editingNameValue}
                    onChange={(e) => { setEditingNameValue(e.target.value); setRenameError(null); }}
                    onBlur={saveName}
                    onKeyDown={handleNameKeyDown}
                    autoFocus
                    className="truncate text-[14px] font-semibold tracking-tight text-foreground bg-background border border-border rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  {renameError && (
                    <p className="text-[11px] text-red-500">{renameError}</p>
                  )}
                </div>
              ) : (
                <p 
                  className="truncate text-[14px] font-semibold tracking-tight text-foreground flex items-center gap-1.5 cursor-pointer hover:text-primary transition-colors"
                  onClick={startEditingName}
                  title="Click to rename"
                >
                  {data?.display_name || summary?.name || dashboardId}
                  <Pencil className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                </p>
              )}
              <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <span className="rounded bg-muted px-1.5 py-0.5 font-medium text-muted-foreground">
                  {data?.source_type || summary?.source_type || "—"}
                </span>
                <span className="text-muted-foreground/50">·</span>
                <span style={mono}>{fdt(data?.last_updated || summary?.last_updated)}</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setChatVisible((v) => !v)}
              className="icon-btn !h-8 !w-8"
              title={chatVisible ? "Hide dashboard agent" : "Show dashboard agent"}
            >
              {chatVisible ? <PanelRightClose className="h-3.5 w-3.5" /> : <PanelRightOpen className="h-3.5 w-3.5" />}
            </button>
            <button
              type="button"
              disabled={command.isPending}
              onClick={() =>
                command.mutate(
                  "Add one new chart that reveals the most insightful pattern in this data — pick the best chart type yourself and pick a metric we don't already visualize.",
                )
              }
              className="inline-flex h-8 items-center gap-1.5 rounded-md border border-emerald-200 bg-emerald-50 px-2.5 text-[12px] font-semibold text-emerald-800 shadow-[0_1px_0_rgba(15,23,42,0.04)] transition hover:bg-emerald-100 disabled:opacity-50 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-200 dark:hover:bg-emerald-900"
              title="Ask the agent to add a new chart"
            >
              {command.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}
              Add chart
            </button>
            <button
              type="button"
              onClick={() => dashboard.refetch()}
              className="icon-btn !h-8 !w-8"
              title="Refresh"
            >
              <RefreshCw className={cn("h-3.5 w-3.5", dashboard.isFetching && "animate-spin")} />
            </button>
            <button
              type="button"
              onClick={() => {
                if (window.confirm(`Delete dashboard "${data?.display_name || summary?.name || dashboardId}"?`)) {
                  deleteMutation.mutate();
                }
              }}
              disabled={deleteMutation.isPending}
              className="icon-btn !h-8 !w-8 text-red-500 hover:text-red-600 dark:text-red-400 dark:hover:text-red-300"
              title="Delete dashboard"
            >
              {deleteMutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            </button>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset",
                tone === "good" && "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800",
                tone === "warn" && "bg-amber-50 text-amber-800 ring-amber-200 dark:bg-amber-950 dark:text-amber-300 dark:ring-amber-800",
                tone === "bad" && "bg-rose-50 text-rose-700 ring-rose-200 dark:bg-rose-950 dark:text-rose-300 dark:ring-rose-800",
              )}
            >
              <Gauge className="h-3 w-3" />
              <span style={mono}>{score}</span>/100
              <span className="text-muted-foreground">·</span>
              <span style={mono}>{grade}</span>
            </span>
            {sql ? (
              <button
                type="button"
                onClick={() => setSqlOpen((v) => !v)}
                className={cn(
                  "inline-flex h-8 items-center gap-1 rounded-md border px-2.5 text-[12px] font-semibold transition",
                  sqlOpen
                    ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-700 dark:bg-emerald-950 dark:text-emerald-200"
                    : "border-input bg-background text-foreground hover:border-border hover:text-foreground",
                )}
              >
                <Code2 className="h-3 w-3" /> SQL
              </button>
            ) : null}
            <a
              href={`/api/agent/dashboard/${dashboardId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-8 items-center gap-1 rounded-md border border-input bg-background px-2.5 text-[12px] font-semibold text-foreground shadow-[0_1px_0_rgba(15,23,42,0.04)] transition hover:border-border hover:text-foreground"
            >
              Published view <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>

        <div ref={canvasRef} className="flex-1 overflow-y-auto px-6 py-5">
          {sql && sqlOpen ? <SqlPreview sql={sql} /> : null}
          {dashboard.isLoading ? (
            <CanvasSkeleton />
          ) : dashboard.isError ? (
            <CanvasError onRetry={() => dashboard.refetch()} />
          ) : (
            <>
              {/* KPIs */}
              {(data?.kpis ?? []).length > 0 && (
                <section className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
                  {(data?.kpis ?? []).slice(0, 4).map((kpi, i) => (
                    <div key={i} className="surface-tinted px-4 py-3">
                      <div className="section-eyebrow">{kpi.label}</div>
                      <div
                        className="mt-1 text-[20px] font-semibold leading-none tracking-tight text-foreground"
                        style={mono}
                      >
                        {String(kpi.value)}
                      </div>
                      {kpi.hint ? (
                        <p className="mt-1 text-[11px] text-muted-foreground">{kpi.hint}</p>
                      ) : null}
                    </div>
                  ))}
                </section>
              )}

              {/* Summary */}
              {data?.ai_summary ? (
                <section className="mb-5 rounded-[10px] border border-border bg-gradient-to-b from-emerald-50/30 to-background px-4 py-3 shadow-[0_1px_0_rgba(15,23,42,0.03)] dark:from-emerald-950/30 dark:to-background">
                  <div className="mb-1 flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                    <span className="section-eyebrow">Agent summary</span>
                  </div>
                  <p className="text-[13px] leading-6 text-foreground">{data.ai_summary}</p>
                </section>
              ) : null}

              {/* Charts canvas — drag/resize grid */}
              {orderedSlots.length === 0 ? (
                <CanvasEmpty />
              ) : (
                <section className="-mx-1">
                  <TypedGrid
                    className="layout"
                    layout={layout}
                    cols={COLS}
                    rowHeight={ROW_HEIGHT}
                    width={canvasWidth - 16}
                    margin={[12, 12]}
                    containerPadding={[4, 4]}
                    draggableHandle=".chart-drag-handle"
                    compactType="vertical"
                    onDragStop={(next: Layout) => persistLayout.mutate(next)}
                    onResizeStop={(next: Layout) => persistLayout.mutate(next)}
                  >
                    {orderedSlots.map((slot) => {
                      const html = charts[`chart_${slot}`];
                      const m = chartMeta.find((cm) => cm.slot === slot);
                      if (!html) return null;
                      return (
                        <div key={String(slot)}>
                          <ChartCard
                            slot={slot}
                            html={html}
                            meta={m}
                            onDelete={() => deleteChart.mutate(slot)}
                            deleting={deleteChart.isPending && deleteChart.variables === slot}
                            onCommand={(text) => command.mutate(text)}
                            busy={command.isPending}
                          />
                        </div>
                      );
                    })}
                  </TypedGrid>
                </section>
              )}
            </>
          )}
        </div>
      </main>
    </div>
  );
};

const CHART_TYPES: { id: string; label: string; icon: typeof BarChart3 }[] = [
  { id: "bar", label: "Bar", icon: BarChart3 },
  { id: "line", label: "Line", icon: LineChartIcon },
  { id: "area", label: "Area", icon: AreaChartIcon },
  { id: "pie", label: "Pie", icon: PieChartIcon },
  { id: "donut", label: "Donut", icon: PieChartIcon },
  { id: "table", label: "Table", icon: Table2 },
];

const PALETTES: { id: string; label: string; swatch: string[] }[] = [
  { id: "emerald", label: "Emerald", swatch: ["#10b981", "#0d9488", "#047857"] },
  { id: "ocean", label: "Ocean", swatch: ["#0ea5e9", "#2563eb", "#1d4ed8"] },
  { id: "violet", label: "Violet", swatch: ["#8b5cf6", "#7c3aed", "#5b21b6"] },
  { id: "sunset", label: "Sunset", swatch: ["#f59e0b", "#f97316", "#dc2626"] },
  { id: "mono", label: "Mono", swatch: ["#475569", "#334155", "#0f172a"] },
];

// const ChartCanvasMount = ({ html, className }: { html: string; className?: string }) => {
//   const ref = useRef<HTMLDivElement>(null);
//   useEffect(() => {
//     const el = ref.current;
//     if (!el) return;
//     el.innerHTML = html;
//     const scripts = Array.from(el.querySelectorAll("script"));
//     scripts.forEach((old) => {
//       const next = document.createElement("script");
//       Array.from(old.attributes).forEach((a) => next.setAttribute(a.name, a.value));
//       next.text = old.text;
//       old.parentNode?.replaceChild(next, old);
//     });
//   }, [html]);
//   return <div ref={ref} className={className} />;
// };
const ChartCanvasMount = ({ html, className }: { html: string; className?: string }) => {
  const ref = useRef<HTMLDivElement>(null);

  // Mount HTML + re-execute embedded <script> tags (Plotly init script)
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.innerHTML = html;
    const scripts = Array.from(el.querySelectorAll("script"));
    scripts.forEach((old) => {
      const next = document.createElement("script");
      Array.from(old.attributes).forEach((a) => next.setAttribute(a.name, a.value));
      next.text = old.text;
      old.parentNode?.replaceChild(next, old);
    });
  }, [html]);

  // Resize Plotly chart whenever the container size changes — needed
  // because react-grid-layout resizes/drags cards without a window resize
  // event, so Plotly's own auto-resize never fires.
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const resizePlots = () => {
      const plotDivs = el.querySelectorAll<HTMLElement>(".js-plotly-plot");
      plotDivs.forEach((div) => {
        // @ts-ignore — Plotly is loaded globally via the embedded script
        if (window.Plotly && div) {
          try {
            // @ts-ignore
            window.Plotly.Plots.resize(div);
          } catch {
            /* noop — chart may not be fully initialized yet */
          }
        }
      });
    };

    const ro = new ResizeObserver(() => {
      // Slight delay so Plotly's own render finishes before we resize it
      requestAnimationFrame(resizePlots);
    });
    ro.observe(el);

    // Also resize once right after mount, in case initial width was wrong
    const initialTimer = setTimeout(resizePlots, 50);

    return () => {
      ro.disconnect();
      clearTimeout(initialTimer);
    };
  }, [html]);

  return <div ref={ref} className={className} />;
};

const ChartCard = ({
  slot,
  html,
  meta,
  onDelete,
  deleting,
  onCommand,
  busy,
}: {
  slot: number;
  html: string;
  meta?: ChartMeta;
  onDelete?: () => void;
  deleting?: boolean;
  onCommand: (text: string) => void;
  busy?: boolean;
}) => {
  const [open, setOpen] = useState<null | "type" | "theme" | "refine">(null);
  const [refineText, setRefineText] = useState("");
  const [expanded, setExpanded] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(null);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  useEffect(() => {
    if (!expanded) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setExpanded(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded]);

  const fire = (text: string) => {
    setOpen(null);
    onCommand(text);
  };

  const titleLabel = meta?.title || `Chart ${slot}`;

  return (
    <>
      <div
        ref={wrapRef}
        className="group/card relative flex h-full flex-col overflow-hidden rounded-[14px] border border-border bg-card shadow-[0_1px_2px_rgba(15,23,42,0.04),0_4px_12px_-6px_rgba(15,23,42,0.06)] transition hover:-translate-y-px hover:border-border hover:shadow-[0_1px_2px_rgba(15,23,42,0.06),0_12px_28px_-12px_rgba(15,23,42,0.16)]"
      >
        {/* Top accent strip */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px"
          style={{
            background:
              "linear-gradient(90deg, transparent 0%, rgba(16,185,129,0.55) 50%, transparent 100%)",
          }}
        />

        {/* Header */}
        <div className="chart-drag-handle flex cursor-move items-center justify-between gap-2 border-b border-border bg-gradient-to-b from-card to-muted/60 px-3 py-2 select-none">
          <div className="flex min-w-0 items-center gap-1.5">
            <GripVertical className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50 transition group-hover/card:text-muted-foreground" />
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold tracking-tight text-foreground">
                {titleLabel}
              </p>
              {meta?.description ? (
                <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{meta.description}</p>
              ) : null}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <span
              className="rounded bg-muted px-1.5 py-0.5 text-[10.5px] font-semibold text-muted-foreground"
              style={mono}
            >
              #{slot}
            </span>
          </div>
        </div>

        {/* Hover toolbar */}
        <div
          onMouseDown={(e) => e.stopPropagation()}
          className="absolute right-2.5 top-11 z-20 flex items-center gap-1 rounded-md border border-border bg-card/95 p-1 opacity-0 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_8px_24px_-12px_rgba(15,23,42,0.18)] backdrop-blur transition-opacity duration-150 group-hover/card:opacity-100 focus-within:opacity-100"
        >
          {/* Type popover */}
          <ToolbarButton
            label="Chart type"
            active={open === "type"}
            onClick={() => setOpen(open === "type" ? null : "type")}
            icon={BarChart3}
            chevron
          />
          {/* Theme popover */}
          <ToolbarButton
            label="Color palette"
            active={open === "theme"}
            onClick={() => setOpen(open === "theme" ? null : "theme")}
            icon={Palette}
            chevron
          />
          {/* Refine popover */}
          <ToolbarButton
            label="Refine with AI"
            active={open === "refine"}
            onClick={() => setOpen(open === "refine" ? null : "refine")}
            icon={MessageSquarePlus}
          />
          <span className="mx-0.5 h-4 w-px bg-border" />
          {/* Regenerate */}
          <ToolbarButton
            label="Regenerate"
            disabled={busy}
            onClick={() =>
              fire(
                `Regenerate chart ${slot} from scratch — pick the best chart type and metric for the underlying data, keep the same intent as "${titleLabel}".`,
              )
            }
            icon={Wand2}
          />
          {/* Expand */}
          <ToolbarButton
            label="Expand"
            onClick={() => setExpanded(true)}
            icon={Maximize2}
          />
          {/* Delete */}
          {onDelete ? (
            <ToolbarButton
              label="Delete"
              tone="danger"
              disabled={deleting}
              onClick={onDelete}
              icon={deleting ? Loader2 : Trash2}
              spinning={deleting}
            />
          ) : null}
        </div>

        {/* Popover panels */}
        {open === "type" && (
          <PopoverPanel>
            <div className="grid grid-cols-3 gap-1.5">
              {CHART_TYPES.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    fire(`Change chart ${slot} to a ${id} chart. Keep the same metric and grouping.`)
                  }
                  className="group/pill flex flex-col items-center gap-1 rounded-md border border-border bg-card px-2 py-2 text-[11px] font-medium text-foreground transition hover:-translate-y-px hover:border-emerald-300 hover:text-emerald-800 hover:shadow-sm disabled:opacity-50 dark:hover:border-emerald-700 dark:hover:text-emerald-200"
                >
                  <Icon className="h-3.5 w-3.5 text-muted-foreground group-hover/pill:text-emerald-600 dark:group-hover/pill:text-emerald-400" />
                  {label}
                </button>
              ))}
            </div>
            <p className="mt-2 text-[10.5px] text-muted-foreground" style={mono}>
              the agent re-renders the chart
            </p>
          </PopoverPanel>
        )}

        {open === "theme" && (
          <PopoverPanel>
            <div className="space-y-1">
              {PALETTES.map(({ id, label, swatch }) => (
                <button
                  key={id}
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    fire(`Recolor chart ${slot} using a ${label} palette (${swatch.join(", ")}).`)
                  }
                  className="flex w-full items-center justify-between gap-2 rounded-md border border-transparent px-2 py-1.5 text-[12px] font-medium text-foreground transition hover:border-border hover:bg-muted disabled:opacity-50"
                >
                  <span className="flex items-center gap-2">
                    <span className="flex">
                      {swatch.map((c) => (
                        <span
                          key={c}
                          className="-ml-1 h-3.5 w-3.5 rounded-full ring-2 ring-background first:ml-0"
                          style={{ background: c }}
                        />
                      ))}
                    </span>
                    {label}
                  </span>
                  <ArrowUpRight className="h-3 w-3 text-muted-foreground" />
                </button>
              ))}
            </div>
          </PopoverPanel>
        )}

        {open === "refine" && (
          <PopoverPanel wide>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const t = refineText.trim();
                if (!t) return;
                fire(`For chart ${slot} ("${titleLabel}"): ${t}`);
                setRefineText("");
              }}
              className="space-y-2"
            >
              <textarea
                autoFocus
                rows={3}
                value={refineText}
                onChange={(e) => setRefineText(e.target.value)}
                placeholder="e.g. group by quarter, sort descending, add a moving average…"
                className="w-full resize-none rounded-md border border-input bg-background px-2 py-1.5 text-[12.5px] leading-5 text-foreground outline-none placeholder:text-muted-foreground focus:border-emerald-400 focus:ring-4 focus:ring-emerald-500/15 dark:border-input dark:focus:border-emerald-500"
              />
              <div className="flex items-center justify-between gap-2">
                <span className="text-[10.5px] text-muted-foreground" style={mono}>
                  refines this chart only
                </span>
                <button
                  type="submit"
                  disabled={busy || !refineText.trim()}
                  className="inline-flex h-7 items-center gap-1.5 rounded-md bg-gradient-to-b from-emerald-500 to-emerald-600 px-2.5 text-[12px] font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2),inset_0_0_0_1px_rgba(4,120,87,0.55),0_1px_2px_rgba(4,120,87,0.3)] transition hover:brightness-[1.06] disabled:opacity-50"
                >
                  <Sparkles className="h-3 w-3" />
                  Apply
                </button>
              </div>
            </form>
          </PopoverPanel>
        )}

        {/* Chart body */}
        <ChartCanvasMount
          html={html}
          className="flex-1 w-full overflow-hidden p-2 [&_*]:max-w-full"
        />
      </div>

      {/* Fullscreen overlay */}
      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/40 p-6 backdrop-blur-sm"
          onClick={() => setExpanded(false)}
        >
          <div
            className="relative flex h-full max-h-[90vh] w-full max-w-6xl flex-col overflow-hidden rounded-[14px] border border-border bg-card shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-border bg-card px-4 py-3">
              <div className="min-w-0">
                <p className="truncate text-[14px] font-semibold tracking-tight text-foreground">
                  {titleLabel}
                </p>
                {meta?.description ? (
                  <p className="mt-0.5 truncate text-[11.5px] text-muted-foreground">
                    {meta.description}
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="icon-btn !h-8 !w-8"
                title="Close (Esc)"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <ChartCanvasMount
              html={html}
              className="flex-1 w-full overflow-auto p-4 [&_*]:max-w-full"
            />
            <div className="flex items-center justify-end gap-1.5 border-t border-border bg-muted/60 px-3 py-2">
              <button
                type="button"
                onClick={() => setExpanded(false)}
                className="inline-flex h-7 items-center gap-1 rounded-md border border-border bg-card px-2.5 text-[12px] font-semibold text-foreground hover:border-border"
              >
                <Minimize2 className="h-3 w-3" /> Collapse
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

const ToolbarButton = ({
  label,
  icon: Icon,
  onClick,
  disabled,
  active,
  tone,
  chevron,
  spinning,
}: {
  label: string;
  icon: typeof BarChart3;
  onClick?: () => void;
  disabled?: boolean;
  active?: boolean;
  tone?: "danger";
  chevron?: boolean;
  spinning?: boolean;
}) => (
  <button
    type="button"
    title={label}
    aria-label={label}
    disabled={disabled}
    onClick={(e) => {
      e.stopPropagation();
      onClick?.();
    }}
    className={cn(
      "inline-flex h-6 items-center gap-0.5 rounded px-1.5 text-[11px] font-medium transition",
      "text-muted-foreground hover:bg-muted hover:text-foreground",
      active && "bg-foreground text-background hover:bg-foreground hover:text-background",
      tone === "danger" && "hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950 dark:hover:text-rose-400",
      disabled && "opacity-50",
    )}
  >
    <Icon className={cn("h-3 w-3", spinning && "animate-spin")} />
    {chevron ? <ChevronDown className="h-2.5 w-2.5 opacity-70" /> : null}
  </button>
);

const PopoverPanel = ({
  children,
  wide = false,
}: {
  children: React.ReactNode;
  wide?: boolean;
}) => (
  <div
    onMouseDown={(e) => e.stopPropagation()}
    className={cn(
      "absolute right-2.5 top-[78px] z-30 rounded-[10px] border border-border bg-card p-2 shadow-[0_1px_2px_rgba(15,23,42,0.06),0_12px_32px_-12px_rgba(15,23,42,0.22)]",
      wide ? "w-[320px]" : "w-[220px]",
    )}
  >
    {children}
  </div>
);

const SqlPreview = ({ sql }: { sql: string }) => {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 1200);
    } catch {
      /* noop */
    }
  };
  return (
    <section className="mb-5 overflow-hidden rounded-[10px] border border-border bg-card shadow-[0_1px_2px_rgba(15,23,42,0.06),0_4px_12px_-6px_rgba(15,23,42,0.18)]">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-1.5">
          <Code2 className="h-3.5 w-3.5 text-emerald-400" />
          <span
            className="text-[10.5px] font-semibold uppercase tracking-[0.16em] text-emerald-300"
            style={mono}
          >
            Source SQL · readonly
          </span>
        </div>
        <button
          type="button"
          onClick={copy}
          className="inline-flex h-6 items-center gap-1 rounded bg-muted px-1.5 text-[11px] font-medium text-muted-foreground transition hover:bg-muted/80"
        >
          <Copy className="h-3 w-3" /> {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        className="overflow-x-auto px-3 py-3 text-[12px] leading-5 text-emerald-100"
        style={mono}
      >
        {sql}
      </pre>
    </section>
  );
};

const ChatBubble = ({ message }: { message: ChatMessage }) => {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex gap-2", isUser ? "flex-row-reverse" : "flex-row")}>
      <span
        className={cn(
          "mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full ring-1 ring-inset",
          isUser
            ? "bg-muted text-muted-foreground ring-border"
            : "bg-emerald-50 text-emerald-700 ring-emerald-200 dark:bg-emerald-950 dark:text-emerald-300 dark:ring-emerald-800",
        )}
      >
        {isUser ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
      </span>
      <div
        className={cn(
          "max-w-[78%] rounded-[10px] px-3 py-2 text-[12.5px] leading-5 ring-1 ring-inset",
          isUser
            ? "bg-muted text-foreground ring-border"
            : "bg-card text-foreground ring-border shadow-[0_1px_0_rgba(15,23,42,0.03)]",
        )}
      >
        {message.content}
      </div>
    </div>
  );
};

const EmptyChat = ({ onPick }: { onPick: (s: string) => void }) => (
  <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
    <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-50 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950 dark:ring-emerald-800">
      <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
    </div>
    <p className="text-[13px] font-semibold text-foreground">Refine your dashboard</p>
    <p className="max-w-[260px] text-[11.5px] text-muted-foreground">
      Ask the agent to add charts, replace metrics, explain anomalies — all in plain English.
    </p>
    <div className="mt-1 flex w-full flex-col gap-1.5">
      {STARTERS.map((s) => (
        <button
          key={s}
          type="button"
          onClick={() => onPick(s)}
          className="inline-flex items-center justify-between gap-2 rounded-md border border-border bg-card px-2.5 py-1.5 text-left text-[12px] text-foreground transition hover:border-border"
        >
          <span className="truncate">{s}</span>
          <ArrowUpRight className="h-3 w-3 text-muted-foreground" />
        </button>
      ))}
    </div>
  </div>
);

const CanvasSkeleton = () => (
  <div className="space-y-4">
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-[68px] animate-pulse rounded-[10px] bg-muted" />
      ))}
    </div>
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-[280px] animate-pulse rounded-[12px] bg-muted" />
      ))}
    </div>
  </div>
);

const CanvasError = ({ onRetry }: { onRetry: () => void }) => (
  <div className="flex flex-col items-center justify-center gap-3 rounded-[12px] border border-rose-200 bg-rose-50/40 px-6 py-12 text-center dark:border-rose-800 dark:bg-rose-950/40">
    <p className="text-[13px] font-semibold text-rose-800 dark:text-rose-300">Couldn't load this dashboard</p>
    <button
      type="button"
      onClick={onRetry}
      className="inline-flex h-8 items-center gap-1.5 rounded-md bg-card px-3 text-[12px] font-semibold text-foreground ring-1 ring-inset ring-border hover:ring-border"
    >
      Try again
    </button>
  </div>
);

const CanvasEmpty = () => (
  <div className="flex flex-col items-center justify-center gap-2 rounded-[12px] border border-dashed border-border bg-muted/40 px-6 py-16 text-center">
    <div className="grid h-10 w-10 place-items-center rounded-full bg-emerald-50 ring-1 ring-inset ring-emerald-200 dark:bg-emerald-950 dark:ring-emerald-800">
      <Sparkles className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
    </div>
    <p className="text-[13px] font-semibold text-foreground">No charts yet</p>
    <p className="max-w-xs text-[11.5px] text-muted-foreground">
      Ask the agent on the left to add the first chart.
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
