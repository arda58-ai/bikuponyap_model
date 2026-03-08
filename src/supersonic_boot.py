import os
import sys
import json
import math
import subprocess
import sqlite3
import numpy as np
import pandas as pd
import lightgbm as lgb

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")

FULL_FEATURES_PATH = os.path.join(PROC_DIR, "full_features_noleak_fe.csv")
TODAY_ODDS_PATH    = os.path.join(PROC_DIR, "today_odds_from_api.csv")
GOAL_MODEL_PATH    = os.path.join(PROC_DIR, "goal_model_lgbm.txt")
GOAL_META_PATH     = os.path.join(PROC_DIR, "goal_model_meta.json")
DB_PATH = "/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db"

def db_hazirla_vip():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS vip_analizler (id INTEGER PRIMARY KEY AUTOINCREMENT, tarih TEXT, mac_adi TEXT, risk_skoru REAL, karar TEXT, oran REAL, tahmin_tipi TEXT, kaynak TEXT, spor TEXT, mac_kodu TEXT)''')
    c.execute("DELETE FROM vip_analizler")
    conn.commit()
    conn.close()

def db_kaydet_vip(tarih, mac_adi, skor, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO vip_analizler (tarih, mac_adi, risk_skoru, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (tarih, mac_adi, skor, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu))
    conn.commit()
    conn.close()

def build_model_g_coupon(df_today: pd.DataFrame) -> pd.DataFrame:
    if not os.path.exists(GOAL_MODEL_PATH): return pd.DataFrame()
    model_g = lgb.Booster(model_file=GOAL_MODEL_PATH)
    with open(GOAL_META_PATH, "r", encoding="utf-8") as f: feat_cols_g = json.load(f)["feature_cols"]

    df_hist = pd.DataFrame()
    mean_vec = pd.Series(dtype=float)
    team_last = pd.DataFrame()
    
    if os.path.exists(FULL_FEATURES_PATH):
        df_hist = pd.read_csv(FULL_FEATURES_PATH)
        mean_vec = df_hist[feat_cols_g].mean()
        df_hist["date"] = pd.to_datetime(df_hist["date"])
        df_hist = df_hist.sort_values("date")
        last_home = df_hist.drop_duplicates(subset=["home_team"], keep="last").set_index("home_team")
        last_away = df_hist.drop_duplicates(subset=["away_team"], keep="last").set_index("away_team")
        team_last = pd.concat([last_home, last_away])
        team_last = team_last[~team_last.index.duplicated(keep="last")]

    X_rows, meta_rows = [], []
    for _, r in df_today.iterrows():
        home, away = str(r["home_team"]), str(r["away_team"])
        v = mean_vec.copy()
        if "B365H" in v.index and pd.notna(r.get("B365H")): v["B365H"] = float(r["B365H"])
        if "B365D" in v.index and pd.notna(r.get("B365D")): v["B365D"] = float(r["B365D"])
        if "B365A" in v.index and pd.notna(r.get("B365A")): v["B365A"] = float(r["B365A"])
        
        if home in team_last.index:
            row_h = team_last.loc[home]
            for col in feat_cols_g:
                if col.startswith("home_") and col in row_h.index: v[col] = row_h[col]
        if away in team_last.index:
            row_a = team_last.loc[away]
            for col in feat_cols_g:
                if col.startswith("away_") and col in row_a.index: v[col] = row_a[col]
                    
        X_rows.append(v.values)
        meta_rows.append(r)

    X_today = pd.DataFrame(X_rows, columns=mean_vec.index)
    for c in feat_cols_g:
        if c not in X_today.columns: X_today[c] = 0.0
    X_today = X_today[feat_cols_g].copy()
    X_today.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_today.fillna(0, inplace=True)
    
    pred_goals = np.clip(model_g.predict(X_today.values), 0.2, 6.0)
    
    results = []
    meta_df = pd.DataFrame(meta_rows)
    for pos in range(min(len(meta_df), len(pred_goals))):
        r = meta_df.iloc[pos]
        lam = pred_goals[pos]
        ml_goals = int(math.floor(lam))
        p_over25 = 1 - (math.exp(-lam) * (1 + lam + (lam**2)/2))
        p_1h_over05 = 1 - math.exp(-(lam * 0.45))
        
        if lam >= 3.20: tempo = "Very high tempo"
        elif lam >= 2.90: tempo = "High tempo"
        elif lam >= 2.60: tempo = "Medium-high tempo"
        else: tempo = "Standard tempo"
            
        results.append({
            "date": r["date"], "datetime_tr": r.get("datetime_tr", ""), "league": r["league"],
            "home_team": r["home_team"], "away_team": r["away_team"],
            "B365O25": r.get("B365O25", 1.0), "lambda_total": lam, 
            "ml_goals": ml_goals, "p_over25": p_over25, "p_1h_over05": p_1h_over05, "tempo": tempo
        })
        
    df_results = pd.DataFrame(results)
    if not df_results.empty: 
        df_results = df_results.sort_values("lambda_total", ascending=False).reset_index(drop=True)
    return df_results

def main():
    if not os.path.exists(TODAY_ODDS_PATH): return
    df_today = pd.read_csv(TODAY_ODDS_PATH)
    if df_today.empty: return
        
    db_hazirla_vip()
    df_g = build_model_g_coupon(df_today)
    
    if not df_g.empty:
        print("\n===== TODAY GOAL REGRESSION (Model-G) =====")
        for _, r in df_g[df_g['p_over25'] >= 0.60].iterrows():
            date_str = str(r["date"])[:10]
            league_str = str(r["league"])
            home, away = r["home_team"], r["away_team"]
            
            print(f"{date_str} | {league_str} | {home} - {away} → λ_total={r['lambda_total']:.2f}, ML_goals={r['ml_goals']}, p(Over2.5)={r['p_over25']:.3f}, 1H Over0.5={r['p_1h_over05']:.3f} [{r['tempo']}]")
            
            tarih_db = str(r["datetime_tr"])[:16].replace("T", " ") if r["datetime_tr"] else date_str
            oran = float(r["B365O25"]) if pd.notna(r["B365O25"]) else 1.0
            risk_skoru = round(100 - (float(r["p_over25"]) * 100), 1)
            mac_kodu = str(abs(hash(home + away)) % 100000)
            
            db_kaydet_vip(tarih_db, f"{home} vs {away}", risk_skoru, r['tempo'], oran, "2.5 ÜST", "Model-G", "Futbol", mac_kodu)

    # Boot bittikten sonra Supersonic Today pipeline'ı çalıştır (1X2 + OU2.5 kuponları da vip_analizler'e eklenir)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pipeline_path = os.path.join(script_dir, "model_supersonic_today_pipeline.py")
    if os.path.exists(pipeline_path):
        print("\n[*] Supersonic Today pipeline çalıştırılıyor...")
        rc = subprocess.run(
            [sys.executable, pipeline_path],
            cwd=BASE_DIR,
        )
        if rc.returncode != 0:
            print("[!] Pipeline çıkış kodu:", rc.returncode)
        else:
            print("[OK] Boot + pipeline tamamlandı.")
    else:
        print("[!] Pipeline bulunamadı:", pipeline_path)

if __name__ == "__main__":
    main()