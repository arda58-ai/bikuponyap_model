import pandas as pd
import os
import re

# === AYARLAR ===
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # proje kök
DATA_RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
OUTPUT_CSV = os.path.join(DATA_PROCESSED_DIR, "master_all_leagues_2021_2026.csv")


def parse_season_from_name(filename: str):
    """
    Dosya adından lig ve sezon bilgisini çözer.

    Örnek:
      SP1.csv      -> league=SP1, season=2025-2026
      SP1 (1).csv  -> league=SP1, season=2024-2025
      SP1 (2).csv  -> league=SP1, season=2023-2024
      SP1 (3).csv  -> league=SP1, season=2022-2023
      SP1 (4).csv  -> league=SP1, season=2021-2022
    """
    m = re.match(r"^([A-Z0-9]+)(?: \((\d)\))?\.csv$", filename)
    if not m:
        return None, None, None

    league = m.group(1)
    idx = m.group(2)

    if idx is None:
        season = "2025-2026"; season_order = 0
    elif idx == "1":
        season = "2024-2025"; season_order = 1
    elif idx == "2":
        season = "2023-2024"; season_order = 2
    elif idx == "3":
        season = "2022-2023"; season_order = 3
    elif idx == "4":
        season = "2021-2022"; season_order = 4
    else:
        season = None; season_order = None

    return league, season, season_order


def build_master():
    all_rows = []

    for fname in sorted(os.listdir(DATA_RAW_DIR)):
        if not fname.endswith(".csv"):
            continue

        league, season, season_order = parse_season_from_name(fname)
        if league is None:
            print(f"[SKIP] Dosya adı format dışı: {fname}")
            continue

        path = os.path.join(DATA_RAW_DIR, fname)
        print(f"[+] Yükleniyor: {fname} | Lig={league} | Sezon={season}")

        df = pd.read_csv(path)

        # Minimum gerekli kolonlar
        required = ["Date", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            print(f"  [-] Atlanıyor, eksik kolonlar: {missing}")
            continue

        # Çekmek istediğimiz ekstra oran kolonları (varsa al, yoksa boş kalsın)
        odds_cols = [
            "B365H", "B365D", "B365A",   # Bet365 1X2
            "PSH", "PSD", "PSA",        # Pinnacle 1X2
            "BbAvH", "BbAvD", "BbAvA",  # Ortalama 1X2
            "BbOU", "BbMx>2.5", "BbMn>2.5", "BbMx<2.5", "BbMn<2.5"
        ]
        existing_odds = [c for c in odds_cols if c in df.columns]

        use_cols = required + existing_odds
        sub = df[use_cols].copy()

        # Lig + sezon
        sub["league"] = league
        sub["season"] = season
        sub["season_order"] = season_order

        # Tarih formatı
        try:
            sub["Date"] = pd.to_datetime(sub["Date"], format="%d/%m/%Y")
        except Exception:
            sub["Date"] = pd.to_datetime(sub["Date"], errors="coerce")

        # Skor + numeric sonuç
        sub["HomeGoals"] = sub["FTHG"]
        sub["AwayGoals"] = sub["FTAG"]
        sub["ResultNumeric"] = sub["FTR"].map({"H": 1, "D": 0, "A": -1})

        all_rows.append(sub)

    if not all_rows:
        raise RuntimeError("Hiçbir uygun csv okunamadı. Kolon isimlerini veya klasörü kontrol et.")

    master = pd.concat(all_rows, ignore_index=True).sort_values("Date").reset_index(drop=True)

    os.makedirs(DATA_PROCESSED_DIR, exist_ok=True)
    master.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")

    print("\n[OK] Birleştirilmiş tablo şekli:", master.shape)
    print("[OK] Kayıt:", OUTPUT_CSV)

    return master


if __name__ == "__main__":
    master_df = build_master()
    print(master_df.head())
