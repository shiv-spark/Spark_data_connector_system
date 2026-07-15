import { api } from './api';

export interface SqlExecuteRequest {
  connection_id: number;
  query: string;
  limit?: number;
  timeout_seconds?: number;
}

export interface SqlColumn {
  name: string;
  type: string;
}

export interface SqlExecuteResponse {
  columns: SqlColumn[];
  rows: any[][];
  row_count: number;
  truncated: boolean;
  execution_time_ms: number;
  query_id: string;
}

export interface QueryHistoryItem {
  query_id: string;
  connection_id: number;
  connection_name?: string;
  connection_type?: string;
  query_text: string;
  status: string;
  row_count: number | null;
  executed_at: string;
  duration_ms: number | null;
}

export interface SqlError {
  error_type: string;
  message: string;
  line?: number;
  column?: number;
}

export const executeQuery = async (params: SqlExecuteRequest): Promise<SqlExecuteResponse> => {
  const response = await api.post<SqlExecuteResponse>('/sql/execute', params);
  return response.data;
};

export const cancelQuery = async (queryId: string): Promise<{ success: boolean; message: string }> => {
  const response = await api.post(`/sql/cancel/${queryId}`);
  return response.data;
};

export const getQueryHistory = async (connectionId?: number, limit?: number): Promise<QueryHistoryItem[]> => {
  const params = new URLSearchParams();
  if (connectionId) params.append('connection_id', connectionId.toString());
  if (limit) params.append('limit', limit.toString());
  
  const response = await api.get<QueryHistoryItem[]>(`/sql/history?${params.toString()}`);
  return response.data;
};

export const formatSql = async (query: string): Promise<{ formatted_query: string }> => {
  const response = await api.post('/sql/format', { query });
  return response.data;
};

export const getConnectionSchema = async (connectionId: number): Promise<{ schema: Record<string, string[]> }> => {
  const response = await api.get(`/sql/schema/${connectionId}`);
  return response.data;
};

export const getConnections = async () => {
  const response = await api.get('/connections');
  return response.data.connections;
};

export const getSqlCapableConnections = async () => {
  const connections = await getConnections();
  return connections.filter((c: any) => 
    c.source_type === 'postgresql' || c.source_type === 'postgres' || c.source_type === 'snowflake'
  );
};

export interface AiGenerateRequest {
  question: string;
  connection_id?: string;
  tables?: string[];
  include_samples?: boolean;
}

export interface AiGenerateResponse {
  success: boolean;
  sql?: string;
  is_valid?: boolean;
  validation_message?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  llm_latency?: number;
  attempts?: number;
  connection_id?: string;
  connection_name?: string;
  error?: string;
}

export const generateSqlFromNaturalLanguage = async (
  params: AiGenerateRequest
): Promise<AiGenerateResponse> => {
  const response = await api.post<AiGenerateResponse>('/text2sql/generate', {
    question: params.question,
    connection_id: params.connection_id,
    tables: params.tables,
    include_samples: params.include_samples ?? true,
    auto_execute: false,
  });
  return response.data;
};

export interface SchemaInfoResponse {
  connection_id?: string;
  connection_name: string;
  db_type: string;
  tables: string[];
  schema_text_length: number;
  column_count: number;
}

export const getConnectionSchemaInfo = async (
  connectionId?: string
): Promise<SchemaInfoResponse> => {
  const params = new URLSearchParams();
  if (connectionId) params.append('connection_id', connectionId);
  const response = await api.get<SchemaInfoResponse>(`/text2sql/schema?${params.toString()}`);
  return response.data;
};