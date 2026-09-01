"""
Baselines del sistema de alerta.

Referencia contra la cual se compara cualquier modelo posterior:

    nunca_alerta      no alerta nunca
    siempre_alerta    alerta todos los meses
    persistencia      alerta si el mes en curso ya esta en brote
    canal_endemico    alerta si los casos del mes en curso ya superan el
                      umbral del mes que se va a predecir

El ultimo es el que importa: es lo que hace hoy una secretaria de salud
mirando su grafica del canal endemico, sin modelo de por medio.

Se reportan dos vistas de cada uno. El agregado sobre todos los meses, y el
restringido a los inicios de brote. La segunda es la que dice si el sistema
sirve: en el agregado la persistencia luce muy bien porque acierta las
continuaciones, pero no detecta un solo inicio.

La particion y los folds van sobre anio_objetivo, el mes que se predice, no
sobre el mes de la fila. Cada fold recalcula el canal, el SIR, la endemicidad
y la etiqueta con aplicar_referencia usando solo los anios anteriores.

La prueba solo se evalua con --incluir-prueba.

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
from src.features.build_features import HORIZONTE, aplicar_referencia

MUNICIPIOS = {"68001": "Bucaramanga", "76001": "Cali"}
COL_ANIO = "anio_objetivo"


def con_etiqueta(df: pd.DataFrame) -> pd.DataFrame:
    """Filas evaluables: las que tienen mes objetivo dentro del panel."""
    d = df[df["objetivo"].notna()].copy()
    d["objetivo"] = d["objetivo"].astype(int)
    d["es_inicio"] = d["es_inicio"].astype(int)
    return d


def predicciones(df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {
        "nunca_alerta": np.zeros(len(df), dtype=int),
        "siempre_alerta": np.ones(len(df), dtype=int),
        "persistencia": df["brote"].to_numpy(),
        "canal_endemico": (df["zona_objetivo"] == 2).astype(int).to_numpy(),
    }


def imprimir_inicios(y, es_inicio, preds: dict[str, np.ndarray]) -> str:
    return tabla_inicios(
        {n: inicios_vs_continuaciones(y, p, es_inicio) for n, p in preds.items()}
    ).to_string()


def evaluar(df: pd.DataFrame, etiqueta: str) -> pd.DataFrame:
    y = df["objetivo"].to_numpy()
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


def evaluar_por_municipio(df: pd.DataFrame, baseline: str) -> None:
    if df["divipola"].nunique() < 2:
        return
    d = df.assign(pred=predicciones(df)[baseline])
    print(f"\n  desglose de '{baseline}' por municipio")
    tabla = metricas_por_grupo(d, "divipola", "objetivo", "pred")
    tabla.index = [MUNICIPIOS.get(i, i) for i in tabla.index]
    print(tabla.to_string())


def recalcular_fold(df: pd.DataFrame, anio: int, horizonte: int) -> pd.DataFrame:
    """
    Recalcula todo lo derivado para el fold que valida un anio.

    Se pasan las filas cuyo MES sea de ese anio o anterior, no solo las que ya
    tienen etiqueta. La etiqueta sale de correr el brote 'horizonte' meses, asi
    que sin los ultimos meses del anio la ultima fila de cada municipio se
    quedaria sin objetivo y el fold perderia observaciones. Esas filas de mas
    solo existen para poder correr la etiqueta: no se evaluan.

    La referencia se corta en anio - 1, asi que el canal no ve el anio validado.
    """
    return aplicar_referencia(
        df[df["anio"] <= anio], ref_fin=anio - 1, horizonte=horizonte
    )


def evaluar_folds(df: pd.DataFrame, horizonte: int) -> pd.DataFrame:
    """Cada baseline sobre la validacion de cada fold, y el agregado."""
    acumulado: dict[str, dict[str, list]] = {}
    inicios: list[np.ndarray] = []
    filas = []

    for anio, _, _ in folds_temporales(df, col_anio=COL_ANIO):
        d = recalcular_fold(df, anio, horizonte)
        val = con_etiqueta(d[d[COL_ANIO] == anio])
        if val.empty:
            continue
        y = val["objetivo"].to_numpy()
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
    print("\n  separando inicios de continuaciones")
    print(imprimir_inicios(
        y_todos, np.concatenate(inicios),
        {n: np.concatenate(d["p"]) for n, d in acumulado.items()},
    ))
    print("\n  la persistencia no puede detectar un inicio: solo alerta si el mes")
    print("  en curso ya esta en brote, y un inicio es justo cuando no lo estaba.")
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
    horizonte = int(df["anio_objetivo"].iloc[0] * 12 + df["mes_objetivo"].iloc[0]
                    - df["anio"].iloc[0] * 12 - df["mes"].iloc[0])

    if not args.todos_los_municipios:
        df = df[df["divipola"].isin(MUNICIPIOS)].copy()
        faltan = set(MUNICIPIOS) - set(df["divipola"])
        if faltan:
            raise ValueError(f"No estan en el panel: {sorted(faltan)}")
        print("Alcance: " + ", ".join(MUNICIPIOS.values()))
    else:
        print(f"Alcance: {df['divipola'].nunique():,} municipios")
    print(f"Horizonte: {horizonte} mes(es). La particion va sobre {COL_ANIO}.")

    particion = split_temporal(df, col_anio=COL_ANIO)
    train = con_etiqueta(particion.train)
    test = con_etiqueta(particion.test)
    print(f"\nentrenamiento {len(train):,} meses con etiqueta, "
          f"prueba {len(test):,}")

    evaluar(train, "ENTRENAMIENTO, referencia fija 2007-2022")
    print("  (solo como contexto: la etiqueta de estas filas se calculo con la")
    print("   ventana completa. Los numeros que valen son los folds y la prueba.)")
    evaluar_folds(df, horizonte)

    if args.incluir_prueba:
        print("\n" + "=" * 70)
        print("PRUEBA. Se mira una sola vez, al final.")
        print("=" * 70)
        evaluar(test, "PRUEBA")
        evaluar_por_municipio(test, "canal_endemico")
    else:
        print("\n(la prueba no se evaluo, --incluir-prueba para verla)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
