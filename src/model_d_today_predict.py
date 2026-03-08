# ======================================================
# model_d_today_predict.py
# Model-B ile %100 uyumlu, full-feature Supersonic kupon
# ======================================================
import os
import json
import sqlite3
import random
import numpy as np
import pandas as pd
import lightgbm as lgb

# -------------------------
# PATHS
# -------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")

TODAY_ODDS_PATH   = os.path.join(PROC_DIR, "today_odds_from_api.csv")
FULL_FEATURES_PATH = os.path.join(PROC_DIR, "full_features_noleak_fe.csv")

MODEL_PATH        = os.path.join(PROC_DIR, "lgbm_model_calibrated.txt")
PLATT_PATH        = os.path.join(PROC_DIR, "platt_params.json")
FEATURE_COLS_PATH = os.path.join(PROC_DIR, "model_b_feature_cols.json")

COUPON_SAVE_PATH  = os.path.join(PROC_DIR, "today_coupon_supersonic.csv")

DB_PATH = "/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db"

TARGET_COUPON_MATCHES = 4
MIN_ODDS = 1.40
MAX_ODDS = 3.00


# -------------------------
# HELPER
# -------------------------
def platt_predict(probs: np.ndarray, params: dict) -> np.ndarray:
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
    inv_h, inv_d, inv_a = 1.0 / oh, 1.0 / od, 1.0 / oa
    total = inv_h + inv_d + inv_a
    return inv_h / total, inv_d / total, inv_a / total


# -------------------------
# DB HELPERS (VIP ANALIZLER)
# -------------------------
def db_hazirla_vip():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS vip_analizler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            mac_adi TEXT,
            risk_skoru REAL,
            karar TEXT,
            oran REAL,
            tahmin_tipi TEXT,
            kaynak TEXT,
            spor TEXT,
            mac_kodu TEXT
        )"""
    )
    conn.commit()
    conn.close()


def db_kaydet_vip(tarih, mac_adi, skor, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO vip_analizler (tarih, mac_adi, risk_skoru, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (tarih, mac_adi, skor, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu),
    )
    conn.commit()
    conn.close()


# -------------------------
# MAIN
# -------------------------
def main():
    # 1) Bugünkü odds
    print("[*] Loading today's odds…")
    df_today = pd.read_csv(TODAY_ODDS_PATH)
    print(f"[OK] Raw matches: {len(df_today)}")

    df_today = df_today.dropna(subset=["B365H", "B365D", "B365A"]).copy()
    if df_today.empty:
        print("[WARN] No matches with full odds. Exit.")
        return

    # 2) Model + Platt + Feature cols
    print("[*] Loading Model-B, calibration and feature columns…")
    model = lgb.Booster(model_file=MODEL_PATH)

    with open(PLATT_PATH, "r", encoding="utf-8") as f:
        platt_params = json.load(f)

    with open(FEATURE_COLS_PATH, "r", encoding="utf-8") as f:
        feature_cols = json.load(f)

    print(f"[INFO] Model-B feature count: {len(feature_cols)}")

    # 3) Tarihsel full_features_noleak_fe
    print("[*] Loading historical feature table…")
    hist = pd.read_csv(FULL_FEATURES_PATH)
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values("date")

    # Sadece feature kolonlarını al, yoksa drop
    hist_feat_cols = [c for c in feature_cols if c in hist.columns]
    hist_base = hist[hist_feat_cols].copy()
    hist_base.replace([np.inf, -np.inf], np.nan, inplace=True)
    hist_base.fillna(0, inplace=True)

    mean_vector = hist_base.mean(axis=0)  # global ortalama (fallback)

    # HOME/ AWAY son maç feature pool
    home_last = (
        hist.sort_values("date")
            .dropna(subset=["home_team"])
            .groupby("home_team")
            .tail(1)
            .set_index("home_team")
    )
    away_last = (
        hist.sort_values("date")
            .dropna(subset=["away_team"])
            .groupby("away_team")
            .tail(1)
            .set_index("away_team")
    )

    print(f"[INFO] home_last teams: {len(home_last)}, away_last teams: {len(away_last)}")

    # 4) Bugünkü maçlar için full feature satırı üret
    X_rows   = []
    meta_rows = []

    for _, r in df_today.iterrows():
        home = str(r["home_team"])
        away = str(r["away_team"])

        v = mean_vector.copy()  # global fallback

        # Odds override
        if "B365H" in v.index:
            v["B365H"] = float(r["B365H"])
        if "B365D" in v.index:
            v["B365D"] = float(r["B365D"])
        if "B365A" in v.index:
            v["B365A"] = float(r["B365A"])

        # HOME tarafını son home maçından doldur
        if home in home_last.index:
            row_h = home_last.loc[home]
            for col in feature_cols:
                if col.startswith("home_") and col in row_h.index:
                    v[col] = row_h[col]

        # AWAY tarafını son away maçından doldur
        if away in away_last.index:
            row_a = away_last.loc[away]
            for col in feature_cols:
                if col.startswith("away_") and col in row_a.index:
                    v[col] = row_a[col]

        # Son hâlini kaydet
        X_rows.append(v.values)
        meta_rows.append({
            "date":       r["date"],
            "datetime_tr": r.get("datetime_tr", ""),
            "league":     r["league"],
            "home_team":  home,
            "away_team":  away,
            "B365H":      float(r["B365H"]),
            "B365D":      float(r["B365D"]),
            "B365A":      float(r["B365A"]),
        })

    # DataFrame yap
    X_today = pd.DataFrame(X_rows, columns=mean_vector.index)

    # Eğer feature_cols'ta olup X_today’da olmayan varsa ekle
    for c in feature_cols:
        if c not in X_today.columns:
            X_today[c] = 0.0

    X_today = X_today[feature_cols].copy()
    X_today.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_today.fillna(0, inplace=True)

    meta_df = pd.DataFrame(meta_rows)

    # 5) Tahmin + Kalibrasyon
    print("[*] Predicting with Model-B…")
    probs_raw = model.predict(X_today.values)
    probs_cal = platt_predict(probs_raw, platt_params)

    meta_df["prob_cal_away"] = probs_cal[:, 0]
    meta_df["prob_cal_draw"] = probs_cal[:, 1]
    meta_df["prob_cal_home"] = probs_cal[:, 2]

    # 6) EV hesapla
    ip_h, ip_d, ip_a = implied_probs_from_odds(
        meta_df["B365H"].values,
        meta_df["B365D"].values,
        meta_df["B365A"].values,
    )
    meta_df["ip_home"] = ip_h
    meta_df["ip_draw"] = ip_d
    meta_df["ip_away"] = ip_a

    meta_df["ev_home"] = meta_df["prob_cal_home"] * meta_df["B365H"] - 1.0
    meta_df["ev_draw"] = meta_df["prob_cal_draw"] * meta_df["B365D"] - 1.0
    meta_df["ev_away"] = meta_df["prob_cal_away"] * meta_df["B365A"] - 1.0

    # 7) Her maç için en iyi tarafı seç (EV max) + odds filtresi
    candidates = []
    for _, r in meta_df.iterrows():
        evs   = np.array([r.ev_away, r.ev_draw, r.ev_home])
        probs = np.array([r.prob_cal_away, r.prob_cal_draw, r.prob_cal_home])
        odds  = np.array([r.B365A, r.B365D, r.B365H])

        k = int(evs.argmax())
        side = ["A", "D", "H"][k]
        odd  = float(odds[k])
        ev   = float(evs[k])
        p    = float(probs[k])

        # Odds aralığı
        if odd < MIN_ODDS or odd > MAX_ODDS:
            continue

        candidates.append({
            "date":        r["date"],
            "datetime_tr": r["datetime_tr"],
            "league":      r["league"],
            "home_team":   r["home_team"],
            "away_team":   r["away_team"],
            "B365H":       r["B365H"],
            "B365D":       r["B365D"],
            "B365A":       r["B365A"],
            "bet_side":    side,
            "bet_odds":    odd,
            "bet_ev":      ev,
            "bet_prob":    p,
        })

    if not candidates:
        print("\n===== SUPERSONIC TODAY COUPON =====")
        print("Hiç maç seçilemedi (odds filtresinden geçemedi).")
        pd.DataFrame().to_csv(COUPON_SAVE_PATH, index=False)
        print("[OK] Saved empty coupon →", COUPON_SAVE_PATH)
        return

    df_bets = pd.DataFrame(candidates)

    # 8) EV’e göre sırala, TOP-4
    df_bets = df_bets.sort_values("bet_ev", ascending=False).reset_index(drop=True)

    if len(df_bets) >= TARGET_COUPON_MATCHES:
        coupon = df_bets.head(TARGET_COUPON_MATCHES).copy()
    else:
        coupon = df_bets.copy()

    coupon.to_csv(COUPON_SAVE_PATH, index=False)

    print("\n===== SUPERSONIC TODAY COUPON (TOP 4) =====")
    for idx, r in coupon.iterrows():
        print(
            f"{idx+1}. {r['date']} | {r['league']} | "
            f"{r['home_team']} - {r['away_team']} → "
            f"{r['bet_side']} @ {r['bet_odds']:.2f} "
            f"(EV={r['bet_ev']:.3f}, p={r['bet_prob']:.3f})"
        )

    # VIP analizler tablosuna yaz
    db_hazirla_vip()
    for _, r in coupon.iterrows():
        tarih_raw = r.get("datetime_tr", "")
        tarih_db = (str(tarih_raw)[:16].replace("T", " ")).strip() if tarih_raw else f"{r['date']} 00:00"
        mac_adi_db = f"{r['home_team']} vs {r['away_team']}"
        oran_db = float(r["bet_odds"])
        prob = float(r["bet_prob"])
        risk_skoru = round(100 - prob * 100, 1)

        side = r["bet_side"]
        if side == "H":
            karar = "MS 1"
        elif side == "A":
            karar = "MS 2"
        else:
            karar = "Beraberlik"

        tahmin_tipi = karar
        mac_kodu = str(random.randint(10000, 99999))

        db_kaydet_vip(
            tarih_db,
            mac_adi_db,
            risk_skoru,
            karar,
            oran_db,
            tahmin_tipi,
            "Model-B Supersonic",
            "Futbol",
            mac_kodu,
        )

    print("\n[OK] Saved supersonic coupon →", COUPON_SAVE_PATH)


if __name__ == "__main__":
    main()
