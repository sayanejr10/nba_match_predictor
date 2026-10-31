import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder

SEASONS = [f"{y}-{str(y + 1)[-2:]}" for y in range(2015, 2026)]  # 2015-16 -> 2025-26
OUTPUT = Path("data/games_raw.csv")


def fetch_season(season: str) -> pd.DataFrame:
    finder = leaguegamefinder.LeagueGameFinder(
        season_nullable=season,
        league_id_nullable="00",
        season_type_nullable="Regular Season",
        timeout=60,
    )
    df = finder.get_data_frames()[0]
    df["SEASON"] = season
    return df


def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    all_seasons = []

    for season in SEASONS:
        print(f"Récupération {season}...", end=" ")
        df = fetch_season(season)
        print(f"{len(df)} lignes")
        all_seasons.append(df)
        time.sleep(2)  # on ne spamme pas le serveur de la NBA

    games = pd.concat(all_seasons, ignore_index=True)
    games.to_csv(OUTPUT, index=False)
    print(f"\nTotal : {games.shape} -> sauvegardé dans {OUTPUT}")


if __name__ == "__main__":
    main()