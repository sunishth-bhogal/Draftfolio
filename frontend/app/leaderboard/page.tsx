"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { pct, signedPct, num } from "@/lib/format";
import { upDown } from "@/lib/format";
import type { ScoreMode } from "@/lib/types";
import { Bar } from "@/components/ui";

const MODES: { key: ScoreMode; label: string; blurb: string }[] = [
  { key: "SPRINT", label: "Sprint", blurb: "Mostly total return" },
  { key: "BALANCED", label: "Balanced", blurb: "Return plus risk control" },
  { key: "INVESTOR", label: "Investor", blurb: "Risk-adjusted & diversified" },
];

export default function Home() {
  const [mode, setMode] = useState<ScoreMode>("BALANCED");
  const { data, isLoading, error } = useQuery({
    queryKey: ["leaderboard", mode],
    queryFn: () => api.leaderboard(mode),
  });

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-4xl font-semibold tracking-tight max-w-2xl">
          Invest like a team. <span className="text-ink-soft">Learn like an analyst.</span>
        </h1>
        <p className="mt-3 text-ink-soft max-w-xl">
          A simulated market for <span className="text-ink font-medium">performance-linked
          virtual player assets</span>. Draft under a cap with fake money and compete on
          risk-adjusted performance — prices respond to real player form, not luck.
        </p>
      </section>

      <section className="flex flex-wrap items-center gap-2">
        {MODES.map((m) => (
          <button
            key={m.key}
            onClick={() => setMode(m.key)}
            className={`rounded-full px-4 py-2 text-sm border transition ${
              mode === m.key
                ? "bg-ink text-cream border-ink"
                : "bg-card text-ink-soft border-line hover:border-ink"
            }`}
          >
            <span className="font-medium">{m.label}</span>
            <span className={mode === m.key ? "text-cream/70" : "text-ink-faint"}> · {m.blurb}</span>
          </button>
        ))}
      </section>

      {data && (
        <p className="text-sm text-ink-faint">
          Score ={" "}
          <b className="text-ink-soft">{data.weights.R}</b> return +{" "}
          <b className="text-ink-soft">{data.weights.B}</b> vs {data.benchmark} +{" "}
          <b className="text-ink-soft">{data.weights.D}</b> drawdown control +{" "}
          <b className="text-ink-soft">{data.weights.C}</b> diversification, each a
          percentile rank within the league.
        </p>
      )}

      <section>
        {isLoading && <div className="text-ink-soft">Loading leaderboard…</div>}
        {error && (
          <div className="text-down">
            Couldn&apos;t reach the API. Is the backend running on :8000?
          </div>
        )}
        {data && (
          <div className="rounded-2xl border border-line bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-ink-faint border-b border-line">
                  <th className="px-5 py-3 font-medium">#</th>
                  <th className="px-5 py-3 font-medium">Portfolio</th>
                  <th className="px-5 py-3 font-medium w-48">Score</th>
                  <th className="px-5 py-3 font-medium text-right">Return</th>
                  <th className="px-5 py-3 font-medium text-right">Max DD</th>
                  <th className="px-5 py-3 font-medium text-right">Eff. holdings</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.map((r) => (
                  <tr key={r.portfolio_id} className="border-b border-line last:border-0 hover:bg-cream/60">
                    <td className="px-5 py-4 num text-ink-faint">{r.rank}</td>
                    <td className="px-5 py-4">
                      <Link href={`/portfolio/${r.portfolio_id}`} className="font-medium hover:text-accent-deep">
                        {r.name}
                      </Link>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <span className="num font-semibold w-12">{r.score.toFixed(1)}</span>
                        <div className="flex-1">
                          <Bar value={r.score / 100} />
                        </div>
                      </div>
                    </td>
                    <td className={`px-5 py-4 text-right num ${upDown(r.cumulative_return)}`}>
                      {signedPct(r.cumulative_return)}
                    </td>
                    <td className="px-5 py-4 text-right num text-down">
                      {r.max_drawdown === null ? "—" : `-${pct(r.max_drawdown)}`}
                    </td>
                    <td className="px-5 py-4 text-right num text-ink-soft">
                      {num(r.effective_holdings, 1)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
