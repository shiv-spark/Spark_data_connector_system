import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { 
  Sparkles, 
  Database, 
  Table,
  Loader2,
  RefreshCw,
  Plug,
  Server,
  Download,
  Upload,
  CheckCircle,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  FileSpreadsheet,
  ArrowRight
} from "lucide-react";
import { fetchDataGenConnections, fetchDataGenTables, fetchDataGenSchema, DataGenConnection } from "@/lib/api";
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

interface GenerationResult {
  success: boolean;
  table: string;
  rows: number;
  columns: string[];
  preview: Record<string, unknown>[];
  csv_path: string;
  loaded_to_db: boolean;
  db_table: string | null;
  connection_id: string | null;
  connection_name: string | null;
  error: string | null;
  generation_config: {
    table: string;
    rows: number;
    locale: string;
    columns: string[];
    hints: Record<string, string>;
  } | null;
}

const DB_ICONS: Record<string, string> = {
  postgresql: "🐘",
  mysql: "🐬",
  sqlite: "💾",
  snowflake: "❄️",
};

const getDBIcon = (type: string) => DB_ICONS[type] || "🗄️";

export default function DataGenerator() {
  const [description, setDescription] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<GenerationResult | null>(null);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");
  const [loadToDb, setLoadToDb] = useState(true);
  const [copied, setCopied] = useState(false);

  // Fetch available connections from data connector
  const { data: connections = [], isLoading: connectionsLoading, refetch: refetchConnections } = useQuery({
    queryKey: ["datagen-connections"],
    queryFn: fetchDataGenConnections,
    staleTime: 30000,
  });

  // Get selected connection info
  const selectedConnection = connections.find((c: DataGenConnection) => c.id === selectedConnectionId);

  // Fetch tables when connection is selected
  const { data: tables = [], isLoading: tablesLoading } = useQuery({
    queryKey: ["datagen-tables", selectedConnectionId],
    queryFn: () => fetchDataGenTables(selectedConnectionId),
    enabled: !!selectedConnectionId,
    staleTime: 60000,
  });

  const [selectedTable, setSelectedTable] = useState("");

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!description.trim() || isGenerating) return;

    setIsGenerating(true);
    setResult(null);
    
    // Include table name in description if selected
    let fullDescription = description;
    if (selectedTable && selectedTable !== "none") {
      fullDescription = `${description} in ${selectedTable} table`;
    }

    try {
      const response = await fetch("/api/datagen/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          description: fullDescription,
          connection_id: selectedConnectionId || undefined,
          load_to_db: loadToDb && !!selectedConnectionId
        })
      });
      
      if (!response.ok) {
        throw new Error(await response.text());
      }
      
      const data = await response.json();
      setResult(data);
    } catch (error) {
      console.error("Data generation error:", error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleLoadToDb = async () => {
    if (!result?.csv_path || !selectedConnectionId || !result?.table) return;
    
    setIsLoading(true);
    try {
      const response = await fetch("/api/datagen/load", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          csv_path: result.csv_path,
          table: result.table,
          connection_id: selectedConnectionId
        })
      });
      
      if (!response.ok) {
        throw new Error(await response.text());
      }
      
      const data = await response.json();
      setResult(prev => prev ? {
        ...prev,
        loaded_to_db: true,
        db_table: data.table,
        rows: data.rows_loaded
      } : null);
    } catch (error) {
      console.error("Load to database error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyPath = () => {
    if (result?.csv_path) {
      navigator.clipboard.writeText(result.csv_path);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const exampleDescriptions = [
    "Generate 50 users with name, email, phone and country",
    "Generate 100 orders with order_id, product_name, amount, order_date",
    "Generate 25 employees with name, department, salary, hire_date",
    "Generate 75 products with name, price, category, in_stock",
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-purple-500" />
            Data Generator
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Generate synthetic data in natural language and load to your database
          </p>
        </div>
        <Badge variant="secondary" className="bg-purple-50 text-purple-700">
          AI Powered
        </Badge>
      </div>

      {/* Connection Selector */}
      <Card className="border-slate-200 shadow-sm">
        <CardContent className="pt-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 flex-1">
              <Plug className="h-5 w-5 text-slate-500" />
              <div className="flex-1">
                <label className="text-sm font-medium text-slate-700 block mb-1">
                  Select Data Source (Optional - for loading to DB)
                </label>
                <Select 
                  value={selectedConnectionId} 
                  onValueChange={setSelectedConnectionId}
                >
                  <SelectTrigger className="w-full md:w-[400px]">
                    <SelectValue placeholder="Choose a database connection..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No connection (preview only)</SelectItem>
                    {connectionsLoading ? (
                      <SelectItem value="loading" disabled>
                        Loading connections...
                      </SelectItem>
                    ) : connections.length === 0 ? (
                      <SelectItem value="none" disabled>
                        No connections available. Create one in Connections page.
                      </SelectItem>
                    ) : (
                      connections.map((conn: DataGenConnection) => (
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
              <Server className="h-4 w-4 text-purple-500" />
              <span>Will load to:</span>
              <span className="font-medium text-slate-900">{selectedConnection?.name}</span>
              <Badge variant="outline" className="text-xs">
                {getDBIcon(selectedConnection?.type || '')} {selectedConnection?.type}
              </Badge>
            </div>
          )}

          {/* Table Selector */}
          {selectedConnectionId && (
            <div className="flex items-center gap-2 mt-3">
              <Table className="h-5 w-5 text-slate-500" />
              <div className="flex-1">
                <label className="text-sm font-medium text-slate-700 block mb-1">
                  Select Table (Optional - for schema-aware generation)
                </label>
                <Select 
                  value={selectedTable} 
                  onValueChange={setSelectedTable}
                >
                  <SelectTrigger className="w-full md:w-[400px]">
                    <SelectValue placeholder="Choose a table..." />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No table (use description only)</SelectItem>
                    {tablesLoading ? (
                      <SelectItem value="loading" disabled>
                        Loading tables...
                      </SelectItem>
                    ) : tables.length === 0 ? (
                      <SelectItem value="empty" disabled>
                        No tables found in database
                      </SelectItem>
                    ) : (
                      tables.map((table: string) => (
                        <SelectItem key={table} value={table}>
                          <span className="font-medium">{table}</span>
                        </SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Generation Area */}
        <div className="lg:col-span-2 space-y-6">
          {/* Input Card */}
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-slate-500" />
                Describe Data to Generate
              </CardTitle>
              <CardDescription>
                Describe the data you want to generate in natural language. The AI will create realistic synthetic data.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-0">
              <form onSubmit={handleGenerate} className="space-y-4">
                <div className="relative">
                  <Input
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder={description || "e.g., Generate 50 users with name, email, phone and country..."}
                    className="h-12 pr-12 text-base"
                    disabled={isGenerating}
                  />
                  <Button
                    type="submit"
                    size="icon"
                    className="absolute right-1 top-1 h-10 w-10 bg-purple-500 hover:bg-purple-600"
                    disabled={isGenerating || !description.trim()}
                  >
                    {isGenerating ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                  </Button>
                </div>

                {/* Example Descriptions */}
                <div className="space-y-2">
                  <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
                    Example Descriptions
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {exampleDescriptions.map((d, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => setDescription(d)}
                        className="text-xs px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-full transition"
                      >
                        {d.length > 40 ? d.substring(0, 40) + "..." : d}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Load to DB option */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="loadToDb"
                    checked={loadToDb}
                    onChange={(e) => setLoadToDb(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-300"
                  />
                  <label htmlFor="loadToDb" className="text-sm text-slate-700">
                    Automatically load to database after generation
                  </label>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Results Area */}
          {result && (
            <Card className={cn(
              "border shadow-sm",
              result.success ? "border-purple-200 bg-purple-50/30" : "border-rose-200 bg-rose-50/30"
            )}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-medium flex items-center gap-2">
                    {result.success ? (
                      <CheckCircle className="h-4 w-4 text-purple-500" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-rose-500" />
                    )}
                    {result.success ? "Data Generated Successfully" : "Generation Failed"}
                  </CardTitle>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      {result.rows} rows
                    </Badge>
                    <Badge variant="outline" className="text-xs">
                      {result.columns.length} columns
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="pt-0 space-y-4">
                {/* Generation Config */}
                {result.generation_config && (
                  <div className="p-3 bg-white rounded-lg border border-slate-200">
                    <div className="flex items-center gap-2 mb-2">
                      <Table className="h-4 w-4 text-slate-500" />
                      <span className="font-medium text-slate-800">
                        Table: {result.generation_config.table}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {result.generation_config.locale}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {result.generation_config.columns.map((col: string) => (
                        <span key={col} className="text-xs px-2 py-1 bg-slate-100 rounded">
                          {col}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* CSV Path */}
                {result.csv_path && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                        <Download className="h-3 w-3" />
                        Generated CSV
                      </span>
                      <button
                        onClick={handleCopyPath}
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
                            Copy Path
                          </>
                        )}
                      </button>
                    </div>
                    <pre className="p-3 bg-slate-900 text-slate-100 rounded-lg text-xs overflow-x-auto">
                      <code>{result.csv_path}</code>
                    </pre>
                  </div>
                )}

                {/* Preview Table */}
                {result.preview && result.preview.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                      <Table className="h-3 w-3" />
                      Preview (First 5 Rows)
                    </span>
                    <div className="border rounded-lg overflow-hidden bg-white">
                      <div className="max-h-64 overflow-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50 sticky top-0">
                            <tr>
                              {result.columns.map((col) => (
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
                            {result.preview.map((row, i) => (
                              <tr key={i} className="hover:bg-slate-50">
                                {result.columns.map((col, j) => (
                                  <td
                                    key={j}
                                    className="px-3 py-2 text-xs text-slate-700 border-b"
                                  >
                                    {row[col] === null || row[col] === undefined ? (
                                      <span className="text-slate-400">NULL</span>
                                    ) : (
                                      String(row[col]).substring(0, 30)
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

                {/* Load to DB Button */}
                {result.success && !result.loaded_to_db && selectedConnectionId && (
                  <Button 
                    onClick={handleLoadToDb}
                    disabled={isLoading}
                    className="w-full bg-purple-500 hover:bg-purple-600"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Loading to Database...
                      </>
                    ) : (
                      <>
                        <Upload className="h-4 w-4 mr-2" />
                        Load to {selectedConnection?.name}
                      </>
                    )}
                  </Button>
                )}

                {/* Load Status */}
                {result.loaded_to_db && (
                  <div className="p-3 bg-green-50 border border-green-200 rounded-lg flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span className="text-sm text-green-700">
                      Successfully loaded {result.rows} rows to table <strong>{result.db_table}</strong>
                    </span>
                  </div>
                )}

                {/* Error */}
                {result.error && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg">
                    <p className="text-sm text-rose-700">{result.error}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Instructions */}
          <Card className="border-slate-200 shadow-sm bg-gradient-to-br from-purple-50/50 to-indigo-50/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-slate-800">
                How to Use
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <ol className="space-y-2 text-sm text-slate-600 list-decimal list-inside">
                <li>Select a database connection (optional for preview)</li>
                <li>Describe the data you want to generate</li>
                <li>Click generate to create synthetic data</li>
                <li>Preview the generated data</li>
                <li>Load to your database if connection selected</li>
              </ol>
            </CardContent>
          </Card>

          {/* Tips */}
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-slate-800">
                Tips for Better Results
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <ul className="space-y-2 text-sm text-slate-600">
                <li className="flex items-start gap-2">
                  <span className="text-purple-500 mt-0.5">•</span>
                  Specify column names explicitly in your description
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-500 mt-0.5">•</span>
                  Include data types or formats when relevant (e.g., dates, prices)
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-500 mt-0.5">•</span>
                  Maximum 1000 rows per generation
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-500 mt-0.5">•</span>
                  Table must exist in the database for loading
                </li>
              </ul>
            </CardContent>
          </Card>

          {/* Supported DB Types */}
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-slate-800">
                Supported Databases
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">PostgreSQL 🐘</Badge>
                <Badge variant="outline">MySQL 🐬</Badge>
                <Badge variant="outline">SQLite 💾</Badge>
                <Badge variant="outline">Snowflake ❄️</Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}