export type Portfolio = {
  id: string;
  name: string;
  base_currency: string;
};

export type Instrument = {
  id: string;
  symbol: string;
  name: string;
  currency: string;
  sector: string | null;
  last_price: number | null;
  asset_class: string;
  sport: string | null;
  team: string | null;
  position: string | null;
  headshot_url: string | null;
};

export type Holding = {
  instrument_id: string;
  symbol: string;
  name: string;
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

export type Signal = {
  source: string;
  signal_type: string;
  value: number;
  confidence: number;
  headline: string;
  source_url: string | null;
};

export type Driver = {
  symbol: string;
  dollar_pnl: number;
  contribution: number;
  price_change: number;
  signals: Signal[];
};

export type Explanation = {
  available: boolean;
  reason: string | null;
  as_of_date: string | null;
  prev_date: string | null;
  portfolio_return: number | null;
  prev_equity: number | null;
  latest_equity: number | null;
  note: string | null;
  drivers: Driver[];
};

export type PricePoint = {
  date: string;
  close: number;
  formula_version: string | null;
};

export type Breakdown = {
  available: boolean;
  games: number;
  formula_version: string | null;
  as_of: string | null;
  averages: Record<string, number>;
  components: Record<string, number>;
  base_value: number;
  form_multiplier: number;
  form_adjustment: number;
  observed_value: number;
  prior_value: number;
  prior_basis: string | null;
  reliability: number;
  final_value: number;
};

export type ValidationRow = {
  name: string;
  value: number;
  ppg: number;
  production: number;
  games: number;
};

export type PositionRow = {
  position: string;
  n: number;
  avg_value: number;
  avg_production: number;
};

export type Validation = {
  num_players: number;
  min_games: number;
  pearson_value_production: number | null;
  spearman_value_production: number | null;
  pearson_value_minutes: number | null;
  spearman_value_minutes: number | null;
  predictive_n: number;
  predictive_pearson: number | null;
  predictive_spearman: number | null;
  top: ValidationRow[];
  watchouts: ValidationRow[];
  by_position: PositionRow[];
};

export type CatalystItem = {
  kind: string;
  direction: string;
  label: string;
  detail: string;
};

export type Catalysts = {
  available: boolean;
  as_of: string | null;
  price_change: number | null;
  summary: string;
  items: CatalystItem[];
};

export type Constituent = {
  symbol: string;
  name: string;
  member_id: string;
  value: number | null;
  weight_pct: number;
};

export type Composition = {
  available: boolean;
  count: number;
  constituents: Constituent[];
};
