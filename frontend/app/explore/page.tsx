"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money2, signedPct, upDown } from "@/lib/format";
import { Card } from "@/components/ui";
import type { Mover, PopularItem } from "@/lib/types";

function icon(sport: string | null) {
  return sport === "NHL" ? "🏒" : sport === "MULTI" ? "★" : "🏀";
}

function Avatar({ url, sport }: { url: string | null; sport: string | null }) {
  return url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt="" className="h-10 w-10 rounded-full bg-cream object-cover border border-line" />
  ) : (
    <div className="h-10 w-10 rounded-lg bg-ink text-cream flex items-center justify-center text-sm">
      {icon(sport)}
    </div>
  );
}

export default function ExplorePage() {
  const { data } = useQuery({ queryKey: ["explore"], queryFn: () => api.explore() });

  return (
    <div className="space-y-10">
      <section>
        <h1 className="text-4xl font-semibold tracking-tight">Explore</h1>
        <p className="mt-2 text-ink-soft">What&apos;s hot, what&apos;s held, and who&apos;s about to list.</p>
      </section>

      {/* Trending */}
      <section>
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-semibold">🔥 Trending — playing well</h2>
          <span className="text-xs text-ink-faint">value over last {6} games</span>
        </div>
        <div className="grid sm:grid-cols-2 gap-3">
          {(data?.trending ?? []).map((m: Mover) => (
            <Link key={m.instrument_id} href={`/player/${m.instrument_id}`}>
              <Card className="hover:border-ink transition flex items-center gap-3 py-3">
                <Avatar url={m.headshot_url} sport={m.sport} />
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{m.name}</div>
                  <div className="text-xs text-ink-faint">{m.position ?? "?"} · {m.team ?? ""}</div>
                </div>
                <div className="text-right">
                  <div className="num text-sm">{money2(m.price)}</div>
                  <div className={`num text-xs ${upDown(m.change)}`}>{signedPct(m.change)}</div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* Popular */}
      <section>
        <h2 className="font-semibold mb-3">👥 Popular — most held</h2>
        <div className="rounded-2xl border border-line bg-card overflow-hidden">
          {(data?.popular ?? []).map((p: PopularItem) => (
            <Link
              key={p.instrument_id}
              href={`/player/${p.instrument_id}`}
              className="flex items-center gap-3 px-5 py-3 border-b border-line last:border-0 hover:bg-cream/60"
            >
              <Avatar url={p.headshot_url} sport={p.sport} />
              <div className="flex-1 font-medium">{p.name}</div>
              <div className="text-xs text-ink-soft num">{p.holders} holders</div>
              <div className="num text-sm w-20 text-right">{money2(p.price)}</div>
            </Link>
          ))}
        </div>
      </section>

      {/* IPOs */}
      <section>
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-semibold">🚀 Upcoming IPOs</h2>
          <span className="text-xs text-ink-faint">not tradeable yet</span>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {(data?.ipos ?? []).map((i) => (
            <Card key={i.name} className="opacity-90">
              <div className="flex items-center justify-between">
                <span className="text-2xl">{icon(i.sport)}</span>
                <span className="text-xs rounded-full bg-accent/30 text-accent-deep px-2 py-0.5">
                  {i.expected}
                </span>
              </div>
              <div className="font-semibold mt-2">{i.name}</div>
              <div className="text-xs text-ink-faint">{i.position} · {i.sport}</div>
              <div className="text-sm text-ink-soft mt-2">{i.note}</div>
              <button
                disabled
                className="mt-3 w-full rounded-lg border border-line py-2 text-sm text-ink-faint cursor-not-allowed"
              >
                Coming soon
              </button>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
