"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money, money2 } from "@/lib/format";
import { getToken } from "@/lib/auth";
import { Card } from "@/components/ui";

export function TradePanel({ instrumentId, price }: { instrumentId: string; price: number | null }) {
  const qc = useQueryClient();
  const [hasToken, setHasToken] = useState(false);
  useEffect(() => setHasToken(!!getToken()), []);

  const me = useQuery({ queryKey: ["me"], queryFn: () => api.me(), enabled: hasToken, retry: false });
  const pid = me.data?.portfolio_id ?? null;
  const valuation = useQuery({
    queryKey: ["valuation", pid],
    queryFn: () => api.valuation(pid!),
    enabled: !!pid,
  });

  const [side, setSide] = useState<"BUY" | "SELL">("BUY");
  const [shares, setShares] = useState(1);
  const [err, setErr] = useState<string | null>(null);

  const trade = useMutation({
    mutationFn: () => api.trade(instrumentId, side, shares),
    onSuccess: () => {
      setErr(null);
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["valuation"] });
      qc.invalidateQueries({ queryKey: ["returns"] });
    },
    onError: () => setErr(side === "BUY" ? "Not enough cash." : "You don't hold that many."),
  });

  if (!hasToken) {
    return (
      <Card>
        <p className="text-sm text-ink-soft">
          <Link href="/login" className="text-accent-deep underline underline-offset-4">Log in</Link> to
          buy or sell.
        </p>
      </Card>
    );
  }

  const cash = valuation.data?.cash ?? 0;
  const held = valuation.data?.holdings.find((h) => h.instrument_id === instrumentId)?.quantity ?? 0;
  const p = price ?? 0;
  const amount = shares * p;
  const canBuy = amount <= cash && shares > 0 && p > 0;
  const canSell = shares <= held && shares > 0;
  const canDo = side === "BUY" ? canBuy : canSell;

  return (
    <Card>
      <div className="flex items-center gap-2 mb-4">
        {(["BUY", "SELL"] as const).map((s) => (
          <button
            key={s}
            onClick={() => { setSide(s); setErr(null); }}
            className={`flex-1 rounded-xl py-2 text-sm font-medium border transition ${
              side === s
                ? s === "BUY"
                  ? "bg-up text-cream border-up"
                  : "bg-down text-cream border-down"
                : "bg-card text-ink-soft border-line hover:border-ink"
            }`}
          >
            {s === "BUY" ? "Buy" : "Sell"}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between text-sm mb-3">
        <span className="text-ink-soft">Shares</span>
        <div className="flex items-center gap-2">
          <button onClick={() => setShares((n) => Math.max(1, n - 1))} className="h-8 w-8 rounded-lg border border-line hover:border-ink">−</button>
          <input
            value={shares}
            onChange={(e) => setShares(Math.max(0, Number(e.target.value) || 0))}
            className="num w-16 text-center rounded-lg border border-line py-1.5 focus:border-ink outline-none"
            inputMode="numeric"
          />
          <button onClick={() => setShares((n) => n + 1)} className="h-8 w-8 rounded-lg border border-line hover:border-ink">+</button>
        </div>
      </div>

      <div className="space-y-1 text-sm border-t border-line pt-3">
        <Row label="Price" value={money2(p)} />
        <Row label={side === "BUY" ? "Cost" : "Proceeds"} value={money2(amount)} strong />
        <Row label="Your cash" value={money(cash)} />
        <Row label="You hold" value={`${held} shares`} />
      </div>

      {err && <div className="text-down text-sm mt-2">{err}</div>}

      <button
        onClick={() => trade.mutate()}
        disabled={!canDo || trade.isPending}
        className={`mt-4 w-full rounded-xl py-3 font-medium text-cream disabled:opacity-40 disabled:cursor-not-allowed ${
          side === "BUY" ? "bg-up hover:opacity-90" : "bg-down hover:opacity-90"
        }`}
      >
        {trade.isPending ? "…" : `${side === "BUY" ? "Buy" : "Sell"} ${shares} ${shares === 1 ? "share" : "shares"}`}
      </button>
    </Card>
  );
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className="text-ink-soft">{label}</span>
      <span className={`num ${strong ? "font-semibold" : ""}`}>{value}</span>
    </div>
  );
}
