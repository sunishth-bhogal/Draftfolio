"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getToken, clearToken } from "@/lib/auth";

/* Minimal stroke icons (inherit currentColor). */
function Icon({ path, fill = false }: { path: string; fill?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-5 w-5"
      fill={fill ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={path} />
    </svg>
  );
}

const ICONS: Record<string, string> = {
  home: "M3 11.5 12 4l9 7.5M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9",
  markets: "M4 19V5M4 19h16M8 15l3-4 3 3 4-6",
  packs: "M20 8H4v11a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8ZM3 5h18v3H3zM12 8v12M12 5c-1.5-2.5-5-2-5 0 0 1.2 2.5 1.2 5 0Zm0 0c1.5-2.5 5-2 5 0 0 1.2-2.5 1.2-5 0Z",
  explore: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18ZM15.5 8.5l-2 5-5 2 2-5 5-2Z",
  rivals: "M8 21v-2a4 4 0 0 1 4-4 4 4 0 0 1 4 4v2M12 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7ZM3 21v-1.5a3 3 0 0 1 3-3M21 21v-1.5a3 3 0 0 0-3-3",
  leaderboard: "M8 21h8M12 17v4M6 4h12v4a6 6 0 0 1-12 0V4ZM6 6H4v1a3 3 0 0 0 2 2.8M18 6h2v1a3 3 0 0 1-2 2.8",
};

const LINKS = [
  { href: "/", label: "Home", icon: "home", match: (p: string) => p === "/" },
  { href: "/markets", label: "Markets", icon: "markets", match: (p: string) => p.startsWith("/markets") },
  { href: "/packs", label: "Packs", icon: "packs", match: (p: string) => p.startsWith("/packs") },
  { href: "/explore", label: "Explore", icon: "explore", match: (p: string) => p.startsWith("/explore") },
  { href: "/rivals", label: "Rivals", icon: "rivals", match: (p: string) => p.startsWith("/rivals") },
  { href: "/leaderboard", label: "Ranks", icon: "leaderboard", match: (p: string) => p.startsWith("/leaderboard") },
];

export function Nav() {
  const pathname = usePathname();
  const [hasToken, setHasToken] = useState(false);
  useEffect(() => setHasToken(!!getToken()), []);
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.me(), enabled: hasToken, retry: false });
  const u = me.data;

  function logout() {
    clearToken();
    window.location.href = "/";
  }

  return (
    <nav className="fixed left-0 top-0 z-20 flex h-screen w-[74px] flex-col items-center gap-1 border-r border-line bg-card/60 px-2 py-4 backdrop-blur">
      {/* Brand mark */}
      <Link href="/" className="mb-4 flex h-11 w-11 items-center justify-center" aria-label="Draftfolio home">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent font-bold text-[#0a0b0d]">
          D
        </span>
      </Link>

      {LINKS.map((l) => {
        const active = l.match(pathname);
        return (
          <Link
            key={l.href}
            href={l.href}
            title={l.label}
            className={`group flex w-full flex-col items-center gap-1 rounded-xl py-2 transition-colors ${
              active ? "bg-elevated text-accent" : "text-ink-faint hover:bg-elevated/60 hover:text-ink"
            }`}
          >
            <Icon path={ICONS[l.icon]} />
            <span className="text-[10px] font-medium">{l.label}</span>
          </Link>
        );
      })}

      <div className="mt-auto flex flex-col items-center gap-2 pt-4">
        {u ? (
          <>
            <Link
              href="/rivals"
              title={`${u.username} · Lv ${u.level} · ${u.division}`}
              className="flex h-10 w-10 items-center justify-center rounded-full border border-line bg-elevated font-semibold text-accent hover:border-accent"
            >
              {u.username.slice(0, 1).toUpperCase()}
            </Link>
            <button
              onClick={logout}
              title="Log out"
              className="text-ink-faint transition-colors hover:text-down"
              aria-label="Log out"
            >
              <Icon path="M15 3h4a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1h-4M10 17l5-5-5-5M15 12H3" />
            </button>
          </>
        ) : (
          <Link
            href="/login"
            title="Log in"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-accent text-[#0a0b0d] hover:opacity-90"
            aria-label="Log in"
          >
            <Icon path="M10 17l5-5-5-5M15 12H3M4 4h8a1 1 0 0 1 1 1v0M13 19v0a1 1 0 0 1-1 1H4" />
          </Link>
        )}
      </div>
    </nav>
  );
}
