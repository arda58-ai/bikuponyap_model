# Flutter VIP sekmesi – Supersonic Today pipeline tanıtımı

Bu metni **Flutter projesinin açık olduğu Cursor** penceresine yapıştır. Böylece AI, VIP sekmesindeki “en güvenilir 4 kupon” bölümünü hangi veriden dolduracağını bilir.

---

## Veritabanı

- **Geliştirme (Mac):** `"/Users/yalcin/development/model_c_app/ios/model_c_arsiv.db"`
- **Tablo:** `vip_analizler`

## Tablo şeması: `vip_analizler`

| Kolon        | Tip    | Açıklama                          |
|-------------|--------|------------------------------------|
| id          | INTEGER| Primary key (otomatik)             |
| tarih       | TEXT   | Maç tarihi (örn. "2026-03-07 17:30") |
| mac_adi     | TEXT   | "Ev Sahibi vs Deplasman"           |
| risk_skoru  | REAL   | Risk skoru (düşük = güvenilir)     |
| karar       | TEXT   | "MS 1", "MS 2", "Beraberlik", "2.5 ÜST" vb. |
| oran        | REAL   | Bahis oranı                       |
| tahmin_tipi | TEXT   | "1X2", "2.5 ÜST" vb.              |
| kaynak      | TEXT   | Hangi modelin yazdığı             |
| spor        | TEXT   | "Futbol"                          |
| mac_kodu    | TEXT   | Benzersiz maç kodu                |

(İsteğe bağlı: `gercek_skor`, `kupon_durumu` – gece_bekcisi sonrası dolar.)

---

## VIP sekmesinde iki veri kaynağı

1. **Tüm VIP maçlar**  
   `vip_analizler` tablosunun **tamamı** (supersonic_boot + model_d + pipeline hepsi bu tabloya yazar).  
   Flutter: `SELECT * FROM vip_analizler ORDER BY tarih, id`

2. **En güvenilir 4 kupon (Supersonic Today)**  
   Python tarafında **model_d_today_predict.py** veya **model_supersonic_today_pipeline.py** çalıştığında, bu scriptler sadece **seçilmiş 4 (veya daha az) kupon satırını** `vip_analizler` tablosuna yazar.  
   Bu satırları Flutter tarafında ayırmak için **`kaynak`** kolonunu kullan:

   - `kaynak = 'Model-B Supersonic'` → model_d_today_predict’in yazdığı 4 kupon (1X2)
   - `kaynak = 'Model-B 1X2'`       → model_supersonic_today_pipeline’ın yazdığı 1X2 kupon satırları (genelde 2–4 adet)

   **“En güvenilir 4 kupon” bölümünü doldurmak için Flutter’da:**

   - `vip_analizler` tablosundan  
     `WHERE kaynak IN ('Model-B Supersonic', 'Model-B 1X2')`  
     `ORDER BY id ASC`  
     ile oku; en fazla **4 kayıt** al (veya hepsini al, zaten 4’ten fazla olmaz).
   - Bu liste, Supersonic Today pipeline’ının ürettiği “en güvenilir 4 kupon” listesidir.

---

## Özet

- **Tüm VIP maçlar:** `vip_analizler` tablosunun tüm satırları.
- **En güvenilir 4 kupon:** Aynı tabloda `kaynak IN ('Model-B Supersonic', 'Model-B 1X2')` ile filtrele, sırala, en fazla 4 satır göster. Bu bölümü bu sorgu ile doldur.
