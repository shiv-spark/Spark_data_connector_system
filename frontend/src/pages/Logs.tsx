import { FormEvent, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ScrollText, Search } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { StatusBadge } from "@/components/StatusBadge";
import { fdt } from "@/lib/format";

export const Logs = () => {
  const [pipeline, setPipeline] = useState("");
  const [activePipeline, setActivePipeline] = useState("");

  const runs = useQuery({
    queryKey: ["runs"],
    queryFn: async () => (await api.get("/runs")).data ?? [],
  });
  const logs = useQuery({
    queryKey: ["pipeline-logs", activePipeline],
    enabled: !!activePipeline,
    queryFn: async () => (await api.get(`/pipeline/${activePipeline}/logs`)).data,
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setActivePipeline(pipeline.trim());
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><ScrollText className="h-5 w-5" /> Logs</h2>
      <Card>
        <CardHeader><CardTitle className="text-sm">Pipeline Log Lookup</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={submit} className="flex gap-3">
            <Input placeholder="Pipeline id or name" value={pipeline} onChange={(e) => setPipeline(e.target.value)} />
            <Button type="submit"><Search /> Load Logs</Button>
          </form>
        </CardContent>
      </Card>

      {activePipeline && (
        <Card>
          <CardHeader><CardTitle className="text-sm">Latest Logs for {activePipeline}</CardTitle></CardHeader>
          <CardContent>
            {logs.isFetching ? <p className="text-sm text-muted-foreground">Loading logs...</p> : logs.error ? (
              <p className="text-sm text-rose-700">{(logs.error as any)?.response?.data?.detail ?? (logs.error as Error).message}</p>
            ) : (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
                  <StatusBadge status={logs.data?.status ?? "UNKNOWN"} />
                  <span>Source: {logs.data?.source ?? "-"}</span>
                  <span>Logged: {fdt(logs.data?.logged_at)}</span>
                </div>
                <pre className="max-h-[520px] overflow-auto rounded-md bg-slate-950 p-4 text-xs text-slate-100">{logs.data?.log ?? "No log content."}</pre>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader><CardTitle className="text-sm">Recent Pipeline Runs</CardTitle></CardHeader>
        <CardContent>
          {runs.isLoading ? <p className="text-sm text-muted-foreground">Loading runs...</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="border-b text-left text-xs uppercase text-muted-foreground">
                  <th className="py-3 pr-4">Run</th><th className="py-3 pr-4">Connector</th><th className="py-3 pr-4">Status</th><th className="py-3 pr-4">Rows</th><th className="py-3 pr-4">Started</th><th className="py-3 pr-4">Error</th>
                </tr></thead>
                <tbody>
                  {(runs.data ?? []).slice(0, 30).map((run: any) => (
                    <tr key={run.run_id} className="border-b border-slate-100">
                      <td className="py-3 pr-4">{run.run_id}</td>
                      <td className="py-3 pr-4">{run.connector_name}</td>
                      <td className="py-3 pr-4"><StatusBadge status={run.status} /></td>
                      <td className="py-3 pr-4">{run.records_count ?? "-"}</td>
                      <td className="py-3 pr-4 text-muted-foreground">{fdt(run.start_time)}</td>
                      <td className="max-w-md truncate py-3 pr-4 text-muted-foreground">{run.error ?? "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
