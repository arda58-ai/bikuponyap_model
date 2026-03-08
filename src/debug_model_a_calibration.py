import pandas as pd
import numpy as np
import os

BASE = os.path.dirname(os.path.dirname(__file__))

FULL_FEATURES = os.path.join(BASE, "data", "processed", "full_features.csv")
MODEL_A = os.path.join(BASE, "data", "processed", "model_a_predictions.csv")

print("[*] Loading:")
print(" -", FULL_FEATURES)
print(" -", MODEL_A)

df_full = pd.read_csv(FULL_FEATURES, parse_dates=["date"])
df_pred = pd.read_csv(MODEL_A, parse_dates=["date"])

# Merge
keys = ["date", "league", "season", "home_team", "away_team"]

df = pd.merge(
    df_pred,
    df_full[keys + ["result"]],
    on=keys,
    how="inner",
    suffixes=("", "_full")
)

print("[OK] Merge shape:", df.shape)

# Sınıf kodları:
# -1 = Away win
#  0 = Draw
#  1 = Home win

# === Calibration function ===
def calibration_table(df, prob_col, target_label, bins=10):
    """
    df: dataframe
    prob_col: 'P_H', 'P_D', 'P_A'
    target_label: 1 for home, 0 for draw, -1 for away
    bins: 10 (decile)
    """
    d = df.copy()
    d["bin"] = pd.qcut(d[prob_col], q=bins, duplicates="drop")
    table = d.groupby("bin").apply(
        lambda x: pd.Series({
            "pred_mean": x[prob_col].mean(),
            "actual_rate": (x["result"] == target_label).mean(),
            "count": len(x)
        })
    )
    return table.reset_index()

# Generate 3 tables
cal_H = calibration_table(df, "P_H", target_label=1)
cal_D = calibration_table(df, "P_D", target_label=0)
cal_A = calibration_table(df, "P_A", target_label=-1)

# Save
OUT_H = os.path.join(BASE, "data", "processed", "calibration_home.csv")
OUT_D = os.path.join(BASE, "data", "processed", "calibration_draw.csv")
OUT_A = os.path.join(BASE, "data", "processed", "calibration_away.csv")

cal_H.to_csv(OUT_H, index=False)
cal_D.to_csv(OUT_D, index=False)
cal_A.to_csv(OUT_A, index=False)

print("\n=== CALIBRATION READY ===")
print("Saved:")
print(" -", OUT_H)
print(" -", OUT_D)
print(" -", OUT_A)

print("\nFirst rows:")
print("Home:\n", cal_H.head())
print("Draw:\n", cal_D.head())
print("Away:\n", cal_A.head())
