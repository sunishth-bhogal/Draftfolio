"""Season lifecycle: state, and end-of-season finalize (rewards + reset)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from app.models import CashBalance, Season, SeasonResult, User
from app.services import auth as auth_svc
from app.services import bootstrap
from app.services.season import (
    DIVISION_REWARD,
    end_season,
    get_or_create_active_season,
    season_state,
)


def _rival(db, username, division, points=0, xp=0):
    u = User(email=f"{username}@r.io", display_name=username, username=username,
             password_hash=auth_svc.hash_password("password"), division=division,
             division_points=points, xp=xp)
    db.add(u)
    db.commit()
    pf = bootstrap.create_portfolio(db, user_id=u.id, name=f"{username} team")
    bootstrap.fund_portfolio(db, portfolio_id=pf.id, amount=Decimal("0"), currency="CAD")
    return u, pf


def test_active_season_is_created(db_session):
    s = get_or_create_active_season(db_session)
    assert s.name == "2025-26" and s.status == "active"
    # idempotent
    assert get_or_create_active_season(db_session).id == s.id


def test_season_state_reports_your_placement(db_session):
    u, _ = _rival(db_session, "me", "Silver", points=5)
    _rival(db_session, "rival", "Silver", points=8)
    st = season_state(db_session, u)
    assert st.name == "2025-26" and st.status == "active"
    assert st.your_division == "Silver"
    assert st.your_rank == 2  # the 8-point rival ranks ahead


def test_end_season_rewards_records_and_resets(db_session):
    gold, gpf = _rival(db_session, "champ", "Gold", points=6, xp=800)
    bronze, _ = _rival(db_session, "rookie", "Bronze", points=1, xp=100)
    season = get_or_create_active_season(db_session)

    fin = end_season(db_session)
    assert fin.finalized == 2

    # Results recorded with the finishing divisions.
    results = {
        r.final_division: r
        for r in db_session.scalars(select(SeasonResult).where(SeasonResult.season_id == season.id))
    }
    assert "Gold" in results and "Bronze" in results
    assert results["Gold"].reward_xp == DIVISION_REWARD["Gold"][0]

    # Rewards paid: XP added, cash added to the team.
    db_session.refresh(gold)
    assert gold.xp == 800 + DIVISION_REWARD["Gold"][0]
    cb = db_session.get(CashBalance, {"portfolio_id": gpf.id, "currency": "CAD"})
    assert float(cb.amount) == DIVISION_REWARD["Gold"][1]

    # Ladder reset for the new season; net worth untouched (still one portfolio).
    db_session.refresh(gold)
    db_session.refresh(bronze)
    assert gold.division == "Bronze" and gold.division_points == 0
    assert bronze.division == "Bronze"

    # Old season ended, a new active season opened.
    assert db_session.get(Season, season.id).status == "ended"
    active = db_session.scalar(select(Season).where(Season.status == "active"))
    assert active is not None and active.name == "2026-27"
