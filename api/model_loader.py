"""Carga el modelo XGBoost desde MLflow o desde un archivo local .pkl."""
import os
import json
import pickle
import mlflow.xgboost

FEATURE_COLS = (
    [f"grave_lag_{l}"   for l in [1, 2, 3, 4, 6]] +
    [f"clasico_lag_{l}" for l in [1, 2, 3, 4, 6]] +
    ["grave_roll3", "clasico_roll3"] +
    ["temp_mean_c", "temp_lag_1", "temp_lag_2", "temp_lag_3"] +
    ["rain_mm_day", "rain_lag_1", "rain_lag_2", "rain_lag_3"] +
    ["mes_sin", "mes_cos", "anio_epidemia", "ANO", "MES"] +
    ["es_endemico", "zona_canal_lag1", "p25", "p75", "sir_lag1"]
)  # 30 features mensuales

# Umbral optimo — se intenta leer del JSON generado por el entrenamiento
def _load_threshold():
    meta_path = os.getenv("MODEL_META_PATH", "model/model_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            return float(json.load(f).get("best_threshold", 0.5))
    return float(os.getenv("MODEL_THRESHOLD", "0.5"))

DEFAULT_THRESHOLD = _load_threshold()

_model = None


def load_model():
    global _model
    if _model is not None:
        return _model

    # 1. Intentar cargar desde MLflow
    mlflow_uri  = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5000")
    mlflow_run  = os.getenv("MLFLOW_RUN_ID", "")
    local_path  = os.getenv("MODEL_LOCAL_PATH", "model/xgb_model.pkl")

    if mlflow_run:
        try:
            mlflow.set_tracking_uri(mlflow_uri)
            _model = mlflow.xgboost.load_model(f"runs:/{mlflow_run}/model")
            print(f"Modelo cargado desde MLflow run {mlflow_run}")
            return _model
        except Exception as e:
            print(f"MLflow load failed: {e}. Intentando archivo local.")

    # 2. Fallback: archivo local
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            _model = pickle.load(f)
        print(f"Modelo cargado desde {local_path}")
        return _model

    raise RuntimeError(
        "No se encontro modelo. Defina MLFLOW_RUN_ID o MODEL_LOCAL_PATH."
    )
