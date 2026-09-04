"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getToken, clearToken } from "@/lib/auth";

/* Minimal stroke icons (inherit currentColor). */
const icons: Record<string, React.ReactNode> = {
  home: <path d="M3 10.5 12 3l9 7.5M5.5 9.5V20h13V9.5" />,
  markets: <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />,
  packs: <path d="M3 8h18v12H3zM3 8l2.5-4h13L21 8M12 4v16M3 12h18" />,
  explore: <path d="M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM15.5 8.5l-2 5-5 2 2-5 5-2z" />,
  rivals: <path d="M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM2 20a6 6 0 0 1 12 0M17 11l4 4M21 11l-4 4M16 20a5 5 0 0 1 6 0" />,
  leaderboard: <path d="M8 21h8M12 17v4M6 4h12v5a6 6 0 0 1-12 0V4zM6 6H3v2a3 3 0 0 0 3 3M18 6h3v2a3 3 0 0 1-3 3" />,
};

function Glyph({ name }: { name: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round" className="h-5 w-5">
      {icons[name]}
    </svg>
  );
}

const links = [
  { href: "/", label: "Home", icon: "home", match: (p: string) => p === "/" },
  { href: "/markets", label: "Markets", icon: "markets", match: (p: string) => p.startsWith("/markets") || p.startsWith("/player") },
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
    <aside className="fixed inset-y-0 left-0 z-20 flex w-[74px] flex-col items-center border-r border-line bg-cream/95 backdrop-blur py-4">
      {/* Brand mark */}
      <Link href="/" className="group mb-3 flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-[#0a0b0d]">
        <span className="text-lg font-bold tracking-tight">D</span>
      </Link>

      {/* Nav rail */}
      <nav className="flex flex-1 flex-col items-center gap-1">
        {links.map((l) => {
          const active = l.match(pathname);
          return (
            <Link
              key={l.href}
              href={l.href}
              title={l.label}
              className={`flex w-[62px] flex-col items-center gap-1 rounded-xl py-2.5 transition-colors ${
                active ? "bg-elevated text-accent" : "text-ink-faint hover:text-ink hover:bg-elevated/60"
              }`}
            >
              <Glyph name={l.icon} />
              <span className="text-[10px] font-medium leading-none">{l.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Account */}
      <div className="mt-3 flex flex-col items-center gap-2">
        {u ? (
          <>
            <Link
              href="/rivals"
              title={`${u.username} · Lv ${u.level} · ${u.division}`}
              className="flex h-10 w-10 items-center justify-center rounded-full bg-elevated text-sm font-semibold uppercase text-accent ring-1 ring-line"
            >
              {u.username.slice(0, 1)}
            </Link>
            <button onClick={logout} title="Log out" className="text-[10px] text-ink-faint hover:text-ink">
              Exit
            </button>
          </>
        ) : (
          <Link
            href="/login"
            title="Log in"
            className="flex h-10 w-10 items-center justify-center rounded-full bg-ink text-cream text-lg font-semibold hover:opacity-90"
          >
            +
          </Link>
        )}
      </div>
    </aside>
  );
}
