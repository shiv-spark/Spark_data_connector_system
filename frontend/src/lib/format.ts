export const fdt = (v: string | number | null | undefined): string => {
  if (!v) return "-";
  const d = new Date(v);
  if (isNaN(d.getTime())) return String(v).slice(0, 16);
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
};

export const fmtInt = (n: number | null | undefined): string =>
  n == null ? "-" : Number(n).toLocaleString("en-IN");
