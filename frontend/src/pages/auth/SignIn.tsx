import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ArrowRight, Eye, EyeOff, Loader2, Lock, Mail, TriangleAlert } from "lucide-react";
import { AuthLayout, TextField } from "@/components/auth/AuthLayout";
import { useAuth } from "@/lib/auth";

export function SignIn() {
  const { user, signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from ?? "/app";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [reveal, setReveal] = useState(false);
  const [capsOn, setCapsOn] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={from} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await signIn(email, password);
      navigate(from, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign in failed. Try again.");
    } finally {
      setBusy(false);
    }
  };

  const trackCaps = (e: KeyboardEvent<HTMLInputElement>) =>
    setCapsOn(e.getModifierState?.("CapsLock") ?? false);

  return (
    <AuthLayout
      mode="signin"
      title="Welcome back"
      subtitle="Sign in to reach your connections, pipelines, and boards."
      footer={
        <>
          No account yet?{" "}
          <Link to="/signup" className="font-semibold text-[color:var(--mk-signal)] hover:underline">
            Create one free
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
            id="password"
            label="Password"
            icon={Lock}
            type={reveal ? "text" : "password"}
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyUp={trackCaps}
            onBlur={() => setCapsOn(false)}
            placeholder="••••••••"
            aside={
              <Link
                to="/signin"
                className="mb-1.5 text-[12.5px] text-[color:var(--mk-muted)] hover:text-[color:var(--mk-graphite)]"
              >
                Forgot it?
              </Link>
            }
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
        </div>

        {capsOn ? (
          <p
            className="mt-2.5 flex items-center gap-2 text-[12px]"
            style={{ color: "var(--mk-amber)" }}
          >
            <TriangleAlert className="h-3.5 w-3.5 shrink-0" />
            Caps Lock is on.
          </p>
        ) : null}

        <button type="submit" disabled={busy} className="mk-cta mt-7 w-full disabled:opacity-60">
          {busy ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Signing in
            </>
          ) : (
            <>
              Sign in
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </form>
    </AuthLayout>
  );
}
