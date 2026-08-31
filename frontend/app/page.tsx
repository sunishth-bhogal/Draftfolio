"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { money, money2, signedPct, upDown } from "@/lib/format";
import { EquityChart } from "@/components/EquityChart";
import { Card, Bar } from "@/components/ui";

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

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="text-sm text-ink-soft">
          {me.data?.username}&apos;s team ·{" "}
          <span className="rounded-full bg-accent/30 text-accent-deep px-2 py-0.5 text-xs">
            {me.data?.division}
          </span>
        </div>
        <div className="flex items-center gap-4 text-sm">
          <Link href="/markets" className="text-ink-soft hover:text-ink">Browse markets →</Link>
          <Link href="/rivals" className="text-ink-soft hover:text-ink">Rivals →</Link>
        </div>
      </div>

      {/* Portfolio value — front and centre */}
      <section>
        <div className="text-xs uppercase tracking-wide text-ink-faint">Portfolio value</div>
        <div className="num text-6xl font-semibold mt-1">{v ? money2(v.equity) : "—"}</div>
        <div className="mt-1 flex items-center gap-3 text-sm">
          <span className={`num ${upDown(dayReturn)}`}>{signedPct(dayReturn)} today</span>
          <span className="text-ink-faint">·</span>
          <span className={`num ${upDown(totalReturn)}`}>{signedPct(totalReturn)} all time</span>
        </div>
      </section>

      {series.length >= 2 && (
        <Card>
          <EquityChart data={series} />
        </Card>
      )}

      {/* Holdings — your positions right there */}
      <section>
        <h2 className="font-semibold mb-3">Holdings</h2>
        {v && v.holdings.length > 0 ? (
          <div className="rounded-2xl border border-line bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-ink-faint border-b border-line">
                  <th className="px-5 py-3 font-medium">Asset</th>
                  <th className="px-5 py-3 font-medium text-right">Shares</th>
                  <th className="px-5 py-3 font-medium text-right">Price</th>
                  <th className="px-5 py-3 font-medium text-right">Value</th>
                  <th className="px-5 py-3 font-medium w-40">Weight</th>
                </tr>
              </thead>
              <tbody>
                {v.holdings.map((h) => (
                  <tr key={h.instrument_id} className="border-b border-line last:border-0 hover:bg-cream/60">
                    <td className="px-5 py-4">
                      <Link href={`/player/${h.instrument_id}`} className="font-medium hover:text-accent-deep">
                        {h.name}
                      </Link>
                    </td>
                    <td className="px-5 py-4 text-right num text-ink-soft">{h.quantity}</td>
                    <td className="px-5 py-4 text-right num text-ink-soft">{money2(h.price)}</td>
                    <td className="px-5 py-4 text-right num font-medium">{money(h.market_value)}</td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <Bar value={h.weight} />
                        <span className="num text-xs text-ink-soft w-9 text-right">
                          {(h.weight * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                  </tr>
                ))}
                {v.cash > 0 && (
                  <tr className="hover:bg-cream/60">
                    <td className="px-5 py-4 text-ink-soft">Cash</td>
                    <td />
                    <td />
                    <td className="px-5 py-4 text-right num text-ink-soft">{money(v.cash)}</td>
                    <td />
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <Card>
            <p className="text-ink-soft text-sm">
              No holdings yet.{" "}
              <Link href="/markets" className="text-accent-deep underline underline-offset-4">
                Browse the market
              </Link>{" "}
              or{" "}
              <Link href="/draft" className="text-accent-deep underline underline-offset-4">
                draft a portfolio
              </Link>
              .
            </p>
          </Card>
        )}
      </section>
    </div>
  );
}
