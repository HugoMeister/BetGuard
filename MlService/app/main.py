from fastapi import FastAPI
from pydantic import BaseModel
import pickle, pandas as pd
from pathlib import Path

app = FastAPI()

# ----------  MODELE DANYCH  ------------------------------------
class Features(BaseModel):
    league:          str    # "E0", "SP1", itd.  ── NOWE
    season:          str    # "2425", "2324", …  ── NOWE
    home_avg_goals:  float
    away_avg_goals:  float
    home_form:       int
    away_form:       int
    b365h:           float
    b365d:           float
    b365a:           float

class PredictResponse(BaseModel):
    home_win_probability: float
    draw_probability:     float
    away_win_probability: float

# ----------  ŁADOWANIE ARTEFAKTÓW  ------------------------------
model_dir = Path("../data/model")
with open(model_dir / "model.pkl", "rb") as f:
    model = pickle.load(f)

with open(model_dir / "cat_mapping.pkl", "rb") as f:
    mapping = pickle.load(f)

expected_cols = mapping["feature_order"]
league_map    = mapping["league"]
season_map    = mapping["season"]

# ----------  POMOCNICZE ----------------------------------------
def implied_and_margin(h, d, a):
    inv_h, inv_d, inv_a = 1/h, 1/d, 1/a
    overround = inv_h + inv_d + inv_a
    margin    = round(overround - 1, 4)
    return inv_h/overround, inv_d/overround, inv_a/overround, margin

# ----------  ENDPOINT  -----------------------------------------
@app.post("/predict", response_model=PredictResponse)
def predict(feat: Features):
    # 1) Zamiana kategorii → kody
    league_code = league_map.get(feat.league, 0)
    season_code = season_map.get(feat.season, 0)

    # 2) Cechy liczbowe
    imp_h, imp_d, imp_a, margin = implied_and_margin(feat.b365h, feat.b365d, feat.b365a)

    data = {
        "home_avg_goals": feat.home_avg_goals,
        "away_avg_goals": feat.away_avg_goals,
        "home_form":      feat.home_form,
        "away_form":      feat.away_form,
        "margin":         margin,
        "imp_h":          round(imp_h, 3),
        "imp_d":          round(imp_d, 3),
        "imp_a":          round(imp_a, 3),
        "league_code":    league_code,
        "season_code":    season_code,
    }

    # 3) DataFrame w kolejności z treningu
    X = pd.DataFrame([data])[expected_cols]

    # 4) (opc.) gdy wszystkie cechy formy/goli są zerowe
    if X.iloc[0][["home_avg_goals","away_avg_goals","home_form","away_form"]].eq(0).all():
        return PredictResponse(
            home_win_probability=0.0,
            draw_probability=0.0,
            away_win_probability=0.0,
        )


    # 5) Predykcja
    p_a, p_d, p_h = model.predict_proba(X)[0]  # RF → [away, draw, home]
    return PredictResponse(
        home_win_probability = float(p_h),
        draw_probability     = float(p_d),
        away_win_probability = float(p_a),
    )
