"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { money, money2, signedPct, upDown } from "@/lib/format";
import { EquityChart } from "@/components/EquityChart";
import { Card, Bar } from "@/components/ui";

export default function Home() {
  const portfolios = useQuery({ queryKey: ["portfolios"], queryFn: () => api.portfolios() });
  const [pid, setPid] = useState<string | null>(null);

  // Default to the saved / first portfolio (Robinhood-style: your holdings on open).
  useEffect(() => {
    if (pid || !portfolios.data?.length) return;
    const saved = typeof window !== "undefined" ? localStorage.getItem("pid") : null;
    const exists = saved && portfolios.data.some((p) => p.id === saved);
    setPid(exists ? saved! : portfolios.data[0].id);
  }, [portfolios.data, pid]);

  function choose(id: string) {
    setPid(id);
    if (typeof window !== "undefined") localStorage.setItem("pid", id);
  }

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

  return (
    <div className="space-y-8">
      {/* Portfolio switcher (stands in for accounts until auth) */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <select
          value={pid ?? ""}
          onChange={(e) => choose(e.target.value)}
          className="rounded-xl border border-line bg-card px-4 py-2 text-sm font-medium focus:border-ink outline-none"
        >
          {portfolios.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <div className="flex items-center gap-4 text-sm">
          <Link href="/markets" className="text-ink-soft hover:text-ink">
            Browse markets →
          </Link>
          <Link
            href="/draft"
            className="rounded-xl bg-ink text-cream px-4 py-2 font-medium hover:opacity-90"
          >
            + New portfolio
          </Link>
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
