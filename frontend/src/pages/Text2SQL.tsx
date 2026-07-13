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

  const { data: connections = [], isLoading: connectionsLoading, refetch: refetchConnections } = useQuery({
    queryKey: ["text2sql-connections"],
    queryFn: fetchText2SQLConnections,
    staleTime: 30000,
  });

  const { data: tablesData, isLoading: tablesLoading } = useQuery({
    queryKey: ["text2sql-tables", selectedConnectionId],
    queryFn: () => fetchText2SQLTables(selectedConnectionId || undefined),
    enabled: !!selectedConnectionId,
    staleTime: 60000,
  });

  const tables = tablesData || [];

  const selectedConnection = connections.find((c: Text2SQLConnection) => c.id === selectedConnectionId);

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
    } catch (error: any) {
      console.error("Text2SQL error:", error);
      const errMsg = error?.response?.data?.detail || error?.message || "An error occurred";
      setResult({
        success: false,
        run_id: "",
        question: question,
        sql: null,
        validation_status: "ERROR",
        execution_status: "ERROR",
        row_count: 0,
        execution_result: null,
        summary: null,
        llm_latency: 0,
        execution_latency: 0,
        total_time: 0,
        error: errMsg
      });
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-emerald-500" />
            Text-to-SQL
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Ask questions about your data in natural language
          </p>
        </div>
        <div className="flex items-center gap-3">
          {stats && (
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1">
                <CheckCircle className="h-4 w-4 text-emerald-500" />
                {stats.successful_runs} successful
              </span>
              <span className="flex items-center gap-1">
                <History className="h-4 w-4 text-muted-foreground" />
                {stats.total_runs} total
              </span>
            </div>
          )}
          <Badge variant="secondary" className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
            AI Powered
          </Badge>
        </div>
      </div>

      <Card className="border-border shadow-sm">
        <CardContent className="pt-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 flex-1">
              <Plug className="h-5 w-5 text-muted-foreground" />
              <div className="flex-1">
                <label className="text-sm font-medium text-foreground block mb-1">
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
                            <span className="text-muted-foreground text-xs">({conn.type})</span>
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
            <div className="mt-3 p-3 bg-muted/50 rounded-lg flex items-center gap-2 text-sm text-muted-foreground">
              <Server className="h-4 w-4 text-emerald-500" />
              <span>Connected to:</span>
              <span className="font-medium text-foreground">{selectedConnection.name}</span>
              <Badge variant="outline" className="text-xs">
                {getDBIcon(selectedConnection.type)} {selectedConnection.type}
              </Badge>
              {tables.length > 0 && (
                <span className="text-muted-foreground">
                  • {tables.length} tables available
                </span>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          <Card className="border-border shadow-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-muted-foreground" />
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

                {selectedConnectionId && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Example Questions
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {exampleQuestions.map((q, i) => (
                        <button
                          key={i}
                          type="button"
                          onClick={() => setQuestion(q)}
                          className="text-xs px-3 py-1.5 bg-muted hover:bg-muted/80 text-foreground rounded-full transition"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {!selectedConnectionId && (
                  <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 rounded-lg text-sm text-amber-700 dark:text-amber-300">
                    Please select a database connection above to start querying.
                  </div>
                )}
              </form>
            </CardContent>
          </Card>

          {result && result.error && result.error.includes("not supported") && (
            <Card className="border-border shadow-sm">
              <CardContent className="pt-4">
                <p className="text-sm text-muted-foreground">{result.error}</p>
              </CardContent>
            </Card>
          )}

          {result && !result.error?.includes("not supported") && (
            <Card className={cn(
              "border shadow-sm",
              result.success 
                ? "border-emerald-200 dark:border-emerald-800 bg-emerald-50/30 dark:bg-emerald-950/20" 
                : "border-rose-200 dark:border-rose-800 bg-rose-50/30 dark:bg-rose-950/20"
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
                      <Table className="h-3 w-3 mr-1" />
                      {result.row_count ?? 0} rows
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0 space-y-4">
                {result.summary && (
                  <div className="p-3 bg-card rounded-lg border border-border">
                    <p className="text-sm text-foreground">{result.summary}</p>
                  </div>
                )}

                {result.sql && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                        <Code className="h-3 w-3" />
                        Generated SQL
                      </span>
                      <button
                        onClick={handleCopySQL}
                        className="text-xs flex items-center gap-1 text-muted-foreground hover:text-foreground"
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
                    <pre className="p-3 bg-slate-900 dark:bg-slate-950 text-slate-100 rounded-lg text-xs overflow-x-auto">
                      <code>{result.sql}</code>
                    </pre>
                  </div>
                )}

                {result.execution_result && result.execution_result.rows && result.execution_result.rows.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                      <Table className="h-3 w-3" />
                      Results
                    </span>
                    <div className="border border-border rounded-lg overflow-hidden bg-card">
                      <div className="max-h-64 overflow-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-muted sticky top-0">
                            <tr>
                              {result.execution_result.columns.map((col) => (
                                <th
                                  key={col}
                                  className="px-3 py-2 text-left text-xs font-medium text-muted-foreground border-b border-border"
                                >
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {result.execution_result.rows.map((row, i) => (
                              <tr key={i} className="hover:bg-muted/50">
                                {row.map((cell: any, j: number) => (
                                  <td
                                    key={j}
                                    className="px-3 py-2 text-xs text-foreground border-b border-border"
                                  >
                                    {cell === null ? (
                                      <span className="text-muted-foreground">NULL</span>
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

                {result.error && (
                  <div className="p-3 bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-800 rounded-lg">
                    <p className="text-sm text-rose-700 dark:text-rose-300">{result.error}</p>
                  </div>
                )}

                <div className="flex items-center gap-4 text-xs text-muted-foreground pt-2 border-t border-border">
                  <span>LLM: {(result.llm_latency ?? 0).toFixed(2)}s</span>
                  <span>Execution: {(result.execution_latency ?? 0).toFixed(2)}s</span>
                  <span>Status: {result.validation_status}</span>
                </div>
              </CardContent>
            </Card>
          )}

          {history.length > 0 && (
            <Card className="border-border shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <History className="h-4 w-4 text-muted-foreground" />
                  Recent Queries
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="space-y-2">
                  {history.map((item, i) => (
                    <button
                      key={i}
                      onClick={() => setQuestion(item.question)}
                      className="w-full text-left p-3 rounded-lg border border-border hover:border-emerald-300 dark:hover:border-emerald-700 hover:bg-emerald-50/30 dark:hover:bg-emerald-950/20 transition text-sm"
                    >
                      <p className="font-medium text-foreground mb-1">{item.question}</p>
                      <code className="text-xs text-muted-foreground block truncate">
                        {item.sql}
                      </code>
                    </button>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card className="border-border shadow-sm">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <Database className="h-4 w-4 text-muted-foreground" />
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
                  <div className="text-center py-4 text-muted-foreground text-sm">
                    No connection selected
                  </div>
                ) : tablesLoading ? (
                  <div className="flex items-center justify-center py-4">
                    <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  </div>
                ) : tables.length === 0 ? (
                  <div className="text-center py-4 text-muted-foreground text-sm">
                    No tables found
                  </div>
                ) : (
                  tables.map((table: string) => (
                    <div
                      key={table}
                      className="flex items-center gap-2 px-2 py-1.5 rounded text-sm text-foreground hover:bg-muted"
                    >
                      <Table className="h-3.5 w-3.5 text-muted-foreground" />
                      {table}
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          {stats && (
            <Card className="border-border shadow-sm">
              <CardHeader className="pb-3">
                <CardTitle className="text-base font-medium flex items-center gap-2">
                  <BarChart3 className="h-4 w-4 text-muted-foreground" />
                  Query Statistics
                </CardTitle>
              </CardHeader>
              <CardContent className="pt-0">
                <div className="grid grid-cols-2 gap-4">
                  <div className="p-3 bg-muted/50 rounded-lg">
                    <p className="text-2xl font-bold text-foreground">{stats.total_runs}</p>
                    <p className="text-xs text-muted-foreground">Total Queries</p>
                  </div>
                  <div className="p-3 bg-emerald-50 dark:bg-emerald-950/30 rounded-lg">
                    <p className="text-2xl font-bold text-emerald-700 dark:text-emerald-400">{stats.successful_runs}</p>
                    <p className="text-xs text-emerald-600 dark:text-emerald-500">Successful</p>
                  </div>
                  <div className="p-3 bg-rose-50 dark:bg-rose-950/30 rounded-lg">
                    <p className="text-2xl font-bold text-rose-700 dark:text-rose-400">{stats.failed_runs}</p>
                    <p className="text-xs text-rose-600 dark:text-rose-500">Failed</p>
                  </div>
                  <div className="p-3 bg-blue-50 dark:bg-blue-950/30 rounded-lg">
                    <p className="text-2xl font-bold text-blue-700 dark:text-blue-400">
                      {stats.avg_llm_latency?.toFixed(2) || 0}s
                    </p>
                    <p className="text-xs text-blue-600 dark:text-blue-500">Avg Latency</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="border-border shadow-sm bg-gradient-to-br from-emerald-50/50 to-teal-50/50 dark:from-emerald-950/30 dark:to-teal-950/30">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-foreground">
                Tips for Better Results
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <ul className="space-y-2 text-sm text-muted-foreground">
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
