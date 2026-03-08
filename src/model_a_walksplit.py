import os
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
PATH = os.path.join(PROC_DIR, "full_features.csv")

# ===========================
# 1) DATA LOADING
# ===========================
print("[*] Loading:", PATH)
df = pd.read_csv(PATH)
print("[OK] full_features:", df.shape)

# ===========================
# 2) TARGET CHECK
# ===========================
TARGET = "result"
if TARGET not in df.columns:
    raise ValueError(f"[FATAL] Target column '{TARGET}' not found. Columns: {df.columns.tolist()}")

# ===========================
# 3) AUTO-DROP NON-NUMERIC
# ===========================
non_numeric_cols = df.select_dtypes(exclude=["number"]).columns.tolist()

print("[INFO] Dropping non-numeric columns:", non_numeric_cols)

df = df.drop(columns=non_numeric_cols)

# ===========================
# 4) FINAL SPLIT (HALF-HALF)
# ===========================
train_df, test_df = train_test_split(df, test_size=0.5, shuffle=False)

X_train = train_df.drop(columns=[TARGET])
y_train = train_df[TARGET]

X_test = test_df.drop(columns=[TARGET])
y_test = test_df[TARGET]

print("Train:", X_train.shape, "| Test:", X_test.shape)

# ===========================
# 5) LIGHTGBM SETTINGS
# ===========================
params = {
    "objective": "binary",     # result=1/0 varsayımı
    "metric": "binary_logloss",
    "learning_rate": 0.03,
    "num_leaves": 31,
    "max_depth": -1,
    "seed": 42
}

train_set = lgb.Dataset(X_train, label=y_train)

# ===========================
# 6) TRAIN MODEL
# ===========================
print("[*] Training LightGBM...")
model = lgb.train(params, train_set, num_boost_round=300)

# ===========================
# 7) PREDICT
# ===========================
pred_proba = model.predict(X_test)
preds = (pred_proba > 0.5).astype(int)

# ===========================
# 8) METRICS
# ===========================
acc = accuracy_score(y_test, preds)

print("\n=== FINAL RESULTS ===")
print("Accuracy:", round(acc, 4))
print("====================")
