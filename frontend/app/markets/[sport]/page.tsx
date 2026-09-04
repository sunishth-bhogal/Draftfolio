"use client";

import { use, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { money2 } from "@/lib/format";
import { Card } from "@/components/ui";
import type { Instrument } from "@/lib/types";

const TITLES: Record<string, string> = { nba: "NBA", nhl: "NHL", index: "Index Funds" };

export default function SportPage({ params }: { params: Promise<{ sport: string }> }) {
  const { sport } = use(params);
  const key = sport.toLowerCase();
  const instruments = useQuery({ queryKey: ["instruments"], queryFn: () => api.instruments() });
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const all = instruments.data ?? [];
  const isIndex = key === "index";

  const items = useMemo(
    () =>
      all.filter((i) =>
        isIndex
          ? i.asset_class === "ETF"
          : i.asset_class === "PLAYER" && (i.sport ?? "").toLowerCase() === key,
      ),
    [all, key, isIndex],
  );

  const filtered = q
    ? items.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()))
    : items;

  // Group players by team (index funds group by sport).
  const groups = useMemo(() => {
    const g: Record<string, Instrument[]> = {};
    for (const i of filtered) {
      const bucket = isIndex ? (i.sport ?? "Other") : (i.team ?? "Free Agents");
      (g[bucket] ??= []).push(i);
    }
    for (const k of Object.keys(g)) {
      g[k].sort((a, b) => (b.last_price ?? 0) - (a.last_price ?? 0));
    }
    return g;
  }, [filtered, isIndex]);

  const groupNames = Object.keys(groups).sort();

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link href="/markets" className="text-sm text-ink-soft hover:text-ink">
            ← Markets
          </Link>
          <h1 className="text-3xl font-semibold tracking-tight">{TITLES[key] ?? key}</h1>
        </div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search players…"
          className="rounded-xl border border-line bg-card px-4 py-2 text-sm w-56 focus:border-ink outline-none"
        />
      </div>

      {isIndex ? (
        <div className="rounded-2xl border border-line bg-card overflow-hidden">
          {filtered.map((i) => (
            <PlayerRow key={i.id} i={i} isIndex />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {groupNames.map((team) => {
            const expanded = q ? true : open === team;
            return (
              <div key={team} className="rounded-2xl border border-line bg-card overflow-hidden">
                <button
                  onClick={() => setOpen(expanded ? null : team)}
                  className="w-full flex items-center justify-between px-5 py-3 hover:bg-elevated/50"
                >
                  <span className="font-medium">{team}</span>
                  <span className="text-xs text-ink-faint num">
                    {groups[team].length} players {expanded ? "▲" : "▼"}
                  </span>
                </button>
                {expanded && (
                  <div className="border-t border-line">
                    {groups[team].map((i) => (
                      <PlayerRow key={i.id} i={i} />
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {groupNames.length === 0 && <p className="text-ink-soft text-sm">No matches.</p>}
        </div>
      )}
    </div>
  );
}

function PlayerRow({ i, isIndex = false }: { i: Instrument; isIndex?: boolean }) {
  return (
    <Link
      href={`/player/${i.id}`}
      className="flex items-center gap-3 px-5 py-3 border-b border-line last:border-0 hover:bg-elevated/50"
    >
      {i.headshot_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={i.headshot_url} alt={i.name} className="h-9 w-9 rounded-full bg-cream object-cover border border-line" />
      ) : (
        <div className="h-9 w-9 rounded-lg bg-elevated text-ink flex items-center justify-center text-sm">
          {i.sport === "NHL" ? "🏒" : i.sport === "MULTI" ? "★" : "🏀"}
        </div>
      )}
      <div className="flex-1 min-w-0">
        <div className="font-medium truncate">{i.name}</div>
        <div className="text-xs text-ink-faint">
          {isIndex ? "Index fund" : `${i.position ?? "?"} · ${i.team ?? ""}`}
        </div>
      </div>
      <div className="num text-sm">{i.last_price != null ? money2(i.last_price) : "—"}</div>
    </Link>
  );
}
