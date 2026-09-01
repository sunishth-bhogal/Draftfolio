"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money, money2 } from "@/lib/format";
import { getToken } from "@/lib/auth";
import { Card } from "@/components/ui";
import type { OpenResult, StoreTier } from "@/lib/types";

const TIER_ICON: Record<string, string> = { bronze: "🥉", silver: "🥈", gold: "🥇", elite: "💎" };
const RARITY: Record<string, string> = {
  legendary: "text-amber-300",
  epic: "text-fuchsia-300",
  rare: "text-sky-300",
  common: "text-cream/70",
};

export default function PacksPage() {
  const qc = useQueryClient();
  const [hasToken, setHasToken] = useState(false);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setHasToken(!!getToken());
    setReady(true);
  }, []);

  const store = useQuery({ queryKey: ["store"], queryFn: () => api.store(), enabled: hasToken, retry: false });
  const [opened, setOpened] = useState<OpenResult | null>(null);

  const open = useMutation({
    mutationFn: (tier: string) => api.openStorePack(tier),
    onSuccess: (res) => {
      setOpened(res);
      qc.invalidateQueries({ queryKey: ["store"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["valuation"] });
    },
  });

  if (ready && !hasToken) {
    return (
      <Card>
        <p className="text-ink-soft">
          <Link href="/login" className="text-accent-deep underline underline-offset-4">Log in</Link> to
          buy packs. Earn cash from your free 12h pack and by selling cards.
        </p>
      </Card>
    );
  }

  const cash = store.data?.cash ?? 0;

  return (
    <div className="space-y-8">
      <section className="flex items-end justify-between">
        <div>
          <h1 className="text-4xl font-semibold tracking-tight">Pack store</h1>
          <p className="mt-2 text-ink-soft">Spend cash on a pack. Bigger packs, better odds — it&apos;s a gamble.</p>
        </div>
        <div className="text-right">
          <div className="text-xs uppercase tracking-wide text-ink-faint">Your cash</div>
          <div className="num text-2xl font-semibold">{money(cash)}</div>
        </div>
      </section>

      {/* Reveal of the latest open */}
      {opened && (
        <div className="rounded-2xl bg-ink text-cream p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="font-semibold">
              You opened a {opened.tier} pack — pulled {opened.cards.length}{" "}
              {opened.cards.length === 1 ? "card" : "cards"}
            </div>
            <div className={`num text-sm ${opened.total_value >= opened.cost ? "text-up" : "text-down"}`}>
              {money(opened.total_value)} for {money(opened.cost)}
            </div>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {opened.cards.map((c, i) => (
              <Link
                key={i}
                href={`/player/${c.instrument_id}`}
                className="rounded-xl bg-cream/5 border border-cream/10 p-3 flex items-center gap-3 hover:bg-cream/10"
              >
                {c.headshot_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={c.headshot_url} alt="" className="h-11 w-11 rounded-full object-cover bg-cream/10" />
                ) : (
                  <div className="h-11 w-11 rounded-lg bg-cream/10 flex items-center justify-center">🏒</div>
                )}
                <div className="min-w-0">
                  <div className={`text-xs uppercase ${RARITY[c.tier] ?? "text-cream/60"}`}>{c.tier}</div>
                  <div className="font-medium truncate">{c.player}</div>
                  <div className="num text-xs text-cream/60">{money2(c.value)}</div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Tiers */}
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {(store.data?.tiers ?? []).map((t: StoreTier) => {
          const afford = cash >= t.cost;
          return (
            <Card key={t.key} className="flex flex-col">
              <div className="text-4xl">{TIER_ICON[t.key] ?? "🎁"}</div>
              <div className="mt-3 font-semibold text-lg">{t.name}</div>
              <div className="text-sm text-ink-soft flex-1">{t.blurb}</div>
              <div className="mt-3 flex flex-wrap gap-1 text-[11px]">
                {Object.entries(t.weights).map(([r, w]) => (
                  <span key={r} className={`rounded-full border border-line px-1.5 py-0.5 ${RARITY[r] ?? ""}`}>
                    {r} {w}%
                  </span>
                ))}
              </div>
              <button
                onClick={() => open.mutate(t.key)}
                disabled={!afford || open.isPending}
                className="mt-4 w-full rounded-xl bg-ink text-cream py-2.5 font-medium disabled:opacity-40 disabled:cursor-not-allowed hover:opacity-90"
              >
                {afford ? `Open · ${money(t.cost)}` : `Need ${money(t.cost)}`}
              </button>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
