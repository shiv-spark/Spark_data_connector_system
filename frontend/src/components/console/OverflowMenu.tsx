import { useEffect, useRef, useState, type ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * Holds the actions that shouldn't sit in the main row — rarely used ones, and
 * destructive ones that don't belong a pixel away from Refresh.
 */
export function OverflowMenu({
  children,
  label = "More actions",
  align = "right",
}: {
  children: (close: () => void) => ReactNode;
  label?: string;
  align?: "left" | "right";
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="icon-btn !h-8 !w-8"
        aria-haspopup="menu"
        aria-expanded={open}
        title={label}
        aria-label={label}
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {open ? (
        <div
          role="menu"
          className={cn(
            "surface-elevated absolute top-full z-50 mt-1.5 w-[212px] overflow-hidden p-1",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {children(() => setOpen(false))}
        </div>
      ) : null}
    </div>
  );
}

export function MenuItem({
  icon: Icon,
  children,
  onClick,
  tone = "default",
  disabled,
  href,
}: {
  icon: React.ComponentType<{ className?: string }>;
  children: ReactNode;
  onClick?: () => void;
  tone?: "default" | "danger";
  disabled?: boolean;
  href?: string;
}) {
  const className = cn(
    "flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-[12.5px] transition disabled:opacity-50",
    tone === "danger"
      ? "text-[hsl(var(--accent-rose))] hover:bg-[hsl(var(--accent-rose)/0.1)]"
      : "text-foreground hover:bg-[hsl(var(--surface-2))]",
  );

  if (href) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer" className={className} role="menuitem">
        <Icon className="h-3.5 w-3.5 shrink-0" />
        {children}
      </a>
    );
  }

  return (
    <button type="button" role="menuitem" onClick={onClick} disabled={disabled} className={className}>
      <Icon className="h-3.5 w-3.5 shrink-0" />
      {children}
    </button>
  );
}

export function MenuSeparator() {
  return <div className="my-1 h-px bg-border" />;
}
