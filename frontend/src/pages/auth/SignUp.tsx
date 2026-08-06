import { useMemo, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  Building2,
  Check,
  Eye,
  EyeOff,
  Loader2,
  Lock,
  Mail,
  TriangleAlert,
  User,
} from "lucide-react";
import { AuthLayout, TextField } from "@/components/auth/AuthLayout";
import { useAuth } from "@/lib/auth";

/** Scores the password and says what's missing, rather than just how it rates. */
function assess(value: string) {
  if (!value) return { score: 0, hint: "" };

  const hasLetter = /[a-zA-Z]/.test(value);
  const hasDigit = /\d/.test(value);
  const hasSymbol = /[^a-zA-Z0-9]/.test(value);

  let score = 0;
  if (value.length >= 8) score += 1;
  if (value.length >= 12) score += 1;
  if (hasLetter && hasDigit) score += 1;
  if (hasSymbol) score += 1;

  let hint: string;
  if (value.length < 8) {
    const short = 8 - value.length;
    hint = `${short} more character${short > 1 ? "s" : ""}`;
  } else if (!hasDigit) {
    hint = "Add a number";
  } else if (!hasLetter) {
    hint = "Add a letter";
  } else if (!hasSymbol) {
    hint = "Good";
  } else {
    hint = "Strong";
  }

  return { score, hint };
}

const PLAN_POINTS = ["2 connections", "5M rows a month", "No card required"];

export function SignUp() {
  const { user, signUp } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false);
  const [capsOn, setCapsOn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const { score, hint } = useMemo(() => assess(password), [password]);

  if (user) return <Navigate to="/app" replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Use at least 8 characters for your password.");
      return;
    }

    setBusy(true);
    try {
      await signUp({ name, email, password, company });
      navigate("/app", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "We couldn't create the account. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const trackCaps = (e: KeyboardEvent<HTMLInputElement>) =>
    setCapsOn(e.getModifierState?.("CapsLock") ?? false);

  return (
    <AuthLayout
      mode="signup"
      title="Create your account"
      subtitle="Connect a read-only database and see your own schema in about five minutes."
      badge={
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <span
            className="mk-mono rounded-full px-2.5 py-1 text-[9.5px] uppercase tracking-[0.14em]"
            style={{
              background: "color-mix(in srgb, var(--mk-signal) 14%, transparent)",
              color: "var(--mk-signal)",
            }}
          >
            Free plan
          </span>
          {PLAN_POINTS.map((p) => (
            <span
              key={p}
              className="inline-flex items-center gap-1.5 text-[12px] text-[color:var(--mk-muted)]"
            >
              <Check className="h-3 w-3" style={{ color: "var(--mk-signal)" }} strokeWidth={3} />
              {p}
            </span>
          ))}
        </div>
      }
      footer={
        <>
          Already have an account?{" "}
          <Link to="/signin" className="font-semibold text-[color:var(--mk-signal)] hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate>
        {error ? (
          <div
            role="alert"
            className="mb-5 flex items-start gap-2.5 rounded-lg p-3 text-[13px] leading-relaxed"
            style={{ background: "color-mix(in srgb, #b45309 12%, transparent)", color: "var(--mk-amber)" }}
          >
            <TriangleAlert className="mt-px h-4 w-4 shrink-0" />
            {error}
          </div>
        ) : null}

        <div className="mk-stagger space-y-4">
          <TextField
            id="name"
            label="Full name"
            icon={User}
            autoComplete="name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Priya Raman"
          />

          <TextField
            id="email"
            label="Work email"
            icon={Mail}
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com"
          />

          <TextField
            id="company"
            label={
              <>
                Company <span className="font-normal text-[color:var(--mk-muted)]">(optional)</span>
              </>
            }
            icon={Building2}
            autoComplete="organization"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Acme Analytics"
          />

          <div>
            <TextField
              id="new-password"
              label="Password"
              icon={Lock}
              type={reveal ? "text" : "password"}
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyUp={trackCaps}
              onBlur={() => setCapsOn(false)}
              placeholder="At least 8 characters"
              trailing={
                <button
                  type="button"
                  onClick={() => setReveal((v) => !v)}
                  className="absolute right-1 top-1/2 grid h-9 w-9 -translate-y-1/2 place-items-center rounded-lg text-[color:var(--mk-muted)] transition hover:text-[color:var(--mk-graphite)]"
                  aria-label={reveal ? "Hide password" : "Show password"}
                >
                  {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              }
            />

            {password ? (
              <div className="mt-2.5 flex items-center gap-3">
                <div className="flex flex-1 gap-1" aria-hidden="true">
                  {[0, 1, 2, 3].map((i) => (
                    <span
                      key={i}
                      className="h-1 flex-1 rounded-full transition-colors duration-200"
                      style={{
                        background:
                          i < score
                            ? score >= 3
                              ? "var(--mk-signal)"
                              : "var(--mk-amber)"
                            : "var(--mk-line)",
                      }}
                    />
                  ))}
                </div>
                <span
                  className="mk-mono shrink-0 text-[10.5px]"
                  style={{ color: score >= 3 ? "var(--mk-signal)" : "var(--mk-muted)" }}
                >
                  {hint}
                </span>
              </div>
            ) : null}

            {capsOn ? (
              <p
                className="mt-2 flex items-center gap-2 text-[12px]"
                style={{ color: "var(--mk-amber)" }}
              >
                <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
                Caps Lock is on.
              </p>
            ) : null}
          </div>
        </div>

        <button type="submit" disabled={busy} className="mk-cta mt-7 w-full disabled:opacity-60">
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Creating account
            </>
          ) : (
            <>
              Create account
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>

        <p className="mt-4 text-[12px] leading-relaxed text-[color:var(--mk-muted)]">
          By creating an account you agree to the terms of service and privacy policy.
        </p>
      </form>
    </AuthLayout>
  );
}
