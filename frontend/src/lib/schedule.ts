export type ScheduleMode = "minutes" | "hourly" | "daily" | "weekly" | "monthly" | "manual";

export type ScheduleState = {
  mode: ScheduleMode;
  interval: string;
  time: string;
  dayOfWeek: string;
  dayOfMonth: string;
  timezone: string;
  manualCron: string;
};

export const timezones = [
  "Asia/Kolkata",
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Dubai",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Australia/Sydney",
];

export const defaultSchedule: ScheduleState = {
  mode: "minutes",
  interval: "5",
  time: "09:00",
  dayOfWeek: "1",
  dayOfMonth: "1",
  timezone: "Asia/Kolkata",
  manualCron: "*/5 * * * *",
};

const clamp = (value: string, min: number, max: number, fallback: number) => {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(Math.max(parsed, min), max);
};

const splitTime = (time: string) => {
  const [hour = "9", minute = "0"] = time.split(":");
  return {
    hour: clamp(hour, 0, 23, 9),
    minute: clamp(minute, 0, 59, 0),
  };
};

export const buildCron = (schedule: ScheduleState) => {
  const interval = clamp(schedule.interval, 1, 59, 5);
  const { hour, minute } = splitTime(schedule.time);
  const dayOfWeek = clamp(schedule.dayOfWeek, 0, 6, 1);
  const dayOfMonth = clamp(schedule.dayOfMonth, 1, 31, 1);

  switch (schedule.mode) {
    case "minutes":
      return `*/${interval} * * * *`;
    case "hourly":
      return `${minute} */${interval} * * *`;
    case "daily":
      return `${minute} ${hour} * * *`;
    case "weekly":
      return `${minute} ${hour} * * ${dayOfWeek}`;
    case "monthly":
      return `${minute} ${hour} ${dayOfMonth} * *`;
    case "manual":
      return schedule.manualCron.trim() || defaultSchedule.manualCron;
    default:
      return defaultSchedule.manualCron;
  }
};

const weekdayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export const describeSchedule = (schedule: ScheduleState) => {
  const interval = clamp(schedule.interval, 1, 59, 5);
  const dayOfWeek = weekdayNames[clamp(schedule.dayOfWeek, 0, 6, 1)];
  const dayOfMonth = clamp(schedule.dayOfMonth, 1, 31, 1);

  switch (schedule.mode) {
    case "minutes":
      return `Runs every ${interval} minute${interval === 1 ? "" : "s"} in ${schedule.timezone}`;
    case "hourly":
      return `Runs every ${interval} hour${interval === 1 ? "" : "s"} at minute ${splitTime(schedule.time).minute} in ${schedule.timezone}`;
    case "daily":
      return `Runs daily at ${schedule.time} in ${schedule.timezone}`;
    case "weekly":
      return `Runs every ${dayOfWeek} at ${schedule.time} in ${schedule.timezone}`;
    case "monthly":
      return `Runs monthly on day ${dayOfMonth} at ${schedule.time} in ${schedule.timezone}`;
    case "manual":
      return `Runs on cron ${buildCron(schedule)} in ${schedule.timezone}`;
    default:
      return "";
  }
};

export const scheduleFromCron = (cron?: string, timezone = "Asia/Kolkata"): ScheduleState => {
  if (!cron) return { ...defaultSchedule, timezone };
  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return { ...defaultSchedule, timezone, mode: "manual", manualCron: cron };
  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

  if (minute.startsWith("*/") && hour === "*" && dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    return { ...defaultSchedule, timezone, mode: "minutes", interval: minute.slice(2), manualCron: cron };
  }

  if (/^\d+$/.test(minute) && hour.startsWith("*/") && dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    return { ...defaultSchedule, timezone, mode: "hourly", interval: hour.slice(2), time: `09:${minute.padStart(2, "0")}`, manualCron: cron };
  }

  if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && dayOfMonth === "*" && month === "*" && dayOfWeek === "*") {
    return { ...defaultSchedule, timezone, mode: "daily", time: `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`, manualCron: cron };
  }

  if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && dayOfMonth === "*" && month === "*" && /^\d+$/.test(dayOfWeek)) {
    return { ...defaultSchedule, timezone, mode: "weekly", time: `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`, dayOfWeek, manualCron: cron };
  }

  if (/^\d+$/.test(minute) && /^\d+$/.test(hour) && /^\d+$/.test(dayOfMonth) && month === "*" && dayOfWeek === "*") {
    return { ...defaultSchedule, timezone, mode: "monthly", time: `${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`, dayOfMonth, manualCron: cron };
  }

  return { ...defaultSchedule, timezone, mode: "manual", manualCron: cron };
};
