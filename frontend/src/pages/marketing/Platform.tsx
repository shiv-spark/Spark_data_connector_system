import { Link } from "react-router-dom";
import {
  ArrowRight,
  Boxes,
  Cloud,
  Database,
  FileSpreadsheet,
  Globe,
  LayoutDashboard,
  Layers,
  Server,
  Sparkles,
  Table2,
  Workflow,
} from "lucide-react";
import { ConnectorExplorer } from "@/components/marketing/ConnectorExplorer";

const CONNECTORS = [
  { icon: Database, name: "PostgreSQL", detail: "Direct connection or via SSH tunnel" },
  { icon: Database, name: "MySQL & MariaDB", detail: "5.7 and above" },
  { icon: Cloud, name: "Snowflake", detail: "Key-pair or password auth" },
  { icon: Server, name: "Amazon S3", detail: "CSV, JSON, Parquet objects" },
  { icon: Boxes, name: "MongoDB", detail: "Collections flattened to tables" },
  { icon: Globe, name: "REST APIs", detail: "Paginated endpoints with auth headers" },
  { icon: FileSpreadsheet, name: "File upload", detail: "Drop a CSV or a whole folder" },
  { icon: Table2, name: "BigQuery", detail: "Service account credentials" },
];

const CAPABILITIES = [
  {
    id: "pipelines",
    tag: "pipeline",
    icon: Workflow,
    title: "Build the job, then stop thinking about it",
    body: "Pick your sources, describe the transformation, set a schedule. Runs execute on Airflow underneath, so retries, backfills, and dependency ordering behave the way you'd expect from a real orchestrator.",
    features: [
      ["Schedules", "Cron expressions or plain intervals, with timezone handling that survives DST."],
      ["Retries", "Exponential backoff per step. A flaky API doesn't fail the whole run."],
      ["Backfills", "Re-run any window without touching the schedule."],
      ["Observability", "Row counts, durations, and logs kept per step, per run."],
    ],
  },
  {
    id: "multi-source",
    tag: "pipeline",
    icon: Layers,
    title: "Join across systems that were never meant to meet",
    body: "Put Postgres orders next to a Stripe endpoint next to a CSV your finance lead maintains. Define the join keys once and the pipeline resolves them on every run.",
    features: [
      ["Cross-source joins", "Relate tables that live in different databases entirely."],
      ["Type reconciliation", "Mismatched column types are surfaced before the run, not during."],
      ["Schema drift", "A renamed column raises a warning instead of silently producing nulls."],
      ["Preview", "See the joined result on sample rows before you commit the pipeline."],
    ],
  },
  {
    id: "ai",
    tag: "model",
    icon: Sparkles,
    title: "AI that has to show its work",
    body: "Ask a question in plain English against a connection. The model reads your live schema, writes SQL, and hands it to you. Nothing executes until you've read it and said yes.",
    features: [
      ["Text-to-SQL", "Grounded in the actual tables and column types on that connection."],
      ["Query preview", "The generated SQL is always shown first. This can't be disabled."],
      ["Dashboard drafts", "Describe a board and get a starting layout with real charts wired up."],
      ["Synthetic data", "Generate realistic test rows that match a schema, for staging work."],
    ],
  },
  {
    id: "dashboards",
    tag: "surface",
    icon: LayoutDashboard,
    title: "A canvas, not a template",
    body: "Drag charts where they belong and size them to match how much they matter. Edit a chart's query, type, or colours in place, and export the finished board to PDF when someone needs it offline.",
    features: [
      ["Drag-and-drop grid", "Snap-to-grid layout that keeps its shape on smaller screens."],
      ["Edit in place", "Change a chart's query or type without leaving the board."],
      ["Live refresh", "Boards re-query on an interval you set."],
      ["PDF export", "The whole board, laid out, in one click."],
    ],
  },
];

export function Platform() {
  return (
    <div className="mx-auto max-w-[1180px] px-5 pt-14 sm:px-7 sm:pt-20">
      <header className="mk-reveal">
        <span className="mk-label">Platform</span>
        <h1 className="mk-display mt-5 max-w-3xl text-[clamp(2.2rem,5.4vw,3.6rem)] text-[color:var(--mk-graphite)]">
          Four stages, one control plane.
        </h1>
        <p className="mk-lede mt-6">
          Everything here works against the database you already run. Nothing asks you to migrate
          first, and nothing keeps a copy of your data to make a feature easier for us.
        </p>
      </header>

      {/* Connectors --------------------------------------------------------- */}
      <section id="connectors" className="mk-stage mt-20 scroll-mt-24">
        <span className="mk-stage-tag" style={{ color: "var(--mk-conduit)" }}>
          source
        </span>
        <h2 className="mk-display mt-4 max-w-2xl text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
          Connect it where it lives
        </h2>
        <p className="mk-lede mt-4 !text-[15.5px]">
          Paste a connection string and we introspect the schema — tables, columns, types,
          row estimates. Read-only credentials are enough to get started.
        </p>

        <div className="mt-10">
          <ConnectorExplorer />
        </div>

        <p className="mk-label mb-5 mt-14">Every source, in detail</p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {CONNECTORS.map(({ icon: Icon, name, detail }) => (
            <div key={name} className="mk-card mk-card-interactive p-5">
              <Icon className="h-5 w-5" style={{ color: "var(--mk-conduit)" }} strokeWidth={1.8} />
              <h3 className="mt-4 text-[14.5px] font-semibold text-[color:var(--mk-graphite)]">{name}</h3>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-[color:var(--mk-muted)]">{detail}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Capabilities -------------------------------------------------------- */}
      {CAPABILITIES.map(({ id, tag, icon: Icon, title, body, features }) => (
        <section key={id} id={id} className="mk-stage mt-24 scroll-mt-24">
          <span
            className="mk-stage-tag"
            style={{ color: tag === "model" ? "var(--mk-signal)" : "var(--mk-conduit)" }}
          >
            {tag}
          </span>
          <div className="mt-4 grid gap-8 lg:grid-cols-[1fr_1.25fr] lg:gap-16">
            <div>
              <Icon
                className="mb-5 h-6 w-6"
                style={{ color: tag === "model" ? "var(--mk-signal)" : "var(--mk-conduit)" }}
                strokeWidth={1.7}
              />
              <h2 className="mk-display text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
                {title}
              </h2>
              <p className="mk-lede mt-4 !text-[15.5px]">{body}</p>
            </div>

            <dl className="grid gap-x-10 gap-y-6 sm:grid-cols-2 lg:pt-2">
              {features.map(([name, detail]) => (
                <div key={name} className="border-t pt-4" style={{ borderColor: "var(--mk-line)" }}>
                  <dt className="text-[14px] font-semibold text-[color:var(--mk-graphite)]">{name}</dt>
                  <dd className="mt-1.5 text-[13.5px] leading-relaxed text-[color:var(--mk-muted)]">
                    {detail}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </section>
      ))}

      <section className="mt-24">
        <div className="mk-conduit px-6 py-14 text-center sm:px-12">
          <div className="relative">
            <h2 className="mk-display text-[clamp(1.7rem,3.8vw,2.4rem)] text-white">
              Point it at something real
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-[15px] leading-relaxed text-white/55">
              The free plan takes two connections. That's enough to find out whether this fits the
              way your team already works.
            </p>
            <Link to="/signup" className="mk-cta mk-on-dark mt-8">
              Start free
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
