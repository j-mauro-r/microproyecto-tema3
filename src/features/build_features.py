"""
Variables de modelado a partir del panel mensual.

La logica viene de src/features/build_features.py de la PR #8 (rama
feat/pipeline-base-mensual-v2, Nicolas Lara): rezagos, suma movil, rezagos de
clima, estacionalidad ciclica, canal endemico con el arreglo para P75 = 0 y
SIR mensual. Todas las variables derivadas de casos se calculan sobre el
rezago y no sobre el mes en curso, que es lo que se quiere predecir.

Diferencias con esa version:
  - lee el panel en parquet en vez de los CSV crudos, de modo que los meses
    sin casos existen como filas y los rezagos son meses calendario
  - el rolling se agrupa por municipio
  - la endemicidad y el canal se calculan solo sobre la ventana de referencia,
    y los folds la recalculan con aplicar_referencia para no ver el futuro
  - se elimina anio_epidemia, que era un indice de tiempo
  - se agrega la etiqueta binaria de brote

Uso:
    python -m src.features.build_features
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SERIE_OBJETIVO = "casos_clasico"

REZAGOS = [1, 2, 3, 4, 6]
VENTANA_ROLLING = 3

# Ventana de referencia por defecto del canal, el SIR y la endemicidad. Termina
# donde termina el entrenamiento (src/evaluation/splits.py).
#
# Para validacion cruzada NO se usa este valor: cada fold recalcula con
# aplicar_referencia(df, ref_fin=anio - 1), porque un p75 calculado hasta 2022
# y usado para validar 2015 ya vio ocho anios de futuro, y como la etiqueta es
# casos > p75, la fuga alcanza tambien a la etiqueta.
REF_INICIO = 2007
REF_FIN = 2022

# Todo lo que depende de la ventana de referencia y hay que recalcular con ella.
DERIVADAS_DE_REFERENCIA = [
    "p25", "p75", "zona_canal_lag1", "sir_lag1", "es_endemico",
    "brote", "brote_lag_1", "es_inicio",
]

# Criterio de municipio endemico de Decisiones_Metodologicas: al menos diez
# anios con casos y doscientos casos acumulados, sobre la serie de dengue
# clasico, que es la que mide transmision sostenida.
SERIE_ENDEMICIDAD = "casos_clasico"
MIN_ANIOS_CON_CASOS = 10
MIN_CASOS_TOTALES = 200

CLIMA = ["temp_mean_c", "rain_mm_day"]
REZAGOS_CLIMA = [1, 2, 3]


def agregar_rezagos(df: pd.DataFrame, col: str) -> pd.DataFrame:
    grupo = df.groupby("divipola")[col]
    for r in REZAGOS:
        df[f"{col}_lag_{r}"] = grupo.shift(r)
    return df


def agregar_rolling(df: pd.DataFrame, col: str, ventana: int = VENTANA_ROLLING) -> pd.DataFrame:
    """Suma de los meses anteriores, sin incluir el mes en curso."""
    previos = df.groupby("divipola")[col].shift(1)
    df[f"{col}_roll{ventana}"] = (
        previos.groupby(df["divipola"])
        .rolling(ventana, min_periods=1)
        .sum()
        .reset_index(level=0, drop=True)
    )
    return df


def agregar_clima(df: pd.DataFrame) -> pd.DataFrame:
    for col in CLIMA:
        if col not in df.columns:
            print(f"  aviso: el panel no trae {col}")
            df[col] = np.nan
        grupo = df.groupby("divipola")[col]
        for r in REZAGOS_CLIMA:
            df[f"{col}_lag_{r}"] = grupo.shift(r)
    return df


def agregar_temporales(df: pd.DataFrame) -> pd.DataFrame:
    df["mes_sin"] = np.sin(df["mes"] * 2 * np.pi / 12)
    df["mes_cos"] = np.cos(df["mes"] * 2 * np.pi / 12)
    return df


def agregar_canal(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Percentiles 25 y 75 por municipio y mes, y la zona del mes anterior."""
    canal = (
        ref.groupby(["divipola", "mes"])[SERIE_OBJETIVO]
        .quantile([0.25, 0.75])
        .unstack()
        .reset_index()
        .rename(columns={0.25: "p25", 0.75: "p75"})
    )
    df = df.merge(canal, on=["divipola", "mes"], how="left")
    df["p25"] = df["p25"].fillna(0.0)
    df["p75"] = df["p75"].fillna(0.0)

    previo = df[f"{SERIE_OBJETIVO}_lag_1"].fillna(0)
    df["zona_canal_lag1"] = np.where(
        df["p75"] == 0,
        np.where(previo == 0, 0, 1),
        np.where(previo < df["p25"], 0, np.where(previo < df["p75"], 1, 2)),
    ).astype(int)
    return df


def agregar_sir(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Casos del mes anterior sobre el promedio historico de ese mes."""
    esperado = (
        ref.groupby(["divipola", "mes"])[SERIE_OBJETIVO]
        .mean()
        .reset_index()
        .rename(columns={SERIE_OBJETIVO: "esperado"})
    )
    df = df.merge(esperado, on=["divipola", "mes"], how="left")
    df["sir_lag1"] = df[f"{SERIE_OBJETIVO}_lag_1"] / df["esperado"].replace(0, np.nan)
    return df.drop(columns=["esperado"])


def agregar_endemico(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Endemicidad segun el criterio del documento, sobre la referencia."""
    por_anio = ref.groupby(["divipola", "anio"])[SERIE_ENDEMICIDAD].sum()
    anios_con_casos = (por_anio > 0).groupby("divipola").sum()
    total = por_anio.groupby("divipola").sum()
    endemicos = (anios_con_casos >= MIN_ANIOS_CON_CASOS) & (total >= MIN_CASOS_TOTALES)
    df["es_endemico"] = df["divipola"].map(endemicos).fillna(False).astype(int)
    return df


def agregar_etiqueta(df: pd.DataFrame) -> pd.DataFrame:
    """
    Brote es superar el P75 historico del mismo mes.

    es_inicio marca el primer mes de cada brote. No es una variable predictora
    porque depende del mes en curso: sirve para separar, al evaluar, la
    deteccion de inicios de la de continuaciones.
    """
    df["brote"] = (df[SERIE_OBJETIVO] > df["p75"]).astype(int)
    df["brote_lag_1"] = df.groupby("divipola")["brote"].shift(1).fillna(0).astype(int)
    df["es_inicio"] = ((df["brote"] == 1) & (df["brote_lag_1"] == 0)).astype(int)
    return df


def aplicar_referencia(
    df: pd.DataFrame,
    ref_fin: int = REF_FIN,
    ref_inicio: int = REF_INICIO,
) -> pd.DataFrame:
    """
    Calcula canal, SIR, endemicidad y etiqueta usando solo los anios de la
    ventana de referencia.

    Es el punto de entrada para los folds: pasar ref_fin igual al anio anterior
    al que se va a validar garantiza que nada de lo derivado haya visto ese anio
    ni los posteriores.
    """
    df = df.drop(columns=[c for c in DERIVADAS_DE_REFERENCIA if c in df.columns])
    df = df.sort_values(["divipola", "anio", "mes"]).reset_index(drop=True)

    ref = df[df["anio"].between(ref_inicio, ref_fin)]
    if ref.empty:
        raise ValueError(
            f"No hay filas en la ventana de referencia {ref_inicio}-{ref_fin}"
        )

    df = agregar_canal(df, ref)
    df = agregar_sir(df, ref)
    df = agregar_endemico(df, ref)
    return agregar_etiqueta(df)


def columnas_predictoras(df: pd.DataFrame) -> list[str]:
    """Columnas numericas utilizables, sin identificadores ni datos del mes en curso."""
    prohibidas = {
        "divipola", "municipio", "departamento", "periodo",
        "anio", "mes", "casos_grave", "casos_clasico", "brote", "es_inicio",
    }
    return [
        c for c in df.columns
        if c not in prohibidas and pd.api.types.is_numeric_dtype(df[c])
    ]


def construir(panel: Path, salida: Path) -> pd.DataFrame:
    if not panel.exists():
        raise FileNotFoundError(
            f"No existe {panel}. Corre primero: python -m src.data.build_panel"
        )

    df = pd.read_parquet(panel)
    print(f"Panel: {len(df):,} filas, {df['divipola'].nunique():,} municipios, "
          f"{df['anio'].min()}-{df['anio'].max()}")
    df = df.sort_values(["divipola", "anio", "mes"]).reset_index(drop=True)

    print("Rezagos y suma movil")
    for col in ("casos_grave", "casos_clasico"):
        df = agregar_rezagos(df, col)
        df = agregar_rolling(df, col)

    print("Clima")
    df = agregar_clima(df)

    print("Estacionalidad")
    df = agregar_temporales(df)

    print(f"Canal, SIR y etiqueta sobre {REF_INICIO}-{REF_FIN}, objetivo {SERIE_OBJETIVO}")
    df = aplicar_referencia(df)

    salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(salida, index=False)
    print(f"\nGuardado {salida}  ({salida.stat().st_size / 1e6:.1f} MB)")
    resumen(df)
    return df


def resumen(df: pd.DataFrame) -> None:
    endemicos = df[df["es_endemico"] == 1]["divipola"].nunique()
    print("\nResumen")
    print(f"  filas               : {len(df):,}")
    print(f"  predictoras         : {len(columnas_predictoras(df))}")
    print(f"  municipios endemicos: {endemicos:,} de {df['divipola'].nunique():,}")
    print(f"  meses en brote      : {df['brote'].mean() * 100:.1f}%")
    print(f"  de ellos, inicios   : {df['es_inicio'].sum():,} de {df['brote'].sum():,}")
    print(f"  meses sin casos     : {(df[SERIE_OBJETIVO] == 0).mean() * 100:.1f}%")

    for cod, nom in (("68001", "Bucaramanga"), ("76001", "Cali")):
        s = df[df["divipola"] == cod]
        if s.empty:
            print(f"  {nom:12s}: no aparece")
            continue
        p75 = s.groupby("mes")["p75"].first()
        print(f"  {nom:12s}: {s['brote'].mean() * 100:4.1f}% de meses en brote, "
              f"P75 entre {p75.min():.0f} y {p75.max():.0f}")

    por_anio = df[df["divipola"].isin(["68001", "76001"])].groupby("anio")["brote"].sum()
    vacios = por_anio[por_anio == 0].index.tolist()
    if vacios:
        print(f"  anios sin brotes en Bucaramanga ni Cali: {vacios}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel", type=Path,
                    default=Path("data/processed/panel_mensual.parquet"))
    ap.add_argument("--out", type=Path,
                    default=Path("data/processed/features_mensual.parquet"))
    args = ap.parse_args(argv)
    construir(args.panel, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
