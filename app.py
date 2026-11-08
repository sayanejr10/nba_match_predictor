import os
from datetime import date

import joblib
import pandas as pd
import streamlit as st
from nba_api.stats.endpoints import leaguegamefinder

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
CURRENT_SEASON = "2026-27"
# Mode développeur : affiché uniquement si on lance l'app avec COURTSIDE_DEBUG=1
DEBUG = os.environ.get("COURTSIDE_DEBUG") == "1"
NBA_LOGO = "https://cdn.nba.com/logos/leagues/logo-nba.svg"
TEAM_LOGO = "https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
BASE_FEATURES = ["WIN_PCT_SEASON", "WIN_PCT_LAST10", "PM_LAST10", "REST_DAYS", "B2B"]
MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
          "juil.", "août", "sept.", "oct.", "nov.", "déc."]

TEAM_COLORS = {
    "ATL": "#E03A3E", "BOS": "#007A33", "BKN": "#4B5563", "CHA": "#1D8CAB", "CHI": "#CE1141",
    "CLE": "#860038", "DAL": "#00538C", "DEN": "#0E2240", "DET": "#C8102E", "GSW": "#1D428A",
    "HOU": "#CE1141", "IND": "#002D62", "LAC": "#C8102E", "LAL": "#552583", "MEM": "#5D76A9",
    "MIA": "#98002E", "MIL": "#00471B", "MIN": "#236192", "NOP": "#0C2340", "NYK": "#F58426",
    "OKC": "#007AC1", "ORL": "#0077C0", "PHI": "#006BB6", "PHX": "#E56020", "POR": "#E03A3E",
    "SAC": "#5A2D81", "SAS": "#6B7280", "TOR": "#CE1141", "UTA": "#002B5C", "WAS": "#002B5C",
}

# Icônes vectorielles (tracés Lucide, licence ISC)
ICONS = {
    "calendar": '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
    "pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "trend": '<path d="M22 7 13.5 15.5 8.5 10.5 2 17"/><path d="M16 7h6v6"/>',
    "scale": '<path d="M12 3v18M5 7h14M5 7l-3 7a4 4 0 0 0 6 0L5 7Zm14 0-3 7a4 4 0 0 0 6 0l-3-7Z"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><path d="M12 9v4M12 17h.01"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "target": '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="6"/><circle cx="12" cy="12" r="2"/>',
}

st.set_page_config(page_title="CourtSide · NBA Match Predictor",
                   page_icon=":material/sports_basketball:", layout="wide")


def html(block: str, target=st) -> None:
    """Affiche du HTML. On retire l'indentation, sinon Markdown le prend pour du code."""
    target.markdown("".join(line.strip() for line in block.splitlines()), unsafe_allow_html=True)


def icon(name: str, size: int = 15) -> str:
    return (f'<svg class="ic" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" '
            f'aria-hidden="true">{ICONS[name]}</svg>')


def count(value: int) -> str:
    """Nombre qui défile de 0 jusqu'à sa valeur (affiché tel quel si l'animation est désactivée)."""
    return f'<span class="count" style="--to:{int(value)}"></span>'


# ----------------------------------------------------------------------------
# Système de design
# ----------------------------------------------------------------------------
html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Russo+One&family=Chakra+Petch:wght@400;500;600;700&display=swap');

:root {
  --bg: #F8FAFC;
  --card: #FFFFFF;
  --fg: #0F172A;
  --muted: #475569;
  --subtle: #64748B;
  --border: #E2E8F0;
  --soft: #F1F5F9;
  --primary: #1E40AF;
  --primary-soft: #EFF6FF;
  --positive: #15803D;
  --negative: #DC2626;
  --radius: 12px;
  --shadow: 0 1px 2px rgba(15,23,42,.04), 0 1px 3px rgba(15,23,42,.06);
  --shadow-hover: 0 10px 24px -8px rgba(15,23,42,.18);
  --display: 'Russo One', 'Arial Black', sans-serif;
  --body: 'Chakra Petch', -apple-system, 'Segoe UI', Roboto, sans-serif;
  /* Jetons de mouvement : une seule courbe et trois durées pour toute l'app */
  --ease: cubic-bezier(.16, 1, .3, 1);
  --spring: cubic-bezier(.34, 1.56, .64, 1);
  --t-fast: .2s;
  --t-in: .6s;
  --t-fill: 1.4s;
}

html, body, .stApp, [class*="css"], button, input, label, p { font-family: var(--body) !important; }
.wm, .panel-title, .card-head h3, .model .big, .tname, .prob, .vs .v, .cmp .val, .g-line .s, .ticker-track .tag {
  font-weight: 400 !important; font-synthesis: none; }
.stApp { background: var(--bg); color: var(--fg); overflow-x: hidden; }
header[data-testid="stHeader"] { display: none; }
#MainMenu, footer { visibility: hidden; }
.block-container { max-width: 1480px; padding: 0 28px 40px; }
.ic { vertical-align: -2px; flex-shrink: 0; }
.num { font-variant-numeric: tabular-nums; }

/* Barre de navigation */
.nav { margin: -16px calc(50% - 50vw) 0; padding: 14px 28px; background: #0B1220; display: flex;
       align-items: center; justify-content: space-between; }
.brand { display: flex; align-items: center; gap: 14px; }
.brand img { height: 40px; }
.brand .wm { font-family: var(--display); font-weight: 700; font-size: 24px; letter-spacing: 1px;
             color: #fff; text-transform: uppercase; line-height: 1; }
.brand .wm span { color: #60A5FA; }
.brand .tl { font-size: 12px; color: #94A3B8; margin-top: 3px; }
.nav-meta { display: flex; gap: 10px; }
.nav-pill { display: inline-flex; align-items: center; gap: 7px; padding: 7px 12px; border-radius: 999px;
            border: 1px solid #1E293B; color: #CBD5E1; font-size: 13px; font-weight: 500; }
.nav-pill b { color: #fff; font-weight: 600; }

/* Bandeau des derniers scores */
.ticker { margin: 0 calc(50% - 50vw) 26px; background: var(--card); border-bottom: 1px solid var(--border);
          overflow: hidden; white-space: nowrap; }
.ticker-track { display: inline-block; padding: 9px 0; animation: scroll 70s linear infinite; }
.ticker:hover .ticker-track { animation-play-state: paused; }
.ticker-track span { font-size: 13px; color: var(--muted); margin: 0 22px; }
.ticker-track b { color: var(--fg); font-weight: 700; font-variant-numeric: tabular-nums; }
.ticker-track .tag { font-family: var(--display); font-weight: 700; font-size: 12px; letter-spacing: 1px;
                     text-transform: uppercase; color: var(--primary); margin: 0 22px 0 28px; }
@keyframes scroll { to { transform: translateX(-50%); } }

/* Panneau de sélection */
.st-key-pick { background: var(--card); border: 1px solid var(--border) !important; border-radius: var(--radius);
               box-shadow: var(--shadow); padding: 14px 18px !important; }
.st-key-pick label p { font-size: 13px !important; font-weight: 600; color: var(--muted); }
.st-key-pick [data-baseweb="select"] > div, .st-key-pick [data-baseweb="input"] {
  background: var(--card) !important; border: 1px solid var(--border) !important; border-radius: 8px !important;
  transition: border-color var(--t-fast) ease, box-shadow var(--t-fast) ease; cursor: pointer; }
.st-key-pick [data-baseweb="select"] > div:hover, .st-key-pick [data-baseweb="input"]:hover {
  border-color: #94A3B8 !important; box-shadow: 0 0 0 3px rgba(30,64,175,.06); }
.panel-title { font-family: var(--display); font-size: 16px; font-weight: 700; text-transform: uppercase;
               letter-spacing: .6px; color: var(--fg); margin: 2px 0 2px; }
.panel-sub { font-size: 13px; color: var(--subtle); margin-bottom: 4px; }

/* Cartes */
.card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: var(--shadow);
        transition: transform var(--t-fast) var(--ease), box-shadow var(--t-fast) ease; }
.card:hover { transform: translateY(-2px); box-shadow: var(--shadow-hover); }
.card-head { display: flex; justify-content: space-between; align-items: baseline; padding: 16px 20px 10px; }
.card-head h3 { font-family: var(--display); font-size: 16px; font-weight: 700; text-transform: uppercase;
                letter-spacing: .6px; color: var(--fg); margin: 0; padding: 0; }
.card-head span { font-size: 13px; color: var(--subtle); display: inline-flex; align-items: center; gap: 5px; }
.eyebrow { font-size: 12px; font-weight: 600; letter-spacing: 1.4px; text-transform: uppercase; color: var(--subtle); }

/* Modèle (colonne de gauche) */
.model { padding: 18px 20px; margin-top: 16px; }
.model .big { font-family: var(--display); font-size: 40px; font-weight: 700; color: var(--fg); line-height: 1; margin-top: 6px; }
.model .cap { font-size: 13px; color: var(--muted); margin-top: 4px; }
.model .gauge { position: relative; height: 8px; border-radius: 999px; background: var(--soft); margin: 14px 0 8px; }
.model .gauge .fill { position: absolute; inset: 0 auto 0 0; border-radius: 999px; background: var(--primary); }
.model .gauge .mark { position: absolute; top: -4px; width: 2px; height: 16px; background: var(--subtle); }
.model .legend { display: flex; justify-content: space-between; font-size: 12px; color: var(--subtle); }
.model dl { display: grid; grid-template-columns: 1fr auto; gap: 8px; margin: 16px 0 0; padding-top: 14px;
            border-top: 1px solid var(--border); font-size: 13px; }
.model dt { color: var(--muted); } .model dd { margin: 0; color: var(--fg); font-weight: 600; text-align: right; }

/* Hero */
.dash { display: grid; gap: 18px; }
.hero { position: relative; overflow: hidden; padding: 22px 28px 24px;
        background:
          radial-gradient(520px 260px at 0% 60%, color-mix(in srgb, var(--home) 13%, transparent), transparent 70%),
          radial-gradient(520px 260px at 100% 60%, color-mix(in srgb, var(--away) 13%, transparent), transparent 70%),
          var(--card); }
.hero:hover { transform: none; box-shadow: var(--shadow); }
.hero-top { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; }
.hero-meta { display: flex; gap: 16px; font-size: 14px; color: var(--muted); }
.hero-meta span { display: inline-flex; align-items: center; gap: 6px; }
.duel { display: grid; grid-template-columns: 1fr 120px 1fr; align-items: center; margin-top: 18px; }
.side { display: flex; align-items: center; gap: 20px; }
.side.away { flex-direction: row-reverse; text-align: right; }
.logo-wrap { position: relative; flex-shrink: 0; width: 104px; height: 104px; display: grid; place-items: center; }
.logo-wrap img { height: 104px; width: 104px; object-fit: contain; filter: drop-shadow(0 6px 14px rgba(15,23,42,.14)); }
.halo { position: absolute; inset: -6px; border-radius: 50%; border: 2px solid var(--c); opacity: 0; }
.tname { font-family: var(--display); font-size: 24px; font-weight: 700; text-transform: uppercase;
         color: var(--fg); line-height: 1; letter-spacing: .3px; }
.trec { font-size: 14px; color: var(--muted); margin-top: 6px; }
.prob { font-family: var(--display); font-size: 64px; font-weight: 700; line-height: .95; margin-top: 8px;
        font-variant-numeric: tabular-nums; color: var(--fg); }
.prob small { font-size: 28px; margin-left: 2px; }
.prob.dog { color: var(--subtle); }
.vs { text-align: center; }
.vs .v { font-family: var(--display); font-size: 22px; font-weight: 700; color: var(--subtle); letter-spacing: 2px; }
.vs .l { font-size: 11px; color: var(--subtle); text-transform: uppercase; letter-spacing: 1.2px; margin-top: 4px; }
.pbar { display: flex; height: 10px; border-radius: 999px; overflow: hidden; gap: 3px; margin-top: 22px; background: var(--soft); }
.pbar div { height: 100%; }
.hero-foot { display: flex; justify-content: space-between; align-items: center; margin-top: 16px; flex-wrap: wrap; gap: 10px; }
.verdict { display: inline-flex; align-items: center; gap: 8px; padding: 7px 14px; border-radius: 999px;
           font-size: 14px; font-weight: 600; }
.verdict.strong { background: #DCFCE7; color: #14532D; }
.verdict.lean { background: var(--primary-soft); color: #1E3A8A; }
.verdict.even { background: var(--soft); color: #334155; }
.note { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; color: #92400E; background: #FEF3C7;
        padding: 7px 12px; border-radius: 8px; }

/* KPIs face à face */
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 18px; }
.kpi { padding: 16px 18px; }
.kpi .eyebrow { margin-bottom: 12px; }
.cmp { display: grid; grid-template-columns: 38px 1fr auto; align-items: center; gap: 10px; }
.cmp + .cmp { margin-top: 10px; }
.cmp .ab { font-size: 13px; font-weight: 700; color: var(--muted); }
.track { height: 6px; border-radius: 999px; background: var(--soft); overflow: hidden; }
.track div { height: 100%; border-radius: 999px; }
.cmp .val { font-family: var(--display); font-size: 19px; font-weight: 600; color: var(--muted);
            font-variant-numeric: tabular-nums; min-width: 48px; text-align: right; }
.cmp .val.best { color: var(--fg); font-weight: 700; }
.tag-b2b { display: inline-block; font-family: var(--body); font-size: 11px; font-weight: 700; color: #92400E;
           background: #FEF3C7; padding: 1px 6px; border-radius: 4px; margin-right: 6px; vertical-align: 3px; }

/* Grille basse */
.split { display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(0, 1fr); gap: 18px; align-items: start; }
.stack { display: grid; gap: 18px; }

/* Classement */
.tbl-wrap { overflow-x: auto; padding: 0 8px 8px; }
table.std { width: 100%; border-collapse: collapse; font-size: 14px; border: none !important; }
table.std th, table.std td { border: none !important; }
table.std th { text-align: left; font-size: 12px; font-weight: 600; letter-spacing: .8px; text-transform: uppercase;
               color: var(--subtle); padding: 8px 12px; border-bottom: 1px solid var(--border) !important; }
table.std th.r { text-align: right; }
table.std td { padding: 9px 12px; color: var(--fg); border-bottom: 1px solid var(--soft) !important;
               font-variant-numeric: tabular-nums; transition: background-color var(--t-fast) ease; }
table.std tr:hover td { background: var(--soft); }
table.std tr.sel td { background: var(--primary-soft); }
table.std tr.sel td:first-child { box-shadow: inset 3px 0 0 var(--primary); }
table.std tr.gap td { padding: 2px 12px; color: var(--subtle); text-align: center; }
table.std .rk { color: var(--subtle); font-weight: 600; width: 36px; }
table.std .club { display: flex; align-items: center; gap: 10px; font-weight: 600; white-space: nowrap; }
table.std .club img { height: 26px; width: 26px; object-fit: contain; transition: transform var(--t-fast) var(--spring); }
table.std tr:hover .club img { transform: scale(1.15); }
.r { text-align: right; }
.pos { color: var(--positive); font-weight: 600; } .neg { color: var(--negative); font-weight: 600; }
.form { display: inline-flex; gap: 3px; }
.form i { width: 8px; height: 22px; border-radius: 3px; display: inline-block; }
.form i.W { background: var(--positive); } .form i.L { background: #FCA5A5; }

/* Derniers matchs */
.games { display: grid; gap: 12px; padding: 0 20px 18px; }
.game { border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
.g-head { display: flex; justify-content: space-between; font-size: 12px; color: var(--subtle); margin-bottom: 8px; }
.g-line { display: grid; grid-template-columns: 28px 1fr auto; align-items: center; gap: 10px; padding: 3px 0; color: var(--subtle); }
.g-line img { height: 26px; width: 26px; object-fit: contain; }
.g-line .n { font-weight: 600; }
.g-line .s { font-family: var(--display); font-size: 19px; font-weight: 600; font-variant-numeric: tabular-nums; }
.g-line.win { color: var(--fg); }
.g-line.win .s { font-weight: 700; }

/* En forme */
.hot { padding: 0 20px 14px; }
.hot-row { display: grid; grid-template-columns: 18px 28px 1fr 64px 40px; align-items: center; gap: 10px;
           padding: 9px 0; border-bottom: 1px solid var(--soft); font-size: 14px; }
.hot-row:last-child { border-bottom: none; }
.hot-row .rk { color: var(--subtle); font-weight: 600; }
.hot-row img { height: 26px; width: 26px; object-fit: contain; }
.hot-row .n { font-weight: 600; color: var(--fg); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.hot-row .p { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; }

.footer { text-align: center; color: var(--subtle); font-size: 12px; margin-top: 26px; }

/* ===================== ANIMATIONS ===================== */
@property --n { syntax: '<integer>'; inherits: false; initial-value: 0; }
.count { counter-reset: n var(--n); --n: var(--to); animation: count var(--t-fill) var(--ease) var(--cd, .5s) both; }
.count::after { content: counter(n); }
@keyframes count { from { --n: 0; } }

/* Entrées */
@keyframes rise     { from { opacity: 0; transform: translateY(16px); } }
@keyframes in-left  { from { opacity: 0; transform: translateX(-40px); } }
@keyframes in-right { from { opacity: 0; transform: translateX(40px); } }
@keyframes pop      { from { opacity: 0; transform: scale(.6); } }
@keyframes fade     { from { opacity: 0; } }
@keyframes grow     { from { transform: scaleX(0); } }
@keyframes grow-y   { from { transform: scaleY(0); } }

.card, .st-key-pick { animation: rise var(--t-in) var(--ease) var(--d, 0s) both; }
.side.home { animation: in-left .8s var(--ease) .25s both; }
.side.away { animation: in-right .8s var(--ease) .25s both; }
.logo-wrap img { animation: pop .7s var(--spring) .35s both; }
.vs { animation: fade .6s ease .5s both; }
.hero-meta { animation: fade .6s ease .3s both; }

/* Barre de probabilité : chaque équipe pousse depuis son côté */
.pbar .h { transform-origin: left;  animation: grow var(--t-fill) var(--ease) .5s both; }
.pbar .a { transform-origin: right; animation: grow var(--t-fill) var(--ease) .5s both; }
.verdict, .note { animation: pop .5s var(--spring) 1.5s both; }

/* Le favori émet une onde douce */
.side.fav .halo { animation: halo 2.6s ease-out 2s infinite; }
@keyframes halo { 0% { opacity: .55; transform: scale(.9); } 100% { opacity: 0; transform: scale(1.35); } }

/* Barres et listes en cascade */
.track div { transform-origin: left; animation: grow 1s var(--ease) calc(.7s + var(--i, 0) * 80ms) both; }
.cmp .val { animation: fade .5s ease calc(.8s + var(--i, 0) * 80ms) both; }
.cascade { animation: rise .45s var(--ease) calc(var(--d0, .6s) + var(--i) * 40ms) both; }
.form i { transform-origin: bottom; animation: grow-y .3s var(--ease) calc(1s + var(--i) * 50ms) both; }
.model .gauge .fill { transform-origin: left; animation: grow var(--t-fill) var(--ease) .3s both; }
.model .gauge .mark { animation: fade .4s ease 1.2s both; }

@media (max-width: 1150px) {
  .kpis { grid-template-columns: repeat(2, 1fr); }
  .split { grid-template-columns: 1fr; }
}
@media (max-width: 680px) {
  .kpis { grid-template-columns: 1fr; }
  .duel { grid-template-columns: 1fr; gap: 14px; }
  .side.away { flex-direction: row; text-align: left; }
  .logo-wrap, .logo-wrap img { height: 64px; width: 64px; }
  .prob { font-size: 56px; }
  .nav-meta { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
</style>
""")


# ----------------------------------------------------------------------------
# Données et modèle
# ----------------------------------------------------------------------------
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
    wins = int(past["WIN"].sum())
    l10_wins = int(last10["WIN"].sum())
    last = past.iloc[-1]
    return {
        # features du modèle
        "WIN_PCT_SEASON": past["WIN"].mean(),
        "WIN_PCT_LAST10": last10["WIN"].mean(),
        "PM_LAST10": last10["PLUS_MINUS"].mean(),
        "REST_DAYS": rest,
        "B2B": int(rest == 1),
        # infos d'affichage
        "GAMES": len(past),
        "RECORD": f"{wins}-{len(past) - wins}",
        "L10": f"{l10_wins}-{len(last10) - l10_wins}",
        "LAST_GAME": {
            "date": last["GAME_DATE"],
            "opp": last["MATCHUP"].split()[-1],
            "home": "vs." in last["MATCHUP"],
            "pts": int(last["PTS"]),
            "opp_pts": int(last["PTS"] - last["PLUS_MINUS"]),
            "wl": last["WL"],
        },
    }


def standings(games, before):
    """Classement de la ligue avec uniquement les matchs joués avant la date choisie."""
    rows = []
    for abbr, t in games[games["GAME_DATE"] < before].groupby("TEAM_ABBREVIATION"):
        w, n = int(t["WIN"].sum()), len(t)
        rows.append({
            "TEAM": abbr, "GP": n, "W": w, "L": n - w, "PCT": w / n, "PM": t["PLUS_MINUS"].mean(),
            "L10": t["WIN"].tail(10).mean(), "LAST5": t["WL"].tail(5).tolist(),
        })
    return pd.DataFrame(rows).sort_values(["PCT", "PM"], ascending=False).reset_index(drop=True)


def latest_scores(games, n=16):
    """Les derniers scores de la ligue pour le bandeau (une entrée par match, côté domicile)."""
    home_rows = games[games["MATCHUP"].str.contains("vs.")].tail(n)
    return "".join(
        f"<span>{r.MATCHUP.split()[-1]} <b>{int(r.PTS - r.PLUS_MINUS)}</b> – <b>{int(r.PTS)}</b> {r.TEAM_ABBREVIATION}</span>"
        for r in home_rows.itertuples()
    )


def fr_date(d, year=True):
    return f"{d.day} {MONTHS[d.month - 1]}" + (f" {d.year}" if year else "")


def form_bars(results):
    label = ", ".join("victoire" if r == "W" else "défaite" for r in results)
    bars = "".join(f'<i class="{r}" style="--i:{j}"></i>' for j, r in enumerate(results))
    return f'<span class="form" role="img" aria-label="5 derniers matchs : {label}">{bars}</span>'


# ----------------------------------------------------------------------------
# Chargement
# ----------------------------------------------------------------------------
bundle = load_model()
model, features = bundle["model"], bundle["features"]
games = load_season_games(CURRENT_SEASON)

teams_info = (
    games.drop_duplicates("TEAM_ABBREVIATION")
    .set_index("TEAM_ABBREVIATION")[["TEAM_ID", "TEAM_NAME"]]
    .sort_values("TEAM_NAME")
)
teams = teams_info.index.tolist()
full_name = teams_info["TEAM_NAME"].to_dict()


def logo(abbr):
    return TEAM_LOGO.format(team_id=teams_info.loc[abbr, "TEAM_ID"])


def color(abbr):
    return TEAM_COLORS.get(abbr, "#1E40AF")


# ----------------------------------------------------------------------------
# Barre de navigation + bandeau des scores
# ----------------------------------------------------------------------------
scores = latest_scores(games)
html(f"""
<nav class="nav">
  <div class="brand">
    <img src="{NBA_LOGO}" alt="NBA">
    <div><div class="wm">Court<span>Side</span></div><div class="tl">Pronostics NBA par machine learning</div></div>
  </div>
  <div class="nav-meta">
    <span class="nav-pill">{icon("calendar", 14)} Saison <b>{CURRENT_SEASON}</b></span>
    <span class="nav-pill">{icon("target", 14)} Précision <b>67 %</b></span>
  </div>
</nav>
<div class="ticker" aria-hidden="true"><div class="ticker-track">
  <span class="tag">Derniers scores</span>{scores}<span class="tag">Derniers scores</span>{scores}
</div></div>
""")

left, main = st.columns([1, 3.6], gap="large")

# ----------------------------------------------------------------------------
# Colonne de gauche : sélection + modèle
# ----------------------------------------------------------------------------
with left:
    with st.container(border=True, key="pick"):
        html('<div class="panel-title">Choisir un match</div>'
             '<div class="panel-sub">Le modèle utilise la forme des équipes avant cette date.</div>')
        home = st.selectbox("Équipe à domicile", teams, format_func=lambda t: full_name[t])
        away = st.selectbox("Équipe à l'extérieur", teams, index=1, format_func=lambda t: full_name[t])
        game_date = pd.Timestamp(st.date_input("Date du match", date.today(), format="DD/MM/YYYY"))

    html(f"""
    <div class="card model" style="--d:.1s">
      <div class="eyebrow">Le modèle</div>
      <div class="big num">{count(67)} %</div>
      <div class="cap">de bonnes prédictions sur 2 418 matchs jamais vus</div>
      <div class="gauge"><div class="fill" style="width:67%"></div><div class="mark" style="left:55%"></div></div>
      <div class="legend"><span>Baseline 55 %</span><span>Modèle 67 %</span></div>
      <dl>
        <dt>Algorithme</dt><dd>Régression logistique</dd>
        <dt>Variables</dt><dd>10</dd>
        <dt>Entraînement</dt><dd class="num">13 023 matchs</dd>
        <dt>Saisons</dt><dd>2015 à 2026</dd>
      </dl>
    </div>
    """)

if home == away:
    main.warning("Choisis deux équipes différentes.")
    st.stop()

h = team_state(games, home, game_date)
a = team_state(games, away, game_date)
if h is None or a is None:
    main.error("Une des deux équipes n'a encore joué aucun match avant cette date.")
    st.stop()

# ----------------------------------------------------------------------------
# Prédiction
# ----------------------------------------------------------------------------
row = {f"{k}_HOME": h[k] for k in BASE_FEATURES} | {f"{k}_AWAY": a[k] for k in BASE_FEATURES}
X = pd.DataFrame([row])[features]
p_home = float(model.predict_proba(X)[0, 1])
p_away = 1 - p_home

fav, p_fav = (home, p_home) if p_home >= 0.5 else (away, p_away)
if p_fav < 0.55:
    verdict = f'<span class="verdict even">{icon("scale")} Match très serré, pas de vrai favori</span>'
elif p_fav < 0.65:
    verdict = f'<span class="verdict lean">{icon("trend")} Léger avantage {full_name[fav]}</span>'
else:
    verdict = f'<span class="verdict strong">{icon("trend")} {full_name[fav]} nettement favori</span>'

note = ""
if min(h["GAMES"], a["GAMES"]) < 10:
    note = (f'<span class="note">{icon("alert", 14)} Début de saison : {h["GAMES"]} et {a["GAMES"]} '
            f'matchs joués, prédiction moins fiable</span>')

home_cls, away_cls = ("", "dog") if p_home >= 0.5 else ("dog", "")
home_fav, away_fav = ("fav", "") if p_home >= 0.5 else ("", "fav")
table = standings(games, game_date)


# ----------------------------------------------------------------------------
# Composants
# ----------------------------------------------------------------------------
def kpi(i, label, hv, av, h_txt, a_txt, scale, higher_is_better=True):
    """Carte de comparaison : une barre par équipe, la meilleure valeur en évidence."""
    h_best = a_best = ""
    if hv != av:
        if (hv > av) == higher_is_better:
            h_best = "best"
        else:
            a_best = "best"
    hw, aw = (max(0.04, min(1, scale(v))) for v in (hv, av))
    return f"""
    <div class="card kpi" style="--d:{.15 + i * .06:.2f}s">
      <div class="eyebrow">{label}</div>
      <div class="cmp"><span class="ab">{home}</span>
        <div class="track"><div style="width:{hw:.0%};background:{color(home)};--i:{i * 2}"></div></div>
        <span class="val {h_best}" style="--i:{i * 2}">{h_txt}</span></div>
      <div class="cmp"><span class="ab">{away}</span>
        <div class="track"><div style="width:{aw:.0%};background:{color(away)};--i:{i * 2 + 1}"></div></div>
        <span class="val {a_best}" style="--i:{i * 2 + 1}">{a_txt}</span></div>
    </div>
    """


def game_card(k, team, state):
    g = state["LAST_GAME"]
    # Convention des tableaux de scores NBA : l'équipe à l'extérieur en haut, à domicile en bas
    lines = [(g["opp"], g["opp_pts"]), (team, g["pts"])] if g["home"] else [(team, g["pts"]), (g["opp"], g["opp_pts"])]
    winner = max(lines, key=lambda x: x[1])[0]
    body = "".join(
        f'<div class="g-line {"win" if t == winner else ""}"><img src="{logo(t)}" alt="{full_name.get(t, t)}">'
        f'<span class="n">{full_name.get(t, t)}</span>'
        f'<span class="s" style="--cd:{.9 + k * .15:.2f}s">{count(pts)}</span></div>'
        for t, pts in lines
    )
    result = "Victoire" if g["wl"] == "W" else "Défaite"
    return (f'<div class="game cascade" style="--d0:.7s;--i:{k}"><div class="g-head"><span>Dernier match {team} · {result}</span>'
            f'<span>{fr_date(g["date"], year=False)}</span></div>{body}</div>')


# ----------------------------------------------------------------------------
# Tableau de bord
# ----------------------------------------------------------------------------
with main:
    hero = f"""
    <section class="card hero" style="--home:{color(home)};--away:{color(away)}">
      <div class="hero-top">
        <span class="eyebrow">Probabilité de victoire</span>
        <div class="hero-meta">
          <span>{icon("calendar")} {fr_date(game_date)}</span>
          <span>{icon("pin")} {full_name[home]} reçoit</span>
        </div>
      </div>
      <div class="duel" role="img" aria-label="{full_name[home]} {p_home:.0%}, {full_name[away]} {p_away:.0%}">
        <div class="side home {home_fav}">
          <div class="logo-wrap" style="--c:{color(home)}"><span class="halo"></span><img src="{logo(home)}" alt="{full_name[home]}"></div>
          <div><div class="tname">{full_name[home]}</div><div class="trec num">{h['RECORD']} · Domicile</div>
               <div class="prob {home_cls}">{count(round(p_home * 100))}<small>%</small></div></div>
        </div>
        <div class="vs"><div class="v">VS</div><div class="l">{fr_date(game_date, year=False)}</div></div>
        <div class="side away {away_fav}">
          <div class="logo-wrap" style="--c:{color(away)}"><span class="halo"></span><img src="{logo(away)}" alt="{full_name[away]}"></div>
          <div><div class="tname">{full_name[away]}</div><div class="trec num">{a['RECORD']} · Extérieur</div>
               <div class="prob {away_cls}">{count(round(p_away * 100))}<small>%</small></div></div>
        </div>
      </div>
      <div class="pbar" aria-hidden="true">
        <div class="h" style="width:{p_home:.1%};background:{color(home)}"></div>
        <div class="a" style="width:{p_away:.1%};background:{color(away)}"></div>
      </div>
      <div class="hero-foot">{verdict}{note}</div>
    </section>
    """

    b2b_h = '<span class="tag-b2b">B2B</span>' if h["B2B"] else ""
    b2b_a = '<span class="tag-b2b">B2B</span>' if a["B2B"] else ""
    kpis = (
        kpi(0, "Bilan saison", h["WIN_PCT_SEASON"], a["WIN_PCT_SEASON"], h["RECORD"], a["RECORD"], lambda v: v)
        + kpi(1, "10 derniers matchs", h["WIN_PCT_LAST10"], a["WIN_PCT_LAST10"], h["L10"], a["L10"], lambda v: v)
        + kpi(2, "Écart moyen · 10 derniers", h["PM_LAST10"], a["PM_LAST10"],
              f"{h['PM_LAST10']:+.1f}", f"{a['PM_LAST10']:+.1f}", lambda v: (v + 15) / 30)
        + kpi(3, "Jours de repos", h["REST_DAYS"], a["REST_DAYS"],
              f"{b2b_h}{h['REST_DAYS']} j", f"{b2b_a}{a['REST_DAYS']} j", lambda v: v / 4)
    )

    shown = table[(table.index < 10) | table["TEAM"].isin([home, away])]
    rows, prev = [], -1
    for n_row, (i, r) in enumerate(shown.iterrows()):
        if i != prev + 1:
            rows.append('<tr class="gap"><td colspan="6">···</td></tr>')
        prev = i
        rows.append(f"""
        <tr class="{'sel' if r.TEAM in (home, away) else ''} cascade" style="--d0:.6s;--i:{n_row}">
          <td class="rk">{i + 1}</td>
          <td><div class="club"><img src="{logo(r.TEAM)}" alt="">{full_name[r.TEAM]}</div></td>
          <td class="r">{r.W}-{r.L}</td>
          <td class="r">{r.PCT:.0%}</td>
          <td class="r {'pos' if r.PM >= 0 else 'neg'}">{r.PM:+.1f}</td>
          <td>{form_bars(r.LAST5)}</td>
        </tr>
        """)

    hot = table.sort_values(["L10", "PM"], ascending=False).head(5).reset_index(drop=True)
    hot_rows = "".join(
        f"""
        <div class="hot-row cascade" style="--d0:.9s;--i:{k}">
          <span class="rk">{k + 1}</span><img src="{logo(r.TEAM)}" alt="">
          <span class="n">{full_name[r.TEAM]}</span>
          <div class="track"><div style="width:{r.L10:.0%};background:{color(r.TEAM)};--i:{k + 3}"></div></div>
          <span class="p">{r.L10:.0%}</span>
        </div>
        """
        for k, r in hot.iterrows()
    )

    html(f"""
    <div class="dash">
      {hero}
      <div class="kpis">{kpis}</div>
      <div class="split">
        <section class="card" style="--d:.4s">
          <div class="card-head"><h3>Classement</h3><span>Saison {CURRENT_SEASON} · avant le {fr_date(game_date, year=False)}</span></div>
          <div class="tbl-wrap">
            <table class="std">
              <tr><th>#</th><th>Équipe</th><th class="r">V-D</th><th class="r">%</th><th class="r">Écart</th><th>Forme</th></tr>
              {"".join(rows)}
            </table>
          </div>
        </section>
        <div class="stack">
          <section class="card" style="--d:.5s">
            <div class="card-head"><h3>Derniers matchs</h3><span>{icon("clock", 13)} avant ce match</span></div>
            <div class="games">{game_card(0, home, h)}{game_card(1, away, a)}</div>
          </section>
          <section class="card" style="--d:.6s">
            <div class="card-head"><h3>En forme</h3><span>10 derniers matchs</span></div>
            <div class="hot">{hot_rows}</div>
          </section>
        </div>
      </div>
    </div>
    """)

    if DEBUG:
        with st.expander("Détail : les 10 valeurs envoyées au modèle"):
            st.dataframe(X.T.rename(columns={0: "valeur"}).round(3), use_container_width=True)

html("""
<div class="footer">
  CourtSide · projet personnel à but pédagogique, non affilié à la NBA. Logos © NBA et ses équipes.
</div>
""")