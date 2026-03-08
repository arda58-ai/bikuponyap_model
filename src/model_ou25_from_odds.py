# ================================================================
# model_ou25_from_odds.py
# Odds-only Over/Under 2.5 modeli (canlı kullanım için)
# ================================================================
import os
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score

# -------------------------
# PATHS
# -------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "full_features_noleak_fe.csv")
SAVE_DIR  = os.path.join(BASE_DIR, "data", "processed")
os.makedirs(SAVE_DIR, exist_ok=True)

TRAIN_SEASONS = ["2021-2022", "2022-2023"]
TEST_SEASONS  = ["2023-2024"]


# -------------------------
# Platt scaling (binary)
# -------------------------
def platt_binary_fit(p_raw, y):
    p_raw = p_raw.clip(1e-6, 1-1e-6).reshape(-1, 1)
    z = np.log(p_raw / (1 - p_raw))
    lr = LogisticRegression(solver="lbfgs")
    lr.fit(z, y)
    return float(lr.intercept_[0]), float(lr.coef_[0, 0])


def platt_binary_predict(p_raw, a, b):
    p_raw = p_raw.clip(1e-6, 1-1e-6)
    z = np.log(p_raw / (1 - p_raw))
    logits = a + b * z
    return 1.0 / (1.0 + np.exp(-logits))


def implied_probs_from_odds(oh, od, oa):
    inv_h = 1.0 / oh
    inv_d = 1.0 / od
    inv_a = 1.0 / oa
    total = inv_h + inv_d + inv_a
    return inv_h / total, inv_d / total, inv_a / total


# -------------------------
# LOAD DATA
# -------------------------
print("[*] Loading full_features_noleak_fe.csv …")
df = pd.read_csv(DATA_PATH)
df["date"] = pd.to_datetime(df["date"])

# Sadece elimizde oran olan satırları kullan
mask_odds = df[["B365H", "B365D", "B365A"]].notna().all(axis=1)
df = df[mask_odds].copy()

# Train / test sezonları
df_train_all = df[df["season"].isin(TRAIN_SEASONS)].copy()
df_test      = df[df["season"].isin(TEST_SEASONS)].copy()

# TARGET: Over 2.5 (toplam gol >=3)
df_train_all["target_ou25"] = (
    df_train_all["home_goals"] + df_train_all["away_goals"] >= 3
).astype(int)
df_test["target_ou25"] = (
    df_test["home_goals"] + df_test["away_goals"] >= 3
).astype(int)

# Zaman sırasına göre train / calib split
df_train_all = df_train_all.sort_values("date").reset_index(drop=True)
split_idx = int(len(df_train_all) * 0.8)

df_train = df_train_all.iloc[:split_idx].copy()
df_cal   = df_train_all.iloc[split_idx:].copy()

y_train = df_train["target_ou25"].values
y_cal   = df_cal["target_ou25"].values
y_test  = df_test["target_ou25"].values

# -------------------------
# FEATURE ENGINEERING (odds-only)
# -------------------------
def build_features(df_in: pd.DataFrame) -> pd.DataFrame:
    df_out = df_in[["B365H", "B365D", "B365A"]].copy()

    # Implied probabilities
    ip_h, ip_d, ip_a = implied_probs_from_odds(
        df_out["B365H"].values,
        df_out["B365D"].values,
        df_out["B365A"].values,
    )
    df_out["ip_home"] = ip_h
    df_out["ip_draw"] = ip_d
    df_out["ip_away"] = ip_a

    # Basit spread feature’ları
    df_out["fav_prob"] = df_out[["ip_home", "ip_draw", "ip_away"]].max(axis=1)
    df_out["und_prob"] = df_out[["ip_home", "ip_draw", "ip_away"]].min(axis=1)
    df_out["prob_gap"] = df_out["fav_prob"] - df_out["und_prob"]

    # Log-odds
    df_out["log_oh"] = np.log(df_out["B365H"])
    df_out["log_od"] = np.log(df_out["B365D"])
    df_out["log_oa"] = np.log(df_out["B365A"])

    return df_out


X_train = build_features(df_train)
X_cal   = build_features(df_cal)
X_test  = build_features(df_test)

# -------------------------
# TRAIN LIGHTGBM
# -------------------------
params = {
    "objective": "binary",
    "learning_rate": 0.03,
    "num_leaves": 31,
    "feature_fraction": 0.9,
    "bagging_fraction": 0.9,
    "bagging_freq": 1,
    "metric": "binary_logloss",
    "verbosity": -1,
}

print("[*] Training OU2.5 (odds-only) model…")
train_set = lgb.Dataset(X_train, label=y_train)
model = lgb.train(params, train_set, num_boost_round=250)
print("[OK] Model trained.")

# -------------------------
# CALIBRATION
# -------------------------
p_cal_raw = model.predict(X_cal)
a, b = platt_binary_fit(p_cal_raw, y_cal)

p_test_raw = model.predict(X_test)
p_test_cal = platt_binary_predict(p_test_raw, a, b)

print("\n[TEST] Raw  logloss:", log_loss(y_test, p_test_raw))
print("[TEST] Cal  logloss:", log_loss(y_test, p_test_cal))
print("[TEST] Cal  AUC    :", roc_auc_score(y_test, p_test_cal))

# -------------------------
# SAVE
# -------------------------
# Tahminleri de isteğe bağlı kaydedebiliriz
out = df_test[["date", "league", "home_team", "away_team",
               "B365H", "B365D", "B365A", "target_ou25"]].copy()
out["p_over25_raw"] = p_test_raw
out["p_over25_cal"] = p_test_cal

out.to_csv(os.path.join(SAVE_DIR, "ou25_odds_only_backtest.csv"), index=False)

# Model & platt params & feature list
model_path = os.path.join(SAVE_DIR, "ou25_model_from_odds.txt")
model.save_model(model_path)

platt_path = os.path.join(SAVE_DIR, "platt_ou25_from_odds.json")
with open(platt_path, "w", encoding="utf-8") as f:
    json.dump({"a": a, "b": b}, f, indent=2)

feat_path = os.path.join(SAVE_DIR, "ou25_features_from_odds.json")
with open(feat_path, "w", encoding="utf-8") as f:
    json.dump({"features": list(X_train.columns)}, f, indent=2)

print("\n[OK] Saved:")
print("  →", model_path)
print("  →", platt_path)
print("  →", feat_path)
print("  → ou25_odds_only_backtest.csv")
