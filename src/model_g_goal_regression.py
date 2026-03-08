# ================================================================
# model_g_goal_regression.py
# Goal Regression Engine (Model-G)
# Amaç: Her maç için toplam gol sayısını (total_goals) tahmin eden
# no-leak LightGBM regresyon modeli.
# ================================================================
import os
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_squared_error

# ------------------------------------------------
# PATHS
# ------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")

DATA_PATH = os.path.join(PROC_DIR, "full_features_noleak_fe.csv")

GOAL_MODEL_PATH = os.path.join(PROC_DIR, "goal_model_lgbm.txt")
GOAL_META_PATH  = os.path.join(PROC_DIR, "goal_model_meta.json")
GOAL_BACKTEST_PATH = os.path.join(PROC_DIR, "goal_regression_backtest.csv")

os.makedirs(PROC_DIR, exist_ok=True)

TRAIN_SEASONS = ["2021-2022", "2022-2023"]
TEST_SEASONS  = ["2023-2024"]

# Sabit: 1. yarı gol oranı (veride 1Y kolonları yok, bu yüzden
# dünya ortalamasına yakın sabit bir oran kullanıyoruz)
FIRST_HALF_RATIO = 0.45   # toplam gollerin ~%45'i 1. yarıda olur varsayımı

# Güvenli lambda sınırları
LAMBDA_MIN = 0.2
LAMBDA_MAX = 6.0


def main():
    print("[*] Loading full_features_noleak_fe.csv …")
    df = pd.read_csv(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])

    # Sadece target'ı dolu satırlar
    mask_target = df[["home_goals", "away_goals"]].notna().all(axis=1)
    df = df[mask_target].copy()

    # Train / test sezonları
    df_train_all = df[df["season"].isin(TRAIN_SEASONS)].copy()
    df_test      = df[df["season"].isin(TEST_SEASONS)].copy()

    # Target: toplam gol
    df_train_all["total_goals"] = df_train_all["home_goals"] + df_train_all["away_goals"]
    df_test["total_goals"]      = df_test["home_goals"] + df_test["away_goals"]

    # Zaman bazlı train / calib split
    df_train_all = df_train_all.sort_values("date").reset_index(drop=True)
    split_idx = int(len(df_train_all) * 0.8)

    df_train = df_train_all.iloc[:split_idx].copy()
    df_cal   = df_train_all.iloc[split_idx:].copy()

    y_train = df_train["total_goals"].values
    y_cal   = df_cal["total_goals"].values
    y_test  = df_test["total_goals"].values

    # ------------------------------------------------
    # FEATURE SET (no-leak, result/goals'lar hariç)
    # ------------------------------------------------
    DROP_COLS = [
        # Target & result
        "result",
        "home_result",
        "away_result",
        "total_goals",

        # Direkt skor
        "home_goals",
        "away_goals",
        "home_home_goals", "home_away_goals",
        "away_home_goals", "away_away_goals",

        # Team-level future-ish goal aggregates
        "home_team_goals_for", "home_team_goals_against",
        "away_team_goals_for", "away_team_goals_against",

        # Clear future points
        "home_team_points",
        "away_team_points",

        # Eski leak'li rolling'ler
        "home_rolling_gf_5", "home_rolling_ga_5", "home_rolling_pts_5",
        "home_rolling_xGF_5", "home_rolling_xGA_5",
        "away_rolling_gf_5", "away_rolling_ga_5", "away_rolling_pts_5",
        "away_rolling_xGF_5", "away_rolling_xGA_5",

        # Model_B lambda/p olasılık kolonları (eski)
        "lambda_home", "lambda_away",
        "p_home", "p_draw", "p_away",
        "p_over25", "p_under25", "p_btts",

        # ID/meta (model için gereksiz)
        "match_id", "home_match_id", "away_match_id",
        "league", "season",
        "home_league", "away_league",
        "home_season", "away_season",
        "home_team", "away_team",
        "team_x", "team_y",

        # Tarih (zaten zaman bazlı split yaptık)
        "date",
    ]

    DROP_COLS = [c for c in DROP_COLS if c in df.columns]

    FEATURE_COLS = [c for c in df.columns if c not in DROP_COLS]

    X_train = df_train[FEATURE_COLS].copy()
    X_cal   = df_cal[FEATURE_COLS].copy()
    X_test  = df_test[FEATURE_COLS].copy()

    # Temizlik
    for X in [X_train, X_cal, X_test]:
        X.replace([np.inf, -np.inf], np.nan, inplace=True)
        X.fillna(0, inplace=True)

    # Zero variance kolonları at
    zero_cols = [c for c in X_train.columns if X_train[c].std() == 0]
    if zero_cols:
        X_train.drop(columns=zero_cols, inplace=True)
        X_cal.drop(columns=zero_cols, inplace=True)
        X_test.drop(columns=zero_cols, inplace=True)

    # Çok yüksek korelasyonlu kolonları at (şişkinliği azalt)
    corr = X_train.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    high_corr = [c for c in upper.columns if any(upper[c] > 0.98)]

    if high_corr:
        X_train.drop(columns=high_corr, inplace=True)
        X_cal.drop(columns=high_corr, inplace=True)
        X_test.drop(columns=high_corr, inplace=True)

    final_features = list(X_train.columns)
    print(f"[INFO] Final feature count (Model-G): {len(final_features)}")

    # ------------------------------------------------
    # LightGBM Regression Train
    # ------------------------------------------------
    params = {
        "objective": "regression_l2",
        "learning_rate": 0.03,
        "num_leaves": 63,
        "feature_fraction": 0.9,
        "bagging_fraction": 0.9,
        "bagging_freq": 1,
        "metric": "rmse",
        "verbosity": -1,
    }

    print("[*] Training Goal Regression (Model-G)…")
    train_set = lgb.Dataset(X_train, label=y_train)
    model = lgb.train(params, train_set, num_boost_round=400)
    print("[OK] Model-G trained.")

    # ------------------------------------------------
    # Eval
    # ------------------------------------------------
    def rmse(y_true, y_pred):
        return np.sqrt(mean_squared_error(y_true, y_pred))

    pred_cal  = model.predict(X_cal)
    pred_test = model.predict(X_test)

    # clip lambdas
    pred_cal_clip  = np.clip(pred_cal,  LAMBDA_MIN, LAMBDA_MAX)
    pred_test_clip = np.clip(pred_test, LAMBDA_MIN, LAMBDA_MAX)

    cal_rmse  = rmse(y_cal,  pred_cal_clip)
    test_rmse = rmse(y_test, pred_test_clip)

    print("\n[CALIB] RMSE:", cal_rmse)
    print("[TEST ] RMSE:", test_rmse)

    # ------------------------------------------------
    # Backtest export (info amaçlı)
    # ------------------------------------------------
    bt = df_test[["date", "league", "home_team", "away_team",
                  "home_goals", "away_goals", "total_goals"]].copy()
    bt["pred_goals_raw"]  = pred_test
    bt["pred_goals_clip"] = pred_test_clip

    bt.to_csv(GOAL_BACKTEST_PATH, index=False)
    print("[OK] Backtest saved →", GOAL_BACKTEST_PATH)

    # ------------------------------------------------
    # Save model + meta
    # ------------------------------------------------
    model.save_model(GOAL_MODEL_PATH)

    meta = {
        "feature_cols": final_features,
        "lambda_min": LAMBDA_MIN,
        "lambda_max": LAMBDA_MAX,
        "first_half_ratio": FIRST_HALF_RATIO,
        "cal_rmse": float(cal_rmse),
        "test_rmse": float(test_rmse),
    }

    with open(GOAL_META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    print("\n[OK] Saved:")
    print("  →", GOAL_MODEL_PATH)
    print("  →", GOAL_META_PATH)


if __name__ == "__main__":
    main()
