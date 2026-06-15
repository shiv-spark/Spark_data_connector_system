import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { 
  MessageSquare, 
  Send, 
  Database, 
  Code, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  BarChart3,
  Table,
  Sparkles,
  Loader2,
  History,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Server,
  RefreshCw,
  Plug
} from "lucide-react";
import { askText2SQL, fetchText2SQLTables, fetchText2SQLStats, fetchText2SQLConnections, Text2SQLConnection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface QueryResult {
  success: boolean;
  run_id: string;
  question: string;
  sql: string | null;
  validation_status: string;
  execution_status: string;
  row_count: number;
  execution_result: {
    columns: string[];
    rows: any[];
    execution_time: number;
  } | null;
  summary: string | null;
  llm_latency: number;
  execution_latency: number;
  total_time: number;
  error: string | null;
}

interface QueryHistory {
  question: string;
  sql: string;
  timestamp: Date;
  status: string;
}

// Database type icons
const DB_ICONS: Record<string, string> = {
  postgresql: "🐘",
  mysql: "🐬",
  sqlite: "💾",
  snowflake: "❄️",
};

const getDBIcon = (type: string) => DB_ICONS[type] || "🗄️";

export default function Text2SQL() {
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<QueryResult | null>(null);
  const [history, setHistory] = useState<QueryHistory[]>([]);
  const [showSchema, setShowSchema] = useState(false);
  const [copied, setCopied] = useState(false);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");

  // Fetch available connections
  const { data: connections = [], isLoading: connectionsLoading, refetch: refetchConnections } = useQuery({
    queryKey: ["text2sql-connections"],
    queryFn: fetchText2SQLConnections,
    staleTime: 30000,
  });

  // Fetch tables for selected connection
  const { data: tablesData, isLoading: tablesLoading } = useQuery({
    queryKey: ["text2sql-tables", selectedConnectionId],
    queryFn: () => fetchText2SQLTables(selectedConnectionId || undefined),
    enabled: !!selectedConnectionId,
    staleTime: 60000,
  });

  const tables = tablesData || [];

  // Get selected connection info
  const selectedConnection = connections.find((c: Text2SQLConnection) => c.id === selectedConnectionId);

  // Fetch stats
  const { data: stats } = useQuery({
    queryKey: ["text2sql-stats"],
    queryFn: fetchText2SQLStats,
    refetchInterval: 30000,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;
    if (!selectedConnectionId) {
      alert("Please select a database connection first");
      return;
    }

    setIsLoading(true);
    try {
      const response = await askText2SQL({ 
        question, 
        connection_id: selectedConnectionId,
        auto_execute: true 
      });
      setResult(response);
      
      if (response.sql) {
        setHistory(prev => [{
          question: response.question,
          sql: response.sql,
          timestamp: new Date(),
          status: response.execution_status
        }, ...prev].slice(0, 10));
      }
    } catch (error) {
      console.error("Text2SQL error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopySQL = () => {
    if (result?.sql) {
      navigator.clipboard.writeText(result.sql);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const exampleQuestions = [
    "How many rows are in the main table?",
    "Show me the top 10 records by date",
    "What is the average value?",
    "List all unique values in the status column",
    "Count records grouped by category",
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-emerald-500" />
            Text-to-SQL
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Ask questions about your data in natural language
          </p>
        </div>
        <div className="flex items-center gap-3">
          {stats && (
            <div className="flex items-center gap-4 text-sm text-slate-600">
              <span className="flex items-center gap-1">
                <CheckCircle className="h-4 w-4 text-emerald-500" />
                {stats.successful_runs} successful
              </span>
              <span className="flex items-center gap-1">
                <History className="h-4 w-4 text-slate-400" />
                {stats.total_runs} total
              </span>
            </div>
          )}
          <Badge variant="secondary" className="bg-emerald-50 text-emerald-700">
            AI Powered
          </Badge>
        </div>
      </div>

      {/* Connection Selector */}
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="pt-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 flex-1">
              <Plug className="h-5 w-5 text-slate-500" />
              <div className="flex-1">
                <label className="text-sm font-medium text-slate-700 block mb-1">
                  Select Data Source
                </label>
                <Select 
                  value={selectedConnectionId} 
                  onValueChange={setSelectedConnectionId}
                >
                  <SelectTrigger className="w-full md:w-[400px]">
                    <SelectValue placeholder="Choose a database connection..." />
                  </SelectTrigger>
                  <SelectContent>
                    {connectionsLoading ? (
                      <SelectItem value="loading" disabled>
                        Loading connections...
                      </SelectItem>
                    ) : connections.length === 0 ? (
                      <SelectItem value="none" disabled>
                        No connections available. Create one in Connections page.
                      </SelectItem>
                    ) : (
                      connections.map((conn: Text2SQLConnection) => (
                        <SelectItem key={conn.id} value={conn.id}>
                          <span className="flex items-center gap-2">
                            <span>{getDBIcon(conn.type)}</span>
                            <span className="font-medium">{conn.name}</span>
                            <span className="text-slate-400 text-xs">({conn.type})</span>
                          </span>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button 
              variant="outline" 
              size="sm" 
              onClick={() => refetchConnections()}
              disabled={connectionsLoading}
            >
              <RefreshCw className={cn("h-4 w-4", connectionsLoading && "animate-spin")} />
            </Button>
          </div>
          
          {selectedConnection && (
            <div className="mt-3 p-3 bg-slate-50 rounded-lg flex items-center gap-2 text-sm text-slate-600">
              <Server className="h-4 w-4 text-emerald-500" />
              <span>Connected to:</span>
              <span className="font-medium text-slate-900">{selectedConnection.name}</span>
              <Badge variant="outline" className="text-xs">
                {getDBIcon(selectedConnection.type)} {selectedConnection.type}
              </Badge>
              {tables.length > 0 && (
                <span className="text-slate-400">
                  • {tables.length} tables available
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Query Area */}
        <div className="lg:col-span-2 space-y-6">
          {/* Input Card */}
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-slate-500" />
                Ask a Question
              </CardTitle>
              <CardDescription>
                Type your question in natural language. The AI will generate and execute the SQL.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="relative">
                  <Input
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder={selectedConnectionId 
                      ? "e.g., How many pipeline runs today?" 
                      : "Select a connection first..."
                    }
                    className="h-12 pr-12 text-base"
                    disabled={isLoading || !selectedConnectionId}
                  />
                  <Button
                    type="submit"
                    size="icon"
                    className="absolute right-1 top-1 h-10 w-10 bg-emerald-500 hover:bg-emerald-600"
                    disabled={isLoading || !question.trim() || !selectedConnectionId}
                  >
                    {isLoading ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </Button>
                </div>

                {/* Example Questions */}
                {selectedConnectionId && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                      Example Questions
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {exampleQuestions.map((q, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setQuestion(q)}
                          className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-full transition"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {!selectedConnectionId && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-700">
                    Please select a database connection above to start querying.
                  </div>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Results Area */}
          {result && (
            <Card className={cn(
              "border shadow-sm",
              result.success ? "border-emerald-200 bg-emerald-50/30" : "border-rose-200 bg-rose-50/30"
            )}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-medium flex items-center gap-2">
                    {result.success ? (
                      <CheckCircle className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-rose-500" />
                    )}
                    {result.success ? "Query Executed Successfully" : "Query Failed"}
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      <Clock className="h-3 w-3 mr-1" />
                      {result.total_time.toFixed(2)}s
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {result.row_count} rows
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0 space-y-4">
                {/* Summary */}
                {result.summary && (
                  <div className="p-3 bg-white rounded-lg border border-slate-200">
                    <p className="text-sm text-slate-700">{result.summary}</p>
                  </div>
                )}

                {/* SQL Code */}
                {result.sql && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                        <Code className="h-3 w-3" />
                        Generated SQL
                      </span>
                      <button
                        onClick={handleCopySQL}
                        className="text-xs flex items-center gap-1 text-slate-500 hover:text-slate-700"
                      >
                        {copied ? (
                          <>
                            <Check className="h-3 w-3" />
                            Copied!
                          </>
                        ) : (
                          <>
                            <Copy className="h-3 w-3" />
                            Copy
                          </>
                        )}
                      </button>
                    </div>
                    <pre className="p-3 bg-slate-900 text-slate-100 rounded-lg text-xs overflow-x-auto">
                      <code>{result.sql}</code>
                    </pre>
                  </div>
                )}

                {/* Results Table */}
                {result.execution_result && result.execution_result.rows.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                      <Table className="h-3 w-3" />
                      Results
                    </span>
                    <div className="border rounded-lg overflow-hidden bg-white">
                      <div className="max-h-64 overflow-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50 sticky top-0">
                            <tr>
                              {result.execution_result.columns.map((col) => (
                                <th
                                  key={col}
                                  className="px-3 py-2 text-left text-xs font-medium text-slate-600 border-b"
                                >
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {result.execution_result.rows.map((row, i) => (
                              <tr key={i} className="hover:bg-slate-50">
                                {row.map((cell: any, j: number) => (
                                  <td
                                    key={j}
                                    className="px-3 py-2 text-xs text-slate-700 border-b"
                                  >
                                    {cell === null ? (
                                      <span className="text-slate-400">NULL</span>
                                    ) : (
                                      String(cell).substring(0, 50)
                                    )}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                )}

                {/* Error */}
                {result.error && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg">
                    <p className="text-sm text-rose-700">{result.error}</p>
                  </div>
                )}

                {/* Metadata */}
                <div className="flex items-center gap-4 text-xs text-slate-500 pt-2 border-t">
                  <span>LLM: {result.llm_latency.toFixed(2)}s</span>
                  <span>Execution: {result.execution_latency.toFixed(2)}s</span>
                  <span>Status: {result.validation_status}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Query History */}
          {history.length > 0 && (
            <Card className="border-slate-200 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <History className="h-4 w-4 text-slate-500" />
                  Recent Queries
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {history.map((item, i) => (
                    <button
                      key={i}
                      onClick={() => setQuestion(item.question)}
                      className="w-full text-left p-3 rounded-lg border border-slate-200 hover:border-emerald-300 hover:bg-emerald-50/30 transition text-sm"
                    >
                      <p className="font-medium text-slate-800 mb-1">{item.question}</p>
                      <code className="text-xs text-slate-500 block truncate">
                        {item.sql}
                      </code>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Schema Explorer */}
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <Database className="h-4 w-4 text-slate-500" />
                  Database Schema
                </CardTitle>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowSchema(!showSchema)}
                  disabled={!selectedConnectionId}
                >
                  {showSchema ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
              </div>
              <CardDescription>
                {selectedConnectionId 
                  ? (tablesLoading 
                    ? "Loading tables..." 
                    : `${tables.length} tables available`
                  )
                  : "Select a connection to view tables"
                }
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="space-y-1 max-h-64 overflow-auto">
                {!selectedConnectionId ? (
                  <div className="text-center py-4 text-slate-400 text-sm">
                    No connection selected
                  </div>
                ) : tablesLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                  </div>
                ) : tables.length === 0 ? (
                  <div className="text-center py-4 text-slate-400 text-sm">
                    No tables found
                  </div>
                ) : (
                  tables.map((table: string) => (
                    <div
                      key={table}
                      className="flex items-center gap-2 px-2 py-1.5 rounded text-sm text-slate-700 hover:bg-slate-100"
                    >
                      <Table className="h-3.5 w-3.5 text-slate-400" />
                      {table}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {/* Quick Stats */}
          {stats && (
            <Card className="border-slate-200 shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-slate-500" />
                  Query Statistics
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-slate-50 rounded-lg">
                    <p className="text-2xl font-bold text-slate-900">{stats.total_runs}</p>
                    <p className="text-xs text-slate-500">Total Queries</p>
                  </div>
                  <div className="p-3 bg-emerald-50 rounded-lg">
                    <p className="text-2xl font-bold text-emerald-700">{stats.successful_runs}</p>
                    <p className="text-xs text-emerald-600">Successful</p>
                  </div>
                  <div className="p-3 bg-rose-50 rounded-lg">
                    <p className="text-2xl font-bold text-rose-700">{stats.failed_runs}</p>
                    <p className="text-xs text-rose-600">Failed</p>
                  </div>
                  <div className="p-3 bg-blue-50 rounded-lg">
                    <p className="text-2xl font-bold text-blue-700">
                      {stats.avg_llm_latency?.toFixed(2) || 0}s
                    </p>
                    <p className="text-xs text-blue-600">Avg Latency</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Usage Tips */}
          <Card className="border-slate-200 shadow-sm bg-gradient-to-br from-emerald-50/50 to-teal-50/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-slate-800">
                Tips for Better Results
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <ul className="space-y-2 text-sm text-slate-600">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">•</span>
                  Be specific about table names when possible
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">•</span>
                  Use filters like "from today" or "last week"
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">•</span>
                  Ask for specific metrics: count, average, top N
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-500 mt-0.5">•</span>
                  Questions about joins across tables are supported
                </li>
              </ul>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
