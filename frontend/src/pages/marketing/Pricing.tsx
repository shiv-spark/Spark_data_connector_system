import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, Minus } from "lucide-react";
import { PLANS, PLAN_ORDER, formatLimit, formatRows, type PlanId } from "@/lib/plans";

const EXTRA_SEAT = PLANS.team.extraSeat ?? 9;

/** Presentation for each plan; the numbers themselves come from lib/plans. */
const TIER_META: Record<PlanId, { cta: string; to: string; featured?: boolean }> = {
  developer:  { cta: "Start free",       to: "/signup" },
  team:       { cta: "Start free trial", to: "/signup", featured: true },
  enterprise: { cta: "Talk to us",       to: "/about#contact" },
};

const TIERS = PLAN_ORDER.map((id) => {
  const plan = PLANS[id];
  return {
    ...plan,
    ...TIER_META[id],
    limits: [
      ["Connections", formatLimit(plan.limits.connections)],
      ["Pipeline runs", plan.limits.pipelineRuns === Infinity ? "Unlimited" : `${formatLimit(plan.limits.pipelineRuns)} / month`],
      ["Rows processed", plan.limits.rows === Infinity ? "Negotiated" : `${formatRows(plan.limits.rows)} / month`],
      [
        "Seats",
        plan.extraSeat
          ? `${formatLimit(plan.limits.seats)}, then $${plan.extraSeat} each`
          : formatLimit(plan.limits.seats),
      ],
    ] as [string, string][],
  };
});

/* --- Estimator ------------------------------------------------------------ */

const ROWS = [1e6, 5e6, 25e6, 100e6, 500e6, 2e9];
const ROW_LABELS = ["1M", "5M", "25M", "100M", "500M", "2B+"];
const CONNS = [1, 2, 5, 10, 25, 50];
const CONN_LABELS = ["1", "2", "5", "10", "25", "50+"];
const SEATS = [1, 3, 5, 10, 25, 50];
const SEAT_LABELS = ["1", "3", "5", "10", "25", "50+"];

const CAPS = PLAN_ORDER.map((id) => ({
  name: PLANS[id].name,
  rows: PLANS[id].limits.rows,
  conns: PLANS[id].limits.connections,
  // Team sells extra seats rather than capping them, so seats never force an
  // upgrade past it.
  seats: id === "team" ? Infinity : PLANS[id].limits.seats,
}));

const DIMENSION_COPY: Record<string, string> = {
  rows: "rows a month",
  conns: "connections",
  seats: "seats",
};

function recommend(rows: number, conns: number, seats: number) {
  const index = CAPS.findIndex((c) => rows <= c.rows && conns <= c.conns && seats <= c.seats);
  const plan = CAPS[index];

  // Name the limit that pushed the recommendation up, so the answer is arguable
  // rather than a black box.
  let reason = "Everything fits inside the free plan.";
  if (index > 0) {
    const under = CAPS[index - 1];
    const exceeded: string[] = [];
    if (rows > under.rows) exceeded.push(DIMENSION_COPY.rows);
    if (conns > under.conns) exceeded.push(DIMENSION_COPY.conns);
    if (seats > under.seats) exceeded.push(DIMENSION_COPY.seats);
    reason = `${under.name} caps out first on ${exceeded.join(" and ")}.`;
  }

  return { plan: plan.name, index, reason };
}

function Slider({
  label,
  value,
  labels,
  onChange,
}: {
  label: string;
  value: number;
  labels: string[];
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <label className="text-[12.5px] font-medium text-white/55" htmlFor={`slider-${label}`}>
          {label}
        </label>
        <span className="mk-mono text-[13px] font-medium text-white">{labels[value]}</span>
      </div>
      <input
        id={`slider-${label}`}
        type="range"
        className="mk-range"
        min={0}
        max={labels.length - 1}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-valuetext={labels[value]}
      />
    </div>
  );
}

function Estimator({ yearly }: { yearly: boolean }) {
  const [rowIdx, setRowIdx] = useState(2);
  const [connIdx, setConnIdx] = useState(2);
  const [seatIdx, setSeatIdx] = useState(2);

  const result = useMemo(
    () => recommend(ROWS[rowIdx], CONNS[connIdx], SEATS[seatIdx]),
    [rowIdx, connIdx, seatIdx],
  );

  const seats = SEATS[seatIdx];
  const base = (yearly ? PLANS.team.yearly : PLANS.team.monthly) ?? 0;
  const extraSeats = result.plan === "Team" ? Math.max(0, seats - 10) : 0;
  const total = base + extraSeats * EXTRA_SEAT;

  return (
    <div className="mk-conduit p-5 sm:p-7">
      <div className="relative grid gap-8 lg:grid-cols-[1fr_1fr] lg:gap-12">
        <div>
          <p className="mk-mono mb-5 text-[10.5px] uppercase tracking-[0.18em] text-white/40">
            Size it yourself
          </p>
          <div className="space-y-5">
            <Slider label="Rows processed each month" value={rowIdx} labels={ROW_LABELS} onChange={setRowIdx} />
            <Slider label="Connections" value={connIdx} labels={CONN_LABELS} onChange={setConnIdx} />
            <Slider label="People who need a seat" value={seatIdx} labels={SEAT_LABELS} onChange={setSeatIdx} />
          </div>
        </div>

        <div className="flex flex-col justify-center border-t border-white/10 pt-7 lg:border-l lg:border-t-0 lg:pl-12 lg:pt-0">
          <p className="mk-mono text-[10.5px] uppercase tracking-[0.18em] text-white/40">
            Your plan
          </p>

          <div key={result.plan} className="mk-swap">
            <p className="mk-display mt-3 text-[40px] leading-none text-white">{result.plan}</p>

            <p className="mt-4 text-[14px] leading-relaxed text-white/55">{result.reason}</p>

            <div className="mt-6 border-t border-white/10 pt-5">
              {result.plan === "Developer" ? (
                <p className="mk-display text-[26px] text-emerald-300">Free</p>
              ) : result.plan === "Enterprise" ? (
                <p className="mk-display text-[26px] text-emerald-300">Let's talk</p>
              ) : (
                <>
                  <p className="mk-display text-[26px] text-emerald-300">
                    ${total}
                    <span className="mk-mono ml-1.5 text-[12px] font-normal text-white/45">
                      / month
                    </span>
                  </p>
                  <p className="mk-mono mt-2 text-[11px] text-white/40">
                    ${base} base
                    {extraSeats > 0 ? ` + ${extraSeats} extra seat${extraSeats > 1 ? "s" : ""} × $${EXTRA_SEAT}` : ""}
                    {yearly ? " · billed annually" : ""}
                  </p>
                </>
              )}
            </div>

            <Link
              to={result.plan === "Enterprise" ? "/about#contact" : "/signup"}
              className="mk-cta mk-on-dark mt-6 w-full"
            >
              {result.plan === "Enterprise" ? "Talk to us" : "Start free"}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

/* --- Comparison ----------------------------------------------------------- */

const MATRIX: { group: string; rows: [string, string | boolean, string | boolean, string | boolean][] }[] = [
  {
    group: "Connect",
    rows: [
      ["Postgres, MySQL, Snowflake, S3", true, true, true],
      ["REST API and file uploads", true, true, true],
      ["Schema drift detection", false, true, true],
      ["Private network connectivity", false, false, true],
    ],
  },
  {
    group: "Build",
    rows: [
      ["Manual pipeline runs", true, true, true],
      ["Scheduled runs", "Hourly minimum", "Per minute", "Per minute"],
      ["Multi-source joins", false, true, true],
      ["Run history", "7 days", "90 days", "Unlimited"],
    ],
  },
  {
    group: "Analyze",
    rows: [
      ["Text-to-SQL", true, true, true],
      ["AI dashboard generation", true, true, true],
      ["Bring your own model key", false, true, true],
    ],
  },
  {
    group: "Govern",
    rows: [
      ["SSO / SAML", false, false, true],
      ["Row-level access policies", false, false, true],
      ["Audit log export", false, false, true],
      ["Support", "Community", "Email, 1 business day", "Named engineer"],
    ],
  },
];

const FAQ: [string, string][] = [
  [
    "What counts as a row processed?",
    "Rows that a pipeline reads from a source during a run. Reading the same table twice in one run counts once. Previewing data in the console is free and never metered.",
  ],
  [
    "Does my data leave my infrastructure?",
    "Only if a pipeline you wrote sends it somewhere. Connections are read-only by default, and the console queries your database directly rather than holding a copy.",
  ],
  [
    "What happens when I hit a limit?",
    "Pipelines keep running and we email you. Nothing is cut off mid-run. You choose whether to upgrade or let the counter reset at the start of the next cycle.",
  ],
  [
    "Can I change plans later?",
    "Yes, in the console under Settings. Upgrades apply immediately and we prorate the difference. Downgrades take effect at the end of the billing period.",
  ],
  [
    "Do you offer a discount for non-profits or academic work?",
    "Yes — 50% off Team. Write to us from your institutional address and we'll set it up.",
  ],
  [
    "What happens to my dashboards if I cancel?",
    "They stay readable for 30 days so you can export what you need. We never delete a connection's credentials silently — you revoke them on your side whenever you like.",
  ],
];

const Cell = ({ value }: { value: string | boolean }) => {
  if (value === true) {
    return <Check className="mx-auto h-4 w-4" style={{ color: "var(--mk-signal)" }} strokeWidth={2.6} />;
  }
  if (value === false) {
    return <Minus className="mx-auto h-4 w-4 text-[color:var(--mk-muted)] opacity-40" />;
  }
  return <span className="mk-mono text-[11.5px] text-[color:var(--mk-muted)]">{value}</span>;
};

/* --- Page ----------------------------------------------------------------- */

export function Pricing() {
  const [yearly, setYearly] = useState(true);

  return (
    <div className="mx-auto max-w-[1180px] px-5 pt-14 sm:px-7 sm:pt-20">
      <header className="mk-reveal">
        <span className="mk-label">Pricing</span>
        <h1 className="mk-display mt-5 max-w-3xl text-[clamp(2.2rem,5.4vw,3.6rem)] text-[color:var(--mk-graphite)]">
          Priced on what you move, not who looks at it.
        </h1>
        <p className="mk-lede mt-6">
          Seats are cheap and rows are the real cost, so that's what we meter. Start on the free
          plan with a live connection and upgrade when a pipeline earns it.
        </p>

        <div
          className="mt-8 inline-flex items-center gap-1 rounded-xl p-1"
          style={{ boxShadow: "inset 0 0 0 1px var(--mk-line)" }}
        >
          {[
            { key: false, label: "Monthly" },
            { key: true, label: "Yearly" },
          ].map((opt) => (
            <button
              key={String(opt.key)}
              onClick={() => setYearly(opt.key)}
              aria-pressed={yearly === opt.key}
              className="rounded-lg px-4 py-2 text-[13px] font-semibold transition"
              style={
                yearly === opt.key
                  ? { background: "var(--mk-graphite)", color: "var(--mk-paper)" }
                  : { color: "var(--mk-muted)" }
              }
            >
              {opt.label}
              {opt.key ? <span className="ml-1.5 opacity-70">−17%</span> : null}
            </button>
          ))}
        </div>
      </header>

      {/* Tiers -------------------------------------------------------------- */}
      <div className="mt-12 grid items-start gap-5 lg:grid-cols-3">
        {TIERS.map((tier) => {
          const price = yearly ? tier.yearly : tier.monthly;
          const dark = !!tier.featured;

          return (
            <div
              key={tier.name}
              className={dark ? "mk-conduit flex flex-col p-6 lg:-my-3 lg:py-9" : "mk-card flex flex-col p-6"}
            >
              <div className="relative flex flex-1 flex-col">
                <div className="flex items-center justify-between">
                  <h2
                    className="text-[17px] font-semibold tracking-[-0.02em]"
                    style={{
                      fontFamily: "var(--mk-display)",
                      color: dark ? "#f1f5f4" : "var(--mk-graphite)",
                    }}
                  >
                    {tier.name}
                  </h2>
                  {dark ? (
                    <span className="mk-mono rounded-full bg-white/10 px-2.5 py-1 text-[9.5px] uppercase tracking-[0.14em] text-emerald-300">
                      Most teams
                    </span>
                  ) : null}
                </div>

                <p
                  className="mt-2 text-[13.5px] leading-relaxed"
                  style={{ color: dark ? "rgba(255,255,255,0.5)" : "var(--mk-muted)" }}
                >
                  {tier.tagline}
                </p>

                <div className="mt-6 flex items-baseline gap-1.5">
                  {price === null ? (
                    <span
                      className="mk-display text-[38px]"
                      style={{ color: dark ? "#fff" : "var(--mk-graphite)" }}
                    >
                      Custom
                    </span>
                  ) : (
                    <>
                      <span
                        className="mk-display text-[38px]"
                        style={{ color: dark ? "#fff" : "var(--mk-graphite)" }}
                      >
                        ${price}
                      </span>
                      <span
                        className="text-[13px]"
                        style={{ color: dark ? "rgba(255,255,255,0.45)" : "var(--mk-muted)" }}
                      >
                        {price === 0 ? "forever" : "/ month"}
                      </span>
                    </>
                  )}
                </div>
                {price !== null && price > 0 && yearly ? (
                  <p
                    className="mk-mono mt-1 text-[11px]"
                    style={{ color: dark ? "rgba(255,255,255,0.4)" : "var(--mk-muted)" }}
                  >
                    billed annually
                  </p>
                ) : null}

                <Link
                  to={tier.to}
                  className={dark ? "mk-cta mk-on-dark mt-6 w-full" : "mk-cta-quiet mt-6 w-full"}
                >
                  {tier.cta}
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>

                <dl
                  className="mt-7 space-y-2 border-t pt-5"
                  style={{ borderColor: dark ? "rgba(255,255,255,0.12)" : "var(--mk-line)" }}
                >
                  {tier.limits.map(([label, value]) => (
                    <div key={label} className="flex items-baseline justify-between gap-3">
                      <dt
                        className="text-[13px]"
                        style={{ color: dark ? "rgba(255,255,255,0.5)" : "var(--mk-muted)" }}
                      >
                        {label}
                      </dt>
                      <dd
                        className="mk-mono text-right text-[12px] font-medium"
                        style={{ color: dark ? "#fff" : "var(--mk-graphite)" }}
                      >
                        {value}
                      </dd>
                    </div>
                  ))}
                </dl>

                <ul
                  className="mt-5 space-y-2.5 border-t pt-5"
                  style={{ borderColor: dark ? "rgba(255,255,255,0.12)" : "var(--mk-line)" }}
                >
                  {tier.includes.map((f) => (
                    <li
                      key={f}
                      className="flex items-start gap-2.5 text-[13.5px]"
                      style={{ color: dark ? "rgba(255,255,255,0.82)" : "var(--mk-graphite)" }}
                    >
                      <Check
                        className="mt-[3px] h-3.5 w-3.5 shrink-0"
                        style={{ color: dark ? "#6ee7b7" : "var(--mk-signal)" }}
                        strokeWidth={2.6}
                      />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          );
        })}
      </div>

      {/* Estimator ---------------------------------------------------------- */}
      <section className="mk-stage mt-24">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <span className="mk-stage-tag" style={{ color: "var(--mk-signal)" }}>
              which plan
            </span>
            <h2 className="mk-display mt-4 text-[clamp(1.7rem,3.4vw,2.4rem)] text-[color:var(--mk-graphite)]">
              Move the sliders. We'll do the arithmetic.
            </h2>
          </div>
          <p className="mk-lede !max-w-sm !text-[14.5px]">
            Three numbers decide your plan. Set them to what you actually run and we'll show which
            limit binds first.
          </p>
        </div>

        <Estimator yearly={yearly} />
      </section>

      {/* Comparison --------------------------------------------------------- */}
      <section className="mk-stage mt-24">
        <span className="mk-label">Compare in full</span>
        <div className="mt-6 overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr>
                <th className="w-[38%] pb-3" />
                {TIERS.map((t) => (
                  <th
                    key={t.name}
                    className="pb-3 text-center text-[13px] font-semibold text-[color:var(--mk-graphite)]"
                  >
                    {t.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {MATRIX.map((group) => (
                <Fragment key={group.group}>
                  <tr>
                    <td colSpan={4} className="border-t pb-2 pt-6" style={{ borderColor: "var(--mk-line)" }}>
                      <span className="mk-label !text-[10px]">{group.group}</span>
                    </td>
                  </tr>
                  {group.rows.map(([label, ...cells]) => (
                    <tr key={label}>
                      <td className="py-2.5 text-[13.5px] text-[color:var(--mk-graphite)]">{label}</td>
                      {cells.map((c, i) => (
                        <td key={i} className="py-2.5 text-center">
                          <Cell value={c} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* FAQ ---------------------------------------------------------------- */}
      <section className="mk-stage mt-24">
        <span className="mk-label">Questions people actually ask</span>
        <div className="mt-7 max-w-3xl">
          {FAQ.map(([q, a]) => (
            <details key={q} className="mk-faq">
              <summary>{q}</summary>
              <p className="mk-faq-body">{a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="mt-24">
        <div className="mk-conduit px-6 py-14 text-center sm:px-12">
          <div className="relative">
            <h2 className="mk-display text-[clamp(1.7rem,3.8vw,2.4rem)] text-white">
              Still sizing it up?
            </h2>
            <p className="mx-auto mt-4 max-w-lg text-[15px] leading-relaxed text-white/55">
              Connect one read-only database on the free plan. You'll know inside an afternoon
              whether the pipeline is worth paying for.
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
