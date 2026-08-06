import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

/** One bordered surface holding many hairline-separated rows. */
export function Panel({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("panel", className)}>{children}</div>;
}

/** Toolbar that lives inside the panel's top edge, not floating above it. */
export function PanelBar({
  title,
  count,
  children,
  className,
}: {
  title?: string;
  count?: number;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("panel-bar", className)}>
      {title ? (
        <div className="flex shrink-0 items-center gap-2">
          <span className="panel-title">{title}</span>
          {count !== undefined ? <span className="chip">{count}</span> : null}
        </div>
      ) : null}
      {children}
    </div>
  );
}

export function PanelSearch({
  value,
  onChange,
  placeholder = "Search…",
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  label: string;
}) {
  return (
    <div className="toolbar-search">
      <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
      <input
        type="search"
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}

/**
 * A list row. `state` drives the colour of the leading rail — the one place
 * saturated colour appears in a list.
 */
export function Row({
  state,
  children,
  className,
}: {
  state?: string | null;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("row", className)} data-state={String(state ?? "unknown").toLowerCase().trim()}>
      {children}
    </div>
  );
}

/** Machine values separated by hairline dots rather than `&nbsp;/&nbsp;`. */
export function Meta({ items }: { items: [string, ReactNode][] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1">
      {items.map(([key, value]) => (
        <span key={key} className="inline-flex items-baseline gap-1.5">
          <span className="meta-key">{key}</span>
          <span className="mono-meta">{value}</span>
        </span>
      ))}
    </div>
  );
}

export function EmptyState({
  icon: Icon,
  title,
  body,
  action,
}: {
  icon: LucideIcon;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-mark">
        <Icon className="h-5 w-5" strokeWidth={1.7} />
      </span>
      <p className="text-[14px] font-semibold text-foreground">{title}</p>
      <p className="max-w-sm text-[12.5px] leading-relaxed text-muted-foreground">{body}</p>
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}

/** Shaped like the rows it replaces, so the list doesn't jump when data lands. */
export function RowSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="row" data-state="unknown">
          <div className="flex items-center justify-between gap-4">
            <div className="min-w-0 flex-1 space-y-2.5">
              <div className="flex items-center gap-2">
                <div className="skel h-[15px]" style={{ width: `${120 + (i % 3) * 40}px` }} />
                <div className="skel h-[17px] w-14 rounded-full" />
              </div>
              <div className="skel h-[11px]" style={{ width: `${210 + (i % 2) * 70}px` }} />
            </div>
            <div className="skel h-8 w-24 shrink-0" />
          </div>
        </div>
      ))}
    </div>
  );
}
