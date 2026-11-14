"""« Beat the AI » : les joueurs font leurs pronostics et se mesurent au modèle.

Stockage : Supabase (base PostgreSQL en ligne), via son API REST.
- SUPABASE_URL et SUPABASE_SECRET_KEY viennent des variables d'environnement (jamais du code).
- La clé secrète ne quitte jamais le serveur : le navigateur des visiteurs ne la voit pas.

Sécurité :
- le code à 6 chiffres n'est jamais stocké, seulement une empreinte scrypt (avec un sel unique) ;
- 5 mauvais codes -> compte bloqué 10 minutes (contre les robots qui essaient tous les codes) ;
- un pronostic est refusé si le match a commencé (vérifié ici, côté serveur) ;
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


def all_picks() -> list:
    """Tous les pronostics de tous les joueurs (Supabase renvoie 1000 lignes max par requête)."""
    out, start = [], 0
    while True:
        rows = _req("GET", "picks", params={"select": "player_id,game_id,picked_team", "order": "id"},
                    range_=f"{start}-{start + 999}")
        out += rows
        if len(rows) < 1000:
            return out
        start += 1000


def players() -> dict:
    rows = _req("GET", "players", params={"select": "id,pseudo"})
    return {r["id"]: r["pseudo"] for r in rows}