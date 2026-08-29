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
        <h2 className="font-semibold mb-3">The formula (model v1)</h2>
        <p className="text-sm text-ink-soft">
          Per-game production, weighted, then scaled to dollars and adjusted for form and
          availability:
        </p>
        <pre className="num text-xs bg-cream border border-line rounded-lg p-3 mt-3 overflow-x-auto">
value = ( 1.0·PTS + 1.2·REB + 1.5·AST + 3·STL + 3·BLK − 1·TOV )
        × $12  × form(last 5 vs season)  × availability
        </pre>
        <div className="grid grid-cols-3 sm:grid-cols-6 gap-2 mt-4">
          {WEIGHTS.map(([label, w]) => (
            <div key={label} className="rounded-lg border border-line bg-card px-2 py-2 text-center">
              <div className="text-xs text-ink-faint">{label}</div>
              <div className="num font-semibold">{w}</div>
            </div>
          ))}
        </div>
      </Card>

      <section>
        <h2 className="font-semibold mb-3">Does the model make sense? (validation)</h2>
        {data && (
          <>
            <div className="grid sm:grid-cols-2 gap-3 mb-4">
              <StatTile
                label="Value vs production"
                value={num(data.corr_value_production, 2)}
                hint="= 1.00 by construction — a pipeline sanity check"
              />
              <StatTile
                label="Value vs minutes played"
                value={num(data.corr_value_minutes, 2)}
                hint="minutes isn't an input — value tracking coach-assigned role is real signal"
              />
            </div>

            <Card className="mb-4">
              <h3 className="font-medium mb-3">
                Top by value (≥ {data.min_games} games) — face validity
              </h3>
              <table className="w-full text-sm">
                <tbody>
                  {data.top.map((r, i) => (
                    <tr key={r.name} className="border-b border-line last:border-0">
                      <td className="py-2 text-ink-faint num w-6">{i + 1}</td>
                      <td className="py-2 font-medium">{r.name}</td>
                      <td className="py-2 text-right num text-ink-soft">{r.ppg} ppg</td>
                      <td className="py-2 text-right num">{money2(r.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-ink-faint mt-2">Recognizable stars — the model ranks sensibly.</p>
            </Card>

            <Card>
              <h3 className="font-medium mb-3">Where the model breaks — small-sample watch-outs</h3>
              <table className="w-full text-sm">
                <tbody>
                  {data.watchouts.map((r) => (
                    <tr key={r.name} className="border-b border-line last:border-0">
                      <td className="py-2 font-medium">{r.name}</td>
                      <td className="py-2 text-right num text-ink-soft">{r.ppg} ppg</td>
                      <td className="py-2 text-right num text-down">{r.games} g</td>
                      <td className="py-2 text-right num">{money2(r.value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="text-xs text-ink-faint mt-2">
                A few big games (or an injured star&apos;s handful of appearances) distort the
                average. Fix in v2: shrink value toward a prior until enough games are logged.
              </p>
            </Card>
          </>
        )}
      </section>

      <Card>
        <h2 className="font-semibold mb-2">Honest limitations</h2>
        <ul className="text-sm text-ink-soft space-y-1.5 list-disc pl-5">
          <li>
            <b>Model-priced, not market-priced.</b> No order book or supply/demand — two users
            wanting the same player doesn&apos;t move the price.
          </li>
          <li>
            <b>Weights are a heuristic</b>, not fit by regression to an outcome.
          </li>
          <li>
            <b>Box scores miss</b> defense beyond steals/blocks, spacing, and on/off impact.
          </li>
          <li>
            <b>Small samples distort</b> value (see watch-outs above) until enough games accrue.
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
