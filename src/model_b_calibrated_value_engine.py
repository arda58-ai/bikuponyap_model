import os
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss

# =========================
# PATH AYARLARI
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "full_features_noleak_fe.csv")
SAVE_DIR  = os.path.join(BASE_DIR, "data", "processed")
os.makedirs(SAVE_DIR, exist_ok=True)

FEATURE_COLS_PATH = os.path.join(SAVE_DIR, "model_b_feature_cols.json")

TRAIN_SEASONS = ["2021-2022", "2022-2023"]
TEST_SEASONS  = ["2023-2024"]

MIN_EV   = 0.03
MIN_PROB = 0.45


# =========================
# HELPER FONKSİYONLAR
# =========================
def map_result_to_classes(series: pd.Series) -> pd.Series:
    mapping = {-1: 0, 0: 1, 1: 2}
    return series.map(mapping)


def platt_fit(probs: np.ndarray, y: np.ndarray) -> dict:
    """Multiclass Platt scaling."""
    n_classes = probs.shape[1]
    params = {}

    for k in range(n_classes):
        p_raw = probs[:, k].clip(1e-6, 1 - 1e-6)
        z = np.log(p_raw / (1 - p_raw)).reshape(-1, 1)
        y_bin = (y == k).astype(int)

        lr = LogisticRegression(solver="lbfgs")
        lr.fit(z, y_bin)

        params[f"class_{k}"] = {
            "a": float(lr.intercept_[0]),
            "b": float(lr.coef_[0, 0]),
        }

    return params


def platt_predict(probs: np.ndarray, params: dict) -> np.ndarray:
    """Multiclass Platt scaling prediction."""
    n_samples, n_classes = probs.shape
    p_cal = np.zeros_like(probs)

    for k_str, par in params.items():
        k = int(k_str.split("_")[-1])
        a = par["a"]
        b = par["b"]

        p_raw = probs[:, k].clip(1e-6, 1 - 1e-6)
        z = np.log(p_raw / (1 - p_raw)).reshape(-1, 1)
        logits = a + b * z
        p_k = (1.0 / (1.0 + np.exp(-logits))).ravel()
        p_cal[:, k] = p_k

    s = p_cal.sum(axis=1, keepdims=True)
    s[s == 0] = 1.0
    p_cal /= s
    return p_cal


def implied_probs_from_odds(oh, od, oa):
    inv_h, inv_d, inv_a = 1 / oh, 1 / od, 1 / oa
    total = inv_h + inv_d + inv_a
    return inv_h / total, inv_d / total, inv_a / total


# =========================
# 1) VERİ YÜKLEME
# =========================
print("[*] Loading features table (no-leak)…")
df = pd.read_csv(DATA_PATH)
df["date"] = pd.to_datetime(df["date"])

df_train_all = df[df["season"].isin(TRAIN_SEASONS)].copy()
df_test      = df[df["season"].isin(TEST_SEASONS)].copy()

y_train_all = map_result_to_classes(df_train_all["result"])
y_test      = map_result_to_classes(df_test["result"])

# Zaman sırasına göre train / calib split
df_train_all = df_train_all.sort_values("date").reset_index(drop=True)
y_train_all  = y_train_all.loc[df_train_all.index]

cut = int(len(df_train_all) * 0.8)
df_train = df_train_all.iloc[:cut].copy()
df_cal   = df_train_all.iloc[cut:].copy()
y_train  = y_train_all.iloc[:cut].values
y_cal    = y_train_all.iloc[cut:].values

print(f"Train subset: {df_train.shape}")
print(f"Calib subset: {df_cal.shape}")
print(f"Test subset : {df_test.shape}")

print("\nOriginal target distribution (train):")
print(df_train_all["result"].value_counts())
print("\nMapped target distribution (train):")
print(y_train_all.value_counts())


# =========================
# 2) FEATURE SET (NO-LEAK)
# =========================
DROP_COLS = [
    # target & türevleri
    "result", "home_result", "away_result",
    "home_team_points", "away_team_points",

    # doğrudan gol/puan
    "home_team_goals_for", "home_team_goals_against",
    "away_team_goals_for", "away_team_goals_against",
    "home_goals", "away_goals",
    "home_home_goals", "home_away_goals",
    "away_home_goals", "away_away_goals",

    # eski rolling puanlar (leak)
    "home_rolling_pts_5", "away_rolling_pts_5",

    # model output’ları
    "lambda_home", "lambda_away",
    "p_home", "p_draw", "p_away",
    "p_over25", "p_under25", "p_btts",

    # id & meta
    "match_id", "home_match_id", "away_match_id",
    "date", "league", "season",
    "home_league", "away_league",
    "home_season", "away_season",
    "home_team", "away_team", "team_x", "team_y",

    # eski rolling goller/xG (leak’li versiyonlar)
    "home_rolling_gf_5", "home_rolling_ga_5",
    "home_rolling_xGF_5", "home_rolling_xGA_5",
    "away_rolling_gf_5", "away_rolling_ga_5",
    "away_rolling_xGF_5", "away_rolling_xGA_5",
]

DROP_COLS = [c for c in DROP_COLS if c in df.columns]
FEATURE_COLS = [c for c in df.columns if c not in DROP_COLS]

X_train = df_train[FEATURE_COLS].copy()
X_cal   = df_cal[FEATURE_COLS].copy()
X_test  = df_test[FEATURE_COLS].copy()

# numeric + temizle
for X in (X_train, X_cal, X_test):
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(0, inplace=True)

# zero variance drop
zero_cols = [c for c in X_train.columns if X_train[c].std() == 0]
if zero_cols:
    X_train.drop(columns=zero_cols, inplace=True)
    X_cal.drop(columns=zero_cols, inplace=True)
    X_test.drop(columns=zero_cols, inplace=True)

# high correlation drop
corr = X_train.corr().abs()
upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
high_corr = [c for c in upper.columns if any(upper[c] > 0.97)]
if high_corr:
    X_train.drop(columns=high_corr, inplace=True)
    X_cal.drop(columns=high_corr, inplace=True)
    X_test.drop(columns=high_corr, inplace=True)

FEATURE_COLS_FINAL = list(X_train.columns)
print("[INFO] Final feature shape:", X_train.shape)

# =========================
# 3) LIGHTGBM TRAIN
# =========================
params = {
    "objective": "multiclass",
    "num_class": 3,
    "learning_rate": 0.05,
    "num_leaves": 63,
    "metric": "multi_logloss",
    "verbosity": -1,
}

print("[*] Training LightGBM (Model-B)…")
train_set = lgb.Dataset(X_train, label=y_train)
model = lgb.train(params, train_set, num_boost_round=350)
print("[OK] Model-B trained.")

# =========================
# 4) CALIBRATION
# =========================
probs_calib_raw = model.predict(X_cal)
platt_params = platt_fit(probs_calib_raw, y_cal)

probs_test_raw = model.predict(X_test)
probs_test_cal = platt_predict(probs_test_raw, platt_params)

acc_raw = (probs_test_raw.argmax(axis=1) == y_test.values).mean()
acc_cal = (probs_test_cal.argmax(axis=1) == y_test.values).mean()

print("\n[TEST] raw acc:", acc_raw)
print("[TEST] cal  acc:", acc_cal)

# =========================
# 5) VALUE BET ENGINE (TEST)
# =========================
eval_cols = [
    "date", "league", "season",
    "home_team", "away_team",
    "B365H", "B365D", "B365A", "result"
]

df_ev = df_test[eval_cols].copy()
df_ev["prob_cal_away"] = probs_test_cal[:, 0]
df_ev["prob_cal_draw"] = probs_test_cal[:, 1]
df_ev["prob_cal_home"] = probs_test_cal[:, 2]

mask = df_ev[["B365H", "B365D", "B365A"]].notna().all(axis=1)
df_ev = df_ev[mask].copy()

df_ev["ev_home"] = df_ev["prob_cal_home"] * df_ev["B365H"] - 1
df_ev["ev_draw"] = df_ev["prob_cal_draw"] * df_ev["B365D"] - 1
df_ev["ev_away"] = df_ev["prob_cal_away"] * df_ev["B365A"] - 1

bets = []
for _, r in df_ev.iterrows():
    evs   = np.array([r.ev_away, r.ev_draw, r.ev_home])
    probs = np.array([r.prob_cal_away, r.prob_cal_draw, r.prob_cal_home])
    odds  = np.array([r.B365A, r.B365D, r.B365H])

    k = evs.argmax()
    max_ev   = float(evs[k])
    max_prob = float(probs[k])

    if max_ev <= MIN_EV or max_prob <= MIN_PROB:
        continue

    side = ["A", "D", "H"][k]
    odd  = float(odds[k])

    # gerçek sonuç
    if r["result"] == 1:
        true_side = "H"
    elif r["result"] == 0:
        true_side = "D"
    else:
        true_side = "A"

    profit = odd - 1 if side == true_side else -1

    bets.append(
        (r.date, r.league, r.home_team, r.away_team,
         side, odd, max_ev, max_prob, profit)
    )

df_bets = pd.DataFrame(
    bets,
    columns=[
        "date", "league", "home_team", "away_team",
        "bet_side", "bet_odds", "bet_ev", "bet_prob", "profit"
    ]
)

# =========================
# 6) SAVE
# =========================
# Model & platt & feature columns
model.save_model(os.path.join(SAVE_DIR, "lgbm_model_calibrated.txt"))
with open(os.path.join(SAVE_DIR, "platt_params.json"), "w", encoding="utf-8") as f:
    json.dump(platt_params, f, indent=2)
with open(FEATURE_COLS_PATH, "w", encoding="utf-8") as f:
    json.dump(FEATURE_COLS_FINAL, f, indent=2)

df_bets.to_csv(
    os.path.join(SAVE_DIR, "walk_season_calibrated_value_engine.csv"),
    index=False
)

print("\n[OK] Saved:")
print("  →", os.path.join(SAVE_DIR, "lgbm_model_calibrated.txt"))
print("  →", os.path.join(SAVE_DIR, "platt_params.json"))
print("  →", FEATURE_COLS_PATH)
print("  → walk_season_calibrated_value_engine.csv")
