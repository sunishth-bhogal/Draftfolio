"""ESPN NBA data provider (keyless hidden API).

Fetches teams, rosters, and per-game season averages, and parses them into the
domain ``PlayerStats`` the valuation model consumes. This is the real-data feed
behind the player market; it is isolated here so the rest of the app depends only
on plain dataclasses, and a different source could be swapped in.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date, datetime

from curl_cffi import requests as _requests

from app.domain.player_value import PlayerStats

SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"

# A marquee subset of team ids for a fast default seed; pass all 30 to go full.
MARQUEE_TEAMS = [13, 9, 2, 7, 15, 18, 25, 6]  # LAL, GSW, BOS, DEN, MIL, NYK, DAL, MIA


class ProviderError(RuntimeError):
    """ESPN was unreachable after retries — callers should degrade gracefully."""


@dataclass
class PlayerMeta:
    espn_id: str
    name: str
    team: str
    position: str | None
    headshot_url: str | None
    injured: bool
    injury_status: str | None = None  # e.g. "Out", "Day-To-Day"


@dataclass
class GameObs:
    espn_event_id: str
    game_date: date
    opponent: str | None
    home: bool
    minutes: float
    points: float
    rebounds: float
    assists: float
    steals: float
    blocks: float
    turnovers: float


def _get(url: str, timeout: int = 15, retries: int = 3) -> dict:
    """GET with retry + exponential backoff.

    ESPN's hidden API sits behind Akamai, which blocks stock Python TLS
    fingerprints; curl_cffi impersonates a real browser handshake. This
    integration is intentionally isolated and treated as best-effort — callers
    handle ``ProviderError`` and fall back to last-known data.
    """
    last: Exception | None = None
    for attempt in range(retries):
        try:
            resp = _requests.get(url, impersonate="chrome", timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.5 * (2**attempt))  # 0.5s, 1s, 2s
    raise ProviderError(f"ESPN failed after {retries} tries: {url}: {last}")


def get_team_ids() -> list[int]:
    data = _get(f"{SITE}/teams")
    teams = data["sports"][0]["leagues"][0]["teams"]
    return [int(t["team"]["id"]) for t in teams]


def get_roster(team_id: int) -> list[PlayerMeta]:
    data = _get(f"{SITE}/teams/{team_id}/roster")
    team_name = data.get("team", {}).get("displayName", "")
    out: list[PlayerMeta] = []
    for a in data.get("athletes", []):
        pos = (a.get("position") or {}).get("abbreviation")
        headshot = (a.get("headshot") or {}).get("href")
        injuries = a.get("injuries") or []
        status = (injuries[0].get("status") if injuries else None) or None
        injured = (status or "").lower() in {"out", "injured", "doubtful", "day-to-day"}
        out.append(
            PlayerMeta(
                espn_id=str(a["id"]),
                name=a.get("fullName", ""),
                team=team_name,
                position=pos,
                headshot_url=headshot,
                injured=injured,
                injury_status=status,
            )
        )
    return out


def _label_index(labels: list[str]) -> dict[str, int]:
    return {label: i for i, label in enumerate(labels)}


def get_season_history(espn_id: str) -> list[tuple[str, PlayerStats]]:
    """All seasons' per-game averages, most recent first: [(displayName, stats)].

    Powers both current-season stats and the previous-season prior used by v2.
    """
    try:
        data = _get(f"{WEB}/athletes/{espn_id}/stats")
    except Exception:  # noqa: BLE001
        return []

    avg_cat = next((c for c in data.get("categories", []) if c.get("name") == "averages"), None)
    if not avg_cat or not avg_cat.get("statistics"):
        return []

    idx = _label_index(avg_cat.get("labels", []))

    def season_year(row: dict) -> int:
        disp = (row.get("season") or {}).get("displayName", "0")
        try:
            return int(str(disp).split("-")[0])
        except ValueError:
            return 0

    def f(stats: list[str], key: str) -> float:
        i = idx.get(key)
        if i is None or i >= len(stats):
            return 0.0
        try:
            return float(stats[i])
        except ValueError:
            return 0.0

    out: list[tuple[str, PlayerStats]] = []
    for row in sorted(avg_cat["statistics"], key=season_year, reverse=True):
        stats = row.get("stats") or []
        gp = f(stats, "GP")
        if gp <= 0:
            continue
        disp = (row.get("season") or {}).get("displayName", "")
        out.append(
            (
                disp,
                PlayerStats(
                    games=int(gp),
                    minutes=f(stats, "MIN"),
                    points=f(stats, "PTS"),
                    rebounds=f(stats, "REB"),
                    assists=f(stats, "AST"),
                    steals=f(stats, "STL"),
                    blocks=f(stats, "BLK"),
                    turnovers=f(stats, "TO"),
                ),
            )
        )
    return out


def get_season_averages(espn_id: str) -> PlayerStats | None:
    """Most recent season's per-game averages, or None if unavailable."""
    hist = get_season_history(espn_id)
    return hist[0][1] if hist else None


# gamelog stat column order (from the endpoint's "names" array)
_GL = {
    "minutes": 0, "reb": 7, "ast": 8, "blk": 9, "stl": 10, "tov": 12, "pts": 13,
}


def _num(v: str) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def get_gamelog(espn_id: str, season_filter: str = "Regular Season") -> list[GameObs]:
    """Per-game observations for a player, most recent season's regular season.

    Returns raw box scores (not values) sorted oldest-first, so a value series
    can be reconstructed point-in-time.
    """
    data = _get(f"{WEB}/athletes/{espn_id}/gamelog")
    events_meta = data.get("events", {}) or {}

    # Pick the season block matching the filter (falls back to the first).
    season_types = data.get("seasonTypes", []) or []
    block = next(
        (s for s in season_types if season_filter in (s.get("displayName") or "")),
        season_types[0] if season_types else None,
    )
    if block is None:
        return []

    out: list[GameObs] = []
    for cat in block.get("categories", []) or []:
        for ev in cat.get("events", []) or []:
            eid = str(ev.get("eventId"))
            stats = ev.get("stats") or []
            meta = events_meta.get(eid, {})
            gd_raw = meta.get("gameDate")
            if not gd_raw:
                continue
            try:
                game_date = datetime.fromisoformat(gd_raw.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            opp = (meta.get("opponent") or {}).get("displayName")
            home = (meta.get("homeAway") or meta.get("atVs") or "home") != "away"

            def s(key: str) -> float:
                i = _GL[key]
                return _num(stats[i]) if i < len(stats) else 0.0

            out.append(
                GameObs(
                    espn_event_id=eid,
                    game_date=game_date,
                    opponent=opp,
                    home=home,
                    minutes=s("minutes"),
                    points=s("pts"),
                    rebounds=s("reb"),
                    assists=s("ast"),
                    steals=s("stl"),
                    blocks=s("blk"),
                    turnovers=s("tov"),
                )
            )
    out.sort(key=lambda g: g.game_date)
    return out
