"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Card } from "@/components/ui";

const CATS = [
  { slug: "nba", label: "NBA", icon: "🏀", blurb: "Basketball players by team" },
  { slug: "nhl", label: "NHL", icon: "🏒", blurb: "Hockey players by team" },
  { slug: "index", label: "Index Funds", icon: "★", blurb: "Baskets of players" },
];

export default function MarketsPage() {
  const instruments = useQuery({ queryKey: ["instruments"], queryFn: () => api.instruments() });
  const counts = (instruments.data ?? []).reduce<Record<string, number>>((acc, i) => {
    const key = i.asset_class === "ETF" ? "index" : (i.sport ?? "").toLowerCase();
    acc[key] = (acc[key] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-4xl font-semibold tracking-tight">Markets</h1>
        <p className="mt-2 text-ink-soft">Browse by sport, then by team — or trade a whole index.</p>
      </section>

      <div className="grid sm:grid-cols-3 gap-4">
        {CATS.map((c) => (
          <Link key={c.slug} href={`/markets/${c.slug}`}>
            <Card className="hover:border-ink transition h-full">
              <div className="text-3xl">{c.icon}</div>
              <div className="mt-3 font-semibold text-lg">{c.label}</div>
              <div className="text-sm text-ink-soft">{c.blurb}</div>
              <div className="text-xs text-ink-faint num mt-3">{counts[c.slug] ?? 0} listed</div>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
