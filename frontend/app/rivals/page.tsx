"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { Card, Bar } from "@/components/ui";

export default function RivalsPage() {
  const [hasToken, setHasToken] = useState(false);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setHasToken(!!getToken());
    setReady(true);
  }, []);
  const me = useQuery({ queryKey: ["me"], queryFn: () => api.me(), enabled: hasToken, retry: false });
  const rivals = useQuery({ queryKey: ["rivals"], queryFn: () => api.rivals(), enabled: hasToken, retry: false });

  if (ready && !hasToken) {
    return (
      <Card>
        <p className="text-ink-soft">
          <Link href="/login" className="text-accent-deep underline underline-offset-4">Log in</Link> to
          join a division and climb the ladder.
        </p>
      </Card>
    );
  }

  const u = me.data;
  const r = rivals.data;

  return (
    <div className="space-y-8">
      {u && (
        <section className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">{u.username}</h1>
            <div className="text-ink-soft text-sm">
              <span className="rounded-full bg-accent/30 text-accent-deep px-2 py-0.5">{u.division}</span>{" "}
              Division · {u.division_points} pts
            </div>
          </div>
          <div className="w-56">
            <div className="flex justify-between text-xs text-ink-faint mb-1">
              <span>Level {u.level}</span>
              <span className="num">{u.xp_into_level}/{u.xp_per_level} XP</span>
            </div>
            <Bar value={u.xp_into_level / u.xp_per_level} />
          </div>
        </section>
      )}

      {/* Division ladder */}
      {r && (
        <div className="flex items-center gap-1 text-xs">
          {r.divisions.map((d) => (
            <span
              key={d}
              className={`rounded-full px-3 py-1 border ${
                d === u?.division ? "bg-ink text-cream border-ink" : "border-line text-ink-faint"
              }`}
            >
              {d}
            </span>
          ))}
        </div>
      )}

      <section>
        <div className="flex items-baseline justify-between mb-3">
          <h2 className="font-semibold">{r?.division} standings</h2>
          {r && (
            <span className="text-xs text-ink-faint">
              promote at {r.promote_at} pts · relegate at {r.relegate_at}
            </span>
          )}
        </div>
        {r && (
          <div className="rounded-2xl border border-line bg-card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-ink-faint border-b border-line">
                  <th className="px-5 py-3 font-medium">#</th>
                  <th className="px-5 py-3 font-medium">Manager</th>
                  <th className="px-5 py-3 font-medium text-right">Level</th>
                  <th className="px-5 py-3 font-medium text-right">XP</th>
                  <th className="px-5 py-3 font-medium text-right">Points</th>
                </tr>
              </thead>
              <tbody>
                {r.standings.map((s, i) => {
                  const zone =
                    s.division_points >= r.promote_at
                      ? "border-l-2 border-l-up"
                      : s.division_points <= r.relegate_at
                        ? "border-l-2 border-l-down"
                        : "";
                  return (
                    <tr
                      key={s.username}
                      className={`border-b border-line last:border-0 ${zone} ${s.is_me ? "bg-accent/10" : ""}`}
                    >
                      <td className="px-5 py-3 num text-ink-faint">{i + 1}</td>
                      <td className="px-5 py-3 font-medium">
                        {s.username} {s.is_me && <span className="text-xs text-accent-deep">· you</span>}
                      </td>
                      <td className="px-5 py-3 text-right num text-ink-soft">{s.level}</td>
                      <td className="px-5 py-3 text-right num text-ink-soft">{s.xp}</td>
                      <td className="px-5 py-3 text-right num font-medium">{s.division_points}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        <p className="text-xs text-ink-faint mt-3">
          Each gameweek your team&apos;s return is ranked against your division. Win to earn points and
          XP; reach {r?.promote_at ?? 10} points to promote.
        </p>
      </section>
    </div>
  );
}
