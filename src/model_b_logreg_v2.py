import pandas as pd
import numpy as np
import os
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, log_loss

BASE = os.path.dirname(os.path.dirname(__file__))
DATASET = os.path.join(BASE, "data", "processed", "full_features.csv")

print("[*] Loading:", DATASET)
df = pd.read_csv(DATASET, parse_dates=["date"])

# ---- Label
y = df["result"]

# ---- Basit özellikler Model B için
features = [
    "home_elo", "away_elo",
    "home_att", "away_att",
    "home_def", "away_def"
]

X = df[features]

# ---- Zaman bazlı split (A model ile aynı)
split_date = "2024-08-01"

train = df[df["date"] < split_date]
test  = df[df["date"] >= split_date]

X_train = train[features]
y_train = train["result"]

X_test = test[features]
y_test = test["result"]

print("Train:", X_train.shape, "Test:", X_test.shape)

# ---- Pipeline
pipe = Pipeline([
    ("scaler", StandardScaler()),
    ("logreg", LogisticRegression(
        multi_class="multinomial",
        max_iter=500,
        C=1.0
    ))
])

pipe.fit(X_train, y_train)

probs = pipe.predict_proba(X_test)
preds = pipe.predict(X_test)

acc = accuracy_score(y_test, preds)
loss = log_loss(y_test, probs)

print("\n=== MODEL B RESULTS ===")
print("Accuracy:", acc)
print("LogLoss:", loss)

labels = pipe.classes_

test_result = test.copy()
test_result["P_A"] = probs[:, list(labels).index(-1)]
test_result["P_D"] = probs[:, list(labels).index(0)]
test_result["P_H"] = probs[:, list(labels).index(1)]

OUT = os.path.join(BASE, "data", "processed", "logreg_predictions.csv")
test_result.to_csv(OUT, index=False)

print("\nSaved →", OUT)
