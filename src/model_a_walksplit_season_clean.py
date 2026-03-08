import pandas as pd
import lightgbm as lgb
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC_DIR = os.path.join(BASE_DIR, "data", "processed")
PATH = os.path.join(PROC_DIR, "full_features.csv")
SAVE_DIR = PROC_DIR

print("[*] Loading full_features.csv …")
df = pd.read_csv(PATH)
print("[OK] Loaded full:", df.shape)

# -----------------------------
# SEASON SPLIT
# -----------------------------
train_seasons = ["2021-2022", "2022-2023"]
test_seasons  = ["2023-2024"]

df_train = df[df["season"].isin(train_seasons)].copy()
df_test  = df[df["season"].isin(test_seasons)].copy()

print("RAW train:", df_train.shape)
print("RAW test :", df_test.shape)

# -----------------------------
# TARGET MAPPING
# -----------------------------
def map_label(x):
    return { -1:0, 0:1, 1:2 }[x]

y_train = df_train["result"].apply(map_label)
y_test  = df_test["result"].apply(map_label)

# -----------------------------
# HARD LEAKAGE DROP LIST
# -----------------------------
leak_drop = [
    "lambda_home","lambda_away",
    "p_home","p_draw","p_away",
    "p_over25","p_under25","p_btts",
    "home_att","home_def","away_att","away_def",
    "home_result","away_result",
    "home_team_points","away_team_points",
    "home_home_goals","home_away_goals",
    "away_home_goals","away_away_goals"
]

base_drop = [
    "date","league","season","home_team","away_team",
    "home_league","home_season","team_x",
    "away_league","away_season","team_y",
    "result"
]

drop_cols = leak_drop + base_drop

X_train = df_train.drop(columns=drop_cols, errors="ignore")
X_test  = df_test.drop(columns=drop_cols, errors="ignore")

# Auto-drop remaining object cols
bad = X_train.select_dtypes(include=["object"]).columns.tolist()
if bad:
    print("[!] Auto-drop:", bad)
    X_train = X_train.drop(columns=bad)
    X_test = X_test.drop(columns=bad)

print("[INFO] Final feature shapes → Train:", X_train.shape, "Test:", X_test.shape)

# -----------------------------
# LIGHTGBM MODEL
# -----------------------------
params = {
    "objective": "multiclass",
    "num_class": 3,
    "learning_rate": 0.04,
    "metric": "multi_logloss"
}

train_set = lgb.Dataset(X_train, label=y_train)

print("[*] Training LightGBM…")
model = lgb.train(params, train_set, num_boost_round=500)

# -----------------------------
# PREDICT
# -----------------------------
pred = model.predict(X_test)
pred_cls = pred.argmax(axis=1)

acc = (pred_cls == y_test.values).mean()
print("===== CLEAN ACCURACY =====")
print(acc)

# -----------------------------
# SAVE OUTPUT
# -----------------------------
df_out = df_test.copy()
df_out["pred"] = pred_cls

save_path = os.path.join(SAVE_DIR, "walk_season_preds_clean.csv")
df_out.to_csv(save_path, index=False)

print("[OK] Saved →", save_path)
