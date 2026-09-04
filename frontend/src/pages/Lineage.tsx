import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  MarkerType,
  Position,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Waypoints, RefreshCw, Loader2, Search as SearchIcon, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState, RowSkeleton } from "@/components/console/Panel";

// ── Types (mirror backend/lineage/router.py response shapes) ──────────────
interface LineageNode {
  node_id: number;
  node_type: "source" | "table" | "column";
  system: string | null;
  name: string;
  parent_id: number | null;
}

interface LineageEdge {
  edge_id: number;
  src_node_id: number;
  tgt_node_id: number;
  pipeline_id: string | null;
  first_seen: string;
  last_seen: string;
}

interface LineageGraphResponse {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

interface RunEvent {
  rows_loaded: number | null;
  status: string;
  ran_at: string;
}

interface TableSource {
  edge_id: number;
  pipeline_id: string | null;
  first_seen: string;
  last_seen: string;
  source_system: string | null;
  source_name: string;
  recent_runs: RunEvent[];
}

interface TableLineageResponse {
  table: string;
  sources: TableSource[];
}

// ── API calls (thin wrappers over the existing `api` axios client) ────────
const fetchLineageGraph = async (focus?: string): Promise<LineageGraphResponse> => {
  const r = await api.get("/lineage/graph", { params: focus ? { focus } : {} });
  return r.data;
};

const fetchTableLineage = async (tableName: string): Promise<TableLineageResponse> => {
  const r = await api.get(`/lineage/table/${encodeURIComponent(tableName)}`);
  return r.data;
};

const runBackfill = async (): Promise<{ status: string; edges_seeded: number }> => {
  const r = await api.post("/lineage/backfill");
  return r.data;
};

// Pydantic validation errors arrive as an array of {loc, msg, ...} objects;
// a plain string detail also happens for HTTPException(detail="..."). This
// turns either shape into short, readable lines — same helper as QualityChecks.tsx.
const formatApiError = (error: unknown): string => {
  const detail = (error as any)?.response?.data?.detail;
  if (!detail) return (error as Error)?.message ?? "Something went wrong.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: any) => {
        const field = Array.isArray(d?.loc) ? d.loc[d.loc.length - 1] : undefined;
        return field ? `${field}: ${d.msg}` : d.msg ?? JSON.stringify(d);
      })
      .join("; ");
  }
  return JSON.stringify(detail);
};

// Rough colour-coding per connector_type so the same source system reads
// consistently everywhere else in the app (Connections, Pipelines, etc.)
// don't have a shared colour map today, so this one is local to the graph.
const CONNECTOR_COLORS: Record<string, string> = {
  csv: "#0ea5e9",
  excel: "#22c55e",
  google_sheets: "#22c55e",
  google_sheet: "#22c55e",
  api: "#f59e0b",
  postgres: "#6366f1",
  mysql: "#f97316",
  oracle: "#ef4444",
  mongodb: "#10b981",
  s3: "#eab308",
  snowflake: "#38bdf8",
  salesforce: "#0ea5e9",
  hubspot: "#f97316",
  zoho: "#dc2626",
};

const NODE_ROW_HEIGHT = 92;

/**
 * Turns the flat {nodes, edges} response into React Flow's shape. The
 * backend models lineage as source_node -> table_node with pipeline_id as
 * an edge attribute (no separate "pipeline" node), so the graph is
 * inherently bipartite — sources on the left, tables on the right. That
 * makes a simple two-column layout accurate today without pulling in a
 * layout library; if a table -> table hop is ever added upstream, this is
 * the place to swap in a real layered-layout algorithm.
 */
function buildFlow(graph: LineageGraphResponse | undefined): { nodes: Node[]; edges: Edge[] } {
  if (!graph) return { nodes: [], edges: [] };

  const sources = graph.nodes.filter((n) => n.node_type === "source");
  const tables = graph.nodes.filter((n) => n.node_type === "table");

  const nodes: Node[] = [
    ...sources.map((n, i) => ({
      id: `n${n.node_id}`,
      position: { x: 0, y: i * NODE_ROW_HEIGHT },
      data: { label: n.name, system: n.system, nodeType: n.node_type },
      sourcePosition: Position.Right,
      style: {
        background: (n.system && CONNECTOR_COLORS[n.system]) || "#64748b",
        color: "#fff",
        border: "none",
        borderRadius: 8,
        padding: "8px 12px",
        fontSize: 12,
        maxWidth: 240,
        boxShadow: "0 1px 2px rgba(15,23,42,0.15)",
      },
    })),
    ...tables.map((n, i) => ({
      id: `n${n.node_id}`,
      position: { x: 560, y: i * NODE_ROW_HEIGHT },
      data: { label: n.name, system: n.system, nodeType: n.node_type },
      targetPosition: Position.Left,
      style: {
        background: "#1e293b",
        color: "#fff",
        border: "1px solid #334155",
        borderRadius: 8,
        padding: "8px 12px",
        fontSize: 12,
        fontWeight: 600,
        maxWidth: 240,
      },
    })),
  ];

  const edges: Edge[] = graph.edges.map((e) => ({
    id: `e${e.edge_id}`,
    source: `n${e.src_node_id}`,
    target: `n${e.tgt_node_id}`,
    animated: true,
    label: e.pipeline_id ?? undefined,
    labelStyle: { fontSize: 10, fill: "#64748b" },
    markerEnd: { type: MarkerType.ArrowClosed, color: "#94a3b8" },
    style: { stroke: "#94a3b8" },
  }));

  return { nodes, edges };
}

export const Lineage = () => {
  const [focus, setFocus] = useState("");
  const [focusInput, setFocusInput] = useState("");
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const qc = useQueryClient();

  const {
    data: graph,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["lineage-graph", focus],
    queryFn: () => fetchLineageGraph(focus || undefined),
    retry: false,
  });

  const { data: tableDetail, isLoading: tableLoading } = useQuery({
    queryKey: ["lineage-table", selectedTable],
    queryFn: () => fetchTableLineage(selectedTable as string),
    enabled: !!selectedTable,
  });

  const backfill = useMutation({
    mutationFn: runBackfill,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lineage-graph"] });
    },
  });

  const { nodes, edges } = useMemo(() => buildFlow(graph), [graph]);
  const hasGraph = !!graph && graph.nodes.length > 0;

  const onNodeClick = useCallback((_event: unknown, node: Node) => {
    const label = node.data?.label as string | undefined;
    if (!label) return;
    if (node.data?.nodeType === "table") {
      setSelectedTable(label);
    } else {
      // Clicking a source re-centers the graph on it — a lightweight
      // "impact view" without needing a separate mode toggle.
      setSelectedTable(null);
      setFocus(label);
      setFocusInput(label);
    }
  }, []);

  const applyFocus = () => setFocus(focusInput.trim());
  const clearFocus = () => {
    setFocus("");
    setFocusInput("");
  };

  return (
    <div className="space-y-5">
      <PageHeader
        icon={Waypoints}
        eyebrow="Observe"
        title="Data Lineage"
        description="See exactly which source feeds which table. Click a source to focus the graph around it, or a table to see its recent runs."
        actions={
          <Button variant="outline" size="sm" onClick={() => backfill.mutate()} disabled={backfill.isPending}>
            {backfill.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            {backfill.isPending ? "Backfilling…" : "Backfill from history"}
          </Button>
        }
      />

      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-xs">
          <SearchIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-8"
            placeholder="Focus on a table or source name…"
            value={focusInput}
            onChange={(e) => setFocusInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") applyFocus();
            }}
          />
        </div>
        <Button size="sm" variant="outline" onClick={applyFocus}>
          Focus
        </Button>
        {focus && (
          <Button size="sm" variant="ghost" onClick={clearFocus}>
            <X className="h-3.5 w-3.5" /> Clear focus
          </Button>
        )}
      </div>

      {backfill.isSuccess && (
        <p className="text-xs text-emerald-700 dark:text-emerald-400">
          Seeded {backfill.data?.edges_seeded ?? 0} edge(s) from pipeline history.
        </p>
      )}
      {backfill.isError && <p className="text-xs text-rose-700 dark:text-rose-400">{formatApiError(backfill.error)}</p>}
      {isError && <p className="text-xs text-rose-700 dark:text-rose-400">{formatApiError(error)}</p>}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        <Card className="overflow-hidden">
          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-4">
                <RowSkeleton rows={5} />
              </div>
            ) : !hasGraph ? (
              <div className="p-8">
                <EmptyState
                  icon={Waypoints}
                  title="No lineage recorded yet"
                  body="Run an ingest, or click “Backfill from history” above to build the graph from your existing pipeline runs."
                />
              </div>
            ) : (
              <div style={{ height: 600 }}>
                <ReactFlow nodes={nodes} edges={edges} onNodeClick={onNodeClick} fitView proOptions={{ hideAttribution: true }}>
                  <Background />
                  <Controls showInteractive={false} />
                  <MiniMap pannable zoomable />
                </ReactFlow>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="truncate text-sm" title={selectedTable ?? undefined}>
              {selectedTable ?? "Details"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedTable ? (
              <p className="text-xs text-muted-foreground">Click a table node to see its upstream sources and recent run history.</p>
            ) : tableLoading ? (
              <RowSkeleton rows={2} />
            ) : !tableDetail?.sources?.length ? (
              <p className="text-xs text-muted-foreground">No recorded sources for this table.</p>
            ) : (
              <div className="space-y-3">
                {tableDetail.sources.map((src) => (
                  <div key={src.edge_id} className="rounded-md border border-border p-2.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-xs font-semibold text-foreground" title={src.source_name}>
                        {src.source_name}
                      </span>
                      {src.source_system && (
                        <span className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium uppercase text-muted-foreground">
                          {src.source_system}
                        </span>
                      )}
                    </div>
                    {src.pipeline_id && <p className="mt-1 truncate text-[11px] text-muted-foreground">Pipeline: {src.pipeline_id}</p>}
                    <p className="mt-0.5 text-[11px] text-muted-foreground">Last seen {new Date(src.last_seen).toLocaleString()}</p>
                    {src.recent_runs?.length > 0 && (
                      <div className="mt-2 space-y-1 border-t border-border pt-2">
                        {src.recent_runs.slice(0, 5).map((run, i) => (
                          <div key={i} className="flex items-center justify-between text-[11px]">
                            <span className={run.status === "SUCCESS" ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400"}>
                              {run.status}
                            </span>
                            <span className="text-muted-foreground">{run.rows_loaded ?? "—"} rows</span>
                            <span className="text-muted-foreground">{new Date(run.ran_at).toLocaleDateString()}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
