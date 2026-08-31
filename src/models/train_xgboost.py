"""
Entrenamiento XGBoost — script de produccion.
Uso:
    python -m src.models.train_xgboost [--data PATH] [--mlflow-uri URI] [--run-name NAME]
"""
import argparse
import json
import os
import pickle

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    average_precision_score, f1_score,
    precision_score, recall_score, roc_auc_score,
)

FEATURE_COLS = (
    [f"grave_lag_{l}"   for l in [1, 2, 3, 4, 6]] +
    [f"clasico_lag_{l}" for l in [1, 2, 3, 4, 6]] +
    ["grave_roll3", "clasico_roll3"] +
    ["temp_mean_c", "temp_lag_1", "temp_lag_2", "temp_lag_3"] +
    ["rain_mm_day", "rain_lag_1", "rain_lag_2", "rain_lag_3"] +
    ["mes_sin", "mes_cos", "anio_epidemia", "ANO", "MES"] +
    ["es_endemico", "zona_canal_lag1", "p25", "p75", "sir_lag1"]
)  # 30 features mensuales
TARGET = "grave"


def load_splits(data_path: str):
    df = pd.read_csv(data_path, low_memory=False)
    df["grave_bin"] = (df[TARGET] > 0).astype(int)
    train = df[df["ANO"] <= 2021]
    val   = df[df["ANO"] == 2022]
    test  = df[df["ANO"] >= 2023]
    return (
        train[FEATURE_COLS], train["grave_bin"],
        val[FEATURE_COLS],   val["grave_bin"],
        test[FEATURE_COLS],  test["grave_bin"],
    )


def compute_metrics(y_true, y_prob, threshold=0.5):
    y_pred = (y_prob >= threshold).astype(int)
    return {
        "precision":     float(precision_score(y_true, y_pred, zero_division=0)),
        "recall":        float(recall_score(y_true, y_pred, zero_division=0)),
        "f1":            float(f1_score(y_true, y_pred, zero_division=0)),
        "auroc":         float(roc_auc_score(y_true, y_prob)),
        "avg_precision": float(average_precision_score(y_true, y_prob)),
    }


def find_best_threshold(y_true, y_prob):
    thresholds = np.arange(0.05, 0.95, 0.01)
    f1s = [f1_score(y_true, (y_prob >= t).astype(int), zero_division=0) for t in thresholds]
    return float(thresholds[int(np.argmax(f1s))])


def train(args):
    X_train, y_train, X_val, y_val, X_test, y_test = load_splits(args.data)

    spw = float((y_train == 0).sum() / (y_train == 1).sum())
    print(f"scale_pos_weight: {spw:.2f}")

    mlflow.set_tracking_uri(args.mlflow_uri)
    mlflow.set_experiment(args.experiment)

    # ── Baseline ──────────────────────────────────────────────────────────────
    with mlflow.start_run(run_name="baseline-stratified"):
        dummy = DummyClassifier(strategy="stratified", random_state=42)
        dummy.fit(X_train, y_train)
        mlflow.log_param("model", "DummyClassifier-stratified")
        for split, X, y in [("val", X_val, y_val), ("test", X_test, y_test)]:
            prob = dummy.predict_proba(X)[:, 1]
            mlflow.log_metrics({f"{split}_{k}": v for k, v in compute_metrics(y, prob).items()})

    # ── XGBoost ───────────────────────────────────────────────────────────────
    params = {
        "n_estimators": 500,
        "max_depth": 6,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "scale_pos_weight": spw,
        "eval_metric": "aucpr",
        "early_stopping_rounds": 30,
        "random_state": 42,
        "n_jobs": -1,
        "tree_method": "hist",
    }

    with mlflow.start_run(run_name=args.run_name) as run:
        mlflow.log_params({k: v for k, v in params.items()
                           if k not in ["early_stopping_rounds", "random_state", "n_jobs"]})
        mlflow.log_param("n_features", len(FEATURE_COLS))
        mlflow.log_param("train_rows", len(X_train))
        mlflow.log_param("train_pos_pct", round(float(y_train.mean()) * 100, 2))

        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=50)

        mlflow.log_param("best_iteration", model.best_iteration)

        prob_val  = model.predict_proba(X_val)[:, 1]
        prob_test = model.predict_proba(X_test)[:, 1]

        for split, y, prob in [("val", y_val, prob_val), ("test", y_test, prob_test)]:
            mlflow.log_metrics({f"{split}_{k}": v
                                for k, v in compute_metrics(y, prob).items()})

        best_thr = find_best_threshold(y_val, prob_val)
        mlflow.log_param("best_threshold", round(best_thr, 2))

        # Metricas con umbral optimo en test
        mlflow.log_metrics({f"test_opt_{k}": v
                             for k, v in compute_metrics(y_test, prob_test, best_thr).items()})

        mlflow.xgboost.log_model(model, artifact_path="model")

        # Guardar localmente como fallback para la API
        out_dir = args.output_dir
        os.makedirs(out_dir, exist_ok=True)
        pkl = os.path.join(out_dir, "xgb_model.pkl")
        with open(pkl, "wb") as f:
            pickle.dump(model, f)

        meta = {
            "run_id": run.info.run_id,
            "mlflow_uri": args.mlflow_uri,
            "best_threshold": round(best_thr, 2),
            "best_iteration": model.best_iteration,
            "n_features": len(FEATURE_COLS),
            "feature_cols": FEATURE_COLS,
        }
        with open(os.path.join(out_dir, "model_meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        print(f"\nrun_id: {run.info.run_id}")
        print(f"Modelo: {pkl}")
        return run.info.run_id


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/processed/dengue_features_modelado.csv")
    parser.add_argument("--mlflow-uri", default="http://127.0.0.1:5000")
    parser.add_argument("--experiment", default="dengue-grave-xgboost")
    parser.add_argument("--run-name", default="xgboost-v1")
    parser.add_argument("--output-dir", default="model")
    args = parser.parse_args()
    train(args)
