import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { DatabaseZap, Figma, Loader2, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { fdt } from "@/lib/format";

type SourceType = "local_folder" | "s3" | "postgres" | "api" | "google_sheet" | "figma_design";

const initial = {
  name: "",
  source_type: "local_folder" as SourceType,
  base_path: "",
  bucket: "",
  prefix: "",
  file_type: "csv",
  host: "",
  database: "",
  user: "",
  password: "",
  port: "5432",
  base_url: "",
  auth_type: "none",
  api_key: "",
  header_name: "Authorization",
  sheet_url: "",
  figma_file_url: "",
  figma_access_token: "",
  figma_node_id: "",
};

export const Connections = () => {
  const qc = useQueryClient();
  const [form, setForm] = useState(initial);
  const update = (key: keyof typeof initial, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const connections = useQuery({
    queryKey: ["connections"],
    queryFn: async () => (await api.get("/connections")).data.connections ?? [],
  });

  const save = useMutation({
    mutationFn: async () => {
      const config = {
        base_path: form.base_path,
        bucket: form.bucket,
        prefix: form.prefix,
        file_type: form.file_type,
        host: form.host,
        database: form.database,
        user: form.user,
        password: form.password,
        port: form.port,
        base_url: form.base_url,
        auth_type: form.auth_type,
        api_key: form.api_key,
        header_name: form.header_name,
        sheet_url: form.sheet_url,
        figma_file_url: form.figma_file_url,
        figma_access_token: form.figma_access_token,
        figma_node_id: form.figma_node_id,
      };
      return (await api.post("/connections", {
        name: form.name,
        source_type: form.source_type,
        config,
      })).data;
    },
    onSuccess: () => {
      setForm(initial);
      qc.invalidateQueries({ queryKey: ["connections"] });
    },
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/connections/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["connections"] }),
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    save.mutate();
  };

  return (
    <div className="space-y-5">
      <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="h-section flex items-center gap-2"><DatabaseZap className="h-5 w-5" /> Connections</h2>
            <p className="mt-3 max-w-2xl text-sm text-muted-foreground">
              Save source details once. After that, dashboard creation only needs a file name, object key, table name, or endpoint path.
            </p>
          </div>
          <Badge variant="success">Reusable sources</Badge>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[430px_1fr]">
        <Card>
          <CardHeader><CardTitle className="text-sm">Create Connection</CardTitle></CardHeader>
          <CardContent>
            <form onSubmit={submit} className="space-y-4">
              <Input placeholder="Connection name" value={form.name} onChange={(e) => update("name", e.target.value)} required />
              <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.source_type} onChange={(e) => update("source_type", e.target.value)}>
                <option value="local_folder">Local / mounted folder</option>
                <option value="s3">S3 bucket</option>
                <option value="postgres">Postgres database</option>
                <option value="api">API base URL</option>
                <option value="google_sheet">Google Sheet</option>
                <option value="figma_design">Figma design</option>
              </select>

              {form.source_type === "local_folder" && (
                <Input placeholder="Base folder path, e.g. /app/data or D:/datasets" value={form.base_path} onChange={(e) => update("base_path", e.target.value)} />
              )}
              {form.source_type === "s3" && (
                <div className="space-y-3">
                  <Input placeholder="Bucket" value={form.bucket} onChange={(e) => update("bucket", e.target.value)} />
                  <Input placeholder="Prefix/folder, e.g. raw/sales" value={form.prefix} onChange={(e) => update("prefix", e.target.value)} />
                  <Input placeholder="Default file type" value={form.file_type} onChange={(e) => update("file_type", e.target.value)} />
                </div>
              )}
              {form.source_type === "postgres" && (
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <Input placeholder="Host" value={form.host} onChange={(e) => update("host", e.target.value)} />
                  <Input placeholder="Database" value={form.database} onChange={(e) => update("database", e.target.value)} />
                  <Input placeholder="User" value={form.user} onChange={(e) => update("user", e.target.value)} />
                  <Input placeholder="Password" type="password" value={form.password} onChange={(e) => update("password", e.target.value)} />
                  <Input placeholder="Port" value={form.port} onChange={(e) => update("port", e.target.value)} />
                </div>
              )}
              {form.source_type === "api" && (
                <div className="space-y-3">
                  <Input placeholder="Base URL, e.g. https://api.company.com" value={form.base_url} onChange={(e) => update("base_url", e.target.value)} />
                  <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={form.auth_type} onChange={(e) => update("auth_type", e.target.value)}>
                    <option value="none">No auth</option>
                    <option value="bearer">Bearer token</option>
                    <option value="api_key_header">API key header</option>
                  </select>
                  {form.auth_type !== "none" && (
                    <>
                      <Input placeholder="Header name, e.g. Authorization or x-api-key" value={form.header_name} onChange={(e) => update("header_name", e.target.value)} />
                      <Input placeholder="API key / token" type="password" value={form.api_key} onChange={(e) => update("api_key", e.target.value)} />
                    </>
                  )}
                </div>
              )}
              {form.source_type === "google_sheet" && (
                <Input placeholder="Reusable Google Sheet URL" value={form.sheet_url} onChange={(e) => update("sheet_url", e.target.value)} />
              )}
              {form.source_type === "figma_design" && (
                <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                    <Figma className="h-4 w-4 text-pink-600" />
                    Figma design reference
                  </div>
                  <Input placeholder="Figma file/design URL" value={form.figma_file_url} onChange={(e) => update("figma_file_url", e.target.value)} required />
                  <Input placeholder="Figma access token" type="password" value={form.figma_access_token} onChange={(e) => update("figma_access_token", e.target.value)} />
                  <Input placeholder="Optional node id, e.g. 12:34" value={form.figma_node_id} onChange={(e) => update("figma_node_id", e.target.value)} />
                  <p className="text-xs leading-5 text-muted-foreground">
                    Use this later as a design blueprint while generating a data dashboard.
                  </p>
                </div>
              )}

              <Button type="submit" disabled={save.isPending} className="w-full">
                {save.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Save Connection
              </Button>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-sm">Saved Connections</CardTitle></CardHeader>
          <CardContent>
            {connections.isLoading ? <p className="text-sm text-muted-foreground">Loading connections...</p> : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {(connections.data ?? []).map((connection: any) => (
                  <div key={connection.id} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-slate-950">{connection.name}</p>
                        <p className="mt-1 text-xs text-muted-foreground">{connection.source_type} / {fdt(connection.updated_at)}</p>
                      </div>
                      <Badge variant={connection.status === "connected" ? "success" : "muted"}>{connection.status}</Badge>
                    </div>
                    <pre className="mt-3 max-h-28 overflow-auto rounded-md bg-slate-50 p-3 text-xs text-slate-600">{JSON.stringify(connection.config, null, 2)}</pre>
                    <Button variant="outline" className="mt-3 hover:border-destructive hover:bg-red-50 hover:text-destructive" onClick={() => remove.mutate(connection.id)}>
                      <Trash2 /> Delete
                    </Button>
                  </div>
                ))}
                {(connections.data ?? []).length === 0 && <p className="text-sm text-muted-foreground">No connections saved yet.</p>}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};
