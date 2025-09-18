# src/modeling.py
from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
import joblib

def time_split(df: pd.DataFrame, test_ratio: float = 0.2):
    n = len(df)
    split = int(n * (1 - test_ratio))
    return df.iloc[:split], df.iloc[split:]

def train_and_save(df: pd.DataFrame, feature_cols, target_col="y", artifacts_dir="artifacts"):
    Path(artifacts_dir).mkdir(exist_ok=True)

    df = df.copy()
    df_train, df_test = time_split(df.dropna())

    X_train = df_train[feature_cols].values
    y_train = df_train[target_col].values
    X_test = df_test[feature_cols].values
    y_test = df_test[target_col].values

    pipe = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000))
    ])
    pipe.fit(X_train, y_train)

    y_pred = pipe.predict(X_test)
    y_proba = pipe.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_pred))
    try:
        auc = float(roc_auc_score(y_test, y_proba))
    except Exception:
        auc = None

    # простейшая стратегия: long, если p>0.55 (без плеча и комиссий)
    thr = 0.55
    signal = (y_proba > thr).astype(int)
    future_ret = df_test["future_ret"].values
    strat_ret = (signal * future_ret)

    total_return = float(np.prod(1.0 + strat_ret) - 1.0)
    sharpe_like = float(np.mean(strat_ret) / (np.std(strat_ret) + 1e-9) * np.sqrt(len(strat_ret))) if len(strat_ret) > 1 else None

    metrics = {
        "n_train": int(len(df_train)),
        "n_test": int(len(df_test)),
        "accuracy": acc,
        "roc_auc": auc,
        "threshold": thr,
        "total_return": total_return,
        "sharpe_like": sharpe_like
    }

    # сохраняем артефакты
    joblib.dump(pipe, f"{artifacts_dir}/model_logreg.pkl")
    with open(f"{artifacts_dir}/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    with open(f"{artifacts_dir}/features.json", "w", encoding="utf-8") as f:
        json.dump({"features": feature_cols}, f, ensure_ascii=False, indent=2)

    return metrics
