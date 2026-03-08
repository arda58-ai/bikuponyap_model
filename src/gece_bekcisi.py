import requests
import json
import sqlite3
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# GECE BEKÇİSİ & KUPON TAKİP SİSTEMİ (MAC İÇİN)
# ==========================================
API_KEY = "6c645065285ee854629b1c2c788491c2"
DB_PATH = r"/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
YENI_SKORLAR_CSV = os.path.join(PROC_DIR, "yeni_biten_maclar.csv")

SPORTS = [
    "soccer_turkey_super_league", "soccer_spain_la_liga",
    "soccer_italy_serie_a", "soccer_france_ligue_one",
    "soccer_epl", "soccer_germany_bundesliga"
]

def veritabani_kolonlarini_hazirla():
    """Kupon takibi için veritabanına Skor ve Durum kolonlarını ekler."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE vip_analizler ADD COLUMN gercek_skor TEXT")
        c.execute("ALTER TABLE vip_analizler ADD COLUMN kupon_durumu TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass # Kolonlar zaten varsa hata verir, pas geçiyoruz
    finally:
        conn.close()

def kuponu_degerlendir(tahmin, ev_skor, dep_skor):
    """Yapay zekanın tahmini ile gerçek skoru karşılaştırır."""
    if ev_skor is None or dep_skor is None: return "BEKLİYOR ⏳"
    
    ev_skor, dep_skor = int(ev_skor), int(dep_skor)
    toplam_gol = ev_skor + dep_skor
    
    if tahmin == "MS 1" and ev_skor > dep_skor: return "KAZANDI ✅"
    if tahmin == "MS 2" and dep_skor > ev_skor: return "KAZANDI ✅"
    if tahmin == "Beraberlik" and ev_skor == dep_skor: return "KAZANDI ✅"
    if tahmin == "2.5 ÜST" and toplam_gol > 2: return "KAZANDI ✅"
    if tahmin == "2.5 ALT" and toplam_gol <= 2: return "KAZANDI ✅"
    
    return "KAYBETTİ ❌"

def gece_bekcisi_calistir():
    print("\n🌙 [GECE BEKÇİSİ] Dünün Maç Skorları Sorgulanıyor...")
    veritabani_kolonlarini_hazirla()
    
    # Veritabanındaki sonuçlanmamış (skoru girilmemiş) VIP tahminleri çek (karar = MS 1 / MS 2 / Beraberlik / 2.5 ÜST vb.)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, mac_adi, tahmin_tipi, karar FROM vip_analizler WHERE kupon_durumu IS NULL OR kupon_durumu = 'BEKLİYOR ⏳'"
    )
    bekleyen_kuponlar = c.fetchall()

    if not bekleyen_kuponlar:
        print("[!] Bekleyen / Sonuçlanmamış VIP analiz bulunmuyor.")
        conn.close()
        return

    print(f"[*] {len(bekleyen_kuponlar)} adet bekleyen VIP kupon bulundu. Skorlar aranıyor...")

    # The Odds API'den son 3 günün bitmiş maçlarını çek
    bitmis_maclar = {}
    for sport in SPORTS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/scores"
        params = {"apiKey": API_KEY, "daysFrom": 3}
        try:
            resp = requests.get(url, params=params)
            if resp.status_code == 200:
                for match in resp.json():
                    if match.get("completed"):
                        home = match.get("home_team")
                        away = match.get("away_team")
                        mac_key = f"{home} vs {away}"
                        scores = match.get("scores", [])
                        if scores and len(scores) == 2:
                            h_score = next((s["score"] for s in scores if s["name"] == home), None)
                            a_score = next((s["score"] for s in scores if s["name"] == away), None)
                            bitmis_maclar[mac_key] = {"h_score": h_score, "a_score": a_score}
        except Exception as e:
            print(f"Hata: {sport} skorları çekilemedi. {e}")

    print(f"[*] API'den {len(bitmis_maclar)} bitmiş maç skoru alındı.")

    # Veritabanındaki kuponları skorlarla eşleştir ve güncelle
    guncellenen = 0
    for kupon in bekleyen_kuponlar:
        k_id, mac_adi, tahmin_tipi, karar = kupon
        # 1X2 için tahmin = karar (MS 1 / MS 2 / Beraberlik), aksi halde tahmin_tipi (2.5 ÜST / 2.5 ALT)
        tahmin = (karar if karar in ("MS 1", "MS 2", "Beraberlik") else tahmin_tipi) or tahmin_tipi

        eslesen_skor = bitmis_maclar.get(mac_adi)
        if eslesen_skor and eslesen_skor["h_score"] is not None:
            g_skor = f"{eslesen_skor['h_score']} - {eslesen_skor['a_score']}"
            durum = kuponu_degerlendir(tahmin, eslesen_skor["h_score"], eslesen_skor["a_score"])
            c.execute(
                "UPDATE vip_analizler SET gercek_skor = ?, kupon_durumu = ? WHERE id = ?",
                (g_skor, durum, k_id),
            )
            print(f" 🏆 KUPON GÜNCELLENDİ: {mac_adi} | Tahmin: {tahmin} | Skor: {g_skor} | Sonuç: {durum}")
            guncellenen += 1

    conn.commit()
    conn.close()

    print(f"\n[OK] Gece Bekçisi Görevini Tamamladı. {guncellenen} kuponun sonucu karnesine işlendi!")

if __name__ == "__main__":
    gece_bekcisi_calistir()