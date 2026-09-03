"""Utilidades de evaluacion compartidas entre scripts de entrenamiento SAT-Dengue.
Delega en src/evaluation/metrics.py para que los nombres de metrica coincidan
con los baselines y se puedan comparar en una sola tabla de MLflow.
"""
import os
import sys

import numpy as np
import mlflow
from sklearn.linear_model import LogisticRegression

# Importar funciones canonicas de metricas desde src/evaluation/metrics.py
_eval_dir = os.path.join(os.path.dirname(__file__), "..", "src", "evaluation")
if _eval_dir not in sys.path:
    sys.path.insert(0, _eval_dir)
from metrics import metricas_alerta, inicios_vs_continuaciones  # noqa: F401  (re-exportadas)


class PlattCalibrator:
    """Platt scaling via logistic regression. Expone .transform() para reemplazar IsotonicRegression."""
    def __init__(self):
        self._lr = LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000)

    def fit(self, probs, labels):
        self._lr.fit(np.array(probs).reshape(-1, 1), labels)
        return self

    def transform(self, probs):
        return self._lr.predict_proba(np.array(probs).reshape(-1, 1))[:, 1]


def full_metrics(y_true, y_pred_bin, y_ini=None, y_score=None):
    """Wrapper sobre metricas_alerta + inicios_vs_continuaciones de src/evaluation/metrics.py.
    Devuelve un dict con los mismos nombres de campo que los baselines para comparar en MLflow.
    """
    m = metricas_alerta(y_true, y_pred_bin, y_score)
    if y_ini is not None:
        m.update(inicios_vs_continuaciones(y_true, y_pred_bin, y_ini))
    return m


def log_full_metrics(m, prefix="test"):
    """Registra metricas en el run activo de MLflow con prefijo dado."""
    loggable = {k: v for k, v in m.items() if isinstance(v, (int, float)) and v == v}
    mlflow.log_metrics({f"{prefix}_{k}": float(v) for k, v in loggable.items()})


def print_metrics(m, label="Test"):
    print(f"  {label}: sensibilidad={m['sensibilidad']:.3f} "
          f"prec={m['precision']:.3f} F1={m['f1']:.3f} "
          f"FAR={m['tasa_falsas_alarmas']:.3f}", end="")
    if "inicios" in m:
        print(f" | inicios {m['inicios_detectados']}/{m['inicios']}")
    else:
        print()


def make_t2_target(df, target_col="brote"):
    """Crea target T+2 desplazando brote un mes hacia adelante por municipio.
    Elimina filas donde el target futuro no esta disponible (ultimo mes por divipola).
    """
    df = df.copy()
    df["__target_t2"] = (
        df.sort_values(["divipola", "anio", "mes"])
          .groupby("divipola")[target_col]
          .shift(-1)
    )
    df = df.dropna(subset=["__target_t2"])
    df["__target_t2"] = df["__target_t2"].astype(int)
    return df, "__target_t2"
