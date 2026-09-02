"""Utilidades de evaluacion compartidas entre scripts de entrenamiento SAT-Dengue.
Calcula el set de metricas del contrato de API v1.1.0.
"""
import numpy as np
import mlflow


def full_metrics(y_true, y_pred_bin, y_ini=None):
    """Calcula recall, precision, F1, false_alarm_rate y deteccion de inicios."""
    y_true = np.asarray(y_true, dtype=int)
    y_pred_bin = np.asarray(y_pred_bin, dtype=int)

    tp = int(((y_pred_bin == 1) & (y_true == 1)).sum())
    fp = int(((y_pred_bin == 1) & (y_true == 0)).sum())
    fn = int(((y_pred_bin == 0) & (y_true == 1)).sum())
    tn = int(((y_pred_bin == 0) & (y_true == 0)).sum())

    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = 2 * recall * precision / (recall + precision) if (recall + precision) > 0 else 0.0
    false_alarm_rate = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    m = {
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "f1": round(f1, 4),
        "false_alarm_rate": round(false_alarm_rate, 4),
        "sample_size": int(len(y_true)),
    }

    if y_ini is not None:
        y_ini = np.asarray(y_ini, dtype=int)
        onsets = int(y_ini.sum())
        detected = int(((y_ini == 1) & (y_pred_bin == 1)).sum())
        m["outbreak_onsets"] = onsets
        m["outbreak_onsets_detected"] = detected
        m["onset_detect_rate"] = round(detected / onsets, 4) if onsets > 0 else 0.0

    return m


def log_full_metrics(m, prefix="test"):
    """Registra metricas en el run activo de MLflow con prefijo dado."""
    mlflow.log_metrics({f"{prefix}_{k}": float(v) for k, v in m.items()})


def print_metrics(m, label="Test"):
    print(f"  {label}: recall={m['recall']:.3f} prec={m['precision']:.3f} "
          f"F1={m['f1']:.3f} FAR={m['false_alarm_rate']:.3f}", end="")
    if "outbreak_onsets" in m:
        print(f" | inicios {m['outbreak_onsets_detected']}/{m['outbreak_onsets']}"
              f" ({m['onset_detect_rate']:.1%})")
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
