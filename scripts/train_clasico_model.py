"""
Entrena XGBoost sobre features_mensual.parquet con objetivo 'brote' (clasico > P75).
Registra experimento en MLflow (MLFLOW_TRACKING_URI o ./mlruns si no se configura).
Uso: python scripts/train_clasico_model.py
"""
import json
import os
import pickle

import mlflow
import mlflow.xgboost
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

ROOT       = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH  = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_PATH = os.path.join(ROOT, "model", "xgb_clasico.pkl")
META_PATH  = os.path.join(ROOT, "model", "xgb_clasico_meta.json")

PROHIBIDAS = {
    "divipola", "municipio", "departamento", "periodo",
    "anio", "mes", "casos_grave", "casos_clasico", "brote", "es_inicio",
}
TARGET    = "brote"
TRAIN_END = 2023   # train 2007-2023, test 2024-2025
VAL_START = TRAIN_END - 1   # 2022-2023 dentro de train como proxy validacion

PARAMS = dict(
    n_estimators=400,
    max_depth=6,
    learning_rate=0.05,
    subsample=0.8,
    colsample_bytree=0.8,
    eval_metric="aucpr",
    early_stopping_rounds=30,
    random_state=42,
    n_jobs=-1,
    tree_method="hist",
)

EXPERIMENT = "dengue-brote-clasico"
RUN_NAME   = f"xgboost-train_end={TRAIN_END}"


def feature_cols(df):
    return [c for c in df.columns if c not in PROHIBIDAS and df[c].dtype != object]


def main():
    df    = pd.read_parquet(DATA_PATH)
    feats = feature_cols(df)

    train = df[df["anio"] <= TRAIN_END].copy()
    test  = df[df["anio"] > TRAIN_END].copy()
    val   = train[train["anio"] >= VAL_START].copy()
    tr    = train[train["anio"] < VAL_START].copy()

    X_tr  = tr[feats].fillna(0);   y_tr  = tr[TARGET]
    X_val = val[feats].fillna(0);  y_val = val[TARGET]
    X_te  = test[feats].fillna(0); y_te  = test[TARGET]

    for name, y in [("train", y_tr), ("val", y_val), ("test", y_te)]:
        print(f"  {name:6s}: {len(y):>7,} filas | {y.mean()*100:.1f}% brote")

    spw = float((y_tr == 0).sum() / max((y_tr == 1).sum(), 1))
    print(f"\nscale_pos_weight: {spw:.2f}")

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=RUN_NAME):
        mlflow.log_params({**PARAMS, "scale_pos_weight": round(spw, 2),
                           "train_end": TRAIN_END, "n_features": len(feats)})

        model = xgb.XGBClassifier(scale_pos_weight=spw, **PARAMS)
        model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=50)

        prob_val = model.predict_proba(X_val)[:, 1]
        prob_te  = model.predict_proba(X_te)[:, 1]

        thresholds = np.arange(0.05, 0.95, 0.01)
        f1s        = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thresholds]
        best_thr   = float(thresholds[int(np.argmax(f1s))])

        val_auroc = roc_auc_score(y_val, prob_val)
        val_ap    = average_precision_score(y_val, prob_val)
        te_auroc  = roc_auc_score(y_te, prob_te)
        te_ap     = average_precision_score(y_te, prob_te)

        print(f"\nVal  AUROC: {val_auroc:.4f}  AP: {val_ap:.4f}")
        print(f"Test AUROC: {te_auroc:.4f}  AP: {te_ap:.4f}")
        print(f"Umbral optimo (F1 en val): {best_thr:.2f}")

        mlflow.log_metrics({
            "val_auroc":      val_auroc,
            "val_ap":         val_ap,
            "test_auroc":     te_auroc,
            "test_ap":        te_ap,
            "best_threshold": best_thr,
            "best_iteration": model.best_iteration,
        })
        # Log con flavor nativo de XGBoost (evita restriccion skops de sklearn flavor)
        mlflow.xgboost.log_model(model, name="model",
                                 registered_model_name="dengue-xgb-clasico",
                                 input_example=X_tr[:5])

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    meta = {
        "feature_cols":   feats,
        "target":         TARGET,
        "best_threshold": round(best_thr, 2),
        "val_auroc":      round(val_auroc, 4),
        "val_ap":         round(val_ap, 4),
        "test_auroc":     round(te_auroc, 4),
        "test_ap":        round(te_ap, 4),
        "best_iteration": int(model.best_iteration),
        "train_split":    f"<=anio {TRAIN_END}",
        "test_split":     f">anio {TRAIN_END}",
        "objetivo":       "brote (casos_clasico > P75)",
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\nModelo guardado: {MODEL_PATH}")
    print(f"Meta:            {META_PATH}")
    print(f"Features ({len(feats)}): {feats}")


if __name__ == "__main__":
    main()
