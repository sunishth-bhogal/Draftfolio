"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money2, num } from "@/lib/format";
import { Card, StatTile } from "@/components/ui";

const WEIGHTS = [
  ["Points", "1.0"],
  ["Rebounds", "1.2"],
  ["Assists", "1.5"],
  ["Steals", "3.0"],
  ["Blocks", "3.0"],
  ["Turnovers", "−1.0"],
];

export default function MethodologyPage() {
  const { data } = useQuery({ queryKey: ["validation"], queryFn: () => api.validation() });

  return (
    <div className="space-y-8 max-w-3xl">
      <section>
        <h1 className="text-4xl font-semibold tracking-tight">How prices work</h1>
        <p className="mt-3 text-ink-soft">
          A player&apos;s price is a <b>transparent valuation of on-court production</b> — not a
          market-cleared price. It&apos;s computed from real box scores, so every dollar is
          traceable and the whole history is reproducible from raw game data.
        </p>
      </section>

      <Card>
        <h2 className="font-semibold mb-3">The formula (model v2)</h2>
        <p className="text-sm text-ink-soft">
          Per-game production, weighted and scaled to dollars, then <b>shrunk toward a quality
          prior</b> based on how many games we&apos;ve actually seen:
        </p>
        <pre className="num text-xs bg-cream border border-line rounded-lg p-3 mt-3 overflow-x-auto">
observed = ( 1.0·PTS + 1.2·REB + 1.5·AST + 3·STL + 3·BLK − 1·TOV ) × $12 × form
value    = (G/(G+K))·observed + (K/(G+K))·prior        (K = 12 games)
        </pre>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-4">
          {WEIGHTS.map(([label, w]) => (
            <div key={label} className="rounded-lg border border-line bg-card px-2 py-2 text-center">
              <div className="text-xs text-ink-faint">{label}</div>
              <div className="num font-semibold">{w}</div>
            </div>
          ))}
        </div>
        <p className="text-sm text-ink-soft mt-4">
          The shrinkage separates <b>current-season confidence</b> (how many games) from{" "}
          <b>underlying ability</b> (the prior). A returning star with two games isn&apos;t marked
          down to nothing — their price leans on last season until the sample grows. Prior =
          previous-season value for veterans, a position-based league prior for rookies.
        </p>
      </Card>

      <section>
        <h2 className="font-semibold mb-3">Does the model make sense? (validation)</h2>
        {data && (
          <>
            <Card className="mb-4">
              <h3 className="font-medium mb-1">Walk-forward predictive test</h3>
              <p className="text-xs text-ink-faint mb-3">
                The real test, with no leakage: value from a player&apos;s first-half games vs
                their production over the second half ({data.predictive_n} players).
              </p>
              <div className="grid grid-cols-2 gap-3">
                <StatTile label="Predictive (Pearson)" value={num(data.predictive_pearson, 2)} />
                <StatTile label="Predictive (Spearman)" value={num(data.predictive_spearman, 2)} />
              </div>
              <p className="text-xs text-ink-faint mt-2">
                Past value genuinely predicts future production — the price carries signal, not
                just a restatement of the same games.
              </p>
            </Card>

            <div className="grid sm:grid-cols-2 gap-3 mb-4">
              <StatTile
                label="Value vs production"
                value={`${num(data.pearson_value_production, 2)} / ${num(data.spearman_value_production, 2)}`}
                hint="Pearson / Spearman — = 1.00 by construction, a pipeline sanity check"
              />
              <StatTile
                label="Value vs minutes"
                value={`${num(data.pearson_value_minutes, 2)} / ${num(data.spearman_value_minutes, 2)}`}
                hint="not fully independent — counting stats rise with minutes"
              />
            </div>

            <Card className="mb-4">
              <h3 className="font-medium mb-3">Average value by position — the center bias</h3>
              <table className="w-full text-sm">
                <tbody>
                  {data.by_position.map((r) => (
                    <tr key={r.position} className="border-b border-line last:border-0">
                      <td className="py-2 font-medium w-16">{r.position}</td>
                      <td className="py-2 text-ink-soft num">{r.n} players</td>
                      <td className="py-2 text-right num">avg {money2(r.avg_value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-ink-faint mt-2">
                Centers value highest — the rebound/block weights reward bigs. Real, and worth
                flagging; a fitted model or an external impact metric (BPM/Win Shares) would
                correct it.
              </p>
            </Card>

            <div className="grid sm:grid-cols-2 gap-4">
              <Card>
                <h3 className="font-medium mb-3">Top by value (≥ {data.min_games} games)</h3>
                <table className="w-full text-sm">
                  <tbody>
                    {data.top.slice(0, 6).map((r, i) => (
                      <tr key={r.name} className="border-b border-line last:border-0">
                        <td className="py-1.5 text-ink-faint num w-6">{i + 1}</td>
                        <td className="py-1.5 font-medium">{r.name}</td>
                        <td className="py-1.5 text-right num">{money2(r.value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Card>
              <Card>
                <h3 className="font-medium mb-3">Small-sample watch-outs</h3>
                <table className="w-full text-sm">
                  <tbody>
                    {data.watchouts.map((r) => (
                      <tr key={r.name} className="border-b border-line last:border-0">
                        <td className="py-1.5 font-medium">{r.name}</td>
                        <td className="py-1.5 text-right num text-down">{r.games} g</td>
                        <td className="py-1.5 text-right num">{money2(r.value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="text-xs text-ink-faint mt-2">
                  Now shrunk toward each player&apos;s prior — flagged, not trusted at face value.
                </p>
              </Card>
            </div>
          </>
        )}
      </section>

      <Card>
        <h2 className="font-semibold mb-2">Honest limitations</h2>
        <ul className="text-sm text-ink-soft space-y-1.5 list-disc pl-5">
          <li>
            <b>Model-priced, not market-priced.</b> No order book or supply/demand yet.
          </li>
          <li>
            <b>Weights are a heuristic</b>, not fit by regression to an outcome.
          </li>
          <li>
            <b>Position bias</b> (above): box scores over-reward rebounding bigs.
          </li>
          <li>
            <b>No external impact metric yet</b> (BPM/Win Shares) — the next validation step.
          </li>
        </ul>
      </Card>

      <p className="text-xs text-ink-faint">
        A simulated market — performance-linked virtual assets traded with fake money, not real
        securities, ownership, or wagers.
      </p>
    </div>
  );
}
