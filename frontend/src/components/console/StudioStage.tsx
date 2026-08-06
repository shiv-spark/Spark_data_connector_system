import type { ReactNode } from "react";
import { Check, Lock, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * One step of the studio flow. Steps stay visible rather than paging, so the
 * whole path is legible at a glance, but a step that isn't reachable yet says
 * so instead of failing when you use it.
 */
export function StudioStage({
  tag,
  title,
  hint,
  done,
  locked,
  lockedReason,
  children,
}: {
  tag: string;
  title: string;
  hint?: string;
  done?: boolean;
  locked?: boolean;
  lockedReason?: string;
  children: ReactNode;
}) {
  return (
    <section
      className={cn(
        "panel transition-opacity duration-200",
        locked && "pointer-events-none select-none opacity-55",
      )}
      aria-disabled={locked || undefined}
    >
      <div className="panel-bar">
        <span
          className={cn(
            "grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] font-bold transition-colors",
            done
              ? "bg-[hsl(var(--accent-signal))] text-[hsl(var(--primary-foreground))]"
              : locked
                ? "bg-[hsl(var(--surface-2))] text-[hsl(var(--text-3))]"
                : "bg-[hsl(var(--accent-conduit)/0.15)] text-[hsl(var(--accent-conduit))] ring-1 ring-inset ring-[hsl(var(--accent-conduit)/0.4)]",
          )}
        >
          {done ? <Check className="h-3 w-3" strokeWidth={3} /> : locked ? <Lock className="h-2.5 w-2.5" /> : null}
        </span>

        <div className="min-w-0 flex-1">
          <span
            className="mono-meta block !text-[10px] uppercase tracking-[0.16em]"
            style={{ color: "hsl(var(--accent-conduit))" }}
          >
            {tag}
          </span>
          <span className="panel-title">{title}</span>
        </div>

        {hint ? <span className="mono-meta shrink-0">{hint}</span> : null}
      </div>

      <div className="p-4">
        {locked && lockedReason ? (
          <p className="text-[12.5px] text-muted-foreground">{lockedReason}</p>
        ) : (
          children
        )}
      </div>
    </section>
  );
}

/** A selectable data source. */
export function SourceTile({
  icon: Icon,
  name,
  detail,
  selected,
  onClick,
}: {
  icon: LucideIcon;
  name: string;
  detail: string;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" onClick={onClick} className="mk-tile" aria-selected={selected} role="option">
      <span
        className="mk-tile-glyph"
        style={{ color: selected ? "hsl(var(--accent-signal))" : "hsl(var(--text-3))" }}
      >
        <Icon className="h-[17px] w-[17px]" strokeWidth={1.8} />
      </span>
      <span className="min-w-0 text-left">
        <span className="block truncate text-[13px] font-semibold text-foreground">{name}</span>
        <span className="mono-meta block truncate !text-[10.5px]">{detail}</span>
      </span>
    </button>
  );
}
