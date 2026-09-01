import { getToken } from "./auth";
import type {
  Analytics,
  Explanation,
  Instrument,
  Breakdown,
  Catalysts,
  Composition,
  Leaderboard,
  ClaimResult,
  DailyStatus,
  Explore,
  Me,
  Portfolio,
  PricePoint,
  Rivals,
  Validation,
  ReturnPoint,
  ScoreMode,
  Valuation,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store", headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText} for ${path}`);
  return res.json() as Promise<T>;
}

async function post<T>(
  path: string,
  body: unknown,
  headers: Record<string, string> = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders(), ...headers },
    body: JSON.stringify(body),
  });
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
  explain: (id: string) => get<Explanation>(`/portfolios/${id}/explain`),
  instruments: () => get<Instrument[]>("/instruments"),
  history: (id: string) => get<PricePoint[]>(`/instruments/${id}/history`),
  breakdown: (id: string) => get<Breakdown>(`/instruments/${id}/breakdown`),
  catalysts: (id: string) => get<Catalysts>(`/instruments/${id}/catalysts`),
  composition: (id: string) => get<Composition>(`/instruments/${id}/composition`),
  signup: (email: string, username: string, password: string) =>
    post<{ token: string; user: Me }>("/auth/signup", { email, username, password }),
  login: (login: string, password: string) =>
    post<{ token: string; user: Me }>("/auth/login", { login, password }),
  me: () => get<Me>("/me"),
  rivals: () => get<Rivals>("/rivals"),
  explore: () => get<Explore>("/explore"),
  dailyStatus: () => get<DailyStatus>("/daily/status"),
  claimDaily: () => post<ClaimResult>("/daily/claim", {}),
  validation: () => get<Validation>("/methodology/validation"),
  createPortfolio: (name: string, starting_cash = 100000) =>
    post<Portfolio>("/portfolios", { name, starting_cash }),
  placeOrder: (
    portfolioId: string,
    pick: { symbol: string; quantity: number; price: number },
    idempotencyKey: string,
  ) =>
    post(`/portfolios/${portfolioId}/orders`, { side: "BUY", ...pick, fee: 0 }, {
      "Idempotency-Key": idempotencyKey,
    }),
};

export const BASE_URL = BASE;
