import { Badge } from "@/components/ui/badge";

const VARIANTS: Record<string, "success" | "warning" | "danger" | "info" | "muted"> = {
  active:   "success",
  paused:   "warning",
  failed:   "danger",
  success:  "success",
  running:  "info",
  skipped:  "warning",
  healthy:  "success",
  degraded: "danger",
  warning:  "warning",
  created:  "info",
};

export const StatusBadge = ({ status }: { status: string | null | undefined }) => {
  const s = String(status ?? "unknown").toLowerCase().trim();
  return <Badge variant={VARIANTS[s] ?? "muted"}>{String(status ?? "UNKNOWN").toUpperCase()}</Badge>;
};