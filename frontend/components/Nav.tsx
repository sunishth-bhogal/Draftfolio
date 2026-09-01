"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getToken, clearToken } from "@/lib/auth";

export function Nav() {
  // Read the token after mount so SSR and first client render match (no hydration mismatch).
  const [hasToken, setHasToken] = useState(false);
  useEffect(() => setHasToken(!!getToken()), []);
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.me(), enabled: hasToken, retry: false });
  const u = me.data;

  function logout() {
    clearToken();
    window.location.href = "/";
  }

  return (
    <div className="mx-auto max-w-6xl px-6 h-16 flex items-center justify-between">
      <Link href="/" className="flex items-center gap-2">
        <span className="inline-block h-3 w-3 rounded-full bg-accent" />
        <span className="font-semibold tracking-tight text-lg">Draftfolio</span>
      </Link>

      <nav className="flex items-center gap-5 text-sm text-ink-soft">
        <Link href="/" className="hover:text-ink transition-colors">Portfolio</Link>
        <Link href="/markets" className="hover:text-ink transition-colors">Markets</Link>
        <Link href="/packs" className="hover:text-ink transition-colors">Packs</Link>
        <Link href="/explore" className="hover:text-ink transition-colors">Explore</Link>
        <Link href="/rivals" className="hover:text-ink transition-colors">Rivals</Link>
        <Link href="/leaderboard" className="hover:text-ink transition-colors hidden sm:inline">Leaderboard</Link>

        {u ? (
          <div className="flex items-center gap-3">
            <Link href="/rivals" className="flex items-center gap-2 rounded-full border border-line bg-card px-3 py-1.5">
              <span className="font-medium text-ink">{u.username}</span>
              <span className="text-xs text-ink-faint num">Lv {u.level}</span>
              <span className="text-xs rounded-full bg-accent/30 text-accent-deep px-2 py-0.5">{u.division}</span>
            </Link>
            <button onClick={logout} className="text-xs text-ink-faint hover:text-ink">Log out</button>
          </div>
        ) : (
          <Link href="/login" className="rounded-xl bg-ink text-cream px-4 py-2 font-medium hover:opacity-90">
            Log in
          </Link>
        )}
      </nav>
    </div>
  );
}
