import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";

/** Product wordmark. The glyph is the conduit in miniature: source dot, wire, output dot. */
export function Wordmark({ className, to = "/" }: { className?: string; to?: string }) {
  return (
    <Link to={to} className={cn("group inline-flex items-center gap-2.5", className)}>
      <span className="relative grid h-8 w-8 place-items-center rounded-[9px] bg-gradient-to-br from-[#0e7490] to-[#059669] shadow-[inset_0_1px_0_rgba(255,255,255,0.28)]">
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden="true">
          <circle cx="5.5" cy="12" r="2.4" fill="#fff" fillOpacity="0.95" />
          <path d="M8.6 12h6.2" stroke="#fff" strokeOpacity="0.65" strokeWidth="1.6" strokeLinecap="round" />
          <path d="M15 8.4 18.8 12 15 15.6" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      <span className="leading-none">
        <span
          className="block text-[15px] font-semibold tracking-[-0.02em]"
          style={{ fontFamily: "var(--mk-display)", color: "var(--mk-graphite)" }}
        >
          Data Connector
        </span>
        <span className="mk-mono mt-[3px] block text-[9.5px] uppercase tracking-[0.18em] text-[color:var(--mk-muted)]">
          by SparkBrains
        </span>
      </span>
    </Link>
  );
}
