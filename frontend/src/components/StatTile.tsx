import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export type StatTone = "neutral" | "positive" | "warning" | "critical" | "info";

/** Tone drives both the numeral colour and the hairline across the tile's top edge. */
const TONES: Record<StatTone, { text: string; rail: string }> = {
  neutral:  { text: "text-foreground",                              rail: "text-slate-300 dark:text-slate-600" },
  positive: { text: "text-emerald-600 dark:text-emerald-400",       rail: "text-emerald-500" },
  warning:  { text: "text-amber-600 dark:text-amber-500",           rail: "text-amber-500" },
  critical: { text: "text-rose-600 dark:text-rose-400",             rail: "text-rose-500" },
  info:     { text: "text-cyan-700 dark:text-cyan-400",             rail: "text-cyan-500" },
};

export function StatTile({
  label,
  value,
  tone = "neutral",
  icon: Icon,
  detail,
  className,
}: {
  label: string;
  value: ReactNode;
  tone?: StatTone;
  icon?: LucideIcon;
  detail?: string;
  className?: string;
}) {
  const t = TONES[tone];

  return (
    <div className={cn("stat-tile", t.rail, className)}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {label}
        </p>
        {Icon ? <Icon className={cn("h-3.5 w-3.5 shrink-0", t.rail)} strokeWidth={2} /> : null}
      </div>

      <p className={cn("stat-value mt-2.5 truncate text-[26px]", t.text)}>{value}</p>

      {detail ? (
        <p className="mt-2 truncate text-[11.5px] text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  );
}
