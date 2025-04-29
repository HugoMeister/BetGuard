#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Value-bet finder — v3.6
Includes manual season split plus Purged CV with date drop fix.
"""

import os
import re
import pickle
import requests
import pandas as pd
import numpy as np
from datetime import timedelta

from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import GridSearchCV
from sklearn.metrics import accuracy_score, roc_auc_score, brier_score_loss

# Constants & Config
SEASONS        = ["2425","2324","2223","2122","2021"]
DIVISIONS      = {"E0":"Premier League","E1":"Championship","SP1":"La Liga",
                  "I1":"Serie A","D1":"Bundesliga","F1":"Ligue 1",
                  "N1":"Eredivisie","D2":"2. Bundesliga","SP2":"Segunda División"}
SPORT_KEYS     = {
    "E0":"soccer_epl","E1":"soccer_england_championship","SP1":"soccer_spain_la_liga",
    "I1":"soccer_italy_serie_a","D1":"soccer_germany_bundesliga","F1":"soccer_france_ligue_1",
    "N1":"soccer_netherlands_eredivisie","D2":"soccer_germany_2_bundesliga","SP2":"soccer_spain_segunda"
}
RAW_DIR        = "MlService/data/raw/"
DATA_DIR       = "MlService/data/"
MODEL_DIR      = "MlService/data/model/"
ODDS_COLS      = ["b365h","b365d","b365a"]
VALUE_THRESHOLD = 0.075
N_FORM          = 5
PINA_API_KEY    = "6ae063796adc45e431a0e1644ca15162"
PINA_ENDPOINT   = "https://api.the-odds-api.com/v4/sports/{sport}/odds?regions=eu&markets=h2h&apiKey={key}"
TEST_SEASONS    = ["2122", "2223", "2324"]

def train_and_find_value(df):
    cat_map = {
        "league": df[["league","league_code"]].drop_duplicates().set_index("league")["league_code"].to_dict(),
        "season": df[["season","season_code"]].drop_duplicates().set_index("season")["season_code"].to_dict()
    }
    X_full = df.drop(["result_label","league","season","date"], axis=1)
    mapping = {**cat_map, "feature_order": X_full.columns.tolist()}
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR,"cat_mapping.pkl"), "wb") as f:
        pickle.dump(mapping, f)

    train_seasons = ["2122","2223","2324"]
    test_season   = "2425"
    train_df = df[df["season"].isin(train_seasons)].reset_index(drop=True)
    test_df  = df[df["season"]==test_season].reset_index(drop=True)

    X_tr, y_tr = train_df.drop(["result_label","league","season","date"], axis=1), train_df["result_label"]
    X_te, y_te = test_df .drop(["result_label","league","season","date"], axis=1), test_df["result_label"]

    print(f"🔹 Training on seasons {train_seasons}, testing on {test_season}")
    param_grid = {
        "n_estimators": [100,200,500],
        "max_depth":    [None,10,20,30],
        "max_features": ["sqrt","log2",0.2,0.5],
        "min_samples_split":[2,5,10],
        "min_samples_leaf": [1,2,4]
    }
    gs = GridSearchCV(RandomForestClassifier(random_state=42, n_jobs=-1), param_grid,
                      scoring="roc_auc_ovo", cv=3, n_jobs=-1, verbose=1, refit=True)
    gs.fit(X_tr, y_tr)
    best_params = gs.best_params_
    print("➡️ Best params:", best_params)

    rf_for_imp = RandomForestClassifier(**best_params, random_state=42, n_jobs=-1)
    rf_for_imp.fit(X_tr, y_tr)
    imp = pd.Series(rf_for_imp.feature_importances_, index=X_tr.columns)
    imp = imp.sort_values(ascending=False)
    print("🔑 Top 10 feature importances:\n", imp.head(10), sep="")

    # Calibration
    clf = CalibratedClassifierCV(gs.best_estimator_, cv=3)
    clf.fit(X_tr, y_tr)

    evaluate_with_purged_cv(df, best_params)

    # Test-season evaluation
    p_te = clf.predict_proba(X_te)
    acc_te = accuracy_score(y_te, clf.predict(X_te))
    auc_te = roc_auc_score(y_te, p_te, multi_class="ovo", average="macro")
    bs_te  = (brier_score_loss((y_te==2).astype(int), p_te[:,2]) +
              brier_score_loss((y_te==1).astype(int), p_te[:,1]) +
              brier_score_loss((y_te==0).astype(int), p_te[:,0]))/3
    print(f"[Test season {test_season}] Acc={acc_te:.3f}, AUC={auc_te:.3f}, Brier={bs_te:.3f}")

    # Build df_v for ROI tests
    df_v = X_te.copy()
    df_v[["p_a","p_d","p_h"]] = p_te
    for side in ["h","d","a"]:
        df_v[f"val_{side}"] = df_v[f"p_{side}"] - df_v[f"imp_{side}"]
    df_v["result_label"] = y_te

    return best_params

def get_result(r):
    return "H" if r.fthg > r.ftag else "A" if r.fthg < r.ftag else "D"

def form_pts(df, team, date):
    recent = df[((df.hometeam==team)|(df.awayteam==team)) & (df.date<date)] \
               .sort_values("date",ascending=False).head(N_FORM)
    pts = 0
    for _, r in recent.iterrows():
        res = get_result(r)
        win = (r.hometeam==team and res=="H") or (r.awayteam==team and res=="A")
        pts += 3 if win else (1 if res=="D" else 0)
    return pts


def avg_goals(df, team, date, home=True):
    recent = df[((df.hometeam==team)|(df.awayteam==team)) & (df.date<date)] \
               .sort_values("date",ascending=False).head(N_FORM)
    goals = []
    for _, r in recent.iterrows():
        if home and r.hometeam==team:
            goals.append(r.fthg)
        elif not home and r.awayteam==team:
            goals.append(r.ftag)
    return sum(goals)/len(goals) if goals else 0.0

# ROI calculation
def compute_roi(df, threshold=VALUE_THRESHOLD, stake=1.0):
    mask = (df["val_h"] > threshold) | (df["val_d"] > threshold) | (df["val_a"] > threshold)
    bets = df.loc[mask].copy()
    if bets.empty:
        return None
    bets["best_side"] = bets[["val_h","val_d","val_a"]].idxmax(axis=1).str[-1]
    bets["odd"] = bets.apply(lambda r: 1 / r[f"imp_{r['best_side']}"], axis=1)
    bets["win"]  = bets.apply(
        lambda r: 1 if r["result_label"] == { 'h': 2, 'd':1, 'a':0 }[r['best_side']] else 0,
        axis=1
    )
    bets["profit"] = bets.apply(
        lambda r: (r["odd"] - 1) * stake if r["win"] == 1 else -stake,
        axis=1
    )
    return bets["profit"].sum() / (len(bets) * stake)

# Compute ROI for one season
def season_roi(df, best_params, season, threshold=VALUE_THRESHOLD):
    train_df = df[df["season"] != season].reset_index(drop=True)
    test_df  = df[df["season"] == season].reset_index(drop=True)

    X_tr = train_df.drop(["result_label","league","season","date"], axis=1)
    y_tr = train_df["result_label"]
    X_te = test_df .drop(["result_label","league","season","date"], axis=1)
    y_te = test_df ["result_label"]

    rf  = RandomForestClassifier(**best_params, random_state=42, n_jobs=-1)
    clf = CalibratedClassifierCV(rf, cv=3)
    clf.fit(X_tr, y_tr)

    p_te = clf.predict_proba(X_te)
    df_v = X_te.copy()
    df_v[["p_a","p_d","p_h"]] = p_te
    for side in ["h","d","a"]:
        df_v[f"val_{side}"] = df_v[f"p_{side}"] - df_v[f"imp_{side}"]
    df_v["result_label"] = y_te
    return compute_roi(df_v, threshold)

# Grid search over VALUE_THRESHOLD
def grid_thresholds(df, best_params, thresholds):
    print("\n=== Grid search VALUE_THRESHOLD ===")
    for thr in thresholds:
        rois = [ season_roi(df, best_params, ts, thr) or 0.0 for ts in TEST_SEASONS ]
        mean_roi = np.mean(rois)
        print(
            f"Threshold {thr:>5.3f} → sezony ROI = {[f'{r*100:5.2f}%' for r in rois]}, "
            f"średnio {mean_roi*100:5.2f}%"
        )

# Backtest ROI on each season
def backtest_by_season(df, best_params, threshold=VALUE_THRESHOLD):
    print("\n=== Backtest across seasons ===")
    for ts in TEST_SEASONS:
        roi = season_roi(df, best_params, ts, threshold)
        n_bets = None  # optionally compute count if needed
        print(f"Season {ts}: ROI={roi*100:5.2f}%")

def download_all():
    os.makedirs(RAW_DIR, exist_ok=True)
    for s in SEASONS:
        for d in DIVISIONS:
            path = os.path.join(RAW_DIR, f"{d}_{s}.csv")
            if not os.path.exists(path):
                try:
                    url = f"https://www.football-data.co.uk/mmz4281/{s}/{d}.csv"
                    r = requests.get(url, timeout=20)
                    if r.ok and r.content:
                        with open(path, "wb") as f:
                            f.write(r.content)
                except:
                    pass

def process_league(path):
    lg, ss = re.match(r"([A-Z0-9]+)_([0-9]{4})\.csv", os.path.basename(path)).groups()
    df = pd.read_csv(path)
    df.columns = [c.lower() for c in df.columns]
    # Upewnij się, że są hometeam i awayteam
    if 'hometeam' not in df.columns or 'awayteam' not in df.columns:
        df.rename(columns={'home':'hometeam','away':'awayteam'}, inplace=True)
    if not set(ODDS_COLS).issubset(df.columns):
        return pd.DataFrame()
    df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['date'] + ODDS_COLS + ['hometeam','awayteam']).sort_values('date')

    # implied odds
    df[['imp_h','imp_d','imp_a']] = 1/df[ODDS_COLS]
    tot = df[['imp_h','imp_d','imp_a']].sum(axis=1)
    df[['imp_h','imp_d','imp_a']] = df[['imp_h','imp_d','imp_a']].div(tot, axis=0)

    # pobranie kursów Pinnacle
    sec_map = {}
    for m in fetch_pinnacle_odds(SPORT_KEYS[lg]):
        sec_map[(m['home'].lower(), m['away'].lower())] = (m['h'],m['d'],m['a'])

    rows = []
    for _, r in df.iterrows():
        rec = {
            'hometeam': r.hometeam,
            'awayteam': r.awayteam,
            'home_avg_goals': round(avg_goals(df, r.hometeam, r.date, True),2),
            'away_avg_goals': round(avg_goals(df, r.awayteam, r.date, False),2),
            'home_form': form_pts(df, r.hometeam, r.date),
            'away_form': form_pts(df, r.awayteam, r.date),
            'imp_h': round(r.imp_h,3),
            'imp_d': round(r.imp_d,3),
            'imp_a': round(r.imp_a,3)
        }
        key = (r.hometeam.lower(), r.awayteam.lower())
        if key in sec_map:
            h2,d2,a2 = sec_map[key]
            inv = [1/h2 if h2 else 0, 1/d2 if d2 else 0, 1/a2 if a2 else 0]
            tot2 = sum(inv)
            imp2 = [round(v/tot2,3) for v in inv] if tot2 else [None,None,None]
            diffs = [round(rec[k]-imp2[i],3) for i,k in enumerate(['imp_h','imp_d','imp_a'])]
            rec.update({'imp2_h': imp2[0], 'imp2_d': imp2[1], 'imp2_a': imp2[2],
                        'diff_h': diffs[0], 'diff_d': diffs[1], 'diff_a': diffs[2]})
        rec.update({'league': lg, 'season': ss,
                    'result_label': {'A':0,'D':1,'H':2}[get_result(r)],
                    'date': r.date})
        rows.append(rec)
    return pd.DataFrame(rows)

def build_dataset():
    os.makedirs(RAW_DIR, exist_ok=True)
    frames = []
    for f in os.listdir(RAW_DIR):
        if f.endswith(".csv"):
            df = process_league(os.path.join(RAW_DIR, f))
            if not df.empty:
                frames.append(df)
    # Połącz wszystkie ligowe dane
    df = pd.concat(frames, ignore_index=True)

    # Różnicowe cechy formy i goli
    df["form_diff"]  = df["home_form"] - df["away_form"]
    df["goals_diff"] = df["home_avg_goals"] - df["away_avg_goals"]

    # Różnice kursów (implied odds)
    df["imp_diff_h_a"] = df["imp_h"] - df["imp_a"]
    df["imp_diff_h_d"] = df["imp_h"] - df["imp_d"]
    df["imp_diff_d_a"] = df["imp_d"] - df["imp_a"]

    # Stosunki (ratios) kursów primary
    df["imp_ratio_h_a"] = df["imp_h"] / df["imp_a"]
    df["imp_ratio_h_d"] = df["imp_h"] / df["imp_d"]
    df["imp_ratio_d_a"] = df["imp_d"] / df["imp_a"]

    # Log-ratio kursów primary (opcjonalnie)
    df["imp_logratio_h_a"] = np.log(df["imp_h"] / df["imp_a"])
    df["imp_logratio_h_d"] = np.log(df["imp_h"] / df["imp_d"])
    df["imp_logratio_d_a"] = np.log(df["imp_d"] / df["imp_a"])

    # Stosunki primary vs secondary odds (jeśli masz imp2_h, imp2_d, imp2_a z Pinnacle)
    if all(col in df.columns for col in ["imp2_h", "imp2_d", "imp2_a"]):
        df["prim_sec_ratio_h"]     = df["imp_h"]  / df["imp2_h"]
        df["prim_sec_ratio_d"]     = df["imp_d"]  / df["imp2_d"]
        df["prim_sec_ratio_a"]     = df["imp_a"]  / df["imp2_a"]
        df["log_prim_sec_ratio_h"] = np.log(df["imp_h"]  / df["imp2_h"])
        df["log_prim_sec_ratio_d"] = np.log(df["imp_d"]  / df["imp2_d"])
        df["log_prim_sec_ratio_a"] = np.log(df["imp_a"]  / df["imp2_a"])

    # Dane o zmęczeniu i harmonogramie
    # zakładamy, że df zawiera kolumny hometeam i awayteam z process_league
    df = df.sort_values("date")
    # dni od ostatniego meczu
    df["days_since_last_match_home"] = df.groupby("hometeam")["date"].diff().dt.days
    df["days_since_last_match_away"] = df.groupby("awayteam")["date"].diff().dt.days
    # liczba meczów w ostatnich 14 dniach (bez bieżącego)
    df["matches_in_last_14d_home"] = df.apply(
        lambda r: ((df["hometeam"]==r["hometeam"]) &
                   (df["date"]<r["date"]) &
                   (df["date"]>=r["date"]-pd.Timedelta(days=14))).sum(), axis=1)
    df["matches_in_last_14d_away"] = df.apply(
        lambda r: ((df["awayteam"]==r["awayteam"]) &
                   (df["date"]<r["date"]) &
                   (df["date"]>=r["date"]-pd.Timedelta(days=14))).sum(), axis=1)

    # Kodowanie kategorii odds (jeśli masz imp2_h, imp2_d, imp2_a z Pinnacle)
    if all(col in df.columns for col in ["imp2_h", "imp2_d", "imp2_a"]):
        df["prim_sec_ratio_h"]     = df["imp_h"]  / df["imp2_h"]
        df["prim_sec_ratio_d"]     = df["imp_d"]  / df["imp2_d"]
        df["prim_sec_ratio_a"]     = df["imp_a"]  / df["imp2_a"]
        df["log_prim_sec_ratio_h"] = np.log(df["imp_h"]  / df["imp2_h"])
        df["log_prim_sec_ratio_d"] = np.log(df["imp_d"]  / df["imp2_d"])
        df["log_prim_sec_ratio_a"] = np.log(df["imp_a"]  / df["imp2_a"])

    # Kodowanie kategorii
    df["league_code"] = df["league"].astype("category").cat.codes
    df["season_code"] = df["season"].astype("category").cat.codes

    df.drop(["hometeam", "awayteam"], axis=1, inplace=True)

    # Zapis do CSV
    os.makedirs(DATA_DIR, exist_ok=True)
    df.to_csv(os.path.join(DATA_DIR, "dataset.csv"), index=False)
    print(f"✅ dataset.csv – {len(df)} wierszy, {df.shape[1]} cech")
    return df

def purged_time_series_split(df,n_splits=5,purge_days=7):
    dates=pd.to_datetime(df["date"]).sort_values().unique()
    for blk in np.array_split(dates,n_splits):
        start,end=blk.min(),blk.max()
        p_start,p_end=start-timedelta(days=purge_days),start+timedelta(days=purge_days)
        is_test=df["date"].between(start,end)
        is_purge=df["date"].between(p_start,p_end)
        is_train=~(is_test|is_purge)
        yield df[is_train].index, df[is_test].index

def evaluate_with_purged_cv(df, best_params, n_splits=5, purge_days=7):
    X = df.drop(["result_label","league","season","date"], axis=1)
    y = df["result_label"]
    accs, aucs, bscores = [], [], []
    for i,(tr,te) in enumerate(purged_time_series_split(df, n_splits, purge_days),1):
        X_tr, y_tr = X.loc[tr], y.loc[tr]
        X_te, y_te = X.loc[te], y.loc[te]
        rf  = RandomForestClassifier(**best_params, random_state=42, n_jobs=-1)
        clf = CalibratedClassifierCV(rf, cv=3)
        clf.fit(X_tr, y_tr)
        p = clf.predict_proba(X_te)
        acc = accuracy_score(y_te, clf.predict(X_te))
        auc = roc_auc_score(y_te, p, multi_class="ovo", average="macro")
        bs  = (
            brier_score_loss((y_te==2).astype(int), p[:,2]) +
            brier_score_loss((y_te==1).astype(int), p[:,1]) +
            brier_score_loss((y_te==0).astype(int), p[:,0])
        )/3
        print(f"Fold {i:>2} → Acc={acc:.3f}, AUC={auc:.3f}, Brier={bs:.3f}")
        accs.append(acc); aucs.append(auc); bscores.append(bs)
    print(f"★ Purged-CV mean → Acc={np.mean(accs):.3f}, AUC={np.mean(aucs):.3f}, Brier={np.mean(bscores):.3f}")

def fetch_pinnacle_odds(sportKey):
    if not PINA_API_KEY:
        return []
    try:
        res = requests.get(
            PINA_ENDPOINT.format(sport=sportKey, key=PINA_API_KEY),
            timeout=10
        ).json()
        if not isinstance(res, list):
            return []
    except:
        return []
    matches = []
    for e in res:
        if not e.get("bookmakers"):
            continue
        mkt = e["bookmakers"][0]["markets"][0]["outcomes"]
        odds = {o["name"]: o["price"] for o in mkt}
        matches.append({
            "home": e["home_team"], "away": e["away_team"],
            "h": odds.get(e["home_team"]),
            "d": odds.get("Draw"),
            "a": odds.get(e["away_team"])
        })
    return matches

def main():
    download_all()
    df = build_dataset()
    best_params = train_and_find_value(df)
    backtest_by_season(df, best_params, threshold=VALUE_THRESHOLD)
    thresholds = np.arange(0.05, 0.1001, 0.005)
    grid_thresholds(df, best_params, thresholds)

if __name__ == "__main__":
    main()
