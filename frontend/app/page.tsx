"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { money, money2, signedPct, upDown } from "@/lib/format";
import { EquityChart } from "@/components/EquityChart";
import { Card, Bar } from "@/components/ui";
import { DailyPack } from "@/components/DailyPack";
import type { ReturnPoint } from "@/lib/types";

const RANGES = ["1W", "1M", "3M", "6M", "YTD", "ALL"] as const;
type Range = (typeof RANGES)[number];

/** Trim a return series to the selected lookback window. */
function windowed(series: ReturnPoint[], range: Range): ReturnPoint[] {
  if (range === "ALL" || series.length === 0) return series;
  const last = new Date(series[series.length - 1].snapshot_date);
  const days =
    range === "1W" ? 7 : range === "1M" ? 30 : range === "3M" ? 90 : range === "6M" ? 180 : NaN;
  const cutoff =
    range === "YTD" ? +new Date(last.getFullYear(), 0, 1) : +last - days * 86_400_000;
  const w = series.filter((p) => +new Date(p.snapshot_date) >= cutoff);
  return w.length >= 2 ? w : series; // never blank the chart on a sparse window
}

export default function Home() {
  const [hasToken, setHasToken] = useState(false);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setHasToken(!!getToken());
    setReady(true);
  }, []);
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.me(), enabled: hasToken, retry: false });
  const pid = me.data?.portfolio_id ?? null;

  const valuation = useQuery({
    queryKey: ["valuation", pid],
    queryFn: () => api.valuation(pid!),
    enabled: !!pid,
  });
  const returns = useQuery({
    queryKey: ["returns", pid],
    queryFn: () => api.returns(pid!),
    enabled: !!pid,
  });

  const [range, setRange] = useState<Range>("ALL");
  const [mode, setMode] = useState<"Value" | "Returns">("Value");

  const v = valuation.data;
  const series = returns.data ?? [];
  const totalReturn = series.length ? series[series.length - 1].cumulative_return : null;
  const dayReturn = series.length ? series[series.length - 1].daily_return : null;

  if (!ready) return null;

  if (!hasToken) {
    return (
      <div className="max-w-xl mx-auto text-center mt-10 space-y-5">
        <h1 className="text-4xl font-semibold tracking-tight">
          Draft a team. Trade the market. Climb the divisions.
        </h1>
        <p className="text-ink-soft">
          A simulated multi-sport market — trade performance-linked NBA & NHL player assets and
          index funds, then compete gameweek to gameweek for XP and promotion.
        </p>
        <div className="flex items-center justify-center gap-3">
          <Link href="/login" className="rounded-xl bg-ink text-cream px-5 py-3 font-medium hover:opacity-90">
            Create your team
          </Link>
          <Link href="/markets" className="rounded-xl border border-line px-5 py-3 font-medium hover:border-ink">
            Browse markets
          </Link>
        </div>
      </div>
    );
  }

  const hour = new Date().getHours();
  const partOfDay = hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";
  const name = me.data?.display_name || me.data?.username || "";

  const u = me.data;
  const xpPct = u && u.xp_per_level ? u.xp_into_level / u.xp_per_level : 0;

  return (
    <div className="space-y-6">
      {/* Full-width greeting bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Good {partOfDay}, {name}</h1>
          <div className="mt-1 flex items-center gap-2 text-sm text-ink-soft">
            <span>{u?.username}&apos;s team</span>
            <span className="rounded-full bg-accent/20 text-accent-deep px-2 py-0.5 text-xs">{u?.division}</span>
          </div>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Link href="/markets" className="rounded-full border border-line px-4 py-2 font-medium hover:border-ink transition-colors">Trade</Link>
          <Link href="/packs" className="rounded-full bg-ink text-cream px-4 py-2 font-medium hover:opacity-90">Open a pack</Link>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left: value + chart */}
        <div className="space-y-6 lg:col-span-2">
          <DailyPack />

          <section>
            <div className="text-xs uppercase tracking-wide text-ink-faint">Portfolio value</div>
            <div className="num text-5xl font-semibold mt-1 sm:text-6xl">{v ? money2(v.equity) : "—"}</div>
            <div className="mt-1 flex items-center gap-3 text-sm">
              <span className={`num ${upDown(dayReturn)}`}>{signedPct(dayReturn)} today</span>
              <span className="text-ink-faint">·</span>
              <span className={`num ${upDown(totalReturn)}`}>{signedPct(totalReturn)} all time</span>
            </div>
          </section>

          {series.length >= 2 ? (
            <Card className="p-4 sm:p-5">
              <EquityChart data={windowed(series, range)} field={mode === "Value" ? "equity" : "cumulative_return"} />
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-1">
                  {RANGES.map((r) => (
                    <button
                      key={r}
                      onClick={() => setRange(r)}
                      className={`num rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
                        range === r ? "bg-elevated text-ink" : "text-ink-faint hover:text-ink"
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
                <div className="flex items-center rounded-lg border border-line p-0.5 text-xs">
                  {(["Value", "Returns"] as const).map((m) => (
                    <button
                      key={m}
                      onClick={() => setMode(m)}
                      className={`rounded-md px-3 py-1 font-medium transition-colors ${
                        mode === m ? "bg-ink text-cream" : "text-ink-faint hover:text-ink"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>
            </Card>
          ) : (
            <Card className="text-sm text-ink-faint">Your performance curve appears once you have a couple of days of history.</Card>
          )}
        </div>

        {/* Right: standing + holdings rail */}
        <div className="space-y-6">
          {u && (
            <Card className="p-5">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wide text-ink-faint">Your standing</span>
                <span className="rounded-full bg-accent/20 text-accent-deep px-2 py-0.5 text-xs">{u.division}</span>
              </div>
              <div className="mt-3 flex items-baseline justify-between">
                <span className="num text-2xl font-semibold">Level {u.level}</span>
                <span className="num text-sm text-ink-soft">{u.division_points} pts</span>
              </div>
              <div className="mt-3">
                <Bar value={xpPct} />
                <div className="mt-1 flex justify-between text-xs text-ink-faint num">
                  <span>{u.xp_into_level} / {u.xp_per_level} XP</span>
                  <Link href="/rivals" className="text-accent-deep hover:underline">Rivals →</Link>
                </div>
              </div>
            </Card>
          )}

          <div className="rounded-2xl border border-line bg-card overflow-hidden">
            <div className="flex items-center justify-between border-b border-line px-4 py-3">
              <h2 className="font-semibold">Holdings</h2>
              <span className="num text-xs text-ink-faint">{v ? v.holdings.length : 0} positions</span>
            </div>
            {v && v.holdings.length > 0 ? (
              <div className="max-h-[560px] divide-y divide-line overflow-y-auto">
                {v.holdings.map((h) => (
                  <Link
                    key={h.instrument_id}
                    href={`/player/${h.instrument_id}`}
                    className="flex items-center gap-3 px-4 py-3 hover:bg-elevated/50"
                  >
                    <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-elevated text-sm font-semibold text-ink-soft">
                      {h.name.slice(0, 1)}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium">{h.name}</div>
                      <div className="num text-xs text-ink-faint">{h.quantity} @ {money2(h.price)}</div>
                    </div>
                    <div className="text-right">
                      <div className="num text-sm font-medium">{money(h.market_value)}</div>
                      <div className="num text-xs text-ink-faint">{(h.weight * 100).toFixed(0)}%</div>
                    </div>
                  </Link>
                ))}
                {v.cash > 0 && (
                  <div className="flex items-center justify-between px-4 py-3 text-sm">
                    <span className="text-ink-soft">Cash</span>
                    <span className="num font-medium">{money(v.cash)}</span>
                  </div>
                )}
              </div>
            ) : (
              <div className="px-4 py-6 text-sm text-ink-soft">
                No holdings yet.{" "}
                <Link href="/markets" className="text-accent-deep underline underline-offset-4">Browse the market</Link>{" "}
                or{" "}
                <Link href="/packs" className="text-accent-deep underline underline-offset-4">open a pack</Link>.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
