import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, PlusCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SchedulerFields } from "@/components/SchedulerFields";
import { buildCron, defaultSchedule } from "@/lib/schedule";

type Connector = "csv" | "excel" | "google_sheets" | "api" | "postgres" | "s3";

const base = {
  pipeline_name: "",
  connector_type: "csv" as Connector,
  table_name: "",
  option: "1",
  after_first_run: "",
  sync_mode: "full",
  incremental_column: "",
  folder_path: "",
  file_path: "",
  sheet_url: "",
  api_url: "",
  src_pg_host: "",
  src_pg_db: "",
  src_pg_user: "",
  src_pg_password: "",
  src_pg_port: "5432",
  pg_query: "",
  s3_bucket: "",
  s3_key: "",
  s3_file_type: "csv",
};

export const CreatePipeline = () => {
  const qc = useQueryClient();
  const [form, setForm] = useState(base);
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [result, setResult] = useState<any>(null);
  const update = (key: keyof typeof base, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const create = useMutation({
    mutationFn: async () => {
      const payload = {
        ...form,
        schedule: buildCron(schedule),
        timezone: schedule.timezone,
        incremental_column: form.sync_mode === "incremental" ? form.incremental_column : null,
        after_first_run: form.option === "3" ? form.after_first_run || null : null,
      };
      const response = await api.post("/create_pipeline", payload);
      return response.data;
    },
    onSuccess: (data) => {
      setResult(data);
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setResult(null);
    create.mutate();
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><PlusCircle className="h-5 w-5" /> Create Pipeline</h2>
      <Card>
        <CardHeader><CardTitle className="text-sm">Pipeline Configuration</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <label className="space-y-1 text-sm font-medium">Pipeline name<Input value={form.pipeline_name} onChange={(e) => update("pipeline_name", e.target.value)} required /></label>
              <label className="space-y-1 text-sm font-medium">
                Connector
                <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.connector_type} onChange={(e) => update("connector_type", e.target.value as Connector)}>
                  <option value="csv">CSV</option>
                  <option value="excel">Excel</option>
                  <option value="google_sheets">Google Sheets</option>
                  <option value="api">API</option>
                  <option value="postgres">Postgres</option>
                  <option value="s3">S3</option>
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

            <SchedulerFields value={schedule} onChange={setSchedule} />

            {form.option === "3" && (
              <label className="block max-w-md space-y-1 text-sm font-medium">After first run<Input placeholder="1 append, 2 overwrite" value={form.after_first_run} onChange={(e) => update("after_first_run", e.target.value)} /></label>
            )}
            {form.sync_mode === "incremental" && (
              <label className="block max-w-md space-y-1 text-sm font-medium">Incremental column<Input value={form.incremental_column} onChange={(e) => update("incremental_column", e.target.value)} /></label>
            )}

            {["csv", "excel"].includes(form.connector_type) && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input placeholder="File path" value={form.file_path} onChange={(e) => update("file_path", e.target.value)} />
                <Input placeholder="Folder path" value={form.folder_path} onChange={(e) => update("folder_path", e.target.value)} />
              </div>
            )}
            {form.connector_type === "google_sheets" && <Input placeholder="Sheet URL" value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} />}
            {form.connector_type === "api" && <Input placeholder="API URL" value={form.api_url} onChange={(e) => update("api_url", e.target.value)} />}
            {form.connector_type === "postgres" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <Input placeholder="Host" value={form.src_pg_host} onChange={(e) => update("src_pg_host", e.target.value)} />
                <Input placeholder="Database" value={form.src_pg_db} onChange={(e) => update("src_pg_db", e.target.value)} />
                <Input placeholder="User" value={form.src_pg_user} onChange={(e) => update("src_pg_user", e.target.value)} />
                <Input placeholder="Password" type="password" value={form.src_pg_password} onChange={(e) => update("src_pg_password", e.target.value)} />
                <Input placeholder="Port" value={form.src_pg_port} onChange={(e) => update("src_pg_port", e.target.value)} />
                <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={form.pg_query} onChange={(e) => update("pg_query", e.target.value)} />
              </div>
            )}
            {form.connector_type === "s3" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <Input placeholder="Bucket" value={form.s3_bucket} onChange={(e) => update("s3_bucket", e.target.value)} />
                <Input placeholder="Key" value={form.s3_key} onChange={(e) => update("s3_key", e.target.value)} />
                <Input placeholder="File type" value={form.s3_file_type} onChange={(e) => update("s3_file_type", e.target.value)} />
              </div>
            )}

            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? <Loader2 className="animate-spin" /> : <PlusCircle />} Create Pipeline
            </Button>
          </form>
        </CardContent>
      </Card>

      {(result || create.error) && (
        <Card className={create.error ? "border-rose-200 bg-rose-50" : "border-emerald-200 bg-emerald-50"}>
          <CardContent className="p-4">
            <pre className="max-h-80 overflow-auto text-xs">{JSON.stringify(result ?? (create.error as any)?.response?.data ?? (create.error as Error).message, null, 2)}</pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
