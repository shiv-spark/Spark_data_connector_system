import type { PlanId } from "@/lib/plans";

export interface User {
  id: string;
  name: string;
  email: string;
  role: string;
  plan: PlanId;
  company?: string;
  avatar?: string;
}

export const getUserInitials = (name: string): string => {
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
};