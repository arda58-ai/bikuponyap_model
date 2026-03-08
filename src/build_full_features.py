import os
import pandas as pd

# ==== PATH AYARLARI ====
BASE = os.path.dirname(os.path.dirname(__file__))

RATINGS_PATH = os.path.join(
    BASE, "data", "processed", "ratings_with_rolling.csv"
)
POISSON_PATH = os.path.join(
    BASE, "data", "processed", "poisson_predictions.csv"
)
OUTPUT_PATH = os.path.join(
    BASE, "data", "processed", "full_features.csv"
)

print("[*] Yükleniyor:")
print("   -", RATINGS_PATH)
print("   -", POISSON_PATH)

# ==== VERİLERİ YÜKLE ====
ratings = pd.read_csv(RATINGS_PATH, parse_dates=["date"])
poisson = pd.read_csv(POISSON_PATH)

print(f"[OK] ratings_with_rolling shape: {ratings.shape}")
print(f"[OK] poisson_predictions shape: {poisson.shape}")

# Satır sayısı tutuyor mu, kontrol et
if len(ratings) != len(poisson):
    raise ValueError(
        f"Row mismatch: ratings={len(ratings)}, poisson={len(poisson)}"
    )

# ==== CONCAT: YAN YANA EKLE ====
full = pd.concat([ratings, poisson], axis=1)

print(f"[OK] Full features shape: {full.shape}")

# Kolonları hafif düzenle (önemli kolonlar öne)
front_cols = [
    "date", "league", "season",
    "home_team", "away_team",
    "home_goals", "away_goals", "result",
    "B365H", "B365D", "B365A",
    "PSH", "PSD", "PSA",
]

# full'da gerçekten var olanları al
front_cols = [c for c in front_cols if c in full.columns]

# Geri kalan kolonları ekle
other_cols = [c for c in full.columns if c not in front_cols]
full = full[front_cols + other_cols]

# ==== KAYDET ====
full.to_csv(OUTPUT_PATH, index=False)
print("[OK] full_features kaydedildi:", OUTPUT_PATH)

# Hızlı sanity check
print("\n=== FIRST 3 ROWS (ÖZET) ===")
print(
    full[
        [
            "date", "league", "season",
            "home_team", "away_team",
            "home_goals", "away_goals", "result"
        ] +
        ["lambda_home", "lambda_away", "p_home", "p_draw", "p_away"]
    ].head(3)
)
