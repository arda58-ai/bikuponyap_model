import os
import pandas as pd
import numpy as np
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, log_loss, classification_report
from sklearn.preprocessing import StandardScaler

BASE = os.path.dirname(os.path.dirname(__file__))
INPUT = os.path.join(BASE, "data", "processed", "full_features.csv")
OUTPUT = os.path.join(BASE, "data", "processed", "model_a_predictions.csv")

print("[*] Loading:", INPUT)
df = pd.read_csv(INPUT, parse_dates=["date"])

# =========== TARGET ==============
df["target"] = df["result"].map({1: 0, 0: 1, -1: 2})  
# 0=H, 1=D, 2=A

# ========== FEATURE SEÇİMİ ==========
feature_cols = [
    # Ratings
    "home_elo", "away_elo",
    "home_att", "away_att",
    "home_def", "away_def",

    # Rolling
    "home_rolling_gf_5", "home_rolling_ga_5", "home_rolling_pts_5",
    "away_rolling_gf_5", "away_rolling_ga_5", "away_rolling_pts_5",

    # Poisson
    "lambda_home", "lambda_away",
    "p_home", "p_draw", "p_away",
    "p_over25", "p_under25", "p_btts",

    # Odds
    "B365H", "B365D", "B365A",
    "PSH", "PSD", "PSA",
]

# Missing değerleri doldur
df[feature_cols] = df[feature_cols].fillna(df[feature_cols].median())

X = df[feature_cols]
y = df["target"]

# ============ Train / Test Split ============
# Lig bazlı değil → tarih bazlı split
df = df.sort_values("date")
X = df[feature_cols]
y = df["target"]

split_idx = int(len(df) * 0.75)
X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

print(f"Train: {X_train.shape}, Test: {X_test.shape}")

# ============ MODEL =============
model = LGBMClassifier(
    n_estimators=700,
    learning_rate=0.015,
    max_depth=8,
    subsample=0.9,
    colsample_bytree=0.9,
    objective="multiclass",
    num_class=3
)

model.fit(X_train, y_train)

# ============ PREDICTIONS ============
probs = model.predict_proba(X_test)

df_pred = df.iloc[split_idx:].copy()
df_pred["P_H"] = probs[:, 0]
df_pred["P_D"] = probs[:, 1]
df_pred["P_A"] = probs[:, 2]

df_pred.to_csv(OUTPUT, index=False)

print("\n=== MODEL A RESULTS ===")
print("Accuracy:", accuracy_score(y_test, probs.argmax(axis=1)))
print("LogLoss:", log_loss(y_test, probs))

print("\nClassification Report:")
print(classification_report(y_test, probs.argmax(axis=1)))

print("\nSaved →", OUTPUT)
