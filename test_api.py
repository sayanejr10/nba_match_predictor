from nba_api.stats.endpoints import leaguegamefinder

finder = leaguegamefinder.LeagueGameFinder(
    season_nullable="2024-25",
    league_id_nullable="00",              # 00 = NBA
    season_type_nullable="Regular Season",
    timeout=60,
)
games = finder.get_data_frames()[0]

print(games.shape)
print(games[["GAME_DATE", "TEAM_ABBREVIATION", "MATCHUP", "WL", "PTS"]].head(10))