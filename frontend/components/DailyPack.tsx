"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { money } from "@/lib/format";
import type { ClaimResult } from "@/lib/types";

export function DailyPack() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["daily"], queryFn: () => api.dailyStatus() });
  const [reveal, setReveal] = useState<ClaimResult | null>(null);

  const claim = useMutation({
    mutationFn: () => api.claimDaily(),
    onSuccess: (res) => {
      setReveal(res);
      // Refresh cash, portfolio value, profile, and status.
      qc.invalidateQueries({ queryKey: ["daily"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["valuation"] });
      qc.invalidateQueries({ queryKey: ["returns"] });
    },
  });

  const s = status.data;
  if (!s) return null;

  // Reveal state after claiming.
  if (reveal) {
    return (
      <div className="rounded-2xl bg-ink text-cream p-6 flex items-center justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-cream/60">
            {reveal.is_welcome ? "Welcome pack" : `Day ${reveal.streak} streak`}
          </div>
          <div className="num text-3xl font-semibold mt-1">+{money(reveal.reward)}</div>
          <div className="text-xs text-cream/60 mt-1">+{reveal.xp_awarded} XP · added to your cash</div>
        </div>
        <div className="text-5xl">🎁</div>
      </div>
    );
  }

  if (!s.can_claim) {
    return (
      <div className="rounded-2xl border border-line bg-card px-6 py-4 flex items-center justify-between text-sm">
        <span className="text-ink-soft">
          Daily pack claimed · <span className="num">{s.streak}</span>-day streak 🔥
        </span>
        <span className="text-ink-faint">Come back tomorrow for more</span>
      </div>
    );
  }

  return (
    <button
      onClick={() => claim.mutate()}
      disabled={claim.isPending}
      className="w-full rounded-2xl bg-accent/20 border border-accent/50 px-6 py-4 flex items-center justify-between hover:bg-accent/30 transition disabled:opacity-50"
    >
      <div className="text-left">
        <div className="font-semibold flex items-center gap-2">
          <span className="text-xl">🎁</span> Claim your daily pack
        </div>
        <div className="text-xs text-ink-soft mt-0.5">
          {s.streak > 0 ? `Day ${s.streak + 1} · ` : ""}~{money(s.next_reward_estimate)} in cash to invest
        </div>
      </div>
      <span className="rounded-xl bg-ink text-cream px-4 py-2 text-sm font-medium">
        {claim.isPending ? "…" : "Open"}
      </span>
    </button>
  );
}
