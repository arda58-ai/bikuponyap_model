import pandas as pd
import numpy as np
import os

# =========================
# CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
PATH = os.path.join(PROC_DIR, "full_features.csv")


# =========================
# LOAD DATA
# =========================
print("\n================= LOAD =================")
df = pd.read_csv(PATH)
print("[OK] Loaded:", df.shape)
print("Columns:", len(df.columns))

print("\n================= BASIC INFO =================")
print("Dtypes:")
print(df.dtypes.value_counts())


# =========================
# 1) ZERO VARIANCE
# =========================
print("\n================= ZERO VARIANCE TEST =================")
zero_var = [c for c in df.columns if df[c].nunique()==1]
print("Zero variance count:", len(zero_var))
if len(zero_var):
    print(zero_var)


# =========================
# 2) MISSING VALUES
# =========================
print("\n================= MISSING VALUE TEST =================")
missing = df.isna().sum()
missing = missing[missing>0]
print("Missing columns:", len(missing))
print(missing)


# =========================
# 3) TARGET LEAK TEST
# =========================
print("\n================= TARGET LEAK TEST =================")

TARGET = "result"
leak_cols = [
    "home_result","away_result",
    "home_team_points","away_team_points",
    "lambda_home","lambda_away",
    "p_home","p_draw","p_away",
    "p_over25","p_under25","p_btts"
]

for col in leak_cols:
    if col in df.columns:
        corr = df[[TARGET, col]].corr().iloc[0,1]
        print(f"{col:25s} → corr(result) = {corr:.4f}")


# =========================
# 4) FUTURE LOOK-AHEAD TEST
# =========================
print("\n================= FUTURE LEAK CHECK (DATE ORDER) =================")

if "date" in df.columns:
    df["date"] = pd.to_datetime(df["date"])
    sorted_check = df["date"].is_monotonic_increasing
    print("Date monotonic increasing:", sorted_check)
else:
    print("No date column.")


# =========================
# 5) ROLLING FEATURES HEALTH
# =========================
print("\n================= ROLLING FEATURE HEALTH =================")

rolling_cols = [c for c in df.columns if "rolling" in c.lower()]

for col in rolling_cols:
    if df[col].isna().mean() > 0.80:
        print(f"{col:25s} → EMPTY ({df[col].isna().mean()*100:.1f}% NaN)")


# =========================
# 6) TEAM-ID LEAK TEST
# =========================
print("\n================= TEAM-ID LEAK TEST =================")

team_cols = ["home_team", "away_team", "team_x", "team_y"]
team_cols = [c for c in team_cols if c in df.columns]

for col in team_cols:
    freq = df.groupby(col)["result"].mean()
    spread = freq.max() - freq.min()
    print(f"{col:10s} → Result spread = {spread:.4f}")


# =========================
# 7) ELO & RATINGS TEST
# =========================
print("\n================= ELO & RATING CHECK =================")

elo_cols = ["home_elo","away_elo","home_att","away_att","home_def","away_def"]
elo_cols = [c for c in elo_cols if c in df.columns]

for col in elo_cols:
    print(f"{col:15s} → unique: {df[col].nunique()}")


# =========================
# 8) ODDS CHECK (PSH vs B365)
# =========================
print("\n================= ODDS CONSISTENCY CHECK =================")

odds_sets = [
    ("B365H","PSH"),
    ("B365D","PSD"),
    ("B365A","PSA")
]

for c1, c2 in odds_sets:
    if c1 in df and c2 in df:
        corr = df[[c1,c2]].corr().iloc[0,1]
        print(f"{c1}-{c2}: corr = {corr:.4f}")


# =========================
# 9) FEATURE → TARGET CORRELATION RANKING
# =========================
print("\n================= CORRELATION RANKING (ABS) =================")

num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
if TARGET in num_cols:
    num_cols.remove(TARGET)

corrs = df[num_cols].corrwith(df[TARGET]).abs().sort_values(ascending=False)
print(corrs.head(20))


# =========================
# 10) DUPLICATE ROWS
# =========================
print("\n================= DUPLICATES =================")
print("Duplicate rows:", df.duplicated().sum())


print("\n========== DIAGNOSTIC COMPLETE ==========")
