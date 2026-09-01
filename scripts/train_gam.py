"""
Entrena GAM (Modelo Aditivo Generalizado) sobre features_mensual.parquet.
Usa pygam.LogisticGAM con features clave de tendencia, estacionalidad y canal endemico.
Registra en MLflow (mismo experimento que XGBoost y regresion logistica).
Uso: python scripts/train_gam.py
"""
import os
import pickle

import mlflow
import numpy as np
import pandas as pd
from pygam import LogisticGAM, s, l, f
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_PATH = os.path.join(ROOT, "model", "gam_clasico.pkl")

TARGET    = "brote"
TRAIN_END = 2023

# Subconjunto de features para GAM: tendencia reciente + estacionalidad + canal endemico
# (GAM con splines no escala bien a 28 features; seleccionamos las de mayor aporte teorico)
GAM_FEATURES = [
    "casos_clasico_lag_1",   # tendencia reciente
    "casos_clasico_lag_2",
    "casos_clasico_roll3",   # suavizado 3 meses
    "brote_lag_1",           # estado previo (0/1)
    "zona_canal_lag1",       # zona endemica previa (0/1/2)
    "mes_sin",               # componente estacional seno
    "mes_cos",               # componente estacional coseno
    "p75",                   # umbral del canal endemico
    "casos_grave_lag_1",     # dengue grave como indicador
    "es_endemico",           # municipio endemico (0/1)
]

EXPERIMENT = "dengue-brote-clasico"
RUN_NAME   = f"gam-splines-train_end={TRAIN_END}"


def main():
    df = pd.read_parquet(DATA_PATH)

    # Verificar features disponibles
    feats = [f for f in GAM_FEATURES if f in df.columns]
    missing = set(GAM_FEATURES) - set(feats)
    if missing:
        print(f"Advertencia: features no disponibles y excluidas: {missing}")

    train = df[df["anio"] <= TRAIN_END].copy()
    test  = df[df["anio"] > TRAIN_END].copy()
    val   = train[train["anio"] >= TRAIN_END - 1].copy()
    tr    = train[train["anio"] < TRAIN_END - 1].copy()

    X_tr  = tr[feats].fillna(0).values;   y_tr  = tr[TARGET].values
    X_val = val[feats].fillna(0).values;  y_val = val[TARGET].values
    X_te  = test[feats].fillna(0).values; y_te  = test[TARGET].values

    for name, y in [("train", y_tr), ("val", y_val), ("test", y_te)]:
        print(f"  {name:6s}: {len(y):>7,} filas | {y.mean()*100:.1f}% brote")

    # Terminos: spline para continuas, lineal para binarias (brote_lag_1, es_endemico)
    terms = (
        s(0, n_splines=10) +   # casos_clasico_lag_1
        s(1, n_splines=10) +   # casos_clasico_lag_2
        s(2, n_splines=10) +   # casos_clasico_roll3
        l(3) +                 # brote_lag_1 (binaria)
        f(4) +                 # zona_canal_lag1 (categorica 0/1/2)
        s(5, n_splines=6) +    # mes_sin (ciclica -1..1)
        s(6, n_splines=6) +    # mes_cos (ciclica -1..1)
        s(7, n_splines=8) +    # p75
        s(8, n_splines=6) +    # casos_grave_lag_1
        l(9)                   # es_endemico (binaria)
    )

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=RUN_NAME):
        mlflow.log_params({
            "model_type": "LogisticGAM",
            "n_features": len(feats),
            "features": feats,
            "train_end": TRAIN_END,
            "lam": "auto (grid search)",
        })

        print("\nEntrenando GAM con busqueda de lambda en validacion...")
        model = LogisticGAM(terms).gridsearch(X_tr, y_tr, progress=True)

        prob_val = model.predict_proba(X_val)
        prob_te  = model.predict_proba(X_te)

        thresholds = np.arange(0.05, 0.95, 0.01)
        f1s        = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thresholds]
        best_thr   = float(thresholds[int(np.argmax(f1s))])

        val_auroc = roc_auc_score(y_val, prob_val)
        val_ap    = average_precision_score(y_val, prob_val)
        te_auroc  = roc_auc_score(y_te, prob_te)
        te_ap     = average_precision_score(y_te, prob_te)

        mlflow.log_metrics({
            "val_auroc": val_auroc, "val_ap": val_ap,
            "test_auroc": te_auroc, "test_ap": te_ap,
            "best_threshold": best_thr,
            "lam": float(model.lam[0][0]) if hasattr(model, "lam") else -1,
        })

        # pygam no tiene interfaz sklearn, guardamos con pickle y como artefacto
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        with open(MODEL_PATH, "wb") as fh:
            pickle.dump({"model": model, "features": feats,
                         "best_threshold": best_thr}, fh)
        mlflow.log_artifact(MODEL_PATH, artifact_path="model")

        print(f"\nVal  AUROC: {val_auroc:.4f}  AP: {val_ap:.4f}")
        print(f"Test AUROC: {te_auroc:.4f}  AP: {te_ap:.4f}")
        print(f"Umbral optimo: {best_thr:.2f}")
        print(f"Modelo guardado: {MODEL_PATH}")


if __name__ == "__main__":
    main()
