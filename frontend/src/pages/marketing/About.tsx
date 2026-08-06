import { Link } from "react-router-dom";
import { ArrowRight, Mail, MapPin } from "lucide-react";

/* The order here carries the argument: each entry is why the next one happened. */
const MILESTONES: { year: string; title: string; body: string; tint: string }[] = [
  {
    year: "2019",
    title: "The first one was hand-built",
    body: "A retail client needed nightly rollups. We wrote the connector, the scheduler, and the dashboard from scratch. It took eleven weeks and only one of us could maintain it.",
    tint: "#22d3ee",
  },
  {
    year: "2021",
    title: "The fourth rebuild",
    body: "Same shape, different client, fourth codebase. We were copying files between projects and calling it a methodology. The parts that changed were never the interesting parts.",
    tint: "#38bdf8",
  },
  {
    year: "2023",
    title: "One codebase instead of six",
    body: "We stopped shipping bespoke pipelines and put every client behind a single control plane. Eleven weeks became four days, and the client could change things without calling us.",
    tint: "#2dd4bf",
  },
  {
    year: "2026",
    title: "Open to anyone with a database",
    body: "What we ran for a handful of companies is now a product you can point at your own Postgres this afternoon. Same control plane, no consultancy attached.",
    tint: "#34d399",
  },
];

const NUMBERS: [string, string][] = [
  ["40+", "Data teams running on it"],
  ["4 days", "Median time to first dashboard"],
  ["6", "People building it"],
];

const PRINCIPLES: { title: string; body: string }[] = [
  {
    title: "Your database stays yours",
    body: "Connections are read-only until you write a pipeline that says otherwise. We would rather lose a feature than quietly hold a copy of someone's production data.",
  },
  {
    title: "The model proposes, you decide",
    body: "Generated SQL is shown before it runs, every time, with no way to turn the confirmation off. An analyst who can't inspect the query can't defend the number.",
  },
  {
    title: "A run you can't explain is a bug",
    body: "Every pipeline run keeps its logs, timings, and row counts. When a dashboard looks wrong, the answer should be two clicks away, not a Slack thread.",
  },
  {
    title: "Boring where it counts",
    body: "Postgres, cron, and SQL are not problems that need reinventing. We spend our novelty budget on the layer above them, and keep the foundation dull on purpose.",
  },
];

export function About() {
  return (
    <div className="mx-auto max-w-[1180px] px-5 pt-14 sm:px-7 sm:pt-20">
      {/* Opening ------------------------------------------------------------ */}
      <header className="mk-reveal">
        <span className="mk-label">About us</span>
        <h1 className="mk-display mt-5 max-w-3xl text-[clamp(2.2rem,5.4vw,3.6rem)] text-[color:var(--mk-graphite)]">
          We got tired of watching good data sit behind a ticket queue.
        </h1>
        <div className="mt-8 grid gap-8 lg:grid-cols-[1.15fr_1fr] lg:gap-16">
          <div className="space-y-5 text-[16px] leading-[1.65] text-[color:var(--mk-muted)]">
            <p>
              SparkBrains started as a consultancy. We spent years building the same thing for
              different companies: a connector to the warehouse someone already had, a scheduled
              job to shape the data, and a dashboard that went stale the week after we left.
            </p>
            <p>
              The pattern was always the same. The data was fine. The database was fine. What was
              missing was a layer where a person who understood the business could reach it
              without waiting on a person who understood the cluster.
            </p>
            <p className="text-[color:var(--mk-graphite)]">
              So we built that layer, and stopped rebuilding it per client.
            </p>
          </div>

          <dl className="grid h-fit grid-cols-3 gap-3 lg:grid-cols-1 lg:gap-0">
            {NUMBERS.map(([value, label]) => (
              <div
                key={label}
                className="border-t pt-4 lg:pb-5"
                style={{ borderColor: "var(--mk-line)" }}
              >
                <dt className="mk-display text-[clamp(1.6rem,3vw,2rem)] leading-none text-[color:var(--mk-graphite)]">
                  {value}
                </dt>
                <dd className="mt-2 text-[12.5px] leading-snug text-[color:var(--mk-muted)]">{label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </header>

      {/* Timeline ------------------------------------------------------------ */}
      <section className="mk-stage mt-24">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="mk-stage-tag" style={{ color: "var(--mk-conduit)" }}>
              how we got here
            </span>
            <h2 className="mk-display mt-4 text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
              Seven years of building the same thing
            </h2>
          </div>
          <p className="mk-lede !max-w-sm !text-[14.5px]">
            Every version taught us which parts were worth keeping. This is the short account of
            what changed and why.
          </p>
        </div>

        <div className="mk-conduit p-6 sm:p-10">
          <div className="relative flex gap-7 sm:gap-9">
            <div className="flex shrink-0 flex-col pt-2">
              <div className="mk-wire-v flex-1" />
            </div>

            <ol className="flex-1 space-y-10 sm:space-y-12">
              {MILESTONES.map((m, i) => (
                <li key={m.year} className="relative">
                  <span
                    className="mk-node absolute top-1.5 -left-[35px] sm:-left-[43px]"
                    data-live={i === MILESTONES.length - 1 ? "true" : "false"}
                    style={{ color: m.tint }}
                  />
                  <span
                    className="mk-mono text-[11px] font-medium uppercase tracking-[0.16em]"
                    style={{ color: m.tint }}
                  >
                    {m.year}
                  </span>
                  <h3 className="mk-station-title mt-2 !text-[clamp(1.05rem,2.2vw,1.3rem)]">
                    {m.title}
                  </h3>
                  <p className="mt-2.5 max-w-xl text-[14px] leading-relaxed text-white/50">
                    {m.body}
                  </p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      {/* Principles --------------------------------------------------------- */}
      <section id="principles" className="mk-stage mt-24 scroll-mt-24">
        <span className="mk-stage-tag" style={{ color: "var(--mk-signal)" }}>
          how we build
        </span>
        <h2 className="mk-display mt-4 max-w-2xl text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
          Four positions we don't trade away
        </h2>

        <div className="mt-10 grid gap-4 md:grid-cols-2">
          {PRINCIPLES.map((p) => (
            <div key={p.title} className="mk-card mk-card-interactive p-6">
              <h3
                className="text-[16.5px] font-semibold tracking-[-0.015em] text-[color:var(--mk-graphite)]"
                style={{ fontFamily: "var(--mk-display)" }}
              >
                {p.title}
              </h3>
              <p className="mt-3 text-[14.5px] leading-relaxed text-[color:var(--mk-muted)]">{p.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Contact ------------------------------------------------------------ */}
      <section id="contact" className="mk-stage mt-24 scroll-mt-24">
        <span className="mk-label">Contact</span>
        <div className="mt-6 grid gap-8 lg:grid-cols-[1fr_1fr] lg:gap-16">
          <div>
            <h2 className="mk-display text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
              Tell us what you're connecting
            </h2>
            <p className="mk-lede mt-4 !text-[15.5px]">
              If you're weighing this against building it in-house, say so — we'll tell you
              honestly when in-house is the better call.
            </p>
            <div className="mt-7 space-y-3.5">
              <a
                href="mailto:hello@sparkbrains.com"
                className="flex items-center gap-3 text-[14.5px] text-[color:var(--mk-graphite)] transition hover:opacity-70"
              >
                <Mail className="h-4 w-4" style={{ color: "var(--mk-signal)" }} />
                hello@sparkbrains.com
              </a>
              <p className="flex items-center gap-3 text-[14.5px] text-[color:var(--mk-muted)]">
                <MapPin className="h-4 w-4" style={{ color: "var(--mk-signal)" }} />
                Chandigarh, India — remote across IST and CET
              </p>
            </div>
          </div>

          <div className="mk-card p-6">
            <p className="mk-label mb-4 !text-[10px]">Faster than an email</p>
            <p className="text-[14.5px] leading-relaxed text-[color:var(--mk-muted)]">
              Create an account and connect a read-only database. Most questions people write to
              us about are answered by seeing their own schema on screen.
            </p>
            <Link to="/signup" className="mk-cta mt-6 w-full">
              Create an account
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
