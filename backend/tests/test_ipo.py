"""Timed IPO listing tests."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.models import Instrument
from app.services.ipo import list_ipos, process_listings, seed_ipos
from app.services.valuation import latest_close


def test_nothing_lists_before_the_date(db_session):
    seed_ipos(db_session)
    assert process_listings(db_session, today=date(2026, 1, 1)) == 0
    ipos = list_ipos(db_session, today=date(2026, 1, 1))
    assert all(i.status == "upcoming" for i in ipos)


def test_ipo_lists_on_its_date_as_tradeable(db_session):
    seed_ipos(db_session)
    # Past the Aug 1 debut of Ace Bailey / Ivan Demidov, before the Oct openers.
    listed = process_listings(db_session, today=date(2026, 9, 1))
    assert listed == 2

    by_name = {i.name: i for i in list_ipos(db_session, today=date(2026, 9, 1))}
    ace = by_name["Ace Bailey"]
    assert ace.status == "listed" and ace.instrument_id
    assert by_name["Gavin McKenna"].status == "upcoming"  # future date

    # A real tradeable PLAYER instrument was created at the IPO price.
    inst = db_session.get(Instrument, uuid.UUID(ace.instrument_id))
    assert inst.asset_class == "PLAYER" and inst.sport == "NBA"
    price = latest_close(db_session, inst.id, datetime.now(timezone.utc))
    assert float(price) == 360


def test_listing_is_idempotent(db_session):
    seed_ipos(db_session)
    process_listings(db_session, today=date(2026, 9, 1))
    again = process_listings(db_session, today=date(2026, 9, 1))
    assert again == 0
    # exactly one instrument per listed IPO
    n = db_session.scalar(select(Instrument).where(Instrument.symbol == "IPO:ace-bailey"))
    assert n is not None


def test_all_list_once_season_opens(db_session):
    seed_ipos(db_session)
    process_listings(db_session, today=date(2026, 11, 1))  # after every date
    ipos = list_ipos(db_session, today=date(2026, 11, 1))
    assert all(i.status == "listed" and i.instrument_id for i in ipos)
