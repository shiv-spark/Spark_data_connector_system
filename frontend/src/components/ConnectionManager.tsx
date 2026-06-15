import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { 
  Database, 
  Plus, 
  Trash2, 
  TestTube, 
  CheckCircle, 
  AlertCircle, 
  ChevronDown,
  ChevronUp,
  Server,
  Settings,
  Save,
  X
} from "lucide-react";
import { 
  fetchText2SQLConnections, 
  createText2SQLConnection, 
  deleteText2SQLConnection,
  testText2SQLConnection 
} from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogFooter,
  DialogClose,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface Connection {
  id: string;
  name: string;
  type: string;
  config: Record<string, any>;
}

interface ConnectionFormData {
  name: string;
  db_type: string;
  host: string;
  port: string;
  database: string;
  user: string;
  password: string;
  database_path: string;
  account: string;
  warehouse: string;
  schema: string;
  role: string;
}

const DB_TYPES = [
  { value: "postgresql", label: "PostgreSQL", icon: "🐘" },
  { value: "mysql", label: "MySQL", icon: "🐬" },
  { value: "sqlite", label: "SQLite", icon: "💾" },
  { value: "snowflake", label: "Snowflake", icon: "❄️" },
];

export default function ConnectionManager() {
  const [expandedConn, setExpandedConn] = useState<string | null>(null);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [testingConn, setTestingConn] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const queryClient = useQueryClient();

  const [formData, setFormData] = useState<ConnectionFormData>({
    name: "",
    db_type: "postgresql",
    host: "",
    port: "",
    database: "",
    user: "",
    password: "",
    database_path: "",
    account: "",
    warehouse: "",
    schema: "",
    role: "",
  });

  // Fetch connections
  const { data: connections = [], isLoading } = useQuery({
    queryKey: ["text2sql-connections"],
    queryFn: fetchText2SQLConnections,
  });

  // Create connection mutation
  const createMutation = useMutation({
    mutationFn: createText2SQLConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["text2sql-connections"] });
      setIsCreateOpen(false);
      resetForm();
    },
  });

  // Delete connection mutation
  const deleteMutation = useMutation({
    mutationFn: deleteText2SQLConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["text2sql-connections"] });
    },
  });

  const resetForm = () => {
    setFormData({
      name: "",
      db_type: "postgresql",
      host: "",
      port: "",
      database: "",
      user: "",
      password: "",
      database_path: "",
      account: "",
      warehouse: "",
      schema: "",
      role: "",
    });
    setTestResult(null);
  };

  const handleCreate = () => {
    const config: Record<string, any> = {};
    
    // Build config based on DB type
    if (formData.db_type === "sqlite") {
      config.database_path = formData.database_path;
    } else if (formData.db_type === "snowflake") {
      config.account = formData.account;
      config.warehouse = formData.warehouse;
      config.database = formData.database;
      config.schema = formData.schema;
      config.user = formData.user;
      config.password = formData.password;
      config.role = formData.role;
    } else {
      // PostgreSQL and MySQL
      config.host = formData.host;
      config.port = formData.port ? parseInt(formData.port) : undefined;
      config.database = formData.database;
      config.user = formData.user;
      config.password = formData.password;
    }
    
    createMutation.mutate({
      name: formData.name,
      db_type: formData.db_type,
      config,
    });
  };

  const handleTest = async (connectionId: string) => {
    setTestingConn(connectionId);
    setTestResult(null);
    
    try {
      const result = await testText2SQLConnection(connectionId);
      setTestResult(result);
    } catch (error) {
      setTestResult({ success: false, message: "Test failed" });
    } finally {
      setTestingConn(null);
    }
  };

  const getDBIcon = (type: string) => {
    const db = DB_TYPES.find(d => d.value === type);
    return db?.icon || "🗄️";
  };

  const getDBLabel = (type: string) => {
    const db = DB_TYPES.find(d => d.value === type);
    return db?.label || type;
  };

  const renderConfigFields = () => {
    switch (formData.db_type) {
      case "sqlite":
        return (
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium">Database Path</label>
              <Input
                placeholder="/path/to/database.db"
                value={formData.database_path}
                onChange={(e) => setFormData({ ...formData, database_path: e.target.value })}
              />
              <p className="text-xs text-slate-500">Path to the SQLite database file</p>
            </div>
          </div>
        );
      
      case "snowflake":
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Account</label>
                <Input
                  placeholder="xyz12345"
                  value={formData.account}
                  onChange={(e) => setFormData({ ...formData, account: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Warehouse</label>
                <Input
                  placeholder="COMPUTE_WH"
                  value={formData.warehouse}
                  onChange={(e) => setFormData({ ...formData, warehouse: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Database</label>
              <Input
                placeholder="MY_DATABASE"
                value={formData.database}
                onChange={(e) => setFormData({ ...formData, database: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Schema</label>
              <Input
                placeholder="PUBLIC"
                value={formData.schema}
                onChange={(e) => setFormData({ ...formData, schema: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">User</label>
                <Input
                  placeholder="username"
                  value={formData.user}
                  onChange={(e) => setFormData({ ...formData, user: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Password</label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Role (Optional)</label>
              <Input
                placeholder="ACCOUNTADMIN"
                value={formData.role}
                onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              />
            </div>
          </div>
        );
      
      default: // postgresql, mysql
        return (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Host</label>
                <Input
                  placeholder="localhost"
                  value={formData.host}
                  onChange={(e) => setFormData({ ...formData, host: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Port</label>
                <Input
                  type="number"
                  placeholder={formData.db_type === "mysql" ? "3306" : "5432"}
                  value={formData.port}
                  onChange={(e) => setFormData({ ...formData, port: e.target.value })}
                />
              </div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Database</label>
              <Input
                placeholder="my_database"
                value={formData.database}
                onChange={(e) => setFormData({ ...formData, database: e.target.value })}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">User</label>
                <Input
                  placeholder="username"
                  value={formData.user}
                  onChange={(e) => setFormData({ ...formData, user: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Password</label>
                <Input
                  type="password"
                  placeholder="••••••••"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                />
              </div>
            </div>
          </div>
        );
    }
  };

  return (
    <Card className="border-slate-200 shadow-sm">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <Server className="h-4 w-4 text-slate-500" />
              Database Connections
            </CardTitle>
            <CardDescription>
              Manage connections to different databases
            </CardDescription>
          </div>
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button size="sm" className="bg-emerald-500 hover:bg-emerald-600">
                <Plus className="h-4 w-4 mr-1" />
                Add Connection
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create New Connection</DialogTitle>
                <DialogDescription>
                  Add a new database connection for Text-to-SQL queries
                </DialogDescription>
              </DialogHeader>
              
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">Connection Name</label>
                  <Input
                    placeholder="e.g., Production DB"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  />
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium">Database Type</label>
                  <Select
                    value={formData.db_type}
                    onValueChange={(value) => setFormData({ ...formData, db_type: value })}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select database type" />
                    </SelectTrigger>
                    <SelectContent>
                      {DB_TYPES.map((db) => (
                        <SelectItem key={db.value} value={db.value}>
                          <span className="flex items-center gap-2">
                            <span>{db.icon}</span>
                            {db.label}
                          </span>
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                
                <div className="border-t pt-4">
                  <h4 className="text-sm font-medium mb-4">Connection Details</h4>
                  {renderConfigFields()}
                </div>
              </div>
              
              <DialogFooter>
                <DialogClose asChild>
                  <Button variant="outline" onClick={resetForm}>
                    Cancel
                  </Button>
                </DialogClose>
                <Button 
                  onClick={handleCreate}
                  disabled={!formData.name || createMutation.isPending}
                  className="bg-emerald-500 hover:bg-emerald-600"
                >
                  {createMutation.isPending ? (
                    <>
                      <div className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin mr-2" />
                      Creating...
                    </>
                  ) : (
                    <>
                      <Save className="h-4 w-4 mr-1" />
                      Create Connection
                    </>
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </CardHeader>
      
      <CardContent className="pt-0">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-8 w-8 border-2 border-slate-200 border-t-emerald-500 rounded-full animate-spin" />
          </div>
        ) : connections.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <Database className="h-12 w-12 mx-auto mb-3 text-slate-300" />
            <p className="text-sm">No connections yet</p>
            <p className="text-xs mt-1">Add a connection to start querying</p>
          </div>
        ) : (
          <div className="space-y-3">
            {connections.map((conn: Connection) => (
              <div
                key={conn.id}
                className={cn(
                  "border rounded-lg overflow-hidden transition",
                  expandedConn === conn.id ? "border-emerald-300 ring-1 ring-emerald-100" : "border-slate-200 hover:border-slate-300"
                )}
              >
                <div className="flex items-center justify-between p-3 bg-slate-50/50">
                  <div className="flex items-center gap-3">
                    <span className="text-lg">{getDBIcon(conn.type)}</span>
                    <div>
                      <p className="font-medium text-slate-800">{conn.name}</p>
                      <p className="text-xs text-slate-500">
                        {getDBLabel(conn.type)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => handleTest(conn.id)}
                      disabled={testingConn === conn.id}
                    >
                      {testingConn === conn.id ? (
                        <div className="h-4 w-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
                      ) : (
                        <TestTube className="h-4 w-4 text-slate-500" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 text-rose-500 hover:text-rose-600 hover:bg-rose-50"
                      onClick={() => deleteMutation.mutate(conn.id)}
                      disabled={deleteMutation.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => setExpandedConn(expandedConn === conn.id ? null : conn.id)}
                    >
                      {expandedConn === conn.id ? (
                        <ChevronUp className="h-4 w-4 text-slate-500" />
                      ) : (
                        <ChevronDown className="h-4 w-4 text-slate-500" />
                      )}
                    </Button>
                  </div>
                </div>
                
                {expandedConn === conn.id && (
                  <div className="p-3 border-t bg-white">
                    <h4 className="text-xs font-medium text-slate-500 uppercase tracking-wide mb-2">
                      Configuration
                    </h4>
                    <div className="space-y-1 text-sm">
                      {Object.entries(conn.config).map(([key, value]) => (
                        <div key={key} className="flex items-center gap-2">
                          <span className="text-slate-500 capitalize min-w-[100px]">
                            {key.replace(/_/g, " ")}:
                          </span>
                          <span className="font-mono text-slate-700">
                            {key.includes("password") ? "••••••••" : String(value)}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {testResult && expandedConn === conn.id && (
                  <div className={cn(
                    "p-3 border-t text-sm flex items-center gap-2",
                    testResult.success ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                  )}>
                    {testResult.success ? (
                      <CheckCircle className="h-4 w-4" />
                    ) : (
                      <AlertCircle className="h-4 w-4" />
                    )}
                    {testResult.message}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
