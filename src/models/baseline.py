"""
Baselines del sistema de alerta.

Referencia contra la cual se compara cualquier modelo posterior:

    nunca_alerta      no alerta nunca
    siempre_alerta    alerta todos los meses
    persistencia      alerta si el mes anterior fue brote
    canal_endemico    alerta si el mes anterior quedo por encima del P75

El ultimo es el que importa: es lo que hace hoy una secretaria de salud
mirando su grafica del canal endemico, sin modelo de por medio.

Se reportan dos vistas de cada uno. El agregado sobre todos los meses, y el
restringido a los inicios de brote. La segunda es la que dice si el sistema
sirve: en el agregado la persistencia luce muy bien porque acierta las
continuaciones, pero no detecta un solo inicio.

Cada fold recalcula el canal, el SIR, la endemicidad y la etiqueta con
aplicar_referencia usando solo los anios anteriores al que valida. El archivo
de variables trae esas columnas calculadas hasta 2022, que es correcto para la
prueba (2023-2025) pero seria fuga dentro de la validacion cruzada.

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

from src.evaluation.metrics import (
    inicios_vs_continuaciones,
    metricas_alerta,
    metricas_por_grupo,
    tabla_comparativa,
    tabla_inicios,
)
from src.evaluation.splits import folds_temporales, split_temporal
from src.features.build_features import aplicar_referencia

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
    ini = df["es_inicio"].to_numpy()
    print(f"\n{etiqueta}: {len(df):,} meses, {y.sum():,} brotes "
          f"({y.mean() * 100:.1f}%), de ellos {ini.sum()} son inicio")
    if y.sum() == 0:
        print("  sin brotes, no hay nada que medir")
        return pd.DataFrame()

    preds = predicciones(df)
    tabla = tabla_comparativa({n: metricas_alerta(y, p) for n, p in preds.items()})
    print(tabla.to_string())
    print("\n  separando inicios de continuaciones")
    print(imprimir_inicios(y, ini, preds))
    return tabla


def imprimir_inicios(y, es_inicio, preds: dict[str, np.ndarray]) -> str:
    return tabla_inicios(
        {n: inicios_vs_continuaciones(y, p, es_inicio) for n, p in preds.items()}
    ).to_string()


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
    acumulado: dict[str, dict[str, list]] = {}
    inicios: list[np.ndarray] = []
    filas = []

    for anio, tr, va in folds_temporales(df):
        d = aplicar_referencia(pd.concat([tr, va], ignore_index=True), ref_fin=anio - 1)
        val = d[d["anio"] == anio]
        y = val["brote"].to_numpy()
        preds = predicciones(val)
        inicios.append(val["es_inicio"].to_numpy())

        for nombre, pred in preds.items():
            acumulado.setdefault(nombre, {"y": [], "p": []})
            acumulado[nombre]["y"].append(y)
            acumulado[nombre]["p"].append(pred)

        fila = {"fold": anio, "ref": f"2007-{anio - 1}", "meses": len(y),
                "brotes": int(y.sum()), "inicios": int(val["es_inicio"].sum())}
        if y.sum():
            r = metricas_alerta(y, preds["canal_endemico"])
            fila |= {"sensibilidad": round(r["sensibilidad"], 3),
                     "precision": round(r["precision"], 3),
                     "falsas_alarmas": round(r["tasa_falsas_alarmas"], 3)}
        filas.append(fila)

    print("\ncanal_endemico fold por fold, con referencia expansiva")
    print(pd.DataFrame(filas).to_string(index=False))
    vacios = [f["fold"] for f in filas if f["brotes"] == 0]
    if vacios:
        print(f"  folds sin brotes, solo aportan falsas alarmas: {vacios}")

    print("\nagregado de todos los folds")
    tabla = tabla_comparativa({
        nombre: metricas_alerta(np.concatenate(d["y"]), np.concatenate(d["p"]))
        for nombre, d in acumulado.items()
    })
    print(tabla.to_string())

    y_todos = np.concatenate(next(iter(acumulado.values()))["y"])
    ini_todos = np.concatenate(inicios)
    print("\n  separando inicios de continuaciones")
    print(imprimir_inicios(
        y_todos, ini_todos,
        {n: np.concatenate(d["p"]) for n, d in acumulado.items()},
    ))
    print("\n  la persistencia no puede detectar un inicio: solo alerta si el mes")
    print("  anterior ya era brote, y un inicio es justo cuando no lo era.")
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

    evaluar(particion.train, "ENTRENAMIENTO, referencia fija 2007-2022")
    print("  (solo como contexto: la etiqueta de estas filas se calculo con la")
    print("   ventana completa, asi que las de 2015 conocen 2016 en adelante.")
    print("   Los numeros que valen son los de los folds y los de la prueba.)")
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
