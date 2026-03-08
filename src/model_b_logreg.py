import pandas as pd
import numpy as np
import os
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, log_loss

BASE = os.path.dirname(os.path.dirname(__file__))
DATASET = os.path.join(BASE, "data", "processed", "ratings_dataset.csv")

# ===============================
# 1. VERİNİN YÜKLENMESİ
# ===============================
df = pd.read_csv(DATASET, parse_dates=["date"])

# Kullanacağımız feature'lar
features = [
    "home_elo", "away_elo",
    "home_att", "away_att",
    "home_def", "away_def"
]

X = df[features]
y = df["result"]            # -1 / 0 / 1


# ===============================
# 2. ZAMAN BAZLI SPLIT
# ===============================
split_date = "2024-08-01"   # Tüm liglerde ortak eşik
train = df[df["date"] < split_date]
test  = df[df["date"] >= split_date]

X_train = train[features]
y_train = train["result"]

X_test = test[features]
y_test = test["result"]

print("Train shape:", X_train.shape)
print("Test shape:", X_test.shape)


# ===============================
# 3. MODEL PIPELINE
# ===============================
pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("logreg", LogisticRegression(
        multi_class="multinomial",
        max_iter=500,
        C=1.0
    ))
])

pipe.fit(X_train, y_train)

# ===============================
# 4. TAHMİNLER
# ===============================
probs = pipe.predict_proba(X_test)
preds = pipe.predict(X_test)

acc = accuracy_score(y_test, preds)
loss = log_loss(y_test, probs)

print("\n=== BASIT MODEL SONUÇLARI ===")
print("Accuracy:", round(acc, 3))
print("Log Loss:", round(loss, 3))

# Olasılıkları tabloya ekleyelim
labels = pipe.classes_  # [-1, 0, 1]

test_result = test.copy()
test_result["P_A"] = probs[:, list(labels).index(-1)]
test_result["P_D"] = probs[:, list(labels).index(0)]
test_result["P_H"] = probs[:, list(labels).index(1)]

OUT = os.path.join(BASE, "data", "processed", "logreg_predictions.csv")
test_result.to_csv(OUT, index=False)

print("\n[OK] Tahmin datası kaydedildi:")
print(OUT)
print(test_result[["home_team", "away_team", "P_H", "P_D", "P_A"]].head())
