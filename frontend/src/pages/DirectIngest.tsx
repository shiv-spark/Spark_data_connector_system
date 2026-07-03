import { FormEvent, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { DownloadCloud, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type Connector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "s3" | "snowflake";

const connectorLabels: Record<Connector, string> = {
  csv: "CSV",
  excel: "Excel",
  google_sheets: "Google Sheets",
  api: "API",
  postgres: "Postgres",
  s3: "S3",
  snowflake: "Snowflake",
};

const initial = {
  connector: "csv" as Connector,
  table_name: "",
  option: "1",
  sync_mode: "full",
  incremental_column: "",
  file_path: "",
  sheet_url: "",
  url: "",
  api_config: "",
  host: "",
  database: "",
  user: "",
  password: "",
  port: "5432",
  query: "",
  bucket: "",
  key: "",
  file_type: "csv",
  // ── Snowflake fields ──────────────────
  sf_account: "",
  sf_user: "",
  sf_password: "",
  sf_warehouse: "",
  sf_database: "",
  sf_schema: "PUBLIC",
  sf_role: "",
  sf_query: "",
};

export const DirectIngest = () => {
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState<any>(null);
  const [apiConfigError, setApiConfigError] = useState<string>("");

  const update = (key: keyof typeof initial, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const ingest = useMutation({
    mutationFn: async () => {
      const common = {
        option: form.option,
        table_name: form.table_name,
        sync_mode: form.sync_mode,
        incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
      };

      let parsedApiConfig: Record<string, unknown> = {};
      if (form.connector === "api" && form.api_config.trim()) {
        try {
          parsedApiConfig = JSON.parse(form.api_config);
        } catch (e) {
          setApiConfigError("Invalid JSON — please check the syntax.");
          throw new Error("Invalid api_config JSON");
        }
      }

      const payloads = {
        csv: { ...common, file_path: form.file_path },
        excel: { ...common, file_path: form.file_path },
        google_sheets: { ...common, sheet_url: form.sheet_url },
        api: { ...common, url: form.url, ...parsedApiConfig },   // ← spread flattened onto APIRequest fields
        postgres: { ...common, host: form.host, database: form.database, user: form.user, password: form.password, port: form.port, query: form.query },
        s3: { ...common, bucket: form.bucket, key: form.key, file_type: form.file_type },
        snowflake: {
          ...common,
          account: form.sf_account,
          user: form.sf_user,
          password: form.sf_password,
          warehouse: form.sf_warehouse,
          database: form.sf_database,
          schema: form.sf_schema,
          role: form.sf_role || null,
          query: form.sf_query,
        },
      };
      const endpoints = {
        csv: "/ingest_csv",
        excel: "/ingest_excel",
        google_sheets: "/ingest_google_sheet",
        api: "/ingest_api",
        postgres: "/ingest_postgres",
        s3: "/ingest_s3",
        snowflake: "/ingest_snowflake",
      };
      const response = await api.post(endpoints[form.connector], payloads[form.connector]);
      return response.data;
    },
    onSuccess: setResult,
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    setApiConfigError("");
    setResult(null);
    ingest.mutate();
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><DownloadCloud className="h-5 w-5" /> Direct Ingest</h2>
      <Card>
        <CardHeader><CardTitle className="text-sm">Run One-Time Ingestion</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
              <label className="space-y-1 text-sm font-medium">
                Connector
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.connector} onChange={(e) => update("connector", e.target.value as Connector)}>
                  {Object.entries(connectorLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium">Target table<Input value={form.table_name} onChange={(e) => update("table_name", e.target.value)} required /></label>
              <label className="space-y-1 text-sm font-medium">
                Load option
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.option} onChange={(e) => update("option", e.target.value)}>
                  <option value="1">Append</option>
                  <option value="2">Overwrite</option>
                  <option value="3">Create new</option>
                </select>
              </label>
              <label className="space-y-1 text-sm font-medium">
                Sync mode
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.sync_mode} onChange={(e) => update("sync_mode", e.target.value)}>
                  <option value="full">Full</option>
                  <option value="incremental">Incremental</option>
                </select>
              </label>
            </div>

            {form.sync_mode === "incremental" && (
              <label className="block max-w-md space-y-1 text-sm font-medium">Incremental column<Input value={form.incremental_column} onChange={(e) => update("incremental_column", e.target.value)} /></label>
            )}

            {["csv", "excel"].includes(form.connector) && (
              <label className="block space-y-1 text-sm font-medium">File path<Input value={form.file_path} onChange={(e) => update("file_path", e.target.value)} placeholder="D:/data/sales.csv" required /></label>
            )}
            {form.connector === "google_sheets" && (
              <label className="block space-y-1 text-sm font-medium">Sheet URL<Input value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} required /></label>
            )}
            {form.connector === "api" && (
              <div className="space-y-2">
                <label className="block space-y-1 text-sm font-medium">API URL<Input value={form.url} onChange={(e) => update("url", e.target.value)} required /></label>
                <label className="space-y-1 text-sm font-medium block">
                  Advanced Config (optional JSON — method, auth_type, body, pagination, etc.)
                  <textarea
                    className="min-h-40 w-full rounded-md border border-input bg-background px-3 py-2 font-mono text-xs"
                    placeholder='{"method": "POST", "auth_type": "bearer", "bearer_token": "...", "pagination_type": "page"}'
                    value={form.api_config}
                    onChange={(e) => {
                      update("api_config", e.target.value);
                      setApiConfigError("");
                    }}
                  />
                </label>
                {apiConfigError && <p className="text-sm text-red-500">{apiConfigError}</p>}
              </div>
            )}
            {form.connector === "postgres" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input placeholder="Host" value={form.host} onChange={(e) => update("host", e.target.value)} required />
                <Input placeholder="Database" value={form.database} onChange={(e) => update("database", e.target.value)} required />
                <Input placeholder="User" value={form.user} onChange={(e) => update("user", e.target.value)} required />
                <Input placeholder="Password" type="password" value={form.password} onChange={(e) => update("password", e.target.value)} required />
                <Input placeholder="Port" value={form.port} onChange={(e) => update("port", e.target.value)} />
                <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.query} onChange={(e) => update("query", e.target.value)} required />
              </div>
            )}
            {form.connector === "s3" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <Input placeholder="Bucket" value={form.bucket} onChange={(e) => update("bucket", e.target.value)} required />
                <Input placeholder="Key" value={form.key} onChange={(e) => update("key", e.target.value)} required />
                <Input placeholder="File type" value={form.file_type} onChange={(e) => update("file_type", e.target.value)} />
              </div>
            )}
            {form.connector === "snowflake" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input placeholder="Account (e.g. XROJPNQ-RO43084)" value={form.sf_account} onChange={(e) => update("sf_account", e.target.value)} required />
                <Input placeholder="User" value={form.sf_user} onChange={(e) => update("sf_user", e.target.value)} required />
                <Input placeholder="Password" type="password" value={form.sf_password} onChange={(e) => update("sf_password", e.target.value)} required />
                <Input placeholder="Warehouse" value={form.sf_warehouse} onChange={(e) => update("sf_warehouse", e.target.value)} required />
                <Input placeholder="Database" value={form.sf_database} onChange={(e) => update("sf_database", e.target.value)} required />
                <Input placeholder="Schema (default PUBLIC)" value={form.sf_schema} onChange={(e) => update("sf_schema", e.target.value)} />
                <Input placeholder="Role (optional)" value={form.sf_role} onChange={(e) => update("sf_role", e.target.value)} />
                <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.sf_query} onChange={(e) => update("sf_query", e.target.value)} required />
              </div>
            )}

            <Button type="submit" disabled={ingest.isPending}>
              {ingest.isPending ? <Loader2 className="animate-spin" /> : <DownloadCloud />} Run Ingest
            </Button>
          </form>
        </CardContent>
      </Card>

      {(result || ingest.error) && (
        <Card className={ingest.error ? "border-rose-200 bg-rose-50" : "border-emerald-200 bg-emerald-50"}>
          <CardContent className="p-4">
            <pre className="max-h-80 overflow-auto text-xs">{JSON.stringify(result ?? (ingest.error as any)?.response?.data ?? (ingest.error as Error).message, null, 2)}</pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
