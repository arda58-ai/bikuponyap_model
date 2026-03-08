import pandas as pd
import os
from poisson_model import PoissonEngine

BASE = os.path.dirname(os.path.dirname(__file__))
INPUT = os.path.join(BASE, "data", "processed", "ratings_with_rolling.csv")
OUTPUT = os.path.join(BASE, "data", "processed", "poisson_predictions.csv")

# 1) Veri yükle
df = pd.read_csv(INPUT, parse_dates=["date"])

engine = PoissonEngine(df)

# 2) Tüm maçlar için Poisson tahmini üret
poisson_df = engine.build_all()

# 3) Tüm kolonları numerik zorla (hata varsa NaN yap)
num_cols = [
    "lambda_home",
    "lambda_away",
    "p_home",
    "p_draw",
    "p_away",
    "p_over25",
    "p_under25",
    "p_btts",
]
poisson_df[num_cols] = poisson_df[num_cols].apply(
    pd.to_numeric, errors="coerce"
)

# 4) Tamamen boş (full-NaN) satırları at
before = len(poisson_df)
poisson_df = poisson_df.dropna(how="all", subset=num_cols).reset_index(drop=True)
after = len(poisson_df)

print(f"[CLEAN] Dropped empty rows: {before - after}")

# 5) Dosyaya yaz
poisson_df.to_csv(OUTPUT, index=False)

print("[OK] Poisson predictions created:", poisson_df.shape)
print(OUTPUT)
