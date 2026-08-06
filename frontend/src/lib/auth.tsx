import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { User } from "@/lib/user";
import { DEFAULT_PLAN } from "@/lib/plans";

/**
 * DEMO AUTHENTICATION — browser-only, no server.
 *
 * The backend exposes no auth endpoints today, so accounts and sessions live in
 * localStorage. This gates the console UI and nothing else: it is not a security
 * boundary, and credentials stored here are readable by anyone with the device.
 * Replace `signIn`/`signUp`/`signOut` with real API calls (and move the session
 * to an httpOnly cookie) before this goes in front of real users.
 */

const SESSION_KEY = "dc.session";
const ACCOUNTS_KEY = "dc.accounts";

interface StoredAccount extends User {
  password: string;
  company?: string;
}

export interface SignUpInput {
  name: string;
  email: string;
  password: string;
  company?: string;
}

interface AuthContextValue {
  user: User | null;
  ready: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (input: SignUpInput) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const readJson = <T,>(key: string, fallback: T): T => {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
};

const writeJson = (key: string, value: unknown) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable (private mode, quota) — session stays in memory */
  }
};

const normalizeEmail = (email: string) => email.trim().toLowerCase();

const publicUser = ({ password: _password, ...rest }: StoredAccount): User => ({
  ...rest,
  // Accounts created before plans existed have no plan field.
  plan: rest.plan ?? DEFAULT_PLAN,
});

/** Simulates network latency so loading states are exercised in the UI. */
const settle = () => new Promise((resolve) => setTimeout(resolve, 550));

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = readJson<User | null>(SESSION_KEY, null);
    setUser(stored ? { ...stored, plan: stored.plan ?? DEFAULT_PLAN } : null);
    setReady(true);
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    await settle();
    const accounts = readJson<StoredAccount[]>(ACCOUNTS_KEY, []);
    const account = accounts.find((a) => a.email === normalizeEmail(email));

    if (!account || account.password !== password) {
      throw new Error("That email and password don't match an account.");
    }

    const session = publicUser(account);
    writeJson(SESSION_KEY, session);
    setUser(session);
  }, []);

  const signUp = useCallback(async ({ name, email, password, company }: SignUpInput) => {
    await settle();
    const accounts = readJson<StoredAccount[]>(ACCOUNTS_KEY, []);
    const normalized = normalizeEmail(email);

    if (accounts.some((a) => a.email === normalized)) {
      throw new Error("An account already uses that email. Sign in instead.");
    }

    const account: StoredAccount = {
      id: crypto.randomUUID(),
      name: name.trim(),
      email: normalized,
      role: "Owner",
      plan: DEFAULT_PLAN,
      company: company?.trim() || undefined,
      password,
    };

    writeJson(ACCOUNTS_KEY, [...accounts, account]);
    const session = publicUser(account);
    writeJson(SESSION_KEY, session);
    setUser(session);
  }, []);

  const signOut = useCallback(() => {
    localStorage.removeItem(SESSION_KEY);
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, ready, signIn, signUp, signOut }),
    [user, ready, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used inside an AuthProvider");
  }
  return context;
}
