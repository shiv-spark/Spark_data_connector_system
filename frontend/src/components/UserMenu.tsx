import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ChevronsUpDown, LogOut, Settings as SettingsIcon } from "lucide-react";
import { getUserInitials } from "@/lib/user";
import { useAuth } from "@/lib/auth";
import { getPlan } from "@/lib/plans";
import { cn } from "@/lib/utils";

export function UserMenu({ collapsed = false }: { collapsed?: boolean }) {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  if (!user) return null;

  const handleSignOut = () => {
    signOut();
    navigate("/", { replace: true });
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={collapsed ? user.name : undefined}
        className={cn(
          "flex items-center gap-2 rounded-md py-1 text-left transition hover:bg-[hsl(var(--surface-2))]",
          collapsed ? "justify-center px-1" : "w-full px-1.5",
        )}
      >
        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gradient-to-br from-emerald-500 via-teal-500 to-emerald-700 text-[10px] font-bold text-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]">
          {getUserInitials(user.name)}
        </span>
        {collapsed ? null : (
          <>
            <span className="flex min-w-0 flex-col items-start leading-tight">
              <span className="max-w-[92px] truncate text-[11.5px] font-semibold text-foreground">
                {user.name}
              </span>
              <span className="text-[10px] text-muted-foreground">{user.role}</span>
            </span>
            <ChevronsUpDown className="ml-auto h-3 w-3 shrink-0 text-muted-foreground" />
          </>
        )}
      </button>

      {open ? (
        <div
          role="menu"
          className="surface-elevated absolute bottom-full left-0 z-50 mb-2 w-[212px] overflow-hidden p-1"
        >
          <div className="border-b border-border px-2.5 py-2">
            <p className="truncate text-[12px] font-semibold text-slate-800 dark:text-slate-200">
              {user.name}
            </p>
            <p className="truncate text-[11px] text-muted-foreground">{user.email}</p>
            <Link
              to="/app/settings"
              onClick={() => setOpen(false)}
              className="mt-1.5 inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 ring-1 ring-inset ring-emerald-200/70 transition hover:brightness-95 dark:bg-emerald-950/60 dark:text-emerald-400 dark:ring-emerald-800"
            >
              {getPlan(user.plan).name} plan
            </Link>
          </div>

          <Link
            to="/app/settings"
            role="menuitem"
            onClick={() => setOpen(false)}
            className="mt-1 flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[12.5px] text-slate-700 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            <SettingsIcon className="h-3.5 w-3.5" />
            Settings
          </Link>

          <button
            role="menuitem"
            onClick={handleSignOut}
            className="flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[12.5px] text-rose-600 transition hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/40"
          >
            <LogOut className="h-3.5 w-3.5" />
            Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
