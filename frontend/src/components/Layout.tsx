import { useEffect, useState } from "react";
import { NavLink, Outlet, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bell,
  BookOpen,
  Bot,
  ChevronDown,
  ChevronsUpDown,
  CircleHelp,
  Database,
  DatabaseZap,
  Download,
  LayoutDashboard,
  LineChart,
  ListChecks,
  MessageSquare,
  Moon,
  Network,
  PanelLeft,
  Plus,
  ScrollText,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  Waves,
} from "lucide-react";
import { fetchHealth } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useTheme } from "@/components/ThemeProvider";
import { UniversalSearch } from "@/components/UniversalSearch";
import { UserMenu } from "@/components/UserMenu";
import { useAuth } from "@/lib/auth";

type NavItem = { to: string; label: string; icon: typeof Sparkles; badge?: string };
type NavGroup = { label: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { to: "/app", label: "Dashboard Studio", icon: Sparkles, badge: "AI" },
      { to: "/app/monitoring", label: "Monitoring", icon: LayoutDashboard },
    ],
  },
  {
    label: "Build",
    items: [
      { to: "/app/connections", label: "Connections", icon: DatabaseZap },
      { to: "/app/create", label: "Create Pipeline", icon: Plus },
      { to: "/app/pipelines", label: "Pipelines", icon: ListChecks },
      { to: "/app/multi-source", label: "Multi-Source", icon: Network },
    ],
  },
  {
    label: "Data",
    items: [
      { to: "/app/ingest", label: "Direct Ingest", icon: Download },
      { to: "/app/preview", label: "Preview", icon: Database },
    ],
  },
  
  {
  label: "Data",
  items: [
      { to: "/app/ingest", label: "Direct Ingest", icon: Download },
      { to: "/app/preview", label: "Preview", icon: Database },
      { to: "/app/quality", label: "Data Quality", icon: ShieldCheck, badge: "New" },   // ← naya
    ],
  },

  {
    label: "Observe",
    items: [
      { to: "/app/metrics", label: "Metrics", icon: LineChart },
      { to: "/app/logs", label: "Logs", icon: ScrollText },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { to: "/app/assistant", label: "AI Assistant", icon: Bot, badge: "Beta" },
      { to: "/app/text2sql", label: "Text-to-SQL", icon: MessageSquare, badge: "New" },
      { to: "/app/datagenerator", label: "Data Generator", icon: Sparkles, badge: "New" },
      { to: "/app/sql-editor", label: "SQL Editor", icon: Database, badge: "New" },
    ],
  },
];

const ProductMark = () => (
  <div className="relative h-8 w-8 shrink-0 overflow-hidden rounded-[8px] shadow-[inset_0_0_0_1px_rgba(15,23,42,0.18),0_1px_2px_rgba(15,23,42,0.08)] dark:shadow-[inset_0_0_0_1px_rgba(255,255,255,0.1),0_1px_2px_rgba(0,0,0,0.3)]">
    <div className="absolute inset-0 bg-gradient-to-br from-emerald-400 via-teal-500 to-emerald-700" />
    <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_20%,rgba(255,255,255,0.45),transparent_55%)]" />
    <Waves className="absolute left-1/2 top-1/2 h-4 w-4 -translate-x-1/2 -translate-y-1/2 text-white" strokeWidth={2.4} />
  </div>
);

export const Layout = () => {
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 15_000,
  });
  const healthy = !!data && !isError;
  const { theme, setTheme, resolvedTheme } = useTheme();
  const { user } = useAuth();
  const workspace = user?.company?.trim() || "SparkBrains";

  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("dc.sidebar") === "collapsed";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem("dc.sidebar", collapsed ? "collapsed" : "expanded");
    } catch {
      /* storage unavailable — the choice just won't persist */
    }
  }, [collapsed]);

  const toggleTheme = () => {
    if (theme === "system") {
      setTheme(resolvedTheme === "dark" ? "light" : "dark");
    } else {
      setTheme(theme === "dark" ? "light" : "dark");
    }
  };

  return (
    <div className="flex h-full">
      <aside
        className={cn(
          "relative flex shrink-0 flex-col border-r border-border bg-[hsl(var(--sidebar-bg))] transition-[width] duration-200 ease-out",
          collapsed ? "nav-collapsed w-[62px]" : "w-[248px]",
        )}
      >
        <div className={cn("pb-3 pt-4", collapsed ? "px-3" : "px-4")}>
          <div className="flex items-center gap-2.5">
            <ProductMark />
            <div className={cn("min-w-0 flex-1", collapsed && "hidden")}>
              <div className="flex items-center gap-1.5">
                <h1 className="truncate text-[14px] font-semibold tracking-[-0.025em] text-slate-900 dark:text-slate-100" style={{ fontFamily: "var(--font-display)" }}>
                  Data Pipeline
                </h1>
                <span className="rounded bg-slate-100 px-1 py-px text-[9.5px] font-semibold tracking-wide text-slate-500 dark:bg-slate-800 dark:text-slate-400" style={{ fontFamily: "var(--font-mono)" }}>
                  v2.0
                </span>
              </div>
              <p className="truncate text-[11px] text-slate-500 dark:text-slate-400">SparkBrains · Control plane</p>
            </div>
          </div>
        </div>

        <nav className={cn("flex-1 space-y-4 overflow-y-auto py-2", collapsed ? "px-3" : "px-3")}>
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="space-y-0.5">
              {collapsed ? (
                <div className="mx-auto mb-1.5 h-px w-6 bg-border" />
              ) : (
                <div className="section-eyebrow px-2 pb-1.5 pt-1">{group.label}</div>
              )}
              {group.items.map(({ to, label, icon: Icon, badge }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/app"}
                  title={collapsed ? label : undefined}
                  className={({ isActive }) => cn("nav-item", isActive && "active")}
                >
                  <Icon className="nav-icon h-[15px] w-[15px] shrink-0" />
                  {collapsed ? (
                    <span className="sr-only">{label}</span>
                  ) : (
                    <>
                      <span className="min-w-0 flex-1 truncate">{label}</span>
                      {badge ? (
                        <span className="rounded bg-[hsl(var(--accent-signal)/0.12)] px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide text-[hsl(var(--accent-signal))]">
                          {badge}
                        </span>
                      ) : null}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="mx-3 mb-3 mt-2 space-y-2">
          <Link
            to="/app/create"
            title={collapsed ? "New pipeline" : undefined}
            className="header-cta flex h-9 w-full items-center justify-center gap-1.5 rounded-lg text-[12.5px] font-semibold text-white"
          >
            <Plus className="h-3.5 w-3.5" strokeWidth={2.4} />
            {collapsed ? <span className="sr-only">New pipeline</span> : "New pipeline"}
          </Link>

          <div
            className={cn(
              "flex items-center rounded-lg py-2 ring-1 ring-inset ring-border",
              collapsed ? "justify-center px-1" : "justify-between px-2.5",
            )}
            title={collapsed ? (healthy ? "API healthy" : "API unreachable") : undefined}
          >
            <span className={cn("section-eyebrow", collapsed && "hidden")}>API</span>
            <span
              className={cn(
                "inline-flex items-center gap-1.5 text-[11px] font-semibold",
                healthy ? "text-emerald-700 dark:text-emerald-400" : "text-rose-700 dark:text-rose-400",
              )}
            >
              <span className="relative inline-flex h-1.5 w-1.5">
                {healthy ? (
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                ) : null}
                <span
                  className={cn(
                    "relative inline-flex h-1.5 w-1.5 rounded-full",
                    healthy ? "bg-emerald-500" : "bg-rose-500",
                  )}
                />
              </span>
              {collapsed ? null : healthy ? "Healthy" : "Unreachable"}
            </span>
          </div>
        </div>

        <div
          className={cn(
            "border-t border-border px-3 py-2",
            collapsed ? "flex flex-col items-center gap-1" : "flex items-center justify-between",
          )}
        >
          <UserMenu collapsed={collapsed} />
          <div className={cn("flex items-center gap-1", collapsed && "flex-col")}>
            <button className="icon-btn !h-7 !w-7" title="Toggle theme" onClick={toggleTheme}>
              {resolvedTheme === "dark" ? <Moon className="h-3.5 w-3.5" /> : <Sun className="h-3.5 w-3.5" />}
            </button>
            <Link to="/app/settings" className="icon-btn !h-7 !w-7" title="Settings">
              <Settings className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-background">
        <header className="app-header sticky top-0 z-20">
          <div className="flex h-14 items-center gap-3 px-4">
            <button
              onClick={() => setCollapsed((v) => !v)}
              className="icon-btn"
              title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              aria-expanded={!collapsed}
            >
              <PanelLeft className="h-4 w-4" />
            </button>
            <span className="hidden h-5 w-px bg-border sm:block" />

            {/* Workspace / project / env breadcrumb */}
            {/* Workspace and environment are display-only until there is more
                than one of either — a chevron that opens nothing is worse than
                no chevron. */}
            <div className="flex min-w-0 items-center gap-2">
              <div className="inline-flex items-center gap-2 px-1.5 py-1">
                <span className="ws-mark h-5 w-5 rounded-[5px] shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]" />
                <span
                  className="truncate text-[13.5px] font-semibold tracking-[-0.02em] text-slate-900 dark:text-slate-100"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  {workspace}
                </span>
              </div>

              <span className="select-none text-slate-300 dark:text-slate-600">/</span>

              <span className="env-pill inline-flex h-6 items-center gap-1.5 rounded-full px-2.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-400">
                <span className="relative inline-flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                </span>
                production
              </span>
            </div>

            {/* Search bar */}
            <div className="ml-4 hidden lg:block">
              <UniversalSearch />
            </div>

            {/* Right cluster */}
            <div className="ml-auto flex items-center gap-1">
              {/* Status read-out */}
              <div
                className="mr-2 hidden items-center gap-2 rounded-md px-2 py-1 text-[11.5px] text-muted-foreground md:flex"
                title={healthy ? "All systems operational" : "API unreachable"}
              >
                <span className="relative inline-flex h-2 w-2">
                  {healthy ? (
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                  ) : null}
                  <span
                    className={cn(
                      "relative inline-flex h-2 w-2 rounded-full",
                      healthy ? "bg-emerald-500" : "bg-rose-500",
                    )}
                  />
                </span>
                <span className="font-medium text-foreground">
                  {healthy ? "Operational" : "Degraded"}
                </span>
              </div>

              <span className="mx-1 hidden h-5 w-px bg-border md:block" />

              {/* <button className="icon-btn" title="Documentation" aria-label="Documentation">
                <BookOpen className="h-4 w-4" />
              </button>
              <button className="icon-btn" title="Help" aria-label="Help">
                <CircleHelp className="h-4 w-4" />
              </button>
              <button className="icon-btn" title="Notifications" aria-label="Notifications">
                <Bell className="h-4 w-4" />
                <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-rose-500 ring-2 ring-white dark:ring-slate-900" />
              </button>

              <span className="mx-1 hidden h-5 w-px bg-border md:block" />

              <button
                className="ml-1 inline-flex h-8 items-center gap-1.5 rounded-md pl-1 pr-2 transition hover:bg-slate-100 dark:hover:bg-slate-800"
                title="Account"
              >
                <span className="grid h-6 w-6 place-items-center rounded-full bg-gradient-to-br from-emerald-500 via-teal-500 to-emerald-700 text-[10px] font-bold text-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]">
                  G
                </span>
                <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
              </button> */}

            </div>
          </div>
        </header>
        <div className="mx-auto w-full max-w-[1440px] px-6 py-7">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
