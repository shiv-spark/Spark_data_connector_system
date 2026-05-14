import { CalendarClock, Clock3, Globe2 } from "lucide-react";
import { Input } from "@/components/ui/input";
import { buildCron, describeSchedule, ScheduleState, timezones } from "@/lib/schedule";

type Props = {
  value: ScheduleState;
  onChange: (value: ScheduleState) => void;
  compact?: boolean;
};

const modeLabels = [
  { value: "minutes", label: "Every few minutes" },
  { value: "hourly", label: "Hourly" },
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "manual", label: "Advanced cron" },
] as const;

const weekdays = [
  ["0", "Sunday"],
  ["1", "Monday"],
  ["2", "Tuesday"],
  ["3", "Wednesday"],
  ["4", "Thursday"],
  ["5", "Friday"],
  ["6", "Saturday"],
];

export const SchedulerFields = ({ value, onChange, compact = false }: Props) => {
  const update = (patch: Partial<ScheduleState>) => onChange({ ...value, ...patch });

  return (
    <div className={compact ? "space-y-3" : "rounded-lg border border-slate-200 bg-slate-50 p-4"}>
      {!compact && (
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <CalendarClock className="h-5 w-5 text-slate-700" />
            <div>
              <p className="text-sm font-semibold text-slate-950">Pipeline Scheduler</p>
              <p className="text-xs text-muted-foreground">Readable timing with timezone-aware Airflow cron.</p>
            </div>
          </div>
          <span className="rounded-md bg-white px-2 py-1 font-mono text-xs text-slate-600">{buildCron(value)}</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <label className="space-y-1 text-sm font-medium">
          Frequency
          <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={value.mode} onChange={(event) => update({ mode: event.target.value as ScheduleState["mode"] })}>
            {modeLabels.map((mode) => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
          </select>
        </label>

        {(value.mode === "minutes" || value.mode === "hourly") && (
          <label className="space-y-1 text-sm font-medium">
            Interval
            <div className="relative">
              <Clock3 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-9" type="number" min="1" max="59" value={value.interval} onChange={(event) => update({ interval: event.target.value })} />
            </div>
          </label>
        )}

        {["hourly", "daily", "weekly", "monthly"].includes(value.mode) && (
          <label className="space-y-1 text-sm font-medium">
            Time
            <Input type="time" value={value.time} onChange={(event) => update({ time: event.target.value })} />
          </label>
        )}

        {value.mode === "weekly" && (
          <label className="space-y-1 text-sm font-medium">
            Day
            <select className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm" value={value.dayOfWeek} onChange={(event) => update({ dayOfWeek: event.target.value })}>
              {weekdays.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        )}

        {value.mode === "monthly" && (
          <label className="space-y-1 text-sm font-medium">
            Day of month
            <Input type="number" min="1" max="31" value={value.dayOfMonth} onChange={(event) => update({ dayOfMonth: event.target.value })} />
          </label>
        )}

        {value.mode === "manual" && (
          <label className="space-y-1 text-sm font-medium">
            Cron
            <Input value={value.manualCron} onChange={(event) => update({ manualCron: event.target.value })} />
          </label>
        )}

        <label className="space-y-1 text-sm font-medium">
          Timezone
          <div className="relative">
            <Globe2 className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <select className="h-9 w-full rounded-md border border-input bg-background pl-9 pr-3 text-sm" value={value.timezone} onChange={(event) => update({ timezone: event.target.value })}>
              {timezones.map((timezone) => <option key={timezone} value={timezone}>{timezone}</option>)}
            </select>
          </div>
        </label>
      </div>

      <div className="mt-3 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
        {describeSchedule(value)}. Cron: <span className="font-mono text-slate-900">{buildCron(value)}</span>
      </div>
    </div>
  );
};
