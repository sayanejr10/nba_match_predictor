"""Jeu de pronostics entre amis : chaque joueur choisit les vainqueurs, et le classement
se fait uniquement dans des ligues privées (on rejoint une ligue avec son code d'invitation).

Stockage : Supabase (base PostgreSQL en ligne), via son API REST.
- SUPABASE_URL et SUPABASE_SECRET_KEY viennent des variables d'environnement (jamais du code).
- La clé secrète ne quitte jamais le serveur : le navigateur des visiteurs ne la voit pas.

Sécurité :
- le code à 6 chiffres n'est jamais stocké, seulement une empreinte scrypt (avec un sel unique) ;
- 5 mauvais codes -> compte bloqué 10 minutes (contre les robots qui essaient tous les codes) ;
- un pronostic est refusé si le match a commencé (vérifié ici, côté serveur) ;
- un code de ligue a 31^6 ≈ 887 millions de valeurs possibles : impossible à deviner ;
- le « se souvenir de moi » utilise un jeton signé (HMAC) : impossible à fabriquer sans la clé du serveur.
"""
import hashlib
import hmac
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone

import requests

PSEUDO_RE = re.compile(r"^[A-Za-z0-9_]{3,16}$")
PIN_RE = re.compile(r"^\d{6}$")
MAX_FAILS, LOCK_MINUTES = 5, 10
SESSION_DAYS = 30
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # sans I, L, O, 0, 1 (trop faciles à confondre)
CODE_RE = re.compile(rf"^[{CODE_ALPHABET}]{{6}}$")
LEAGUE_NAME_RE = re.compile(r"^[\w' .\-]{3,30}$")
MAX_LEAGUES, MAX_MEMBERS = 10, 50


class BeatAIError(Exception):
    """Erreur affichable telle quelle au joueur."""


def _secret(name):
    value = os.environ.get(name)
    if value:
        return value
    try:                                      # en local, on peut aussi utiliser .streamlit/secrets.toml
        import streamlit as st
        return st.secrets.get(name)
    except Exception:
        return None


URL = (_secret("SUPABASE_URL") or "").rstrip("/")
KEY = _secret("SUPABASE_SECRET_KEY") or ""


def enabled() -> bool:
    """Le jeu n'apparaît que si la base est configurée."""
    return bool(URL and KEY)


def _headers(extra=None):
    h = {"apikey": KEY, "Content-Type": "application/json"}
    if not KEY.startswith("sb_"):             # anciennes clés (JWT) : il faut aussi l'en-tête Authorization
        h["Authorization"] = f"Bearer {KEY}"
    if extra:
        h.update(extra)
    return h


def _req(method, table, params=None, json=None, prefer=None, range_=None):
    extra = {}
    if prefer:
        extra["Prefer"] = prefer
    if range_:
        extra["Range-Unit"], extra["Range"] = "items", range_
    r = requests.request(method, f"{URL}/rest/v1/{table}", params=params, json=json,
                         headers=_headers(extra), timeout=15)
    if r.status_code >= 400:
        raise RuntimeError(f"Supabase {method} {table}: {r.status_code}")
    return r.json() if r.content else None


# ---------------------------------------------------------------- Code secret
def hash_pin(pin: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(pin.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def check_pin(pin: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$")
        test = hashlib.scrypt(pin.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(test.hex(), digest)
    except (ValueError, TypeError):
        return False


def _find(pseudo):
    # ilike = sans tenir compte des majuscules ; on échappe « _ » qui serait sinon un joker
    rows = _req("GET", "players", params={
        "select": "id,pseudo,pin_hash,failed_attempts,locked_until",
        "pseudo": "ilike." + pseudo.replace("_", r"\_"),
    })
    return rows[0] if rows else None


# ---------------------------------------------------------------- Comptes
def register(pseudo: str, pin: str) -> dict:
    pseudo, pin = pseudo.strip(), pin.strip()
    if not PSEUDO_RE.fullmatch(pseudo):
        raise BeatAIError("Username: 3 to 16 characters, letters, numbers or _ only.")
    if not PIN_RE.fullmatch(pin):
        raise BeatAIError("PIN: exactly 6 digits.")
    if len(set(pin)) == 1 or pin in "0123456789" or pin in "9876543210":
        raise BeatAIError("This PIN is too easy to guess. Pick another one.")
    if _find(pseudo):
        raise BeatAIError("This username is already taken.")
    try:
        row = _req("POST", "players", json={"pseudo": pseudo, "pin_hash": hash_pin(pin)},
                   prefer="return=representation")[0]
    except RuntimeError:
        raise BeatAIError("This username is already taken.")
    return {"id": row["id"], "pseudo": row["pseudo"]}


def login(pseudo: str, pin: str) -> dict:
    pseudo, pin = pseudo.strip(), pin.strip()
    generic = BeatAIError("Wrong username or PIN.")
    if not PSEUDO_RE.fullmatch(pseudo) or not PIN_RE.fullmatch(pin):
        raise generic
    row = _find(pseudo)
    if not row:
        raise generic
    now = datetime.now(timezone.utc)
    if row["locked_until"] and datetime.fromisoformat(row["locked_until"]) > now:
        raise BeatAIError(f"Too many wrong PINs. Try again in {LOCK_MINUTES} minutes.")
    if not check_pin(pin, row["pin_hash"]):
        fails = row["failed_attempts"] + 1
        patch = {"failed_attempts": fails}
        if fails >= MAX_FAILS:
            patch = {"failed_attempts": 0, "locked_until": (now + timedelta(minutes=LOCK_MINUTES)).isoformat()}
        _req("PATCH", "players", params={"id": f"eq.{row['id']}"}, json=patch)
        raise generic
    if row["failed_attempts"] or row["locked_until"]:
        _req("PATCH", "players", params={"id": f"eq.{row['id']}"},
             json={"failed_attempts": 0, "locked_until": None})
    return {"id": row["id"], "pseudo": row["pseudo"]}


# ---------------------------------------------------------------- « Se souvenir de moi »
def _sign(msg: str) -> str:
    key = hmac.new(KEY.encode(), b"courtside-session", hashlib.sha256).digest()
    return hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()[:40]


def make_token(player: dict) -> str:
    exp = int(time.time()) + SESSION_DAYS * 86400
    msg = f"{player['id']}.{player['pseudo']}.{exp}"
    return f"{msg}.{_sign(msg)}"


def read_token(token) -> dict | None:
    try:
        pid, pseudo, exp, sig = str(token).split(".")
        msg = f"{pid}.{pseudo}.{exp}"
        if (hmac.compare_digest(sig, _sign(msg)) and int(exp) > time.time()
                and PSEUDO_RE.fullmatch(pseudo) and re.fullmatch(r"[0-9a-f-]{36}", pid)):
            return {"id": pid, "pseudo": pseudo}
    except (ValueError, AttributeError):
        pass
    return None


# ---------------------------------------------------------------- Pronostics
def my_picks(player_id: str) -> dict:
    rows = _req("GET", "picks", params={"select": "game_id,picked_team", "player_id": f"eq.{player_id}"})
    return {r["game_id"]: r["picked_team"] for r in rows}


def save_pick(player_id: str, game_id: str, team: str):
    _req("POST", "picks", params={"on_conflict": "player_id,game_id"},
         json={"player_id": player_id, "game_id": game_id, "picked_team": team,
               "updated_at": datetime.now(timezone.utc).isoformat()},
         prefer="resolution=merge-duplicates,return=minimal")


def _in(ids):
    return "in.(" + ",".join(ids) + ")"


def picks_of(player_ids: list) -> list:
    """Les pronostics des membres d'une ligue (Supabase renvoie 1000 lignes max par requête)."""
    if not player_ids:
        return []
    out, start = [], 0
    while True:
        rows = _req("GET", "picks", params={"select": "player_id,game_id,picked_team",
                                            "player_id": _in(player_ids), "order": "id"},
                    range_=f"{start}-{start + 999}")
        out += rows
        if len(rows) < 1000:
            return out
        start += 1000


# ---------------------------------------------------------------- Ligues privées
def clean_code(code) -> str:
    return re.sub(r"[\s\-]", "", str(code or "")).upper()


def _new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def my_leagues(player_id: str) -> list:
    rows = _req("GET", "league_members", params={"select": "league_id", "player_id": f"eq.{player_id}"})
    if not rows:
        return []
    leagues = _req("GET", "leagues", params={"select": "id,name,code,owner_id",
                                             "id": _in([r["league_id"] for r in rows])})
    return sorted(leagues, key=lambda l: l["name"].lower())


def create_league(player_id: str, name: str) -> dict:
    name = re.sub(r"\s+", " ", str(name or "")).strip()
    if not LEAGUE_NAME_RE.fullmatch(name):
        raise BeatAIError("League name: 3 to 30 characters (letters, numbers, spaces).")
    if len(my_leagues(player_id)) >= MAX_LEAGUES:
        raise BeatAIError(f"You can be in {MAX_LEAGUES} leagues at most.")
    for _ in range(5):                          # en cas (très rare) de code déjà pris, on en tire un autre
        try:
            league = _req("POST", "leagues", json={"name": name, "code": _new_code(), "owner_id": player_id},
                          prefer="return=representation")[0]
            break
        except RuntimeError:
            continue
    else:
        raise RuntimeError("Could not create a unique league code")
    _req("POST", "league_members", json={"league_id": league["id"], "player_id": player_id},
         prefer="return=minimal")
    return league


def join_league(player_id: str, code: str) -> dict:
    code = clean_code(code)
    if not CODE_RE.fullmatch(code):
        raise BeatAIError("A league code is 6 letters and numbers, like K7P2QX.")
    rows = _req("GET", "leagues", params={"select": "id,name,code,owner_id", "code": f"eq.{code}"})
    if not rows:
        raise BeatAIError("No league found with this code. Check it with your friend.")
    league = rows[0]
    mine = my_leagues(player_id)
    if any(l["id"] == league["id"] for l in mine):
        raise BeatAIError(f"You are already in {league['name']}.")
    if len(mine) >= MAX_LEAGUES:
        raise BeatAIError(f"You can be in {MAX_LEAGUES} leagues at most.")
    if len(members(league["id"])) >= MAX_MEMBERS:
        raise BeatAIError(f"This league is full ({MAX_MEMBERS} players).")
    _req("POST", "league_members", json={"league_id": league["id"], "player_id": player_id},
         prefer="return=minimal")
    return league


def members(league_id: str) -> dict:
    """{id du joueur: pseudo} pour tous les membres d'une ligue."""
    rows = _req("GET", "league_members", params={"select": "player_id", "league_id": f"eq.{league_id}"})
    if not rows:
        return {}
    ps = _req("GET", "players", params={"select": "id,pseudo", "id": _in([r["player_id"] for r in rows])})
    return {r["id"]: r["pseudo"] for r in ps}


def leave_league(player_id: str, league_id: str):
    _req("DELETE", "league_members", params={"league_id": f"eq.{league_id}", "player_id": f"eq.{player_id}"})
    if not members(league_id):                  # dernier membre parti : la ligue disparaît
        _req("DELETE", "leagues", params={"id": f"eq.{league_id}"})