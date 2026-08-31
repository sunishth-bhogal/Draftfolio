"""Daily pack economy tests."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services import bootstrap, daily
from app.services.daily import AlreadyClaimed, claim, reward_for_streak, status


def _user_with_team(db):
    u = bootstrap.create_user(db, email="p@x.io", display_name="p")
    pf = bootstrap.create_portfolio(db, user_id=u.id, name="p team")
    bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal("0"), currency="CAD")
    return u


def test_reward_always_in_range():
    for s in range(1, 30):
        r = reward_for_streak(s)
        assert 100 <= r <= 1000 and r % 10 == 0


def test_first_claim_is_welcome_pack(db_session):
    u = _user_with_team(db_session)
    res = claim(db_session, u, today=date(2026, 1, 10))
    assert res.is_welcome and res.reward == 1000
    assert res.streak == 1
    assert res.new_cash == 1000.0  # credited to the team


def test_cannot_claim_twice_same_day(db_session):
    u = _user_with_team(db_session)
    claim(db_session, u, today=date(2026, 1, 10))
    with pytest.raises(AlreadyClaimed):
        claim(db_session, u, today=date(2026, 1, 10))


def test_streak_increments_on_consecutive_days(db_session):
    u = _user_with_team(db_session)
    claim(db_session, u, today=date(2026, 1, 10))
    r2 = claim(db_session, u, today=date(2026, 1, 11))
    r3 = claim(db_session, u, today=date(2026, 1, 12))
    assert r2.streak == 2 and r3.streak == 3


def test_streak_resets_after_missed_day(db_session):
    u = _user_with_team(db_session)
    claim(db_session, u, today=date(2026, 1, 10))
    claim(db_session, u, today=date(2026, 1, 11))
    missed = claim(db_session, u, today=date(2026, 1, 20))  # gap
    assert missed.streak == 1


def test_status_reflects_claim(db_session):
    u = _user_with_team(db_session)
    assert status(db_session, u, today=date(2026, 1, 10)).can_claim is True
    claim(db_session, u, today=date(2026, 1, 10))
    assert status(db_session, u, today=date(2026, 1, 10)).can_claim is False
