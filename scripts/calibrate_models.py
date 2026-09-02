"""
Post-hoc calibration via Platt scaling (LogisticRegression) sobre el val set (anio 2022-2023).
El API contract (seccion 7.7) permite probability solo cuando es estadisticamente valida.

Input:  model/xgb_clasico.pkl, model/lgbm_clasico.pkl,
        model/xgb_clasico_T2.pkl, model/lgbm_clasico_T2.pkl
Output: model/xgb_clasico_calibrated.pkl, model/lgbm_clasico_calibrated.pkl,
        model/xgb_clasico_T2_calibrated.pkl, model/lgbm_clasico_T2_calibrated.pkl
        Cada pkl es un dict: {model, calibrator, features, calibrated, method,
                              brier_before, brier_after, best_threshold}
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import make_t2_target, PlattCalibrator

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, f1_score

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR = os.path.join(ROOT, "model")

TARGET    = "objetivo"
TRAIN_END = 2023


def compute_threshold(y_val, prob_val):
    thresholds = np.arange(0.05, 0.95, 0.01)
    f1s = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thresholds]
    return float(thresholds[int(np.argmax(f1s))])


def calibrate_model(raw, X_val, y_val, out_path, model_name):
    prob_raw  = raw.predict_proba(X_val)[:, 1]
    brier_pre = brier_score_loss(y_val, prob_raw)

    cal = PlattCalibrator()
    cal.fit(prob_raw, y_val)

    prob_cal   = cal.transform(prob_raw)
    brier_post = brier_score_loss(y_val, prob_cal)
    best_thr   = compute_threshold(y_val, prob_cal)

    print(f"{model_name}: Brier {brier_pre:.4f} -> {brier_post:.4f}  |  umbral={best_thr:.2f}")

    out = {
        "model":          raw,
        "calibrator":     cal,
        "features":       list(raw.feature_names_in_),
        "calibrated":     True,
        "method":         "platt",
        "brier_before":   brier_pre,
        "brier_after":    brier_post,
        "best_threshold": best_thr,
    }
    with open(out_path, "wb") as fh:
        pickle.dump(out, fh)
    print(f"  -> {out_path}")


def main():
    df  = pd.read_parquet(DATA_PATH)
    df  = df[df[TARGET].notna()].copy()
    val = df[(df["anio"] >= TRAIN_END - 1) & (df["anio"] <= TRAIN_END)].copy()

    # T+1: XGBoost and LightGBM
    for name in ["xgb_clasico", "lgbm_clasico"]:
        path = os.path.join(MODEL_DIR, f"{name}.pkl")
        with open(path, "rb") as fh:
            raw = pickle.load(fh)
        feats = list(raw.feature_names_in_)
        X_val = val[feats].fillna(0)
        y_val = val[TARGET].astype(int).values
        calibrate_model(
            raw, X_val, y_val,
            os.path.join(MODEL_DIR, f"{name}_calibrated.pkl"),
            name,
        )

    # T+2: XGBoost and LightGBM
    df_t2, t2_col = make_t2_target(pd.read_parquet(DATA_PATH), "objetivo")
    val_t2 = df_t2[(df_t2["anio"] >= TRAIN_END - 1) & (df_t2["anio"] <= TRAIN_END)].copy()

    for name, pkl in [("xgb_clasico_T2", "xgb_clasico_T2"),
                      ("lgbm_clasico_T2", "lgbm_clasico_T2")]:
        pkl_path = os.path.join(MODEL_DIR, f"{pkl}.pkl")
        if not os.path.exists(pkl_path):
            print(f"{name}: no encontrado — omitido.")
            continue
        with open(pkl_path, "rb") as fh:
            raw = pickle.load(fh)
        feats   = list(raw.feature_names_in_)
        X_val   = val_t2[feats].fillna(0)
        y_val   = val_t2[t2_col].astype(int).values
        calibrate_model(
            raw, X_val, y_val,
            os.path.join(MODEL_DIR, f"{name}_calibrated.pkl"),
            name,
        )


if __name__ == "__main__":
    main()
