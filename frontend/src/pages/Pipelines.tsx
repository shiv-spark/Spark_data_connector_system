import { useMemo, useState } from "react";
import { useQuery, useQueries, useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, ListChecks, Pause, Play, Save, Trash2, RefreshCw, Search, X } from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/StatusBadge";
import { fdt } from "@/lib/format";
import { SchedulerFields } from "@/components/SchedulerFields";
import { buildCron, scheduleFromCron, ScheduleState } from "@/lib/schedule";

type Pipeline = { dag_id: string; size_kb?: number; schedule?: string; timezone?: string };

const fetchPipelines = async (): Promise<Pipeline[]> => {
  const r = await api.get("/pipelines");
  return r.data?.pipelines ?? [];
};

const fetchStatus = async (name: string) => {
  const r = await api.get(`/pipeline/${name}/status`);
  return r.data;
};

export const Pipelines = () => {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<Record<string, ScheduleState>>({});

  const { data: pipes = [], isLoading } = useQuery({
    queryKey: ["pipelines"],
    queryFn: fetchPipelines,
  });

  const statusQueries = useQueries({
    queries: pipes.map((pipeline) => ({
      queryKey: ["pipeline-status", pipeline.dag_id],
      queryFn: () => fetchStatus(pipeline.dag_id.replace(/^pipeline_/, "")),
      staleTime: 15_000,
    })),
  });

  const rows = useMemo(
    () =>
      pipes.map((pipeline, index) => {
        const name = pipeline.dag_id.replace(/^pipeline_/, "");
        const statusData = statusQueries[index]?.data;
        return {
          dag_id: pipeline.dag_id,
          name,
          status: statusData?.status ?? "UNKNOWN",
          next_run: statusData?.next_run ?? null,
          size_kb: pipeline.size_kb ?? "-",
          schedule: pipeline.schedule ?? "*/5 * * * *",
          timezone: pipeline.timezone ?? "Asia/Kolkata",
        };
      }),
    [pipes, statusQueries],
  );

  const filtered = rows.filter((row) =>
    !search ? true : row.dag_id.toLowerCase().includes(search.toLowerCase()),
  );

  const pauseM = useMutation({
    mutationFn: (name: string) => api.patch(`/pipeline/${name}/pause`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline-status"] }),
  });
  const resumeM = useMutation({
    mutationFn: (name: string) => api.patch(`/pipeline/${name}/unpause`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pipeline-status"] }),
  });
  const deleteM = useMutation({
    mutationFn: (name: string) => api.delete(`/delete_pipeline/${name}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["pipeline-status"] });
    },
  });
  const editScheduleM = useMutation({
    mutationFn: ({ name, schedule }: { name: string; schedule: ScheduleState }) =>
      api.patch(`/edit_pipeline/${name}`, { schedule: buildCron(schedule), timezone: schedule.timezone }),
    onSuccess: (_, variables) => {
      setEditing((current) => {
        const next = { ...current };
        delete next[variables.name];
        return next;
      });
      qc.invalidateQueries({ queryKey: ["pipelines"] });
      qc.invalidateQueries({ queryKey: ["pipeline-status"] });
    },
  });

  const counts = {
    total: rows.length,
    active: rows.filter((row) => row.status === "ACTIVE").length,
    paused: rows.filter((row) => row.status === "PAUSED").length,
  };

  return (
    <div className="space-y-5">
      <h2 className="h-section flex items-center gap-2"><ListChecks className="h-5 w-5" /> Manage Pipelines</h2>

      <div className="flex items-center gap-3">
        <Button variant="outline" onClick={() => qc.invalidateQueries({ queryKey: ["pipelines"] })}>
          <RefreshCw /> Refresh
        </Button>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search pipeline..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
      </div>

      {isLoading ? (
        <p className="text-muted-foreground">Loading pipelines...</p>
      ) : pipes.length === 0 ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="px-4 py-3 text-sm text-amber-800">
            No pipelines found. Create one using the "Create Pipeline" page.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <Card><CardContent className="px-4 py-3">
              <p className="text-xs text-muted-foreground">Total Pipelines</p>
              <p className="text-2xl font-bold text-slate-900">{counts.total}</p>
            </CardContent></Card>
            <Card><CardContent className="px-4 py-3">
              <p className="text-xs text-muted-foreground">Active</p>
              <p className="text-2xl font-bold text-emerald-600">{counts.active}</p>
            </CardContent></Card>
            <Card><CardContent className="px-4 py-3">
              <p className="text-xs text-muted-foreground">Paused</p>
              <p className="text-2xl font-bold text-amber-600">{counts.paused}</p>
            </CardContent></Card>
          </div>

          <div className="space-y-2">
            {filtered.length === 0 && (
              <p className="text-sm text-muted-foreground">No pipelines match your search.</p>
            )}

            {filtered.map((row) => (
              <Card key={row.dag_id}>
                <CardContent className="space-y-3 px-4 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-900">{row.dag_id}</span>
                        <StatusBadge status={row.status} />
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        Next run: {fdt(row.next_run)} &nbsp;/&nbsp; Size: {String(row.size_kb)} KB
                      </p>
                      <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                        <CalendarClock className="h-3.5 w-3.5" />
                        <span className="font-mono">{row.schedule}</span>
                        <span>in {row.timezone}</span>
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={() => setEditing((current) => ({
                          ...current,
                          [row.name]: scheduleFromCron(row.schedule, row.timezone),
                        }))}
                      >
                        <CalendarClock /> Schedule
                      </Button>
                      {row.status === "ACTIVE" ? (
                        <Button variant="outline" onClick={() => pauseM.mutate(row.name)}>
                          <Pause /> Pause
                        </Button>
                      ) : (
                        <Button variant="outline" onClick={() => resumeM.mutate(row.name)}>
                          <Play /> Resume
                        </Button>
                      )}
                      <Button
                        variant="outline"
                        className="hover:border-destructive hover:bg-red-50 hover:text-destructive"
                        onClick={() => {
                          if (confirm(`Delete pipeline "${row.name}"? This cannot be undone.`)) {
                            deleteM.mutate(row.name);
                          }
                        }}
                      >
                        <Trash2 /> Delete
                      </Button>
                    </div>
                  </div>

                  {editing[row.name] && (
                    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
                      <SchedulerFields
                        compact
                        value={editing[row.name]}
                        onChange={(next) => setEditing((current) => ({ ...current, [row.name]: next }))}
                      />
                      <div className="mt-3 flex justify-end gap-2">
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => setEditing((current) => {
                            const next = { ...current };
                            delete next[row.name];
                            return next;
                          })}
                        >
                          <X /> Cancel
                        </Button>
                        <Button
                          type="button"
                          disabled={editScheduleM.isPending}
                          onClick={() => editScheduleM.mutate({ name: row.name, schedule: editing[row.name] })}
                        >
                          <Save /> Save Schedule
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
