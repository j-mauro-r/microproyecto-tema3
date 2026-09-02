"""
Genera prediction_history.parquet segun contrato API BIOMAC seccion 10.
Para cada fila del test set (anio > 2023) en Bucaramanga y Cali, produce una
entrada por horizonte con: reference_month, horizon, target_month, divipola,
label, probability, risk_score, model_version, observed_label, probability_threshold.

Usa el modelo calibrado si existe, si no el raw T1/T2 pkl.
T+2 requiere haber entrenado con: python scripts/train_clasico_model.py --horizonte 2

Salida: data/processed/prediction_history.parquet
"""
import os
import pickle
from datetime import datetime, timezone, date

import sys
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from sklearn.metrics import f1_score

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import make_t2_target

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR = os.path.join(ROOT, "model")
OUT_PATH  = os.path.join(ROOT, "data", "processed", "prediction_history.parquet")

PROHIBIDAS = {
    "divipola", "municipio", "departamento", "periodo",
    "anio", "mes", "casos_grave", "casos_clasico", "es_inicio",
    "objetivo", "casos_objetivo", "anio_objetivo", "mes_objetivo", "__target_t2",
}
CITIES    = {"68001": "Bucaramanga", "76001": "Cali"}
TARGET    = "objetivo"
TRAIN_END = 2023
GENERATED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def feature_cols(df):
    return [c for c in df.columns if c not in PROHIBIDAS and pd.api.types.is_numeric_dtype(df[c])]


def load_model(horizonte):
    """Load calibrated model if available, else raw pkl.
    Returns (model, calibrator_or_None, features, threshold_or_None, version, is_calibrated).
    """
    cal_name = "xgb_clasico_calibrated.pkl" if horizonte == 1 else f"xgb_clasico_T{horizonte}_calibrated.pkl"
    cal_path = os.path.join(MODEL_DIR, cal_name)
    if os.path.exists(cal_path):
        with open(cal_path, "rb") as fh:
            pkg = pickle.load(fh)
        return pkg["model"], pkg["calibrator"], pkg["features"], pkg["best_threshold"], f"xgb-calibrated-T{horizonte}", True
    raw_path = os.path.join(MODEL_DIR, f"xgb_clasico_T{horizonte}.pkl")
    if not os.path.exists(raw_path):
        return None, None, None, None, None, False
    with open(raw_path, "rb") as fh:
        model = pickle.load(fh)
    return model, None, list(model.feature_names_in_), None, f"xgb-T{horizonte}", False


def best_threshold_from_val(model, feats, df, horizonte=1):
    if horizonte == 2:
        df, target_col = make_t2_target(df, TARGET)
    else:
        target_col = TARGET
    val = df[(df["anio"] >= TRAIN_END - 1) & (df["anio"] <= TRAIN_END)].copy()
    X_val = val[feats].fillna(0)
    y_val = val[target_col].astype(int).values
    prob_val = model.predict_proba(X_val)[:, 1]
    thrs = np.arange(0.05, 0.95, 0.01)
    f1s  = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thrs]
    return float(thrs[int(np.argmax(f1s))])


def main():
    df = pd.read_parquet(DATA_PATH)
    df = df[df[TARGET].notna()].copy()
    test = df[df["anio"] > TRAIN_END].copy()
    test_cities = test[test["divipola"].astype(str).isin(CITIES)].copy()

    records = []

    for horizonte in [1, 2]:
        model, calibrator, feats, thr, model_version, is_calibrated = load_model(horizonte)
        if model is None:
            print(f"T+{horizonte}: modelo no encontrado — omitido. "
                  f"Entrena con: python scripts/train_clasico_model.py --horizonte {horizonte}")
            continue

        # Build a lookup: (divipola_str, anio, mes) -> brote (actual state at that month)
        target_lookup = {
            (str(int(r["divipola"])), int(r["anio"]), int(r["mes"])): int(r["brote"])
            for _, r in df.iterrows()
            if pd.notna(r["brote"]) and pd.notna(r["divipola"])
        }

        # Compute threshold from val if not available
        if thr is None:
            thr = best_threshold_from_val(model, feats, df, horizonte)

        X_cities = test_cities[feats].fillna(0)
        probs_raw = model.predict_proba(X_cities)[:, 1]
        probs = calibrator.transform(probs_raw) if calibrator is not None else probs_raw

        tc_reset = test_cities.reset_index(drop=True)
        for i, row in tc_reset.iterrows():
            div    = str(int(row["divipola"]))
            anio   = int(row["anio"])
            mes    = int(row["mes"])
            ref_month    = f"{anio}-{mes:02d}"
            target_date  = date(anio, mes, 1) + relativedelta(months=horizonte)
            target_month = target_date.strftime("%Y-%m")

            prob  = float(probs[i])
            label = "EXCESO" if prob >= thr else "NO_EXCESO"
            obs_val = target_lookup.get((div, target_date.year, target_date.month))
            observed_label = ("EXCESO" if obs_val == 1 else "NO_EXCESO") if obs_val is not None else None

            records.append({
                "generated_at":         GENERATED_AT,
                "reference_month":      ref_month,
                "horizon":              f"T+{horizonte}",
                "target_month":         target_month,
                "divipola":             div,
                "city_name":            CITIES.get(div, div),
                "label":                label,
                "probability":          round(prob, 4),
                "risk_score":           round(prob, 4),
                "probability_threshold": round(thr, 2),
                "model_version":        model_version,
                "calibrated":           is_calibrated,
                "observed_label":       observed_label,
            })

        print(f"T+{horizonte}: {len([r for r in records if r['horizon'] == f'T+{horizonte}'])} filas")

    hist = pd.DataFrame(records)
    hist.to_parquet(OUT_PATH, index=False)
    print(f"\nGuardado: {OUT_PATH}  ({len(hist)} filas)")
    if len(hist):
        print(hist.groupby(["horizon", "city_name", "label"]).size().to_string())


if __name__ == "__main__":
    main()
