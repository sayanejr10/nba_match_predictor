from datetime import date

import joblib
import pandas as pd
import streamlit as st
from nba_api.stats.endpoints import leaguegamefinder

CURRENT_SEASON = "2026-27"


@st.cache_resource
def load_model():
    return joblib.load("models/model.joblib")


@st.cache_data(ttl=3600)  # on re-télécharge au maximum une fois par heure
def load_season_games(season):
    df = leaguegamefinder.LeagueGameFinder(
        season_nullable=season,
        league_id_nullable="00",
        season_type_nullable="Regular Season",
        timeout=60,
    ).get_data_frames()[0]
    df = df[df["WL"].notna()].copy()  # uniquement les matchs terminés
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df["WIN"] = (df["WL"] == "W").astype(int)
    return df.sort_values("GAME_DATE")


def team_state(games, team, game_date):
    """Les features d'une équipe AVANT le match : seulement les matchs joués avant game_date."""
    past = games[(games["TEAM_ABBREVIATION"] == team) & (games["GAME_DATE"] < game_date)]
    if past.empty:
        return None
    last10 = past.tail(10)
    rest = min((game_date - past["GAME_DATE"].iloc[-1]).days, 4)
    return {
        "WIN_PCT_SEASON": past["WIN"].mean(),
        "WIN_PCT_LAST10": last10["WIN"].mean(),
        "PM_LAST10": last10["PLUS_MINUS"].mean(),
        "REST_DAYS": rest,
        "B2B": int(rest == 1),
        "GAMES": len(past),
    }


st.title("🏀 NBA Match Predictor")
st.caption("Régression logistique entraînée sur 11 saisons NBA (2015-2026)")

bundle = load_model()
model, features = bundle["model"], bundle["features"]
games = load_season_games(CURRENT_SEASON)
teams = sorted(games["TEAM_ABBREVIATION"].unique())

col1, col2 = st.columns(2)
home = col1.selectbox("🏠 Équipe à domicile", teams)
away = col2.selectbox("✈️ Équipe à l'extérieur", teams, index=1)
game_date = pd.Timestamp(st.date_input("Date du match", date.today()))

if home == away:
    st.warning("Choisis deux équipes différentes.")
    st.stop()

h = team_state(games, home, game_date)
a = team_state(games, away, game_date)
if h is None or a is None:
    st.error("Une des deux équipes n'a encore joué aucun match avant cette date.")
    st.stop()

row = {f"{k}_HOME": v for k, v in h.items()} | {f"{k}_AWAY": v for k, v in a.items()}
X = pd.DataFrame([row])[features]
p_home = model.predict_proba(X)[0, 1]

st.subheader("Probabilité de victoire")
c1, c2 = st.columns(2)
c1.metric(home, f"{p_home:.0%}")
c2.metric(away, f"{1 - p_home:.0%}")
st.progress(float(p_home))

if min(h["GAMES"], a["GAMES"]) < 10:
    st.info(
        f"Début de saison : {home} a joué {h['GAMES']} matchs et {away} en a joué {a['GAMES']}. "
        "Les features reposent sur peu de matchs, donc la prédiction est moins fiable."
    )

with st.expander("Voir les features utilisées"):
    st.dataframe(pd.DataFrame({home: h, away: a}).round(2))