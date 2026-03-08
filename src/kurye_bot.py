import requests
import json
import os

# Sistemin ana klasörünü otomatik bulur (bikuponyap_model)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Veriyi doğrudan senin kurduğun data/raw/ klasörüne kaydeder
KAYIT_YERI = os.path.join(BASE_DIR, "data", "raw", "bugunun_maclari.txt")

API_KEY = "6c645065285ee854629b1c2c788491c2"

SPORTS = [
    "soccer_turkey_super_league", "soccer_spain_la_liga", "soccer_italy_serie_a",
    "soccer_france_ligue_one", "soccer_epl", "soccer_germany_bundesliga"
]

def canli_kurye():
    print("[*] Kurye Yola Çıktı: Veriler the-odds-api'den çekiliyor...")
    all_matches = []
    
    for sport in SPORTS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
        # Orijinal scriptlerinin Alt/Üst oranlarını bulabilmesi için totals eklendi
        params = {
            "apiKey": API_KEY, 
            "regions": "eu", 
            "markets": "h2h,totals", 
            "oddsFormat": "decimal"
        }
        try:
            response = requests.get(url, params=params)
            if response.status_code == 200:
                all_matches.extend(response.json())
        except Exception as e:
            print(f"[-] {sport} verisi çekilirken hata oluştu: {e}")

    # Klasör yoksa hata vermemesi için otomatik oluştur (data/raw/)
    os.makedirs(os.path.dirname(KAYIT_YERI), exist_ok=True)
    
    with open(KAYIT_YERI, "w", encoding="utf-8") as f:
        json.dump({"data": all_matches}, f, ensure_ascii=False, indent=4)

    print(f"[OK] Toplam {len(all_matches)} maç başarıyla kaydedildi!")
    print(f"[+] Dosya Yolu: {KAYIT_YERI}")

if __name__ == "__main__":
    canli_kurye()