"""
Genera valores SHAP locales para XGBoost T+1 sobre el test set de Bucaramanga y Cali.
El API contract (seccion 9.9) exige scope='local': los valores deben corresponder a
inferencias individuales, no a importancias globales.

Salidas:
  model/shap_local_T1.parquet  - valores SHAP por fila (divipola, anio, mes) — sirve al API
  reports/shap_bga_T1.png      - bar chart top-15 para Bucaramanga
  reports/shap_cali_T1.png     - bar chart top-15 para Cali
"""
import os
import pickle

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR = os.path.join(ROOT, "model")
REPORT_DIR = os.path.join(ROOT, "reports")

TARGET    = "objetivo"
TRAIN_END = 2023
CITIES    = {"68001": "Bucaramanga", "76001": "Cali"}
TOP_N     = 15


def main():
    df   = pd.read_parquet(DATA_PATH)
    df   = df[df[TARGET].notna()].copy()
    test = df[df["anio"] > TRAIN_END].copy()

    with open(os.path.join(MODEL_DIR, "xgb_clasico_T1.pkl"), "rb") as fh:
        model = pickle.load(fh)

    feats  = list(model.feature_names_in_)
    X_test = test[feats].fillna(0)

    print(f"Calculando SHAP TreeExplainer sobre {len(X_test):,} filas del test set...")
    explainer   = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test)  # shape: (n, n_feats)
    expected_val = float(explainer.expected_value)

    # Build parquet indexed by (divipola, anio, mes)
    shap_df = pd.DataFrame(shap_values, columns=[f"shap_{c}" for c in feats])
    shap_df["divipola"]    = test["divipola"].values
    shap_df["anio"]        = test["anio"].values
    shap_df["mes"]         = test["mes"].values
    shap_df["y_true"]      = test[TARGET].values
    shap_df["expected_val"] = expected_val

    out_parquet = os.path.join(MODEL_DIR, "shap_local_T1.parquet")
    shap_df.to_parquet(out_parquet, index=False)
    print(f"SHAP parquet guardado: {out_parquet}  ({len(shap_df):,} filas)")

    os.makedirs(REPORT_DIR, exist_ok=True)

    # City-level bar charts (mean |SHAP| = global signal PER city)
    test_arr = test.reset_index(drop=True)
    for div, city in CITIES.items():
        mask = (test_arr["divipola"].astype(str) == div).values
        n    = mask.sum()
        if n < 3:
            print(f"{city}: insuficientes observaciones ({n})")
            continue

        sv         = shap_values[mask]
        mean_abs   = np.abs(sv).mean(axis=0)
        top_idx    = np.argsort(mean_abs)[::-1][:TOP_N]
        top_feats  = [feats[i] for i in top_idx]
        top_vals   = mean_abs[top_idx]

        fig, ax = plt.subplots(figsize=(10, 6))
        colors  = ["#e74c3c" if v > 0 else "#3498db" for v in sv[:, top_idx].mean(axis=0)]
        ax.barh(range(TOP_N), top_vals[::-1], color=colors[::-1])
        ax.set_yticks(range(TOP_N))
        ax.set_yticklabels(top_feats[::-1], fontsize=9)
        ax.set_xlabel("Mean |SHAP value|  (contribucion local promedio)")
        ax.set_title(f"SHAP local — {city} ({div}) | XGBoost T+1 | test n={n}")
        ax.axvline(0, color="black", linewidth=0.5)
        plt.tight_layout()

        out_png = os.path.join(REPORT_DIR, f"shap_local_{div}_T1.png")
        plt.savefig(out_png, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  {city}: top feature = {top_feats[0]}  (|SHAP|={top_vals[0]:.4f})")
        print(f"  PNG: {out_png}")

    print("\nListo. El parquet shap_local_T1.parquet permite al API devolver")
    print("explanation.method='shap', scope='local' con top_features por inferencia.")


if __name__ == "__main__":
    main()
