/**
 * Plan definitions — the single source of truth for both the public pricing
 * page and the console. Changing a limit here changes it in both places, so
 * the two can't drift apart.
 *
 * Note: nothing enforces these limits yet. The console reads them to show you
 * where you stand; the backend has no concept of a plan.
 */

export type PlanId = "developer" | "team" | "enterprise";

export interface PlanLimits {
  /** Infinity means unlimited. */
  connections: number;
  pipelineRuns: number;
  rows: number;
  seats: number;
}

export interface Plan {
  id: PlanId;
  name: string;
  tagline: string;
  /** null means "priced on conversation". */
  monthly: number | null;
  yearly: number | null;
  extraSeat: number | null;
  limits: PlanLimits;
  includes: string[];
}

export const DEFAULT_PLAN: PlanId = "developer";

export const PLAN_ORDER: PlanId[] = ["developer", "team", "enterprise"];

export const PLANS: Record<PlanId, Plan> = {
  developer: {
    id: "developer",
    name: "Developer",
    tagline: "For one person wiring up a first connection.",
    monthly: 0,
    yearly: 0,
    extraSeat: null,
    limits: { connections: 2, pipelineRuns: 500, rows: 5_000_000, seats: 1 },
    includes: [
      "All connector types",
      "Text-to-SQL with query preview",
      "Dashboard studio",
      "7-day run history",
    ],
  },
  team: {
    id: "team",
    name: "Team",
    tagline: "For the group that owns reporting.",
    monthly: 89,
    yearly: 74,
    extraSeat: 9,
    limits: { connections: 25, pipelineRuns: 25_000, rows: 500_000_000, seats: 10 },
    includes: [
      "Everything in Developer",
      "Scheduled pipelines with retries",
      "Shared dashboards and PDF export",
      "Multi-source joins",
      "90-day run history",
      "Email and Slack alerts",
    ],
  },
  enterprise: {
    id: "enterprise",
    name: "Enterprise",
    tagline: "For data that comes with an audit.",
    monthly: null,
    yearly: null,
    extraSeat: null,
    limits: {
      connections: Infinity,
      pipelineRuns: Infinity,
      rows: Infinity,
      seats: Infinity,
    },
    includes: [
      "Everything in Team",
      "Deploy in your own VPC",
      "SSO and SCIM provisioning",
      "Row-level access policies",
      "Audit log export",
      "Named support engineer",
    ],
  },
};

export const getPlan = (id: PlanId | undefined): Plan => PLANS[id ?? DEFAULT_PLAN] ?? PLANS[DEFAULT_PLAN];

/** "Unlimited" for Infinity, otherwise a grouped integer. */
export const formatLimit = (value: number): string =>
  value === Infinity ? "Unlimited" : value.toLocaleString();

/** Compact row counts: 5M, 500M, 2B. */
export const formatRows = (value: number): string => {
  if (value === Infinity) return "Unlimited";
  if (value >= 1_000_000_000) return `${value / 1_000_000_000}B`;
  if (value >= 1_000_000) return `${value / 1_000_000}M`;
  if (value >= 1_000) return `${value / 1_000}K`;
  return String(value);
};

export const nextPlan = (id: PlanId): Plan | null => {
  const i = PLAN_ORDER.indexOf(id);
  return i >= 0 && i < PLAN_ORDER.length - 1 ? PLANS[PLAN_ORDER[i + 1]] : null;
};
