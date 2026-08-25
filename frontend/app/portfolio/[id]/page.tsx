"use client";

import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { money, money2, pct, signedPct, num, upDown } from "@/lib/format";
import { EquityChart } from "@/components/EquityChart";
import { Card, StatTile, Bar } from "@/components/ui";

export default function PortfolioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  const valuation = useQuery({ queryKey: ["valuation", id], queryFn: () => api.valuation(id) });
  const returns = useQuery({ queryKey: ["returns", id], queryFn: () => api.returns(id) });
  const analytics = useQuery({ queryKey: ["analytics", id], queryFn: () => api.analytics(id) });

  const v = valuation.data;
  const a = analytics.data;
  const totalReturn = a?.cumulative_return ?? null;

  return (
    <div className="space-y-8">
      <Link href="/" className="text-sm text-ink-soft hover:text-ink">
        ← Leaderboard
      </Link>

      <section className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-ink-faint">Portfolio value</div>
          <div className="num text-5xl font-semibold mt-1">{v ? money2(v.equity) : "—"}</div>
          <div className={`num mt-1 ${upDown(totalReturn)}`}>
            {signedPct(totalReturn)} total return
          </div>
        </div>
        <div className="w-full sm:w-auto sm:min-w-[360px]">
          {returns.data && <EquityChart data={returns.data} />}
        </div>
      </section>

      {/* Risk tiles — the "risk-adjusted" story */}
      <section className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile label="Sharpe" value={num(a?.sharpe, 2)} hint="excess return / volatility" />
        <StatTile label="Sortino" value={num(a?.sortino, 2)} hint="downside-only risk" />
        <StatTile
          label="Volatility"
          value={a?.annualized_volatility != null ? pct(a.annualized_volatility) : "—"}
          hint="annualized"
        />
        <StatTile
          label="Max drawdown"
          value={a?.max_drawdown != null ? `-${pct(a.max_drawdown)}` : "—"}
          tone="text-down"
          hint="peak to trough"
        />
        <StatTile label="Beta" value={num(a?.beta, 2)} hint={`vs ${a?.benchmark ?? "—"}`} />
        <StatTile label="Alpha" value={a?.alpha != null ? signedPct(a.alpha) : "—"} hint="annualized" />
        <StatTile
          label="vs Benchmark"
          value={
            a?.cumulative_return != null && a?.benchmark_return != null
              ? signedPct(a.cumulative_return - a.benchmark_return)
              : "—"
          }
          tone={upDown(
            a?.cumulative_return != null && a?.benchmark_return != null
              ? a.cumulative_return - a.benchmark_return
              : null,
          )}
          hint={a?.benchmark ?? undefined}
        />
        <StatTile
          label="Eff. holdings"
          value={num(a?.effective_holdings, 1)}
          hint="1 / concentration"
        />
      </section>

      {/* Holdings */}
      <section className="grid md:grid-cols-3 gap-6">
        <Card className="md:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">Holdings</h2>
            {v && <span className="text-sm text-ink-faint">Cash {money(v.cash)}</span>}
          </div>
          {v && v.holdings.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-ink-faint border-b border-line">
                  <th className="py-2 font-medium">Symbol</th>
                  <th className="py-2 font-medium text-right">Qty</th>
                  <th className="py-2 font-medium text-right">Price</th>
                  <th className="py-2 font-medium text-right">Value</th>
                  <th className="py-2 pl-6 font-medium w-40">Weight</th>
                </tr>
              </thead>
              <tbody>
                {v.holdings.map((h) => (
                  <tr key={h.symbol} className="border-b border-line last:border-0">
                    <td className="py-3 font-medium">{h.symbol}</td>
                    <td className="py-3 text-right num text-ink-soft">{num(h.quantity, 0)}</td>
                    <td className="py-3 text-right num text-ink-soft">{money2(h.price)}</td>
                    <td className="py-3 text-right num">{money(h.market_value)}</td>
                    <td className="py-3 pl-6">
                      <div className="flex items-center gap-2">
                        <Bar value={h.weight} />
                        <span className="num text-xs text-ink-soft w-10 text-right">{pct(h.weight, 0)}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-ink-faint text-sm">No priced holdings.</div>
          )}
        </Card>

        <Card>
          <h2 className="font-semibold mb-4">Composition</h2>
          {v && (
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-ink-soft">Cash</span>
                <span className="num">{money(v.cash)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-soft">Market value</span>
                <span className="num">{money(v.market_value)}</span>
              </div>
              <div className="flex justify-between border-t border-line pt-3 font-medium">
                <span>Equity</span>
                <span className="num">{money(v.equity)}</span>
              </div>
              {v.fx_pending.length > 0 && (
                <div className="text-xs text-ink-faint pt-2">
                  FX pending: {v.fx_pending.join(", ")}
                </div>
              )}
            </div>
          )}
        </Card>
      </section>
    </div>
  );
}
