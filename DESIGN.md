# Draftfolio — Design

Risk-aware fantasy investing. Users draft virtual stock/ETF portfolios under a
salary cap and compete on **risk-adjusted** performance, not raw return. This
document is the spine: what the system guarantees, and why it's built this way.

The guiding principle: **one system built to production depth beats a broad
demo.** The depth here is the ledger — a virtual brokerage you genuinely cannot
lose or invent money in.

## The spine (what we build first)

```
users ─▶ portfolios ─▶ orders ─▶ transactions ─▶ positions ─▶ snapshots
                        (request)  (append-only)   (derived)    (history)
```

Everything else in the original concept — leagues, drafts, market replay,
sentiment/prediction-market signals — is a layer on top of this and is deferred
until the spine is solid.

## Money invariants (enforced + tested)

These are asserted by property-based tests in
`backend/tests/test_ledger_invariants.py` against thousands of generated trade
sequences:

| Invariant | Meaning |
| --- | --- |
| `cash + market value = equity` | The core accounting identity always holds. |
| Buy-then-sell at one price costs only fees | Trading cannot create money. |
| `replay(log) == live state` | State is reconstructable from the append-only log. |
| Re-applying an order id is a no-op | Client retries never double-spend. |
| Cash cannot go negative | You cannot spend virtual money you don't have. |
| No shorting (v1) | You cannot sell more shares than you hold. |

## The four-table decision (the interview centerpiece)

The most important design choice is separating what would naively be one
"holdings" table into four:

- **`orders`** — what the user *requested*. Immutable.
- **`transactions`** — what the system *executed*. **Append-only ledger**; a
  completed trade is never edited or deleted.
- **`positions`** — current *derived* state, a cache of the folded log.
- **`portfolio_snapshots`** — historical calculated state for charts/scoring.

Because `positions` is derived, it can always be rebuilt from `transactions`
(`replay()`), and a scheduled **reconciliation job** asserts the two agree — if
they ever diverge, that's a caught bug, not silent corruption.

## Architecture Decision Records

### ADR-001: Money is `Decimal`, never `float`
`0.1 + 0.2 != 0.3` in binary floating point. In a ledger that rounding error is
money appearing or vanishing. All amounts are `Decimal` quantized to cents via a
`Money` value object that also forbids cross-currency arithmetic (a CAD balance
can never silently absorb USD). See `app/domain/money.py`.

### ADR-002: Orders and transactions are separate, append-only tables
Requests and executions have different lifecycles and can diverge (rejected,
partially filled, retried). Keeping executions append-only gives an auditable
history and makes reconciliation possible. We never `UPDATE` a completed trade.

### ADR-003: Idempotent order processing via idempotency key
`POST /orders` carries an `Idempotency-Key`. A retried request (network blip,
double-click) creates at most one transaction. Enforced in the domain today
(processed-order set) and at the DB layer via a unique constraint later.

### ADR-004: No WebSockets in v1
The leaderboard is a cached DB query refreshed on price updates, not a real-time
socket fan-out. Real-time is a Phase-4 stretch; adding it early is complexity
that doesn't strengthen the core thesis.

### ADR-005: Pure domain layer, thin infrastructure
The money/ledger logic in `app/domain/` has no database or framework imports, so
it can be tested exhaustively without infra. SQLAlchemy and FastAPI are shells
that call into it. This is why the invariants can be proven before Postgres is
even running.

## Signals layer (later, read-only)

Non-price signals — news, prediction-market odds (Polymarket/Kalshi), optional
social sentiment — never touch the ledger write path. They flatten into one
`signal_events` table (`ts, source, instrument, signal_type, value, confidence,
source_url`) and feed a **deterministic** "why did my portfolio move?" explainer:
rank holdings by contribution, left-join signals in the same window, label every
one *correlation, not causation* with a source link. No LLM guessing.

## Stack

- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Pydantic, Redis (cache).
- **Testing:** pytest + Hypothesis (property-based on financial invariants).
- **Frontend (later):** Next.js, TypeScript, Tailwind, TanStack Query.
- **Infra:** Docker Compose (Postgres + Redis) locally.

## Build phases

1. **Foundation** — ledger core ✅ (domain + invariants), persistence, one
   idempotent order endpoint, EOD prices, basic return.
2. **League experience** — create/join leagues, draft flow, standings, snapshots.
3. **Analytics** — benchmarks, drawdown, volatility, attribution, diversification.
4. **Production** — workers, Redis caching, rate limiting, observability, load test.
5. **Differentiator** — "why did my portfolio move?" with the signals layer.
