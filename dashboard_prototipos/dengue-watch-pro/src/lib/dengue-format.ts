const MONTH_LABELS = [
  "ene.",
  "feb.",
  "mar.",
  "abr.",
  "may.",
  "jun.",
  "jul.",
  "ago.",
  "sep.",
  "oct.",
  "nov.",
  "dic.",
];

export const formatPercent = (value: number, decimals = 0) => `${(value * 100).toFixed(decimals)}%`;

export const formatMonth = (month: string) => {
  const [y = "", m = ""] = month.split("-");
  return `${MONTH_LABELS[Number(m) - 1] ?? ""} ${y}`.trim();
};

export const formatShortMonth = (month: string): string => {
  const m = Number(month.split("-")[1]);
  return "EFMAMJJASOND"[m - 1] ?? "";
};

export const formatDateTime = (iso: string) => {
  const d = new Date(iso);
  const date = `${String(d.getDate()).padStart(2, "0")} ${MONTH_LABELS[d.getMonth()] ?? ""} ${d.getFullYear()}`;
  const time = d.toLocaleTimeString("es-CO", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${date} ${time}`;
};

export const labelText = (label: 0 | 1) => (label === 1 ? "EXCESO" : "NO EXCESO");
