"""
Entrena GAM (Modelo Aditivo Generalizado) sobre features_mensual.parquet.
Usa pygam.LogisticGAM con features clave de tendencia, estacionalidad y canal endemico.
Registra en MLflow (mismo experimento que XGBoost y regresion logistica).
Uso:
  python scripts/train_gam.py               # T+1
  python scripts/train_gam.py --horizonte 2  # T+2
"""
import argparse
import os
import pickle
import sys

import mlflow
import numpy as np
import pandas as pd
from pygam import LogisticGAM, s, l, f
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import full_metrics, log_full_metrics, make_t2_target, print_metrics

ROOT       = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH  = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR  = os.path.join(ROOT, "model")

TRAIN_END = 2023
CITIES    = {"68001": "Bucaramanga", "76001": "Cali"}

GAM_FEATURES = [
    "casos_clasico_lag_1",
    "casos_clasico_lag_2",
    "casos_clasico_roll3",
    "brote_lag_1",
    "zona_canal",
    "mes_sin",
    "mes_cos",
    "p75",
    "casos_grave_lag_1",
    "es_endemico",
]
GAM_SAMPLE = 50_000  # GAM scales poorly with n; use subsample

EXPERIMENT = "dengue-brote-clasico"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--horizonte", type=int, default=1, choices=[1, 2])
    parser.add_argument("--lam", type=float, default=0.6,
                        help="Lambda de regularizacion (default=0.6)")
    args = parser.parse_args()
    H = args.horizonte

    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

    df = pd.read_parquet(DATA_PATH)

    if H == 2:
        df, target_col = make_t2_target(df, "objetivo")
    else:
        target_col = "objetivo"

    df = df[df[target_col].notna()].copy()

    feats = [ft for ft in GAM_FEATURES if ft in df.columns]
    missing = set(GAM_FEATURES) - set(feats)
    if missing:
        print(f"Advertencia: features excluidas (no disponibles): {missing}")

    train = df[df["anio"] <= TRAIN_END].copy()
    test  = df[df["anio"] > TRAIN_END].copy()
    val   = train[train["anio"] >= TRAIN_END - 1].copy()
    tr    = train[train["anio"] < TRAIN_END - 1].copy()

    test_divipola = test["divipola"].astype(str)
    y_ini_te      = test["es_inicio"].values if "es_inicio" in test.columns else None

    # Use subsample for GAM (scales poorly with n)
    rng = np.random.default_rng(42)
    idx = rng.choice(len(tr), size=min(GAM_SAMPLE, len(tr)), replace=False)
    X_tr  = tr[feats].fillna(0).values[idx];  y_tr  = tr[target_col].values[idx]
    X_val = val[feats].fillna(0).values;       y_val = val[target_col].values
    X_te  = test[feats].fillna(0).values;      y_te  = test[target_col].values

    for name, y in [("train (sample)", y_tr), ("val", y_val), ("test", y_te)]:
        print(f"  {name:20s}: {len(y):>7,} filas | {y.mean()*100:.1f}% objetivo")

    # Terminos: spline para continuas, lineal para binarias, factor para categorica
    def make_terms(feats):
        pieces = []
        for i, ft in enumerate(feats):
            if ft in ("brote_lag_1", "es_endemico"):
                pieces.append(l(i))
            elif ft == "zona_canal":
                pieces.append(f(i))
            else:
                pieces.append(s(i, n_splines=8))
        return sum(pieces[1:], pieces[0])

    terms = make_terms(feats)

    run_name = f"gam-splines-T+{H}-lam={args.lam}-train_end={TRAIN_END}"
    registered_name = f"dengue-gam-clasico-T{H}"
    model_file = os.path.join(MODEL_DIR, f"gam_clasico_T{H}.pkl")

    mlflow.set_experiment(EXPERIMENT)
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({
            "model_type": "LogisticGAM",
            "n_features": len(feats),
            "features": str(feats),
            "train_end": TRAIN_END,
            "lam": args.lam,
            "horizonte": H,
            "output_type": "probability",
            "gam_sample": GAM_SAMPLE,
        })

        print(f"\nEntrenando GAM con lam={args.lam} (n={len(y_tr):,}) ...")
        model = LogisticGAM(terms, lam=args.lam).fit(X_tr, y_tr)

        prob_val = model.predict_proba(X_val)
        prob_te  = model.predict_proba(X_te)

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

        m_te = full_metrics(y_te, pred_te, y_ini_te, y_score=prob_te)
        log_full_metrics(m_te, prefix="test")
        print(f"\nT+{H} | AUROC={te_auroc:.4f} AP={te_ap:.4f} thr={best_thr:.2f}")
        print_metrics(m_te, f"Global T+{H}")

        for div, city in CITIES.items():
            mask = (test_divipola == div).values
            if mask.sum() < 5:
                continue
            y_c   = y_te[mask]; pr_c = prob_te[mask]
            ini_c = y_ini_te[mask] if y_ini_te is not None else None
            m_c   = full_metrics(y_c, (pr_c >= best_thr).astype(int), ini_c, y_score=pr_c)
            log_full_metrics(m_c, prefix=f"test_{div}")
            print_metrics(m_c, f"{city} ({div})")

        os.makedirs(MODEL_DIR, exist_ok=True)
        with open(model_file, "wb") as fh:
            pickle.dump({"model": model, "features": feats,
                         "best_threshold": best_thr, "horizonte": H}, fh)
        canonical = os.path.join(MODEL_DIR, "gam_clasico.pkl")
        with open(canonical, "wb") as fh:
            pickle.dump({"model": model, "features": feats,
                         "best_threshold": best_thr, "horizonte": H}, fh)
        mlflow.log_artifact(model_file, artifact_path="model")

        print(f"\nVal  AUROC: {val_auroc:.4f}  AP: {val_ap:.4f}")
        print(f"Test AUROC: {te_auroc:.4f}  AP: {te_ap:.4f}")
        print(f"Umbral optimo: {best_thr:.2f}")
        print(f"Modelo guardado: {model_file}")


if __name__ == "__main__":
    main()
