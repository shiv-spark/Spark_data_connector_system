import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

export const api = axios.create({
  baseURL,
  timeout: 200000, //  — analyze/ingest can take 20–60s due to LLM + heavy queries
});

// ── Attach JWT token to every outgoing request ──────────────────────────
api.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Existing response interceptor, extended to also handle 401 (auth expired) ──
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.code === "ECONNABORTED") {
      err.message = "Request timed out. Is the backend running?";
    } else if (!err.response) {
      err.message = "Cannot reach the API. Is the container up?";
    } else if (err.response.status === 401) {
      // Token missing/expired/invalid — clear stored auth and send user to login.
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      if (window.location.pathname !== "/login") {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

export const fetchHealth = async () => {
  const r = await api.get("/health");
  return r.data;
};

// ── everything below this line is UNCHANGED from your existing file ──────

// Text-to-SQL API functions
export interface Text2SQLRequest {
  question: string;
  connection_id?: string;
  tables?: string[];
  auto_execute?: boolean;
  include_samples?: boolean;
}

export const askText2SQL = async (request: Text2SQLRequest) => {
  const r = await api.post("/text2sql/ask", request);
  return r.data;
};

export const generateText2SQL = async (request: Text2SQLRequest) => {
  const r = await api.post("/text2sql/generate", request);
  return r.data;
};

export const fetchText2SQLTables = async (connectionId?: string) => {
  const params = connectionId ? { connection_id: connectionId } : {};
  const r = await api.get("/text2sql/tables", { params });
  return r.data.tables || [];
};

export const fetchText2SQLSchema = async (tables?: string[], connectionId?: string) => {
  const params: Record<string, string> = {};
  if (tables) params.tables = tables.join(",");
  if (connectionId) params.connection_id = connectionId;
  const r = await api.get("/text2sql/schema", { params });
  return r.data;
};

export interface Text2SQLConnection {
  id: string;
  name: string;
  type: string;
  config: Record<string, any>;
}

export const fetchText2SQLConnections = async (): Promise<Text2SQLConnection[]> => {
  const r = await api.get("/text2sql/connections");
  return r.data || [];
};

export const fetchText2SQLStats = async () => {
  const r = await api.get("/text2sql/metadata/stats");
  return r.data;
};

export const fetchText2SQLRuns = async (limit: number = 10) => {
  const r = await api.get("/text2sql/metadata/runs", { params: { limit } });
  return r.data;
};

// Connection Management API
export interface DatabaseConfig {
  host?: string;
  port?: number;
  database?: string;
  user?: string;
  password?: string;
  database_path?: string;
  account?: string;
  warehouse?: string;
  schema?: string;
  role?: string;
}

export interface ConnectionRequest {
  name: string;
  db_type: string;
  config: DatabaseConfig;
}

export const createText2SQLConnection = async (request: ConnectionRequest) => {
  const r = await api.post("/text2sql/connections", request);
  return r.data;
};

export const deleteText2SQLConnection = async (connectionId: string) => {
  const r = await api.delete(`/text2sql/connections/${connectionId}`);
  return r.data;
};

export const testText2SQLConnection = async (connectionId: string) => {
  const r = await api.post(`/text2sql/connections/${connectionId}/test`);
  return r.data;
};

// Data Generator Connections (from data connector's saved_connections)
export interface DataGenConnection {
  id: string;
  name: string;
  type: string;
  config: Record<string, any>;
}

export const fetchDataGenConnections = async (): Promise<DataGenConnection[]> => {
  const r = await api.get("/datagen/connections");
  return r.data?.connections || [];
};

export const fetchDataGenTables = async (connectionId: string): Promise<string[]> => {
  const r = await api.get(`/datagen/connections/${connectionId}/tables`);
  return r.data?.tables || [];
};

export const fetchDataGenSchema = async (connectionId: string, tableName: string) => {
  const r = await api.get(`/datagen/connections/${connectionId}/schema/${tableName}`);
  return r.data;
};

export interface SearchResult {
  id: string;
  title: string;
  subtitle?: string;
  category: 'pipelines' | 'connections' | 'dashboards' | 'metrics' | 'logs';
  path: string;
  icon?: string;
}

export interface SearchResults {
  pipelines: SearchResult[];
  connections: SearchResult[];
  dashboards: SearchResult[];
  metrics: SearchResult[];
  logs: SearchResult[];
}

export const searchPipelines = async (query: string): Promise<SearchResult[]> => {
  try {
    const r = await api.get('/pipelines');
    const pipelines = r.data?.pipelines || r.data || [];
    const q = query.toLowerCase();
    return pipelines
      .filter((p: any) => 
        (p.pipeline_id?.toLowerCase().includes(q)) ||
        (p.table_name?.toLowerCase().includes(q)) ||
        (p.status?.toLowerCase().includes(q))
      )
      .slice(0, 10)
      .map((p: any) => ({
        id: p.pipeline_id || p.id,
        title: p.pipeline_id || p.table_name || 'Unknown Pipeline',
        subtitle: p.table_name || p.status,
        category: 'pipelines' as const,
        path: `/pipelines?highlight=${encodeURIComponent(p.pipeline_id || p.id)}`,
      }));
  } catch {
    return [];
  }
};

export const searchConnections = async (query: string): Promise<SearchResult[]> => {
  try {
    const r = await api.get('/connections');
    const connections = r.data?.connections || [];
    const q = query.toLowerCase();
    return connections
      .filter((c: any) =>
        (c.name?.toLowerCase().includes(q)) ||
        (c.source_type?.toLowerCase().includes(q))
      )
      .slice(0, 10)
      .map((c: any) => ({
        id: String(c.id),
        title: c.name || 'Unknown Connection',
        subtitle: c.source_type,
        category: 'connections' as const,
        path: `/connections?highlight=${c.id}`,
      }));
  } catch {
    return [];
  }
};

export const searchDashboards = async (query: string): Promise<SearchResult[]> => {
  try {
    const r = await api.get('/agent/dashboards');
    const dashboards = r.data?.dashboards || [];
    const q = query.toLowerCase();
    
    return dashboards
      .filter((d: any) =>
        (d.name?.toLowerCase().includes(q)) ||
        (d.dashboard_id?.toLowerCase().includes(q)) ||
        (d.source_type?.toLowerCase().includes(q))
      )
      .slice(0, 10)
      .map((d: any) => ({
        id: d.dashboard_id,
        title: d.name || d.dashboard_id,
        subtitle: `${d.source_type || ''}${d.grade ? ` • Grade: ${d.grade}` : ''}`,
        category: 'dashboards' as const,
        path: `/studio/${d.dashboard_id}`,
      }));
  } catch {
    return [];
  }
};

export const updateDashboardName = async (dashboardId: string, displayName: string) => {
  const r = await api.patch(`/agent/dashboard/${dashboardId}`, { display_name: displayName });
  return r.data;
};

export const deleteDashboard = async (dashboardId: string) => {
  const r = await api.delete(`/agent/dashboard/${dashboardId}`);
  return r.data;
};

export const renameChart = async (dashboardId: string, slot: number, title: string) => {
  const r = await api.patch(`/agent/dashboard/${dashboardId}/chart/${slot}`, { title });
  return r.data;
};

export const updateChartDescription = async (dashboardId: string, slot: number, description: string) => {
  const r = await api.patch(`/agent/dashboard/${dashboardId}/chart/${slot}`, { description });
  return r.data;
};

export const searchMetrics = async (query: string): Promise<SearchResult[]> => {
  try {
    const r = await api.get('/metrics/summary/all');
    const metrics = r.data?.summary || r.data || [];
    const q = query.toLowerCase();
    
    if (!Array.isArray(metrics)) return [];
    
    return metrics
      .filter((m: any) =>
        (m.pipeline_id?.toLowerCase().includes(q)) ||
        (m.table_name?.toLowerCase().includes(q))
      )
      .slice(0, 10)
      .map((m: any) => ({
        id: m.pipeline_id || m.id,
        title: m.pipeline_id || m.table_name || 'Unknown',
        subtitle: `${m.total_runs || 0} runs, ${m.success || 0} success`,
        category: 'metrics' as const,
        path: `/metrics?pipeline=${encodeURIComponent(m.pipeline_id || '')}`,
      }));
  } catch {
    return [];
  }
};

export const searchLogs = async (query: string): Promise<SearchResult[]> => {
  try {
    const r = await api.get('/logs', { params: { limit: 100 } });
    const logs = r.data?.logs || r.data || [];
    const q = query.toLowerCase();
    
    if (!Array.isArray(logs)) return [];
    
    return logs
      .filter((l: any) =>
        (l.message?.toLowerCase().includes(q)) ||
        (l.level?.toLowerCase().includes(q)) ||
        (l.pipeline_id?.toLowerCase().includes(q))
      )
      .slice(0, 10)
      .map((l: any, idx: number) => ({
        id: l.id || `log-${idx}`,
        title: l.message?.substring(0, 60) || 'Log entry',
        subtitle: `${l.level || 'INFO'} - ${l.pipeline_id || ''}`,
        category: 'logs' as const,
        path: `/logs`,
      }));
  } catch {
    return [];
  }
};

export const globalSearch = async (query: string): Promise<SearchResults> => {
  if (!query.trim()) {
    return { pipelines: [], connections: [], dashboards: [], metrics: [], logs: [] };
  }

  const [pipelines, connections, dashboards, metrics, logs] = await Promise.all([
    searchPipelines(query),
    searchConnections(query),
    searchDashboards(query),
    searchMetrics(query),
    searchLogs(query),
  ]);

  return { pipelines, connections, dashboards, metrics, logs };
};
/* --- Dashboard version history ------------------------------------------ */

export interface DashboardVersion {
  version_id: number;
  label: string | null;
  created_at: string | null;
}

export const fetchDashboardHistory = async (dashboardId: string): Promise<DashboardVersion[]> => {
  const r = await api.get(`/agent/dashboard/${dashboardId}/history`);
  return r.data?.history ?? [];
};

/** Steps back one change. Returns the label of what was undone. */
export const undoDashboard = async (dashboardId: string): Promise<string | null> => {
  const r = await api.post(`/agent/dashboard/${dashboardId}/undo`);
  return r.data?.undid ?? null;
};

export const restoreDashboardVersion = async (dashboardId: string, versionId: number) => {
  const r = await api.post(`/agent/dashboard/${dashboardId}/restore/${versionId}`);
  return r.data;
};
