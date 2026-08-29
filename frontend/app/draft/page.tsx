"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { money, money2, pct } from "@/lib/format";
import { Card, Bar } from "@/components/ui";

const CAP = 100000;

export default function DraftPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [picks, setPicks] = useState<Record<string, number>>({}); // symbol -> qty
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const instruments = useQuery({ queryKey: ["instruments"], queryFn: () => api.instruments() });

  const priced = (instruments.data ?? []).filter((i) => i.last_price != null);

  const spent = useMemo(
    () =>
      Object.entries(picks).reduce((sum, [sym, qty]) => {
        const inst = priced.find((i) => i.symbol === sym);
        return sum + (inst?.last_price ?? 0) * qty;
      }, 0),
    [picks, priced],
  );
  const remaining = CAP - spent;
  const overCap = remaining < 0;

  const nPicks = Object.values(picks).filter((q) => q > 0).length;
  const canDraft = name.trim().length > 0 && nPicks > 0 && !overCap && !submitting;

  function setQty(symbol: string, qty: number) {
    setPicks((p) => ({ ...p, [symbol]: Math.max(0, qty) }));
  }

  async function submitDraft() {
    setSubmitting(true);
    setError(null);
    try {
      const pf = await api.createPortfolio(name.trim(), CAP);
      for (const [symbol, qty] of Object.entries(picks)) {
        if (qty <= 0) continue;
        const inst = priced.find((i) => i.symbol === symbol)!;
        await api.placeOrder(
          pf.id,
          { symbol, quantity: qty, price: inst.last_price! },
          `${pf.id}-${symbol}`,
        );
      }
      router.push(`/portfolio/${pf.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Draft failed");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-4xl font-semibold tracking-tight">Draft room</h1>
        <p className="mt-2 text-ink-soft max-w-xl">
          You have <span className="text-ink font-medium num">{money(CAP)}</span> in virtual
          cash. Draft <b>performance-linked virtual player assets</b> under the cap and compete on
          risk-adjusted performance. Simulated market · fake money.
        </p>
      </section>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Asset picker */}
        <div className="lg:col-span-2 space-y-3">
          {instruments.isLoading && <div className="text-ink-soft">Loading assets…</div>}
          {instruments.error && (
            <div className="text-down">Couldn&apos;t load instruments — is the API on :8000?</div>
          )}
          {priced.map((inst) => {
            const qty = picks[inst.symbol] ?? 0;
            const cost = (inst.last_price ?? 0) * qty;
            return (
              <div
                key={inst.id}
                className="rounded-xl border border-line bg-card px-4 py-3 flex items-center gap-4"
              >
                {inst.headshot_url && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={inst.headshot_url}
                    alt={inst.name}
                    className="h-11 w-11 rounded-full bg-cream object-cover border border-line"
                  />
                )}
                <div className="flex-1 min-w-0">
                  <Link href={`/player/${inst.id}`} className="font-semibold truncate hover:text-accent-deep block">
                    {inst.name}
                  </Link>
                  <div className="text-xs text-ink-faint">
                    {inst.asset_class === "PLAYER"
                      ? `${inst.position ?? "?"} · ${inst.team ?? ""}`
                      : (inst.sector ?? inst.symbol)}{" "}
                    · <span className="num">{money2(inst.last_price ?? 0)}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setQty(inst.symbol, qty - 10)}
                    className="h-8 w-8 rounded-lg border border-line hover:border-ink text-ink-soft"
                    aria-label={`Sell 10 ${inst.symbol}`}
                  >
                    −
                  </button>
                  <input
                    value={qty}
                    onChange={(e) => setQty(inst.symbol, Number(e.target.value) || 0)}
                    className="num w-16 text-center rounded-lg border border-line py-1.5 focus:border-ink outline-none"
                    inputMode="numeric"
                  />
                  <button
                    onClick={() => setQty(inst.symbol, qty + 10)}
                    className="h-8 w-8 rounded-lg border border-line hover:border-ink text-ink-soft"
                    aria-label={`Buy 10 ${inst.symbol}`}
                  >
                    +
                  </button>
                </div>
                <div className="num w-24 text-right text-sm text-ink-soft">
                  {cost > 0 ? money(cost) : "—"}
                </div>
              </div>
            );
          })}
          {!instruments.isLoading && priced.length === 0 && (
            <div className="text-ink-faint text-sm">
              No priced instruments. Run the seed script to populate the catalog.
            </div>
          )}
        </div>

        {/* Live cap panel */}
        <div className="lg:col-span-1">
          <Card className="sticky top-24">
            <label className="block text-xs uppercase tracking-wide text-ink-faint mb-1">
              Portfolio name
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Power Play"
              className="w-full rounded-lg border border-line px-3 py-2 mb-5 focus:border-ink outline-none"
            />

            <div className="flex justify-between text-sm">
              <span className="text-ink-soft">Salary cap</span>
              <span className="num">{money(CAP)}</span>
            </div>
            <div className="flex justify-between text-sm mt-1">
              <span className="text-ink-soft">Drafted</span>
              <span className="num">{money(spent)}</span>
            </div>
            <div className="flex justify-between font-medium mt-1">
              <span>Remaining</span>
              <span className={`num ${overCap ? "text-down" : ""}`}>{money(remaining)}</span>
            </div>
            <div className="mt-3">
              <Bar value={spent / CAP} tone={overCap ? "bg-down" : "bg-accent"} />
              <div className="text-xs text-ink-faint mt-1">{pct(spent / CAP, 0)} of cap used</div>
            </div>

            {overCap && (
              <div className="text-down text-sm mt-3">Over the cap — remove some picks.</div>
            )}
            {error && <div className="text-down text-sm mt-3">{error}</div>}

            <button
              onClick={submitDraft}
              disabled={!canDraft}
              className="mt-5 w-full rounded-xl bg-ink text-cream py-3 font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90 transition"
            >
              {submitting ? "Drafting…" : `Draft ${nPicks || ""} ${nPicks === 1 ? "asset" : "assets"}`}
            </button>
            <p className="text-xs text-ink-faint mt-3">
              Picks execute at the latest price and post to the ledger as orders.
            </p>
          </Card>
        </div>
      </div>
    </div>
  );
}
