import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowUpRight, Check, Info } from "lucide-react";
import { api } from "@/lib/api";
import { formatLimit, formatRows, getPlan, nextPlan, type PlanId } from "@/lib/plans";
import { cn } from "@/lib/utils";

const fetchConnectionCount = async (): Promise<number> => {
  const r = await api.get("/connections");
  return (r.data?.connections ?? []).length;
};

const fetchPipelineCount = async (): Promise<number> => {
  const r = await api.get("/pipelines");
  return (r.data?.pipelines ?? []).length;
};

/** A metered row with a real number behind it. */
function UsageBar({ label, used, limit }: { label: string; used: number; limit: number }) {
  const unlimited = limit === Infinity;
  const ratio = unlimited ? 0 : Math.min(1, used / limit);
  const over = !unlimited && used > limit;
  const near = !over && ratio >= 0.8;

  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[13px] text-foreground">{label}</span>
        <span className="stat-value text-[13px] text-muted-foreground">
          <span className={cn(over && "text-rose-600 dark:text-rose-400", near && "text-amber-600 dark:text-amber-500")}>
            {used.toLocaleString()}
          </span>
          <span className="mx-1 opacity-50">/</span>
          {formatLimit(limit)}
        </span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div
          className={cn(
            "h-full rounded-full transition-[width] duration-500",
            over ? "bg-rose-500" : near ? "bg-amber-500" : "bg-gradient-to-r from-cyan-500 to-emerald-500",
          )}
          style={{ width: unlimited ? "8%" : `${Math.max(ratio * 100, used > 0 ? 4 : 0)}%` }}
        />
      </div>
    </div>
  );
}

/** A limit the product doesn't measure yet. Says so, rather than inventing a number. */
function UnmeteredRow({ label, limit }: { label: string; limit: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-[13px] text-foreground">{label}</span>
      <span className="flex items-center gap-2">
        <span className="text-[12px] text-muted-foreground">Not measured yet</span>
        <span className="stat-value text-[13px] text-muted-foreground">
          <span className="mx-1 opacity-50">/</span>
          {limit}
        </span>
      </span>
    </div>
  );
}

export function PlanUsage({ planId }: { planId: PlanId }) {
  const plan = getPlan(planId);
  const upgrade = nextPlan(plan.id);

  const { data: connections = 0 } = useQuery({
    queryKey: ["usage-connections"],
    queryFn: fetchConnectionCount,
    retry: false,
  });
  const { data: pipelines = 0 } = useQuery({
    queryKey: ["usage-pipelines"],
    queryFn: fetchPipelineCount,
    retry: false,
  });

  const price =
    plan.monthly === null ? "Custom" : plan.monthly === 0 ? "Free" : `$${plan.monthly}/mo`;

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-6 py-4">
        <h2 className="text-base font-semibold text-foreground">Plan and usage</h2>
        <Link
          to="/pricing"
          className="inline-flex items-center gap-1.5 text-[13px] font-semibold text-emerald-700 hover:underline dark:text-emerald-400"
        >
          Compare plans
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      <div className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2.5">
              <h3 className="page-title !text-[20px]">{plan.name}</h3>
              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-emerald-700 ring-1 ring-inset ring-emerald-200/70 dark:bg-emerald-950/60 dark:text-emerald-400 dark:ring-emerald-800">
                Current plan
              </span>
            </div>
            <p className="mt-1.5 text-[13px] text-muted-foreground">{plan.tagline}</p>
          </div>
          <p className="stat-value text-[24px] text-foreground">{price}</p>
        </div>

        <div className="mt-7 space-y-5">
          <UsageBar label="Connections" used={connections} limit={plan.limits.connections} />
          <UsageBar label="Seats" used={1} limit={plan.limits.seats} />
          <UnmeteredRow
            label="Pipeline runs this month"
            limit={formatLimit(plan.limits.pipelineRuns)}
          />
          <UnmeteredRow label="Rows processed this month" limit={formatRows(plan.limits.rows)} />
        </div>

        <p className="mt-5 flex items-start gap-2 rounded-md bg-muted/60 p-3 text-[12px] leading-relaxed text-muted-foreground">
          <Info className="mt-px h-3.5 w-3.5 shrink-0" />
          Connections and seats are counted live. Run and row metering isn't wired up yet, and no
          limit is enforced anywhere — you have {pipelines.toLocaleString()}{" "}
          {pipelines === 1 ? "pipeline" : "pipelines"} defined.
        </p>

        {upgrade ? (
          <div className="mt-6 rounded-lg border border-border bg-muted/40 p-5">
            <p className="section-eyebrow">Next step up</p>
            <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
              <div>
                <h4 className="text-[15px] font-semibold text-foreground">{upgrade.name}</h4>
                <p className="mt-1 text-[12.5px] text-muted-foreground">{upgrade.tagline}</p>
              </div>
              <Link
                to="/pricing"
                className="inline-flex h-9 items-center gap-1.5 rounded-md bg-gradient-to-b from-emerald-500 to-emerald-600 px-4 text-[13px] font-semibold text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.2)] transition hover:brightness-105"
              >
                See {upgrade.name}
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>
            <ul className="mt-4 grid gap-2 sm:grid-cols-2">
              {upgrade.includes.slice(0, 4).map((f) => (
                <li key={f} className="flex items-start gap-2 text-[12.5px] text-muted-foreground">
                  <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" strokeWidth={2.6} />
                  {f}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}
