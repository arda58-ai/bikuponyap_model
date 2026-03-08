import pandas as pd
import os
from feature_engineering import RollingFeatureBuilder

BASE = os.path.dirname(os.path.dirname(__file__))
INPUT = os.path.join(BASE, "data", "processed", "ratings_dataset.csv")
OUTPUT = os.path.join(BASE, "data", "processed", "ratings_with_rolling.csv")

df = pd.read_csv(INPUT, parse_dates=["date"])

builder = RollingFeatureBuilder(df)
rolling_df = builder.build()

rolling_df.to_csv(OUTPUT, index=False)

print("[OK] Rolling features created:", rolling_df.shape)
print(OUTPUT)
