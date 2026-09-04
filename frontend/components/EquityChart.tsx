"use client";

import type { ReturnPoint } from "@/lib/types";

/** Minimal, dependency-free area+line chart for an equity / return curve. */
export function EquityChart({
  data,
  field = "equity",
}: {
  data: ReturnPoint[];
  field?: "equity" | "cumulative_return";
}) {
  // Pull the chosen series; cumulative_return can be null at the first point.
  const points = data
    .map((d) => ({ date: d.snapshot_date, v: field === "equity" ? d.equity : d.cumulative_return }))
    .filter((p): p is { date: string; v: number } => p.v != null);

  if (points.length < 2) {
    return <div className="text-sm text-ink-faint">Not enough history to chart yet.</div>;
  }

  const W = 720;
  const H = 220;
  const P = 8;
  const values = points.map((p) => p.v);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  const x = (i: number) => P + (i / (points.length - 1)) * (W - 2 * P);
  const y = (v: number) => P + (1 - (v - min) / span) * (H - 2 * P);

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.v).toFixed(1)}`).join(" ");
  const area = `${line} L ${x(points.length - 1).toFixed(1)} ${H - P} L ${x(0).toFixed(1)} ${H - P} Z`;
  const up = points[points.length - 1].v >= points[0].v;
  const stroke = up ? "var(--color-up)" : "var(--color-down)";

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto" role="img" aria-label="Performance curve">
      <defs>
        <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.18" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#eq)" />
      <path d={line} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={x(points.length - 1)} cy={y(points[points.length - 1].v)} r="3.5" fill={stroke} />
    </svg>
  );
}
