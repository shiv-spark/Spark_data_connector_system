import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Network, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SchedulerFields } from "@/components/SchedulerFields";
import { buildCron, defaultSchedule } from "@/lib/schedule";

type Source = {
  connector_type: string;
  file_path: string;
  sheet_url: string;
  api_url: string;
  s3_bucket: string;
  s3_key: string;
  s3_file_type: string;
  src_pg_host: string;
  src_pg_db: string;
  src_pg_user: string;
  src_pg_password: string;
  src_pg_port: string;
  pg_query: string;
};

const blankSource = (): Source => ({
  connector_type: "csv",
  file_path: "",
  sheet_url: "",
  api_url: "",
  s3_bucket: "",
  s3_key: "",
  s3_file_type: "csv",
  src_pg_host: "",
  src_pg_db: "",
  src_pg_user: "",
  src_pg_password: "",
  src_pg_port: "5432",
  pg_query: "",
});

export const MultiSource = () => {
  const qc = useQueryClient();
  const [pipelineName, setPipelineName] = useState("");
  const [tableName, setTableName] = useState("");
  const [schedule, setSchedule] = useState(defaultSchedule);
  const [option, setOption] = useState("1");
  const [sources, setSources] = useState<Source[]>([blankSource()]);
  const [result, setResult] = useState<any>(null);

  const updateSource = (index: number, key: keyof Source, value: string) =>
    setSources((current) => current.map((source, i) => i === index ? { ...source, [key]: value } : source));

  const create = useMutation({
    mutationFn: async () => {
      const response = await api.post("/create_multi_pipeline", {
        pipeline_name: pipelineName,
        table_name: tableName,
        option,
        schedule: buildCron(schedule),
        timezone: schedule.timezone,
        sync_mode: "full",
        sources,
      });
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
      <h2 className="h-section flex items-center gap-2"><Network className="h-5 w-5" /> Multi-Source Pipeline</h2>
      <Card>
        <CardHeader><CardTitle className="text-sm">Merge Multiple Sources Into One Pipeline</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Input placeholder="Pipeline name" value={pipelineName} onChange={(e) => setPipelineName(e.target.value)} required />
              <Input placeholder="Target table" value={tableName} onChange={(e) => setTableName(e.target.value)} required />
              <select className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={option} onChange={(e) => setOption(e.target.value)}>
                <option value="1">Append</option><option value="2">Overwrite</option><option value="3">Create new</option>
              </select>
            </div>

            <SchedulerFields value={schedule} onChange={setSchedule} />

            <div className="space-y-4">
              {sources.map((source, index) => (
                <Card key={index} className="bg-slate-50">
                  <CardContent className="space-y-4 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <select className="h-9 rounded-md border border-input bg-background px-3 text-sm" value={source.connector_type} onChange={(e) => updateSource(index, "connector_type", e.target.value)}>
                        <option value="csv">CSV</option><option value="excel">Excel</option><option value="google_sheets">Google Sheets</option><option value="api">API</option><option value="postgres">Postgres</option><option value="s3">S3</option>
                      </select>
                      {sources.length > 1 && <Button type="button" variant="outline" onClick={() => setSources((current) => current.filter((_, i) => i !== index))}><Trash2 /> Remove</Button>}
                    </div>

                    {["csv", "excel"].includes(source.connector_type) && <Input placeholder="File path" value={source.file_path} onChange={(e) => updateSource(index, "file_path", e.target.value)} />}
                    {source.connector_type === "google_sheets" && <Input placeholder="Sheet URL" value={source.sheet_url} onChange={(e) => updateSource(index, "sheet_url", e.target.value)} />}
                    {source.connector_type === "api" && <Input placeholder="API URL" value={source.api_url} onChange={(e) => updateSource(index, "api_url", e.target.value)} />}
                    {source.connector_type === "s3" && (
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                        <Input placeholder="Bucket" value={source.s3_bucket} onChange={(e) => updateSource(index, "s3_bucket", e.target.value)} />
                        <Input placeholder="Key" value={source.s3_key} onChange={(e) => updateSource(index, "s3_key", e.target.value)} />
                        <Input placeholder="File type" value={source.s3_file_type} onChange={(e) => updateSource(index, "s3_file_type", e.target.value)} />
                      </div>
                    )}
                    {source.connector_type === "postgres" && (
                      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <Input placeholder="Host" value={source.src_pg_host} onChange={(e) => updateSource(index, "src_pg_host", e.target.value)} />
                        <Input placeholder="Database" value={source.src_pg_db} onChange={(e) => updateSource(index, "src_pg_db", e.target.value)} />
                        <Input placeholder="User" value={source.src_pg_user} onChange={(e) => updateSource(index, "src_pg_user", e.target.value)} />
                        <Input type="password" placeholder="Password" value={source.src_pg_password} onChange={(e) => updateSource(index, "src_pg_password", e.target.value)} />
                        <Input placeholder="Port" value={source.src_pg_port} onChange={(e) => updateSource(index, "src_pg_port", e.target.value)} />
                        <textarea className="min-h-24 rounded-md border border-input bg-background px-3 py-2 text-sm md:col-span-2" placeholder="SQL query" value={source.pg_query} onChange={(e) => updateSource(index, "pg_query", e.target.value)} />
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>

            <div className="flex gap-3">
              <Button type="button" variant="outline" onClick={() => setSources((current) => [...current, blankSource()])}><Plus /> Add Source</Button>
              <Button type="submit" disabled={create.isPending}>{create.isPending ? <Loader2 className="animate-spin" /> : <Network />} Create Multi-Source Pipeline</Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {(result || create.error) && (
        <Card className={create.error ? "border-rose-200 bg-rose-50" : "border-emerald-200 bg-emerald-50"}>
          <CardContent className="p-4"><pre className="max-h-80 overflow-auto text-xs">{JSON.stringify(result ?? (create.error as any)?.response?.data ?? (create.error as Error).message, null, 2)}</pre></CardContent>
        </Card>
      )}
    </div>
  );
};
