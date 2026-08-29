"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money2, upDown } from "@/lib/format";
import { Card } from "@/components/ui";

const STAT_LABEL: Record<string, string> = {
  points: "Points",
  rebounds: "Rebounds",
  assists: "Assists",
  steals: "Steals",
  blocks: "Blocks",
  turnovers: "Turnovers",
};

export function ValueBreakdown({ instrumentId }: { instrumentId: string }) {
  const { data } = useQuery({
    queryKey: ["breakdown", instrumentId],
    queryFn: () => api.breakdown(instrumentId),
  });
  if (!data || !data.available) return null;

  const entries = Object.entries(data.components);
  const maxAbs = Math.max(...entries.map(([, v]) => Math.abs(v)), 1);

  return (
    <Card>
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-semibold">Why this value</h2>
        <span className="text-xs text-ink-faint num">
          {data.games} games · model {data.formula_version}
        </span>
      </div>

      <div className="space-y-2">
        {entries.map(([stat, dollars]) => {
          const avg = data.averages[stat];
          const pos = dollars >= 0;
          return (
            <div key={stat} className="flex items-center gap-3 text-sm">
              <div className="w-28 text-ink-soft">
                {STAT_LABEL[stat] ?? stat}
                {avg != null && <span className="text-ink-faint num"> · {avg}</span>}
              </div>
              <div className="flex-1 flex items-center">
                {/* center baseline: negative bars go left, positive right */}
                <div className="w-1/2 flex justify-end">
                  {!pos && (
                    <div
                      className="h-2 rounded-l-full bg-down"
                      style={{ width: `${(Math.abs(dollars) / maxAbs) * 100}%` }}
                    />
                  )}
                </div>
                <div className="w-1/2">
                  {pos && (
                    <div
                      className="h-2 rounded-r-full bg-accent"
                      style={{ width: `${(dollars / maxAbs) * 100}%` }}
                    />
                  )}
                </div>
              </div>
              <div className={`num w-20 text-right ${upDown(dollars)}`}>
                {pos ? "+" : ""}
                {money2(dollars)}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-4 pt-3 border-t border-line space-y-1 text-sm">
        <Row label="Base value (production)" value={money2(data.base_value)} />
        <Row
          label={`Recent form (×${data.form_multiplier})`}
          value={`${data.form_adjustment >= 0 ? "+" : ""}${money2(data.form_adjustment)}`}
          tone={upDown(data.form_adjustment)}
        />
        <div className="flex justify-between font-semibold pt-1">
          <span>Model value</span>
          <span className="num">{money2(data.final_value)}</span>
        </div>
      </div>
    </Card>
  );
}

function Row({ label, value, tone = "" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-ink-soft">{label}</span>
      <span className={`num ${tone}`}>{value}</span>
    </div>
  );
}
