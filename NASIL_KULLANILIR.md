# Nasıl Kullanılır?

Bu projeyi iki aşamada kullanırsın: **ilk kurulum** (bir kere) ve **her gün** (günlük bülten + VIP + kupon).

---

## Başlamadan önce

- Terminali aç.
- Proje klasörüne geç:
  ```bash
  cd /Users/yalcin/Desktop/bikuponyap_model
  ```
- Tüm komutları bu klasörde çalıştır.

---

## A) İlk kurulum (sadece bir kere)

Bu adımlar modelleri ve veri setlerini oluşturur. **Sadece ilk kez** veya veriyi/Modelleri baştan üretmek istediğinde yaparsın.

1. **Lig CSV’lerini koy**  
   `data/raw/` klasörüne lig dosyalarını koy (D1.csv, E0.csv, F1.csv, I1.csv, SP1.csv, T1.csv vb.).

2. **Scriptleri sırayla çalıştır** (her satırı kopyalayıp terminale yapıştır, Enter):
   ```bash
   python3 src/build_master_dataset.py
   python3 src/build_poisson_dataset.py
   python3 src/build_ratings.py
   python3 src/build_rolling_features.py
   python3 src/build_full_features.py
   python3 src/build_rolling_features_noleak.py
   python3 src/feature_engineering.py
   python3 src/team_ratings.py
   python3 src/model_b_calibrated_value_engine.py
   python3 src/model_g_goal_regression.py
   python3 src/model_ou25_from_odds.py
   ```
   Hepsi hatasız bitince ilk kurulum tamam demektir.

---

## B) Her gün kullanım (bülten + VIP + kupon)

Her gün **sadece şu üç komutu** sırayla çalıştırırsın. Önce kurye oranları çeker, sonra harvester CSV + bülten DB’yi doldurur, en son boot hem lambda/VIP’i hem pipeline’ı (4’lü kupon) çalıştırır.

1. **Kurye (oranları çek):**
   ```bash
   python3 src/kurye_bot.py
   ```
   - Ne yapar: İnternetten günün maç oranlarını alır, `data/raw/bugunun_maclari.txt` dosyasına yazar.

2. **Harvester (bülten + CSV):**
   ```bash
   python3 src/master_harvester.py
   ```
   - Ne yapar: Oran dosyasını işler; `data/processed/today_odds_from_api.csv` ve Flutter DB’deki **tum_bulten** tablosunu doldurur.

3. **Boot (VIP + lambda + 4’lü kupon):**
   ```bash
   python3 src/supersonic_boot.py
   ```
   - Ne yapar:  
     - Model-G ile her maç için lambda (λ), tempo, p(Over2.5) hesaplar; terminalde yazar ve **vip_analizler** tablosuna VIP maçları yazar.  
     - Bittikten sonra **otomatik** pipeline’ı çalıştırır: 1X2 + OU2.5 kuponları üretir, “SON 4’LÜ” özetini terminalde gösterir ve yine **vip_analizler**’e yazar.

**Üçünü tek satırda çalıştırmak istersen:**
```bash
python3 src/kurye_bot.py && python3 src/master_harvester.py && python3 src/supersonic_boot.py
```

---

## C) Gece (biten maçlar)

Maçlar bittikten sonra, kupon sonuçlarını DB’ye işlemek için **bir kere**:

```bash
python3 src/gece_bekcisi.py
```

- Ne yapar: API’den biten maç skorlarını alır, **vip_analizler** tablosundaki bekleyen kuponları bulur; **gercek_skor** ve **kupon_durumu** (KAZANDI ✅ / KAYBETTİ ❌) alanlarını günceller.

---

## Özet tablo

| Ne zaman?      | Ne çalıştır?                          |
|----------------|----------------------------------------|
| İlk kez / modelleri yenilemek | A) İlk kurulum (build_* + model_* scriptleri) |
| Her gün        | kurye_bot → master_harvester → supersonic_boot |
| Maçlar bittikten sonra | gece_bekcisi |

---

## Flutter uygulaması

- Veritabanı: `/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db`
- **tum_bulten:** Günlük bülten listesi (master_harvester doldurur).
- **vip_analizler:** VIP maçlar + 4’lü kupon + (gece bekçisinden sonra) skor ve kupon sonucu.

Flutter’da nasıl okuyacağın ve “en güvenilir 4 kupon”u nasıl göstereceğin için **FLUTTER_VIP_SUPERSONIC_TANITIM.md** dosyasına bak.

---

## Detay ve sorun giderme

Komutların tam listesi, hangi scriptin ne okuduğu/yazdığı ve sık görülen hatalar için **PIPELINE_TAM_KULLANIM_KILAVUZU.md** dosyasını kullan.
