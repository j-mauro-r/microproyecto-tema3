"""
Post-hoc calibration via IsotonicRegression sobre el val set (anio 2022-2023).
El API contract (seccion 7.7) permite probability solo cuando es estadisticamente valida.

Input:  model/xgb_clasico.pkl, model/lgbm_clasico.pkl, model/xgb_clasico_T2.pkl
Output: model/xgb_clasico_calibrated.pkl, model/lgbm_clasico_calibrated.pkl,
        model/xgb_clasico_T2_calibrated.pkl
        Cada pkl es un dict: {model, calibrator, features, calibrated, method,
                              brier_before, brier_after, best_threshold}
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import make_t2_target

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, f1_score

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR = os.path.join(ROOT, "model")

PROHIBIDAS = {
    "divipola", "municipio", "departamento", "periodo",
    "anio", "mes", "casos_grave", "casos_clasico", "es_inicio",
    "objetivo", "casos_objetivo", "anio_objetivo", "mes_objetivo", "__target_t2",
}
TARGET    = "objetivo"
TRAIN_END = 2023


def compute_threshold(y_val, prob_val):
    thresholds = np.arange(0.05, 0.95, 0.01)
    f1s = [f1_score(y_val, (prob_val >= t).astype(int), zero_division=0) for t in thresholds]
    return float(thresholds[int(np.argmax(f1s))])


def main():
    df  = pd.read_parquet(DATA_PATH)
    df  = df[df[TARGET].notna()].copy()
    val = df[(df["anio"] >= TRAIN_END - 1) & (df["anio"] <= TRAIN_END)].copy()

    for name in ["xgb_clasico", "lgbm_clasico"]:
        path = os.path.join(MODEL_DIR, f"{name}.pkl")
        with open(path, "rb") as fh:
            raw = pickle.load(fh)

        feats = list(raw.feature_names_in_)
        X_val = val[feats].fillna(0)
        y_val = val[TARGET].astype(int).values

        prob_raw   = raw.predict_proba(X_val)[:, 1]
        brier_pre  = brier_score_loss(y_val, prob_raw)

        # sklearn 1.2+ removed cv='prefit'; use IsotonicRegression directly
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(prob_raw, y_val)

        prob_cal  = iso.transform(prob_raw)
        brier_post = brier_score_loss(y_val, prob_cal)
        best_thr   = compute_threshold(y_val, prob_cal)

        print(f"{name}: Brier {brier_pre:.4f} -> {brier_post:.4f}  |  umbral={best_thr:.2f}")

        out = {
            "model":        raw,   # base model for predict_proba
            "calibrator":   iso,   # isotonic regressor applied to raw prob
            "features":     feats,
            "calibrated":   True,
            "method":       "isotonic",
            "brier_before": brier_pre,
            "brier_after":  brier_post,
            "best_threshold": best_thr,
        }
        out_path = os.path.join(MODEL_DIR, f"{name}_calibrated.pkl")
        with open(out_path, "wb") as fh:
            pickle.dump(out, fh)
        print(f"  -> {out_path}")

    # ── T+2: XGBoost only ────────────────────────────────────────────────────
    df_t2   = pd.read_parquet(DATA_PATH)
    df_t2, t2_col = make_t2_target(df_t2, "objetivo")
    val_t2  = df_t2[(df_t2["anio"] >= TRAIN_END - 1) & (df_t2["anio"] <= TRAIN_END)].copy()

    t2_path = os.path.join(MODEL_DIR, "xgb_clasico_T2.pkl")
    if os.path.exists(t2_path):
        with open(t2_path, "rb") as fh:
            raw_t2 = pickle.load(fh)

        feats_t2 = list(raw_t2.feature_names_in_)
        X_val_t2 = val_t2[feats_t2].fillna(0)
        y_val_t2 = val_t2[t2_col].astype(int).values

        prob_raw_t2  = raw_t2.predict_proba(X_val_t2)[:, 1]
        brier_pre_t2 = brier_score_loss(y_val_t2, prob_raw_t2)

        iso_t2 = IsotonicRegression(out_of_bounds="clip")
        iso_t2.fit(prob_raw_t2, y_val_t2)

        prob_cal_t2  = iso_t2.transform(prob_raw_t2)
        brier_post_t2 = brier_score_loss(y_val_t2, prob_cal_t2)
        best_thr_t2   = compute_threshold(y_val_t2, prob_cal_t2)

        print(f"xgb_clasico_T2: Brier {brier_pre_t2:.4f} -> {brier_post_t2:.4f}  |  umbral={best_thr_t2:.2f}")

        out_t2 = {
            "model":        raw_t2,
            "calibrator":   iso_t2,
            "features":     feats_t2,
            "calibrated":   True,
            "method":       "isotonic",
            "brier_before": brier_pre_t2,
            "brier_after":  brier_post_t2,
            "best_threshold": best_thr_t2,
        }
        out_path_t2 = os.path.join(MODEL_DIR, "xgb_clasico_T2_calibrated.pkl")
        with open(out_path_t2, "wb") as fh:
            pickle.dump(out_t2, fh)
        print(f"  -> {out_path_t2}")
    else:
        print("xgb_clasico_T2.pkl no encontrado — omitido.")


if __name__ == "__main__":
    main()
