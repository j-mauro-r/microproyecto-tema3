"""
Metricas del sistema de alerta.

Todos los modelos se reportan con estas funciones para que la tabla
comparativa de la entrega compare lo mismo.

La exactitud se calcula y se devuelve, pero no sirve como criterio. En los
folds de validacion los meses por encima del canal son alrededor del 14%, asi
que un modelo que nunca alerta acierta el 86% sin detectar un solo brote. Las
metricas de decision son sensibilidad, precision, tasa de falsas alarmas y
PR-AUC.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ORDEN_COLUMNAS = [
    "n", "brotes_reales", "alertas_emitidas",
    "sensibilidad", "precision", "f1", "especificidad", "tasa_falsas_alarmas",
    "pr_auc", "exactitud", "tasa_base", "vp", "fp", "vn", "fn",
]


def _a_binario(y, nombre: str) -> np.ndarray:
    arr = np.asarray(y)
    if arr.ndim != 1:
        arr = arr.ravel()
    if pd.isna(arr).any():
        raise ValueError(f"{nombre} tiene valores nulos")
    arr = arr.astype(int)
    extra = set(np.unique(arr)) - {0, 1}
    if extra:
        raise ValueError(f"{nombre} tiene valores {sorted(extra)}, se esperaba 0 y 1")
    return arr


def promedio_precision(y_real, y_score) -> float:
    """
    Area bajo la curva precision-recall.

    Misma definicion que sklearn.metrics.average_precision_score: suma de la
    precision en cada punto de corte ponderada por el incremento del recall,
    sin interpolacion.
    """
    y_real = _a_binario(y_real, "y_real")
    y_score = np.asarray(y_score, dtype=float)
    if len(y_real) != len(y_score):
        raise ValueError("y_real y y_score tienen distinta longitud")

    positivos = int(y_real.sum())
    if positivos == 0:
        return float("nan")

    orden = np.argsort(-y_score, kind="mergesort")
    y, s = y_real[orden], y_score[orden]
    vp = np.cumsum(y)
    fp = np.cumsum(1 - y)

    # Dos observaciones con el mismo score no se pueden separar, asi que solo
    # cuenta el ultimo indice de cada valor distinto.
    cortes = np.r_[np.nonzero(np.diff(s))[0], len(s) - 1]
    vp, fp = vp[cortes], fp[cortes]

    precision = vp / (vp + fp)
    recall = vp / positivos
    return float(np.sum(np.diff(np.r_[0.0, recall]) * precision))


def metricas_alerta(y_real, y_pred, y_score=None) -> dict:
    """
    y_real  : 0/1, si el mes fue brote
    y_pred  : 0/1, si el modelo alerto
    y_score : puntaje continuo. Sin el no hay pr_auc.
    """
    y_real = _a_binario(y_real, "y_real")
    y_pred = _a_binario(y_pred, "y_pred")
    if len(y_real) != len(y_pred):
        raise ValueError(
            f"y_real tiene {len(y_real)} filas y y_pred tiene {len(y_pred)}"
        )

    vp = int(np.sum((y_real == 1) & (y_pred == 1)))
    fp = int(np.sum((y_real == 0) & (y_pred == 1)))
    vn = int(np.sum((y_real == 0) & (y_pred == 0)))
    fn = int(np.sum((y_real == 1) & (y_pred == 0)))

    def div(a, b):
        return float(a / b) if b else float("nan")

    sensibilidad = div(vp, vp + fn)
    precision = div(vp, vp + fp)
    if (vp + fn) and (vp + fp) and (precision + sensibilidad):
        f1 = 2 * precision * sensibilidad / (precision + sensibilidad)
    elif (vp + fn) or (vp + fp):
        f1 = 0.0
    else:
        f1 = float("nan")

    return {
        "n": len(y_real),
        "brotes_reales": vp + fn,
        "alertas_emitidas": vp + fp,
        "sensibilidad": sensibilidad,
        "precision": precision,
        "f1": f1,
        "especificidad": div(vn, vn + fp),
        "tasa_falsas_alarmas": div(fp, fp + vn),
        "pr_auc": promedio_precision(y_real, y_score) if y_score is not None else float("nan"),
        "exactitud": div(vp + vn, len(y_real)),
        "tasa_base": div(vp + fn, len(y_real)),
        "vp": vp, "fp": fp, "vn": vn, "fn": fn,
    }


def tabla_comparativa(resultados: dict[str, dict], decimales: int = 3) -> pd.DataFrame:
    """resultados: {nombre del modelo: dict devuelto por metricas_alerta}"""
    tabla = pd.DataFrame(resultados).T
    tabla = tabla[[c for c in ORDEN_COLUMNAS if c in tabla.columns]]
    enteras = {"n", "brotes_reales", "alertas_emitidas", "vp", "fp", "vn", "fn"}
    for c in tabla.columns:
        tabla[c] = tabla[c].astype(int) if c in enteras else tabla[c].astype(float).round(decimales)
    return tabla


def inicios_vs_continuaciones(y_real, y_pred, es_inicio) -> dict:
    """
    Separa la deteccion de inicios de brote de la de continuaciones.

    Un inicio es un mes en brote cuyo mes anterior no lo estaba. Es lo unico
    que puede aportar un sistema de alerta temprana: cuando el brote ya lleva
    meses, la secretaria de salud ya lo sabe. Un baseline de persistencia luce
    bien en el agregado porque acierta las continuaciones, pero por
    construccion no puede detectar un solo inicio.

    Se devuelve como conteo. Los inicios son pocos y una proporcion sobre tres
    casos no significa nada.
    """
    y_real = _a_binario(y_real, "y_real")
    y_pred = _a_binario(y_pred, "y_pred")
    es_inicio = _a_binario(es_inicio, "es_inicio")
    if not len(y_real) == len(y_pred) == len(es_inicio):
        raise ValueError("y_real, y_pred y es_inicio tienen distinta longitud")

    inicio = (y_real == 1) & (es_inicio == 1)
    continua = (y_real == 1) & (es_inicio == 0)
    return {
        "inicios": int(inicio.sum()),
        "inicios_detectados": int((inicio & (y_pred == 1)).sum()),
        "continuaciones": int(continua.sum()),
        "continuaciones_detectadas": int((continua & (y_pred == 1)).sum()),
    }


def tabla_inicios(resultados: dict[str, dict]) -> pd.DataFrame:
    """resultados: {nombre del modelo: dict devuelto por inicios_vs_continuaciones}"""
    tabla = pd.DataFrame(resultados).T
    with np.errstate(invalid="ignore", divide="ignore"):
        tabla["sens_inicios"] = (tabla["inicios_detectados"] / tabla["inicios"]).round(3)
        tabla["sens_continuaciones"] = (
            tabla["continuaciones_detectadas"] / tabla["continuaciones"]
        ).round(3)
    return tabla


def metricas_por_grupo(
    df: pd.DataFrame,
    col_grupo: str,
    col_real: str,
    col_pred: str,
    col_score: str | None = None,
) -> pd.DataFrame:
    """
    Metricas desglosadas por municipio.

    Los dos municipios tienen dinamicas distintas y no aportan lo mismo: en los
    folds de validacion casi todos los brotes son de Cali. El promedio de los
    dos puede esconder que el modelo sirve en uno y no en el otro.
    """
    filas = {
        clave: metricas_alerta(g[col_real], g[col_pred], g[col_score] if col_score else None)
        for clave, g in df.groupby(col_grupo, observed=True)
    }
    return tabla_comparativa(filas)
