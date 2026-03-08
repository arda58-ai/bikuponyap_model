import pandas as pd
import lightgbm as lgb
import os

# ================================
# LOAD DATA
# ================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
PATH = os.path.join(PROC_DIR, "full_features.csv")
SAVE_DIR = PROC_DIR

df = pd.read_csv(PATH)
print("[OK] Loaded full:", df.shape)

# ================================
# TARGET = result (mapped)
# ================================
if "result" not in df.columns:
    raise Exception("❌ 'result' column not found in full_features.csv")

df["target"] = df["result"].map({-1: 0, 0: 1, 1: 2})

# ================================
# SEASON SPLIT
# ================================
train_seasons = ["2021-2022", "2022-2023"]
test_seasons  = ["2023-2024"]

df_train = df[df["season"].isin(train_seasons)].copy()
df_test  = df[df["season"].isin(test_seasons)].copy()

print("Train:", df_train.shape)
print("Test :", df_test.shape)

# ================================
# DROP NON-NUMERIC COLUMNS
# ================================
drop_cols = [
    "date","league","season","home_team","away_team",
    "home_league","home_season","team_x",
    "away_league","away_season","team_y",
    "result"  # raw result
]

features_train = df_train.drop(columns=drop_cols)
features_test  = df_test.drop(columns=drop_cols)

y_train = df_train["target"]
y_test  = df_test["target"]

# Remove target column from features
features_train = features_train.drop(columns=["target"])
features_test  = features_test.drop(columns=["target"])

# ================================
# MODEL
# ================================
params = {
    "objective": "multiclass",
    "num_class": 3,
    "metric": "multi_logloss",
    "learning_rate": 0.03
}

train_set = lgb.Dataset(features_train, label=y_train)

model = lgb.train(params, train_set, num_boost_round=500)

# ================================
# PREDICT
# ================================
pred = model.predict(features_test)
pred_cls = pred.argmax(axis=1)

acc = (pred_cls == y_test.values).mean()

print("===== SEASON SPLIT ACCURACY =====")
print(acc)

# ================================
# SAVE OUTPUTS
# ================================
df_out = df_test.copy()
df_out["pred"] = pred_cls

out_path = os.path.join(SAVE_DIR, "season_split_preds.csv")
df_out.to_csv(out_path, index=False)

print("[OK] Saved predictions →", out_path)
