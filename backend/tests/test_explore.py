"""Explore / discovery tests."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models import Instrument, Position
from app.services import bootstrap
from app.services.explore import explore, popular, trending


def _player(db, symbol, name, sport="NBA"):
    i = Instrument(symbol=symbol, name=name, currency="CAD", asset_class="PLAYER", sport=sport, team="T")
    db.add(i)
    db.commit()
    return i


def _bars(db, inst, closes):
    base = date(2026, 1, 1)
    for k, c in enumerate(closes):
        db.add_all([])
        from app.models import PriceBar

        db.add(
            PriceBar(
                instrument_id=inst.id, bar_date=base + timedelta(days=k), close=Decimal(str(c)),
                currency="CAD", source="espn",
                as_of=datetime.combine(base + timedelta(days=k), datetime.min.time(), tzinfo=timezone.utc),
            )
        )
    db.commit()


def test_trending_ranks_risers_and_filters_scrubs(db_session):
    riser = _player(db_session, "NBA:R", "Rising Star")
    _bars(db_session, riser, [300, 320, 360, 400, 450, 500])  # big riser, high value
    scrub = _player(db_session, "NBA:S", "Deep Bench")
    _bars(db_session, scrub, [5, 6, 8, 10, 20, 40])  # huge % but tiny value -> filtered

    rows = trending(db_session)
    names = [m.name for m in rows]
    assert "Rising Star" in names
    assert "Deep Bench" not in names  # below MIN_TREND_PRICE
    assert rows[0].change > 0


def test_popular_counts_holders(db_session):
    user = bootstrap.create_user(db_session, email="a@b.io", display_name="a")
    star = _player(db_session, "NBA:P", "Popular Guy")
    _bars(db_session, star, [400, 410])
    # two portfolios hold the star
    for n in range(2):
        pf = bootstrap.create_portfolio(db_session, user_id=user.id, name=f"pf{n}")
        db_session.add(Position(portfolio_id=pf.id, instrument_id=star.id, quantity=Decimal("10")))
    db_session.commit()

    rows = popular(db_session)
    assert rows[0].name == "Popular Guy"
    assert rows[0].holders == 2


def test_explore_includes_ipos(db_session):
    e = explore(db_session)
    assert len(e.ipos) >= 4
    assert any("McKenna" in i.name for i in e.ipos)
