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

function Avatar({ url, sport, size = "h-11 w-11" }: { url: string | null; sport: string | null; size?: string }) {
  return url ? (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={url} alt="" className={`${size} rounded-full bg-cream object-cover border border-line`} />
  ) : (
    <div className={`${size} rounded-lg bg-ink text-cream flex items-center justify-center`}>{icon(sport)}</div>
  );
}

export default function ExplorePage() {
  const { data } = useQuery({ queryKey: ["explore"], queryFn: () => api.explore() });
  const trending = data?.trending ?? [];
  const spotlight = trending[0];
  const rest = trending.slice(1);

  return (
    <div className="space-y-12">
      <section>
        <h1 className="text-4xl font-semibold tracking-tight">Explore</h1>
        <p className="mt-2 text-ink-soft">What&apos;s hot, what&apos;s held, and who&apos;s about to list.</p>
      </section>

      {/* Spotlight — the hottest mover */}
      {spotlight && (
        <section>
          <div className="text-xs uppercase tracking-wide text-ink-faint mb-2">🔥 Mover of the moment</div>
          <Link href={`/player/${spotlight.instrument_id}`}>
            <div className="rounded-3xl bg-ink text-cream p-6 sm:p-8 flex items-center gap-6 hover:opacity-95 transition overflow-hidden relative">
              <div className="absolute -right-8 -top-10 text-[10rem] opacity-10 select-none">{icon(spotlight.sport)}</div>
              <Avatar url={spotlight.headshot_url} sport={spotlight.sport} size="h-24 w-24" />
              <div className="flex-1 min-w-0 relative">
                <div className="text-cream/60 text-sm">{spotlight.position ?? "?"} · {spotlight.team ?? ""}</div>
                <div className="text-3xl font-semibold truncate">{spotlight.name}</div>
                <div className="mt-2 flex items-baseline gap-3">
                  <span className="num text-2xl">{money2(spotlight.price)}</span>
                  <span className="num text-lg text-accent font-semibold">{signedPct(spotlight.change)}</span>
                  <span className="text-cream/50 text-xs">last 6 games</span>
                </div>
              </div>
            </div>
          </Link>
        </section>
      )}

      {/* Trending grid */}
      <section>
        <h2 className="font-semibold mb-4">Trending — playing well</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {rest.map((m: Mover, i) => (
            <Link key={m.instrument_id} href={`/player/${m.instrument_id}`}>
              <Card className="hover:border-ink transition flex items-center gap-3 py-3">
                <span className="num text-ink-faint w-5 text-center text-sm">{i + 2}</span>
                <Avatar url={m.headshot_url} sport={m.sport} />
                <div className="flex-1 min-w-0">
                  <div className="font-medium truncate">{m.name}</div>
                  <div className="text-xs text-ink-faint truncate">{m.position ?? "?"} · {m.team ?? ""}</div>
                </div>
                <div className="text-right">
                  <div className="num text-sm">{money2(m.price)}</div>
                  <div className={`num text-xs font-medium ${upDown(m.change)}`}>{signedPct(m.change)}</div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* Popular */}
      <section>
        <h2 className="font-semibold mb-4">Most held</h2>
        <div className="grid sm:grid-cols-2 gap-3">
          {(data?.popular ?? []).map((p: PopularItem, i) => (
            <Link key={p.instrument_id} href={`/player/${p.instrument_id}`}>
              <Card className="hover:border-ink transition flex items-center gap-3 py-3">
                <span className="w-6 text-center text-lg">
                  {i < 3 ? ["🥇", "🥈", "🥉"][i] : <span className="num text-ink-faint text-sm">{i + 1}</span>}
                </span>
                <Avatar url={p.headshot_url} sport={p.sport} />
                <div className="flex-1 min-w-0 font-medium truncate">{p.name}</div>
                <div className="text-xs text-ink-soft num">{p.holders} owners</div>
                <div className="num text-sm w-20 text-right">{money2(p.price)}</div>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* IPOs */}
      <section>
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="font-semibold">🚀 Upcoming IPOs</h2>
          <span className="text-xs text-ink-faint">listing soon · not tradeable yet</span>
        </div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {(data?.ipos ?? []).map((ipo) => {
            const listed = ipo.status === "listed" && ipo.instrument_id;
            const days = Math.ceil((new Date(ipo.list_date).getTime() - Date.now()) / 86400000);
            const card = (
              <div className="rounded-2xl border border-line bg-gradient-to-br from-accent/15 to-card p-5 flex flex-col h-full">
                <div className="flex items-center justify-between">
                  <span className="text-3xl">{icon(ipo.sport)}</span>
                  <span
                    className={`text-[11px] rounded-full px-2 py-0.5 ${
                      listed ? "bg-up text-cream" : "bg-ink text-cream"
                    }`}
                  >
                    {listed ? "Now trading" : days > 0 ? `Lists in ${days}d` : "Listing"}
                  </span>
                </div>
                <div className="font-semibold text-lg mt-3">{ipo.name}</div>
                <div className="text-xs text-ink-faint">{ipo.position} · {ipo.sport}</div>
                <div className="text-sm text-ink-soft mt-2 flex-1">{ipo.note}</div>
                <div className="mt-3 border-t border-line pt-2 flex items-center justify-between text-xs">
                  <span className="text-ink-faint num">
                    {listed ? "Price" : `IPO ${ipo.list_date}`}
                  </span>
                  <span className="num font-medium">{money2(ipo.ipo_price)}</span>
                </div>
                {listed && (
                  <div className="mt-2 text-center text-sm text-accent-deep font-medium">Trade now →</div>
                )}
              </div>
            );
            return listed ? (
              <Link key={ipo.name} href={`/player/${ipo.instrument_id}`}>{card}</Link>
            ) : (
              <div key={ipo.name}>{card}</div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
