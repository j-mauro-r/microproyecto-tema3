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
from metrics import metricas_alerta, inicios_vs_continuaciones  # noqa: F401
from splits import ANIO_FIN_TRAIN  # noqa: F401  — TRAIN_END canónico = 2022

EXPERIMENT = "sat-dengue"


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
    Claves de inicios llevan prefijo ini_ para coincidir con el registro de baselines.
    """
    m = metricas_alerta(y_true, y_pred_bin, y_score)
    if y_ini is not None:
        ini = inicios_vs_continuaciones(y_true, y_pred_bin, y_ini)
        m.update({f"ini_{k}": v for k, v in ini.items()})
    return m


def log_full_metrics(m, prefix=None):
    """Registra metricas en el run activo de MLflow.
    Sin prefix: metricas globales sin prefijo (para coincidir con baselines en sat-dengue).
    Con prefix: metricas de ciudad con {divipola}_ como prefijo.
    """
    loggable = {k: v for k, v in m.items() if isinstance(v, (int, float)) and v == v}
    if prefix:
        mlflow.log_metrics({f"{prefix}_{k}": float(v) for k, v in loggable.items()})
    else:
        mlflow.log_metrics({k: float(v) for k, v in loggable.items()})


def print_metrics(m, label="Test"):
    print(f"  {label}: sensibilidad={m['sensibilidad']:.3f} "
          f"prec={m['precision']:.3f} F1={m['f1']:.3f} "
          f"FAR={m['tasa_falsas_alarmas']:.3f}", end="")
    if "ini_inicios" in m:
        print(f" | inicios {m['ini_inicios_detectados']}/{m['ini_inicios']}")
    else:
        print()


def make_t2_target(df, target_col="objetivo"):
    """
    Objetivo de T+2, corriendo un mes mas la etiqueta de T+1.

    es_inicio se recalcula porque la columna del panel marca el inicio a un mes:
    dejarla como esta deja la etiqueta y el indicador corridos entre si. Un
    inicio a dos meses es que t+2 este en brote y t+1 no, y t+1 es target_col.
    """
    df = df.copy()
    df["__target_t2"] = (
        df.sort_values(["divipola", "anio", "mes"])
          .groupby("divipola")[target_col]
          .shift(-1)
    )
    df = df.dropna(subset=["__target_t2"])
    df["__target_t2"] = df["__target_t2"].astype(int)
    df["es_inicio"] = (
        (df["__target_t2"] == 1) & (df[target_col].astype(int) == 0)
    ).astype(int)
    return df, "__target_t2"


CIUDADES = {"68001": "Bucaramanga", "76001": "Cali"}


def _sub(a, mask):
    return None if a is None else np.asarray(a)[mask]


def registrar_por_alcance(divipolas, y_true, y_pred, y_ini=None, y_score=None,
                          imprimir=True):
    """
    Registra las metricas en tres alcances con una convencion fija:

        sin prefijo    los dos municipios del alcance
        nacional_      todos los municipios del panel
        {divipola}_    cada municipio por separado

    Las que van sin prefijo son las que quedan en la misma columna de MLflow
    que los baselines, asi que tienen que significar lo mismo en todos los
    scripts. La tasa base nacional es 39% y la de las dos ciudades 60%.

    Devuelve el dict del alcance del producto.
    """
    divipolas = np.asarray(divipolas).astype(str)

    m_nac = full_metrics(y_true, y_pred, y_ini, y_score)
    log_full_metrics(m_nac, prefix="nacional")

    mask = np.isin(divipolas, list(CIUDADES))
    m_prod = full_metrics(_sub(y_true, mask), _sub(y_pred, mask),
                          _sub(y_ini, mask), _sub(y_score, mask))
    log_full_metrics(m_prod)

    if imprimir:
        print_metrics(m_nac, "Nacional")
        print_metrics(m_prod, "Bucaramanga + Cali")

    for div, ciudad in CIUDADES.items():
        m = divipolas == div
        if m.sum() < 5:
            continue
        m_c = full_metrics(_sub(y_true, m), _sub(y_pred, m),
                           _sub(y_ini, m), _sub(y_score, m))
        log_full_metrics(m_c, prefix=div)
        if imprimir:
            print_metrics(m_c, f"{ciudad} ({div})")

    return m_prod
