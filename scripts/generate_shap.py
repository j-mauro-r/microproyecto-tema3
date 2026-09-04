"""
Genera valores SHAP locales para XGBoost T+1 y T+2 sobre el test set de Bucaramanga y Cali.
El API contract (seccion 9.9) exige scope='local': los valores deben corresponder a
inferencias individuales, no a importancias globales.

Salidas por horizonte H in {1, 2}:
  model/shap_local_TH.parquet       - valores SHAP por fila (divipola, anio, mes) — sirve al API
  reports/shap_local_{div}_TH.png   - bar chart top-15 por ciudad
"""
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import ANIO_FIN_TRAIN, make_t2_target

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

ROOT       = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH  = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR  = os.path.join(ROOT, "model")
REPORT_DIR = os.path.join(ROOT, "reports")

TARGET    = "objetivo"
TRAIN_END = ANIO_FIN_TRAIN
CITIES    = {"68001": "Bucaramanga", "76001": "Cali"}
TOP_N     = 15


def run_horizon(horizonte, df_base):
    model_path = os.path.join(MODEL_DIR, f"xgb_clasico_T{horizonte}.pkl")
    if not os.path.exists(model_path):
        print(f"T+{horizonte}: {model_path} no encontrado — omitido.")
        return

    if horizonte == 2:
        df_h, target_col = make_t2_target(df_base, "objetivo")
    else:
        df_h = df_base.copy()
        target_col = TARGET

    test = df_h[df_h["anio"] > TRAIN_END].copy().reset_index(drop=True)

    with open(model_path, "rb") as fh:
        model = pickle.load(fh)

    feats  = list(model.feature_names_in_)
    X_test = test[feats].fillna(0)

    print(f"\nT+{horizonte}: SHAP TreeExplainer sobre {len(X_test):,} filas...")
    explainer    = shap.TreeExplainer(model)
    shap_values  = explainer.shap_values(X_test)
    expected_val = float(explainer.expected_value)

    shap_df = pd.DataFrame(shap_values, columns=[f"shap_{c}" for c in feats])
    shap_df["divipola"]     = test["divipola"].values
    shap_df["anio"]         = test["anio"].values
    shap_df["mes"]          = test["mes"].values
    shap_df["y_true"]       = test[target_col].values
    shap_df["expected_val"] = expected_val

    out_parquet = os.path.join(MODEL_DIR, f"shap_local_T{horizonte}.parquet")
    shap_df.to_parquet(out_parquet, index=False)
    print(f"  parquet: {out_parquet}  ({len(shap_df):,} filas)")

    os.makedirs(REPORT_DIR, exist_ok=True)

    for div, city in CITIES.items():
        mask = (test["divipola"].astype(str) == div).values
        n    = mask.sum()
        if n < 3:
            print(f"  {city}: insuficientes observaciones ({n})")
            continue

        sv        = shap_values[mask]
        mean_abs  = np.abs(sv).mean(axis=0)
        top_idx   = np.argsort(mean_abs)[::-1][:TOP_N]
        top_feats = [feats[i] for i in top_idx]
        top_vals  = mean_abs[top_idx]

        fig, ax = plt.subplots(figsize=(10, 6))
        colors  = ["#e74c3c" if v > 0 else "#3498db" for v in sv[:, top_idx].mean(axis=0)]
        ax.barh(range(TOP_N), top_vals[::-1], color=colors[::-1])
        ax.set_yticks(range(TOP_N))
        ax.set_yticklabels(top_feats[::-1], fontsize=9)
        ax.set_xlabel("Mean |SHAP value|  (contribucion local promedio)")
        ax.set_title(f"SHAP local — {city} ({div}) | XGBoost T+{horizonte} | test n={n}")
        ax.axvline(0, color="black", linewidth=0.5)
        plt.tight_layout()

        out_png = os.path.join(REPORT_DIR, f"shap_local_{div}_T{horizonte}.png")
        plt.savefig(out_png, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  {city}: top={top_feats[0]} (|SHAP|={top_vals[0]:.4f})  PNG: {out_png}")


def main():
    df_base = pd.read_parquet(DATA_PATH)
    df_base = df_base[df_base[TARGET].notna()].copy()

    for h in [1, 2]:
        run_horizon(h, df_base)

    print("\nListo. Los parquets shap_local_T*.parquet permiten al API devolver")
    print("explanation.method='shap', scope='local' con top_features por inferencia.")


if __name__ == "__main__":
    main()
