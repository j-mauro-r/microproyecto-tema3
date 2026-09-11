"""
Registra los modelos entrenados en el servidor MLflow remoto y designa champions.

Prerequisito:
  $env:MLFLOW_TRACKING_URI = "http://<ec2-host>:<puerto>"
  python scripts/register_models_remote.py

El script crea un run por modelo en el experimento 'sat-dengue',
sube el pkl calibrado como artefacto, registra el modelo en el Model Registry
y asigna el alias 'champion' al modelo ganador de cada horizonte.

Champion designado: XGBoost calibrado (mejor AUROC en test 2024-2025).
  T+1: AUROC=0.900  AP=0.882  F1=0.792  Brier(cal)=0.0947
  T+2: AUROC=0.871  AP=0.840  F1=0.758  Brier(cal)=0.1129
"""
import os
import pickle
import shutil
import sys
import tempfile

import mlflow
import mlflow.pyfunc
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, roc_auc_score

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import ANIO_FIN_TRAIN, EXPERIMENT, full_metrics, make_t2_target

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR = os.path.join(ROOT, "model")

TARGET    = "objetivo"
TRAIN_END = ANIO_FIN_TRAIN

CITIES = {"68001": "Bucaramanga", "76001": "Cali"}

MODELS = [
    # (pkl_name,            registered_name,            horizonte, is_champion)
    ("xgb_clasico_calibrated",  "dengue-xgb-clasico-T1", 1, True),
    ("xgb_clasico_T2_calibrated", "dengue-xgb-clasico-T2", 2, True),
    ("lgbm_clasico_calibrated", "dengue-lgbm-clasico-T1", 1, False),
]


def load_data():
    df = pd.read_parquet(DATA_PATH)
    df = df[df[TARGET].notna()].copy()
    return df


def evaluate(pkg, df, horizonte):
    """Run evaluation and return metrics dict."""
    if horizonte == 2:
        df_h, target_col = make_t2_target(df, TARGET)
    else:
        df_h, target_col = df, TARGET

    test = df_h[df_h["anio"] > TRAIN_END].copy()
    val  = df_h[(df_h["anio"] >= TRAIN_END - 1) & (df_h["anio"] <= TRAIN_END)].copy()

    model      = pkg["model"]
    calibrator = pkg.get("calibrator")
    feats      = pkg["features"]
    thr        = pkg["best_threshold"]

    def predict(X):
        p = model.predict_proba(X[feats].fillna(0))[:, 1]
        return calibrator.transform(p) if calibrator else p

    p_val = predict(val); y_val = val[target_col].astype(int).values
    p_te  = predict(test); y_te  = test[target_col].astype(int).values
    y_ini = test["es_inicio"].values if "es_inicio" in test.columns else None

    pred_te = (p_te >= thr).astype(int)

    metrics = {
        "val_auroc":       float(roc_auc_score(y_val, p_val)),
        "val_ap":          float(average_precision_score(y_val, p_val)),
        "val_brier":       float(brier_score_loss(y_val, p_val)),
        "test_auroc":      float(roc_auc_score(y_te, p_te)),
        "test_ap":         float(average_precision_score(y_te, p_te)),
        "test_f1":         float(f1_score(y_te, pred_te, zero_division=0)),
        "test_brier":      float(brier_score_loss(y_te, p_te)),
        "best_threshold":  thr,
        "brier_before_cal": pkg.get("brier_before", float("nan")),
        "brier_after_cal":  pkg.get("brier_after",  float("nan")),
    }

    m_global = full_metrics(y_te, pred_te, y_ini, y_score=p_te)
    metrics.update({f"nacional_{k}": float(v) for k, v in m_global.items() if isinstance(v, (int, float)) and v == v})

    # Sin prefijo van las dos ciudades: es el alcance del producto y la columna
    # que se compara contra los baselines.
    mask_ciudades = test["divipola"].astype(str).isin(CITIES).values
    m_prod = full_metrics(y_te[mask_ciudades], pred_te[mask_ciudades],
                          y_ini[mask_ciudades] if y_ini is not None else None,
                          y_score=p_te[mask_ciudades])
    metrics.update({k: float(v) for k, v in m_prod.items() if isinstance(v, (int, float)) and v == v})

    for div, city in CITIES.items():
        mask = (test["divipola"].astype(str) == div).values
        if mask.sum() < 5:
            continue
        m_c = full_metrics(y_te[mask], pred_te[mask],
                           y_ini[mask] if y_ini is not None else None,
                           y_score=p_te[mask])
        metrics.update({f"{div}_{k}": float(v) for k, v in m_c.items() if isinstance(v, (int, float)) and v == v})

    return metrics


def main():
    uri = os.environ.get("MLFLOW_TRACKING_URI", "")
    if not uri:
        print("ERROR: MLFLOW_TRACKING_URI no configurado.")
        print("  Ejemplo: $env:MLFLOW_TRACKING_URI = 'http://<ec2-host>:5000'")
        sys.exit(1)

    print(f"Conectando a MLflow en: {uri}")
    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment(EXPERIMENT)
    client = mlflow.tracking.MlflowClient()

    df = load_data()

    for pkl_name, reg_name, horizonte, is_champion in MODELS:
        pkl_path = os.path.join(MODEL_DIR, f"{pkl_name}.pkl")
        if not os.path.exists(pkl_path):
            print(f"  {pkl_name}: no encontrado — omitido.")
            continue

        with open(pkl_path, "rb") as fh:
            pkg = pickle.load(fh)

        print(f"\n{'='*60}")
        print(f"Registrando: {reg_name}  (horizonte T+{horizonte})")

        metrics = evaluate(pkg, df, horizonte)

        run_name = f"{reg_name}-remote-register"
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.log_params({
                "horizonte":      horizonte,
                "conjunto":       "prueba",
                "alcance":        "Bucaramanga, Cali",
                "serie_objetivo": "casos_clasico",
                "train_end":      TRAIN_END,
                "n_variables":    len(pkg["features"]),
                "features":       str(pkg["features"]),
                "calibrated":     pkg.get("calibrated", False),
                "calib_method":   pkg.get("method", "none"),
                "output_type":    "probability",
                "champion":       is_champion,
            })
            mlflow.log_metrics(metrics)

            # Upload calibrated pkl as artifact
            with tempfile.TemporaryDirectory() as tmp:
                tmp_pkl = os.path.join(tmp, f"{pkl_name}.pkl")
                shutil.copy(pkl_path, tmp_pkl)
                mlflow.log_artifact(tmp_pkl, artifact_path="calibrated_model")

            run_id = run.info.run_id
            print(f"  run_id: {run_id}")
            print(f"  test_auroc={metrics['test_auroc']:.4f}  "
                  f"test_ap={metrics['test_ap']:.4f}  "
                  f"test_f1={metrics['test_f1']:.3f}  "
                  f"brier_cal={metrics['test_brier']:.4f}")

        # Register model in registry
        artifact_uri = f"runs:/{run_id}/calibrated_model"
        mv = mlflow.register_model(artifact_uri, reg_name)
        print(f"  Registrado: {reg_name} v{mv.version}")

        # Set champion alias
        if is_champion:
            client.set_registered_model_alias(reg_name, "champion", mv.version)
            print(f"  Alias 'champion' -> v{mv.version}")

    print("\nListo. Champions registrados:")
    for _, reg_name, h, is_champ in MODELS:
        if is_champ:
            print(f"  T+{h}: models:/{reg_name}@champion")

    print("\nPara cargar en FastAPI:")
    print("  import mlflow.pyfunc, pickle")
    print("  # Option A (pkl directo):")
    print("  pkg = pickle.load(open('model/xgb_clasico_calibrated.pkl','rb'))")
    print("  # Option B (MLflow registry):")
    print("  # mlflow.pyfunc.load_model('models:/dengue-xgb-clasico-T1@champion')")


if __name__ == "__main__":
    main()
