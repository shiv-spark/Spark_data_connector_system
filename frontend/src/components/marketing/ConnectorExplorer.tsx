import { useRef, useState, type KeyboardEvent } from "react";
import { Check } from "lucide-react";

/**
 * Connector explorer.
 *
 * Pick a source and see the two things that actually matter when you connect
 * one: the fields you have to fill in, and what comes back when you do. Drawn
 * glyphs rather than vendor logos, so nothing here misrepresents a trademark.
 */

type Connector = {
  id: string;
  name: string;
  kind: string;
  tint: string;
  glyph: JSX.Element;
  fields: [string, string][];
  found: [string, string][];
  foundLabel: string;
  stat: string;
};

const S = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

/* Drawn marks — a visual family, one per storage shape. */
const Cylinder = (
  <svg viewBox="0 0 24 24" className="h-[17px] w-[17px]" {...S}>
    <ellipse cx="12" cy="6" rx="7" ry="2.8" />
    <path d="M5 6v12c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8V6" />
    <path d="M5 12c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8" />
  </svg>
);

const Dolphin = (
  <svg viewBox="0 0 24 24" className="h-[17px] w-[17px]" {...S}>
    <ellipse cx="12" cy="6.5" rx="7" ry="2.8" />
    <path d="M5 6.5v11c0 1.55 3.13 2.8 7 2.8s7-1.25 7-2.8v-11" />
    <path d="M8.5 11.5h7M8.5 15.5h4" />
  </svg>
);

const Crystal = (
  <svg viewBox="0 0 24 24" className="h-[17px] w-[17px]" {...S}>
    <path d="M12 2.8v18.4M4 7.4l16 9.2M20 7.4 4 16.6" />
    <path d="M12 2.8 9 5m3-2.2L15 5M12 21.2 9 19m3 2.2L15 19" />
  </svg>
);

const Prism = (
  <svg viewBox="0 0 24 24" className="h-[17px] w-[17px]" {...S}>
    <path d="M12 3 3.5 7.6 12 12.2l8.5-4.6L12 3Z" />
    <path d="M3.5 12.2 12 16.8l8.5-4.6M3.5 16.4 12 21l8.5-4.6" />
  </svg>
);

const Bucket = (
  <svg viewBox="0 0 24 24" className="h-[17px] w-[17px]" {...S}>
    <path d="M4.2 6.4h15.6l-1.6 13.1a1.6 1.6 0 0 1-1.6 1.4H7.4a1.6 1.6 0 0 1-1.6-1.4L4.2 6.4Z" />
    <ellipse cx="12" cy="5.4" rx="6.6" ry="2.4" />
  </svg>
);

const Hexes = (
  <svg viewBox="0 0 24 24" className="h-[17px] w-[17px]" {...S}>
    <path d="M12 2.6 16 5v4.8L12 12 8 9.8V5l4-2.4Z" />
    <path d="M6.6 12.4 10 14.4v3.9l-3.4 2-3.4-2v-3.9l3.4-2ZM17.4 12.4l3.4 2v3.9l-3.4 2-3.4-2v-3.9l3.4-2Z" />
  </svg>
);

const Endpoint = (
  <svg viewBox="0 0 24 24" className="h-[17px] w-[17px]" {...S}>
    <circle cx="12" cy="12" r="9" />
    <path d="M3 12h18M12 3c2.4 2.6 3.6 5.6 3.6 9s-1.2 6.4-3.6 9c-2.4-2.6-3.6-5.6-3.6-9S9.6 5.6 12 3Z" />
  </svg>
);

const Sheet = (
  <svg viewBox="0 0 24 24" className="h-[17px] w-[17px]" {...S}>
    <path d="M6 2.8h8.2L19 7.6v13.6H6V2.8Z" />
    <path d="M14 2.8v5h5M9 12.4h7M9 16.2h7" />
  </svg>
);

const CONNECTORS: Connector[] = [
  {
    id: "postgres",
    name: "PostgreSQL",
    kind: "Relational",
    tint: "#22d3ee",
    glyph: Cylinder,
    fields: [
      ["Host", "prod-analytics.internal"],
      ["Port", "5432"],
      ["Database", "commerce"],
      ["User", "dc_readonly"],
      ["SSL mode", "require"],
    ],
    foundLabel: "Tables found",
    found: [
      ["orders", "2.4M rows"],
      ["customers", "184K rows"],
      ["line_items", "9.1M rows"],
      ["refunds", "12K rows"],
    ],
    stat: "184 tables · connected in 1.2s",
  },
  {
    id: "mysql",
    name: "MySQL",
    kind: "Relational",
    tint: "#38bdf8",
    glyph: Dolphin,
    fields: [
      ["Host", "storefront-db.internal"],
      ["Port", "3306"],
      ["Database", "storefront"],
      ["User", "dc_readonly"],
      ["Charset", "utf8mb4"],
    ],
    foundLabel: "Tables found",
    found: [
      ["products", "48K rows"],
      ["inventory", "240K rows"],
      ["suppliers", "1.2K rows"],
      ["price_history", "1.9M rows"],
    ],
    stat: "62 tables · connected in 0.9s",
  },
  {
    id: "snowflake",
    name: "Snowflake",
    kind: "Warehouse",
    tint: "#67e8f9",
    glyph: Crystal,
    fields: [
      ["Account", "xy12345.ap-south-1"],
      ["Warehouse", "ANALYTICS_WH"],
      ["Database", "SALES"],
      ["Role", "DC_READER"],
      ["Auth", "Key pair"],
    ],
    foundLabel: "Objects found",
    found: [
      ["FACT_SALES", "128M rows"],
      ["DIM_CUSTOMER", "890K rows"],
      ["DIM_PRODUCT", "62K rows"],
      ["V_MARGIN_DAILY", "view"],
    ],
    stat: "3 schemas · connected in 2.4s",
  },
  {
    id: "bigquery",
    name: "BigQuery",
    kind: "Warehouse",
    tint: "#2dd4bf",
    glyph: Prism,
    fields: [
      ["Project", "acme-data-prod"],
      ["Dataset", "commerce"],
      ["Service account", "dc-reader@acme…"],
      ["Location", "asia-south1"],
    ],
    foundLabel: "Tables found",
    found: [
      ["events", "1.8B rows"],
      ["sessions", "94M rows"],
      ["users", "12M rows"],
      ["attribution", "partitioned"],
    ],
    stat: "41 tables · connected in 1.8s",
  },
  {
    id: "s3",
    name: "Amazon S3",
    kind: "Object store",
    tint: "#34d399",
    glyph: Bucket,
    fields: [
      ["Bucket", "acme-data-lake"],
      ["Prefix", "events/2026/"],
      ["Region", "ap-south-1"],
      ["Format", "parquet"],
      ["Access", "IAM role"],
    ],
    foundLabel: "Objects matched",
    found: [
      ["events/2026/07/*", "1,204 files"],
      ["Compressed size", "82 GB"],
      ["Schema", "24 columns"],
      ["Partitioning", "by day"],
    ],
    stat: "1,204 objects · scanned in 3.1s",
  },
  {
    id: "mongodb",
    name: "MongoDB",
    kind: "Document",
    tint: "#4ade80",
    glyph: Hexes,
    fields: [
      ["Cluster", "mongodb+srv://acme…"],
      ["Database", "catalog"],
      ["Auth", "SCRAM-SHA-256"],
      ["Read preference", "secondary"],
    ],
    foundLabel: "Collections found",
    found: [
      ["items", "640K docs"],
      ["reviews", "3.1M docs"],
      ["vendors", "8.4K docs"],
      ["Inferred fields", "38 columns"],
    ],
    stat: "12 collections · sampled in 1.6s",
  },
  {
    id: "rest",
    name: "REST API",
    kind: "Endpoint",
    tint: "#a3e635",
    glyph: Endpoint,
    fields: [
      ["Base URL", "https://api.acme.io/v1"],
      ["Auth", "Bearer ••••••••"],
      ["Pagination", "cursor"],
      ["Rate limit", "100 req/s"],
    ],
    foundLabel: "Endpoints mapped",
    found: [
      ["/charges", "42 fields"],
      ["/customers", "28 fields"],
      ["/invoices", "51 fields"],
      ["/subscriptions", "33 fields"],
    ],
    stat: "4 endpoints · probed in 2.0s",
  },
  {
    id: "files",
    name: "CSV & files",
    kind: "Upload",
    tint: "#fbbf24",
    glyph: Sheet,
    fields: [
      ["Source", "Folder watch"],
      ["Formats", "CSV, TSV, Parquet"],
      ["Delimiter", "Auto-detected"],
      ["Header row", "First row"],
    ],
    foundLabel: "Files read",
    found: [
      ["q3_budget.csv", "18K rows"],
      ["headcount.csv", "420 rows"],
      ["targets_2026.csv", "1.2K rows"],
      ["Types inferred", "11 columns"],
    ],
    stat: "3 files · parsed in 0.4s",
  },
];

export function ConnectorExplorer() {
  const [activeId, setActiveId] = useState(CONNECTORS[0].id);
  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const active = CONNECTORS.find((c) => c.id === activeId) ?? CONNECTORS[0];
  const activeIndex = CONNECTORS.findIndex((c) => c.id === activeId);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const forward = e.key === "ArrowRight" || e.key === "ArrowDown";
    const back = e.key === "ArrowLeft" || e.key === "ArrowUp";
    if (!forward && !back) return;
    e.preventDefault();
    const next = (activeIndex + (forward ? 1 : -1) + CONNECTORS.length) % CONNECTORS.length;
    setActiveId(CONNECTORS[next].id);
    tabRefs.current[next]?.focus();
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,360px)_1fr] lg:gap-8">
      {/* Picker ------------------------------------------------------------ */}
      <div
        role="tablist"
        aria-label="Data sources"
        onKeyDown={onKeyDown}
        className="grid h-fit grid-cols-2 gap-2"
      >
        {CONNECTORS.map((c, i) => {
          const selected = c.id === activeId;
          return (
            <button
              key={c.id}
              ref={(el) => { tabRefs.current[i] = el; }}
              role="tab"
              id={`connector-tab-${c.id}`}
              aria-selected={selected}
              aria-controls="connector-panel"
              tabIndex={selected ? 0 : -1}
              onClick={() => setActiveId(c.id)}
              className="mk-tile"
            >
              <span
                className="mk-tile-glyph"
                style={{ color: selected ? c.tint : "var(--mk-muted)" }}
              >
                {c.glyph}
              </span>
              <span className="min-w-0">
                <span className="block truncate text-[13px] font-semibold text-[color:var(--mk-graphite)]">
                  {c.name}
                </span>
                <span className="mk-mono block truncate text-[9.5px] uppercase tracking-[0.12em] text-[color:var(--mk-muted)]">
                  {c.kind}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      {/* Result panel ------------------------------------------------------ */}
      <div
        role="tabpanel"
        id="connector-panel"
        aria-labelledby={`connector-tab-${active.id}`}
        className="mk-conduit p-5 sm:p-6"
      >
        <div key={active.id} className="mk-swap relative">
          <div className="mb-5 flex items-center gap-2.5">
            <span className="mk-tile-glyph !h-7 !w-7" style={{ color: active.tint }}>
              {active.glyph}
            </span>
            <div className="min-w-0">
              <h3 className="mk-station-title !text-[15px]">{active.name}</h3>
              <p className="mk-mono text-[10px] uppercase tracking-[0.14em] text-white/40">
                {active.kind}
              </p>
            </div>
            <span
              className="mk-mono ml-auto inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px]"
              style={{
                color: active.tint,
                background: "rgba(255,255,255,0.06)",
              }}
            >
              <Check className="h-3 w-3" strokeWidth={2.6} />
              connected
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {/* What you fill in */}
            <div className="mk-station">
              <p className="mk-mono mb-3 text-[9.5px] uppercase tracking-[0.16em] text-white/40">
                What you fill in
              </p>
              <dl className="space-y-2">
                {active.fields.map(([label, value]) => (
                  <div key={label} className="flex items-baseline justify-between gap-3">
                    <dt className="shrink-0 text-[11.5px] text-white/45">{label}</dt>
                    <dd className="mk-mono truncate text-[11px] text-white/80">{value}</dd>
                  </div>
                ))}
              </dl>
            </div>

            {/* What comes back */}
            <div className="mk-station">
              <p className="mk-mono mb-3 text-[9.5px] uppercase tracking-[0.16em] text-white/40">
                {active.foundLabel}
              </p>
              <ul className="space-y-2">
                {active.found.map(([name, meta]) => (
                  <li key={name} className="flex items-baseline justify-between gap-3">
                    <span className="mk-mono truncate text-[11px]" style={{ color: active.tint }}>
                      {name}
                    </span>
                    <span className="mk-mono shrink-0 text-[11px] text-white/45">{meta}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="mt-4 flex items-center gap-2.5 border-t border-white/10 pt-4">
            <span className="relative inline-flex h-1.5 w-1.5" aria-hidden="true">
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-70"
                style={{ background: active.tint }}
              />
              <span
                className="relative inline-flex h-1.5 w-1.5 rounded-full"
                style={{ background: active.tint }}
              />
            </span>
            <p className="mk-mono text-[11px] text-white/45">{active.stat}</p>
            <p className="mk-mono ml-auto hidden text-[11px] text-white/30 sm:block">read-only</p>
          </div>
        </div>
      </div>
    </div>
  );
}
