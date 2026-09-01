"""
Variables de modelado a partir del panel mensual.

Encuadre
--------
Cada fila es un municipio y un mes t. Las variables son todo lo que se conoce
al cerrar ese mes, y la etiqueta es si habra brote en t + HORIZONTE. Mover el
horizonte es cambiar una constante: no hay que rezagar variable por variable.

    fila = (municipio, mes t)
    variables = casos, clima, canal y estacionalidad hasta el mes t
    objetivo  = brote en el mes t + HORIZONTE

De ahi salen dos columnas de calendario, anio_objetivo y mes_objetivo, que son
el mes que se esta prediciendo. La particion y los folds se hacen sobre
anio_objetivo, no sobre anio: con horizonte de un mes, la fila de diciembre de
2022 predice enero de 2023, que es prueba, y particionar por el mes de la fila
dejaria esa etiqueta del lado del entrenamiento.

La ventana de referencia del canal si va por anio, que es cuando ocurrieron los
casos.

Origen
------
La logica de variables viene de src/features/build_features.py de la PR #8
(rama feat/pipeline-base-mensual-v2, Nicolas Lara): rezagos, suma movil,
rezagos de clima, estacionalidad ciclica, canal endemico con el arreglo para
P75 = 0 y SIR mensual.

Uso:
    python -m src.features.build_features
    python -m src.features.build_features --horizonte 3
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SERIE_OBJETIVO = "casos_clasico"

# Meses de anticipacion. Con 1 se predice el mes siguiente.
HORIZONTE = 1

REZAGOS = [1, 2, 3, 4, 6]
VENTANA_ROLLING = 3

# Ventana de referencia del canal, el SIR y la endemicidad. Termina donde
# termina el entrenamiento (src/evaluation/splits.py).
#
# En validacion cruzada NO se usa este valor: cada fold recalcula con
# aplicar_referencia(df, ref_fin=anio - 1). Un p75 calculado hasta 2022 y usado
# para validar 2015 ya vio ocho anios de futuro, y como la etiqueta sale de
# comparar contra el p75, la fuga alcanzaria tambien a la etiqueta.
REF_INICIO = 2007
REF_FIN = 2022

# Columnas que dependen de la ventana de referencia o del horizonte, y que hay
# que borrar antes de recalcular.
DERIVADAS = [
    "p25", "p75", "zona_canal", "sir", "es_endemico",
    "brote", "objetivo", "es_inicio", "anio_objetivo", "mes_objetivo",
    "p25_objetivo", "p75_objetivo", "zona_objetivo",
]

# Columnas que no puede usar un modelo: identificadores, calendario del mes que
# se predice, la etiqueta y lo que se deriva de ella.
NO_PREDICTORAS = {
    "divipola", "municipio", "departamento", "periodo",
    "anio", "mes", "anio_objetivo", "mes_objetivo",
    "objetivo", "es_inicio",
}

# Criterio de municipio endemico de Decisiones_Metodologicas: al menos diez
# anios con casos y doscientos casos acumulados, sobre la serie de clasico.
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


def tabla_canal(ref: pd.DataFrame) -> pd.DataFrame:
    """Percentiles 25 y 75 de casos por municipio y mes del anio."""
    return (
        ref.groupby(["divipola", "mes"])[SERIE_OBJETIVO]
        .quantile([0.25, 0.75])
        .unstack()
        .reset_index()
        .rename(columns={0.25: "p25", 0.75: "p75"})
    )


def zona(casos: pd.Series, p25: pd.Series, p75: pd.Series) -> np.ndarray:
    """
    0 exito, 1 seguridad o alerta, 2 epidemia.

    Cuando el P75 historico es cero no hay tres zonas que distinguir: o hubo
    casos o no los hubo.
    """
    return np.where(
        p75 == 0,
        np.where(casos == 0, 0, 1),
        np.where(casos < p25, 0, np.where(casos < p75, 1, 2)),
    ).astype(int)


def agregar_canal(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Umbrales del mes en curso y la zona en la que cayo."""
    df = df.merge(tabla_canal(ref), on=["divipola", "mes"], how="left")
    df["p25"] = df["p25"].fillna(0.0)
    df["p75"] = df["p75"].fillna(0.0)
    df["zona_canal"] = zona(df[SERIE_OBJETIVO], df["p25"], df["p75"])
    return df


def agregar_umbral_objetivo(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """
    Umbral del mes que se predice, y en que zona de ese umbral caen los casos
    del mes en curso.

    Es distinto de zona_canal porque el canal es estacional: estar en 300 casos
    puede ser epidemia en un mes cuyo P75 es 250 y normal en el siguiente si su
    P75 es 400. Esta es la pregunta que se hace una secretaria de salud mirando
    la grafica: con lo que llevo hoy, cruzo el umbral del mes que viene.

    Los umbrales salen de la ventana de referencia, asi que son conocidos de
    antemano y no miran el futuro.
    """
    canal = tabla_canal(ref).rename(
        columns={"mes": "mes_objetivo", "p25": "p25_objetivo", "p75": "p75_objetivo"}
    )
    df = df.merge(canal, on=["divipola", "mes_objetivo"], how="left")
    df["p25_objetivo"] = df["p25_objetivo"].fillna(0.0)
    df["p75_objetivo"] = df["p75_objetivo"].fillna(0.0)
    df["zona_objetivo"] = zona(
        df[SERIE_OBJETIVO], df["p25_objetivo"], df["p75_objetivo"]
    )
    return df


def agregar_sir(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Casos del mes en curso sobre el promedio historico de ese mes."""
    esperado = (
        ref.groupby(["divipola", "mes"])[SERIE_OBJETIVO]
        .mean()
        .reset_index()
        .rename(columns={SERIE_OBJETIVO: "esperado"})
    )
    df = df.merge(esperado, on=["divipola", "mes"], how="left")
    df["sir"] = df[SERIE_OBJETIVO] / df["esperado"].replace(0, np.nan)
    return df.drop(columns=["esperado"])


def agregar_endemico(df: pd.DataFrame, ref: pd.DataFrame) -> pd.DataFrame:
    """Endemicidad segun el criterio del documento, sobre la referencia."""
    por_anio = ref.groupby(["divipola", "anio"])[SERIE_ENDEMICIDAD].sum()
    anios_con_casos = (por_anio > 0).groupby("divipola").sum()
    total = por_anio.groupby("divipola").sum()
    endemicos = (anios_con_casos >= MIN_ANIOS_CON_CASOS) & (total >= MIN_CASOS_TOTALES)
    df["es_endemico"] = df["divipola"].map(endemicos).fillna(False).astype(int)
    return df


def agregar_objetivo(df: pd.DataFrame, horizonte: int = HORIZONTE) -> pd.DataFrame:
    """
    brote     : el mes en curso supera el P75 historico. Es variable, no etiqueta.
    objetivo  : si habra brote dentro de 'horizonte' meses. Es la etiqueta.
    es_inicio : el mes objetivo arranca el brote, o sea que el anterior no lo era.

    anio_objetivo y mes_objetivo son el calendario del mes que se predice.
    Sobre ellos se parte el conjunto, no sobre anio.
    """
    if horizonte < 1:
        raise ValueError(f"El horizonte tiene que ser al menos 1, llego {horizonte}")

    df["brote"] = (df[SERIE_OBJETIVO] > df["p75"]).astype(int)

    grupo = df.groupby("divipola")["brote"]
    df["objetivo"] = grupo.shift(-horizonte)
    previo = grupo.shift(-(horizonte - 1))
    df["es_inicio"] = ((df["objetivo"] == 1) & (previo == 0)).astype("Int64")
    df.loc[df["objetivo"].isna(), "es_inicio"] = pd.NA

    absoluto = df["anio"] * 12 + (df["mes"] - 1) + horizonte
    df["anio_objetivo"] = (absoluto // 12).astype(int)
    df["mes_objetivo"] = (absoluto % 12 + 1).astype(int)
    return df


def aplicar_referencia(
    df: pd.DataFrame,
    ref_fin: int = REF_FIN,
    ref_inicio: int = REF_INICIO,
    horizonte: int = HORIZONTE,
) -> pd.DataFrame:
    """
    Calcula canal, SIR, endemicidad y etiqueta usando solo los anios de la
    ventana de referencia.

    Es el punto de entrada para los folds: con ref_fin igual al anio anterior al
    que se valida, nada de lo derivado ve ese anio ni los posteriores.
    """
    df = df.drop(columns=[c for c in DERIVADAS if c in df.columns])
    df = df.sort_values(["divipola", "anio", "mes"]).reset_index(drop=True)

    ref = df[df["anio"].between(ref_inicio, ref_fin)]
    if ref.empty:
        raise ValueError(f"No hay filas en la referencia {ref_inicio}-{ref_fin}")

    df = agregar_canal(df, ref)
    df = agregar_sir(df, ref)
    df = agregar_endemico(df, ref)
    df = agregar_objetivo(df, horizonte)
    return agregar_umbral_objetivo(df, ref)


def columnas_predictoras(df: pd.DataFrame) -> list[str]:
    """Columnas numericas que un modelo puede usar."""
    return [
        c for c in df.columns
        if c not in NO_PREDICTORAS and pd.api.types.is_numeric_dtype(df[c])
    ]


def construir(panel: Path, salida: Path, horizonte: int = HORIZONTE) -> pd.DataFrame:
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

    print(f"Canal, SIR y etiqueta sobre {REF_INICIO}-{REF_FIN}, "
          f"objetivo {SERIE_OBJETIVO} a {horizonte} mes(es)")
    df = aplicar_referencia(df, horizonte=horizonte)

    salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(salida, index=False)
    print(f"\nGuardado {salida}  ({salida.stat().st_size / 1e6:.1f} MB)")
    resumen(df, horizonte)
    return df


def resumen(df: pd.DataFrame, horizonte: int = HORIZONTE) -> None:
    con_objetivo = df[df["objetivo"].notna()]
    endemicos = df[df["es_endemico"] == 1]["divipola"].nunique()
    print("\nResumen")
    print(f"  horizonte           : {horizonte} mes(es)")
    print(f"  filas               : {len(df):,}, con etiqueta {len(con_objetivo):,}")
    print(f"  predictoras         : {len(columnas_predictoras(df))}")
    print(f"  municipios endemicos: {endemicos:,} de {df['divipola'].nunique():,}")
    print(f"  meses objetivo en brote: {con_objetivo['objetivo'].mean() * 100:.1f}%")
    print(f"  de ellos inicio     : {int(con_objetivo['es_inicio'].sum()):,} "
          f"de {int(con_objetivo['objetivo'].sum()):,}")

    for cod, nom in (("68001", "Bucaramanga"), ("76001", "Cali")):
        s = con_objetivo[con_objetivo["divipola"] == cod]
        if s.empty:
            print(f"  {nom:12s}: no aparece")
            continue
        p75 = s.groupby("mes")["p75"].first()
        print(f"  {nom:12s}: {s['objetivo'].mean() * 100:4.1f}% de meses objetivo "
              f"en brote, P75 entre {p75.min():.0f} y {p75.max():.0f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--panel", type=Path,
                    default=Path("data/processed/panel_mensual.parquet"))
    ap.add_argument("--out", type=Path,
                    default=Path("data/processed/features_mensual.parquet"))
    ap.add_argument("--horizonte", type=int, default=HORIZONTE,
                    help="Meses de anticipacion de la prediccion")
    args = ap.parse_args(argv)
    construir(args.panel, args.out, args.horizonte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
