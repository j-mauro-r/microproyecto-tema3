"""
Registra los modelos pendientes en el servidor MLflow remoto:
  - LGBM T+2 calibrado
  - GAM T+1  (sin calibracion adicional — LogisticGAM produce probabilidades via link logistico)
  - GAM T+2  (sin calibracion adicional)

Prerequisito:
  $env:MLFLOW_TRACKING_URI = "http://<ec2-host>:<puerto>"
  python scripts/register_remaining_remote.py
"""
import os, pickle, shutil, sys, tempfile
import mlflow
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, roc_auc_score

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import full_metrics, make_t2_target

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR = os.path.join(ROOT, "model")

TARGET    = "objetivo"
TRAIN_END = 2023
EXPERIMENT = "dengue-brote-clasico"
CITIES = {"68001": "Bucaramanga", "76001": "Cali"}

# (pkl_name, registered_name, horizonte)
MODELS = [
    ("lgbm_clasico_T2_calibrated", "dengue-lgbm-clasico-T2", 2),
    ("gam_clasico",                "dengue-gam-clasico-T1",  1),
    ("gam_clasico_T2",             "dengue-gam-clasico-T2",  2),
]


def load_pkg(pkl_name):
    path = os.path.join(MODEL_DIR, f"{pkl_name}.pkl")
    with open(path, "rb") as fh:
        return pickle.load(fh)


def get_features(pkg):
    if isinstance(pkg, dict):
        return pkg["features"]
    return list(pkg.feature_names_in_)


def predict_proba(pkg, X_df, feats):
    """Handles calibrated dict, raw sklearn model, and GAM dict."""
    if isinstance(pkg, dict) and "calibrator" in pkg:
        raw  = pkg["model"].predict_proba(X_df[feats].fillna(0))[:, 1]
        return pkg["calibrator"].transform(raw)
    elif isinstance(pkg, dict) and "model" in pkg:
        # GAM: needs numpy array
        return pkg["model"].predict_proba(X_df[feats].fillna(0).values)
    else:
        return pkg.predict_proba(X_df[feats].fillna(0))[:, 1]


def get_threshold(pkg):
    if isinstance(pkg, dict):
        return pkg.get("best_threshold", 0.5)
    return 0.5


def evaluate(pkg, df, horizonte):
    if horizonte == 2:
        df_h, target_col = make_t2_target(df, TARGET)
    else:
        df_h, target_col = df.copy(), TARGET

    test = df_h[df_h["anio"] > TRAIN_END].copy()
    val  = df_h[(df_h["anio"] >= TRAIN_END - 1) & (df_h["anio"] <= TRAIN_END)].copy()

    feats = get_features(pkg)
    thr   = get_threshold(pkg)

    p_val = predict_proba(pkg, val, feats)
    p_te  = predict_proba(pkg, test, feats)
    y_val = val[target_col].astype(int).values
    y_te  = test[target_col].astype(int).values
    y_ini = test["es_inicio"].values if "es_inicio" in test.columns else None

    pred_te = (p_te >= thr).astype(int)

    metrics = {
        "val_auroc":  float(roc_auc_score(y_val, p_val)),
        "val_ap":     float(average_precision_score(y_val, p_val)),
        "val_brier":  float(brier_score_loss(y_val, p_val)),
        "test_auroc": float(roc_auc_score(y_te, p_te)),
        "test_ap":    float(average_precision_score(y_te, p_te)),
        "test_f1":    float(f1_score(y_te, pred_te, zero_division=0)),
        "test_brier": float(brier_score_loss(y_te, p_te)),
        "best_threshold": thr,
    }
    if isinstance(pkg, dict):
        metrics["brier_before_cal"] = pkg.get("brier_before", float("nan"))
        metrics["brier_after_cal"]  = pkg.get("brier_after",  float("nan"))

    m_global = full_metrics(y_te, pred_te, y_ini)
    metrics.update({f"test_{k}": float(v) for k, v in m_global.items()})

    for div, city in CITIES.items():
        mask = (test["divipola"].astype(str) == div).values
        if mask.sum() < 5: continue
        m_c = full_metrics(y_te[mask], pred_te[mask],
                           y_ini[mask] if y_ini is not None else None)
        metrics.update({f"test_{div}_{k}": float(v) for k, v in m_c.items()})

    return metrics


def main():
    uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    if not uri:
        print("ERROR: MLFLOW_TRACKING_URI no configurado.")
        sys.exit(1)

    print(f"Conectando a MLflow en: {uri}")
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(EXPERIMENT)

    df = pd.read_parquet(DATA_PATH)
    df = df[df[TARGET].notna()].copy()

    for pkl_name, reg_name, horizonte in MODELS:
        pkl_path = os.path.join(MODEL_DIR, f"{pkl_name}.pkl")
        if not os.path.exists(pkl_path):
            print(f"\n{pkl_name}: no encontrado — omitido.")
            continue

        pkg = load_pkg(pkl_name)
        print(f"\n{'='*55}")
        print(f"Registrando: {reg_name}  (T+{horizonte})")

        metrics  = evaluate(pkg, df, horizonte)
        is_cal   = isinstance(pkg, dict) and pkg.get("calibrated", False)
        pkg_type = "lgbm" if "lgbm" in pkl_name else "gam"

        run_name = f"{reg_name}-remote-register"
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.log_params({
                "horizonte":    horizonte,
                "train_end":    TRAIN_END,
                "n_features":   len(get_features(pkg)),
                "calibrated":   is_cal,
                "calib_method": pkg.get("method", "none") if isinstance(pkg, dict) else "none",
                "output_type":  "probability",
                "model_type":   pkg_type,
            })
            mlflow.log_metrics(metrics)

            with tempfile.TemporaryDirectory() as tmp:
                tmp_pkl = os.path.join(tmp, f"{pkl_name}.pkl")
                shutil.copy(pkl_path, tmp_pkl)
                mlflow.log_artifact(tmp_pkl, artifact_path="model_pkl")

            run_id = run.info.run_id
            print(f"  run_id: {run_id}")
            print(f"  test_auroc={metrics['test_auroc']:.4f}  "
                  f"test_f1={metrics['test_f1']:.3f}  "
                  f"brier={metrics['test_brier']:.4f}")

        mv = mlflow.register_model(f"runs:/{run_id}/model_pkl", reg_name)
        print(f"  Registrado: {reg_name} v{mv.version}")

    print("\nListo.")


if __name__ == "__main__":
    main()
