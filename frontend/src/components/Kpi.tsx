import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type Props = {
  value: React.ReactNode;
  label: string;
  color?: string;
  icon?: LucideIcon;
  detail?: string;
  className?: string;
};

export const Kpi = ({ value, label, color = "hsl(var(--primary))", icon: Icon, detail, className }: Props) => (
  <Card className={cn("overflow-hidden", className)}>
    <CardContent className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[0.68rem] font-semibold uppercase text-muted-foreground">{label}</p>
          <p className="mt-2 truncate text-2xl font-bold leading-tight text-foreground dark:text-foreground" style={{ color }}>
            {value}
          </p>
        </div>
        {Icon ? (
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground dark:bg-muted dark:text-muted-foreground">
            <Icon className="h-4 w-4" />
          </div>
        ) : null}
      </div>
      {detail ? (
        <p className="mt-3 truncate text-xs text-muted-foreground">
          {detail}
        </p>
      ) : null}
    </CardContent>
  </Card>
);
