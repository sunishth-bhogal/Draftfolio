import type {
  Analytics,
  Leaderboard,
  Portfolio,
  ReturnPoint,
  ScoreMode,
  Valuation,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json() as Promise<T>;
}

export const api = {
  portfolios: () => get<Portfolio[]>("/portfolios"),
  valuation: (id: string) => get<Valuation>(`/portfolios/${id}/valuation`),
  returns: (id: string) => get<ReturnPoint[]>(`/portfolios/${id}/returns`),
  analytics: (id: string, benchmark = "XEQT", rf = 0.04) =>
    get<Analytics>(`/portfolios/${id}/analytics?benchmark=${benchmark}&rf=${rf}`),
  leaderboard: (mode: ScoreMode = "BALANCED", benchmark = "XEQT", rf = 0.04) =>
    get<Leaderboard>(`/leaderboard?mode=${mode}&benchmark=${benchmark}&rf=${rf}`),
};

export const BASE_URL = BASE;
