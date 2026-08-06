import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, Bot, DatabaseZap, LayoutDashboard, ListChecks } from "lucide-react";
import { Wordmark } from "@/components/marketing/Wordmark";
import { cn } from "@/lib/utils";

type PanelEntry = {
  key: string;
  icon: typeof DatabaseZap;
  label: string;
  title: string;
  detail: string;
  tint: string;
};

/** Sign up looks forward: this is the work the account is for. */
const NEXT_STEPS: PanelEntry[] = [
  {
    key: "source",
    icon: DatabaseZap,
    label: "source",
    title: "Connect a database",
    detail: "A read-only connection string is enough. We map the schema from there.",
    tint: "#22d3ee",
  },
  {
    key: "pipeline",
    icon: ListChecks,
    label: "pipeline",
    title: "Schedule the first run",
    detail: "Shape the data once, then let it run nightly with retries and logs.",
    tint: "#2dd4bf",
  },
  {
    key: "surface",
    icon: LayoutDashboard,
    label: "surface",
    title: "Lay out the board",
    detail: "Ask a question, keep the chart, arrange it, share the link.",
    tint: "#34d399",
  },
];

/** Sign in looks inward: this is what's behind the door. */
const INSIDE: PanelEntry[] = [
  {
    key: "connections",
    icon: DatabaseZap,
    label: "connections",
    title: "Every source you've wired up",
    detail: "Schemas stay mapped and credentials stay read-only.",
    tint: "#22d3ee",
  },
  {
    key: "pipelines",
    icon: ListChecks,
    label: "pipelines",
    title: "Runs, logs, and row counts",
    detail: "Each run keeps its timings, so a wrong number is two clicks from an answer.",
    tint: "#38bdf8",
  },
  {
    key: "assistant",
    icon: Bot,
    label: "assistant",
    title: "Questions in plain English",
    detail: "The SQL is written for you and shown before it runs.",
    tint: "#2dd4bf",
  },
  {
    key: "dashboards",
    icon: LayoutDashboard,
    label: "dashboards",
    title: "Boards exactly as you left them",
    detail: "Same layout, refreshed against live data.",
    tint: "#34d399",
  },
];

/**
 * Split auth shell: form on paper, a vertical run of the conduit alongside it.
 * The panel differs by page — sign up shows what happens next, sign in shows
 * what's waiting — so neither side is filler.
 */
export function AuthLayout({
  mode,
  title,
  subtitle,
  badge,
  children,
  footer,
}: {
  mode: "signin" | "signup";
  title: string;
  subtitle: string;
  badge?: ReactNode;
  children: ReactNode;
  footer: ReactNode;
}) {
  const entries = mode === "signup" ? NEXT_STEPS : INSIDE;

  return (
    <div className="mk-shell grid min-h-full lg:grid-cols-[1fr_1fr]">
      {/* Form side -------------------------------------------------------- */}
      <div className="mk-auth-paper flex flex-col px-5 py-7 sm:px-10 lg:px-14">
        <div className="flex items-center justify-between">
          <Wordmark />
          <Link to="/" className="mk-navlink inline-flex items-center gap-1.5">
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to site
          </Link>
        </div>

        <div className="flex flex-1 items-center justify-center py-10">
          <div className="mk-reveal w-full max-w-[416px]">
            <div className="mk-authcard">
              {badge ? <div className="mb-5">{badge}</div> : null}

              <h1 className="mk-display text-[clamp(1.75rem,3.6vw,2.15rem)] text-[color:var(--mk-graphite)]">
                {title}
              </h1>
              <p className="mt-2.5 text-[14px] leading-relaxed text-[color:var(--mk-muted)]">
                {subtitle}
              </p>

              <div className="mt-7">{children}</div>
            </div>

            <p className="mt-5 text-center text-[13.5px] text-[color:var(--mk-muted)]">{footer}</p>
          </div>
        </div>
      </div>

      {/* Conduit side ------------------------------------------------------ */}
      <div className="mk-conduit relative hidden !rounded-none lg:block">
        <div className="relative flex h-full flex-col justify-center px-14 py-16">
          <span className="mk-mono text-[10.5px] uppercase tracking-[0.18em] text-white/40">
            {mode === "signup" ? "What happens next" : "What's waiting"}
          </span>

          <div className="mt-9 flex gap-6">
            <div className="flex shrink-0 flex-col pt-2">
              <div className="mk-wire-v flex-1" />
            </div>

            <ol className={cn("flex-1", mode === "signup" ? "space-y-11" : "space-y-8")}>
              {entries.map((entry, i) => {
                const Icon = entry.icon;
                return (
                  <li key={entry.key} className="relative">
                    <span
                      className="mk-node absolute -left-[30px] top-1.5"
                      data-live={i === 0 ? "true" : "false"}
                      style={{ color: entry.tint }}
                    />
                    <span className="flex items-center gap-2">
                      <Icon className="h-3.5 w-3.5" style={{ color: entry.tint }} strokeWidth={2.1} />
                      <span
                        className="mk-mono text-[10px] uppercase tracking-[0.16em]"
                        style={{ color: entry.tint }}
                      >
                        {entry.label}
                      </span>
                    </span>
                    <h2 className="mk-station-title mt-2 !text-[16.5px]">{entry.title}</h2>
                    <p className="mt-1.5 max-w-sm text-[13.5px] leading-relaxed text-white/50">
                      {entry.detail}
                    </p>
                  </li>
                );
              })}
            </ol>
          </div>

          <p className="mk-mono mt-14 max-w-sm text-[11px] leading-relaxed text-white/35">
            Connections are read-only by default. Nothing leaves your database unless a pipeline
            you wrote sends it somewhere.
          </p>
        </div>
      </div>
    </div>
  );
}

/* --- Shared field -------------------------------------------------------- */

export function TextField({
  id,
  label,
  icon: Icon,
  aside,
  trailing,
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  label: ReactNode;
  icon: typeof DatabaseZap;
  aside?: ReactNode;
  trailing?: ReactNode;
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <label htmlFor={id} className="mk-field-label">
          {label}
        </label>
        {aside}
      </div>
      <div className="relative">
        <Icon
          className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-[color:var(--mk-muted)]"
          strokeWidth={1.8}
          aria-hidden="true"
        />
        <input id={id} className={cn("mk-input pl-10", trailing && "pr-11", className)} {...props} />
        {trailing}
      </div>
    </div>
  );
}
