import pandas as pd
import numpy as np
import os

# ================================
# CONFIG
# ================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
PATH_BETS = os.path.join(DATA_DIR, "walk_season_calibrated_value_engine.csv")

COL_DATE   = "date"
COL_SIDE   = "bet_side"
COL_ODDS   = "bet_odds"
COL_EV     = "bet_ev"
COL_PROB   = "bet_prob"
COL_PROFIT = "profit"

# ======= SMART FILTERS =======
MIN_EV_COUPON   = 0.10
MIN_PROB_COUPON = 0.65
MIN_ODDS        = 1.50
MAX_ODDS        = 2.50

FORM_DIFF_MIN   = 0.35   # yeni optimum
VAR_MAX         = 2.50    # rolling varyans sınırı

MIN_MATCHES     = 3
MAX_MATCHES     = 5

# Fallback devreye girerse
FALLBACK_K      = 4

STAKE = 1.0

SAVE_PATH = os.path.join(DATA_DIR, "daily_coupon_backtest.csv")


# ================================
# LOAD
# ================================
print("[*] Loading bets file…")
df = pd.read_csv(PATH_BETS)

df[COL_DATE] = pd.to_datetime(df[COL_DATE])

# Form & varyans kolon kontrolü
HAS_FORM = all(c in df.columns for c in [
    "home_rolling_pts_5_nl", "away_rolling_pts_5_nl"
])
HAS_VAR = all(c in df.columns for c in [
    "home_rolling_gd_var_5_nl", "away_rolling_gd_var_5_nl"
])

if HAS_FORM:
    df["form_diff_abs"] = (df["home_rolling_pts_5_nl"] -
                           df["away_rolling_pts_5_nl"]).abs()

if HAS_VAR:
    df["max_gd_var"] = df[[
        "home_rolling_gd_var_5_nl",
        "away_rolling_gd_var_5_nl"
    ]].max(axis=1)


# ================================
# DAILY BACKTEST ENGINE
# ================================
records = []

for date, group in df.groupby(df[COL_DATE].dt.date):

    day_df = group.copy()

    if day_df.empty:
        continue

    # 1) Core filters
    filtered = day_df[
        (day_df[COL_EV] >= MIN_EV_COUPON) &
        (day_df[COL_PROB] >= MIN_PROB_COUPON) &
        (day_df[COL_ODDS] >= MIN_ODDS) &
        (day_df[COL_ODDS] <= MAX_ODDS)
    ].copy()

    # 2) Form
    if HAS_FORM:
        filtered = filtered[filtered["form_diff_abs"] >= FORM_DIFF_MIN]

    # 3) Varyans
    if HAS_VAR:
        filtered = filtered[filtered["max_gd_var"] <= VAR_MAX]

    # ------- FINAL CANDIDATE COUNT -------
    candidate_count = len(filtered)

    # Eğer filtrelerden geçen aday yoksa fallback
    if candidate_count == 0:
        filtered = day_df.sort_values(COL_EV, ascending=False).head(FALLBACK_K)
        selected = filtered
    else:
        # Yeterli sayıda aday varsa maç sayısını seç
        filtered = filtered.sort_values(COL_EV, ascending=False)

        if candidate_count < MIN_MATCHES:
            continue  # kupon yok (fallback de istemiyorsak)
        elif MIN_MATCHES <= candidate_count <= MAX_MATCHES:
            selected = filtered
        else:
            selected = filtered.head(MAX_MATCHES)

    # ------ Kupon hesaplama ------
    total_odds = np.prod(selected[COL_ODDS].values)
    is_win = np.all(selected[COL_PROFIT] > 0)
    roi = total_odds - 1 if is_win else -1

    records.append({
        "date": date,
        "match_count": len(selected),
        "candidate_count": candidate_count,
        "total_odds": total_odds,
        "is_win": int(is_win),
        "roi": roi,
        "daily_profit": roi * STAKE
    })


# ================================
# OUTPUT
# ================================
res = pd.DataFrame(records)

if res.empty:
    print("\n===== DAILY COUPON BACKTEST =====")
    print("Hiçbir gün kupon oluşmadı.")
else:
    print("\n===== DAILY COUPON BACKTEST =====")
    print("Toplam gün:", len(res))
    print("Ortalama maç sayısı:", res["match_count"].mean())
    print("Kupon isabet oranı:", res["is_win"].mean())
    print("Toplam profit:", res["daily_profit"].sum())
    print("Ortalama ROI:", res["roi"].mean())

res.to_csv(SAVE_PATH, index=False)
print("[OK] Saved →", SAVE_PATH)
