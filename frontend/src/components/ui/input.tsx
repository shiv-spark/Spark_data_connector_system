import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      ref={ref}
      type={type}
      className={cn(
        "flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 py-1 text-[13px] text-slate-900",
        "shadow-[inset_0_1px_0_rgba(15,23,42,0.02),0_1px_0_rgba(15,23,42,0.02)]",
        "placeholder:text-slate-400 transition-all",
        "hover:border-slate-300",
        "focus-visible:outline-none focus-visible:border-emerald-400 focus-visible:ring-4 focus-visible:ring-emerald-500/15",
        "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-slate-50",
        "file:border-0 file:bg-transparent file:text-sm file:font-medium",
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = "Input";