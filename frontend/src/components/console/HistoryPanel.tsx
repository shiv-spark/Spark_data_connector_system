import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History, Loader2, RotateCcw, X } from "lucide-react";
import {
  fetchDashboardHistory,
  restoreDashboardVersion,
  type DashboardVersion,
} from "@/lib/api";
import { fdt } from "@/lib/format";

/**
 * The version log. Rewinding discards everything after the chosen point, which
 * is why there's no redo — the panel says so rather than letting people find
 * out afterwards.
 */
export function HistoryPanel({
  dashboardId,
  onClose,
  onRestored,
}: {
  dashboardId: string;
  onClose: () => void;
  onRestored: () => void;
}) {
  const queryClient = useQueryClient();

  const history = useQuery({
    queryKey: ["dashboard-history", dashboardId],
    queryFn: () => fetchDashboardHistory(dashboardId),
  });

  const restore = useMutation({
    mutationFn: (versionId: number) => restoreDashboardVersion(dashboardId, versionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dashboard-history", dashboardId] });
      onRestored();
    },
  });

  const versions = history.data ?? [];

  return (
    <aside className="flex h-full w-[320px] shrink-0 flex-col border-l border-border bg-[hsl(var(--surface-1))]">
      <div className="panel-bar !rounded-none">
        <History className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="panel-title">Version history</span>
        <button onClick={onClose} className="icon-btn ml-auto !h-7 !w-7" aria-label="Close history">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {history.isLoading ? (
          <div className="space-y-2 p-4">
            {[0, 1, 2].map((i) => (
              <div key={i} className="skel h-11" />
            ))}
          </div>
        ) : versions.length === 0 ? (
          <div className="empty !py-12">
            <span className="empty-mark">
              <History className="h-5 w-5" strokeWidth={1.7} />
            </span>
            <p className="text-[13px] font-semibold text-foreground">No earlier versions</p>
            <p className="max-w-[15rem] text-[12px] leading-relaxed text-muted-foreground">
              Every edit you or the agent makes is recorded here, so you can step back to any of
              them.
            </p>
          </div>
        ) : (
          versions.map((version: DashboardVersion, i: number) => (
            <div key={version.version_id} className="row" data-state={i === 0 ? "active" : "unknown"}>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-[12.5px] font-medium text-foreground">
                    {version.label || "Edited"}
                  </p>
                  <p className="mono-meta mt-1">{fdt(version.created_at)}</p>
                </div>
                <button
                  onClick={() => restore.mutate(version.version_id)}
                  disabled={restore.isPending}
                  title="Restore the board as it was before this change"
                  className="inline-flex h-7 shrink-0 items-center gap-1.5 rounded-md px-2 text-[11.5px] font-semibold text-foreground ring-1 ring-inset ring-border transition hover:bg-[hsl(var(--surface-2))] disabled:opacity-50"
                >
                  {restore.isPending && restore.variables === version.version_id ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <RotateCcw className="h-3 w-3" />
                  )}
                  Restore
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <p className="border-t border-border px-4 py-3 text-[11.5px] leading-relaxed text-muted-foreground">
        Restoring a version discards the changes made after it. There's no redo.
      </p>
    </aside>
  );
}
