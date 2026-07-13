import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-[13px] text-foreground",
        "shadow-[inset_0_1px_0_rgba(15,23,42,0.02),0_1px_0_rgba(15,23,42,0.02)]",
        "dark:shadow-[inset_0_1px_0_rgba(0,0,0,0.2),0_1px_0_rgba(0,0,0,0.1)]",
        "placeholder:text-muted-foreground transition-all",
        "hover:border-slate-300 dark:hover:border-slate-600",
        "focus-visible:outline-none focus-visible:border-emerald-400 focus-visible:ring-4 focus-visible:ring-emerald-500/15",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-slate-50 dark:disabled:bg-slate-800",
        "file:border-0 file:bg-transparent file:text-sm file:font-medium",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";