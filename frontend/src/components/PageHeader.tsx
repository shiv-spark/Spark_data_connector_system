import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * One heading treatment for every console page. Replaces the three ad-hoc
 * styles that had drifted apart across pages (`h-section`, `text-2xl font-bold`,
 * `text-xl font-semibold`).
 */
export function PageHeader({
  icon: Icon,
  eyebrow,
  title,
  description,
  actions,
  className,
}: {
  icon?: LucideIcon;
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={cn("mb-6 flex flex-wrap items-start justify-between gap-4", className)}>
      <div className="flex min-w-0 items-start gap-3">
        {Icon ? (
          <span className="page-icon mt-0.5">
            <Icon className="h-[17px] w-[17px]" strokeWidth={1.9} />
          </span>
        ) : null}
        <div className="min-w-0">
          {eyebrow ? <div className="section-eyebrow mb-1.5">{eyebrow}</div> : null}
          <h1 className="page-title truncate">{title}</h1>
          {description ? (
            <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-muted-foreground">
              {description}
            </p>
          ) : null}
        </div>
      </div>

      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
