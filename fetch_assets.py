"""Télécharge les joueurs 3D de l'intro depuis le dépôt privé « courtside-assets ».

Pourquoi ? La licence Mixamo interdit de publier les fichiers bruts dans un dépôt public.
Ils sont donc rangés dans un dépôt privé, et le serveur les récupère au moment du déploiement
grâce à une clé secrète (variable d'environnement ASSETS_TOKEN, jamais écrite dans le code).

Utilisation (commande de build sur Render) :
    pip install -r requirements.txt && python fetch_assets.py

En local, les fichiers sont déjà là : le script ne fait rien.
Si la clé manque ou si le téléchargement échoue, l'app fonctionne quand même : l'intro est
simplement sautée.
"""
import os
import sys
from pathlib import Path

import requests

REPO = "sayanejr10/courtside-assets"
FILES = ["passer.glb", "dunker.glb"]
DEST = Path(__file__).parent / "static" / "intro"


def main() -> int:
    DEST.mkdir(parents=True, exist_ok=True)
    missing = [f for f in FILES if not (DEST / f).exists()]
    if not missing:
        print("Assets déjà présents, rien à faire.")
        return 0
    token = os.environ.get("ASSETS_TOKEN")
    if not token:
        print("ASSETS_TOKEN absent : l'intro 3D sera désactivée.")
        return 0
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw",
               "X-GitHub-Api-Version": "2022-11-28"}
    for name in missing:
        url = f"https://api.github.com/repos/{REPO}/contents/{name}"
        try:
            r = requests.get(url, headers=headers, timeout=60)
            r.raise_for_status()
            if r.content[:4] != b"glTF":           # on vérifie que c'est bien un fichier 3D
                raise ValueError("contenu inattendu")
            (DEST / name).write_bytes(r.content)
            print(f"{name} téléchargé ({len(r.content) // 1024} Ko)")
        except Exception as e:                      # le message n'affiche jamais la clé
            print(f"Échec pour {name} : {type(e).__name__}. L'intro 3D sera désactivée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
