"""ESPN NBA data provider (keyless hidden API).

Fetches teams, rosters, and per-game season averages, and parses them into the
domain ``PlayerStats`` the valuation model consumes. This is the real-data feed
behind the player market; it is isolated here so the rest of the app depends only
on plain dataclasses, and a different source could be swapped in.
"""

from __future__ import annotations

from dataclasses import dataclass

from curl_cffi import requests as _requests

from app.domain.player_value import PlayerStats

SITE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba"

# A marquee subset of team ids for a fast default seed; pass all 30 to go full.
MARQUEE_TEAMS = [13, 9, 2, 7, 15, 18, 25, 6]  # LAL, GSW, BOS, DEN, MIL, NYK, DAL, MIA


@dataclass
class PlayerMeta:
    espn_id: str
    name: str
    team: str
    position: str | None
    headshot_url: str | None
    injured: bool


def _get(url: str, timeout: int = 15) -> dict:
    # ESPN's hidden API sits behind Akamai, which blocks stock Python TLS
    # fingerprints. curl_cffi impersonates a real browser handshake.
    resp = _requests.get(url, impersonate="chrome", timeout=timeout)
    resp.raise_for_status()
    return resp.json()


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
        injured = any(
            (inj.get("status") or "").lower() in {"out", "injured", "doubtful"}
            for inj in injuries
        )
        out.append(
            PlayerMeta(
                espn_id=str(a["id"]),
                name=a.get("fullName", ""),
                team=team_name,
                position=pos,
                headshot_url=headshot,
                injured=injured,
            )
        )
    return out


def _label_index(labels: list[str]) -> dict[str, int]:
    return {label: i for i, label in enumerate(labels)}


def get_season_averages(espn_id: str) -> PlayerStats | None:
    """Most recent season's per-game averages, or None if unavailable."""
    try:
        data = _get(f"{WEB}/athletes/{espn_id}/stats")
    except Exception:  # noqa: BLE001
        return None

    avg_cat = next((c for c in data.get("categories", []) if c.get("name") == "averages"), None)
    if not avg_cat or not avg_cat.get("statistics"):
        return None

    idx = _label_index(avg_cat.get("labels", []))
    # Pick the most recent season row that has games played.
    rows = avg_cat["statistics"]

    def season_year(row: dict) -> int:
        disp = (row.get("season") or {}).get("displayName", "0")
        try:
            return int(str(disp).split("-")[0])
        except ValueError:
            return 0

    rows = sorted(rows, key=season_year, reverse=True)

    def f(stats: list[str], key: str) -> float:
        i = idx.get(key)
        if i is None or i >= len(stats):
            return 0.0
        try:
            return float(stats[i])
        except ValueError:
            return 0.0

    for row in rows:
        stats = row.get("stats") or []
        gp = f(stats, "GP")
        if gp <= 0:
            continue
        return PlayerStats(
            games=int(gp),
            minutes=f(stats, "MIN"),
            points=f(stats, "PTS"),
            rebounds=f(stats, "REB"),
            assists=f(stats, "AST"),
            steals=f(stats, "STL"),
            blocks=f(stats, "BLK"),
            turnovers=f(stats, "TO"),
        )
    return None
