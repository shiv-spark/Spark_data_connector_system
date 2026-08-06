import { Link } from "react-router-dom";
import { ArrowRight, Check, Clock, Play, RotateCcw } from "lucide-react";
import { Conduit } from "@/components/marketing/Conduit";
import { ConnectorExplorer } from "@/components/marketing/ConnectorExplorer";

/* --- Small artifacts. Each one shows the real thing the stage produces. ---- */

const RunArtifact = () => (
  <div className="mk-card p-4">
    <div className="mk-mono mb-3 flex items-center justify-between text-[10.5px] text-[color:var(--mk-muted)]">
      <span>nightly-revenue-rollup</span>
      <span className="inline-flex items-center gap-1.5 text-[color:var(--mk-signal)]">
        <Check className="h-3 w-3" /> passed
      </span>
    </div>
    <ul className="space-y-2">
      {[
        ["extract", "48s"],
        ["dedupe", "1m 06s"],
        ["join", "1m 51s"],
        ["load", "27s"],
      ].map(([step, dur], i) => (
        <li key={step} className="flex items-center gap-3">
          <span className="mk-mono w-14 text-[11px] text-[color:var(--mk-graphite)]">{step}</span>
          <span className="h-1.5 flex-1 overflow-hidden rounded-full bg-[color:var(--mk-line)]">
            <span
              className="block h-full rounded-full"
              style={{
                width: `${[26, 38, 62, 15][i]}%`,
                background: "linear-gradient(90deg, var(--mk-conduit), var(--mk-signal))",
              }}
            />
          </span>
          <span className="mk-mono w-12 text-right text-[11px] text-[color:var(--mk-muted)]">{dur}</span>
        </li>
      ))}
    </ul>
  </div>
);

const QueryArtifact = () => (
  <div className="mk-card overflow-hidden">
    <div className="border-b p-4" style={{ borderColor: "var(--mk-line)" }}>
      <p className="mk-label mb-2 !text-[10px]">You ask</p>
      <p className="text-[14px] text-[color:var(--mk-graphite)]">
        Which SKUs lost margin last quarter?
      </p>
    </div>
    <div className="p-4">
      <p className="mk-label mb-2 !text-[10px]">It writes — you approve before it runs</p>
      <pre className="mk-mono overflow-x-auto text-[11px] leading-relaxed text-[color:var(--mk-muted)]">
        <code>
          {`SELECT sku,
       SUM(revenue - cogs) AS margin
FROM   line_items
WHERE  closed_at >= '2026-01-01'
GROUP  BY sku
HAVING SUM(revenue - cogs) < 0`}
        </code>
      </pre>
    </div>
  </div>
);

const BoardArtifact = () => (
  <div className="mk-card p-4">
    <div className="mk-mono mb-3 flex items-center justify-between text-[10.5px] text-[color:var(--mk-muted)]">
      <span>Margin watch</span>
      <span>12 viewers</span>
    </div>
    <div className="grid grid-cols-3 gap-2">
      <div className="col-span-2 flex h-[74px] items-end gap-1 rounded-lg bg-[color:var(--mk-paper-2)] p-2.5">
        {[42, 58, 51, 73, 66, 88, 79].map((h, i) => (
          <div
            key={i}
            className="flex-1 rounded-[2px]"
            style={{ height: `${h}%`, background: "linear-gradient(180deg, var(--mk-signal), color-mix(in srgb, var(--mk-signal) 30%, transparent))" }}
          />
        ))}
      </div>
      <div className="flex h-[74px] flex-col justify-center rounded-lg bg-[color:var(--mk-paper-2)] p-2.5">
        <p className="mk-mono text-[9.5px] uppercase tracking-[0.14em] text-[color:var(--mk-muted)]">at risk</p>
        <p className="mk-display mt-1 text-[24px] text-[color:var(--mk-graphite)]">14</p>
      </div>
      <div className="col-span-3 h-[46px] rounded-lg bg-[color:var(--mk-paper-2)] p-2.5">
        <div className="flex h-full items-end gap-[3px]">
          {[30, 44, 38, 52, 47, 61, 55, 70, 64, 78, 72, 86].map((h, i) => (
            <div
              key={i}
              className="flex-1 rounded-[1px]"
              style={{ height: `${h}%`, background: "color-mix(in srgb, var(--mk-conduit) 45%, transparent)" }}
            />
          ))}
        </div>
      </div>
    </div>
  </div>
);

const STAGES = [
  {
    tag: "pipeline",
    title: "Pipelines that explain themselves",
    body: "Build a job once and schedule it. Every run keeps its logs, timings, and row counts, so when a number looks wrong you can see which step produced it instead of guessing.",
    points: ["Cron or interval schedules", "Automatic retries with backoff", "Per-step logs and row counts"],
    artifact: <RunArtifact />,
  },
  {
    tag: "model",
    title: "Ask in the language you think in",
    body: "Type a question and get SQL back, written against your real schema. You read it and approve it before anything runs — the model proposes, you decide.",
    points: ["SQL shown before execution", "Grounded in your live schema", "Every answer keeps its query"],
    artifact: <QueryArtifact />,
  },
  {
    tag: "surface",
    title: "Dashboards you arrange yourself",
    body: "Drag charts into place, resize them until the layout reads the way you'd explain it out loud, then share it. Export the whole board to PDF when someone wants it in a deck.",
    points: ["Drag-and-drop grid", "Edit any chart in place", "One-click PDF export"],
    artifact: <BoardArtifact />,
  },
];

export function Landing() {
  return (
    <>
      {/* Hero ------------------------------------------------------------- */}
      <section className="mx-auto max-w-[1180px] px-5 pb-16 pt-14 sm:px-7 sm:pt-20">
        <div className="mk-reveal">
          <span className="mk-label">Control plane for data you already have</span>
          <h1 className="mk-display mt-5 text-[clamp(2.4rem,6.2vw,4.4rem)] text-[color:var(--mk-graphite)]">
            Your data already exists.
            <br />
            <span
              style={{
                background: "linear-gradient(100deg, var(--mk-conduit), var(--mk-signal))",
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Point us at it.
            </span>
          </h1>
          <p className="mk-lede mt-6">
            Connect Postgres, Snowflake, S3, or any REST API without moving a row. Build the
            pipeline, ask questions in plain English, and lay out a dashboard your team can
            actually read.
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-3">
            <Link to="/signup" className="mk-cta">
              Start free
              <ArrowRight className="h-4 w-4" />
            </Link>
            <Link to="/platform" className="mk-cta-quiet">
              <Play className="h-3.5 w-3.5" />
              See how it works
            </Link>
          </div>
          <p className="mk-mono mt-4 text-[11.5px] text-[color:var(--mk-muted)]">
            No credit card · Connect a database in about five minutes
          </p>
        </div>

        <div className="mk-reveal mt-14" style={{ animationDelay: "120ms" }}>
          <Conduit />
        </div>
      </section>

      {/* Connectors ------------------------------------------------------- */}
      <section id="connectors" className="mx-auto max-w-[1180px] scroll-mt-24 px-5 pb-20 sm:px-7">
        <div className="mk-stage">
          <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
            <div>
              <span className="mk-stage-tag" style={{ color: "var(--mk-conduit)" }}>
                source
              </span>
              <h2 className="mk-display mt-4 max-w-xl text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
                Pick a source. See what you'd fill in.
              </h2>
            </div>
            <p className="mk-lede !max-w-sm !text-[14.5px]">
              Every connector needs a handful of fields and gives back a mapped schema. Here's
              exactly what that trade looks like on each one.
            </p>
          </div>

          <ConnectorExplorer />
        </div>
      </section>

      {/* Stages ----------------------------------------------------------- */}
      <section id="ai" className="mx-auto max-w-[1180px] px-5 sm:px-7">
        <div className="space-y-20">
          {STAGES.map((stage) => (
            <div key={stage.tag} className="mk-stage grid gap-8 lg:grid-cols-[1fr_1fr] lg:gap-16">
              <div>
                <span className="mk-stage-tag" style={{ color: "var(--mk-signal)" }}>
                  {stage.tag}
                </span>
                <h2 className="mk-display mt-4 text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
                  {stage.title}
                </h2>
                <p className="mk-lede mt-4 !text-[15.5px]">{stage.body}</p>
                <ul className="mt-6 space-y-2.5">
                  {stage.points.map((p) => (
                    <li key={p} className="flex items-start gap-2.5 text-[14px] text-[color:var(--mk-graphite)]">
                      <Check
                        className="mt-[3px] h-3.5 w-3.5 shrink-0"
                        style={{ color: "var(--mk-signal)" }}
                        strokeWidth={2.6}
                      />
                      {p}
                    </li>
                  ))}
                </ul>
              </div>
              <div className="lg:pt-10">{stage.artifact}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Contrast — amber is the only place the palette leaves the flow ---- */}
      <section className="mx-auto mt-24 max-w-[1180px] px-5 sm:px-7">
        <div className="mk-stage">
          <span className="mk-stage-tag" style={{ color: "var(--mk-amber)" }}>
            what this replaces
          </span>
          <h2 className="mk-display mt-4 max-w-2xl text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
            The dashboard request that takes three weeks
          </h2>

          <div className="mt-10 grid gap-6 md:grid-cols-2">
            <div className="mk-card p-6">
              <p className="mk-label mb-4 !text-[10px]" style={{ color: "var(--mk-amber)" }}>
                Today
              </p>
              <ul className="space-y-3.5">
                {[
                  "File a ticket. Wait for someone with warehouse access.",
                  "Stand up an ETL script nobody else can read.",
                  "Rewrite the query four times over Slack.",
                  "Ship a screenshot into a deck. It's stale by Monday.",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3 text-[14px] text-[color:var(--mk-muted)]">
                    <Clock className="mt-[3px] h-3.5 w-3.5 shrink-0" style={{ color: "var(--mk-amber)" }} />
                    {t}
                  </li>
                ))}
              </ul>
            </div>

            <div className="mk-card p-6">
              <p className="mk-label mb-4 !text-[10px]" style={{ color: "var(--mk-signal)" }}>
                With Data Connector
              </p>
              <ul className="space-y-3.5">
                {[
                  "Paste a read-only connection string. Schema appears.",
                  "Describe the job. Schedule it. Watch the first run.",
                  "Ask the question in English. Read the SQL. Run it.",
                  "Arrange the board and share the link. It refreshes itself.",
                ].map((t) => (
                  <li key={t} className="flex items-start gap-3 text-[14px] text-[color:var(--mk-graphite)]">
                    <RotateCcw className="mt-[3px] h-3.5 w-3.5 shrink-0" style={{ color: "var(--mk-signal)" }} />
                    {t}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Close ------------------------------------------------------------ */}
      <section className="mx-auto mt-24 max-w-[1180px] px-5 sm:px-7">
        <div className="mk-conduit px-6 py-16 text-center sm:px-12">
          <div className="relative mx-auto max-w-2xl">
            <h2 className="mk-display text-[clamp(2rem,4.6vw,3rem)] text-white">
              Connect a database. See it working in five minutes.
            </h2>
            <p className="mt-5 text-[16px] leading-relaxed text-white/55">
              Start with a read-only connection to something real. If it doesn't earn its place
              by the end of the trial, disconnect it and nothing of yours has moved.
            </p>
            <div className="mt-9 flex flex-wrap justify-center gap-3">
              <Link to="/signup" className="mk-cta mk-on-dark">
                Start free
                <ArrowRight className="h-4 w-4" />
              </Link>
              <Link to="/pricing" className="mk-cta-quiet mk-on-dark">
                See pricing
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
