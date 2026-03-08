import pandas as pd
import numpy as np
import os

BASE = os.path.dirname(os.path.dirname(__file__))

FULL = os.path.join(BASE, "data", "processed", "full_features.csv")
PRED = os.path.join(BASE, "data", "processed", "model_a_predictions.csv")

print("[*] Loading datasets:")
full = pd.read_csv(FULL, parse_dates=["date"])
pred = pd.read_csv(PRED, parse_dates=["date"])

print("[OK] full_features:", full.shape)
print("[OK] model_a_predictions:", pred.shape)

# --------------------------------------------------
# JOIN
# --------------------------------------------------
keys = ["date", "league", "season", "home_team", "away_team"]

df = pd.merge(full, pred, on=keys, suffixes=("", "_gbm"))
print("[OK] merged:", df.shape)

# --------------------------------------------------
# CHECK REQUIRED COLUMNS
# --------------------------------------------------
required_probs = ["P_H", "P_D", "P_A"]
required_odds  = ["B365H", "B365D", "B365A"]

for col in required_probs + required_odds:
    if col not in df.columns:
        raise ValueError(f"Missing column: {col}")

# --------------------------------------------------
# STRICT BETTING POLICY
# --------------------------------------------------
print("\n=== STRICT POLICY TEST (MODEL A – GBM) ===")

records = []

for idx, row in df.iterrows():

    probs = {
        "H": row["P_H"],
        "D": row["P_D"],
        "A": row["P_A"]
    }

    odds = {
        "H": row["B365H"],
        "D": row["B365D"],
        "A": row["B365A"]
    }

    # EV hesapla
    ev = {side: probs[side] * odds[side] - 1 for side in ["H", "D", "A"]}

    # STRICT FİLTRE:
    # 1) EV ≥ 0.05
    # 2) P(side) ≥ 0.50
    # 3) Odds ≤ 3.0
    valid = {
        s: ev[s] >= 0.05 and probs[s] >= 0.50 and odds[s] <= 3.00
        for s in ["H", "D", "A"]
    }

    # Tek bir seçim yap (en yüksek EV olan)
    side = None
    best_ev = -999

    for s in ["H", "D", "A"]:
        if valid[s] and ev[s] > best_ev:
            side = s
            best_ev = ev[s]

    if side is None:
        continue  # maç atlanır

    # Sonuç
    actual = row["result"]   # 1=H, 0=D, -1=A
    win = (
        (side == "H" and actual == 1) or
        (side == "D" and actual == 0) or
        (side == "A" and actual == -1)
    )

    pnl = odds[side] - 1 if win else -1

    records.append({
        "date": row["date"],
        "league": row["league"],
        "side": side,
        "prob": probs[side],
        "odds": odds[side],
        "ev": ev[side],
        "win": win,
        "pnl": pnl
    })

# --------------------------------------------------
# RESULTS
# --------------------------------------------------
res = pd.DataFrame(records)

print("\nToplam bahis:", len(res))

if len(res) > 0:
    winrate = res["win"].mean()
    total_pnl = res["pnl"].sum()
    roi = total_pnl / len(res)

    print("\n=== STRICT POLICY RESULTS ===")
    print(f"Hit rate   : {winrate:.3f}")
    print(f"P&L        : {total_pnl:.2f}")
    print(f"ROI        : {roi:.3f} (%{roi*100:.1f})")
else:
    print("\nStrict filtre → hiç bet çıkmadı (model yeterince güvenilir değil).")

OUT = os.path.join(BASE, "data", "processed", "value_strict_results.csv")
res.to_csv(OUT, index=False)
print("\nSaved:", OUT)
