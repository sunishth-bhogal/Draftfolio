export type Portfolio = {
  id: string;
  name: string;
  base_currency: string;
};

export type Holding = {
  symbol: string;
  quantity: number;
  price: number;
  market_value: number;
  weight: number;
};

export type Valuation = {
  as_of: string;
  base_currency: string;
  cash: number;
  market_value: number;
  equity: number;
  holdings: Holding[];
  fx_pending: string[];
  unpriced: string[];
};

export type ReturnPoint = {
  snapshot_date: string;
  equity: number;
  daily_return: number | null;
  cumulative_return: number | null;
};

export type Analytics = {
  periods: number;
  cumulative_return: number | null;
  annualized_return: number | null;
  annualized_volatility: number | null;
  sharpe: number | null;
  sortino: number | null;
  max_drawdown: number | null;
  benchmark: string | null;
  benchmark_return: number | null;
  beta: number | null;
  alpha: number | null;
  tracking_error: number | null;
  hhi: number | null;
  effective_holdings: number | null;
  notes: string[];
};

export type LeaderboardRow = {
  portfolio_id: string;
  name: string;
  rank: number;
  score: number;
  percentiles: Record<"R" | "B" | "D" | "C", number>;
  cumulative_return: number | null;
  benchmark_return: number | null;
  max_drawdown: number | null;
  effective_holdings: number | null;
  notes: string[];
};

export type Leaderboard = {
  mode: string;
  weights: Record<"R" | "B" | "D" | "C", number>;
  benchmark: string | null;
  rows: LeaderboardRow[];
};

export type ScoreMode = "SPRINT" | "BALANCED" | "INVESTOR";
