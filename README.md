# bikuponyap_model

Futbol maçları için tahmin pipeline'ı: Model-B (1X2), OU2.5, Supersonic kupon, puan durumu / lig sıralaması analizi. Flutter uygulaması ile VIP analizler veritabanı entegrasyonu.

---

## Kurulum

```bash
git clone https://github.com/arda58-ai/bikuponyap_model.git
cd bikuponyap_model
```

**Clone sırasında kimlik sorarsa:** Kullanıcı adı = GitHub kullanıcı adın, şifre = **Personal Access Token** (GitHub → Settings → Developer settings → Personal access tokens). Normal hesap şifresi çalışmaz.

```bash
pip install pandas numpy lightgbm scikit-learn  # gerekli Python paketleri
```

---

## Veri

- **Ham veri:** `data/processed/master_all_leagues_2021_2026.csv` (maç sonuçları, lig, takım, oran). Bu dosya repoda yok; harvester veya el ile eklenir.
- **Veri pipeline:** Master CSV varsa `./run_puan_durumu_veri_pipeline.sh` ile rating → rolling → poisson → full_features → full_features_noleak_fe üretilir.
- **Bugünkü oranlar:** `data/processed/today_odds_from_api.csv` (API/harvester ile doldurulur).

Detay: `PUAN_DURUMU_ADIM_ADIM.md`, `DÜZEN_KILAVUZ.md`.

---

## Çalıştırma

```bash
# Günlük tahmin + kupon + puan durumu
python src/model_supersonic_today_pipeline.py
```

Veya önce boot, sonra pipeline: `python src/supersonic_boot.py`

---

## Dokümanlar

| Dosya | Açıklama |
|-------|----------|
| `DÜZEN_KILAVUZ.md` | Pipeline sırası, lig eşlemesi, dosya konumları |
| `PUAN_DURUMU_ADIM_ADIM.md` | Puan durumu verisi nasıl üretilir (adım adım) |
| `GITHUB_YUKLEME.md` | GitHub’a yükleme ve push |
| `STANDINGS_API_SOZLESMESI.md` | Gerçek lig sıralaması için harici API formatı |
| `NASIL_KULLANILIR.md` | Kullanım kılavuzu |
| `PIPELINE_TAM_KULLANIM_KILAVUZU.md` | Tam pipeline detayı |

---

## İki yazılımcı birlikte çalışma

- Repo sahibi: GitHub → Settings → Collaborators → ikinci kişiyi ekle.
- İkinci yazılımcı: `git clone` (yukarıdaki gibi token ile) → değişiklik yap → `git add .` → `git commit -m "..."` → `git push`.
- Güncellemeleri almak: `git pull`.

---

## Lisans

Özel proje.
