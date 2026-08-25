export const money = (n: number, ccy = "CAD") =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: ccy,
    maximumFractionDigits: 0,
  }).format(n);

export const money2 = (n: number, ccy = "CAD") =>
  new Intl.NumberFormat("en-CA", {
    style: "currency",
    currency: ccy,
    maximumFractionDigits: 2,
  }).format(n);

export const pct = (n: number | null | undefined, digits = 2) =>
  n === null || n === undefined ? "—" : `${(n * 100).toFixed(digits)}%`;

export const signedPct = (n: number | null | undefined, digits = 2) => {
  if (n === null || n === undefined) return "—";
  const s = (n * 100).toFixed(digits);
  return `${n >= 0 ? "+" : ""}${s}%`;
};

export const num = (n: number | null | undefined, digits = 2) =>
  n === null || n === undefined ? "—" : n.toFixed(digits);

export const upDown = (n: number | null | undefined) =>
  n === null || n === undefined ? "text-ink-soft" : n >= 0 ? "text-up" : "text-down";
