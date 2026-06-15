import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL || "/api";

export const api = axios.create({
  baseURL,
  timeout: 120_000, // 2 min — analyze/ingest can take 20–60s due to LLM + heavy queries
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.code === "ECONNABORTED") {
      err.message = "Request timed out. Is the backend running?";
    } else if (!err.response) {
      err.message = "Cannot reach the API. Is the container up?";
    }
    return Promise.reject(err);
  },
);

export const fetchHealth = async () => {
  const r = await api.get("/health");
  return r.data;
};

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