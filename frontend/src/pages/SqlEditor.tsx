import { useState, useCallback, useEffect, useRef } from 'react';
import Editor, { Monaco } from '@monaco-editor/react';
import {
  Play,
  Square,
  Download,
  Clock,
  AlertCircle,
  Database,
  History,
  ChevronDown,
  Loader2,
} from 'lucide-react';
import {
  executeQuery,
  cancelQuery,
  getQueryHistory,
  formatSql,
  getConnections,
  type SqlExecuteResponse,
  type QueryHistoryItem,
  type SqlError,
} from '../lib/sql-api';

interface Connection {
  id: number;
  name: string;
  source_type: string;
  config: Record<string, any>;
}

const SQL_CAPABLE_TYPES = ['postgresql', 'postgres', 'snowflake'];

export default function SqlEditor() {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selectedConnection, setSelectedConnection] = useState<Connection | null>(null);
  const [query, setQuery] = useState('SELECT * FROM ');
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<SqlExecuteResponse | null>(null);
  const [error, setError] = useState<SqlError | null>(null);
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [currentQueryId, setCurrentQueryId] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const parentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadConnections();
    loadHistory();
  }, []);

  useEffect(() => {
    if (isRunning) {
      setElapsedTime(0);
      timerRef.current = window.setInterval(() => {
        setElapsedTime((t) => t + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [isRunning]);

  const loadConnections = async () => {
    try {
      const allConnections = await getConnections();
      const sqlConnections = allConnections.filter((c: Connection) =>
        SQL_CAPABLE_TYPES.includes(c.source_type.toLowerCase())
      );
      setConnections(sqlConnections);
      if (sqlConnections.length > 0 && !selectedConnection) {
        setSelectedConnection(sqlConnections[0]);
      }
    } catch (err) {
      console.error('Failed to load connections:', err);
    }
  };

  const loadHistory = async () => {
    try {
      const historyData = await getQueryHistory();
      setHistory(historyData);
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  };

  const handleRunQuery = async () => {
    if (!selectedConnection || !query.trim()) return;

    setIsRunning(true);
    setError(null);
    setResults(null);

    try {
      const response = await executeQuery({
        connection_id: selectedConnection.id,
        query: query,
        limit: 100,
        timeout_seconds: 30,
      });
      setResults(response);
      setCurrentQueryId(response.query_id);
      loadHistory();
    } catch (err: any) {
      if (err.response?.data) {
        setError(err.response.data.detail);
      } else {
        setError({ error_type: 'unknown', message: 'An unexpected error occurred' });
      }
    } finally {
      setIsRunning(false);
    }
  };

  const handleCancel = async () => {
    if (!currentQueryId) return;

    try {
      await cancelQuery(currentQueryId);
      setIsRunning(false);
    } catch (err) {
      console.error('Failed to cancel query:', err);
    }
  };

  const handleFormat = async () => {
    if (!query.trim()) return;

    try {
      const { formatted_query } = await formatSql(query);
      setQuery(formatted_query);
    } catch (err) {
      console.error('Failed to format query:', err);
    }
  };

  const handleExport = () => {
    if (!results) return;

    const headers = results.columns.map((c) => c.name).join(',');
    const rows = results.rows.map((row) =>
      row.map((cell) => {
        if (cell === null) return '';
        const str = String(cell);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      }).join(',')
    );
    const csv = [headers, ...rows].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `query_results_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSelectHistory = (item: QueryHistoryItem) => {
    // Find and select the connection from history
    const conn = connections.find(c => c.id === item.connection_id);
    if (conn) {
      setSelectedConnection(conn);
      setResults(null);
      setError(null);
    }
    setQuery(item.query_text);
    setShowHistory(false);
  };

  const handleEditorMount = (editor: any, monaco: Monaco) => {
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => {
      handleRunQuery();
    });

    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, (e: any) => {
      e.preventDefault();
      handleFormat();
    });
  };

  const getEditorLanguage = () => {
    if (!selectedConnection) return 'sql';
    const type = selectedConnection.source_type.toLowerCase();
    if (type === 'snowflake') return 'sql';
    return 'sql';
  };

  return (
    <div className="flex flex-col h-screen bg-white text-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-600" />
            SQL Editor
          </h1>

          {/* Connection Selector */}
          <div className="relative">
            <select
              value={selectedConnection?.id || ''}
              onChange={(e) => {
                const conn = connections.find((c) => c.id === Number(e.target.value));
                setSelectedConnection(conn || null);
                setResults(null);
                setError(null);
              }}
              className="appearance-none bg-white border border-gray-300 rounded-lg px-4 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isRunning}
            >
              <option value="">Select a connection...</option>
              {connections.map((conn) => (
                <option key={conn.id} value={conn.id}>
                  {conn.name} ({conn.source_type})
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRunQuery}
            disabled={!selectedConnection || !query.trim() || isRunning}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors"
          >
            {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {isRunning ? 'Running...' : 'Run'}
          </button>

          {isRunning && (
            <button
              onClick={handleCancel}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg text-sm font-medium text-white transition-colors"
            >
              <Square className="w-4 h-4" />
              Cancel
            </button>
          )}

          <button
            onClick={handleFormat}
            disabled={!query.trim() || isRunning}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-gray-700 transition-colors border border-gray-300"
          >
            Format
          </button>

          <button
            onClick={() => setShowHistory(!showHistory)}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium text-gray-700 transition-colors border border-gray-300"
          >
            <History className="w-4 h-4" />
          </button>

          {results && (
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium text-gray-700 transition-colors border border-gray-300"
            >
              <Download className="w-4 h-4" />
              Export
            </button>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Editor Panel */}
        <div className={`flex-1 flex flex-col ${showHistory ? 'w-3/4' : 'w-full'}`}>
          {/* Error Banner */}
          {error && (
            <div className="mx-6 mt-4 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-red-700">{error.error_type}</p>
                <p className="text-red-600 text-sm mt-1">{error.message}</p>
                {error.line && (
                  <p className="text-red-500 text-xs mt-2">
                    Line {error.line}{error.column ? `, Column ${error.column}` : ''}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Editor */}
          <div className="flex-1 p-4">
            <div className="h-full border border-gray-300 rounded-lg overflow-hidden">
              <Editor
                height="100%"
                language={getEditorLanguage()}
                value={query}
                onChange={(value) => setQuery(value || '')}
                onMount={handleEditorMount}
                theme="light"
                options={{
                  minimap: { enabled: false },
                  fontSize: 14,
                  lineNumbers: 'on',
                  scrollBeyondLastLine: false,
                  automaticLayout: true,
                  tabSize: 2,
                  wordWrap: 'on',
                  padding: { top: 16, bottom: 16 },
                }}
              />
            </div>
          </div>

          {/* Results Panel */}
          <div className="h-1/2 border-t border-gray-200 flex flex-col">
            {/* Results Header */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-gray-700">Results</span>
                {results && (
                  <>
                    <span className="text-xs text-gray-500">
                      {results.row_count} row{results.row_count !== 1 ? 's' : ''}
                      {results.truncated && ' (truncated)'}
                    </span>
                    <span className="text-xs text-gray-500 flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {results.execution_time_ms}ms
                    </span>
                  </>
                )}
              </div>

              {isRunning && (
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{elapsedTime}s</span>
                </div>
              )}
            </div>

            {/* Results Table */}
            <div className="flex-1 overflow-auto" ref={parentRef}>
              {results && results.rows.length > 0 ? (
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-gray-50">
                    <tr>
                      {results.columns.map((col, i) => (
                        <th
                          key={i}
                          className="px-4 py-2 text-left font-medium text-gray-700 border-b border-gray-200 whitespace-nowrap bg-gray-50"
                        >
                          <div className="flex flex-col">
                            <span>{col.name}</span>
                            <span className="text-xs text-gray-500 font-normal">
                              {col.type}
                            </span>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {results.rows.map((row, rowIdx) => (
                      <tr
                        key={rowIdx}
                        className="hover:bg-gray-50 border-b border-gray-100"
                      >
                        {row.map((cell, cellIdx) => (
                          <td
                            key={cellIdx}
                            className="px-4 py-2 text-gray-700 whitespace-nowrap max-w-xs overflow-hidden text-ellipsis"
                          >
                            {cell === null ? (
                              <span className="text-gray-400 italic">NULL</span>
                            ) : (
                              String(cell)
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : results && results.rows.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-500">
                  Query returned no results
                </div>
              ) : !results && !error && (
                <div className="flex items-center justify-center h-full text-gray-500">
                  Run a query to see results
                </div>
              )}
            </div>
          </div>
        </div>

        {/* History Sidebar */}
        {showHistory && (
          <div className="w-1/4 border-l border-gray-200 flex flex-col bg-gray-50">
            <div className="p-4 border-b border-gray-200">
              <h2 className="font-medium text-gray-700">Query History</h2>
            </div>
            <div className="flex-1 overflow-y-auto">
              {history.length === 0 ? (
                <div className="p-4 text-gray-500 text-sm">
                  No query history yet
                </div>
              ) : (
                <div className="divide-y divide-gray-200">
                  {history.map((item) => (
                    <button
                      key={item.query_id}
                      onClick={() => handleSelectHistory(item)}
                      className="w-full p-4 text-left hover:bg-white transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className={`text-xs px-2 py-0.5 rounded ${
                            item.status === 'success'
                              ? 'bg-green-100 text-green-700'
                              : 'bg-red-100 text-red-700'
                          }`}
                        >
                          {item.status}
                        </span>
                        <span className="text-xs text-gray-500">
                          {item.duration_ms}ms
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 font-mono truncate">
                        {item.query_text.split('\n')[0]}
                      </p>
                      <p className="text-xs text-gray-500 mt-1 flex items-center gap-2">
                        {item.connection_name && (
                          <span className="px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                            {item.connection_name}
                          </span>
                        )}
                        {new Date(item.executed_at).toLocaleString()}
                      </p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}