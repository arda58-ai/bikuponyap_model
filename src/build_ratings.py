import pandas as pd
import os
from team_ratings import TeamRatingEngine

BASE = os.path.dirname(os.path.dirname(__file__))
MASTER = os.path.join(BASE, "data", "processed", "master_all_leagues_2021_2026.csv")
OUTPUT = os.path.join(BASE, "data", "processed", "ratings_dataset.csv")

df = pd.read_csv(MASTER, parse_dates=["Date"])

# Oran kolonlarını belirle
odds_columns = [
    "B365H","B365D","B365A",
    "BbAvH","BbAvD","BbAvA",
    "PSH","PSD","PSA"
]

# Dataset'te gerçekten var olan oran kolonlarını seç
odds_columns = [c for c in odds_columns if c in df.columns]

df = df.sort_values("Date")

# Rating üret
engine = TeamRatingEngine(df)
ratings_df = engine.build()

# Merge için gerekli kolonları kontrol et
merge_columns = ["Date", "HomeTeam", "AwayTeam"] + odds_columns

merge_source = df[merge_columns].copy()

# RENAME for merge clarity
merge_source = merge_source.rename(columns={
    "Date": "orig_Date",
    "HomeTeam": "orig_HomeTeam",
    "AwayTeam": "orig_AwayTeam"
})

# MERGE
ratings_df = ratings_df.merge(
    merge_source,
    left_on=["date", "home_team", "away_team"],
    right_on=["orig_Date", "orig_HomeTeam", "orig_AwayTeam"],
    how="left"
)

# Temizlik
ratings_df = ratings_df.drop(columns=["orig_Date", "orig_HomeTeam", "orig_AwayTeam"])

# Kaydet
ratings_df.to_csv(OUTPUT, index=False)

print("[OK] Rating dataset oluşturuldu:", ratings_df.shape)
print(OUTPUT)
