import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { ArrowRight, Menu, Moon, Sun, X } from "lucide-react";
import { useTheme } from "@/components/ThemeProvider";
import { useAuth } from "@/lib/auth";
import { Wordmark } from "@/components/marketing/Wordmark";

const NAV = [
  { to: "/platform", label: "Platform" },
  { to: "/pricing", label: "Pricing" },
  { to: "/about", label: "About" },
];

const FOOTER_COLUMNS = [
  {
    heading: "Platform",
    links: [
      { to: "/platform", label: "How it works" },
      { to: "/platform#connectors", label: "Connectors" },
      { to: "/platform#ai", label: "AI on your data" },
      { to: "/pricing", label: "Pricing" },
    ],
  },
  {
    heading: "Company",
    links: [
      { to: "/about", label: "About us" },
      { to: "/about#principles", label: "How we build" },
      { to: "/about#contact", label: "Contact" },
    ],
  },
  {
    heading: "Get started",
    links: [
      { to: "/signup", label: "Create an account" },
      { to: "/signin", label: "Sign in" },
      { to: "/app", label: "Open the console" },
    ],
  },
];

function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";

  return (
    <button
      onClick={() => setTheme(theme === "system" ? (isDark ? "light" : "dark") : isDark ? "light" : "dark")}
      className="grid h-9 w-9 place-items-center rounded-lg text-[color:var(--mk-muted)] transition hover:bg-black/5 hover:text-[color:var(--mk-graphite)] dark:hover:bg-white/10"
      aria-label={isDark ? "Switch to light theme" : "Switch to dark theme"}
    >
      {isDark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
    </button>
  );
}

function SiteHeader() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const { user } = useAuth();
  const { pathname } = useLocation();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => setMenuOpen(false), [pathname]);

  return (
    <header
      className="sticky top-0 z-50 transition-all duration-200"
      style={{
        background: scrolled ? "color-mix(in srgb, var(--mk-paper) 88%, transparent)" : "transparent",
        backdropFilter: scrolled ? "blur(12px)" : "none",
        borderBottom: `1px solid ${scrolled ? "var(--mk-line)" : "transparent"}`,
      }}
    >
      <div className="mx-auto flex h-[68px] max-w-[1180px] items-center gap-8 px-5 sm:px-7">
        <Wordmark />

        <nav className="hidden items-center gap-7 md:flex">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className="mk-navlink">
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <ThemeToggle />
          {user ? (
            <Link
              to="/app"
              className="mk-cta !h-9 !px-4 !text-[13.5px]"
            >
              Open console
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          ) : (
            <>
              <Link to="/signin" className="mk-navlink hidden px-3 sm:block">
                Sign in
              </Link>
              <Link to="/signup" className="mk-cta !h-9 !px-4 !text-[13.5px]">
                Start free
              </Link>
            </>
          )}
          <button
            onClick={() => setMenuOpen((v) => !v)}
            className="grid h-9 w-9 place-items-center rounded-lg text-[color:var(--mk-graphite)] md:hidden"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </div>

      {menuOpen ? (
        <div
          className="border-t px-5 py-3 md:hidden"
          style={{ borderColor: "var(--mk-line)", background: "var(--mk-paper)" }}
        >
          {NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="block py-2.5 text-[15px] font-medium text-[color:var(--mk-graphite)]"
            >
              {item.label}
            </Link>
          ))}
          <Link to="/signin" className="block py-2.5 text-[15px] font-medium text-[color:var(--mk-muted)]">
            Sign in
          </Link>
        </div>
      ) : null}
    </header>
  );
}

function SiteFooter() {
  return (
    <footer className="mt-24 border-t" style={{ borderColor: "var(--mk-line)" }}>
      <div className="mx-auto max-w-[1180px] px-5 py-14 sm:px-7">
        <div className="grid gap-10 md:grid-cols-[1.4fr_repeat(3,1fr)]">
          <div>
            <Wordmark />
            <p className="mk-lede mt-4 !text-[13.5px] !max-w-[16rem]">
              A control plane for the databases you already run.
            </p>
          </div>

          {FOOTER_COLUMNS.map((col) => (
            <div key={col.heading}>
              <h4 className="mk-label mb-4 !text-[10px]">{col.heading}</h4>
              <ul className="space-y-2.5">
                {col.links.map((link) => (
                  <li key={link.to + link.label}>
                    <Link
                      to={link.to}
                      className="text-[13.5px] text-[color:var(--mk-muted)] transition hover:text-[color:var(--mk-graphite)]"
                    >
                      {link.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div
          className="mt-12 flex flex-col gap-3 border-t pt-6 sm:flex-row sm:items-center sm:justify-between"
          style={{ borderColor: "var(--mk-line)" }}
        >
          <p className="mk-mono text-[11px] text-[color:var(--mk-muted)]">
            © {new Date().getFullYear()} SparkBrains
          </p>
          <p className="mk-mono text-[11px] text-[color:var(--mk-muted)]">
            Postgres · MySQL · Snowflake · S3 · REST
          </p>
        </div>
      </div>
    </footer>
  );
}

export function MarketingLayout() {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (!hash) {
      window.scrollTo(0, 0);
      return;
    }
    // Let the incoming page mount before looking for the anchor.
    const id = requestAnimationFrame(() => {
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    return () => cancelAnimationFrame(id);
  }, [pathname, hash]);

  return (
    <div className="mk-shell flex min-h-full flex-col">
      <SiteHeader />
      <main className="flex-1">
        <Outlet />
      </main>
      <SiteFooter />
    </div>
  );
}
