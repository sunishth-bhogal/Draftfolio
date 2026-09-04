"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { PackResult } from "@/lib/types";

const TIER_STYLE: Record<string, string> = {
  legendary: "text-amber-300",
  epic: "text-fuchsia-300",
  rare: "text-sky-300",
  common: "text-ink-soft",
};

function fmt(seconds: number) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

export function DailyPack() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["pack"], queryFn: () => api.packStatus() });
  const [pull, setPull] = useState<PackResult | null>(null);

  const open = useMutation({
    mutationFn: () => api.openPack(),
    onSuccess: (res) => {
      setPull(res);
      qc.invalidateQueries({ queryKey: ["pack"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["valuation"] });
      qc.invalidateQueries({ queryKey: ["returns"] });
    },
  });

  const s = status.data;
  if (!s) return null;

  // Reveal of the pulled card.
  if (pull) {
    return (
      <Link href={`/player/${pull.instrument_id}`}>
        <div className="rounded-2xl bg-elevated text-ink p-6 flex items-center gap-5 hover:opacity-95 transition">
          {pull.headshot_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={pull.headshot_url} alt="" className="h-16 w-16 rounded-full object-cover border border-line bg-white/5" />
          ) : (
            <div className="h-16 w-16 rounded-xl bg-white/5 flex items-center justify-center text-3xl">🎁</div>
          )}
          <div className="flex-1">
            <div className={`text-xs uppercase tracking-wide ${TIER_STYLE[pull.tier] ?? "text-ink-soft"}`}>
              {pull.tier} pull · +{pull.xp_awarded} XP
            </div>
            <div className="text-2xl font-semibold mt-0.5">{pull.player}</div>
            <div className="text-sm text-ink-soft">
              {pull.shares} shares · {money(pull.value)} added to your team →
            </div>
          </div>
          <div className="text-4xl">🎉</div>
        </div>
      </Link>
    );
  }

  if (!s.can_claim) {
    return (
      <div className="rounded-2xl border border-line bg-card px-6 py-4 flex items-center justify-between text-sm">
        <span className="text-ink-soft">
          Next pack in <span className="num font-medium">{fmt(s.seconds_remaining)}</span> ·{" "}
          <span className="num">{s.streak}</span>-streak 🔥
        </span>
        <span className="text-ink-faint">Packs every {s.cooldown_hours}h</span>
      </div>
    );
  }

  return (
    <button
      onClick={() => open.mutate()}
      disabled={open.isPending}
      className="w-full rounded-2xl bg-accent/20 border border-accent/50 px-6 py-4 flex items-center justify-between hover:bg-accent/30 transition disabled:opacity-50"
    >
      <div className="text-left">
        <div className="font-semibold flex items-center gap-2">
          <span className="text-xl">🎁</span> Open your player pack
        </div>
        <div className="text-xs text-ink-soft mt-0.5">
          A random player (~{money(1000)}) lands on your team · every {s.cooldown_hours}h
        </div>
      </div>
      <span className="rounded-xl bg-ink text-cream px-4 py-2 text-sm font-medium">
        {open.isPending ? "…" : "Open"}
      </span>
    </button>
  );
}
