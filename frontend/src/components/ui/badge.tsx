import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold tracking-tight ring-1 ring-inset transition-colors",
  {
    variants: {
      variant: {
        default:     "bg-emerald-50 text-emerald-700 ring-emerald-200",
        secondary:   "bg-slate-50 text-slate-700 ring-slate-200",
        destructive: "bg-rose-50 text-rose-700 ring-rose-200",
        outline:     "bg-white text-slate-700 ring-slate-200",
        success:     "bg-emerald-50 text-emerald-700 ring-emerald-200",
        warning:     "bg-amber-50 text-amber-800 ring-amber-200",
        danger:      "bg-rose-50 text-rose-700 ring-rose-200",
        info:        "bg-sky-50 text-sky-700 ring-sky-200",
        muted:       "bg-slate-50 text-slate-600 ring-slate-200",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = ({ className, variant, ...props }: BadgeProps) => (
  <span className={cn(badgeVariants({ variant }), className)} {...props} />
);

export { badgeVariants };
