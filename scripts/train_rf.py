"""
Entrena Random Forest sobre features_mensual.parquet con objetivo 'brote'.
Registra en MLflow (experimento 'sat-dengue').
Uso:
  python scripts/train_rf.py               # T+1
  python scripts/train_rf.py --horizonte 2  # T+2
"""
import argparse
import os
import sys

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import (ANIO_FIN_TRAIN, EXPERIMENT, full_metrics, log_full_metrics,
                         make_t2_target, print_metrics, registrar_por_alcance)

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR = os.path.join(ROOT, "model")

PROHIBIDAS = {
    "divipola", "municipio", "departamento", "periodo",
    "anio", "mes", "casos_grave", "casos_clasico", "brote", "es_inicio",
    "__target_t2",
}
TRAIN_END = ANIO_FIN_TRAIN  # 2022, importado de src/evaluation/splits.py
CITIES    = {"68001": "Bucaramanga", "76001": "Cali"}

PARAMS = dict(
    n_estimators=500,
    max_depth=12,
    min_samples_leaf=20,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)



def feature_cols(df):
    return [c for c in df.columns
            if c not in PROHIBIDAS
            and pd.api.types.is_numeric_dtype(df[c])]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizonte", type=int, default=1, choices=[1, 2])
    args = parser.parse_args()
    H = args.horizonte

    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

    df = pd.read_parquet(DATA_PATH)

    if H == 2:
        df, target_col = make_t2_target(df, "objetivo")
    else:
        target_col = "brote"

    feats = feature_cols(df)

    train = df[df["anio"] <= TRAIN_END].copy()
    test  = df[df["anio"] > TRAIN_END].copy()
    val   = train[train["anio"] >= TRAIN_END - 1].copy()
    tr    = train[train["anio"] < TRAIN_END - 1].copy()

    X_tr  = tr[feats].fillna(0);   y_tr  = tr[target_col]
    X_val = val[feats].fillna(0);  y_val = val[target_col]
    X_te  = test[feats].fillna(0); y_te  = test[target_col]

    y_ini_te = test["es_inicio"] if "es_inicio" in test.columns else None

    for name, y in [("train", y_tr), ("val", y_val), ("test", y_te)]:
        print(f"  {name:6s}: {len(y):>7,} filas | {y.mean()*100:.1f}% brote")

    run_name = f"random-forest-T+{H}-train_end={TRAIN_END}"
    registered_name = f"dengue-rf-clasico-T{H}"

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({**PARAMS, "train_end": TRAIN_END, "n_features": len(feats),
                           "horizonte": H, "output_type": "probability"})

        model = RandomForestClassifier(**PARAMS)
        model.fit(X_tr, y_tr)

        prob_val = model.predict_proba(X_val)[:, 1]
        prob_te  = model.predict_proba(X_te)[:, 1]

        thresholds = np.arange(0.05, 0.95, 0.01)
        f1s      = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thresholds]
        best_thr = float(thresholds[int(np.argmax(f1s))])
        pred_te  = (prob_te >= best_thr).astype(int)

        val_auroc = roc_auc_score(y_val, prob_val)
        val_ap    = average_precision_score(y_val, prob_val)
        te_auroc  = roc_auc_score(y_te, prob_te)
        te_ap     = average_precision_score(y_te, prob_te)

        mlflow.log_metrics({
            "val_auroc": val_auroc, "val_ap": val_ap,
            "test_auroc": te_auroc, "test_ap": te_ap,
            "best_threshold": best_thr,
        })

        print(f"\nT+{H} | AUROC={te_auroc:.4f} AP={te_ap:.4f} thr={best_thr:.2f}")
        registrar_por_alcance(test["divipola"], y_te, pred_te, y_ini_te, prob_te)

        mlflow.sklearn.log_model(
            model, artifact_path="model",
            registered_model_name=registered_name,
            skops_trusted_types=["sklearn.ensemble._forest.RandomForestClassifier"],
        )

        print(f"\nVal  AUROC: {val_auroc:.4f}  AP: {val_ap:.4f}")
        print(f"Test AUROC: {te_auroc:.4f}  AP: {te_ap:.4f}")
        print(f"Umbral optimo: {best_thr:.2f}")


if __name__ == "__main__":
    main()
