"""Pure scoring tests — the thesis in a unit test: mode changes the winner."""

from __future__ import annotations

from app.domain.scoring import Components, ScoreMode, percentile_ranks, score_cohort


def approx(a, b, tol=1e-4):
    return abs(a - b) < tol


def test_percentile_ranks_basic():
    pr = percentile_ranks([10, 20, 30])
    assert approx(pr[0], 1 / 6) and approx(pr[1], 0.5) and approx(pr[2], 5 / 6)


def test_percentile_ranks_ties_and_singleton():
    assert percentile_ranks([10, 10]) == [0.5, 0.5]  # tie -> shared rank
    assert percentile_ranks([42]) == [0.5]  # lone portfolio -> neutral


def test_mode_changes_the_winner():
    """A gambler tops Sprint; a risk-aware all-rounder tops Investor."""
    gambler = Components(R=0.30, B=0.15, D=-0.40, C=1.0)  # big return, big drawdown, concentrated
    allrounder = Components(R=0.12, B=0.03, D=-0.03, C=6.0)  # modest return, best risk + diversification
    laggard = Components(R=0.05, B=-0.02, D=-0.10, C=3.0)
    cohort = [gambler, allrounder, laggard]

    sprint = score_cohort(cohort, ScoreMode.SPRINT)
    investor = score_cohort(cohort, ScoreMode.INVESTOR)

    sprint_winner = max(range(3), key=lambda i: sprint[i].score)
    investor_winner = max(range(3), key=lambda i: investor[i].score)

    assert sprint_winner == 0  # gambler wins the return-heavy mode
    assert investor_winner == 1  # all-rounder wins the risk-aware mode
    # And the gambler is demoted under Investor.
    assert investor[0].score < investor[1].score


def test_scores_are_scaled_0_to_100():
    cohort = [Components(0.1, 0.0, -0.1, 2.0), Components(0.2, 0.05, -0.05, 3.0)]
    for s in score_cohort(cohort, ScoreMode.BALANCED):
        assert 0.0 <= s.score <= 100.0
        assert set(s.percentiles) == {"R", "B", "D", "C"}
