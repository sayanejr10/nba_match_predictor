"""Récupère le calendrier et les résultats de la saison NBA chez ESPN.

Pourquoi ESPN ? Le site de stats de la NBA (utilisé par nba_api) bloque souvent les serveurs
cloud, alors que l'app doit tourner en ligne. ESPN publie les mêmes informations (dates, équipes,
scores, salles) dans un format JSON ouvert, sans clé.

Attention : c'est une API non officielle. Si elle change ou ne répond pas, app.py repasse
automatiquement sur nba_api.

Ce module renvoie deux tableaux au MÊME format que celui produit par nba_api, pour que le reste
de l'app n'ait rien à changer :
- games    : une ligne par équipe et par match terminé (comme LeagueGameFinder)
- schedule : une ligne par match, joué ou à venir (comme ScheduleLeagueV2)
"""
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
US_TZ = "America/New_York"

# Sigles ESPN -> sigles NBA (les autres sont identiques)
TRICODE = {"GS": "GSW", "NY": "NYK", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS"}

# Identifiants NBA des 30 équipes (servent aux logos). Seules ces équipes sont acceptées :
# cela écarte les matchs d'exhibition, le All-Star Game et les équipes « à déterminer ».
NBA_TEAM_ID = {
    "ATL": 1610612737, "BOS": 1610612738, "BKN": 1610612751, "CHA": 1610612766, "CHI": 1610612741,
    "CLE": 1610612739, "DAL": 1610612742, "DEN": 1610612743, "DET": 1610612765, "GSW": 1610612744,
    "HOU": 1610612745, "IND": 1610612754, "LAC": 1610612746, "LAL": 1610612747, "MEM": 1610612763,
    "MIA": 1610612748, "MIL": 1610612749, "MIN": 1610612750, "NOP": 1610612740, "NYK": 1610612752,
    "OKC": 1610612760, "ORL": 1610612753, "PHI": 1610612755, "PHX": 1610612756, "POR": 1610612757,
    "SAC": 1610612758, "SAS": 1610612759, "TOR": 1610612761, "UTA": 1610612762, "WAS": 1610612764,
}

# Types de saison ESPN : 2 = saison régulière, 3 = play-offs, 5 = play-in (1 = présaison, écartée)
KEPT_TYPES = {2, 3, 5}
STATUS = {"pre": 1, "in": 2, "post": 3}      # même codage que la NBA : 1 à venir, 2 en cours, 3 terminé


def fetch_month(yyyymm: str) -> list:
    """Tous les matchs d'un mois (ESPN limite à 100 par défaut, d'où limit=1000)."""
    r = requests.get(URL, params={"dates": yyyymm, "limit": 1000}, timeout=20,
                     headers={"User-Agent": "CourtSide/1.0"})
    r.raise_for_status()
    return r.json().get("events", [])


def season_months(season: str) -> list:
    """« 2026-27 » -> octobre 2026 à juin 2027."""
    start = int(season[:4])
    return [f"{start}{m:02d}" for m in range(10, 13)] + [f"{start + 1}{m:02d}" for m in range(1, 7)]


def parse_events(events: list) -> pd.DataFrame:
    """Transforme la réponse ESPN en un tableau au format ScheduleLeagueV2 (celui de nba_api)."""
    rows = []
    for e in events:
        try:
            if int(e.get("season", {}).get("type", 0)) not in KEPT_TYPES:
                continue
            comp = e["competitions"][0]
            side = {}
            for c in comp["competitors"]:
                tri = TRICODE.get(c["team"]["abbreviation"], c["team"]["abbreviation"])
                side[c["homeAway"]] = (tri, c)
            if set(side) != {"home", "away"} or any(side[s][0] not in NBA_TEAM_ID for s in side):
                continue
            row = {
                "gameId": str(e["id"]),
                "gameDateTimeUTC": e["date"],
                "gameStatus": STATUS.get(e["status"]["type"]["state"], 1),
                "seasonType": int(e["season"]["type"]),
                "arenaName": comp.get("venue", {}).get("fullName", ""),
                "arenaCity": comp.get("venue", {}).get("address", {}).get("city", ""),
            }
            for s, prefix in (("home", "homeTeam"), ("away", "awayTeam")):
                tri, c = side[s]
                row[f"{prefix}_teamTricode"] = tri
                row[f"{prefix}_teamId"] = NBA_TEAM_ID[tri]
                row[f"{prefix}_teamCity"] = c["team"].get("location", "")
                row[f"{prefix}_teamName"] = c["team"].get("name", "")
                row[f"{prefix}_score"] = c.get("score", 0)
            rows.append(row)
        except (KeyError, IndexError, TypeError, ValueError):
            continue          # un match mal formé est ignoré, sans faire planter l'app
    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("ESPN: aucun match exploitable")
    df = df.drop_duplicates("gameId")
    # Même validation que pour nba_api : identifiant uniquement en chiffres (complété à 10)
    df["gameId"] = df["gameId"].str.zfill(10)
    df = df[df["gameId"].str.fullmatch(r"\d{10}")].copy()
    df["START_UTC"] = pd.to_datetime(df["gameDateTimeUTC"], utc=True, errors="coerce")
    # La date « US » d'un match = sa date à New York (un match à 1h UTC est la veille aux États-Unis)
    df["US_DATE"] = df["START_UTC"].dt.tz_convert(US_TZ).dt.tz_localize(None).dt.normalize()
    for side in ("homeTeam", "awayTeam"):
        df[f"{side}_score"] = pd.to_numeric(df[f"{side}_score"], errors="coerce").fillna(0).astype(int)
    return df.dropna(subset=["US_DATE"]).sort_values(["US_DATE", "START_UTC"]).reset_index(drop=True)


def games_from_schedule(schedule: pd.DataFrame) -> pd.DataFrame:
    """Les matchs terminés de saison régulière, une ligne par équipe (format LeagueGameFinder)."""
    done = schedule[(schedule["gameStatus"] == 3) & (schedule["seasonType"] == 2)]
    rows = []
    for g in done.itertuples():
        for team, opp, pts, opp_pts, sep in (
            (g.homeTeam_teamTricode, g.awayTeam_teamTricode, g.homeTeam_score, g.awayTeam_score, "vs."),
            (g.awayTeam_teamTricode, g.homeTeam_teamTricode, g.awayTeam_score, g.homeTeam_score, "@"),
        ):
            rows.append({
                "GAME_ID": g.gameId, "TEAM_ABBREVIATION": team, "GAME_DATE": g.US_DATE,
                "MATCHUP": f"{team} {sep} {opp}", "PTS": pts, "PLUS_MINUS": pts - opp_pts,
                "WL": "W" if pts > opp_pts else "L", "START_UTC": g.START_UTC,
            })
    games = pd.DataFrame(rows, columns=["GAME_ID", "TEAM_ABBREVIATION", "GAME_DATE", "MATCHUP", "PTS",
                                        "PLUS_MINUS", "WL", "START_UTC"])
    games["WIN"] = (games["WL"] == "W").astype(int)
    return games.sort_values(["GAME_DATE", "START_UTC"]).drop(columns="START_UTC").reset_index(drop=True)


def load_season(season: str, today=None):
    """(games, schedule) pour la saison demandée. Les mois futurs vides sont simplement ignorés."""
    # Les 9 mois sont téléchargés en même temps (et non l'un après l'autre) : chargement bien plus rapide
    with ThreadPoolExecutor(max_workers=9) as pool:
        months = list(pool.map(fetch_month, season_months(season)))
    events = [e for month in months for e in month]
    schedule = parse_events(events)
    return games_from_schedule(schedule), schedule