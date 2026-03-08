import os
import numpy as np
import pandas as pd

# =========================
# 1. PATHLER
# =========================
BASE = os.path.dirname(os.path.dirname(__file__))
FULL = os.path.join(BASE, "data", "processed", "full_features.csv")
PRED = os.path.join(BASE, "data", "processed", "model_a_predictions.csv")

print("[*] Loading:")
print("   -", FULL)
print("   -", PRED)

df_full = pd.read_csv(FULL)
df_pred = pd.read_csv(PRED)

# DATE TİPLERİNİ EŞITLE
df_full["date"] = pd.to_datetime(df_full["date"], errors="coerce")
df_pred["date"] = pd.to_datetime(df_pred["date"], errors="coerce")

print("[OK] full_features shape:", df_full.shape)
print("[OK] model_a_predictions shape:", df_pred.shape)

# =========================
# 2. PROBA KOLONLARINI BUL
# =========================
prob_candidates = [
    ("P_H", "P_D", "P_A"),
    ("p_home", "p_draw", "p_away"),
]

col_H = col_D = col_A = None
for cols in prob_candidates:
    if all(c in df_pred.columns for c in cols):
        col_H, col_D, col_A = cols
        break

if col_H is None:
    raise ValueError("Prob kolonları bulunamadı.")

print(f"[OK] Prob kolonları: {col_H}, {col_D}, {col_A}")

# =========================
# 3. GERÇEK SONUÇ KOLONU
# =========================
result_candidates = ["ResultNumeric", "result", "target"]
result_col = None
for c in result_candidates:
    if c in df_full.columns:
        result_col = c
        break

if result_col is None:
    raise ValueError("Result kolonu bulunamadı.")

print(f"[OK] Result kolonu: {result_col}")

# =========================
# 4. ODDS KOLONLARI
# =========================
odds_candidates = [
    ("B365H", "B365D", "B365A"),
    ("PSH", "PSD", "PSA"),
]

odd_H = odd_D = odd_A = None
for cols in odds_candidates:
    if all(c in df_full.columns for c in cols):
        odd_H, odd_D, odd_A = cols
        break

if odd_H is None:
    raise ValueError("Odds kolonları bulunamadı.")

print(f"[OK] Odds kolonları: {odd_H}, {odd_D}, {odd_A}")

# =========================
# 5. JOIN KEY
# =========================
key_candidates = ["date", "league", "season", "home_team", "away_team"]
keys = [k for k in key_candidates if k in df_full.columns and k in df_pred.columns]

print("[OK] Join keyleri:", keys)

# MERGE
df = pd.merge(
    df_full,
    df_pred[keys + [col_H, col_D, col_A]],
    on=keys,
    how="inner",
    validate="one_to_one"
)

print("[OK] Birleşmiş shape:", df.shape)

# =========================
# 6. EV HESABI
# =========================
df_ev = df.dropna(subset=[odd_H, odd_D, odd_A]).copy()
print("[OK] Odds mevcut maç sayısı:", len(df_ev))

# Model probabilities
pH = df_ev[col_H]
pD = df_ev[col_D]
pA = df_ev[col_A]

# EV
df_ev["EV_H"] = pH * df_ev[odd_H] - 1
df_ev["EV_D"] = pD * df_ev[odd_D] - 1
df_ev["EV_A"] = pA * df_ev[odd_A] - 1

ev_cols = ["EV_H", "EV_D", "EV_A"]

# Best side
side_map = {0: "H", 1: "D", 2: "A"}

df_ev["best_side"] = pd.Series(
    df_ev[["EV_H", "EV_D", "EV_A"]].values.argmax(axis=1)
).map(side_map)

df_ev["best_EV"] = df_ev[["EV_H", "EV_D", "EV_A"]].max(axis=1)


# True label
def numeric_to_side(x):
    return "H" if x == 1 else "D" if x == 0 else "A"

df_ev["true_side"] = df_ev[result_col].apply(numeric_to_side)

# =========================
# 7. EV EŞİK TESTLERİ
# =========================
thresholds = [0.00, 0.02, 0.05, 0.08, 0.10]

print("\n=== VALUE BET TEST – MODEL A (GBM) ===")
print("Toplam maç:", len(df_ev))

for th in thresholds:
    bets = df_ev[df_ev["best_EV"] >= th]
    n_bets = len(bets)

    if n_bets == 0:
        print(f"\n[EV >= {th:.2f}] Hiç bahis yok.")
        continue

    profit = []
    for _, r in bets.iterrows():
        side = r["best_side"]
        true = r["true_side"]

        odd = r[odd_H] if side == "H" else r[odd_D] if side == "D" else r[odd_A]
        profit.append(odd - 1 if side == true else -1)

    profit = np.array(profit)
    roi = profit.sum() / n_bets

    print(f"\n[EV >= {th:.2f}]")
    print("  Bahis sayısı :", n_bets)
    print("  İsabet oranı :", (profit > 0).mean())
    print("  P&L          :", profit.sum())
    print("  ROI          :", roi, f"(%{roi*100:.1f})")
