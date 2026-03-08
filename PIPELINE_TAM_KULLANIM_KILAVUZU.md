# Bikuponyap Model – Tam Kullanım Kılavuzu

Bu doküman, projedeki **tüm scriptlerin sırası**, **okudukları/yazdıkları dosyalar** ve **veri akışı**nı eksiksiz özetler. Hiçbir koda dokunmadan sadece çalıştırma sırası ve bağımlılıklar burada.

---

## 1. Proje yapısı

```
bikuponyap_model/
├── data/
│   ├── raw/                    # Ham veriler (API çıktısı, lig CSV’leri)
│   │   ├── bugunun_maclari.txt           ← kurye_bot yazar
│   │   ├── D1.csv, E0.csv, F1.csv, ...   ← lig CSV’leri (build_master_dataset okur)
│   │   └── Yeni Metin Belgesi (2).txt    ← opsiyonel; parse_odds_json_to_csv okur
│   └── processed/              # İşlenmiş veriler, modeller, kuponlar
│       ├── master_all_leagues_2021_2026.csv
│       ├── poisson_predictions.csv
│       ├── ratings_dataset.csv
│       ├── ratings_with_rolling.csv
│       ├── full_features.csv
│       ├── full_features_noleak_fe.csv
│       ├── today_odds_from_api.csv
│       ├── goal_model_lgbm.txt / goal_model_meta.json
│       ├── lgbm_model_calibrated.txt / platt_params.json / model_b_feature_cols.json
│       ├── ou25_model_from_odds.txt / platt_ou25_from_odds.json / ou25_features_from_odds.json
│       ├── today_coupon_supersonic*.csv
│       └── ...
└── src/                        # Tüm Python scriptleri
```

**Flutter DB (scriptlerden değiştirilmez):**  
`/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db`  
- Tablolar: `tum_bulten`, `vip_analizler` (opsiyonel: `gercek_skor`, `kupon_durumu`)

---

## 2. İlk kurulum / tek seferlik veri ve model hazırlığı

Bu sıra **bir kere** çalıştırılır: ham lig verileri ve eğitim scriptleriyle modeller + feature setleri üretilir.

| Sıra | Script | Okur | Yazar | Komut |
|------|--------|------|-------|--------|
| 1 | **build_master_dataset.py** | `data/raw/*.csv` (D1, E0, F1, I1, SP1, T1 vb.) | `data/processed/master_all_leagues_2021_2026.csv` | `python3 src/build_master_dataset.py` |
| 2 | **build_poisson_dataset.py** | master CSV | `data/processed/poisson_predictions.csv` | `python3 src/build_poisson_dataset.py` |
| 3 | **build_ratings.py** | master CSV | `data/processed/ratings_dataset.csv` | `python3 src/build_ratings.py` |
| 4 | **build_rolling_features.py** | ratings_dataset | `data/processed/ratings_with_rolling.csv` | `python3 src/build_rolling_features.py` |
| 5 | **build_full_features.py** | ratings_with_rolling + poisson_predictions | `data/processed/full_features.csv` | `python3 src/build_full_features.py` |
| 6 | **build_rolling_features_noleak.py** | full_features.csv | `data/processed/full_features_noleak_fe.csv` | `python3 src/build_rolling_features_noleak.py` |
| 7 | **feature_engineering.py** | (projeye özel) | (projeye özel) | `python3 src/feature_engineering.py` |
| 8 | **team_ratings.py** | (projeye özel) | (projeye özel) | `python3 src/team_ratings.py` |
| 9 | **model_b_calibrated_value_engine.py** | full_features_noleak_fe.csv | lgbm_model_calibrated.txt, platt_params.json, model_b_feature_cols.json, walk_season_calibrated_value_engine.csv | `python3 src/model_b_calibrated_value_engine.py` |
| 10 | **model_g_goal_regression.py** | full_features_noleak_fe.csv | goal_model_lgbm.txt, goal_model_meta.json, goal_regression_backtest.csv | `python3 src/model_g_goal_regression.py` |
| 11 | **model_ou25_from_odds.py** | full_features_noleak_fe.csv | ou25_model_from_odds.txt, platt_ou25_from_odds.json, ou25_features_from_odds.json, ou25_odds_only_backtest.csv | `python3 src/model_ou25_from_odds.py` |

Bunlardan sonra `data/processed` içinde günlük canlı akış için gerekli tüm model ve feature dosyaları hazır olur.

---

## 3. Günlük canlı akış (her gün / bülten + VIP + kupon)

Her gün **sırayla** aşağıdaki scriptler çalıştırılır. Önce bülten verisi alınır, sonra VIP ve kuponlar üretilir.

| Sıra | Script | Okur | Yazar / Günceller | Komut |
|------|--------|------|-------------------|--------|
| 1 | **kurye_bot.py** | (API) | `data/raw/bugunun_maclari.txt` | `python3 src/kurye_bot.py` |
| 2 | **master_harvester.py** | data/raw/bugunun_maclari.txt | data/processed/today_odds_from_api.csv + DB `tum_bulten` | `python3 src/master_harvester.py` |
| 3 | **supersonic_boot.py** | today_odds_from_api.csv, full_features_noleak_fe.csv, goal_model_*.txt/json | Terminalde λ/VIP çıktısı + DB `vip_analizler`; **bitince otomatik pipeline çalışır** | `python3 src/supersonic_boot.py` |
| 4 | **model_supersonic_today_pipeline.py** | (boot tarafından otomatik çağrılır veya elle) today_odds_from_api + Model-B/OU25 artefaktları | today_coupon_supersonic_1x2/ou25/combo.csv + DB `vip_analizler` + terminalde “SON 4’LÜ” özeti | Boot sonrası otomatik; veya `python3 src/model_supersonic_today_pipeline.py` |
| 5 | **gece_bekcisi.py** | (API scores) + DB `vip_analizler` (bekleyen kuponlar) | DB `vip_analizler`: gercek_skor, kupon_durumu | `python3 src/gece_bekcisi.py` |

**Özet komut (günlük, tek seferde):**
```bash
cd /Users/yalcin/Desktop/bikuponyap_model
python3 src/kurye_bot.py
python3 src/master_harvester.py
python3 src/supersonic_boot.py
# pipeline boot içinden otomatik çalışır
# Gece: python3 src/gece_bekcisi.py
```

---

## 4. Veritabanı tabloları (Flutter ile paylaşılan)

- **tum_bulten:** master_harvester’ın yazdığı günlük bülten (tarih, mac_adi, risk_skoru, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu).
- **vip_analizler:** supersonic_boot + model_supersonic_today_pipeline (ve istenirse model_d_today_predict) tarafından doldurulur. Kolonlar: id, tarih, mac_adi, risk_skoru, karar, oran, tahmin_tipi, kaynak, spor, mac_kodu. Gece bekçisinden sonra: gercek_skor, kupon_durumu (KAZANDI ✅ / KAYBETTİ ❌ / BEKLİYOR ⏳).

Flutter tarafı için ayrıntılı tablo şeması ve “en güvenilir 4 kupon” sorgusu: **FLUTTER_VIP_SUPERSONIC_TANITIM.md** dosyasına bakın.

---

## 5. Opsiyonel / alternatif scriptler

- **parse_odds_json_to_csv.py:** Ham JSON’u (örn. `data/raw/Yeni Metin Belgesi (2).txt`) `today_odds_from_api.csv` formatına çevirir; API yerine manuel dosyadan günlük veri üretmek için.
- **model_d_today_predict.py:** Sadece Model-B ile 4’lü Supersonic kupon üretir; CSV + `vip_analizler`. Pipeline kullanıyorsan ayrıca çalıştırmana gerek yok.
- **diagnostic_full.py**, **debug_model_a_calibration.py**, **model_c_daily_coupon_backtest.py**, **value_test_*.py** vb.: Analiz ve backtest; günlük akışı etkilemez.

---

## 6. Kontrol listesi (eksiksiz hareket için)

**İlk kurulumda:**
- [ ] `data/raw` içinde lig CSV’leri var (D1, E0, F1, I1, SP1, T1 vb.).
- [ ] 2. bölümdeki 1–11 arası scriptler sırayla çalıştırıldı.
- [ ] `data/processed` içinde full_features_noleak_fe.csv, goal_model_*.txt/json, lgbm_model_calibrated.txt, platt_*.json, ou25_* dosyaları var.

**Her gün:**
- [ ] kurye_bot → master_harvester → supersonic_boot (pipeline otomatik).
- [ ] İstenirse gece bekçisi çalıştırıldı.
- [ ] Flutter DB yolu değişmediyse aynı: `/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db`.

Bu kılavuza uyarak tüm kod, veri ve akış sırası eksiksiz ilerler; scriptlerin içeriği değiştirilmez.

---

## 7. Hızlı komutlar (kopyala-yapıştır)

**Proje köküne geç:**
```bash
cd /Users/yalcin/Desktop/bikuponyap_model
```

**Günlük akış (üç komut):**
```bash
python3 src/kurye_bot.py && python3 src/master_harvester.py && python3 src/supersonic_boot.py
```

**Sadece lambda/VIP + pipeline (today_odds_from_api.csv zaten varsa):**
```bash
python3 src/supersonic_boot.py
```

**Biten maçları DB’ye işle (gece):**
```bash
python3 src/gece_bekcisi.py
```

**İlk kurulum – modelleri yeniden üret (sırayla):**
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

---

## 8. Lambda (λ) ve tempo ne anlama geliyor?

- **λ_total (lambda_total):** Model-G’nin maç başına tahmin ettiği **toplam gol beklentisi**. Yüksek = daha golcül maç.
- **ML_goals:** λ’nın tam sayıya yuvarlanmış hali (ör. λ=2.8 → 2).
- **p(Over2.5):** Poisson formülüyle hesaplanan “toplam gol 2.5’ten fazla” olasılığı. VIP filtrede genelde ≥ 0.60 kullanılır.
- **1H Over0.5:** İlk yarıda en az 1 gol olasılığı (λ’nın ~%45’i 1. yarı varsayımıyla).
- **Tempo etiketleri:**
  - **Very high tempo:** λ ≥ 3.20  
  - **High tempo:** λ ≥ 2.90  
  - **Medium-high tempo:** λ ≥ 2.60  
  - **Standard tempo:** λ < 2.60  

Terminalde `supersonic_boot` veya pipeline’daki “SON 4’LÜ” çıktısında bu değerler aynı anlama gelir.

---

## 9. Sık karşılaşılan durumlar

| Durum | Olası sebep | Ne yapılır |
|-------|--------------|------------|
| Boot/pipeline çalışmıyor, “today_odds_from_api.csv bulunamadı” | Kurye veya harvester çalışmamış | Önce `kurye_bot.py`, sonra `master_harvester.py` çalıştır. |
| Hiç λ / VIP satırı yok | Model-G dosyaları yok veya p_over25 < 0.60 | `model_g_goal_regression.py` çalıştır; `data/processed` içinde goal_model_lgbm.txt ve goal_model_meta.json olduğundan emin ol. |
| “index out of bounds” (lambda) | Satır sırası uyumsuzluğu | Scriptlerdeki son hali kullan; kılavuzda belirtilen sırayla çalıştır. |
| Flutter’da veri görünmüyor | DB yolu veya tablo adı farklı | DB: `/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db`. Tablolar: `tum_bulten`, `vip_analizler`. FLUTTER_VIP_SUPERSONIC_TANITIM.md’ye bak. |
| Gece bekçisi kupon güncellemiyor | API’den skor gelmemiş veya maç adı eşleşmemiş | Bekleyen kuponların `mac_adi` formatı “Ev vs Deplasman” olmalı; API aynı formatta dönüyor mu kontrol et. |
| Pipeline “No matches for today” | ONLY_TODAY=True ve bugün için maç yok | today_odds_from_api.csv’deki tarih sütununu kontrol et; gerekirse pipeline’daki ONLY_TODAY veya tarih filtresini incele (kod değişikliği senin kararın). |

---

## 10. Doküman özeti

| Dosya | İçerik |
|-------|--------|
| **PIPELINE_TAM_KULLANIM_KILAVUZU.md** (bu dosya) | Sıra, komutlar, veri akışı, lambda/tempo, sık durumlar. |
| **FLUTTER_VIP_SUPERSONIC_TANITIM.md** | Flutter tarafı: DB şeması, vip_analizler, en güvenilir 4 kupon sorgusu. |

İkisini birlikte kullanarak hem model tarafını hem Flutter entegrasyonunu eksiksiz yönetebilirsin.
