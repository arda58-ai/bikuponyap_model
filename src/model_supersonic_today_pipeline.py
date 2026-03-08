# ======================================================
# model_supersonic_today_pipeline.py
# Model-B (1X2) + OU2.5 odds-only + Supersonic Final
# ======================================================
import os
import sys
import json
import sqlite3
import random
import urllib.request
import urllib.error
import numpy as np
import pandas as pd
import lightgbm as lgb
from datetime import datetime, date

# Model-G lambda verileri için (son 4'lü eksiksiz özet)
try:
    _src_dir = os.path.dirname(os.path.abspath(__file__))
    if _src_dir not in sys.path:
        sys.path.insert(0, _src_dir)
    import supersonic_boot as _sb
    _HAS_MODEL_G = True
except Exception:
    _HAS_MODEL_G = False

# -------------------------
# PATHS
# -------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")

FULL_FEATURES_PATH        = os.path.join(PROC_DIR, "full_features_noleak_fe.csv")
TODAY_ODDS_PATH           = os.path.join(PROC_DIR, "today_odds_from_api.csv")

MODEL_B_PATH              = os.path.join(PROC_DIR, "lgbm_model_calibrated.txt")
PLATT_B_PATH              = os.path.join(PROC_DIR, "platt_params.json")
FEATURE_COLS_B_PATH       = os.path.join(PROC_DIR, "model_b_feature_cols.json")

OU25_MODEL_PATH           = os.path.join(PROC_DIR, "ou25_model_from_odds.txt")
OU25_PLATT_PATH           = os.path.join(PROC_DIR, "platt_ou25_from_odds.json")
OU25_FEATURES_PATH        = os.path.join(PROC_DIR, "ou25_features_from_odds.json")

COUPON_1X2_SAVE_PATH      = os.path.join(PROC_DIR, "today_coupon_supersonic_1x2.csv")
COUPON_OU25_SAVE_PATH     = os.path.join(PROC_DIR, "today_coupon_supersonic_ou25.csv")
COUPON_COMBO_SAVE_PATH    = os.path.join(PROC_DIR, "today_coupon_supersonic_combo.csv")

DB_PATH = "/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db"

# API/kupon lig adları → full_features_noleak_fe.csv içindeki lig kodu (master verisi F1, SP1, T1, E0, D1, I1 kullanıyor)
LEAGUE_API_TO_DATA = {
    "Ligue 1 - France": "F1",
    "La Liga - Spain": "SP1",
    "Turkey Super League": "T1",
    "Super Lig": "T1",
    "Premier League - England": "E0",
    "English Premier League": "E0",
    "Bundesliga - Germany": "D1",
    "Serie A - Italy": "I1",
    "Italian Serie A": "I1",
}
# API/kupon takım adları → veri dosyasındaki takım adı (puan durumu eşleşmesi için)
TEAM_API_TO_DATA = {
    "Rayo Vallecano": "Vallecano",
    "RC Lens": "Lens",
}


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
# PUAN DURUMU / AGRESIF / AVERAJ / GOLCU (lig tablosu – sadece ek gösterim, algoritmaya dokunmaz)
# -------------------------
# Kullanılan veriler (full_features_noleak_fe.csv, en güncel sezon):
#   - result (1=ev, 0=berabere, -1=deplasman) → puan (3/1/0)
#   - home_goals, away_goals → takım bazında atılan/yenen gol → averaj (GF-GA), golcu (GF)
# Sıra: önce puana göre, eşitlikte averaja göre (klasik lig kuralı).
# Agresif beklenti: tabloda daha alttaki takım (puan ihtiyacı varsayımıyla daha agresif).
# Golcu beklenti: sezonluk atılan gol (GF) daha yüksek olan taraf.
def _puan_durumu_ve_agresif(full_features_path: str, df_matches: pd.DataFrame) -> pd.DataFrame:
    if not os.path.exists(full_features_path) or df_matches is None or df_matches.empty:
        return pd.DataFrame()
    req = ["league", "home_team", "away_team"]
    if not all(c in df_matches.columns for c in req):
        return pd.DataFrame()
    avail = pd.read_csv(full_features_path, nrows=0).columns.tolist()
    usecols = [c for c in ["date", "league", "season", "home_team", "away_team", "result", "home_goals", "away_goals"] if c in avail]
    df = pd.read_csv(full_features_path, usecols=usecols, nrows=None)
    if "result" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df["home_pts"] = df["result"].map({1: 3, 0: 1, -1: 0})
    df["away_pts"] = df["result"].map({1: 0, 0: 1, -1: 3})
    has_goals = "home_goals" in df.columns and "away_goals" in df.columns
    if has_goals:
        df["home_gf"] = df["home_goals"]
        df["home_ga"] = df["away_goals"]
        df["away_gf"] = df["away_goals"]
        df["away_ga"] = df["home_goals"]
    league_latest_season = df.groupby("league")["season"].max().to_dict()
    out_rows = []
    for _, row in df_matches.iterrows():
        league, h, a = row["league"], row["home_team"], row["away_team"]
        season = league_latest_season.get(league)
        if season is None:
            out_rows.append(_puan_row(league, h, a, None))
            continue
        g = df[(df["league"] == league) & (df["season"] == season)]
        if g.empty:
            out_rows.append(_puan_row(league, h, a, None))
            continue
        home_pts = g.groupby("home_team")["home_pts"].sum()
        away_pts = g.groupby("away_team")["away_pts"].sum()
        all_teams = home_pts.index.union(away_pts.index).unique()
        team_pts = home_pts.reindex(all_teams).fillna(0) + away_pts.reindex(all_teams).fillna(0)
        if has_goals:
            home_gf = g.groupby("home_team")["home_gf"].sum()
            home_ga = g.groupby("home_team")["home_ga"].sum()
            away_gf = g.groupby("away_team")["away_gf"].sum()
            away_ga = g.groupby("away_team")["away_ga"].sum()
            team_gf = home_gf.reindex(all_teams).fillna(0) + away_gf.reindex(all_teams).fillna(0)
            team_ga = home_ga.reindex(all_teams).fillna(0) + away_ga.reindex(all_teams).fillna(0)
            team_avg = team_gf - team_ga
            team_pts = team_pts.astype(float)
            team_avg = team_avg.astype(float)
            # Sıra: önce puan (azalan), sonra averaj (azalan)
            order = team_pts.index[team_pts.values.argsort()[::-1]]
            tied = team_pts.loc[order]
            idx = 0
            position = pd.Series(index=team_pts.index, dtype=object)
            for _, grp in tied.groupby(tied):
                grp_teams = grp.index.tolist()
                if len(grp_teams) > 1 and has_goals:
                    grp_avg = team_avg.reindex(grp_teams).fillna(0)
                    grp_teams = grp_avg.sort_values(ascending=False).index.tolist()
                for t in grp_teams:
                    position.loc[t] = idx + 1
                    idx += 1
        else:
            team_pts = team_pts.sort_values(ascending=False)
            position = pd.Series(np.arange(1, len(team_pts) + 1), index=team_pts.index)
            team_avg = None
            team_gf = None
        hp, ap = position.get(h), position.get(a)
        hpts, apts = team_pts.get(h), team_pts.get(a)
        havg = (team_avg.get(h) if team_avg is not None else None)
        aavg = (team_avg.get(a) if team_avg is not None else None)
        hgf = (team_gf.get(h) if has_goals and team_gf is not None else None)
        agf = (team_gf.get(a) if has_goals and team_gf is not None else None)
        if pd.notna(hp) and pd.notna(ap):
            agresif = "Ev" if hp > ap else ("Deplasman" if ap > hp else "Belirsiz")
        else:
            agresif = "—"
        if has_goals and pd.notna(hgf) and pd.notna(agf):
            golcu = "Ev" if hgf > agf else ("Deplasman" if agf > hgf else "Belirsiz")
        else:
            golcu = "—"
        out_rows.append({
            "league": league,
            "home_team": h,
            "away_team": a,
            "home_pos": int(hp) if pd.notna(hp) else "—",
            "away_pos": int(ap) if pd.notna(ap) else "—",
            "home_pts": int(hpts) if pd.notna(hpts) else "—",
            "away_pts": int(apts) if pd.notna(apts) else "—",
            "home_avg": int(havg) if pd.notna(havg) else "—",
            "away_avg": int(aavg) if pd.notna(aavg) else "—",
            "agresif_beklenti": agresif,
            "golcu_beklenti": golcu,
        })
    return pd.DataFrame(out_rows)


def _puan_row(league, h, a, _):
    return {
        "league": league, "home_team": h, "away_team": a,
        "home_pos": "—", "away_pos": "—", "home_pts": "—", "away_pts": "—",
        "home_avg": "—", "away_avg": "—",
        "agresif_beklenti": "—", "golcu_beklenti": "—",
    }


def _lig_tablolari_build(full_features_path: str, leagues: list) -> dict:
    """
    Verilen ligler için (en güncel sezon) tam puan durumu tablosu üretir.
    Döner: { lig_adi: DataFrame(sira, takim, puan, averaj, gf, ga) }
    """
    if not os.path.exists(full_features_path) or not leagues:
        return {}
    avail = pd.read_csv(full_features_path, nrows=0).columns.tolist()
    usecols = [c for c in ["date", "league", "season", "home_team", "away_team", "result", "home_goals", "away_goals"] if c in avail]
    df = pd.read_csv(full_features_path, usecols=usecols, nrows=None)
    if "result" not in df.columns:
        return {}
    df["home_pts"] = df["result"].map({1: 3, 0: 1, -1: 0})
    df["away_pts"] = df["result"].map({1: 0, 0: 1, -1: 3})
    has_goals = "home_goals" in df.columns and "away_goals" in df.columns
    if has_goals:
        df["home_gf"], df["home_ga"] = df["home_goals"], df["away_goals"]
        df["away_gf"], df["away_ga"] = df["away_goals"], df["home_goals"]
    league_season = df.groupby("league")["season"].max().to_dict()
    out = {}
    for league in leagues:
        season = league_season.get(league)
        if season is None:
            continue
        g = df[(df["league"] == league) & (df["season"] == season)]
        if g.empty:
            continue
        home_pts = g.groupby("home_team")["home_pts"].sum()
        away_pts = g.groupby("away_team")["away_pts"].sum()
        all_teams = home_pts.index.union(away_pts.index).unique()
        team_pts = home_pts.reindex(all_teams).fillna(0) + away_pts.reindex(all_teams).fillna(0)
        if has_goals:
            team_gf = g.groupby("home_team")["home_gf"].sum().reindex(all_teams).fillna(0) + g.groupby("away_team")["away_gf"].sum().reindex(all_teams).fillna(0)
            team_ga = g.groupby("home_team")["home_ga"].sum().reindex(all_teams).fillna(0) + g.groupby("away_team")["away_ga"].sum().reindex(all_teams).fillna(0)
            team_avg = team_gf - team_ga
            team_pts = team_pts.astype(float)
            team_avg = team_avg.astype(float)
            order = team_pts.index[team_pts.values.argsort()[::-1]]
            tied = team_pts.loc[order]
            idx, position = 0, pd.Series(index=team_pts.index, dtype=object)
            for _, grp in tied.groupby(tied):
                grp_teams = grp.index.tolist()
                if len(grp_teams) > 1:
                    grp_avg = team_avg.reindex(grp_teams).fillna(0)
                    grp_teams = grp_avg.sort_values(ascending=False).index.tolist()
                for t in grp_teams:
                    position.loc[t] = idx + 1
                    idx += 1
            tab = pd.DataFrame(index=position.index)
            tab["sira"] = position.astype(int)
            tab["takim"] = tab.index
            tab["puan"] = team_pts.reindex(tab.index).fillna(0).astype(int)
            tab["averaj"] = team_avg.reindex(tab.index).fillna(0).astype(int)
            tab["gf"] = team_gf.reindex(tab.index).fillna(0).astype(int)
            tab["ga"] = team_ga.reindex(tab.index).fillna(0).astype(int)
        else:
            team_pts = team_pts.sort_values(ascending=False)
            tab = pd.DataFrame({
                "sira": np.arange(1, len(team_pts) + 1),
                "takim": team_pts.index,
                "puan": team_pts.values.astype(int),
                "averaj": 0,
                "gf": 0,
                "ga": 0,
            })
        tab = tab.sort_values("sira").reset_index(drop=True)
        out[league] = tab
    return out


def _puan_durumu_analiz_yorumu(r: dict, n_teams: int) -> str:
    """
    Tabloya göre kime yarıyor / kim daha agresif oynar – kısa analiz cümlesi.
    """
    hp, ap = r.get("home_pos"), r.get("away_pos")
    hpts, apts = r.get("home_pts"), r.get("away_pts")
    agresif = r.get("agresif_beklenti", "—")
    if hp in (None, "—") or ap in (None, "—") or not isinstance(hp, (int, np.integer)) or not isinstance(ap, (int, np.integer)):
        return "Puan durumu verisi yok."
    n = max(n_teams, 1)
    # Bölge etiketleri (üst / orta / küme düşme)
    def _bolge(pos):
        if pos <= min(3, n):
            return "üst sıralar"
        if pos >= max(n - 2, 1):
            return "küme düşme bölgesi"
        return "orta sıralar"
    ev_bolge, dep_bolge = _bolge(int(hp)), _bolge(int(ap))
    if agresif == "Ev":
        return f"Ev {int(hp)}. sırada ({int(hpts)} puan, {ev_bolge}), Dep {int(ap)}. sırada ({int(apts)} puan, {dep_bolge}). Ev tabloda daha altta; sıralamayı korumak veya yukarı çıkmak için daha agresif oynayacaktır."
    if agresif == "Deplasman":
        return f"Ev {int(hp)}. sırada ({int(hpts)} puan, {ev_bolge}), Dep {int(ap)}. sırada ({int(apts)} puan, {dep_bolge}). Deplasman tabloda daha altta; sıralamayı korumak veya yukarı çıkmak için daha agresif oynayacaktır."
    return f"Ev {int(hp)}. sırada ({int(hpts)} puan, {ev_bolge}), Dep {int(ap)}. sırada ({int(apts)} puan, {dep_bolge}). Her iki takım da tabloda yakın bölgede; puan ihtiyacı benzer, agresiflik dengeli olabilir."


# -------------------------
# PUAN DURUMU – HARİCİ API (gerçek sıralama; STANDINGS_API_URL set edilirse kullanılır)
# -------------------------
STANDINGS_API_URL = os.environ.get("STANDINGS_API_URL", "").strip() or None


def _fetch_standings_from_api(url: str) -> dict:
    """
    GET url → JSON { "F1": [ {team, position, points, goals_for, goals_against, goal_difference?}, ... ], ... }
    Döner: { "F1": DataFrame(sira, takim, puan, averaj, gf, ga), ... } veya hata durumunda {}.
    """
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        print("\n[STANDINGS API] Veri alınamadı:", e)
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for league_key, teams in data.items():
        if not isinstance(teams, list):
            continue
        rows = []
        for t in teams:
            if not isinstance(t, dict):
                continue
            team = t.get("team")
            pos = t.get("position")
            pts = t.get("points")
            gf = t.get("goals_for")
            ga = t.get("goals_against")
            gd = t.get("goal_difference")
            if team is None or pos is None or pts is None:
                continue
            if gf is None:
                gf = 0
            if ga is None:
                ga = 0
            if gd is None and gf is not None and ga is not None:
                gd = int(gf) - int(ga)
            rows.append({"sira": int(pos), "takim": str(team), "puan": int(pts), "averaj": int(gd) if gd is not None else 0, "gf": int(gf), "ga": int(ga)})
        if rows:
            out[league_key] = pd.DataFrame(rows).sort_values("sira").reset_index(drop=True)
    return out


def _puan_from_tablolar(tablolar: dict, df_matches: pd.DataFrame) -> pd.DataFrame:
    """
    tablolar = { lig_kodu: DataFrame(sira, takim, puan, averaj, gf, ga) }. df_matches'ta league, home_team, away_team.
    Her maç için puan durumu + agresif + golcu satırı üretir (_puan_durumu_ve_agresif ile aynı kolonlar).
    """
    if not tablolar or df_matches is None or df_matches.empty:
        return pd.DataFrame()
    req = ["league", "home_team", "away_team"]
    if not all(c in df_matches.columns for c in req):
        return pd.DataFrame()
    out_rows = []
    for _, row in df_matches.iterrows():
        league, h, a = row["league"], row["home_team"], row["away_team"]
        tab = tablolar.get(league)
        if tab is None or tab.empty:
            out_rows.append({"league": league, "home_team": h, "away_team": a, "home_pos": "—", "away_pos": "—", "home_pts": "—", "away_pts": "—", "home_avg": "—", "away_avg": "—", "agresif_beklenti": "—", "golcu_beklenti": "—"})
            continue
        tab_team = tab.set_index("takim")
        hp = tab_team.loc[h, "sira"] if h in tab_team.index else None
        ap = tab_team.loc[a, "sira"] if a in tab_team.index else None
        hpts = tab_team.loc[h, "puan"] if h in tab_team.index else None
        apts = tab_team.loc[a, "puan"] if a in tab_team.index else None
        havg = tab_team.loc[h, "averaj"] if h in tab_team.index else None
        aavg = tab_team.loc[a, "averaj"] if a in tab_team.index else None
        hgf = tab_team.loc[h, "gf"] if h in tab_team.index else None
        agf = tab_team.loc[a, "gf"] if a in tab_team.index else None
        if pd.notna(hp) and pd.notna(ap):
            agresif = "Ev" if hp > ap else ("Deplasman" if ap > hp else "Belirsiz")
        else:
            agresif = "—"
        if pd.notna(hgf) and pd.notna(agf):
            golcu = "Ev" if hgf > agf else ("Deplasman" if agf > hgf else "Belirsiz")
        else:
            golcu = "—"
        out_rows.append({
            "league": league,
            "home_team": h,
            "away_team": a,
            "home_pos": int(hp) if pd.notna(hp) else "—",
            "away_pos": int(ap) if pd.notna(ap) else "—",
            "home_pts": int(hpts) if pd.notna(hpts) else "—",
            "away_pts": int(apts) if pd.notna(apts) else "—",
            "home_avg": int(havg) if pd.notna(havg) else "—",
            "away_avg": int(aavg) if pd.notna(aavg) else "—",
            "agresif_beklenti": agresif,
            "golcu_beklenti": golcu,
        })
    return pd.DataFrame(out_rows)


# -------------------------
# CONFIG
# -------------------------
TARGET_COUPON_MATCHES_1X2  = 4
TARGET_COUPON_MATCHES_OU25 = 4

MIN_ODDS_1X2 = 1.40
MAX_ODDS_1X2 = 3.00

MIN_OU25_ODDS = 1.20
MAX_OU25_ODDS = 2.50
MIN_P_OVER25  = 0.40   # kalibre over olasılığı eşiği

# Sadece "bugün" için mi seçim yapalım?
ONLY_TODAY = True   # gerekirse False yapıp tüm future günleri kapsarsın


# -------------------------
# HELPER FUNCTIONS
# -------------------------
def platt_multiclass_predict(probs: np.ndarray, params: dict) -> np.ndarray:
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


def platt_binary_predict(p_raw: np.ndarray, a: float, b: float) -> np.ndarray:
    p_raw = p_raw.clip(1e-6, 1 - 1e-6)
    z = np.log(p_raw / (1 - p_raw))
    logits = a + b * z
    return 1.0 / (1.0 + np.exp(-logits))


def implied_probs_from_odds(oh, od, oa):
    inv_h, inv_d, inv_a = 1.0 / oh, 1.0 / od, 1.0 / oa
    total = inv_h + inv_d + inv_a
    return inv_h / total, inv_d / total, inv_a / total


def build_ou25_features_from_odds(df_in: pd.DataFrame) -> pd.DataFrame:
    """
    model_ou25_from_odds.py ile uyumlu odds-only feature builder
    """
    df_out = df_in[["B365H", "B365D", "B365A"]].copy()

    # Implied probabilities
    ip_h, ip_d, ip_a = implied_probs_from_odds(
        df_out["B365H"].values,
        df_out["B365D"].values,
        df_out["B365A"].values,
    )
    df_out["ip_home"] = ip_h
    df_out["ip_draw"] = ip_d
    df_out["ip_away"] = ip_a

    # Spread features
    df_out["fav_prob"] = df_out[["ip_home", "ip_draw", "ip_away"]].max(axis=1)
    df_out["und_prob"] = df_out[["ip_home", "ip_draw", "ip_away"]].min(axis=1)
    df_out["prob_gap"] = df_out["fav_prob"] - df_out["und_prob"]

    # Log-odds
    df_out["log_oh"] = np.log(df_out["B365H"])
    df_out["log_od"] = np.log(df_out["B365D"])
    df_out["log_oa"] = np.log(df_out["B365A"])

    return df_out


# -------------------------
# 1X2 COUPON (MODEL-B)
# -------------------------
def build_supersonic_1x2_coupon(df_today: pd.DataFrame) -> pd.DataFrame:
    """
    Model-B ile %100 uyumlu, team-centric full-feature tahmin + kupon üretimi.
    """
    # Model-B artefaktları
    model_b = lgb.Booster(model_file=MODEL_B_PATH)

    with open(PLATT_B_PATH, "r", encoding="utf-8") as f:
        platt_b = json.load(f)

    with open(FEATURE_COLS_B_PATH, "r", encoding="utf-8") as f:
        feature_cols_b = json.load(f)

    # Tarihsel full_features
    hist = pd.read_csv(FULL_FEATURES_PATH)
    hist["date"] = pd.to_datetime(hist["date"])
    hist = hist.sort_values("date")

    # Sadece feature kolonları
    hist_feat_cols = [c for c in feature_cols_b if c in hist.columns]
    hist_base = hist[hist_feat_cols].copy()
    hist_base.replace([np.inf, -np.inf], np.nan, inplace=True)
    hist_base.fillna(0, inplace=True)

    # Global fallback
    mean_vector = hist_base.mean(axis=0)

    # --- TEAM-CENTRIC HISTORY ---
    print("[*] Building team-centric history for Model-B…")

    home_hist = hist.rename(columns={"home_team": "team"}).copy()
    home_hist["__is_home"] = 1

    away_hist = hist.rename(columns={"away_team": "team"}).copy()
    away_hist["__is_home"] = 0

    team_hist = pd.concat([home_hist, away_hist], ignore_index=True)
    team_hist = team_hist[["team", "date"] + hist_feat_cols].copy()

    team_last = (
        team_hist
        .sort_values("date")
        .groupby("team")
        .tail(1)
        .set_index("team")
    )

    print(f"[INFO] team_last count: {len(team_last)}")

    # --- BUGÜN MAÇLARI İÇİN FEATURE GENERATION ---
    X_rows   = []
    meta_rows = []

    for _, r in df_today.iterrows():
        home = str(r["home_team"])
        away = str(r["away_team"])

        v = mean_vector.copy()

        # Odds override
        if "B365H" in v.index: v["B365H"] = float(r["B365H"])
        if "B365D" in v.index: v["B365D"] = float(r["B365D"])
        if "B365A" in v.index: v["B365A"] = float(r["B365A"])

        # HOME team last features
        if home in team_last.index:
            row_h = team_last.loc[home]
            for col in feature_cols_b:
                if col.startswith("home_") and col in row_h.index:
                    v[col] = row_h[col]

        # AWAY team last features
        if away in team_last.index:
            row_a = team_last.loc[away]
            for col in feature_cols_b:
                if col.startswith("away_") and col in row_a.index:
                    v[col] = row_a[col]

        X_rows.append(v.values)
        meta_rows.append({
            "date":        r["date"],
            "datetime_tr": r.get("datetime_tr", ""),
            "league":      r["league"],
            "home_team":   home,
            "away_team":   away,
            "B365H":       float(r["B365H"]),
            "B365D":       float(r["B365D"]),
            "B365A":       float(r["B365A"]),
        })

    X_today = pd.DataFrame(X_rows, columns=mean_vector.index)

    # Eksik feature kolonlarını ekle
    for c in feature_cols_b:
        if c not in X_today.columns:
            X_today[c] = 0.0

    X_today = X_today[feature_cols_b].copy()
    X_today.replace([np.inf, -np.inf], np.nan, inplace=True)
    X_today.fillna(0, inplace=True)

    meta_df = pd.DataFrame(meta_rows)

    # Tahmin + kalibrasyon
    print("[*] Predicting 1X2 with Model-B…")
    probs_raw = model_b.predict(X_today.values)
    probs_cal = platt_multiclass_predict(probs_raw, platt_b)

    meta_df["prob_cal_away"] = probs_cal[:, 0]
    meta_df["prob_cal_draw"] = probs_cal[:, 1]
    meta_df["prob_cal_home"] = probs_cal[:, 2]

    # EV hesapla
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

    # Her maç için en iyi taraf (EV max) + odds filtresi
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

        if odd < MIN_ODDS_1X2 or odd > MAX_ODDS_1X2:
            continue

        candidates.append({
            "date":        r["date"],
            "datetime_tr": r["datetime_tr"],
            "league":      r["league"],
            "market":      "1X2",
            "home_team":   r["home_team"],
            "away_team":   r["away_team"],
            "B365H":       r["B365H"],
            "B365D":       r["B365D"],
            "B365A":       r["B365A"],
            "bet_selection": side,
            "bet_odds":     odd,
            "bet_ev":       ev,
            "bet_prob":     p,
        })

    if not candidates:
        return pd.DataFrame()

    df_bets = pd.DataFrame(candidates)
    df_bets = df_bets.sort_values("bet_ev", ascending=False).reset_index(drop=True)

    if len(df_bets) >= TARGET_COUPON_MATCHES_1X2:
        coupon = df_bets.head(TARGET_COUPON_MATCHES_1X2).copy()
    else:
        coupon = df_bets.copy()

    return coupon


# -------------------------
# OU2.5 COUPON
# -------------------------
def build_ou25_coupon(df_today: pd.DataFrame) -> pd.DataFrame:
    """
    Odds-only OU2.5 modeli ile günlük kupon.
    """
    ou_model = lgb.Booster(model_file=OU25_MODEL_PATH)

    with open(OU25_PLATT_PATH, "r", encoding="utf-8") as f:
        platt_ou = json.load(f)

    with open(OU25_FEATURES_PATH, "r", encoding="utf-8") as f:
        ou_feat_json = json.load(f)
        ou_features = ou_feat_json["features"]

    # Odds eksik olanları at
    df = df_today.dropna(subset=["B365H", "B365D", "B365A"]).copy()
    if df.empty:
        return pd.DataFrame()

    X = build_ou25_features_from_odds(df)

    # Sadece eğitimde kullanılan feature’ları sırayla al
    X = X[ou_features].copy()
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(0, inplace=True)

    print("[*] Predicting OU2.5 (odds-only)…")
    p_raw = ou_model.predict(X.values)
    a, b = platt_ou["a"], platt_ou["b"]
    p_cal = platt_binary_predict(p_raw, a, b)   # p(Over 2.5)

    df_out = df.copy()
    df_out["p_over25_cal"] = p_cal

    # Odds filtresi (Bkz: Over 2.5 odds sütunu yok; burayı future’da genişletebilirsin)
    # Şimdilik sadece p_over25 sıralıyoruz, odds aralığı check yok.
    df_out = df_out.sort_values("p_over25_cal", ascending=False).reset_index(drop=True)

    # Threshold + TOP-N
    df_out = df_out[df_out["p_over25_cal"] >= MIN_P_OVER25].copy()
    if df_out.empty:
        return pd.DataFrame()

    if len(df_out) > TARGET_COUPON_MATCHES_OU25:
        df_out = df_out.head(TARGET_COUPON_MATCHES_OU25).copy()

    # Output format
    coupon = pd.DataFrame({
        "date":        df_out["date"],
        "datetime_tr": df_out.get("datetime_tr", ""),
        "league":      df_out["league"],
        "market":      "OU2.5",
        "home_team":   df_out["home_team"],
        "away_team":   df_out["away_team"],
        "B365H":       df_out["B365H"],
        "B365D":       df_out["B365D"],
        "B365A":       df_out["B365A"],
        "bet_selection": "Over 2.5",
        "bet_odds":    np.nan,  # API Over/Under odds gelirse buraya yazarsın
        "bet_ev":      np.nan,  # EV hesaplamak için U/O odds lazım
        "bet_prob":    df_out["p_over25_cal"],
    })

    return coupon


# -------------------------
# COMBINED SUPersonic Coupon
# -------------------------
def build_combined_coupon(coupon_1x2: pd.DataFrame,
                          coupon_ou: pd.DataFrame,
                          target_size: int = 4) -> pd.DataFrame:
    """
    Basit kombinasyon: 2 maç 1X2 + 2 maç OU2.5 (mümkünse farklı maçlar).
    """
    if coupon_1x2 is None or coupon_1x2.empty:
        if coupon_ou is None or coupon_ou.empty:
            return pd.DataFrame()
        # sadece OU varsa, ordan kısalt
        return coupon_ou.head(target_size).copy()

    if coupon_ou is None or coupon_ou.empty:
        # sadece 1X2 varsa
        return coupon_1x2.head(target_size).copy()

    # 1X2 tarafını EV’ye göre sıralı varsayıyoruz
    c1 = coupon_1x2.copy()
    if "bet_ev" in c1.columns:
        c1 = c1.sort_values("bet_ev", ascending=False)

    # OU tarafını prob’a göre sıralı varsayıyoruz
    c2 = coupon_ou.copy()
    if "bet_prob" in c2.columns:
        c2 = c2.sort_values("bet_prob", ascending=False)

    # 2+2 dağıt
    take_1x2 = min(2, len(c1))
    take_ou  = min(2, len(c2))

    selected_1x2 = c1.head(take_1x2).copy()

    # OU tarafında aynı maçı seçmemeye çalış
    used_pairs = set(
        (h, a) for h, a in zip(selected_1x2["home_team"], selected_1x2["away_team"])
    )

    ou_rows = []
    for _, r in c2.iterrows():
        pair = (r["home_team"], r["away_team"])
        if pair in used_pairs:
            continue
        ou_rows.append(r)
        if len(ou_rows) >= take_ou:
            break

    selected_ou = pd.DataFrame(ou_rows)

    combo = pd.concat([selected_1x2, selected_ou], ignore_index=True)

    # Eğer hâlâ 4 değilse, eldekilerle doldur
    if len(combo) > target_size:
        combo = combo.head(target_size)
    return combo


# -------------------------
# MAIN PIPELINE
# -------------------------
def main():
    # 0) Bugünkü odds
    print("[*] Loading today's odds from API csv…")
    df_today = pd.read_csv(TODAY_ODDS_PATH)
    print(f"[OK] Raw rows: {len(df_today)}")

    # Sadece tam odds olanlar
    df_today = df_today.dropna(subset=["B365H", "B365D", "B365A"]).copy()
    if df_today.empty:
        print("[WARN] No rows with full 1X2 odds. Exiting.")
        return

    # Sadece bugünün maçlarını filtrele (opsiyonel)
    df_today["date"] = pd.to_datetime(df_today["date"]).dt.date

    if ONLY_TODAY:
        today = date.today()
        # Veri "UTC vs TR" kayıyorsa, minimum tarihi referans almak istersen:
        # today = df_today["date"].min()
        df_today = df_today[df_today["date"] == today].copy()
        print(f"[INFO] Filtering for today={today}, matches: {len(df_today)}")

    if df_today.empty:
        print("[WARN] No matches for today after date filter. Exiting.")
        return

    # 1) 1X2 Kupon (Model-B)
    coupon_1x2 = build_supersonic_1x2_coupon(df_today)
    if coupon_1x2 is None or coupon_1x2.empty:
        print("\n[1X2] No candidates for 1X2 coupon.")
        pd.DataFrame().to_csv(COUPON_1X2_SAVE_PATH, index=False)
    else:
        coupon_1x2.to_csv(COUPON_1X2_SAVE_PATH, index=False)
        print("\n===== SUPERSONIC TODAY 1X2 COUPON =====")
        for idx, r in coupon_1x2.iterrows():
            print(
                f"{idx+1}. {r['date']} | {r['league']} | "
                f"{r['home_team']} - {r['away_team']} → "
                f"{r['bet_selection']} @ {r['bet_odds']:.2f} "
                f"(EV={r['bet_ev']:.3f}, p={r['bet_prob']:.3f})"
            )
        print("[OK] Saved 1X2 coupon →", COUPON_1X2_SAVE_PATH)

        # VIP analizler tablosuna yaz (1X2 kupon)
        db_hazirla_vip()
        for _, r in coupon_1x2.iterrows():
            tarih_raw = r.get("datetime_tr", "")
            tarih_db = (str(tarih_raw)[:16].replace("T", " ")).strip() if tarih_raw else f"{r['date']} 00:00"
            mac_adi_db = f"{r['home_team']} vs {r['away_team']}"
            oran_db = float(r["bet_odds"])
            prob = float(r["bet_prob"])
            risk_skoru = round(100 - prob * 100, 1)

            side = r["bet_selection"]
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
                "Model-B 1X2",
                "Futbol",
                mac_kodu,
            )

    # 2) OU2.5 Kupon
    coupon_ou = build_ou25_coupon(df_today)
    if coupon_ou is None or coupon_ou.empty:
        print("\n[OU2.5] No candidates for OU2.5 coupon.")
        pd.DataFrame().to_csv(COUPON_OU25_SAVE_PATH, index=False)
    else:
        coupon_ou.to_csv(COUPON_OU25_SAVE_PATH, index=False)
        print("\n===== SUPERSONIC TODAY OU2.5 COUPON =====")
        for idx, r in coupon_ou.iterrows():
            print(
                f"{idx+1}. {r['date']} | {r['league']} | "
                f"{r['home_team']} - {r['away_team']} → "
                f"{r['bet_selection']} "
                f"(p_over25={r['bet_prob']:.3f})"
            )
        print("[OK] Saved OU2.5 coupon →", COUPON_OU25_SAVE_PATH)

    # 3) Combined Supersonic Kupon
    combo = build_combined_coupon(coupon_1x2, coupon_ou, target_size=4)
    if combo is None or combo.empty:
        print("\n[COMBO] No combined coupon could be built.")
        pd.DataFrame().to_csv(COUPON_COMBO_SAVE_PATH, index=False)
    else:
        combo.to_csv(COUPON_COMBO_SAVE_PATH, index=False)
        print("\n===== SUPERSONIC COMBINED COUPON (1X2 + OU2.5) =====")
        for idx, r in combo.iterrows():
            if r["market"] == "1X2":
                print(
                    f"{idx+1}. {r['date']} | {r['league']} | "
                    f"{r['home_team']} - {r['away_team']} → "
                    f"{r['bet_selection']} @ {r['bet_odds']:.2f} "
                    f"(EV={r['bet_ev']:.3f}, p={r['bet_prob']:.3f})"
                )
            else:
                print(
                    f"{idx+1}. {r['date']} | {r['league']} | "
                    f"{r['home_team']} - {r['away_team']} → "
                    f"{r['bet_selection']} "
                    f"(p_over25={r['bet_prob']:.3f})"
                )
        print("[OK] Saved combined coupon →", COUPON_COMBO_SAVE_PATH)

        # 4) Son 4'lü – lambda dahil eksiksiz özet (Model-G ile birleştir)
        if _HAS_MODEL_G:
            df_g = _sb.build_model_g_coupon(df_today)
            if not df_g.empty and not combo.empty:
                lg = df_g[["home_team", "away_team", "lambda_total", "ml_goals", "p_over25", "p_1h_over05", "tempo"]].copy()
                lg = lg.rename(columns={"p_over25": "lambda_p_over25", "p_1h_over05": "lambda_1h_over05", "tempo": "lambda_tempo"})
                combo_full = combo.merge(lg, on=["home_team", "away_team"], how="left")
                # Puan durumu / lig sıralaması: Önce STANDINGS_API_URL varsa API'den (gerçek veri), yoksa full_features_noleak_fe.csv'den.
                combo_lookup = combo.copy()
                combo_lookup["league"] = combo_lookup["league"].map(lambda x: LEAGUE_API_TO_DATA.get(x, x))
                combo_lookup["home_team"] = combo_lookup["home_team"].map(lambda x: TEAM_API_TO_DATA.get(x, x))
                combo_lookup["away_team"] = combo_lookup["away_team"].map(lambda x: TEAM_API_TO_DATA.get(x, x))
                ligler = combo["league"].unique().tolist()
                ligler_lookup = [LEAGUE_API_TO_DATA.get(l, l) for l in ligler]
                tablolar = {}
                puan_kaynak = "full_features_noleak_fe.csv"
                df_puan = pd.DataFrame()
                if STANDINGS_API_URL:
                    tablolar = _fetch_standings_from_api(STANDINGS_API_URL)
                    if tablolar:
                        puan_kaynak = "Standings API (gerçek sıralama)"
                        df_puan = _puan_from_tablolar(tablolar, combo_lookup)
                if not tablolar:
                    if not os.path.exists(FULL_FEATURES_PATH):
                        print("\n[PUAN DURUMU] Veri dosyası yok:", FULL_FEATURES_PATH)
                        print("             STANDINGS_API_URL da set değil veya API hata verdi. Lig sıralamaları için ya API kurun ya da build_ratings → build_rolling_features pipeline çalıştırın.")
                    df_puan = _puan_durumu_ve_agresif(FULL_FEATURES_PATH, combo_lookup)
                    tablolar = _lig_tablolari_build(FULL_FEATURES_PATH, ligler_lookup)
                elif df_puan.empty:
                    df_puan = _puan_from_tablolar(tablolar, combo_lookup)
                if not df_puan.empty:
                    combo_full["_league_lookup"] = combo_full["league"].map(lambda x: LEAGUE_API_TO_DATA.get(x, x))
                    combo_full["_home_lookup"] = combo_full["home_team"].map(lambda x: TEAM_API_TO_DATA.get(x, x))
                    combo_full["_away_lookup"] = combo_full["away_team"].map(lambda x: TEAM_API_TO_DATA.get(x, x))
                    combo_full = combo_full.merge(
                        df_puan,
                        left_on=["_league_lookup", "_home_lookup", "_away_lookup"],
                        right_on=["league", "home_team", "away_team"],
                        how="left",
                        suffixes=("", "_puan"),
                    )
                    drop_cols = [c for c in combo_full.columns if c.endswith("_puan") or c in ("_league_lookup", "_home_lookup", "_away_lookup")]
                    combo_full = combo_full.drop(columns=[c for c in drop_cols if c in combo_full.columns], errors="ignore")
                else:
                    print("\n[PUAN DURUMU] Tablo/agresif verisi üretilemedi (API yok/hatalı veya CSV'de kupon ligleri yok).")
                # Sadece istenen liglerin tablolarını kullan (API tüm ligleri döndürebilir)
                tablolar = {k: v for k, v in tablolar.items() if k in ligler_lookup}
                if not tablolar and ligler:
                    print("\n[LİG SIRALAMALARI] Tablo yok. STANDINGS_API_URL ile gerçek veri veya full_features_noleak_fe.csv ile hesaplanan veri kullanılabilir.")
                if tablolar:
                    print("\n" + "=" * 80)
                    print("LİG SIRALAMALARI (Kaynak:", puan_kaynak + ")")
                    print("=" * 80)
                    for display_lig in ligler:
                        lookup_key = LEAGUE_API_TO_DATA.get(display_lig, display_lig)
                        if lookup_key not in tablolar:
                            continue
                        t = tablolar[lookup_key]
                        print(f"\n  --- {display_lig} ---")
                        print("  Sıra   Takım                    Puan  Averaj   GF   GA")
                        print("  " + "-" * 55)
                        for _, row in t.iterrows():
                            takim = str(row["takim"])[:24].ljust(24)
                            print(f"  {int(row['sira']):2d}     {takim}  {int(row['puan']):3d}    {int(row['averaj']):+4d}   {int(row['gf']):3d}   {int(row['ga']):3d}")
                    print("=" * 80)
                print("\n" + "=" * 80)
                print("SON 4'LÜ – EKSİKSİZ ÖZET (1X2 + OU2.5 + LAMBDA)")
                print("=" * 80)
                for no, (_, r) in enumerate(combo_full.iterrows(), 1):
                    lam = r.get("lambda_total")
                    lam_s = f"λ_total={lam:.2f}" if pd.notna(lam) else "λ_total=—"
                    mlg = r.get("ml_goals")
                    mlg_s = f"ML_goals={int(mlg)}" if pd.notna(mlg) else "ML_goals=—"
                    po25 = r.get("lambda_p_over25")
                    po25_s = f"p(Over2.5)={po25:.3f}" if pd.notna(po25) else "p(Over2.5)=—"
                    p1h = r.get("lambda_1h_over05")
                    p1h_s = f"1H Over0.5={p1h:.3f}" if pd.notna(p1h) else "1H Over0.5=—"
                    tempo_s = r.get("lambda_tempo") if pd.notna(r.get("lambda_tempo")) else "—"
                    odds_s = f"{r['bet_odds']:.2f}" if pd.notna(r.get("bet_odds")) else "—"
                    ev_s = f"{r['bet_ev']:.3f}" if pd.notna(r.get("bet_ev")) else "—"
                    prob_s = f"{r['bet_prob']:.3f}" if pd.notna(r.get("bet_prob")) else "—"
                    hp, ap = r.get("home_pos"), r.get("away_pos")
                    hpts, apts = r.get("home_pts"), r.get("away_pts")
                    havg, aavg = r.get("home_avg"), r.get("away_avg")
                    agresif = r.get("agresif_beklenti", "—")
                    golcu = r.get("golcu_beklenti", "—")
                    if pd.notna(hp) and hp != "—" and pd.notna(ap) and ap != "—":
                        puan_s = f"Ev {hp}. ({hpts} puan) / Dep {ap}. ({apts} puan)"
                    else:
                        puan_s = "—"
                    if pd.notna(havg) and havg != "—" and pd.notna(aavg) and aavg != "—":
                        avg_s = f"Ev averaj {havg} / Dep averaj {aavg}"
                    else:
                        avg_s = "—"
                    print(f"\n  [{no}] {r['date']} | {r['league']}")
                    print(f"      Maç: {r['home_team']} – {r['away_team']}")
                    print(f"      Piyasa: {r.get('market', '—')}  |  Tahmin: {r.get('bet_selection', '—')}  |  Oran: {odds_s}")
                    print(f"      EV: {ev_s}  |  p: {prob_s}")
                    print(f"      Puan durumu: {puan_s}  |  Agresif beklenti: {agresif}")
                    print(f"      Averaj: {avg_s}  |  Golcu (GF yüksek): {golcu}")
                    _lk = LEAGUE_API_TO_DATA.get(r["league"], r["league"])
                    n_teams = len(tablolar.get(_lk, pd.DataFrame())) if tablolar else 0
                    yorum = _puan_durumu_analiz_yorumu(r.to_dict(), n_teams)
                    print(f"      Puan durumu analizi: {yorum}")
                    print(f"      Lambda: {lam_s}  |  {mlg_s}  |  {po25_s}  |  {p1h_s}  |  [{tempo_s}]")
                print("=" * 80)


if __name__ == "__main__":
    main()
