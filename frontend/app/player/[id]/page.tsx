"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { money2, signedPct, upDown } from "@/lib/format";
import { PriceChart } from "@/components/PriceChart";
import { ValueBreakdown } from "@/components/ValueBreakdown";
import { Card, StatTile } from "@/components/ui";

export default function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const instruments = useQuery({ queryKey: ["instruments"], queryFn: () => api.instruments() });
  const history = useQuery({ queryKey: ["history", id], queryFn: () => api.history(id) });
  const breakdown = useQuery({ queryKey: ["breakdown", id], queryFn: () => api.breakdown(id) });

  const inst = instruments.data?.find((i) => i.id === id);
  const points = history.data ?? [];
  const b = breakdown.data;
  // The v2 shrunk value is authoritative; label it so it never looks inconsistent.
  const current = b?.available ? b.final_value : points.length ? points[points.length - 1].close : inst?.last_price ?? null;

  const change = (n: number) => {
    if (points.length < n + 1) return null;
    const a = points[points.length - 1 - n].close;
    const b = points[points.length - 1].close;
    return a ? b / a - 1 : null;
  };
  const daily = change(1);
  const weekly = change(5);

  return (
    <div className="space-y-8">
      <Link href="/draft" className="text-sm text-ink-soft hover:text-ink">
        ← Draft room
      </Link>

      <section className="flex items-center gap-4">
        {inst?.headshot_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={inst.headshot_url}
            alt={inst?.name ?? ""}
            className="h-20 w-20 rounded-full bg-card object-cover border border-line"
          />
        )}
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">{inst?.name ?? "Player"}</h1>
          <div className="text-ink-soft text-sm">
            {inst?.position ?? "?"} · {inst?.team ?? ""} · {inst?.sport ?? ""}
          </div>
        </div>
      </section>

      <section className="flex flex-wrap items-end gap-8">
        <div>
          <div className="text-xs uppercase tracking-wide text-ink-faint">Current value</div>
          <div className="num text-5xl font-semibold mt-1">
            {current != null ? money2(current) : "—"}
          </div>
          {b?.available && (
            <div className="text-xs text-ink-faint mt-1 num">
              model {b.formula_version} · updated {b.as_of} ·{" "}
              {(b.reliability * 100).toFixed(0)}% confidence
            </div>
          )}
        </div>
        <StatTile label="Daily" value={signedPct(daily)} tone={upDown(daily)} />
        <StatTile label="Weekly (5 games)" value={signedPct(weekly)} tone={upDown(weekly)} />
      </section>

      <Card>
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-semibold">Value history</h2>
          <span className="text-xs text-ink-faint num">
            {points.length} game observations · model{" "}
            {points.find((p) => p.formula_version)?.formula_version ?? "—"}
          </span>
        </div>
        <PriceChart data={points} />
      </Card>

      <ValueBreakdown instrumentId={id} />

      <p className="text-xs text-ink-faint">
        A simulated market. Values are a transparent index derived from real box-score
        performance — <b>performance-linked virtual assets traded with fake money</b>, not real
        securities, ownership, or wagers.
      </p>
    </div>
  );
}
