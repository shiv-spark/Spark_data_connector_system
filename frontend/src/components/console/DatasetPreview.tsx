import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Columns3, Table2 } from "lucide-react";
import { fetchDataGenSchema } from "@/lib/api";

type ColumnInfo = { data_type?: string; nullable?: boolean };

/** Groups raw SQL types into something an analyst reads faster than "int8". */
const familyOf = (raw: string): { label: string; tint: string } => {
  const t = (raw || "").toLowerCase();
  if (/(int|numeric|decimal|float|double|real|number)/.test(t)) return { label: "number", tint: "var(--accent-conduit)" };
  if (/(date|time|stamp)/.test(t)) return { label: "date", tint: "var(--accent-amber)" };
  if (/(bool)/.test(t)) return { label: "boolean", tint: "var(--accent-signal)" };
  return { label: "text", tint: "var(--text-3)" };
};

export function DatasetPreview({
  connectionId,
  table,
  supported,
}: {
  connectionId: string;
  table: string;
  supported: boolean;
}) {
  const enabled = supported && !!connectionId && !!table;

  const { data, isLoading, error } = useQuery({
    queryKey: ["studio-schema", connectionId, table],
    queryFn: () => fetchDataGenSchema(connectionId, table),
    enabled,
    retry: false,
    staleTime: 60_000,
  });

  if (!enabled) {
    return (
      <div className="panel">
        <div className="panel-bar">
          <span className="panel-title">Preview</span>
        </div>
        <div className="empty !py-12">
          <span className="empty-mark">
            <Table2 className="h-5 w-5" strokeWidth={1.7} />
          </span>
          <p className="text-[13.5px] font-semibold text-foreground">Nothing selected yet</p>
          <p className="max-w-[15rem] text-[12px] leading-relaxed text-muted-foreground">
            {supported
              ? "Pick a table and its columns, types, and a few sample rows appear here before you generate anything."
              : "This source type doesn't expose a schema. You can still generate — the agent profiles the file when it runs."}
          </p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="panel">
        <div className="panel-bar">
          <span className="panel-title">Preview</span>
          <span className="mono-meta ml-auto">reading schema…</span>
        </div>
        <div className="space-y-2.5 p-4">
          {Array.from({ length: 7 }).map((_, i) => (
            <div key={i} className="flex items-center gap-3">
              <div className="skel h-3 flex-1" />
              <div className="skel h-3 w-14" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel">
        <div className="panel-bar">
          <span className="panel-title">Preview</span>
        </div>
        <div className="p-4">
          <div className="flex items-start gap-2.5 rounded-lg bg-[hsl(var(--accent-amber)/0.1)] p-3">
            <AlertTriangle className="mt-px h-4 w-4 shrink-0 text-[hsl(var(--accent-amber))]" />
            <div>
              <p className="text-[12.5px] font-semibold text-foreground">Couldn't read that table</p>
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                Check the name is spelled exactly as it is in the database. You can still generate —
                the agent will try to profile it directly.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const columns: Record<string, ColumnInfo> = data?.schema?.columns ?? {};
  const names = Object.keys(columns);
  const sampleCount = (data?.schema?.sample_data ?? []).length;

  return (
    <div className="panel">
      <div className="panel-bar">
        <span className="panel-title">Preview</span>
        <span className="chip">
          <Columns3 className="h-3 w-3" />
          {names.length}
        </span>
        <span className="mono-meta ml-auto truncate">{data?.table}</span>
      </div>

      {names.length === 0 ? (
        <div className="empty !py-10">
          <p className="text-[13px] font-semibold text-foreground">No columns returned</p>
          <p className="text-[12px] text-muted-foreground">The table exists but reported no schema.</p>
        </div>
      ) : (
        <>
          <div className="max-h-[340px] overflow-y-auto">
            {names.map((name) => {
              const info = columns[name] ?? {};
              const family = familyOf(info.data_type ?? "");
              return (
                <div
                  key={name}
                  className="flex items-baseline justify-between gap-3 border-b border-border px-4 py-2 last:border-0"
                >
                  <span className="mono-meta truncate !text-[12px] !text-foreground">{name}</span>
                  <span className="flex shrink-0 items-center gap-2">
                    {info.nullable ? <span className="mono-meta !text-[10px] opacity-60">null</span> : null}
                    <span className="mono-meta !text-[10.5px]" style={{ color: family.tint }}>
                      {family.label}
                    </span>
                  </span>
                </div>
              );
            })}
          </div>

          <div className="border-t border-border px-4 py-2.5">
            <p className="mono-meta">
              {names.length} columns · {sampleCount} sample rows read
            </p>
          </div>
        </>
      )}
    </div>
  );
}
