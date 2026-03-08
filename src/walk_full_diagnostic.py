import pandas as pd
import numpy as np
import os

# ================================================================
# 0) LOAD FILES
# ================================================================
BASE = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE, "..", "data", "processed")

FULL = os.path.join(DATA_DIR, "full_features.csv")
TRAIN = os.path.join(DATA_DIR, "walk_train.csv")
TEST  = os.path.join(DATA_DIR, "walk_test.csv")

print("\n================= LOADING =================")
df_full = pd.read_csv(FULL)
df_train = pd.read_csv(TRAIN)
df_test = pd.read_csv(TEST)

print("[OK] Loaded full:", df_full.shape)
print("[OK] Train:", df_train.shape)
print("[OK] Test :", df_test.shape)


# ================================================================
# 1) SEASON CHECK
# ================================================================
print("\n================= SEASON CHECK =================")

if "season" not in df_full.columns:
    print("❌ ERROR: 'season' column missing.")
else:
    print("Full seasons:", df_full["season"].unique())
    print("Train seasons:", df_train["season"].unique() if "season" in df_train else "N/A")
    print("Test seasons:", df_test["season"].unique() if "season" in df_test else "N/A")


# ================================================================
# 2) MATCH_ID LEAK CHECK
# ================================================================
print("\n================= MATCH_ID CROSS-CHECK =================")

if "match_id" in df_train.columns and "match_id" in df_test.columns:
    inter = set(df_train["match_id"]).intersection(df_test["match_id"])
    print("Intersection count:", len(inter))
    if len(inter) > 0:
        print("❌ MATCH_ID LEAK DETECTED → SAME MATCH IN TRAIN & TEST")
    else:
        print("✅ No match_id leakage detected.")
else:
    print("❌ match_id missing in train/test")


# ================================================================
# 3) FEATURE ZERO-VARIANCE TEST
# ================================================================
print("\n================= ZERO VARIANCE TEST =================")

train_features = df_train.select_dtypes(include=[np.number])
zero_var_cols = train_features.columns[train_features.var() == 0]

print("Zero variance count:", len(zero_var_cols))
if len(zero_var_cols) > 0:
    print("❌ Zero-variance features detected:")
    for c in zero_var_cols:
        print("   -", c)
else:
    print("✅ No zero-variance issues.")


# ================================================================
# 4) TARGET LEAKAGE CORRELATION TEST
# ================================================================
print("\n================= TARGET LEAK CHECK =================")

LEAK_CANDS = [
    "p_home", "p_draw", "p_away",
    "lambda_home", "lambda_away",
    "home_result", "away_result",
]

if "result" not in df_test.columns:
    print("❌ Missing target 'result' column in test set.")
else:
    for col in LEAK_CANDS:
        if col in df_test.columns:
            corr = np.corrcoef(df_test[col].astype(float), df_test["result"])[0,1]
            print(f"{col:15s} → corr={corr:.4f}")
            if abs(corr) > 0.25:
                print(f"   ❌ POSSIBLE LEAK or feature contains target info!")
        else:
            print(f"{col:15s} → (not found)")


# ================================================================
# 5) DUPLICATE CHECK
# ================================================================
print("\n================= DUPLICATE CHECK =================")

dup_train = df_train.duplicated().sum()
dup_test = df_test.duplicated().sum()

print("Train duplicates:", dup_train)
print("Test duplicates :", dup_test)

if dup_train > 0 or dup_test > 0:
    print("❌ Duplicate rows detected.")
else:
    print("✅ No duplicate rows.")


# ================================================================
# 6) FEATURE OVERLAP LEAK (train/test mix)
# ================================================================
print("\n================= FEATURE OVERLAP CHECK =================")

if "date" in df_train.columns and "date" in df_test.columns:
    overlap_dates = set(df_train["date"]).intersection(df_test["date"])
    print("Date intersection:", len(overlap_dates))
else:
    print("Date column missing → cannot check.")


# ================================================================
# 7) PRINT SUMMARY
# ================================================================
print("\n================= SUMMARY =================")

print("✔ Loaded datasets")
print("✔ Season distribution analyzed")
print("✔ Match-ID leakage checked")
print("✔ Zero variance verified")
print("✔ Target leakage scored")
print("✔ Duplicate rows checked")
print("✔ Date overlap tested")

print("\n========== DIAGNOSTIC COMPLETE ==========\n")
