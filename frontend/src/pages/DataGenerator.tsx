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
import { PageHeader } from "@/components/PageHeader";

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

  const { data: connections = [], isLoading: connectionsLoading, refetch: refetchConnections } = useQuery({
    queryKey: ["datagen-connections"],
    queryFn: fetchDataGenConnections,
    staleTime: 30000,
  });

  const selectedConnection = connections.find((c: DataGenConnection) => c.id === selectedConnectionId);

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
      <PageHeader
        icon={Sparkles}
        eyebrow="Intelligence"
        title="Data Generator"
        description="Describe the rows you need and load realistic test data into a table."
        actions={
          <Badge variant="secondary" className="bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300">
            AI Powered
          </Badge>
        }
      />

      <Card className="border-border shadow-sm">
        <CardContent className="pt-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-2 flex-1">
              <Plug className="h-5 w-5 text-muted-foreground" />
              <div className="flex-1">
                <label className="text-sm font-medium text-foreground block mb-1">
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
              <Server className="h-4 w-4 text-purple-500 dark:text-purple-400" />
              <span>Will load to:</span>
              <span className="font-medium text-foreground">{selectedConnection?.name}</span>
              <Badge variant="outline" className="text-xs">
                {getDBIcon(selectedConnection?.type || '')} {selectedConnection?.type}
              </Badge>
            </div>
          )}

          {selectedConnectionId && (
            <div className="flex items-center gap-2 mt-3">
              <Table className="h-5 w-5 text-muted-foreground" />
              <div className="flex-1">
                <label className="text-sm font-medium text-foreground block mb-1">
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
        <div className="lg:col-span-2 space-y-6">
          <Card className="border-border shadow-sm">
            <CardHeader className="pb-4">
              <CardTitle className="text-base font-medium flex items-center gap-2">
                <FileSpreadsheet className="h-4 w-4 text-muted-foreground" />
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
                    className="absolute right-1 top-1 h-10 w-10 bg-purple-500 hover:bg-purple-600 dark:bg-purple-600 dark:hover:bg-purple-700"
                    disabled={isGenerating || !description.trim()}
                  >
                    {isGenerating ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4" />
                    )}
                  </Button>
                </div>

                <div className="space-y-2">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Example Descriptions
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {exampleDescriptions.map((d, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => setDescription(d)}
                        className="text-xs px-3 py-1.5 bg-muted hover:bg-muted/80 text-foreground rounded-full transition"
                      >
                        {d.length > 40 ? d.substring(0, 40) + "..." : d}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="loadToDb"
                    checked={loadToDb}
                    onChange={(e) => setLoadToDb(e.target.checked)}
                    className="w-4 h-4 rounded border-border"
                  />
                  <label htmlFor="loadToDb" className="text-sm text-foreground">
                    Automatically load to database after generation
                  </label>
                </div>
              </form>
            </CardContent>
          </Card>

          {result && (
            <Card className={cn(
              "border shadow-sm",
              result.success 
                ? "border-purple-200 dark:border-purple-800 bg-purple-50/30 dark:bg-purple-950/30" 
                : "border-rose-200 dark:border-rose-800 bg-rose-50/30 dark:bg-rose-950/30"
            )}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-medium flex items-center gap-2">
                    {result.success ? (
                      <CheckCircle className="h-4 w-4 text-purple-500 dark:text-purple-400" />
                    ) : (
                      <AlertCircle className="h-4 w-4 text-rose-500 dark:text-rose-400" />
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
                {result.generation_config && (
                  <div className="p-3 bg-card rounded-lg border border-border">
                    <div className="flex items-center gap-2 mb-2">
                      <Table className="h-4 w-4 text-muted-foreground" />
                      <span className="font-medium text-foreground">
                        Table: {result.generation_config.table}
                      </span>
                      <Badge variant="outline" className="text-xs">
                        {result.generation_config.locale}
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {result.generation_config.columns.map((col: string) => (
                        <span key={col} className="text-xs px-2 py-1 bg-muted rounded text-foreground">
                          {col}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {result.csv_path && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                        <Download className="h-3 w-3" />
                        Generated CSV
                      </span>
                      <button
                        onClick={handleCopyPath}
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
                            Copy Path
                          </>
                        )}
                      </button>
                    </div>
                    <pre className="p-3 bg-slate-900 dark:bg-slate-950 text-slate-100 dark:text-slate-200 rounded-lg text-xs overflow-x-auto">
                      <code>{result.csv_path}</code>
                    </pre>
                  </div>
                )}

                {result.preview && result.preview.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                      <Table className="h-3 w-3" />
                      Preview (First 5 Rows)
                    </span>
                    <div className="border border-border rounded-lg overflow-hidden bg-card">
                      <div className="max-h-64 overflow-auto">
                        <table className="w-full text-sm">
                          <thead className="bg-muted sticky top-0">
                            <tr>
                              {result.columns.map((col) => (
                                <th
                                  key={col}
                                  className="px-3 py-2 text-left text-xs font-medium text-foreground border-b border-border"
                                >
                                  {col}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {result.preview.map((row, i) => (
                              <tr key={i} className="hover:bg-muted/50">
                                {result.columns.map((col, j) => (
                                  <td
                                    key={j}
                                    className="px-3 py-2 text-xs text-foreground border-b border-border"
                                  >
                                    {row[col] === null || row[col] === undefined ? (
                                      <span className="text-muted-foreground">NULL</span>
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

                {result.success && !result.loaded_to_db && selectedConnectionId && (
                  <Button 
                    onClick={handleLoadToDb}
                    disabled={isLoading}
                    className="w-full bg-purple-500 hover:bg-purple-600 dark:bg-purple-600 dark:hover:bg-purple-700"
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

                {result.loaded_to_db && (
                  <div className="p-3 bg-green-50 dark:bg-green-950/50 border border-green-200 dark:border-green-800 rounded-lg flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500 dark:text-green-400" />
                    <span className="text-sm text-green-700 dark:text-green-300">
                      Successfully loaded {result.rows} rows to table <strong>{result.db_table}</strong>
                    </span>
                  </div>
                )}

                {result.error && (
                  <div className="p-3 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 rounded-lg">
                    <p className="text-sm text-rose-700 dark:text-rose-300">{result.error}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        <div className="space-y-6">
          <Card className="border-border shadow-sm bg-gradient-to-br from-purple-50/50 to-indigo-50/50 dark:from-purple-950/30 dark:to-indigo-950/30">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-foreground">
                How to Use
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <ol className="space-y-2 text-sm text-muted-foreground list-decimal list-inside">
                <li>Select a database connection (optional for preview)</li>
                <li>Describe the data you want to generate</li>
                <li>Click generate to create synthetic data</li>
                <li>Preview the generated data</li>
                <li>Load to your database if connection selected</li>
              </ol>
            </CardContent>
          </Card>

          <Card className="border-border shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-foreground">
                Tips for Better Results
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <ul className="space-y-2 text-sm text-muted-foreground">
                <li className="flex items-start gap-2">
                  <span className="text-purple-500 dark:text-purple-400 mt-0.5">•</span>
                  Specify column names explicitly in your description
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-500 dark:text-purple-400 mt-0.5">•</span>
                  Include data types or formats when relevant (e.g., dates, prices)
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-500 dark:text-purple-400 mt-0.5">•</span>
                  Maximum 1000 rows per generation
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-purple-500 dark:text-purple-400 mt-0.5">•</span>
                  Table must exist in the database for loading
                </li>
              </ul>
            </CardContent>
          </Card>

          <Card className="border-border shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium text-foreground">
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
