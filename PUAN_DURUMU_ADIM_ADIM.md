# Puan Durumu & Lig Sıralamaları – Adım Adım Veri Hazırlığı

Lig sıralamaları ve "kime yarıyor / kim agresif" analizi **harici API veya siteden çekilmez**. Tüm veri proje içindeki `full_features_noleak_fe.csv` dosyasından hesaplanır. Bu dosyayı oluşturmak için aşağıdaki adımları **sırayla** uygulayın.

---

## Ön koşul: Ham veri

- **Dosya:** `data/processed/master_all_leagues_2021_2026.csv`
- Bu dosya maç sonuçları, takım adları, lig, tarih ve oranları içermelidir. Yoksa önce bu veriyi (kurye_bot, master_harvester vb.) ile oluşturup `data/processed/` altına koyun.

---

## Adım 1 – Rating verisi

**Script:** `src/build_ratings.py`  
**Girdi:** `data/processed/master_all_leagues_2021_2026.csv`  
**Çıktı:** `data/processed/ratings_dataset.csv`

```bash
cd /Users/yalcin/Desktop/bikuponyap_model
python src/build_ratings.py
```

Beklenen: `[OK] Rating dataset oluşturuldu:` ve `ratings_dataset.csv` oluşmalı.

---

## Adım 2 – Rolling features (rating + rolling)

**Script:** `src/build_rolling_features.py`  
**Girdi:** `data/processed/ratings_dataset.csv`  
**Çıktı:** `data/processed/ratings_with_rolling.csv`

```bash
python src/build_rolling_features.py
```

Beklenen: `[OK] Rolling features created:` ve `ratings_with_rolling.csv` oluşmalı.

---

## Adım 3 – Poisson tahminleri

**Script:** `src/build_poisson_dataset.py`  
**Girdi:** `data/processed/ratings_with_rolling.csv`  
**Çıktı:** `data/processed/poisson_predictions.csv`

```bash
python src/build_poisson_dataset.py
```

Beklenen: `poisson_predictions.csv` oluşmalı.

---

## Adım 4 – Full features (rating + poisson birleşik)

**Script:** `src/build_full_features.py`  
**Girdi:** `ratings_with_rolling.csv` + `poisson_predictions.csv`  
**Çıktı:** `data/processed/full_features.csv`

```bash
python src/build_full_features.py
```

Beklenen: `[OK] full_features kaydedildi:` ve `full_features.csv` oluşmalı.

---

## Adım 5 – No-leak rolling → puan durumu kaynağı

**Script:** `src/build_rolling_features_noleak.py`  
**Girdi:** `data/processed/full_features.csv`  
**Çıktı:** `data/processed/full_features_noleak_fe.csv`  ← **Puan durumu / lig sıralaması bu dosyadan okunur**

```bash
python src/build_rolling_features_noleak.py
```

Beklenen: `[OK] Saved → ... full_features_noleak_fe.csv` ve `full_features_noleak_fe.csv` oluşmalı.

---

## Adım 6 – Supersonic pipeline (puan durumunun yansıdığı yer)

Bu adımdan sonra `full_features_noleak_fe.csv` dolu ve güncelse, pipeline çalıştığında:

- **LİG SIRALAMALARI** bölümünde kuponundaki liglerin puan tabloları,
- Her maç için **Puan durumu analizi** (kime yarıyor / kim agresif) satırı

görünür.

```bash
python src/model_supersonic_today_pipeline.py
```

(veya önce `python src/supersonic_boot.py` ile boot + pipeline birlikte çalıştırıyorsanız aynı çıktıyı orada da görürsünüz.)

---

## Tek seferde tüm veri adımları (1–5)

Proje kökünden:

```bash
cd /Users/yalcin/Desktop/bikuponyap_model
python src/build_ratings.py && \
python src/build_rolling_features.py && \
python src/build_poisson_dataset.py && \
python src/build_full_features.py && \
python src/build_rolling_features_noleak.py
```

Hata alırsanız ilk kırmızı mesajı okuyun; genelde bir önceki adımın çıktısı eksik veya kolon uyumsuzluğudur.

---

## Özet zincir

```
master_all_leagues_2021_2026.csv
    → build_ratings.py           → ratings_dataset.csv
    → build_rolling_features.py  → ratings_with_rolling.csv
    → build_poisson_dataset.py  → poisson_predictions.csv
    → build_full_features.py    → full_features.csv
    → build_rolling_features_noleak.py  → full_features_noleak_fe.csv
                                                                  ↑
                                    Puan durumu / lig sıralaması buradan okunur
```

Bu dosya güncel ve kuponundaki ligler bu veride varsa, **LİG SIRALAMALARI** ve **Puan durumu analizi** yansır; API veya site kullanılmaz.
