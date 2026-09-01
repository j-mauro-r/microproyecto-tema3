"""
Baselines del sistema de alerta.

Referencia contra la cual se compara cualquier modelo posterior:

    nunca_alerta      no alerta nunca
    siempre_alerta    alerta todos los meses
    persistencia      alerta si el mes anterior fue brote
    canal_endemico    alerta si el mes anterior quedo por encima del P75

El ultimo es el que importa: es lo que hace hoy una secretaria de salud
mirando su grafica del canal endemico, sin modelo de por medio.

La prueba solo se evalua con --incluir-prueba. Son 2023, 2024 y 2025 y se
miran una vez, cuando ya este escogido el modelo.

Uso:
    python -m src.models.baseline
    python -m src.models.baseline --todos-los-municipios
    python -m src.models.baseline --incluir-prueba
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluation.metrics import metricas_alerta, metricas_por_grupo, tabla_comparativa
from src.evaluation.splits import folds_temporales, resumen_folds, split_temporal

MUNICIPIOS = {"68001": "Bucaramanga", "76001": "Cali"}


def predicciones(df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        "nunca_alerta": np.zeros(len(df), dtype=int),
        "siempre_alerta": np.ones(len(df), dtype=int),
        "persistencia": df["brote_lag_1"].to_numpy(),
        "canal_endemico": (df["zona_canal_lag1"] == 2).astype(int).to_numpy(),
    }


def evaluar(df: pd.DataFrame, etiqueta: str) -> pd.DataFrame:
    y = df["brote"].to_numpy()
    print(f"\n{etiqueta}: {len(df):,} meses, {y.sum():,} brotes ({y.mean() * 100:.1f}%)")
    if y.sum() == 0:
        print("  sin brotes, no hay nada que medir")
        return pd.DataFrame()
    tabla = tabla_comparativa(
        {nombre: metricas_alerta(y, pred) for nombre, pred in predicciones(df).items()}
    )
    print(tabla.to_string())
    return tabla


def evaluar_por_municipio(df: pd.DataFrame, baseline: str) -> None:
    if df["divipola"].nunique() < 2:
        return
    d = df.assign(pred=predicciones(df)[baseline])
    print(f"\n  desglose de '{baseline}' por municipio")
    tabla = metricas_por_grupo(d, "divipola", "brote", "pred")
    tabla.index = [MUNICIPIOS.get(i, i) for i in tabla.index]
    print(tabla.to_string())


def evaluar_folds(df: pd.DataFrame) -> pd.DataFrame:
    """Cada baseline sobre la validacion de cada fold, y el agregado."""
    acumulado = {nombre: {"y": [], "p": []} for nombre in predicciones(df.head(1))}
    filas = []
    for anio, _, val in folds_temporales(df):
        y = val["brote"].to_numpy()
        for nombre, pred in predicciones(val).items():
            acumulado[nombre]["y"].append(y)
            acumulado[nombre]["p"].append(pred)
        if y.sum():
            r = metricas_alerta(y, predicciones(val)["canal_endemico"])
            filas.append({"fold": anio, "meses": len(y), "brotes": int(y.sum()),
                          "sensibilidad": round(r["sensibilidad"], 3),
                          "precision": round(r["precision"], 3),
                          "falsas_alarmas": round(r["tasa_falsas_alarmas"], 3)})

    if filas:
        print("\ncanal_endemico fold por fold")
        print(pd.DataFrame(filas).to_string(index=False))

    print("\nagregado de todos los folds")
    tabla = tabla_comparativa({
        nombre: metricas_alerta(np.concatenate(d["y"]), np.concatenate(d["p"]))
        for nombre, d in acumulado.items()
    })
    print(tabla.to_string())
    return tabla


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", type=Path,
                    default=Path("data/processed/features_mensual.parquet"))
    ap.add_argument("--todos-los-municipios", action="store_true")
    ap.add_argument("--incluir-prueba", action="store_true")
    args = ap.parse_args(argv)

    if not args.features.exists():
        raise FileNotFoundError(
            f"No existe {args.features}. Corre primero:\n"
            f"  python -m src.data.build_panel\n"
            f"  python -m src.features.build_features"
        )

    df = pd.read_parquet(args.features)
    if not args.todos_los_municipios:
        df = df[df["divipola"].isin(MUNICIPIOS)].copy()
        faltan = set(MUNICIPIOS) - set(df["divipola"])
        if faltan:
            raise ValueError(f"No estan en el panel: {sorted(faltan)}")
        print("Alcance: " + ", ".join(MUNICIPIOS.values()))
    else:
        print(f"Alcance: {df['divipola'].nunique():,} municipios")

    particion = split_temporal(df)
    particion.resumen(col_objetivo="brote")

    print("\nFolds de validacion cruzada temporal")
    resumen_folds(particion.train, "brote")

    evaluar(particion.train, "ENTRENAMIENTO COMPLETO")
    evaluar_folds(particion.train)

    if args.incluir_prueba:
        print("\n" + "=" * 70)
        print("PRUEBA. Se mira una sola vez, al final.")
        print("=" * 70)
        evaluar(particion.test, "PRUEBA")
        evaluar_por_municipio(particion.test, "canal_endemico")
    else:
        print("\n(la prueba no se evaluo, --incluir-prueba para verla)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
