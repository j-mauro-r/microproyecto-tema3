"""
Comparacion de modelos — script de produccion.
Entrena LR, Poisson, GAM-Poisson, RF y XGBoost; registra todos en MLflow.
Uso:
    python -m src.models.train_comparison [--data PATH] [--mlflow-uri URI]
"""
import argparse
import os
import warnings
import numpy as np
import pandas as pd
import mlflow
import mlflow.sklearn
import mlflow.xgboost
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, average_precision_score, f1_score,
    precision_score, recall_score,
)
import xgboost as xgb

warnings.filterwarnings("ignore")

FEATURE_COLS = (
    [f"grave_lag_{l}"   for l in [1, 2, 3, 4, 6]] +
    [f"clasico_lag_{l}" for l in [1, 2, 3, 4, 6]] +
    ["grave_roll3", "clasico_roll3"] +
    ["temp_mean_c", "temp_lag_1", "temp_lag_2", "temp_lag_3"] +
    ["rain_mm_day", "rain_lag_1", "rain_lag_2", "rain_lag_3"] +
    ["mes_sin", "mes_cos", "anio_epidemia", "ANO", "MES"] +
    ["es_endemico", "zona_canal_lag1", "p25", "p75", "sir_lag1"]
)  # 30 features mensuales

GAM_FEATURES = [
    "grave_lag_1", "grave_lag_2", "grave_lag_4", "grave_roll3",
    "clasico_lag_1", "clasico_roll3",
    "sir_lag1", "zona_canal_lag1", "p75",
    "mes_sin", "mes_cos", "ANO",
]


def _metricas(y_true, y_prob, thr=0.5):
    y_pred = (y_prob >= thr).astype(int)
    return {
        "auroc":         float(roc_auc_score(y_true, y_prob)),
        "avg_precision": float(average_precision_score(y_true, y_prob)),
        "f1":            float(f1_score(y_true, y_pred, zero_division=0)),
        "recall":        float(recall_score(y_true, y_pred, zero_division=0)),
        "precision":     float(precision_score(y_true, y_pred, zero_division=0)),
    }


def _best_thr(y_val, prob_val):
    thrs = np.arange(0.05, 0.95, 0.01)
    f1s  = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thrs]
    return float(thrs[int(np.argmax(f1s))])


def run(args):
    df = pd.read_csv(args.data, low_memory=False)
    df["grave_bin"] = (df["grave"] > 0).astype(int)

    train = df[df["ANO"] <= 2021]
    val   = df[df["ANO"] == 2022]
    test  = df[df["ANO"] >= 2023]

    X_tr = train[FEATURE_COLS].fillna(0)
    X_va = val[FEATURE_COLS].fillna(0)
    X_te = test[FEATURE_COLS].fillna(0)
    y_tr_bin = train["grave_bin"]
    y_va_bin = val["grave_bin"]
    y_te_bin = test["grave_bin"]
    y_tr_cnt = train["grave"]

    scaler = StandardScaler()
    X_tr_sc = scaler.fit_transform(X_tr)
    X_va_sc = scaler.transform(X_va)
    X_te_sc = scaler.transform(X_te)

    spw = float((y_tr_bin == 0).sum() / (y_tr_bin == 1).sum())

    mlflow.set_tracking_uri(args.mlflow_uri)
    mlflow.set_experiment(args.experiment)

    results = {}

    # ── Regresion Logistica ────────────────────────────────────────────────────
    print("Entrenando Regresion Logistica...")
    with mlflow.start_run(run_name="logistic-regression"):
        lr = LogisticRegression(C=0.1, class_weight="balanced",
                                max_iter=500, n_jobs=-1, random_state=42)
        lr.fit(X_tr_sc, y_tr_bin)
        mlflow.log_params({"model": "LogisticRegression", "C": 0.1})
        p_va = lr.predict_proba(X_va_sc)[:, 1]
        p_te = lr.predict_proba(X_te_sc)[:, 1]
        thr  = _best_thr(y_va_bin, p_va)
        mlflow.log_metrics({f"val_{k}":  v for k, v in _metricas(y_va_bin, p_va, thr).items()})
        mlflow.log_metrics({f"test_{k}": v for k, v in _metricas(y_te_bin, p_te, thr).items()})
        mlflow.log_param("best_threshold", round(thr, 2))
        mlflow.sklearn.log_model(lr, "model")
        results["Logistica"] = {"val": _metricas(y_va_bin, p_va, thr),
                                "test": _metricas(y_te_bin, p_te, thr)}

    # ── Regresion de Poisson ───────────────────────────────────────────────────
    print("Entrenando Regresion de Poisson...")
    with mlflow.start_run(run_name="poisson-regression"):
        po = PoissonRegressor(alpha=0.1, max_iter=300)
        po.fit(X_tr_sc, y_tr_cnt)
        mlflow.log_params({"model": "PoissonRegressor", "alpha": 0.1})
        lam_va = np.clip(po.predict(X_va_sc), 0, None)
        lam_te = np.clip(po.predict(X_te_sc), 0, None)
        p_va = 1 - np.exp(-lam_va)
        p_te = 1 - np.exp(-lam_te)
        thr  = _best_thr(y_va_bin, p_va)
        mlflow.log_metrics({f"val_{k}":  v for k, v in _metricas(y_va_bin, p_va, thr).items()})
        mlflow.log_metrics({f"test_{k}": v for k, v in _metricas(y_te_bin, p_te, thr).items()})
        mlflow.log_param("best_threshold", round(thr, 2))
        mlflow.sklearn.log_model(po, "model")
        results["Poisson"] = {"val": _metricas(y_va_bin, p_va, thr),
                              "test": _metricas(y_te_bin, p_te, thr)}

    # ── GAM de Poisson ─────────────────────────────────────────────────────────
    print("Entrenando GAM de Poisson...")
    X_tr_g = train[GAM_FEATURES].fillna(0).values
    X_va_g = val[GAM_FEATURES].fillna(0).values
    X_te_g = test[GAM_FEATURES].fillna(0).values
    with mlflow.start_run(run_name="gam-poisson"):
        mlflow.log_param("n_features_gam", len(GAM_FEATURES))
        try:
            from pygam import PoissonGAM, s
            terms = sum(s(i) for i in range(len(GAM_FEATURES)))
            gam = PoissonGAM(terms).fit(X_tr_g, y_tr_cnt)
            lam_va = np.clip(gam.predict(X_va_g), 0, None)
            lam_te = np.clip(gam.predict(X_te_g), 0, None)
            mlflow.log_param("gam_backend", "pygam")
        except ImportError:
            # Fallback: Poisson con features GAM (sin splines)
            po2 = PoissonRegressor(alpha=0.01, max_iter=300)
            po2.fit(X_tr_g, y_tr_cnt)
            lam_va = np.clip(po2.predict(X_va_g), 0, None)
            lam_te = np.clip(po2.predict(X_te_g), 0, None)
            mlflow.log_param("gam_backend", "poisson-fallback")
        p_va = 1 - np.exp(-lam_va)
        p_te = 1 - np.exp(-lam_te)
        thr  = _best_thr(y_va_bin, p_va)
        mlflow.log_metrics({f"val_{k}":  v for k, v in _metricas(y_va_bin, p_va, thr).items()})
        mlflow.log_metrics({f"test_{k}": v for k, v in _metricas(y_te_bin, p_te, thr).items()})
        mlflow.log_param("best_threshold", round(thr, 2))
        results["GAM-Poisson"] = {"val": _metricas(y_va_bin, p_va, thr),
                                  "test": _metricas(y_te_bin, p_te, thr)}

    # ── Random Forest ──────────────────────────────────────────────────────────
    print("Entrenando Random Forest...")
    with mlflow.start_run(run_name="random-forest"):
        rf = RandomForestClassifier(n_estimators=200, max_depth=10,
                                    class_weight="balanced",
                                    n_jobs=-1, random_state=42)
        rf.fit(X_tr, y_tr_bin)
        mlflow.log_params({"model": "RandomForest", "n_estimators": 200, "max_depth": 10})
        p_va = rf.predict_proba(X_va)[:, 1]
        p_te = rf.predict_proba(X_te)[:, 1]
        thr  = _best_thr(y_va_bin, p_va)
        mlflow.log_metrics({f"val_{k}":  v for k, v in _metricas(y_va_bin, p_va, thr).items()})
        mlflow.log_metrics({f"test_{k}": v for k, v in _metricas(y_te_bin, p_te, thr).items()})
        mlflow.log_param("best_threshold", round(thr, 2))
        mlflow.sklearn.log_model(rf, "model")
        results["RandomForest"] = {"val": _metricas(y_va_bin, p_va, thr),
                                   "test": _metricas(y_te_bin, p_te, thr)}

    # ── XGBoost ────────────────────────────────────────────────────────────────
    print("Entrenando XGBoost...")
    with mlflow.start_run(run_name="xgboost-v1-ref"):
        xgb_m = xgb.XGBClassifier(
            n_estimators=500, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=spw, eval_metric="aucpr",
            early_stopping_rounds=30, random_state=42,
            n_jobs=-1, tree_method="hist",
        )
        xgb_m.fit(X_tr, y_tr_bin, eval_set=[(X_va, y_va_bin)], verbose=False)
        mlflow.log_params({"model": "XGBoost", "scale_pos_weight": round(spw, 1),
                           "best_iteration": xgb_m.best_iteration})
        p_va = xgb_m.predict_proba(X_va)[:, 1]
        p_te = xgb_m.predict_proba(X_te)[:, 1]
        thr  = _best_thr(y_va_bin, p_va)
        mlflow.log_metrics({f"val_{k}":  v for k, v in _metricas(y_va_bin, p_va, thr).items()})
        mlflow.log_metrics({f"test_{k}": v for k, v in _metricas(y_te_bin, p_te, thr).items()})
        mlflow.log_param("best_threshold", round(thr, 2))
        mlflow.xgboost.log_model(xgb_m, "model")
        results["XGBoost"] = {"val": _metricas(y_va_bin, p_va, thr),
                              "test": _metricas(y_te_bin, p_te, thr)}

    # ── Tabla ──────────────────────────────────────────────────────────────────
    rows = []
    for nombre, res in results.items():
        for split, m in res.items():
            rows.append({"Modelo": nombre, "Conjunto": split,
                         "AUROC": round(m["auroc"], 3),
                         "AP": round(m["avg_precision"], 3),
                         "F1": round(m["f1"], 3)})
    comp = pd.DataFrame(rows)
    out_csv = os.path.join(os.path.dirname(args.data), "comparacion_modelos.csv")
    comp.to_csv(out_csv, index=False)
    print("\n=== Comparacion de modelos ===")
    print(comp.to_string(index=False))
    print(f"\nGuardado: {out_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data",       default="data/processed/dengue_features_modelado.csv")
    parser.add_argument("--mlflow-uri", default="http://127.0.0.1:5000")
    parser.add_argument("--experiment", default="dengue-grave-xgboost")
    args = parser.parse_args()
    run(args)
