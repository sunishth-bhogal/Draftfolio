"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { money2 } from "@/lib/format";
import { Card } from "@/components/ui";

export function Composition({ instrumentId }: { instrumentId: string }) {
  const { data } = useQuery({
    queryKey: ["composition", instrumentId],
    queryFn: () => api.composition(instrumentId),
  });
  if (!data || !data.available) return null;

  return (
    <Card>
      <div className="flex items-baseline justify-between mb-4">
        <h2 className="font-semibold">Holdings</h2>
        <span className="text-xs text-ink-faint num">{data.count} players · equal weight</span>
      </div>
      <table className="w-full text-sm">
        <tbody>
          {data.constituents.map((c) => (
            <tr key={c.member_id} className="border-b border-line last:border-0">
              <td className="py-2">
                <Link href={`/player/${c.member_id}`} className="font-medium hover:text-accent-deep">
                  {c.name}
                </Link>
              </td>
              <td className="py-2 text-right num text-ink-soft">{c.weight_pct}%</td>
              <td className="py-2 text-right num">{c.value != null ? money2(c.value) : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-ink-faint mt-3">
        An index fund of players — its price is the weighted basket of these values, so it moves
        with the group and diversifies single-player risk.
      </p>
    </Card>
  );
}
