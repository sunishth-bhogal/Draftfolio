"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money, signedPct, upDown } from "@/lib/format";
import { Card } from "@/components/ui";
import type { Signal } from "@/lib/types";

function SignalChip({ s }: { s: Signal }) {
  const label = s.source === "prediction_market" ? "prediction market" : s.source;
  const body = (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-cream px-2.5 py-1 text-xs">
      <span className="uppercase tracking-wide text-ink-faint">{label}</span>
      <span className="text-ink-soft">{s.headline}</span>
      <span className="num text-ink-faint">· {Math.round(s.confidence * 100)}%</span>
    </span>
  );
  return s.source_url ? (
    <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="hover:opacity-80">
      {body}
    </a>
  ) : (
    body
  );
}

export function ExplainCard({ portfolioId }: { portfolioId: string }) {
  const { data } = useQuery({
    queryKey: ["explain", portfolioId],
    queryFn: () => api.explain(portfolioId),
  });

  if (!data) return null;

  if (!data.available) {
    return (
      <Card>
        <h2 className="font-semibold">Why did it move?</h2>
        <p className="text-sm text-ink-faint mt-2">
          {data.reason ?? "Not enough history yet."} Check back once daily snapshots accrue.
        </p>
      </Card>
    );
  }

  const ret = data.portfolio_return ?? 0;

  return (
    <Card>
      <div className="flex items-baseline justify-between">
        <h2 className="font-semibold">Why did it move?</h2>
        <span className="text-xs text-ink-faint num">
          {data.prev_date} → {data.as_of_date}
        </span>
      </div>
      <p className="mt-2 text-sm text-ink-soft">
        Portfolio moved{" "}
        <span className={`num font-medium ${upDown(ret)}`}>{signedPct(ret)}</span> over the last
        session. Biggest drivers:
      </p>

      <div className="mt-4 space-y-4">
        {data.drivers.map((d) => (
          <div key={d.symbol} className="border-t border-line pt-3 first:border-0 first:pt-0">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-medium">{d.symbol}</span>
                <span className={`num text-sm ${upDown(d.price_change)}`}>
                  {signedPct(d.price_change)}
                </span>
              </div>
              <div className="text-right">
                <div className={`num text-sm font-medium ${upDown(d.contribution)}`}>
                  {signedPct(d.contribution)} of portfolio
                </div>
                <div className={`num text-xs ${upDown(d.dollar_pnl)}`}>
                  {d.dollar_pnl >= 0 ? "+" : ""}
                  {money(d.dollar_pnl)}
                </div>
              </div>
            </div>
            {d.signals.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2">
                {d.signals.map((s, i) => (
                  <SignalChip key={i} s={s} />
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      {data.note && <p className="mt-4 text-xs text-ink-faint">{data.note}</p>}
    </Card>
  );
}
