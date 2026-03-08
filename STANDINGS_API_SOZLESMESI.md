# Puan Durumu / Lig Sıralaması API sözleşmesi

Pipeline, **gerçek** lig sıralaması ve averaj için isteğe bağlı olarak harici bir API kullanabilir. API yoksa veya hata dönerse mevcut davranış (full_features_noleak_fe.csv’den hesaplama) kullanılır.

---

## Ortam değişkeni

```bash
export STANDINGS_API_URL="https://your-api.com/standings"
```

Bu tanımlı değilse veya boşsa API çağrılmaz, CSV kaynağı kullanılır.

---

## İstek

- **Metot:** `GET`
- **URL:** `STANDINGS_API_URL` (sorgu parametresi yok)
- **Header:** İhtiyaca göre `Accept: application/json`

---

## Beklenen yanıt (JSON)

Tek bir JSON objesi. Anahtarlar **lig kodu** (pipeline’daki kodlar), değerler o ligin **takım listesi**.

**Lig kodları:** `E0` (İngiltere), `D1` (Almanya), `F1` (Fransa), `I1` (İtalya), `SP1` (İspanya), `T1` (Türkiye). Döndürmek istediğiniz ligleri bu kodlarla verin.

**Örnek:**

```json
{
  "F1": [
    {
      "team": "Paris SG",
      "position": 1,
      "points": 65,
      "goals_for": 72,
      "goals_against": 28,
      "goal_difference": 44
    },
    {
      "team": "Monaco",
      "position": 2,
      "points": 58,
      "goals_for": 62,
      "goals_against": 35,
      "goal_difference": 27
    }
  ],
  "SP1": [
    {
      "team": "Real Madrid",
      "position": 1,
      "points": 72,
      "goals_for": 78,
      "goals_against": 22,
      "goal_difference": 56
    }
  ],
  "T1": [
    {
      "team": "Fenerbahce",
      "position": 1,
      "points": 68,
      "goals_for": 70,
      "goals_against": 25,
      "goal_difference": 45
    }
  ]
}
```

### Alanlar (her takım objesi)

| Alan | Zorunlu | Açıklama |
|------|---------|----------|
| `team` | Evet | Takım adı. Kupon/odds ile eşleşmek için aynı isimler kullanılmalı (örn. "Rayo Vallecano", "RC Lens"). |
| `position` | Evet | Sıra (1, 2, 3, …). |
| `points` | Evet | Puan. |
| `goals_for` | Evet | Atılan gol (GF). |
| `goals_against` | Evet | Yenen gol (GA). |
| `goal_difference` | Hayır | Averaj (GF − GA). Yoksa pipeline `goals_for - goals_against` ile hesaplar. |

---

## Takım adı eşleşmesi

Pipeline’da `TEAM_API_TO_DATA` ile bazı kupon adları veri adına çevriliyor (örn. "Rayo Vallecano" → "Vallecano", "RC Lens" → "Lens").  
API’den dönen `team` değerleri:

- Ya kuponla **bire bir** aynı olmalı (Rayo Vallecano, RC Lens),  
- Ya da veri tarafındaki kısa adlar (Vallecano, Lens) dönmeli ve pipeline’daki eşleme aynen kullanılır.

Öneri: API’de takım isimlerini kupon/odds ile aynı tutmak (Rayo Vallecano, RC Lens, Nice, Rennes, …).

---

## Hata / yok sayma

- API cevap vermezse, 4xx/5xx dönerse veya JSON parse edilmezse pipeline hata vermez; sadece CSV kaynağına döner.
- Eksik lig (örn. kupon’da F1 var ama yanıtta `F1` yok) o lig için yine CSV’den hesaplanır (veya tablo boş kalır).

Bu sözleşme, sizin kuracağınız “puan durumu / sıralama API” için tek taraflı beklentiyi tanımlar; kod tarafında sadece bu formata uyum beklenir.
