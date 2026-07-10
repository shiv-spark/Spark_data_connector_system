import { NavLink, Outlet } from "react-router-dom";
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
  Network,
  Plus,
  ScrollText,
  Search,
  Settings,
  Sparkles,
  Waves,
} from "lucide-react";
import { fetchHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

type NavItem = { to: string; label: string; icon: typeof Sparkles; badge?: string };
type NavGroup = { label: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { to: "/", label: "Dashboard Studio", icon: Sparkles, badge: "AI" },
      { to: "/monitoring", label: "Monitoring", icon: LayoutDashboard },
    ],
  },
  {
    label: "Build",
    items: [
      { to: "/connections", label: "Connections", icon: DatabaseZap },
      { to: "/create", label: "Create Pipeline", icon: Plus },
      { to: "/pipelines", label: "Pipelines", icon: ListChecks },
      { to: "/multi-source", label: "Multi-Source", icon: Network },
    ],
  },
  {
    label: "Data",
    items: [
      { to: "/ingest", label: "Direct Ingest", icon: Download },
      { to: "/preview", label: "Preview", icon: Database },
    ],
  },
  {
    label: "Observe",
    items: [
      { to: "/metrics", label: "Metrics", icon: LineChart },
      { to: "/logs", label: "Logs", icon: ScrollText },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { to: "/assistant", label: "AI Assistant", icon: Bot, badge: "Beta" },
      { to: "/text2sql", label: "Text-to-SQL", icon: MessageSquare, badge: "New" },
      { to: "/datagenerator", label: "Data Generator", icon: Sparkles, badge: "New" },
      { to: "/sql-editor", label: "SQL Editor", icon: Database, badge: "New" },
    ],
  },
];

const ProductMark = () => (
  <div className="relative h-8 w-8 shrink-0 overflow-hidden rounded-[8px] shadow-[inset_0_0_0_1px_rgba(15,23,42,0.18),0_1px_2px_rgba(15,23,42,0.08)]">
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

  return (
    <div className="flex h-full">
      <aside className="relative flex w-[248px] shrink-0 flex-col border-r border-slate-200/70 bg-white/70 backdrop-blur">
        <div className="px-4 pt-4 pb-3">
          <div className="flex items-center gap-2.5">
            <ProductMark />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <h1 className="truncate text-[13.5px] font-semibold tracking-tight text-slate-900">
                  Data Pipeline
                </h1>
                <span className="rounded bg-slate-100 px-1 py-px text-[9.5px] font-semibold tracking-wide text-slate-500" style={{ fontFamily: "var(--font-mono)" }}>
                  v2.0
                </span>
              </div>
              <p className="truncate text-[11px] text-slate-500">SparkBrains · Control plane</p>
            </div>
          </div>
        </div>

        <div className="px-3 pb-2">
          <button
            className="group flex w-full items-center gap-2 rounded-md border border-slate-200/80 bg-white px-2.5 py-1.5 text-left shadow-[0_1px_0_rgba(15,23,42,0.03)] transition hover:border-slate-300"
          >
            <Search className="h-3.5 w-3.5 text-slate-400" />
            <span className="flex-1 text-[12px] text-slate-400">Quick find</span>
            <span className="kbd">⌘K</span>
          </button>
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-2">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="space-y-0.5">
              <div className="px-2 pb-1.5 pt-1 text-[10.5px] font-semibold uppercase tracking-[0.12em] text-slate-400">
                {group.label}
              </div>
              {group.items.map(({ to, label, icon: Icon, badge }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  className={({ isActive }) => cn("nav-item", isActive && "active")}
                >
                  <Icon className="nav-icon h-[15px] w-[15px] shrink-0 text-slate-500" />
                  <span className="min-w-0 flex-1 truncate">{label}</span>
                  {badge ? (
                    <span className="rounded bg-gradient-to-b from-emerald-50 to-emerald-100 px-1.5 py-0.5 text-[9.5px] font-semibold uppercase tracking-wide text-emerald-700 ring-1 ring-inset ring-emerald-200/70">
                      {badge}
                    </span>
                  ) : null}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="mx-3 mb-3 mt-2 rounded-[10px] border border-slate-200/80 bg-gradient-to-b from-white to-slate-50/60 p-3 shadow-[0_1px_0_rgba(15,23,42,0.03)]">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-[10.5px] font-semibold uppercase tracking-[0.14em] text-slate-500">
              System
            </span>
            <span
              className={cn(
                "inline-flex items-center gap-1 text-[10.5px] font-semibold",
                healthy ? "text-emerald-700" : "text-rose-700",
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
              {healthy ? "Healthy" : "Down"}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-1.5 text-center">
            <div className="rounded-md bg-white px-1 py-1.5 ring-1 ring-inset ring-slate-200/70">
              <div className="text-[10px] font-medium text-slate-500">API</div>
              <div className="text-[11px] font-semibold text-slate-900" style={{ fontFamily: "var(--font-mono)" }}>
                42ms
              </div>
            </div>
            <div className="rounded-md bg-white px-1 py-1.5 ring-1 ring-inset ring-slate-200/70">
              <div className="text-[10px] font-medium text-slate-500">Jobs</div>
              <div className="text-[11px] font-semibold text-slate-900" style={{ fontFamily: "var(--font-mono)" }}>
                12
              </div>
            </div>
            <div className="rounded-md bg-white px-1 py-1.5 ring-1 ring-inset ring-slate-200/70">
              <div className="text-[10px] font-medium text-slate-500">Err</div>
              <div className="text-[11px] font-semibold text-emerald-600" style={{ fontFamily: "var(--font-mono)" }}>
                0
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-slate-200/70 px-3 py-2">
          <button className="flex items-center gap-2 rounded-md px-1.5 py-1 transition hover:bg-slate-100">
            <span className="grid h-6 w-6 place-items-center rounded-full bg-gradient-to-br from-emerald-500 via-teal-500 to-emerald-700 text-[10px] font-bold text-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]">
              G
            </span>
            <div className="flex flex-col items-start leading-tight">
              <span className="text-[11.5px] font-semibold text-slate-800">Gaurav</span>
              <span className="text-[10px] text-slate-500">Owner</span>
            </div>
          </button>
          <button className="icon-btn !h-7 !w-7" title="Settings">
            <Settings className="h-3.5 w-3.5" />
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto">
        <header className="app-header sticky top-0 z-20">
          <div className="mx-auto flex h-14 max-w-[1500px] items-center gap-3 px-5">
            {/* Workspace / project / env breadcrumb */}
            <div className="flex min-w-0 items-center gap-2">
              <button className="group inline-flex items-center gap-2 rounded-md px-1.5 py-1 transition hover:bg-slate-100">
                <span className="ws-mark h-5 w-5 rounded-[5px] shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]" />
                <span className="text-[13px] font-semibold text-slate-900">SparkBrains</span>
                <ChevronsUpDown className="h-3.5 w-3.5 text-slate-400 transition group-hover:text-slate-600" />
              </button>

              <span className="select-none text-slate-300">/</span>

              <button className="group inline-flex items-center gap-1.5 rounded-md px-1.5 py-1 transition hover:bg-slate-100">
                <span className="text-[13px] font-medium text-slate-700">data-pipeline</span>
                <ChevronDown className="h-3.5 w-3.5 text-slate-400 transition group-hover:text-slate-600" />
              </button>

              <span className="select-none text-slate-300">/</span>

              <button className="env-pill inline-flex h-6 items-center gap-1.5 rounded-full px-2 text-[11px] font-semibold text-emerald-700 transition hover:brightness-[0.98]">
                <span className="relative inline-flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                </span>
                production
                <ChevronDown className="h-3 w-3 text-emerald-600/70" />
              </button>
            </div>

            {/* Command palette trigger */}
            <button className="cmdk-trigger group ml-4 hidden h-8 w-[300px] items-center gap-2 rounded-md px-2.5 text-left lg:flex xl:w-[380px]">
              <Search className="h-3.5 w-3.5 text-slate-400" />
              <span className="flex-1 text-[12.5px] text-slate-400 group-hover:text-slate-500">
                Search pipelines, runs, logs…
              </span>
              <span className="kbd">⌘K</span>
            </button>

            {/* Right cluster */}
            <div className="ml-auto flex items-center gap-1">
              {/* Status read-out */}
              <div
                className="mr-2 hidden items-center gap-2 rounded-md px-2 py-1 text-[11.5px] text-slate-500 md:flex"
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
                <span className="font-medium text-slate-700">
                  {healthy ? "Operational" : "Degraded"}
                </span>
                <span className="hidden text-slate-300 xl:inline">·</span>
                <span
                  className="hidden text-slate-500 xl:inline"
                  style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}
                >
                  4m ago
                </span>
              </div>

              <span className="mx-1 hidden h-5 w-px bg-slate-200 md:block" />

              <button className="icon-btn" title="Documentation" aria-label="Documentation">
                <BookOpen className="h-4 w-4" />
              </button>
              <button className="icon-btn" title="Help" aria-label="Help">
                <CircleHelp className="h-4 w-4" />
              </button>
              <button className="icon-btn" title="Notifications" aria-label="Notifications">
                <Bell className="h-4 w-4" />
                <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-rose-500 ring-2 ring-white" />
              </button>

              <span className="mx-1 hidden h-5 w-px bg-slate-200 md:block" />

              <button
                className="ml-1 inline-flex h-8 items-center gap-1.5 rounded-md pl-1 pr-2 transition hover:bg-slate-100"
                title="Account"
              >
                <span className="grid h-6 w-6 place-items-center rounded-full bg-gradient-to-br from-emerald-500 via-teal-500 to-emerald-700 text-[10px] font-bold text-white shadow-[inset_0_0_0_1px_rgba(15,23,42,0.12)]">
                  G
                </span>
                <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
              </button>

            </div>
          </div>
        </header>
        <div className="mx-auto max-w-[1500px] px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
