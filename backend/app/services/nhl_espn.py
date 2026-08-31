"""ESPN NHL data provider (keyless hidden API), same shape as the NBA one.

Rosters are grouped by position; we take skaters (C/LW/RW/D) for v1 — goalies
need a separate stat model. Games carry a sport-agnostic ``stats`` dict so the
value pipeline and breakdown work for hockey exactly as for basketball.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from app.services.nba_espn import _get  # shared curl_cffi + retry/backoff

SITE = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports/hockey/nhl"

MARQUEE_TEAMS = [6, 21, 16, 10, 14, 25, 27, 3]  # EDM, COL, CHI, TOR, TBL, ...


@dataclass
class PlayerMeta:
    espn_id: str
    name: str
    team: str
    position: str | None
    headshot_url: str | None
    injured: bool
    injury_status: str | None = None


@dataclass
class GameObs:
    espn_event_id: str
    game_date: date
    opponent: str | None
    home: bool
    minutes: float  # TOI in minutes
    stats: dict[str, float] = field(default_factory=dict)  # goals, assists, shots, plus_minus, pim


def _toi_to_min(toi: str) -> float:
    try:
        m, s = toi.split(":")
        return int(m) + int(s) / 60.0
    except (ValueError, AttributeError):
        return 0.0


def _num(v) -> float:
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def get_team_ids() -> list[int]:
    data = _get(f"{SITE}/teams")
    return [int(t["team"]["id"]) for t in data["sports"][0]["leagues"][0]["teams"]]


def get_roster(team_id: int) -> list[PlayerMeta]:
    data = _get(f"{SITE}/teams/{team_id}/roster")
    team_name = data.get("team", {}).get("displayName", "")
    out: list[PlayerMeta] = []
    for group in data.get("athletes", []):
        if (group.get("position") or "").lower().startswith("goalie"):
            continue  # skaters only for v1
        for a in group.get("items", []):
            pos = (a.get("position") or {}).get("abbreviation")
            injuries = a.get("injuries") or []
            status = (injuries[0].get("status") if injuries else None) or None
            out.append(
                PlayerMeta(
                    espn_id=str(a["id"]),
                    name=a.get("fullName", ""),
                    team=team_name,
                    position=pos,
                    headshot_url=(a.get("headshot") or {}).get("href"),
                    injured=(status or "").lower() in {"out", "injured", "doubtful", "day-to-day"},
                    injury_status=status,
                )
            )
    return out


def _season_year(row: dict) -> int:
    disp = (row.get("season") or {}).get("displayName", "0")
    try:
        return int(str(disp).split("-")[0])
    except ValueError:
        return 0


def get_season_history(espn_id: str) -> list[tuple[str, dict[str, float], int]]:
    """[(seasonName, per_game_stats, games)] most recent first. Season stats are
    totals on ESPN, so we divide by games played to get per-game."""
    try:
        data = _get(f"{WEB}/athletes/{espn_id}/stats")
    except Exception:  # noqa: BLE001
        return []
    cats = data.get("categories", [])
    if not cats or not cats[0].get("statistics"):
        return []
    cat = cats[0]
    idx = {lab: i for i, lab in enumerate(cat.get("labels", []))}

    def val(stats, key):
        i = idx.get(key)
        return _num(stats[i]) if i is not None and i < len(stats) else 0.0

    out: list[tuple[str, dict[str, float], int]] = []
    for row in sorted(cat["statistics"], key=_season_year, reverse=True):
        stats = row.get("stats") or []
        gp = val(stats, "GP")
        if gp <= 0:
            continue
        per = {
            "goals": val(stats, "G") / gp,
            "assists": val(stats, "A") / gp,
            "shots": val(stats, "SOG") / gp,
            "plus_minus": val(stats, "+/-") / gp,
            "pim": val(stats, "PIM") / gp,
        }
        out.append(((row.get("season") or {}).get("displayName", ""), per, int(gp)))
    return out


def get_gamelog(espn_id: str, season_filter: str = "Regular Season") -> list[GameObs]:
    data = _get(f"{WEB}/athletes/{espn_id}/gamelog")
    events_meta = data.get("events", {}) or {}
    names = data.get("names", []) or []
    idx = {n: i for i, n in enumerate(names)}

    def gv(stats, name):
        i = idx.get(name)
        return _num(stats[i]) if i is not None and i < len(stats) else 0.0

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
            gd = meta.get("gameDate")
            if not gd:
                continue
            try:
                gday = datetime.fromisoformat(gd.replace("Z", "+00:00")).date()
            except ValueError:
                continue
            toi_i = idx.get("timeOnIcePerGame")
            toi = stats[toi_i] if toi_i is not None and toi_i < len(stats) else "0:00"
            out.append(
                GameObs(
                    espn_event_id=eid,
                    game_date=gday,
                    opponent=(meta.get("opponent") or {}).get("displayName"),
                    home=(meta.get("homeAway") or "home") != "away",
                    minutes=_toi_to_min(toi),
                    stats={
                        "goals": gv(stats, "goals"),
                        "assists": gv(stats, "assists"),
                        "shots": gv(stats, "shotsTotal"),
                        "plus_minus": gv(stats, "plusMinus"),
                        "pim": gv(stats, "penaltyMinutes"),
                    },
                )
            )
    out.sort(key=lambda g: g.game_date)
    return out
