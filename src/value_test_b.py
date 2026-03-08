import pandas as pd
import numpy as np
import os

BASE = os.path.dirname(os.path.dirname(__file__))

FULL = os.path.join(BASE, "data", "processed", "full_features.csv")
LOGREG = os.path.join(BASE, "data", "processed", "logreg_predictions.csv")

print("[*] Loading:")
print("   -", FULL)
print("   -", LOGREG)

full = pd.read_csv(FULL, parse_dates=["date"])
logreg = pd.read_csv(LOGREG, parse_dates=["date"])

print("[OK] full_features shape:", full.shape)
print("[OK] logreg_predictions shape:", logreg.shape)

# ===============================================================
# 1 — MERGE
# ===============================================================

merge_keys = ["date", "league", "season", "home_team", "away_team"]

merged = pd.merge(
    full,
    logreg,
    on=merge_keys,
    suffixes=("", "_logreg"),
    how="inner"
)

print("[OK] Birleşmiş shape:", merged.shape)

# ===============================================================
# 2 — ODDs KOLONLARINI NORMALİZE ET
#    B365H, B365D, B365A kesin olmalı
# ===============================================================

odds = ["B365H", "B365D", "B365A"]

def select_odds(main, merged_df):
    if main in merged_df.columns:
        return merged_df[main]

    # fallback: home_B365H
    home_col = f"home_{main}"
    away_col = f"away_{main}"
    log_col = f"{main}_logreg"

    if home_col in merged_df.columns:
        return merged_df[home_col]
    if away_col in merged_df.columns:
        return merged_df[away_col]
    if log_col in merged_df.columns:
        return merged_df[log_col]

    raise ValueError(f"[ERR] {main} bulunamadı!")

for col in odds:
    merged[col] = select_odds(col, merged)

# Gereksiz tüm odds kolonlarını sil
for c in merged.columns:
    if ("B365" in c) and (c not in odds):
        merged.drop(columns=[c], inplace=True)

print("[OK] Odds normalize edildi. Kalan kolonlar:", [c for c in merged.columns if "B365" in c])

# ===============================================================
# 3 — EV HESAPLAMA
# ===============================================================

# Model B tahmin kolonları
P_H = merged["P_H"]
P_D = merged["P_D"]
P_A = merged["P_A"]

# Gerçek sonuç
y_true = merged["result"]

# Bookmaker odds
O_H = merged["B365H"]
O_D = merged["B365D"]
O_A = merged["B365A"]

# EV = P * Odds - (1 - P)
merged["EV_H"] = P_H * O_H - (1 - P_H)
merged["EV_D"] = P_D * O_D - (1 - P_D)
merged["EV_A"] = P_A * O_A - (1 - P_A)

# En yüksek EV hangi tarafta?
ev_cols = ["EV_H", "EV_D", "EV_A"]
idxmax = merged[ev_cols].values.argmax(axis=1)

side_map = {0: "H", 1: "D", 2: "A"}
merged["best_side"] = [side_map[i] for i in idxmax]

# ===============================================================
# 4 — BAHİS İSABET + ROI HESABI
# ===============================================================

def evaluate(min_ev):
    df_ev = merged[merged[ev_cols].max(axis=1) >= min_ev].copy()
    if len(df_ev) == 0:
        return (0, 0, 0, 0)

    df_ev["hit"] = (
        ((df_ev["best_side"] == "H") & (df_ev["result"] == 1)) |
        ((df_ev["best_side"] == "D") & (df_ev["result"] == 0)) |
        ((df_ev["best_side"] == "A") & (df_ev["result"] == -1))
    )

    df_ev["profit"] = np.where(
        df_ev["hit"],
        np.where(df_ev["best_side"] == "H", df_ev["B365H"],
        np.where(df_ev["best_side"] == "D", df_ev["B365D"], df_ev["B365A"])) - 1,
        -1
    )

    bets = len(df_ev)
    acc = df_ev["hit"].mean()
    pnl = df_ev["profit"].sum()
    roi = pnl / bets

    return bets, acc, pnl, roi


print("\n=== VALUE BET TEST – MODEL B (LogReg) ===")
print(f"Toplam maç: {len(merged)}\n")

for th in [0.00, 0.02, 0.05, 0.08, 0.10]:
    bets, acc, pnl, roi = evaluate(th)
    print(f"[EV >= {th:.2f}]")
    print("  Bahis sayısı :", bets)
    print("  İsabet oranı :", acc)
    print("  P&L          :", pnl)
    print(f"  ROI          : {roi:.3f} (%{roi*100:.1f})\n")
