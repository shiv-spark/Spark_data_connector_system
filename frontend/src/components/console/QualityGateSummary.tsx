import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { ShieldCheck, ShieldAlert, Wrench, Sparkles, Loader2, Settings2 } from "lucide-react";
import { api } from "@/lib/api";

export interface QualityCheckResult {
  table_name?: string;
  check_name: string;
  status: "PASS" | "FAIL" | "ERROR";
  failed_rows?: number | null;
  message: string;
  fix_suggestion?: string;
}

export interface QualityGateResult {
  status: "PASS" | "FAIL" | "ERROR";
  total_checks: number;
  passed: number;
  failed: number;
  results: QualityCheckResult[];
  run_id?: string;
}

const askAiFix = async (payload: { results: QualityCheckResult[]; connection_id?: number }) => {
  const r = await api.post("/quality/ai-fix", payload);
  return r.data as { advice: string };
};

// Most df_quality check_names carry the column right in the name, e.g.
// "NULL_PCT_CHECK[order_id]" — pull it out so "Fix in Configure" can jump
// straight to that column instead of the whole (possibly 20-column) block.
// DUPLICATE_ROWS_CHECK is the one exception: it has no brackets, but its
// message says "N duplicate row(s) on (col1, col2)" — take the first
// column named there.
function extractColumn(check: QualityCheckResult): string | undefined {
  const bracketMatch = check.check_name.match(/\[([^\]]+)\]/);
  if (bracketMatch) return bracketMatch[1];

  const onMatch = check.message?.match(/\bon \(([^)]+)\)/);
  if (onMatch) return onMatch[1].split(",")[0].trim();

  return undefined;
}

/**
 * Renders a df_quality or quality gate result from an ingest response
 * (see utils/ingest_runner.py) as a readable pass/fail list with each
 * failed check's rule-based fix_suggestion inline, plus an optional
 * "Ask AI to help fix" button for deeper, LLM-reasoned help.
 *
 * Works for both gates: the pre-ingest dataframe gate (which can truly
 * block a run before anything is written) and the post-load table gate.
 */
export function QualityGateSummary({
  title,
  gate,
  connectionId,
  onFixInConfig,
  fixTarget,
}: {
  title: string;
  gate: QualityGateResult | null | undefined;
  connectionId?: number | null;
  /**
   * Optional. When provided, a "Fix in Configure" button appears next to
   * "Ask AI to help fix" — it jumps the caller straight to the editable
   * config (source/schedule fields) instead of leaving the person stuck
   * reading advice with no way to act on it. The caller decides what
   * "jump to config" means (switch tab, scroll, highlight, etc).
   */
  onFixInConfig?: (target?: "df_quality" | "table_quality", column?: string) => void;
  /**
   * Which check spec this gate's failures actually live in — the
   * pre-ingest dataframe gate's config (df_quality_config, editable right
   * in the pipeline's Configure tab) vs the post-load table gate's spec
   * (only editable on the separate Quality Checks page). Passed through
   * to onFixInConfig so the caller can route/highlight correctly instead
   * of always assuming "Configure tab" is the right destination.
   */
  fixTarget?: "df_quality" | "table_quality";
}) {
  const [advice, setAdvice] = useState<string | null>(null);
  const mutation = useMutation({
    mutationFn: askAiFix,
    onSuccess: (data) => setAdvice(data.advice),
  });

  if (!gate || !gate.results?.length) return null;

  const failing = gate.results.filter((r) => r.status !== "PASS");
  const passed = gate.status === "PASS";
  // "Fix in Configure" jumps to the FIRST failing check's column — good
  // enough for the common case (one bad column). With several different
  // columns failing, the person still lands in the right section and can
  // open the others themselves; the list right below already shows all of
  // them by name.
  const firstFailingColumn = failing.length > 0 ? extractColumn(failing[0]) : undefined;

  return (
    <div className="space-y-2 rounded-md border border-border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 text-sm font-medium">
          {passed ? (
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
          ) : (
            <ShieldAlert className="h-4 w-4 text-rose-600" />
          )}
          {title}: <span className={passed ? "text-emerald-600" : "text-rose-600"}>{gate.status}</span>{" "}
          <span className="text-muted-foreground">
            ({gate.passed}/{gate.total_checks} checks passed)
          </span>
        </div>
        {!passed && failing.length > 0 && (
          <div className="flex items-center gap-1.5">
            {onFixInConfig && (
              <button
                type="button"
                onClick={() => onFixInConfig(fixTarget, firstFailingColumn)}
                className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs font-medium text-foreground transition hover:bg-[hsl(var(--surface-2))]"
              >
                <Settings2 className="h-3.5 w-3.5" /> Fix in Configure
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                setAdvice(null);
                mutation.mutate({ results: failing, connection_id: connectionId ?? undefined });
              }}
              disabled={mutation.isPending}
              className="inline-flex items-center gap-1.5 rounded-md border border-indigo-200 bg-indigo-50 px-2.5 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-60 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-300"
            >
              {mutation.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
              Ask AI to help fix
            </button>
          </div>
        )}
      </div>

      {failing.length > 0 && (
        <ul className="space-y-1.5">
          {failing.map((r, i) => (
            <li key={i} className="rounded-md bg-muted/50 p-2 text-xs">
              <div className="font-mono text-foreground">
                {r.table_name ? `${r.table_name} — ` : ""}
                {r.check_name}
                {typeof r.failed_rows === "number" && r.failed_rows > 0 ? ` (${r.failed_rows} row(s))` : ""}
              </div>
              <div className="mt-0.5 text-muted-foreground">{r.message}</div>
              {r.fix_suggestion && (
                <div className="mt-1 flex gap-1.5 rounded bg-amber-50 px-2 py-1 text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                  <Wrench className="mt-0.5 h-3 w-3 shrink-0" />
                  <span>{r.fix_suggestion}</span>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {mutation.isError && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700 dark:border-rose-800 dark:bg-rose-950 dark:text-rose-400">
          Couldn't get AI fix help — {(mutation.error as any)?.response?.data?.detail ?? (mutation.error as Error).message}
        </div>
      )}

      {advice && (
        <div className="rounded-md border border-indigo-200 bg-indigo-50 p-2.5 text-xs text-indigo-900 dark:border-indigo-800 dark:bg-indigo-950/40 dark:text-indigo-200">
          <div className="mb-1 flex items-center gap-1.5 font-semibold uppercase tracking-wide">
            <Sparkles className="h-3 w-3" /> AI fix suggestions
          </div>
          <div className="whitespace-pre-wrap">{advice}</div>
          {onFixInConfig && (
            <button
              type="button"
              onClick={() => onFixInConfig(fixTarget, firstFailingColumn)}
              className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-indigo-700"
            >
              <Settings2 className="h-3.5 w-3.5" /> Take me to Configure
            </button>
          )}
        </div>
      )}
    </div>
  );
}
