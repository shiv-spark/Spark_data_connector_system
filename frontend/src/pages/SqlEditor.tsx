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
  Sparkles,
  Save,
  Trash2,
  Pencil,
  Check,
  X as XIcon,
} from 'lucide-react';
import {
  executeQuery,
  cancelQuery,
  getQueryHistory,
  formatSql,
  getConnections,
  saveQuery,
  listSavedQueries,
  updateSavedQuery,
  deleteSavedQuery,
  fetchSqlQueryHistory,
  restoreSqlQueryVersion,
  type SqlExecuteResponse,
  type QueryHistoryItem,
  type SqlError,
  type SavedQueryItem,
} from '../lib/sql-api';
import { AiQueryDialog } from '@/components/AiQueryDialog';
import { HistoryPanel } from '@/components/console/HistoryPanel';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';

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
  const [historyTab, setHistoryTab] = useState<'runs' | 'saved'>('runs');
  const [savedQueries, setSavedQueries] = useState<SavedQueryItem[]>([]);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveDialogName, setSaveDialogName] = useState('');
  const [renamingQueryId, setRenamingQueryId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const [versionHistoryQueryId, setVersionHistoryQueryId] = useState<string | null>(null);
  const [elapsedTime, setElapsedTime] = useState(0);
  const [currentQueryId, setCurrentQueryId] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);
  const parentRef = useRef<HTMLDivElement>(null);
  const [showAiDialog, setShowAiDialog] = useState(false);

  useEffect(() => {
    loadConnections();
    loadHistory();
    loadSavedQueries();
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

  const loadSavedQueries = async () => {
    try {
      const data = await listSavedQueries();
      setSavedQueries(data);
    } catch (err) {
      console.error('Failed to load saved queries:', err);
    }
  };

  const handleOpenSaveDialog = () => {
    if (!selectedConnection || !query.trim()) return;
    setSaveDialogName('');
    setShowSaveDialog(true);
  };

  const handleConfirmSaveQuery = async () => {
    if (!selectedConnection || !saveDialogName.trim()) return;
    try {
      await saveQuery({
        connection_id: selectedConnection.id,
        name: saveDialogName.trim(),
        query_text: query,
      });
      setShowSaveDialog(false);
      await loadSavedQueries();
      setShowHistory(true);
      setHistoryTab('saved');
    } catch (err) {
      console.error('Failed to save query:', err);
    }
  };

  const handleSelectSavedQuery = (item: SavedQueryItem) => {
    const conn = connections.find((c) => c.id === item.connection_id);
    if (conn) {
      setSelectedConnection(conn);
      setResults(null);
      setError(null);
    }
    setQuery(item.query_text);
  };

  const handleStartRename = (item: SavedQueryItem) => {
    setRenamingQueryId(item.id);
    setRenameDraft(item.name);
  };

  const handleConfirmRename = async (id: string) => {
    if (!renameDraft.trim()) return;
    try {
      await updateSavedQuery(id, { name: renameDraft.trim() });
      setRenamingQueryId(null);
      await loadSavedQueries();
    } catch (err) {
      console.error('Failed to rename saved query:', err);
    }
  };

  /** Saves the CURRENT editor text into an already-saved query — this is
      what actually creates a new version, since PUT is what history_store
      snapshots against. Renaming alone also goes through PUT/history. */
  const handleUpdateSavedQueryText = async (item: SavedQueryItem) => {
    try {
      await updateSavedQuery(item.id, { query_text: query });
      await loadSavedQueries();
    } catch (err) {
      console.error('Failed to update saved query:', err);
    }
  };

  const handleDeleteSavedQuery = async (id: string) => {
    if (!confirm('Delete this saved query? This cannot be undone.')) return;
    try {
      await deleteSavedQuery(id);
      await loadSavedQueries();
    } catch (err) {
      console.error('Failed to delete saved query:', err);
    }
  };

  const handleInsertAiSql = (sql: string) => {
    setQuery(sql);
    setError(null);
    setResults(null);
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
    <div className="flex flex-col h-screen bg-background text-foreground">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border bg-card">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-600 dark:text-blue-400" />
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
              className="appearance-none bg-background border border-border rounded-lg px-4 py-2 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-blue-400 text-foreground"
              disabled={isRunning}
            >
              <option value="">Select a connection...</option>
              {connections.map((conn) => (
                <option key={conn.id} value={conn.id}>
                  {conn.name} ({conn.source_type})
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground pointer-events-none" />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRunQuery}
            disabled={!selectedConnection || !query.trim() || isRunning}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 dark:bg-green-600 dark:hover:bg-green-700 disabled:bg-muted disabled:dark:bg-muted disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors"
          >
            {isRunning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            {isRunning ? 'Running...' : 'Run'}
          </button>

          {isRunning && (
            <button
              onClick={handleCancel}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 dark:bg-red-600 dark:hover:bg-red-700 rounded-lg text-sm font-medium text-white transition-colors"
            >
              <Square className="w-4 h-4" />
              Cancel
            </button>
          )}

          <button
            onClick={handleFormat}
            disabled={!query.trim() || isRunning}
            className="px-4 py-2 bg-secondary hover:bg-secondary/80 dark:bg-secondary dark:hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-secondary-foreground transition-colors border border-border"
          >
            Format
          </button>

          <button
            onClick={() => setShowAiDialog(true)}
            disabled={!selectedConnection || isRunning}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 dark:bg-purple-600 dark:hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-white transition-colors"
          >
            <Sparkles className="w-4 h-4" />
            Generate with AI
          </button>

          <button
            onClick={handleOpenSaveDialog}
            disabled={!selectedConnection || !query.trim()}
            className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 dark:bg-secondary dark:hover:bg-secondary/80 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-sm font-medium text-secondary-foreground transition-colors border border-border"
          >
            <Save className="w-4 h-4" />
            Save query
          </button>

          <button
            onClick={() => setShowHistory(!showHistory)}
            className="px-4 py-2 bg-secondary hover:bg-secondary/80 dark:bg-secondary dark:hover:bg-secondary/80 rounded-lg text-sm font-medium text-secondary-foreground transition-colors border border-border"
          >
            <History className="w-4 h-4" />
          </button>

          {results && (
            <button
              onClick={handleExport}
              className="flex items-center gap-2 px-4 py-2 bg-secondary hover:bg-secondary/80 dark:bg-secondary dark:hover:bg-secondary/80 rounded-lg text-sm font-medium text-secondary-foreground transition-colors border border-border"
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
        <div className={`flex-1 flex flex-col ${showHistory ? 'w-3/4' : 'w-full'} min-w-0`}>
          {/* Error Banner */}
          {error && (
            <div className="mx-6 mt-4 p-4 bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-500 dark:text-red-400 flex-shrink-0 mt-0.5" />
              <div>
                <p className="font-medium text-red-700 dark:text-red-400">{error.error_type}</p>
                <p className="text-red-600 dark:text-red-300 text-sm mt-1">{error.message}</p>
                {error.line && (
                  <p className="text-red-500 dark:text-red-400 text-xs mt-2">
                    Line {error.line}{error.column ? `, Column ${error.column}` : ''}
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Editor */}
          <div className="flex-1 p-4">
            <div className="h-full border border-border rounded-lg overflow-hidden bg-card">
              <Editor
                height="100%"
                language={getEditorLanguage()}
                value={query}
                onChange={(value) => setQuery(value || '')}
                onMount={handleEditorMount}
                theme="vs-dark"
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
          <div className="h-1/2 border-t border-border flex flex-col bg-card">
            {/* Results Header */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-border bg-muted/50">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-foreground">Results</span>
                {results && (
                  <>
                    <span className="text-xs text-muted-foreground">
                      {results.row_count} row{results.row_count !== 1 ? 's' : ''}
                      {results.truncated && ' (truncated)'}
                    </span>
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {results.execution_time_ms}ms
                    </span>
                  </>
                )}
              </div>

              {isRunning && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{elapsedTime}s</span>
                </div>
              )}
            </div>

            {/* Results Table */}
            <div className="flex-1 overflow-auto" ref={parentRef}>
              {results && results.rows.length > 0 ? (
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-muted/50">
                    <tr>
                      {results.columns.map((col, i) => (
                        <th
                          key={i}
                          className="px-4 py-2 text-left font-medium text-foreground border-b border-border whitespace-nowrap bg-muted/50"
                        >
                          <div className="flex flex-col">
                            <span>{col.name}</span>
                            <span className="text-xs text-muted-foreground font-normal">
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
                        className="hover:bg-muted/50 dark:hover:bg-muted/30 border-b border-border"
                      >
                        {row.map((cell, cellIdx) => (
                          <td
                            key={cellIdx}
                            className="px-4 py-2 text-foreground whitespace-nowrap max-w-xs overflow-hidden text-ellipsis"
                          >
                            {cell === null ? (
                              <span className="text-muted-foreground italic">NULL</span>
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
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Query returned no results
                </div>
              ) : !results && !error && (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  Run a query to see results
                </div>
              )}
            </div>
          </div>
        </div>

        {/* History Sidebar */}
        {showHistory && (
          <div className="w-1/4 border-l border-border flex flex-col bg-card shrink-0">
            <div className="border-b border-border flex">
              <button
                onClick={() => setHistoryTab('runs')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                  historyTab === 'runs'
                    ? 'text-foreground border-b-2 border-blue-600 dark:border-blue-400'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Runs
              </button>
              <button
                onClick={() => setHistoryTab('saved')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                  historyTab === 'saved'
                    ? 'text-foreground border-b-2 border-blue-600 dark:border-blue-400'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                Saved
              </button>
            </div>

            {historyTab === 'runs' ? (
              <div className="flex-1 overflow-y-auto">
                {history.length === 0 ? (
                  <div className="p-4 text-muted-foreground text-sm">
                    No query history yet
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {history.map((item) => (
                      <button
                        key={item.query_id}
                        onClick={() => handleSelectHistory(item)}
                        className="w-full p-4 text-left hover:bg-muted/50 dark:hover:bg-muted/30 transition-colors"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span
                            className={`text-xs px-2 py-0.5 rounded ${
                              item.status === 'success'
                                ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                                : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                            }`}
                          >
                            {item.status}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {item.duration_ms}ms
                          </span>
                        </div>
                        <p className="text-sm text-foreground font-mono truncate">
                          {item.query_text.split('\n')[0]}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1 flex items-center gap-2">
                          {item.connection_name && (
                            <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded text-xs">
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
            ) : (
              <div className="flex-1 overflow-y-auto">
                {savedQueries.length === 0 ? (
                  <div className="p-4 text-muted-foreground text-sm">
                    No saved queries yet — write a query and hit "Save query" above.
                  </div>
                ) : (
                  <div className="divide-y divide-border">
                    {savedQueries.map((item) => (
                      <div key={item.id} className="p-4 hover:bg-muted/50 dark:hover:bg-muted/30 transition-colors">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          {renamingQueryId === item.id ? (
                            <div className="flex items-center gap-1 flex-1 min-w-0">
                              <Input
                                autoFocus
                                value={renameDraft}
                                onChange={(e) => setRenameDraft(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleConfirmRename(item.id);
                                  if (e.key === 'Escape') setRenamingQueryId(null);
                                }}
                                className="h-7 text-sm"
                              />
                              <button
                                onClick={() => handleConfirmRename(item.id)}
                                className="p-1 text-green-600 hover:text-green-700"
                                aria-label="Confirm rename"
                              >
                                <Check className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => setRenamingQueryId(null)}
                                className="p-1 text-muted-foreground hover:text-foreground"
                                aria-label="Cancel rename"
                              >
                                <XIcon className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => handleSelectSavedQuery(item)}
                              className="text-sm font-medium text-foreground truncate text-left flex-1"
                              title="Load into editor"
                            >
                              {item.name}
                            </button>
                          )}
                        </div>

                        <button
                          onClick={() => handleSelectSavedQuery(item)}
                          className="block w-full text-left text-sm text-muted-foreground font-mono truncate mb-2"
                          title="Load into editor"
                        >
                          {item.query_text.split('\n')[0]}
                        </button>

                        <div className="flex items-center justify-between gap-2">
                          <p className="text-xs text-muted-foreground flex items-center gap-2 min-w-0">
                            {item.connection_name && (
                              <span className="px-1.5 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded text-xs shrink-0">
                                {item.connection_name}
                              </span>
                            )}
                            <span className="truncate">{new Date(item.updated_at).toLocaleString()}</span>
                          </p>
                          <div className="flex items-center gap-1 shrink-0">
                            <button
                              onClick={() => handleUpdateSavedQueryText(item)}
                              title="Save current editor text as a new version"
                              className="p-1.5 text-muted-foreground hover:text-foreground"
                            >
                              <Save className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleStartRename(item)}
                              title="Rename"
                              className="p-1.5 text-muted-foreground hover:text-foreground"
                            >
                              <Pencil className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => setVersionHistoryQueryId(item.id)}
                              title="Version history"
                              className="p-1.5 text-muted-foreground hover:text-foreground"
                            >
                              <History className="w-3.5 h-3.5" />
                            </button>
                            <button
                              onClick={() => handleDeleteSavedQuery(item.id)}
                              title="Delete"
                              className="p-1.5 text-muted-foreground hover:text-destructive"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Saved-query version history — separate panel so it doesn't replace the list above */}
        {versionHistoryQueryId && (
          <HistoryPanel
            queryKey={["sql-query-history", versionHistoryQueryId]}
            fetchHistory={() => fetchSqlQueryHistory(versionHistoryQueryId)}
            restoreVersion={async (versionId) => {
              const restored = await restoreSqlQueryVersion(versionHistoryQueryId, versionId);
              await loadSavedQueries();
              return restored;
            }}
            onClose={() => setVersionHistoryQueryId(null)}
            onRestored={() => loadSavedQueries()}
          />
        )}
      </div>

      {/* Save query dialog */}
      <Dialog open={showSaveDialog} onOpenChange={setShowSaveDialog}>
        <DialogContent className="sm:max-w-[420px]">
          <DialogHeader>
            <DialogTitle>Save query</DialogTitle>
          </DialogHeader>
          <label className="space-y-1 text-sm font-medium text-foreground">
            Name
            <Input
              autoFocus
              value={saveDialogName}
              onChange={(e) => setSaveDialogName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleConfirmSaveQuery()}
              placeholder="e.g. Monthly active users"
            />
          </label>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowSaveDialog(false)}>Cancel</Button>
            <Button onClick={handleConfirmSaveQuery} disabled={!saveDialogName.trim()}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AiQueryDialog
        open={showAiDialog}
        onOpenChange={setShowAiDialog}
        connectionId={selectedConnection?.id ?? null}
        connectionName={selectedConnection?.name ?? ''}
        onInsert={handleInsertAiSql}
      />
    </div>
  );
}
