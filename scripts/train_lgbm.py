"""
Entrena LightGBM sobre features_mensual.parquet con objetivo 'brote'.
Registra en MLflow (experimento 'dengue-brote-clasico').
Uso: python scripts/train_lgbm.py
"""
import os
import pickle

import mlflow
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

ROOT       = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH  = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_PATH = os.path.join(ROOT, "model", "lgbm_clasico.pkl")

PROHIBIDAS = {
    "divipola", "municipio", "departamento", "periodo",
    "anio", "mes", "casos_grave", "casos_clasico", "brote", "es_inicio",
}
TARGET    = "brote"
TRAIN_END = 2023

PARAMS = dict(
    n_estimators=500,
    max_depth=6,
    learning_rate=0.05,
    num_leaves=63,
    subsample=0.8,
    colsample_bytree=0.8,
    min_child_samples=20,
    is_unbalance=True,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)

EXPERIMENT = "dengue-brote-clasico"
RUN_NAME   = f"lightgbm-train_end={TRAIN_END}"


def feature_cols(df):
    return [c for c in df.columns
            if c not in PROHIBIDAS
            and pd.api.types.is_numeric_dtype(df[c])]


def main():
    df    = pd.read_parquet(DATA_PATH)
    feats = feature_cols(df)

    train = df[df["anio"] <= TRAIN_END].copy()
    test  = df[df["anio"] > TRAIN_END].copy()
    val   = train[train["anio"] >= TRAIN_END - 1].copy()
    tr    = train[train["anio"] < TRAIN_END - 1].copy()

    X_tr  = tr[feats].fillna(0);   y_tr  = tr[TARGET]
    X_val = val[feats].fillna(0);  y_val = val[TARGET]
    X_te  = test[feats].fillna(0); y_te  = test[TARGET]

    for name, y in [("train", y_tr), ("val", y_val), ("test", y_te)]:
        print(f"  {name:6s}: {len(y):>7,} filas | {y.mean()*100:.1f}% brote")

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=RUN_NAME):
        mlflow.log_params({**PARAMS, "train_end": TRAIN_END, "n_features": len(feats)})

        model = lgb.LGBMClassifier(**PARAMS)
        model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(30, verbose=False),
                       lgb.log_evaluation(50)],
        )

        prob_val = model.predict_proba(X_val)[:, 1]
        prob_te  = model.predict_proba(X_te)[:, 1]

        thresholds = np.arange(0.05, 0.95, 0.01)
        f1s        = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thresholds]
        best_thr   = float(thresholds[int(np.argmax(f1s))])

        val_auroc = roc_auc_score(y_val, prob_val)
        val_ap    = average_precision_score(y_val, prob_val)
        te_auroc  = roc_auc_score(y_te, prob_te)
        te_ap     = average_precision_score(y_te, prob_te)

        mlflow.log_metrics({
            "val_auroc":      val_auroc,
            "val_ap":         val_ap,
            "test_auroc":     te_auroc,
            "test_ap":        te_ap,
            "best_threshold": best_thr,
            "best_iteration": int(model.best_iteration_),
        })
        mlflow.lightgbm.log_model(model, name="model",
                                  registered_model_name="dengue-lgbm-clasico")

        print(f"\nVal  AUROC: {val_auroc:.4f}  AP: {val_ap:.4f}")
        print(f"Test AUROC: {te_auroc:.4f}  AP: {te_ap:.4f}")
        print(f"Umbral optimo: {best_thr:.2f}")
        print(f"Best iteration: {model.best_iteration_}")

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"Modelo guardado: {MODEL_PATH}")


if __name__ == "__main__":
    main()
