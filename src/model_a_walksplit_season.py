import pandas as pd
import lightgbm as lgb
import os

# =======================
# PATHS
# =======================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
PATH = os.path.join(PROC_DIR, "full_features.csv")
SAVE_DIR = PROC_DIR

print("[*] Loading full_features.csv …")
df = pd.read_csv(PATH)
print("[OK] Loaded full:", df.shape)

# =======================
# SEASON SPLIT
# =======================
train_seasons = ["2021-2022", "2022-2023"]
test_seasons  = ["2023-2024"]

df_train_raw = df[df["season"].isin(train_seasons)].copy()
df_test_raw  = df[df["season"].isin(test_seasons)].copy()

print("RAW train:", df_train_raw.shape)
print("RAW test :", df_test_raw.shape)

# =======================
# TARGET FIX (MULTICLASS)
# =======================
def map_label(x):
    if x == -1:
        return 0
    elif x == 0:
        return 1
    elif x == 1:
        return 2

y_train = df_train_raw["result"].apply(map_label)
y_test  = df_test_raw["result"].apply(map_label)

# =======================
# DROP NON-NUMERIC FIX
# =======================
drop_cols = [
    "date",
    "league",
    "season",
    "home_team",
    "away_team",
    "home_league",
    "home_season",
    "team_x",
    "away_league",
    "away_season",
    "team_y",
    "result"
]

X_train = df_train_raw.drop(columns=drop_cols, errors="ignore")
X_test  = df_test_raw.drop(columns=drop_cols, errors="ignore")

# AUTO DROP ANY NON-NUMERIC
bad_cols = list(set(
    X_train.select_dtypes(include=["object"]).columns.tolist()
  + X_test.select_dtypes(include=["object"]).columns.tolist()
))

if bad_cols:
    print("[AUTO DROP] Non-numeric columns found:", bad_cols)
    X_train = X_train.drop(columns=bad_cols)
    X_test = X_test.drop(columns=bad_cols)

print(f"[INFO] Final features → Train: {X_train.shape} | Test: {X_test.shape}")

# =======================
# LIGHTGBM MODEL
# =======================
params = {
    "objective": "multiclass",
    "num_class": 3,
    "learning_rate": 0.05,
    "metric": "multi_logloss",
    "verbosity": -1
}

train_set = lgb.Dataset(X_train, label=y_train)

print("[*] Training LightGBM…")
model = lgb.train(params, train_set, num_boost_round=400)
print("[OK] Model trained.")

# =======================
# PREDICT
# =======================
pred = model.predict(X_test)
pred_cls = pred.argmax(axis=1)

acc = (pred_cls == y_test.values).mean()
print("===== FINAL ACCURACY =====")
print(acc)

# =======================
# SAVE OUTPUT
# =======================
df_out = df_test_raw.copy()
df_out["pred"] = pred_cls

out_path = os.path.join(SAVE_DIR, "walk_season_preds.csv")
df_out.to_csv(out_path, index=False)

print("[OK] Saved predictions →", out_path)
