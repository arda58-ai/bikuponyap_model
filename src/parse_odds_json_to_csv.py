import json
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo  # Python 3.9+
import os

# ==============================
# CONFIG
# ==============================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")

# JSON dosyanın yolu (senin attığın dosya)
INPUT_JSON = os.path.join(RAW_DIR, "Yeni Metin Belgesi (2).txt")
OUTPUT_CSV = os.path.join(PROC_DIR, "today_odds_from_api.csv")

TARGET_BOOKMAKER = "bet365"     # varsa bunu kullan, yoksa ilkini seç
TARGET_MARKET_KEY = "h2h"       # maç sonucu 1-X-2


def pick_bookmaker(markets_list, target_name):
    """
    bookmakers listesinden önce target_name'i (bet365),
    yoksa listenin ilkini döndür.
    """
    if not markets_list:
        return None

    # Önce isme göre ara
    for b in markets_list:
        if b.get("key") == target_name or b.get("title", "").lower().startswith(target_name):
            return b

    # Yoksa ilk bookmaker
    return markets_list[0]


def pick_market(bookmaker, market_key="h2h"):
    """
    Bookmaker içinden 'h2h' marketini bul.
    """
    for m in bookmaker.get("markets", []):
        if m.get("key") == market_key:
            return m
    return None


def extract_h2h_prices(m, home_team, away_team):
    """
    h2h marketinden Home / Draw / Away oranlarını çek.
    Odds API'de outcomes genelde:
      name: home_team / away_team / 'Draw'
    şeklinde gidiyor.
    """
    B365H = B365D = B365A = None

    for o in m.get("outcomes", []):
        name = o.get("name")
        price = o.get("price")

        if name == home_team:
            B365H = price
        elif name == away_team:
            B365A = price
        else:
            # Kalan genelde 'Draw'
            B365D = price

    return B365H, B365D, B365A


def main():
    print("[*] Loading JSON:", INPUT_JSON)
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    # Bazı editörler gereksiz BOM / whitespace koyabiliyor
    data = json.loads(raw)

    matches = data.get("data", [])
    print(f"[OK] Toplam maç sayısı (JSON): {len(matches)}")

    rows = []

    tz_istanbul = ZoneInfo("Europe/Istanbul")

    for m in matches:
        home = m.get("home_team")
        away = m.get("away_team")
        sport_title = m.get("sport_title")  # örn: "Soccer - Turkey Super Lig"
        commence_time = m.get("commence_time")  # ISO string, UTC

        # Tarihi datetime + Istanbul saatine çevir
        # Örn: "2025-12-06T15:00:00Z"
        dt_utc = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
        dt_tr = dt_utc.astimezone(tz_istanbul)

        bookmakers = m.get("bookmakers", [])
        if not bookmakers:
            # hiçbir oran yok -> atla
            continue

        b = pick_bookmaker(bookmakers, TARGET_BOOKMAKER)
        if b is None:
            continue

        market_h2h = pick_market(b, TARGET_MARKET_KEY)
        if market_h2h is None:
            continue

        B365H, B365D, B365A = extract_h2h_prices(market_h2h, home, away)

        # Herhangi biri yoksa o maçı şimdilik atlıyoruz
        if B365H is None or B365D is None or B365A is None:
            continue

        rows.append({
            "date": dt_tr.date().isoformat(),   # "2025-12-06"
            "datetime_tr": dt_tr.isoformat(),   # "2025-12-06T18:00:00+03:00"
            "league": sport_title,
            "home_team": home,
            "away_team": away,
            "B365H": B365H,
            "B365D": B365D,
            "B365A": B365A,
            "bookmaker_key": b.get("key"),
            "bookmaker_title": b.get("title"),
        })

    df = pd.DataFrame(rows)
    print("[OK] DataFrame shape:", df.shape)
    print(df.head())

    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)
    print("[OK] Saved →", OUTPUT_CSV)


if __name__ == "__main__":
    main()
