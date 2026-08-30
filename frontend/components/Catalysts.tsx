"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { signedPct, upDown } from "@/lib/format";
import { Card } from "@/components/ui";

const ICON: Record<string, string> = {
  performance: "🏀",
  minutes: "⏱",
  form: "📈",
  availability: "🩹",
  schedule: "📅",
};

function arrow(dir: string) {
  if (dir === "up") return <span className="text-up">▲</span>;
  if (dir === "down") return <span className="text-down">▼</span>;
  return <span className="text-ink-faint">•</span>;
}

export function Catalysts({ instrumentId }: { instrumentId: string }) {
  const { data } = useQuery({
    queryKey: ["catalysts", instrumentId],
    queryFn: () => api.catalysts(instrumentId),
  });
  if (!data || !data.available) return null;

  return (
    <Card>
      <div className="flex items-baseline justify-between mb-1">
        <h2 className="font-semibold">What moved it</h2>
        {data.price_change != null && (
          <span className={`num text-sm font-medium ${upDown(data.price_change)}`}>
            {signedPct(data.price_change)} last game
          </span>
        )}
      </div>
      {data.as_of && (
        <p className="text-xs text-ink-faint mb-3 num">latest game {data.as_of}</p>
      )}

      <div className="space-y-2">
        {data.items.map((c, i) => (
          <div key={i} className="flex items-start gap-3 text-sm">
            <span className="w-5 text-center">{ICON[c.kind] ?? "•"}</span>
            <span className="w-4">{arrow(c.direction)}</span>
            <div>
              <span className="font-medium">{c.label}</span>
              <span className="text-ink-soft"> — {c.detail}</span>
            </div>
          </div>
        ))}
      </div>

      <p className="text-xs text-ink-faint mt-3">
        Catalysts are derived from real box scores. Opponent is shown as context, not a price
        driver — correlation, not causation.
      </p>
    </Card>
  );
}
