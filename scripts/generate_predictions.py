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

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from sklearn.metrics import f1_score

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
    if horizonte == 1:
        cal_path = os.path.join(MODEL_DIR, "xgb_clasico_calibrated.pkl")
        if os.path.exists(cal_path):
            with open(cal_path, "rb") as fh:
                pkg = pickle.load(fh)
            return pkg["model"], pkg["calibrator"], pkg["features"], pkg["best_threshold"], "xgb-calibrated-T1", True
    raw_path = os.path.join(MODEL_DIR, f"xgb_clasico_T{horizonte}.pkl")
    if not os.path.exists(raw_path):
        return None, None, None, None, None, False
    with open(raw_path, "rb") as fh:
        model = pickle.load(fh)
    return model, None, list(model.feature_names_in_), None, f"xgb-T{horizonte}", False


def best_threshold_from_val(model, feats, df):
    val = df[(df["anio"] >= TRAIN_END - 1) & (df["anio"] <= TRAIN_END)].copy()
    X_val = val[feats].fillna(0)
    y_val = val[TARGET].astype(int).values
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

        # T+2 needs target shifted by 2; approximate by using objetivo lookahead from df
        if horizonte == 2:
            # Build T+2 label: brote at t+2 = objetivo of row 2 months forward per municipio
            tc2_map = (
                df[["divipola", "anio", "mes", TARGET]]
                .copy()
                .rename(columns={TARGET: "objetivo_t2"})
            )
            # Shift 2 months forward: match current (div, anio, mes) to future (div, anio+2m, mes+2m)
            def add_months(row, n):
                d = date(int(row["anio"]), int(row["mes"]), 1) + relativedelta(months=n)
                return d.year, d.month
            test_cities = test_cities.copy()
            future_keys = test_cities.apply(
                lambda r: add_months(r, 2), axis=1, result_type="expand"
            ).rename(columns={0: "f_anio", 1: "f_mes"})
            test_cities = pd.concat([test_cities.reset_index(drop=True), future_keys], axis=1)
            test_cities = test_cities.merge(
                tc2_map[["divipola", "anio", "mes", "objetivo_t2"]],
                left_on=["divipola", "f_anio", "f_mes"],
                right_on=["divipola", "anio", "mes"],
                how="left", suffixes=("", "_fwd"),
            )
            target_col_h = "objetivo_t2"
        else:
            target_col_h = TARGET

        # Compute threshold from val if not available
        if thr is None:
            thr = best_threshold_from_val(model, feats, df)

        X_cities = test_cities[feats].fillna(0)
        probs_raw = model.predict_proba(X_cities)[:, 1]
        probs = calibrator.transform(probs_raw) if calibrator is not None else probs_raw

        for i, (_, row) in enumerate(test_cities.iterrows()):
            div    = str(int(row["divipola"]))
            anio   = int(row["anio"])
            mes    = int(row["mes"])
            ref_month    = f"{anio}-{mes:02d}"
            target_date  = date(anio, mes, 1) + relativedelta(months=horizonte)
            target_month = target_date.strftime("%Y-%m")

            prob  = float(probs[i])
            label = "EXCESO" if prob >= thr else "NO_EXCESO"
            obs_val = row.get(target_col_h)
            observed_label = ("EXCESO" if int(obs_val) == 1 else "NO_EXCESO") if pd.notna(obs_val) else None

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
