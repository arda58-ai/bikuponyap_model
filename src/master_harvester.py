import json
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_JSON = os.path.join(BASE_DIR, "data", "raw", "bugunun_maclari.txt")
OUTPUT_CSV = os.path.join(BASE_DIR, "data", "processed", "today_odds_from_api.csv")
DB_PATH = "/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db"

def db_hazirla():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tum_bulten (id INTEGER PRIMARY KEY AUTOINCREMENT, tarih TEXT, mac_adi TEXT, risk_skoru REAL, karar TEXT, oran REAL, tahmin_tipi TEXT, kaynak TEXT, spor TEXT, mac_kodu TEXT)''')
    c.execute("DELETE FROM tum_bulten") 
    conn.commit()
    conn.close()

def db_kaydet(tarih, mac_adi, skor, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO tum_bulten (tarih, mac_adi, risk_skoru, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (tarih, mac_adi, skor, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu))
    conn.commit()
    conn.close()

def main():
    if not os.path.exists(INPUT_JSON): 
        return
        
    with open(INPUT_JSON, "r", encoding="utf-8") as f: 
        data = json.loads(f.read().strip())
        
    matches = data.get("data", data)
    if isinstance(matches, dict): matches = [matches]
    
    os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)
    db_hazirla()
    
    csv_rows = []
    tz_ist = ZoneInfo("Europe/Istanbul")
    
    for m in matches:
        home = m.get("home_team")
        away = m.get("away_team")
        try:
            dt_tr = datetime.fromisoformat(m.get("commence_time").replace("Z", "+00:00")).astimezone(tz_ist)
        except: 
            continue
        
        bkmks = m.get("bookmakers", [])
        B365H = B365D = B365A = B365O25 = B365U25 = None
        
        for b in bkmks:
            for mk in b.get("markets", []):
                if mk.get("key") == "h2h":
                    for o in mk.get("outcomes", []):
                        if o.get("name") == home: B365H = o.get("price")
                        elif o.get("name") == away: B365A = o.get("price")
                        else: B365D = o.get("price")
                elif mk.get("key") == "totals":
                    for o in mk.get("outcomes", []):
                        if str(o.get("point")) == "2.5" or o.get("point") == 2.5:
                            if o.get("name") == "Over": B365O25 = o.get("price")
                            elif o.get("name") == "Under": B365U25 = o.get("price")
                            
        if B365H is None or B365A is None: 
            continue
        
        tarih_temiz = dt_tr.isoformat()[:16].replace("T", " ")
        mac_kodu = str(abs(hash(home + away)) % 100000)
        risk = round(100 - (((1/float(B365H)) / ((1/float(B365H)) + (1/float(B365A)))) * 100), 1)
        
        db_kaydet(tarih_temiz, f"{home} vs {away}", risk, "İncele", B365H, "1X2", "API", "Futbol", mac_kodu)
        
        csv_rows.append({
            "date": dt_tr.date().isoformat(),
            "datetime_tr": dt_tr.isoformat(),
            "league": m.get("sport_title", ""),
            "home_team": home,
            "away_team": away,
            "B365H": B365H, "B365D": B365D, "B365A": B365A,
            "B365O25": B365O25, "B365U25": B365U25
        })

    pd.DataFrame(csv_rows).to_csv(OUTPUT_CSV, index=False)
    print("[OK] master_harvester tamamlandı.")

if __name__ == "__main__": 
    main()