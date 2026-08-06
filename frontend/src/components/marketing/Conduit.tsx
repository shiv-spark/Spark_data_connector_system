import { Database, GitBranch, LayoutDashboard, Sparkles } from "lucide-react";

/**
 * The conduit — the site's signature element.
 *
 * Four stations wired left to right, matching the order data actually moves
 * through the product. Colour is directional: conduit cyan at the source end,
 * signal emerald at the surface end.
 */

type Station = {
  stage: string;
  icon: typeof Database;
  title: string;
  meta: string;
  tint: string;
  artifact: React.ReactNode;
};

const Bars = () => {
  const heights = [38, 52, 44, 68, 61, 82];
  return (
    <div className="flex h-[42px] items-end gap-[5px]" aria-hidden="true">
      {heights.map((h, i) => (
        <div
          key={i}
          className="flex-1 rounded-[2px]"
          style={{
            height: `${h}%`,
            background: `linear-gradient(180deg, rgba(110,231,183,${0.35 + i * 0.11}), rgba(110,231,183,0.12))`,
          }}
        />
      ))}
    </div>
  );
};

const STATIONS: Station[] = [
  {
    stage: "source",
    icon: Database,
    title: "Your database, in place",
    meta: "184 tables mapped",
    tint: "#22d3ee",
    artifact: (
      <p className="mk-mono text-[11px] leading-relaxed text-cyan-200/75">
        postgres://prod-analytics
        <br />
        <span className="text-white/35">:5432/commerce</span>
      </p>
    ),
  },
  {
    stage: "pipeline",
    icon: GitBranch,
    title: "Scheduled and versioned",
    meta: "Nightly · 4m 12s",
    tint: "#38bdf8",
    artifact: (
      <ul className="mk-mono space-y-[3px] text-[11px] text-sky-200/70">
        <li>extract → stage</li>
        <li>dedupe → join</li>
        <li>load → warehouse</li>
      </ul>
    ),
  },
  {
    stage: "model",
    icon: Sparkles,
    title: "Questions, not queries",
    meta: "Answered in 1.8s",
    tint: "#2dd4bf",
    artifact: (
      <p className="text-[11.5px] italic leading-relaxed text-teal-100/75">
        “Which SKUs lost margin last quarter?”
      </p>
    ),
  },
  {
    stage: "surface",
    icon: LayoutDashboard,
    title: "Dashboards you lay out",
    meta: "Shared with 12 people",
    tint: "#34d399",
    artifact: <Bars />,
  },
];

export function Conduit() {
  return (
    <div className="mk-conduit p-5 sm:p-7">
      <div className="relative">
        <div className="mb-5 flex items-center justify-between">
          <span className="mk-mono text-[10.5px] uppercase tracking-[0.18em] text-white/40">
            commerce · production
          </span>
          <span className="mk-mono inline-flex items-center gap-2 text-[10.5px] text-emerald-300/80">
            <span className="relative inline-flex h-1.5 w-1.5" aria-hidden="true">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
            </span>
            streaming
          </span>
        </div>

        {/* Wire: four nodes at the column centres of the grid below. */}
        <div className="relative mb-5 hidden h-3 md:block" aria-hidden="true">
          <div className="mk-wire absolute left-[12.5%] right-[12.5%] top-1/2 -translate-y-1/2" />
          {STATIONS.map((s, i) => (
            <span
              key={s.stage}
              className="mk-node absolute top-1/2 -translate-x-1/2 -translate-y-1/2"
              data-live={i === 0 ? "true" : "false"}
              style={{ left: `${12.5 + i * 25}%`, color: s.tint }}
            />
          ))}
        </div>

        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
          {STATIONS.map((s, i) => {
            const Icon = s.icon;
            return (
              <div
                key={s.stage}
                className="mk-station mk-reveal"
                style={{ animationDelay: `${180 + i * 110}ms` }}
              >
                <div className="mb-3 flex items-center gap-2">
                  <Icon className="h-3.5 w-3.5" style={{ color: s.tint }} strokeWidth={2.2} />
                  <span
                    className="mk-mono text-[10px] uppercase tracking-[0.16em]"
                    style={{ color: s.tint }}
                  >
                    {s.stage}
                  </span>
                </div>
                <h3 className="mk-station-title mb-2.5">{s.title}</h3>
                <div className="mb-3 min-h-[46px]">{s.artifact}</div>
                <p className="mk-mono text-[10.5px] text-white/40">{s.meta}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
