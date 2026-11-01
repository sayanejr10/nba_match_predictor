from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = [
    "WIN_PCT_SEASON_HOME", "WIN_PCT_LAST10_HOME", "PM_LAST10_HOME", "REST_DAYS_HOME", "B2B_HOME",
    "WIN_PCT_SEASON_AWAY", "WIN_PCT_LAST10_AWAY", "PM_LAST10_AWAY", "REST_DAYS_AWAY", "B2B_AWAY",
]

matches = pd.read_csv("data/matches.csv")

# Modèle final : entraîné sur TOUTES les saisons (l'évaluation honnête a déjà été faite)
model = make_pipeline(StandardScaler(), LogisticRegression())
model.fit(matches[FEATURES], matches["HOME_WIN"])

Path("models").mkdir(exist_ok=True)
joblib.dump({"model": model, "features": FEATURES}, "models/model.joblib")
print(f"Modèle entraîné sur {len(matches)} matchs -> models/model.joblib")