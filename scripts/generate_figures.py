"""
Genera figuras para el reporte de Entrega 2.
Salida: data/figures/report_*.png
Uso: python scripts/generate_figures.py
"""
import json
import os
import pickle
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve, auc, precision_recall_curve, average_precision_score

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
FIG_DIR   = os.path.join(ROOT, "data", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

DIVIPOLAS = {"68001": "Bucaramanga", "76001": "Cali"}
CLR_CITY  = {"68001": "#1654A2", "76001": "#BE1D2B"}
ZONA_CLR  = {0: "#22A24A", 1: "#E99A00", 2: "#E83545"}
ZONA_LBL  = {0: "Normal", 1: "Alerta", 2: "Exceso"}
sys.path.insert(0, os.path.dirname(__file__))
from model_utils import ANIO_FIN_TRAIN
TRAIN_END = ANIO_FIN_TRAIN  # 2022, importado de src/evaluation/splits.py
PROHIBIDAS = {
    "divipola", "municipio", "departamento", "periodo",
    "anio", "mes", "casos_grave", "casos_clasico", "brote", "es_inicio",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})


def load_data():
    df = pd.read_parquet(DATA_PATH)
    df["divipola"] = df["divipola"].astype(str).str.zfill(5)
    df = df[df["divipola"].isin(DIVIPOLAS)].copy()
    df["fecha"] = pd.to_datetime({"year": df["anio"], "month": df["mes"], "day": 1})
    df = df.sort_values(["divipola", "fecha"]).reset_index(drop=True)
    return df


def load_models(df):
    feats = [c for c in df.columns
             if c not in PROHIBIDAS
             and pd.api.types.is_numeric_dtype(df[c])
             and c != "fecha"]
    with open(os.path.join(ROOT, "model", "xgb_clasico.pkl"), "rb") as f:
        xgb_model = pickle.load(f)
    with open(os.path.join(ROOT, "model", "xgb_clasico_meta.json")) as f:
        meta = json.load(f)

    train = df[df["anio"] <= TRAIN_END]
    test  = df[df["anio"] > TRAIN_END]

    X_te = test[feats].fillna(0)
    y_te = test["brote"]

    xgb_prob_te = xgb_model.predict_proba(X_te)[:, 1]
    return feats, xgb_model, meta, X_te, y_te, xgb_prob_te


# ── Fig 1: Canal endemico por ciudad ────────────────────────────────────────
def fig_canal_endemico(df):
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=False)
    for ax, (div, city) in zip(axes, DIVIPOLAS.items()):
        cdf = df[df["divipola"] == div].copy()
        cdf["zona"] = cdf.apply(
            lambda r: 2 if r.brote == 1 else (1 if r.casos_clasico > r.p25 and r.p25 > 0 else 0),
            axis=1,
        )
        ax.fill_between(cdf["fecha"], 0, cdf["p25"],
                        color="#22A24A", alpha=0.08, label="Zona normal (< P25)")
        ax.fill_between(cdf["fecha"], cdf["p25"], cdf["p75"],
                        color="#E99A00", alpha=0.12, label="Zona alerta (P25-P75)")
        ax.fill_between(cdf["fecha"], cdf["p75"], cdf["p75"].max() * 1.15,
                        color="#E83545", alpha=0.06, label="Zona exceso (> P75)")
        ax.plot(cdf["fecha"], cdf["p25"], color="#22A24A", lw=1.2, ls="--", alpha=0.7)
        ax.plot(cdf["fecha"], cdf["p75"], color="#E99A00", lw=1.5, ls="--", alpha=0.8)

        bar_colors = [ZONA_CLR[z] for z in cdf["zona"]]
        ax.bar(cdf["fecha"], cdf["casos_clasico"], color=bar_colors,
               alpha=0.75, width=25, label="Casos dengue total/mes")

        ax.set_title(f"{city} — Dengue total mensual y canal endémico (2007-2025)",
                     fontsize=12, fontweight="bold")
        ax.set_ylabel("Casos/mes")
        ax.set_xlim(cdf["fecha"].min(), cdf["fecha"].max())

        # Leyenda zona
        patches = [mpatches.Patch(color=ZONA_CLR[i], alpha=0.7, label=ZONA_LBL[i])
                   for i in [0, 1, 2]]
        ax.legend(handles=patches, loc="upper left", fontsize=8)

    fig.tight_layout(pad=2)
    out = os.path.join(FIG_DIR, "report_canal_endemico.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Guardada: {out}")


# ── Fig 2: Distribucion mensual de brotes ────────────────────────────────────
def fig_estacionalidad(df):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    for ax, (div, city) in zip(axes, DIVIPOLAS.items()):
        cdf = df[df["divipola"] == div]
        pct_brote = cdf.groupby("mes")["brote"].mean() * 100
        ax.bar(range(1, 13), pct_brote.reindex(range(1, 13), fill_value=0),
               color=CLR_CITY[div], alpha=0.8)
        ax.set_xticks(range(1, 13))
        ax.set_xticklabels(meses, fontsize=8)
        ax.set_title(f"{city} — % meses en brote por mes del año", fontsize=11, fontweight="bold")
        ax.set_ylabel("% meses en brote")
        ax.set_ylim(0, 70)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "report_estacionalidad_brotes.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Guardada: {out}")


# ── Fig 3: Curvas ROC y PR ────────────────────────────────────────────────────
def fig_roc_pr(df, xgb_model, xgb_prob_te, y_te, feats, meta):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # XGBoost ROC
    fpr, tpr, _ = roc_curve(y_te, xgb_prob_te)
    roc_auc = auc(fpr, tpr)
    ax1.plot(fpr, tpr, color="#1654A2", lw=2,
             label=f"XGBoost (AUROC = {roc_auc:.3f})")

    # Logistic
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        train = df[df["anio"] <= TRAIN_END]
        test  = df[df["anio"] > TRAIN_END]
        val   = train[train["anio"] >= TRAIN_END - 1]
        tr    = train[train["anio"] < TRAIN_END - 1]
        X_tr  = tr[feats].fillna(0).values
        y_tr  = tr["brote"].values
        X_te  = test[feats].fillna(0).values

        scaler = StandardScaler()
        X_tr_s = scaler.fit_transform(X_tr)
        X_te_s = scaler.transform(X_te)
        lr = LogisticRegression(C=0.1, max_iter=1000, class_weight="balanced",
                                random_state=42, n_jobs=-1)
        lr.fit(X_tr_s, y_tr)
        lr_prob = lr.predict_proba(X_te_s)[:, 1]
        fpr_l, tpr_l, _ = roc_curve(y_te, lr_prob)
        roc_l = auc(fpr_l, tpr_l)
        ax1.plot(fpr_l, tpr_l, color="#E83545", lw=2, ls="--",
                 label=f"Regresion Logistica (AUROC = {roc_l:.3f})")
    except Exception as e:
        print(f"  LR ROC error: {e}")

    ax1.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5, label="Aleatorio (AUROC = 0.500)")
    ax1.set_xlabel("Tasa de Falsos Positivos")
    ax1.set_ylabel("Tasa de Verdaderos Positivos")
    ax1.set_title("Curvas ROC — conjunto de prueba (2024-2025)", fontweight="bold")
    ax1.legend(fontsize=9)

    # PR curves
    prec_x, rec_x, _ = precision_recall_curve(y_te, xgb_prob_te)
    ap_x = average_precision_score(y_te, xgb_prob_te)
    ax2.plot(rec_x, prec_x, color="#1654A2", lw=2,
             label=f"XGBoost (AP = {ap_x:.3f})")
    if 'lr_prob' in dir():
        prec_l, rec_l, _ = precision_recall_curve(y_te, lr_prob)
        ap_l = average_precision_score(y_te, lr_prob)
        ax2.plot(rec_l, prec_l, color="#E83545", lw=2, ls="--",
                 label=f"Regresion Logistica (AP = {ap_l:.3f})")
    prev = y_te.mean()
    ax2.axhline(prev, color="gray", ls=":", lw=1, label=f"Prevalencia ({prev:.2f})")
    ax2.set_xlabel("Recall")
    ax2.set_ylabel("Precision")
    ax2.set_title("Curvas Precision-Recall — conjunto de prueba (2024-2025)", fontweight="bold")
    ax2.legend(fontsize=9)

    fig.tight_layout()
    out = os.path.join(FIG_DIR, "report_roc_pr.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Guardada: {out}")


# ── Fig 4: Importancia de features XGBoost ──────────────────────────────────
def fig_feature_importance(xgb_model, feats):
    importances = xgb_model.feature_importances_
    fi = pd.Series(importances, index=feats).sort_values(ascending=True)
    top = fi.tail(15)

    fig, ax = plt.subplots(figsize=(9, 6))
    colors = ["#1654A2" if "clasico" in f or "brote" in f else
              "#E99A00" if "mes_" in f or "p25" in f or "p75" in f or "zona" in f else
              "#888" for f in top.index]
    ax.barh(top.index, top.values, color=colors, alpha=0.85)
    ax.set_xlabel("Importancia (gain)")
    ax.set_title("Top 15 features — XGBoost (dengue total, brote clasico)",
                 fontweight="bold")

    legend_patches = [
        mpatches.Patch(color="#1654A2", alpha=0.85, label="Tendencia (lags clasico/brote)"),
        mpatches.Patch(color="#E99A00", alpha=0.85, label="Estacionalidad y canal endemico"),
        mpatches.Patch(color="#888",    alpha=0.85, label="Otras"),
    ]
    ax.legend(handles=legend_patches, fontsize=9, loc="lower right")
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "report_feature_importance.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Guardada: {out}")


# ── Fig 5: Deteccion de inicios de brote por modelo ─────────────────────────
def fig_inicios(ini_results):
    """ini_results: dict {modelo: (ini_det, ini_total, pct)}"""
    modelos = list(ini_results.keys())
    pcts    = [v[2] for v in ini_results.values()]
    colores = ["#1654A2" if "XGBoost" in m else
               "#2196F3" if "LightGBM" in m else
               "#E83545" if "Persistencia" in m else
               "#E99A00" if "Canal" in m else
               "#888" for m in modelos]

    fig, ax = plt.subplots(figsize=(10, 4.5))
    bars = ax.bar(modelos, pcts, color=colores, alpha=0.85, width=0.55)
    for bar, (m, (det, tot, pct)) in zip(bars, ini_results.items()):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{det}/{tot}", ha="center", va="bottom", fontsize=9, fontweight="bold")
    ax.set_ylabel("% de inicios de brote detectados")
    ax.set_title(
        "Deteccion de inicios de brote (es_inicio=1) en conjunto de prueba 2024-2025\n"
        "\"Brote es un estado, no un evento\" — la persistencia detecta 0% de los inicios",
        fontsize=11, fontweight="bold",
    )
    ax.set_ylim(0, 45)
    ax.axhline(18, color="#E99A00", ls="--", lw=1.2, alpha=0.7,
               label="Canal endémico actual (18%)")
    ax.legend(fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, "report_inicios_brote.png")
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    print(f"Guardada: {out}")
    return out


def main():
    print("Cargando datos...")
    df_all = pd.read_parquet(DATA_PATH)
    df_all["divipola"] = df_all["divipola"].astype(str).str.zfill(5)

    df = df_all[df_all["divipola"].isin(DIVIPOLAS)].copy()
    df["fecha"] = pd.to_datetime({"year": df["anio"], "month": df["mes"], "day": 1})
    df = df.sort_values(["divipola", "fecha"]).reset_index(drop=True)

    feats_base = [c for c in df_all.columns
                  if c not in PROHIBIDAS and pd.api.types.is_numeric_dtype(df_all[c])]

    feats, xgb_model, meta, X_te, y_te, xgb_prob_te = load_models(df)

    # ── Deteccion de inicios (test global) ──────────────────────────────────
    import pickle
    test_all = df_all[df_all["anio"] > TRAIN_END].copy()
    X_te_all  = test_all[feats_base].fillna(0)
    y_ini_all = test_all["es_inicio"]
    y_brt_all = test_all["brote"]

    with open(os.path.join(ROOT, "model", "lgbm_clasico.pkl"), "rb") as f:
        lgb_m = pickle.load(f)

    probs_xgb = xgb_model.predict_proba(X_te_all)[:, 1]
    probs_lgb = lgb_m.predict_proba(X_te_all)[:, 1]

    def ini_stats(probs, thr):
        pred = (probs >= thr).astype(int)
        det  = int(pred[y_ini_all == 1].sum())
        tot  = int(y_ini_all.sum())
        return det, tot, det / max(tot, 1) * 100

    pers  = test_all["brote_lag_1"].fillna(0).astype(int)
    canal = (test_all["zona_canal_lag1"].fillna(0) >= 2).astype(int)

    ini_results = {
        "XGBoost":          ini_stats(probs_xgb, 0.61),
        "LightGBM":         ini_stats(probs_lgb, 0.49),
        "Canal\nendemico":  (int(canal[y_ini_all == 1].sum()), int(y_ini_all.sum()),
                             int(canal[y_ini_all == 1].sum()) / max(y_ini_all.sum(), 1) * 100),
        "Persistencia\n(baseline)": (int(pers[y_ini_all == 1].sum()), int(y_ini_all.sum()),
                                     int(pers[y_ini_all == 1].sum()) / max(y_ini_all.sum(), 1) * 100),
    }

    print("Generando figuras...")
    fig_canal_endemico(df)
    fig_estacionalidad(df)
    fig_roc_pr(df_all, xgb_model, probs_xgb[test_all.index.isin(
        df_all[df_all["anio"] > TRAIN_END].index)], y_brt_all, feats_base, meta)
    fig_feature_importance(xgb_model, feats_base)
    fig_inicios(ini_results)
    print("Listo.")


if __name__ == "__main__":
    main()
