import os
import numpy as np
import pandas as pd

# ==========================
# PATH AYARLARI
# ==========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")
INPUT_FILE = os.path.join(DATA_DIR, "full_features.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "full_features_noleak_fe.csv")


# ==========================================================
# 1) LONG VIEW — her maç 2 satır (home / away)
# ==========================================================
def build_long_view(df: pd.DataFrame) -> pd.DataFrame:
    """
    Wide maçı long forma çevirir:
    - Her maç için 2 satır (home, away)
    - NO-LEAK: Sonradan rolling için sadece geçmiş veriyi kullanacağız.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])

    # HOME perspective
    home = pd.DataFrame({
        "row_id": df["row_id"],
        "team": df["home_team"],
        "date": df["date"],
        "match_id": df["match_id"],
        "is_home": True,
        "gf": df["home_goals"],
        "ga": df["away_goals"],
        "pts": np.select(
            [df["result"] == 1, df["result"] == 0, df["result"] == -1],
            [3, 1, 0],
            default=0
        ),
        "xgf": df["lambda_home"],
        "xga": df["lambda_away"],
        "elo": df["home_elo"],
        "opp_elo": df["away_elo"],
    })

    # AWAY perspective
    away = pd.DataFrame({
        "row_id": df["row_id"],
        "team": df["away_team"],
        "date": df["date"],
        "match_id": df["match_id"],
        "is_home": False,
        "gf": df["away_goals"],
        "ga": df["home_goals"],
        "pts": np.select(
            [df["result"] == -1, df["result"] == 0, df["result"] == 1],
            [3, 1, 0],
            default=0
        ),
        "xgf": df["lambda_away"],
        "xga": df["lambda_home"],
        "elo": df["away_elo"],
        "opp_elo": df["home_elo"],
    })

    long_df = pd.concat([home, away], ignore_index=True)
    return long_df


# ==========================================================
# 2) ROLLING (NO LEAK) + EK METRİKLER
# ==========================================================
def add_rolling_features(long_df: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    """
    Takım bazında, zaman sıralı, NO-LEAK rolling feature’lar:
      - roll_gf, roll_ga, roll_pts, roll_xgf, roll_xga, roll_oppelo
      - roll_gd, roll_gd_var  (goal difference & variance)
      - elo_trend_5
      - xgf_trend_5
      - form_trend_5
      - momentum_5
    Tüm hesaplar shift(1) ile geleceği görmeyecek şekilde yapılıyor.
    """

    def _rolling(g: pd.DataFrame) -> pd.DataFrame:
        g = g.sort_values(["date", "match_id"])

        # base series
        gf = g["gf"]
        ga = g["ga"]
        pts = g["pts"]
        xgf = g["xgf"]
        xga = g["xga"]
        elo = g["elo"]
        opp_elo = g["opp_elo"]

        # goal difference
        gd = gf - ga

        # --- NO-LEAK ROLLING MEANLER (shift(1)) ---
        g["roll_gf"] = gf.shift(1).rolling(window, min_periods=1).mean()
        g["roll_ga"] = ga.shift(1).rolling(window, min_periods=1).mean()
        g["roll_pts"] = pts.shift(1).rolling(window, min_periods=1).mean()
        g["roll_xgf"] = xgf.shift(1).rolling(window, min_periods=1).mean()
        g["roll_xga"] = xga.shift(1).rolling(window, min_periods=1).mean()
        g["roll_oppelo"] = opp_elo.shift(1).rolling(window, min_periods=1).mean()

        # --- GD MEAN & VAR (NO LEAK) ---
        g["roll_gd"] = gd.shift(1).rolling(window, min_periods=1).mean()
        g["roll_gd_var"] = gd.shift(1).rolling(window, min_periods=2).var()

        # --- ELO TREND (son elo - son 5 elo ort.) ---
        elo_shift = elo.shift(1)
        elo_mean_5 = elo_shift.rolling(window, min_periods=1).mean()
        g["elo_trend_5"] = elo_shift - elo_mean_5

        # --- xGF TREND (son xgf - son 5 xgf ort.) ---
        xgf_shift = xgf.shift(1)
        xgf_mean_5 = xgf_shift.rolling(window, min_periods=1).mean()
        g["xgf_trend_5"] = xgf_shift - xgf_mean_5

        # --- FORM TREND (son pts - son 5 pts ort.) ---
        pts_shift = pts.shift(1)
        pts_mean_5 = pts_shift.rolling(window, min_periods=1).mean()
        g["form_trend_5"] = pts_shift - pts_mean_5

        # --- Basit MOMENTUM SKORU ---
        #   - roll_pts : puan formu
        #   - roll_gd  : gol averajı formu
        #   - elo_trend_5 / 100 : ELO değişimi (normalize)
        g["momentum_5"] = (
            0.5 * g["roll_pts"].fillna(0) +
            0.3 * g["roll_gd"].fillna(0) +
            0.2 * (g["elo_trend_5"].fillna(0) / 100.0)
        )

        return g

    # pandas >= 2.2 için include_groups=False, future warning çözümü
    long_roll = (
        long_df.groupby("team", group_keys=False)
        .apply(_rolling, include_groups=False)
    )

    return long_roll


# ==========================================================
# 3) MERGE LONG → WIDE
# ==========================================================
def merge_back(df: pd.DataFrame, long_roll: pd.DataFrame) -> pd.DataFrame:
    """
    long_roll içindeki rolling feature’ları wide tabloya geri yazar.
    row_id ile join yapılır.
    """
    df = df.copy()
    df = df.set_index("row_id")  # garanti

    home_lr = long_roll[long_roll["is_home"]].set_index("row_id")
    away_lr = long_roll[~long_roll["is_home"]].set_index("row_id")

    # --- HOME eski rolling'ler (no-leak versiyonları) ---
    df["home_rolling_gf_5_nl"] = home_lr["roll_gf"]
    df["home_rolling_ga_5_nl"] = home_lr["roll_ga"]
    df["home_rolling_pts_5_nl"] = home_lr["roll_pts"]
    df["home_rolling_xGF_5_nl"] = home_lr["roll_xgf"]
    df["home_rolling_xGA_5_nl"] = home_lr["roll_xga"]
    df["home_rolling_oppelo_5_nl"] = home_lr["roll_oppelo"]

    # --- AWAY eski rolling'ler ---
    df["away_rolling_gf_5_nl"] = away_lr["roll_gf"]
    df["away_rolling_ga_5_nl"] = away_lr["roll_ga"]
    df["away_rolling_pts_5_nl"] = away_lr["roll_pts"]
    df["away_rolling_xGF_5_nl"] = away_lr["roll_xgf"]
    df["away_rolling_xGA_5_nl"] = away_lr["roll_xga"]
    df["away_rolling_oppelo_5_nl"] = away_lr["roll_oppelo"]

    # --- YENİ METRİKLER: GD, VAR, TREND, MOMENTUM ---
    # HOME
    df["home_rolling_gd_5_nl"] = home_lr["roll_gd"]
    df["home_rolling_gd_var_5_nl"] = home_lr["roll_gd_var"]
    df["home_elo_trend_5_nl"] = home_lr["elo_trend_5"]
    df["home_xgf_trend_5_nl"] = home_lr["xgf_trend_5"]
    df["home_form_trend_5_nl"] = home_lr["form_trend_5"]
    df["home_momentum_5_nl"] = home_lr["momentum_5"]

    # AWAY
    df["away_rolling_gd_5_nl"] = away_lr["roll_gd"]
    df["away_rolling_gd_var_5_nl"] = away_lr["roll_gd_var"]
    df["away_elo_trend_5_nl"] = away_lr["elo_trend_5"]
    df["away_xgf_trend_5_nl"] = away_lr["xgf_trend_5"]
    df["away_form_trend_5_nl"] = away_lr["form_trend_5"]
    df["away_momentum_5_nl"] = away_lr["momentum_5"]

    return df.reset_index()


# ==========================================================
# MAIN
# ==========================================================
def main():
    print("================= NO-LEAK ROLLING BUILDER =================")

    print(f"[*] Loading: {INPUT_FILE}")
    df = pd.read_csv(INPUT_FILE)
    print("[OK] Loaded:", df.shape)

    # row_id wide tabloya göm
    if "row_id" not in df.columns:
        df["row_id"] = np.arange(len(df))

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # ---- 1) LONG
    print("[*] Building long view…")
    long_df = build_long_view(df)
    print("[OK] Long:", long_df.shape)

    # ---- 2) ROLLING
    print("[*] Computing rolling (shift(1), window=5)…")
    long_roll = add_rolling_features(long_df, window=5)
    print("[OK] Rolling done.")

    # ---- 3) MERGE
    print("[*] Merging back to wide…")
    df2 = merge_back(df, long_roll)
    print("[OK] Final shape:", df2.shape)

    # ---- 4) SAVE
    df2.to_csv(OUTPUT_FILE, index=False)
    print("[OK] Saved →", OUTPUT_FILE)
    print("================= DONE =================")


if __name__ == "__main__":
    main()
