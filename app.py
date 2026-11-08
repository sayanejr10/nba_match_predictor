import os
from datetime import date, timedelta
from html import escape

import joblib
import pandas as pd
import streamlit as st
from nba_api.stats.endpoints import leaguegamefinder, scheduleleaguev2

# ----------------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------------
# Les matchs sont rangés par date américaine (comme sur NBA.com), les heures affichées en heure de Cotonou
US_TZ = "America/New_York"
LOCAL_TZ = "Africa/Lagos"            # même fuseau que Cotonou (UTC+1)
US_TODAY = pd.Timestamp.now(tz=US_TZ).date()
# Saison en cours, détectée automatiquement : une saison NBA commence en octobre
_start = US_TODAY.year if US_TODAY.month >= 10 else US_TODAY.year - 1
CURRENT_SEASON = f"{_start}-{str(_start + 1)[-2:]}"
# Mode développeur : affiché uniquement si on lance l'app avec COURTSIDE_DEBUG=1
DEBUG = os.environ.get("COURTSIDE_DEBUG") == "1"
NBA_LOGO = "https://cdn.nba.com/logos/leagues/logo-nba.svg"
TEAM_LOGO = "https://cdn.nba.com/logos/nba/{team_id}/global/L/logo.svg"
BASE_FEATURES = ["WIN_PCT_SEASON", "WIN_PCT_LAST10", "PM_LAST10", "REST_DAYS", "B2B"]
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

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
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "tv": '<rect x="2" y="7" width="20" height="15" rx="2"/><path d="m17 2-5 5-5-5"/>',
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


BALL_SVG = ('<svg viewBox="0 0 32 32" aria-hidden="true"><circle cx="16" cy="16" r="15" fill="#EA7A2B" stroke="#3A1D0B" stroke-width="1.4"/>'
            '<path d="M16 1v30M1 16h30M5.5 5.5c5 4 5 17 0 21M26.5 5.5c-5 4-5 17 0 21" fill="none" stroke="#3A1D0B" stroke-width="1.4"/></svg>')


def flaps(value: int, delay: float = .6) -> str:
    """Chiffres façon panneau d'arène : chaque chiffre est une plaque qui bascule jusqu'à sa valeur."""
    tiles = []
    for k, ch in enumerate(str(int(value))):
        d = int(ch)
        tiles.append(f'<span class="flap" style="--to:{d};--st:{max(d, 1)};--fd:{delay + k * .15:.2f}s">'
                     f'<span class="digit"></span><i class="leaf"></i></span>')
    return f'<span class="flaps">{"".join(tiles)}</span>'


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
/* Rail de probabilité + ballon */
.roll { position: relative; height: 32px; margin-top: 20px; --t-roll: 1.6s; }
.roll .rail { position: absolute; left: 0; right: 0; top: 11px; height: 10px; border-radius: 999px; overflow: hidden;
              background: var(--away); }
.roll .rail .fill { position: absolute; inset: 0 auto 0 0; width: var(--p); background: var(--home); }
.roll .pos { position: absolute; left: 0; top: 0; width: var(--p); height: 32px; }
.roll .ball-y { position: absolute; right: -16px; top: 0; width: 32px; height: 32px; }
.roll .ball { width: 32px; height: 32px; filter: drop-shadow(0 3px 4px rgba(15,23,42,.3)); }
.roll .ball svg { width: 100%; height: 100%; display: block; }

/* Chiffres d'arène */
.flaps { display: inline-flex; gap: .06em; vertical-align: top; }
.flap { position: relative; width: .7em; height: 1.08em; border-radius: .09em; background: #0F172A; color: #fff;
        display: grid; place-items: center; line-height: 1; perspective: 300px; overflow: hidden;
        box-shadow: inset 0 -.04em 0 rgba(255,255,255,.08), 0 .06em .16em rgba(15,23,42,.22); }
.flap::after { content: ""; position: absolute; left: 0; right: 0; top: 50%; height: .03em; background: rgba(0,0,0,.5); z-index: 2; }
.digit { counter-reset: n var(--n); --n: var(--to); position: relative; top: .02em; }
.digit::after { content: counter(n); }
.leaf { position: absolute; left: 0; right: 0; top: 0; height: 50%; opacity: 0; z-index: 1; transform-origin: bottom;
        backface-visibility: hidden; background: linear-gradient(180deg, #1E293B, #0F172A); }
.prob.dog .flap { background: #CBD5E1; color: #334155; }
.prob.dog .leaf { background: linear-gradient(180deg, #E2E8F0, #CBD5E1); }
.prob small { vertical-align: top; }
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
/* --o : décalage global. Il vaut la durée de l'intro quand elle est jouée, sinon 0. */
@property --n { syntax: '<integer>'; inherits: false; initial-value: 0; }
.count { counter-reset: n var(--n); --n: var(--to); animation: count var(--t-fill) var(--ease) calc(var(--o, 0s) + var(--cd, .5s)) both; }
.count::after { content: counter(n); }
@keyframes count { from { --n: 0; } }

@keyframes rise     { from { opacity: 0; transform: translateY(16px); } }
@keyframes in-left  { from { opacity: 0; transform: translateX(-40px); } }
@keyframes in-right { from { opacity: 0; transform: translateX(40px); } }
@keyframes pop      { from { opacity: 0; transform: scale(.6); } }
@keyframes fade     { from { opacity: 0; } }
@keyframes grow     { from { transform: scaleX(0); } }
@keyframes grow-y   { from { transform: scaleY(0); } }

.card, .st-key-pick { animation: rise var(--t-in) var(--ease) calc(var(--o, 0s) + var(--d, 0s)) both; }
.side.home { animation: in-left .8s var(--ease) calc(var(--o, 0s) + .25s) both; }
.side.away { animation: in-right .8s var(--ease) calc(var(--o, 0s) + .25s) both; }
.logo-wrap img { animation: pop .7s var(--spring) calc(var(--o, 0s) + .35s) both; }
.vs { animation: fade .6s ease calc(var(--o, 0s) + .5s) both; }
.hero-meta { animation: fade .6s ease calc(var(--o, 0s) + .3s) both; }
.verdict, .note { animation: pop .5s var(--spring) calc(var(--o, 0s) + 2.2s) both; }

/* 3. Chiffres d'arène : chaque plaque bascule autant de fois que la valeur du chiffre */
.digit { animation: count 1.3s steps(var(--st)) calc(var(--o, 0s) + var(--fd)) both; }
.leaf { animation: flip calc(1.3s / var(--st)) cubic-bezier(.55, 0, .75, .5) calc(var(--o, 0s) + var(--fd)) var(--st) both; }
@keyframes flip { from { opacity: 1; transform: rotateX(0deg); } to { opacity: 1; transform: rotateX(-180deg); } }

/* 2. Le ballon roule jusqu'à la probabilité, peint la couleur de l'équipe, puis rebondit */
.roll .rail .fill { transform-origin: left; animation: grow var(--t-roll) var(--ease) calc(var(--o, 0s) + .5s) both; }
.roll .pos { animation: roll-x var(--t-roll) var(--ease) calc(var(--o, 0s) + .5s) both; }
@keyframes roll-x { from { transform: translateX(-100%); } }
.roll .ball { animation: spin var(--t-roll) var(--ease) calc(var(--o, 0s) + .5s) both; }
@keyframes spin { from { transform: rotate(-2.5turn); } }
.roll .ball-y { animation: bounce .6s ease-out calc(var(--o, 0s) + .5s + var(--t-roll) - .1s) both; }
@keyframes bounce { 0%, 100% { transform: translateY(0); } 30% { transform: translateY(-12px); }
                    55% { transform: translateY(0); } 75% { transform: translateY(-4px); } }

/* Le favori émet une onde douce */
.side.fav .halo { animation: halo 2.6s ease-out calc(var(--o, 0s) + 2.4s) infinite; }
@keyframes halo { 0% { opacity: .55; transform: scale(.9); } 100% { opacity: 0; transform: scale(1.35); } }

/* Barres et listes en cascade */
.track div { transform-origin: left; animation: grow 1s var(--ease) calc(var(--o, 0s) + .7s + var(--i, 0) * 80ms) both; }
.cmp .val { animation: fade .5s ease calc(var(--o, 0s) + .8s + var(--i, 0) * 80ms) both; }
.cascade { animation: rise .45s var(--ease) calc(var(--o, 0s) + var(--d0, .6s) + var(--i) * 40ms) both; }
.form i { transform-origin: bottom; animation: grow-y .3s var(--ease) calc(var(--o, 0s) + 1s + var(--i) * 50ms) both; }
.model .gauge .fill { transform-origin: left; animation: grow var(--t-fill) var(--ease) calc(var(--o, 0s) + .3s) both; }
.model .gauge .mark { animation: fade .4s ease calc(var(--o, 0s) + 1.2s) both; }

/* 1. Intro « swish » : un tir, le filet, puis le tableau de bord */
.skip-cb { position: fixed; opacity: 0; pointer-events: none; }
.intro { position: fixed; inset: 0; z-index: 100000; cursor: pointer; overflow: hidden; display: block;
         background: radial-gradient(70% 60% at 50% 35%, #1B2A4A 0%, #0B1220 60%, #060A12 100%);
         animation: intro-out .55s ease-in 2.35s forwards; }
.skip-cb:checked + .intro { display: none; }
:root:has(.skip-cb:checked) { --o: 0s !important; }
@keyframes intro-out { to { opacity: 0; visibility: hidden; } }
.intro .floor { position: absolute; left: -10%; right: -10%; bottom: -30%; height: 60%; border-radius: 50%;
                border: 2px solid rgba(96,165,250,.18); }
.stage { position: absolute; left: 50%; top: 40%; width: 0; height: 0; }
.board { position: absolute; left: -95px; top: -118px; width: 190px; height: 120px; border: 4px solid #E2E8F0;
         border-radius: 6px; background: rgba(255,255,255,.06); z-index: 1; }
.board::after { content: ""; position: absolute; left: 62px; bottom: 6px; width: 58px; height: 42px; border: 3px solid #E2E8F0; }
.rim { position: absolute; left: -40px; top: -6px; width: 80px; height: 12px; border: 4px solid #F97316; border-radius: 50%; }
.rim.back { z-index: 1; clip-path: inset(0 0 50% 0); }
.rim.front { z-index: 3; clip-path: inset(50% 0 0 0); }
.net { position: absolute; left: -36px; top: 2px; width: 72px; height: 62px; z-index: 3; transform-origin: top; }
.net svg { width: 100%; height: 100%; display: block; }
.shot { position: absolute; left: 0; top: 0; z-index: 2; }
.shot-y, .shot-drop, .shot-ball { position: absolute; left: 0; top: 0; }
.shot-ball { width: 46px; height: 46px; margin: -30px 0 0 -23px; }
.shot-ball svg { width: 100%; height: 100%; display: block; }
.intro-title { position: absolute; left: 0; right: 0; top: calc(40% + 110px); text-align: center;
               font-family: var(--display); font-size: 46px; color: #fff; letter-spacing: 2px; text-transform: uppercase; }
.intro-title span { color: #60A5FA; }
.intro-sub { position: absolute; left: 0; right: 0; top: calc(40% + 170px); text-align: center; color: #94A3B8;
             font-size: 15px; letter-spacing: 3px; text-transform: uppercase; }
.intro-skip { position: absolute; right: 24px; bottom: 20px; color: #64748B; font-size: 13px; }

/* Trajectoire : X linéaire, Y en parabole (monte en ralentissant, retombe en accélérant) */
.shot { animation: shot-x 1.05s linear .25s both; }
@keyframes shot-x { from { transform: translateX(-42vw); } to { transform: translateX(0); } }
.shot-y { animation: shot-y 1.05s .25s both; }
@keyframes shot-y {
  0%   { transform: translateY(55vh); animation-timing-function: cubic-bezier(.2, .7, .4, 1); }
  58%  { transform: translateY(-24vh); animation-timing-function: cubic-bezier(.6, 0, .8, .4); }
  100% { transform: translateY(0); } }
.shot-drop { animation: shot-drop .45s cubic-bezier(.5, 0, 1, 1) 1.3s forwards; }
@keyframes shot-drop { to { transform: translateY(95px) scale(.88); opacity: 0; } }
.shot-ball { animation: shot-spin 1.5s linear .25s both; }
@keyframes shot-spin { from { transform: rotate(-540deg); } }
.net { animation: swish .55s ease-out 1.3s both; }
@keyframes swish { 0% { transform: scaleY(1) scaleX(1); } 35% { transform: scaleY(1.32) scaleX(.86); }
                   65% { transform: scaleY(.92) scaleX(1.04); } 100% { transform: none; } }
.intro-title { animation: title-in .6s var(--spring) 1.5s both; }
@keyframes title-in { from { opacity: 0; transform: scale(.7) translateY(10px); } }
.intro-sub { animation: fade .5s ease 1.75s both; }
.intro-skip { animation: fade .4s ease .4s both; }


/* ===================== CALENDRIER DES MATCHS ===================== */
.st-key-datebar { background: var(--card); border: 1px solid var(--border) !important; border-radius: var(--radius);
                  box-shadow: var(--shadow); padding: 10px 14px !important; margin-top: 4px;
                  animation: rise var(--t-in) var(--ease) var(--o, 0s) both; }
.st-key-datebar [data-baseweb="input"] { border-radius: 8px !important; }
.st-key-datebar button { border-radius: 8px !important; }
.day-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px; margin: 22px 0 12px; }
.day-head h2 { font-family: var(--display); font-weight: 400 !important; font-size: 24px; text-transform: uppercase;
               letter-spacing: .5px; color: var(--fg); margin: 0; padding: 0; }
.day-head h2 span { color: var(--primary); }
.day-head .sub { font-size: 13px; color: var(--subtle); display: inline-flex; align-items: center; gap: 6px; }

.ggrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(255px, 1fr)); gap: 14px; }
a.gcard, a.gcard:hover, a.gcard:visited { text-decoration: none !important; color: inherit !important; }
.gcard { display: block; background: var(--card); border: 1px solid var(--border); border-radius: var(--radius);
         padding: 12px 14px 12px; box-shadow: var(--shadow); cursor: pointer;
         transition: transform var(--t-fast) var(--ease), box-shadow var(--t-fast) ease, border-color var(--t-fast) ease; }
.gcard:hover { transform: translateY(-3px); box-shadow: var(--shadow-hover); border-color: #93C5FD; }
.gcard:focus-visible { outline: 3px solid #93C5FD; outline-offset: 2px; }
.gcard.sel { border-color: var(--primary); box-shadow: 0 0 0 3px rgba(30,64,175,.15), var(--shadow-hover); }
.gtop { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--subtle); margin-bottom: 8px; }
.gtime { font-family: var(--display); font-size: 15px; color: var(--fg); letter-spacing: .5px; }
.gfinal { font-weight: 700; color: var(--muted); text-transform: uppercase; letter-spacing: 1px; font-size: 11px; }
.glive { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; color: var(--negative);
         text-transform: uppercase; letter-spacing: 1px; font-size: 11px; }
.glive::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: var(--negative);
                 animation: blink 1.2s ease-in-out infinite; }
@keyframes blink { 50% { opacity: .25; } }
.gline { display: grid; grid-template-columns: 30px 1fr auto; align-items: center; gap: 10px; padding: 4px 0; color: var(--muted); }
.gline img { width: 30px; height: 30px; object-fit: contain; }
.gline .t { font-weight: 600; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.gline .t small { display: block; font-weight: 500; font-size: 11px; color: var(--subtle); }
.gline .v { font-family: var(--display); font-size: 20px; font-variant-numeric: tabular-nums; }
.gline .v small { font-size: 12px; }
.gline.lead { color: var(--fg); }
.gfoot { margin-top: 8px; padding-top: 8px; border-top: 1px solid var(--soft); font-size: 12px; color: var(--muted);
         display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; font-weight: 600; font-size: 12px; }
.chip.ok { background: #DCFCE7; color: #14532D; }
.chip.miss { background: #FEE2E2; color: #991B1B; }
.chip.fav { background: var(--primary-soft); color: #1E3A8A; }
.chip.na { background: var(--soft); color: var(--muted); }
.gfoot .see { color: var(--primary); font-weight: 600; }

.empty { text-align: center; padding: 34px 20px; color: var(--muted); }
.empty b { display: block; font-family: var(--display); font-weight: 400; font-size: 18px; color: var(--fg); margin-bottom: 6px; }
.hint { display: flex; align-items: center; gap: 14px; padding: 16px 20px; margin-top: 18px; color: var(--muted); font-size: 14px; }
.hint .dot { width: 36px; height: 36px; flex-shrink: 0; }
.hint .dot svg { width: 100%; height: 100%; }
.detail-head { display: flex; justify-content: space-between; align-items: center; margin: 30px 0 12px; }
.detail-head h2 { font-family: var(--display); font-weight: 400 !important; font-size: 20px; text-transform: uppercase;
                  letter-spacing: .5px; color: var(--fg); margin: 0; padding: 0; }
a.back, a.back:visited { font-size: 13px; color: var(--primary) !important; text-decoration: none !important; font-weight: 600; }
a.back:hover { text-decoration: underline !important; }
.result { display: inline-flex; align-items: center; gap: 10px; font-size: 14px; color: var(--fg); font-weight: 600; }
.result b { font-family: var(--display); font-weight: 400; font-size: 18px; }
.gcard.cascade { animation-duration: .5s; }

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
  .intro { display: none !important; }
  .leaf { display: none; }
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
    # Sécurité : on ne garde que des codes d'équipe au format attendu (2 à 4 majuscules),
    # car ils sont ensuite insérés dans le HTML de la page
    opp = df["MATCHUP"].astype(str).str.split().str[-1]
    df = df[df["TEAM_ABBREVIATION"].astype(str).str.fullmatch(r"[A-Z]{2,4}") & opp.str.fullmatch(r"[A-Z]{2,4}")]
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"])
    df["WIN"] = (df["WL"] == "W").astype(int)
    return df.sort_values("GAME_DATE")


def team_state(games, team, game_date, last_date=None):
    """Les features d'une équipe AVANT le match : seulement les matchs joués avant game_date.
    last_date : date de son match précédent selon le calendrier (sert aux jours de repos)."""
    past = games[(games["TEAM_ABBREVIATION"] == team) & (games["GAME_DATE"] < game_date)]
    if past.empty:
        return None
    last10 = past.tail(10)
    previous = last_date if last_date is not None else past["GAME_DATE"].iloc[-1]
    rest = min((game_date - previous).days, 4)
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
    if not rows:  # jour d'ouverture : aucun match encore joué
        return pd.DataFrame(columns=["TEAM", "GP", "W", "L", "PCT", "PM", "L10", "LAST5"])
    return pd.DataFrame(rows).sort_values(["PCT", "PM"], ascending=False).reset_index(drop=True)


def latest_scores(games, n=16):
    """Les derniers scores de la ligue pour le bandeau (une entrée par match, côté domicile)."""
    home_rows = games[games["MATCHUP"].str.contains("vs.")].tail(n)
    return "".join(
        f"<span>{r.MATCHUP.split()[-1]} <b>{int(r.PTS - r.PLUS_MINUS)}</b> – <b>{int(r.PTS)}</b> {r.TEAM_ABBREVIATION}</span>"
        for r in home_rows.itertuples()
    )


def fr_day(d):
    """« Sunday, November 8 »"""
    full_months = ["January", "February", "March", "April", "May", "June", "July", "August",
                   "September", "October", "November", "December"]
    return f"{WEEKDAYS[d.weekday()]}, {full_months[d.month - 1]} {d.day}"


def fr_date(d, year=True):
    return f"{MONTHS[d.month - 1]} {d.day}" + (f", {d.year}" if year else "")


def form_bars(results):
    label = ", ".join("win" if r == "W" else "loss" for r in results)
    bars = "".join(f'<i class="{r}" style="--i:{j}"></i>' for j, r in enumerate(results))
    return f'<span class="form" role="img" aria-label="Last 5 games: {label}">{bars}</span>'


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
    result = "Win" if g["wl"] == "W" else "Loss"
    return (f'<div class="game cascade" style="--d0:.7s;--i:{k}"><div class="g-head"><span>{team} last game · {result}</span>'
            f'<span>{fr_date(g["date"], year=False)}</span></div>{body}</div>')


# ----------------------------------------------------------------------------
# Calendrier de la saison
# ----------------------------------------------------------------------------
@st.cache_data(ttl=3600)  # le calendrier (horaires, scores, statuts) est rafraîchi au maximum une fois par heure
def load_schedule(season):
    df = scheduleleaguev2.ScheduleLeagueV2(league_id="00", season=season, timeout=60).get_data_frames()[0]
    df["gameId"] = df["gameId"].astype(str).str.zfill(10)
    # 002 = saison régulière, 004 = play-offs, 005 = play-in (on écarte la présaison et le All-Star Game)
    df = df[df["gameId"].str[:3].isin(["002", "004", "005"])].drop_duplicates("gameId").copy()
    # Sécurité : identifiants de match uniquement en chiffres, codes d'équipe au format attendu
    df = df[df["gameId"].str.fullmatch(r"\d{10}")]
    df = df[df["homeTeam_teamTricode"].astype(str).str.fullmatch(r"[A-Z]{2,4}")
            & df["awayTeam_teamTricode"].astype(str).str.fullmatch(r"[A-Z]{2,4}")]
    df["US_DATE"] = pd.to_datetime(df["gameDateEst"].astype(str).str[:10], format="mixed", errors="coerce")
    df["START_UTC"] = pd.to_datetime(df["gameDateTimeUTC"], utc=True, errors="coerce")
    df["gameStatus"] = pd.to_numeric(df["gameStatus"], errors="coerce").fillna(1).astype(int)
    for side in ("homeTeam", "awayTeam"):
        df[f"{side}_score"] = pd.to_numeric(df[f"{side}_score"], errors="coerce").fillna(0).astype(int)
    return df.dropna(subset=["US_DATE"]).sort_values(["US_DATE", "START_UTC"]).reset_index(drop=True)


# ----------------------------------------------------------------------------
# Chargement
# ----------------------------------------------------------------------------
bundle = load_model()
model, features = bundle["model"], bundle["features"]
try:
    games = load_season_games(CURRENT_SEASON)
    schedule = load_schedule(CURRENT_SEASON)
except Exception:  # API lente, indisponible ou réponse inattendue
    if DEBUG:
        raise  # en mode développeur, on veut voir l'erreur complète
    st.error("Live NBA data is temporarily unavailable. Please try again in a few minutes.")
    st.stop()

# Équipes : identifiant (pour les logos) et nom complet, tirés du calendrier
teams_info = pd.concat([
    schedule[[f"{s}_teamTricode", f"{s}_teamId", f"{s}_teamCity", f"{s}_teamName"]]
    .set_axis(["TRI", "ID", "CITY", "NAME"], axis=1)
    for s in ("homeTeam", "awayTeam")
]).drop_duplicates("TRI").set_index("TRI")
# escape() neutralise les caractères spéciaux (<, >, ", &) : un texte de l'API ne peut pas devenir du code
full_name = {t: escape(f"{c} {n}") for t, c, n in zip(teams_info.index, teams_info["CITY"], teams_info["NAME"])}

# Dates de tous les matchs prévus de chaque équipe (pour calculer les jours de repos)
team_dates = {
    t: sorted(set(schedule.loc[(schedule["homeTeam_teamTricode"] == t) | (schedule["awayTeam_teamTricode"] == t), "US_DATE"]))
    for t in teams_info.index
}


def logo(abbr):
    return TEAM_LOGO.format(team_id=int(teams_info.loc[abbr, "ID"])) if abbr in teams_info.index else NBA_LOGO


def color(abbr):
    return TEAM_COLORS.get(abbr, "#1E40AF")


def previous_game(team, day):
    before = [d for d in team_dates.get(team, []) if d < day]
    return before[-1] if before else None


def predict(home_t, away_t, day):
    """Probabilité de victoire de l'équipe à domicile, avec la forme des deux équipes avant ce jour."""
    hs = team_state(games, home_t, day, previous_game(home_t, day))
    as_ = team_state(games, away_t, day, previous_game(away_t, day))
    if hs is None or as_ is None:
        return None, hs, as_
    x = pd.DataFrame([{f"{k}_HOME": hs[k] for k in BASE_FEATURES} | {f"{k}_AWAY": as_[k] for k in BASE_FEATURES}])[features]
    return float(model.predict_proba(x)[0, 1]), hs, as_


def local_time(g):
    """Heure de Cotonou. Si le match tombe le lendemain à Cotonou, on ajoute le jour (« lun. 02:30 »)."""
    if pd.isna(g.START_UTC):
        return "Time TBD"
    t = g.START_UTC.tz_convert(LOCAL_TZ)
    hhmm = t.strftime("%H:%M")
    return hhmm if t.date() == g.US_DATE.date() else f"{WEEKDAYS[t.weekday()][:3]} {hhmm}"


def pct(p):
    """Pourcentage affiché entre 1 et 99 : le modèle n'est jamais certain à 100 %."""
    return min(99, max(1, round(p * 100)))


def link(day, game_id=None):
    """Lien interne : garde la date, ouvre un match, et ne rejoue pas l'intro."""
    return f"?date={day.isoformat()}" + (f"&match={game_id}" if game_id else "") + "&intro=0"


# ----------------------------------------------------------------------------
# Date choisie et match sélectionné (dans l'adresse de la page : liens partageables)
# ----------------------------------------------------------------------------
qp = st.query_params


def _parse(s):
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return None


if "day" not in st.session_state:
    st.session_state["day"] = _parse(qp.get("date")) or US_TODAY


def _clear_match():
    if "match" in st.query_params:
        del st.query_params["match"]


def _shift(n):
    st.session_state["day"] = st.session_state["day"] + timedelta(days=n)
    _clear_match()


# ----------------------------------------------------------------------------
# Intro « swish » : une seule fois par visite, jamais en revenant d'un clic sur un match
# ----------------------------------------------------------------------------
if not st.session_state.get("intro_done") and qp.get("intro") != "0":
    st.session_state["intro_done"] = True
    net_lines = "".join(f'<path d="M{4 + k * 8} 2 L{10 + k * 6.5} 58"/><path d="M{68 - k * 8} 2 L{62 - k * 6.5} 58"/>' for k in range(5))
    html(f"""
    <style>:root {{ --o: 2.3s; }}</style>
    <input type="checkbox" id="skip-intro" class="skip-cb" aria-hidden="true" tabindex="-1">
    <label for="skip-intro" class="intro" aria-hidden="true">
      <div class="floor"></div>
      <div class="stage">
        <div class="board"></div>
        <div class="rim back"></div>
        <div class="shot"><div class="shot-y"><div class="shot-drop"><div class="shot-ball">{BALL_SVG}</div></div></div></div>
        <div class="rim front"></div>
        <div class="net"><svg viewBox="0 0 72 62" fill="none" stroke="#E2E8F0" stroke-width="1.6" stroke-linecap="round">
          {net_lines}<path d="M6 16 H66 M9 30 H63 M11 44 H61"/></svg></div>
      </div>
      <div class="intro-title">Court<span>Side</span></div>
      <div class="intro-sub">NBA Predictions</div>
      <div class="intro-skip">Click to skip</div>
    </label>
    """)

# ----------------------------------------------------------------------------
# Barre de navigation + bandeau des scores
# ----------------------------------------------------------------------------
scores = latest_scores(games)
html(f"""
<nav class="nav">
  <div class="brand">
    <img src="{NBA_LOGO}" alt="NBA">
    <div><div class="wm">Court<span>Side</span></div><div class="tl">NBA game predictions powered by machine learning</div></div>
  </div>
  <div class="nav-meta">
    <span class="nav-pill">{icon("calendar", 14)} Season <b>{CURRENT_SEASON}</b></span>
    <span class="nav-pill">{icon("target", 14)} Accuracy <b>67%</b></span>
  </div>
</nav>
<div class="ticker" aria-hidden="true"><div class="ticker-track">
  <span class="tag">Latest scores</span>{scores}<span class="tag">Latest scores</span>{scores}
</div></div>
""")

# ----------------------------------------------------------------------------
# Choix de la date
# ----------------------------------------------------------------------------
with st.container(key="datebar"):
    c_prev, c_date, c_next, c_today = st.columns([1, 2.2, 1, 1], vertical_alignment="bottom")
    c_prev.button("Previous day", icon=":material/chevron_left:", on_click=_shift, args=(-1,), use_container_width=True)
    c_date.date_input("Game date (US date)", key="day", format="MM/DD/YYYY", on_change=_clear_match)
    c_next.button("Next day", icon=":material/chevron_right:",
                  on_click=_shift, args=(1,), use_container_width=True)
    c_today.button("Today", on_click=lambda: (st.session_state.update(day=US_TODAY), _clear_match()),
                   use_container_width=True)

day = st.session_state["day"]
day_ts = pd.Timestamp(day)
st.query_params["date"] = day.isoformat()
selected = st.query_params.get("match")

day_games = schedule[schedule["US_DATE"] == day_ts]
n = len(day_games)

# ----------------------------------------------------------------------------
# Grille des matchs du jour
# ----------------------------------------------------------------------------
def game_tile(k, g):
    hm, aw = g.homeTeam_teamTricode, g.awayTeam_teamTricode
    p, _, _ = predict(hm, aw, day_ts)
    status = g.gameStatus
    if status == 3:
        top = '<span class="gfinal">Final</span>'
    elif status == 2:
        top = '<span class="glive">Live</span>'
    else:
        top = f'<span class="gtime">{local_time(g)}</span>'

    def line(t, side_p, score, lead):
        right = (f'<span class="v">{score}</span>' if status >= 2
                 else (f'<span class="v">{pct(side_p)}<small>%</small></span>' if side_p is not None else '<span class="v">–</span>'))
        return (f'<div class="gline {"lead" if lead else ""}"><img src="{logo(t)}" alt="">'
                f'<span class="t">{t}<small>{full_name.get(t, t)}</small></span>{right}</div>')

    hs, as_ = g.homeTeam_score, g.awayTeam_score
    if status >= 2:
        home_lead, away_lead = hs > as_, as_ > hs
    else:
        home_lead = p is not None and p >= .5
        away_lead = p is not None and p < .5
    # Convention des tableaux de scores NBA : l'équipe à l'extérieur en haut
    body = line(aw, None if p is None else 1 - p, as_, away_lead) + line(hm, p, hs, home_lead)

    if p is None:
        foot = '<span class="chip na">Not enough games yet</span>'
    elif status == 3:
        ok = (p >= .5) == (hs > as_)
        foot = (f'<span class="chip ok">{icon("check", 12)} Correct pick</span>' if ok
                else f'<span class="chip miss">{icon("x", 12)} Missed pick</span>')
    else:
        fav_t, fav_p = (hm, p) if p >= .5 else (aw, 1 - p)
        foot = f'<span class="chip fav">Favorite: {fav_t} {pct(fav_p)}%</span>'
    sel = "sel" if g.gameId == selected else ""
    return (f'<a class="gcard cascade {sel}" href="{link(day, g.gameId)}" target="_self" style="--d0:.15s;--i:{k}"'
            f' aria-label="{full_name.get(aw, aw)} at {full_name.get(hm, hm)}, see the prediction">'
            f'<div class="gtop">{top}<span>{escape(g.arenaCity) if isinstance(g.arenaCity, str) else ""}</span></div>'
            f'{body}<div class="gfoot">{foot}<span class="see">View</span></div></a>')


table = standings(games, day_ts)
hot = table.sort_values(["L10", "PM"], ascending=False).head(5).reset_index(drop=True)
hot_rows = "".join(
    f"""
    <div class="hot-row cascade" style="--d0:.9s;--i:{k}">
      <span class="rk">{k + 1}</span><img src="{logo(r.TEAM)}" alt="">
      <span class="n">{full_name.get(r.TEAM, r.TEAM)}</span>
      <div class="track"><div style="width:{r.L10:.0%};background:{color(r.TEAM)};--i:{k + 3}"></div></div>
      <span class="p">{r.L10:.0%}</span>
    </div>
    """
    for k, r in hot.iterrows()
)
model_card = f"""
<div class="card model" style="--d:.1s;margin-top:0">
  <div class="eyebrow">The model</div>
  <div class="big num">{count(67)}%</div>
  <div class="cap">correct predictions on 2,418 unseen games</div>
  <div class="gauge"><div class="fill" style="width:67%"></div><div class="mark" style="left:55%"></div></div>
  <div class="legend"><span>Baseline 55%</span><span>Model 67%</span></div>
  <dl>
    <dt>Algorithm</dt><dd>Logistic regression</dd>
    <dt>Features</dt><dd>10</dd>
    <dt>Training set</dt><dd class="num">13,023 games</dd>
    <dt>Seasons</dt><dd>2015 to 2026</dd>
  </dl>
</div>
"""


def standings_card(highlight=()):
    if table.empty:
        return ('<section class="card empty" style="--d:.4s"><b>Standings</b>'
                'The standings will appear once the first games of the season have been played.</section>')
    shown = table[(table.index < 10) | table["TEAM"].isin(list(highlight))]
    rows, prev = [], -1
    for n_row, (i, r) in enumerate(shown.iterrows()):
        if i != prev + 1:
            rows.append('<tr class="gap"><td colspan="6">···</td></tr>')
        prev = i
        rows.append(f"""
        <tr class="{'sel' if r.TEAM in highlight else ''} cascade" style="--d0:.6s;--i:{n_row}">
          <td class="rk">{i + 1}</td>
          <td><div class="club"><img src="{logo(r.TEAM)}" alt="">{full_name.get(r.TEAM, r.TEAM)}</div></td>
          <td class="r">{r.W}-{r.L}</td>
          <td class="r">{r.PCT:.0%}</td>
          <td class="r {'pos' if r.PM >= 0 else 'neg'}">{r.PM:+.1f}</td>
          <td>{form_bars(r.LAST5)}</td>
        </tr>
        """)
    return f"""
    <section class="card" style="--d:.4s">
      <div class="card-head"><h3>Standings</h3><span>Season {CURRENT_SEASON} · before {fr_date(day_ts, year=False)}</span></div>
      <div class="tbl-wrap">
        <table class="std">
          <tr><th>#</th><th>Team</th><th class="r">W-L</th><th class="r">Win %</th><th class="r">Diff</th><th>Form</th></tr>
          {"".join(rows)}
        </table>
      </div>
    </section>
    """


def render_grid(title=None):
    html(f"""
    <div class="day-head">
      <h2>{title or 'Games on <span>' + fr_day(day) + '</span>'}</h2>
      <span class="sub">{icon("clock", 13)} {n} game{"s" if n != 1 else ""} · times shown in Cotonou time</span>
    </div>
    """)
    if n == 0:
        html(f"""
        <div class="card empty">
          <b>No games on this day</b>
          Use the buttons to go to the previous or next day.
        </div>
        """)
    else:
        html(f'<div class="ggrid">{"".join(game_tile(k, g) for k, g in enumerate(day_games.itertuples()))}</div>')



match = day_games[day_games["gameId"] == selected] if selected else day_games.iloc[0:0]

# ----------------------------------------------------------------------------
# Aucun match sélectionné : invitation à cliquer + vue d'ensemble
# ----------------------------------------------------------------------------
if match.empty:
    render_grid()
    if n:
        html(f"""
        <div class="card hint" style="--d:.3s">
          <span class="dot">{BALL_SVG}</span>
          Click a game to see the full prediction: win probabilities, head-to-head comparison and recent results.
        </div>
        """)
    html(f"""
    <div class="split" style="margin-top:18px">
      {standings_card()}
      <div class="stack">
        <section class="card" style="--d:.5s">
          <div class="card-head"><h3>Hot teams</h3><span>Last 10 games</span></div>
          <div class="hot">{hot_rows or '<div class="empty">No games played yet.</div>'}</div>
        </section>
        {model_card}
      </div>
    </div>
    """)

# ----------------------------------------------------------------------------
# Match sélectionné : le pronostic détaillé
# ----------------------------------------------------------------------------
else:
    g = next(match.itertuples())
    home, away = g.homeTeam_teamTricode, g.awayTeam_teamTricode
    p_home, h, a = predict(home, away, day_ts)

    html(f"""
    <div class="detail-head" style="margin-top:22px">
      <h2>Prediction · <span style="color:var(--primary)">{full_name[away]} at {full_name[home]}</span></h2>
      <a class="back" href="{link(day)}" target="_self">Close prediction</a>
    </div>
    """)

    if p_home is None:
        html("""
        <div class="card empty">
          <b>No prediction for this game yet</b>
          One of the two teams hasn't played a game before this date, so the model has no form to analyze.
        </div>
        """)
        st.stop()

    p_away = 1 - p_home
    fav, p_fav = (home, p_home) if p_home >= 0.5 else (away, p_away)
    if p_fav < 0.55:
        verdict = f'<span class="verdict even">{icon("scale")} Toss-up, no clear favorite</span>'
    elif p_fav < 0.65:
        verdict = f'<span class="verdict lean">{icon("trend")} Slight edge: {full_name[fav]}</span>'
    else:
        verdict = f'<span class="verdict strong">{icon("trend")} {full_name[fav]} strong favorite</span>'

    # Match terminé : on montre le score final et si le modèle avait raison
    if g.gameStatus == 3:
        ok = (p_home >= .5) == (g.homeTeam_score > g.awayTeam_score)
        chip = (f'<span class="chip ok">{icon("check", 12)} The model got it right</span>' if ok
                else f'<span class="chip miss">{icon("x", 12)} The model got it wrong</span>')
        verdict += (f'<span class="result">Final score <b>{away} {g.awayTeam_score} – {g.homeTeam_score} {home}</b>'
                    f'{chip}</span>')

    note = ""
    if min(h["GAMES"], a["GAMES"]) < 10:
        note = (f'<span class="note">{icon("alert", 14)} Early season: {h["GAMES"]} and {a["GAMES"]} '
                f'games played, less reliable prediction</span>')

    home_cls, away_cls = ("", "dog") if p_home >= 0.5 else ("dog", "")
    home_fav, away_fav = ("fav", "") if p_home >= 0.5 else ("", "fav")
    arena = escape(g.arenaName) if isinstance(g.arenaName, str) and g.arenaName else full_name[home]

    hero = f"""
    <section class="card hero" style="--home:{color(home)};--away:{color(away)}">
      <div class="hero-top">
        <span class="eyebrow">Win probability</span>
        <div class="hero-meta">
          <span>{icon("calendar")} {fr_date(day_ts)} · {local_time(g)} Cotonou time</span>
          <span>{icon("pin")} {arena}</span>
        </div>
      </div>
      <div class="duel" role="img" aria-label="{full_name[home]} {p_home:.0%}, {full_name[away]} {p_away:.0%}">
        <div class="side home {home_fav}">
          <div class="logo-wrap" style="--c:{color(home)}"><span class="halo"></span><img src="{logo(home)}" alt="{full_name[home]}"></div>
          <div><div class="tname">{full_name[home]}</div><div class="trec num">{h['RECORD']} · Home</div>
               <div class="prob {home_cls}">{flaps(pct(p_home), .55)}<small>%</small></div></div>
        </div>
        <div class="vs"><div class="v">VS</div><div class="l">{fr_date(day_ts, year=False)}</div></div>
        <div class="side away {away_fav}">
          <div class="logo-wrap" style="--c:{color(away)}"><span class="halo"></span><img src="{logo(away)}" alt="{full_name[away]}"></div>
          <div><div class="tname">{full_name[away]}</div><div class="trec num">{a['RECORD']} · Away</div>
               <div class="prob {away_cls}">{flaps(100 - pct(p_home), .7)}<small>%</small></div></div>
        </div>
      </div>
      <div class="roll" aria-hidden="true" style="--p:{p_home:.1%}">
        <div class="rail"><div class="fill"></div></div>
        <div class="pos"><div class="ball-y"><div class="ball">{BALL_SVG}</div></div></div>
      </div>
      <div class="hero-foot">{verdict}{note}</div>
    </section>
    """

    b2b_h = '<span class="tag-b2b">B2B</span>' if h["B2B"] else ""
    b2b_a = '<span class="tag-b2b">B2B</span>' if a["B2B"] else ""
    kpis = (
        kpi(0, "Season record", h["WIN_PCT_SEASON"], a["WIN_PCT_SEASON"], h["RECORD"], a["RECORD"], lambda v: v)
        + kpi(1, "Last 10 games", h["WIN_PCT_LAST10"], a["WIN_PCT_LAST10"], h["L10"], a["L10"], lambda v: v)
        + kpi(2, "Avg point diff · last 10", h["PM_LAST10"], a["PM_LAST10"],
              f"{h['PM_LAST10']:+.1f}", f"{a['PM_LAST10']:+.1f}", lambda v: (v + 15) / 30)
        + kpi(3, "Days of rest", h["REST_DAYS"], a["REST_DAYS"],
              f"{b2b_h}{h['REST_DAYS']}d", f"{b2b_a}{a['REST_DAYS']}d", lambda v: v / 4)
    )

    html(f"""
    <div class="dash">
      {hero}
      <div class="kpis">{kpis}</div>
      <div class="split">
        {standings_card((home, away))}
        <div class="stack">
          <section class="card" style="--d:.5s">
            <div class="card-head"><h3>Last games</h3><span>{icon("clock", 13)} before this game</span></div>
            <div class="games">{game_card(0, home, h)}{game_card(1, away, a)}</div>
          </section>
          <section class="card" style="--d:.6s">
            <div class="card-head"><h3>Hot teams</h3><span>Last 10 games</span></div>
            <div class="hot">{hot_rows or '<div class="empty">No games played yet.</div>'}</div>
          </section>
        </div>
      </div>
    </div>
    """)

    render_grid(f"Other games on <span>{fr_day(day)}</span>")

    if DEBUG:
        row = {f"{k}_HOME": h[k] for k in BASE_FEATURES} | {f"{k}_AWAY": a[k] for k in BASE_FEATURES}
        X = pd.DataFrame([row])[features]
        with st.expander("Debug: the 10 values sent to the model"):
            st.dataframe(X.T.rename(columns={0: "value"}).round(3), use_container_width=True)

html("""
<div class="footer">
  CourtSide · personal learning project, not affiliated with the NBA. Logos © NBA and its teams.
</div>
""")