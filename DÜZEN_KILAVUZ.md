# Proje düzen kılavuzu

Kod değişikliği yapılmadan tüm adımların ve eşlemelerin tek yerde toplandığı özet.

---

## 1. Genel sıra

| Sıra | Ne yapılıyor | Ne zaman |
|------|----------------|---------|
| A | Veri hazırlık pipeline (1–5) | İlk kurulum veya veriyi yenilediğinizde |
| B | Bugünkü oranlar | `today_odds_from_api.csv` dolu olmalı (API/kurye) |
| C | Supersonic pipeline veya boot | Günlük tahmin + kupon + puan durumu çıktısı |

---

## 2. Veri hazırlık pipeline (A – sırayla)

Tüm komutlar proje kökünden: `cd /Users/yalcin/Desktop/bikuponyap_model`

| Adım | Script | Girdi | Çıktı |
|------|--------|-------|--------|
| 1 | `python src/build_ratings.py` | `data/processed/master_all_leagues_2021_2026.csv` | `data/processed/ratings_dataset.csv` |
| 2 | `python src/build_rolling_features.py` | `ratings_dataset.csv` | `ratings_with_rolling.csv` |
| 3 | `python src/build_poisson_dataset.py` | `ratings_with_rolling.csv` | `poisson_predictions.csv` |
| 4 | `python src/build_full_features.py` | `ratings_with_rolling.csv` + `poisson_predictions.csv` | `full_features.csv` |
| 5 | `python src/build_rolling_features_noleak.py` | `full_features.csv` | `full_features_noleak_fe.csv` |

**Tek komut (1–5):**  
`./run_puan_durumu_veri_pipeline.sh`  
veya  
`bash run_puan_durumu_veri_pipeline.sh`

**Ön koşul:** `data/processed/master_all_leagues_2021_2026.csv` mevcut ve dolu olmalı.

---

## 3. Lig eşlemesi (API/kupon → veri kodu)

Puan durumu ve lig sıralaması, veri dosyasında kısa lig kodu ile tutulur. Kupon/API’deki lig adı otomatik olarak aşağıdaki kodlara çevrilir (kodda `LEAGUE_API_TO_DATA`).

| API / kupon lig adı | Veri kodu (master / full_features) |
|---------------------|-------------------------------------|
| Ligue 1 - France | F1 |
| La Liga - Spain | SP1 |
| Turkey Super League | T1 |
| Super Lig | T1 |
| Premier League - England | E0 |
| English Premier League | E0 |
| Bundesliga - Germany | D1 |
| Serie A - Italy | I1 |
| Italian Serie A | I1 |

Bu listede olmayan lig adları olduğu gibi kullanılır (eşleme yoksa veri kodunun aynı olması gerekir).

---

## 4. Günlük çalıştırma (B + C)

1. **Bugünkü oranlar:** `data/processed/today_odds_from_api.csv` güncel olmalı (harvester/API).
2. **Pipeline:**  
   - `python src/model_supersonic_today_pipeline.py`  
   veya  
   - `python src/supersonic_boot.py` (boot + pipeline birlikte)

Çıktıda: kuponlar, SON 4’LÜ, LİG SIRALAMALARI, Puan durumu analizi (agresif / golcu).

---

## 5. Önemli dosya konumları

| Dosya | Konum | Açıklama |
|-------|--------|----------|
| Master maç verisi | `data/processed/master_all_leagues_2021_2026.csv` | Veri zincirinin başlangıcı |
| Bugünkü oranlar | `data/processed/today_odds_from_api.csv` | Günlük pipeline girdisi |
| Puan durumu kaynağı | `data/processed/full_features_noleak_fe.csv` | Lig sıralaması / agresif buradan hesaplanır |
| 1X2 kupon | `data/processed/today_coupon_supersonic_1x2.csv` | |
| OU2.5 kupon | `data/processed/today_coupon_supersonic_ou25.csv` | |
| Birleşik kupon | `data/processed/today_coupon_supersonic_combo.csv` | |
| Flutter DB | `DB_PATH` (model_supersonic_today_pipeline.py içinde sabit) | vip_analizler tablosu |

---

## 6. Zincir özeti

```
master_all_leagues_2021_2026.csv
    → build_ratings.py                 → ratings_dataset.csv
    → build_rolling_features.py        → ratings_with_rolling.csv
    → build_poisson_dataset.py         → poisson_predictions.csv
    → build_full_features.py           → full_features.csv
    → build_rolling_features_noleak.py → full_features_noleak_fe.csv
                                                          ↑
                        Puan durumu / lig sıralaması buradan okunur

today_odds_from_api.csv
    → model_supersonic_today_pipeline.py (veya supersonic_boot.py)
        → kuponlar, SON 4’LÜ, LİG SIRALAMALARI, Puan durumu analizi
```

---

## 7. Gerçek puan durumu için harici API (isteğe bağlı)

Şu anki sıralama/averaj verisi `full_features_noleak_fe.csv` üzerinden hesaplanıyor; kaynak yanlış veya eksikse sonuç da yanlış olur. **Gerçek** lig sıralaması için ayrı bir API kullanılabilir.

- **Ortam değişkeni:** `STANDINGS_API_URL` (örn. `https://your-api.com/standings`)
- **Davranış:** Bu set edilmişse pipeline önce bu URL’e GET atar; gelen JSON’a göre LİG SIRALAMALARI ve puan durumu analizi **API’den** doldurulur. API yoksa veya hata verirse yine CSV kaynağı kullanılır.
- **API sözleşmesi:** `STANDINGS_API_SOZLESMESI.md` dosyasında (yanıt formatı, lig kodları, takım adları).

```bash
export STANDINGS_API_URL="https://your-standings-api.com/standings"
python3 src/model_supersonic_today_pipeline.py
```

---

Bu kılavuz mevcut kodu ve davranışı yansıtır.
