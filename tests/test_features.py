"""
Verificacion de src/features/build_features.

    python -m tests.test_features

Cada prueba corresponde a un error concreto que ya ocurrio.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.build_features import (
    REF_FIN,
    REF_INICIO,
    SERIE_OBJETIVO,
    agregar_endemico,
    agregar_rezagos,
    agregar_rolling,
    aplicar_referencia,
    columnas_predictoras,
)

fallos: list[str] = []


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    print(f"  {'ok   ' if condicion else 'FALLA'} {nombre} {detalle}")
    if not condicion:
        fallos.append(nombre)


def panel_minimo(anios=range(2007, 2026), municipios=("68001", "76001")) -> pd.DataFrame:
    filas = [
        {"divipola": m, "anio": a, "mes": mes}
        for m in municipios for a in anios for mes in range(1, 13)
    ]
    df = pd.DataFrame(filas)
    rng = np.random.default_rng(1)
    df["casos_grave"] = rng.integers(0, 12, len(df))
    df["casos_clasico"] = rng.integers(0, 200, len(df))
    return df.sort_values(["divipola", "anio", "mes"]).reset_index(drop=True)


def preparado(**kw) -> pd.DataFrame:
    df = panel_minimo(**kw)
    for col in ("casos_grave", "casos_clasico"):
        df = agregar_rezagos(df, col)
    return df


def test_rolling_no_cruza_municipios() -> None:
    print("\nel rolling no se pasa de un municipio al siguiente")
    df = pd.DataFrame(
        {
            "divipola": ["A"] * 5 + ["B"] * 5,
            "anio": [2007] * 10,
            "mes": list(range(1, 6)) * 2,
            "casos_grave": [1, 2, 3, 4, 5, 100, 200, 300, 400, 500],
        }
    )
    r = agregar_rolling(df.copy(), "casos_grave", ventana=3)["casos_grave_roll3"]
    b = r[df["divipola"] == "B"].tolist()
    check("la primera fila del segundo municipio es nula", pd.isna(b[0]), f"= {b[0]}")
    check("la segunda solo suma casos de su propio municipio", b[1] == 100.0, f"= {b[1]}")
    check("el tercero suma 100 + 200", b[2] == 300.0, f"= {b[2]}")


def test_rezagos_son_meses_calendario() -> None:
    print("\nlos rezagos son el mes calendario anterior, no la fila anterior")
    df = panel_minimo(anios=[2007, 2008], municipios=("68001",))
    df = agregar_rezagos(df, "casos_grave")
    esperado = df["casos_grave"].shift(1)
    check("lag_1 coincide con el mes anterior",
          bool(df["casos_grave_lag_1"].iloc[1:].eq(esperado.iloc[1:]).all()))
    check("la primera fila no tiene rezago", pd.isna(df["casos_grave_lag_1"].iloc[0]))
    check("lag_6 arranca en la fila 7", pd.isna(df["casos_grave_lag_6"].iloc[5])
          and pd.notna(df["casos_grave_lag_6"].iloc[6]))


def test_endemico() -> None:
    print("\nendemicidad: diez anios con casos y doscientos acumulados")
    df = panel_minimo(municipios=("sostenido", "concentrado", "disperso", "tardio"))
    df["casos_clasico"] = 0
    dentro = df["anio"].between(REF_INICIO, REF_FIN)

    df.loc[(df.divipola == "sostenido") & dentro & (df.anio <= REF_INICIO + 11), "casos_clasico"] = 30
    df.loc[(df.divipola == "concentrado") & dentro & (df.anio <= REF_INICIO + 4), "casos_clasico"] = 200
    df.loc[(df.divipola == "disperso") & dentro & (df.mes == 1), "casos_clasico"] = 1
    df.loc[(df.divipola == "tardio") & ~dentro, "casos_clasico"] = 500

    marca = agregar_endemico(df.copy(), df[dentro]).groupby("divipola")["es_endemico"].first()
    check("doce anios con casos y 4.320 acumulados es endemico", marca["sostenido"] == 1)
    check("mil casos en cinco anios NO es endemico", marca["concentrado"] == 0)
    check("catorce anios con 14 casos NO es endemico", marca["disperso"] == 0)
    check("casos solo despues de la referencia NO es endemico", marca["tardio"] == 0)


def test_canal_y_etiqueta() -> None:
    print("\ncanal endemico y etiqueta de brote")
    df = preparado(municipios=("68001", "76001", "99999"))
    df.loc[(df["divipola"] == "99999") & (df["anio"] <= REF_FIN), SERIE_OBJETIVO] = 0
    df = aplicar_referencia(df)

    check("p25 nunca es mayor que p75", bool((df["p25"] <= df["p75"]).all()))
    check("la zona solo toma valores 0, 1 y 2",
          set(df["zona_canal_lag1"].unique()) <= {0, 1, 2})
    check(f"brote es exactamente {SERIE_OBJETIVO} > p75",
          bool((df["brote"] == (df[SERIE_OBJETIVO] > df["p75"]).astype(int)).all()))
    check("brote_lag_1 es brote corrido un mes",
          bool((df.groupby("divipola")["brote"].shift(1).fillna(0).astype(int)
                == df["brote_lag_1"]).all()))
    check("no quedan nulos en la etiqueta", bool(df["brote"].notna().all()))
    check("es_inicio es brote sin brote el mes anterior",
          bool((df["es_inicio"] == ((df["brote"] == 1) & (df["brote_lag_1"] == 0))
                .astype(int)).all()))
    check("todo inicio es brote", bool(df.loc[df["es_inicio"] == 1, "brote"].eq(1).all()))

    ceros = df[df["p75"] == 0]
    check("cuando p75 es 0, la zona nunca es 2",
          bool(ceros["zona_canal_lag1"].isin([0, 1]).all()), f"({len(ceros)} filas)")


def test_referencia_expansiva() -> None:
    """
    Lo que reporto Mauro: el p75 no puede depender de anios posteriores al
    fold que se esta validando.
    """
    print("\nla referencia no ve el futuro")
    base = preparado()

    alterado = base.copy()
    alterado.loc[alterado["anio"] > 2014, SERIE_OBJETIVO] = 9999

    corte = aplicar_referencia(base, ref_fin=2014)
    corte_alterado = aplicar_referencia(alterado, ref_fin=2014)

    hasta_2014 = corte["anio"] <= 2014
    check("cambiar 2015 en adelante no mueve el p75 de la referencia",
          bool(corte["p75"].equals(corte_alterado["p75"])))
    check("tampoco mueve la etiqueta de los anios de la referencia",
          bool(corte.loc[hasta_2014, "brote"].equals(
               corte_alterado.loc[hasta_2014, "brote"])))

    # Contraprueba: con la ventana completa si tiene que cambiar, o la de
    # arriba estaria pasando por casualidad.
    completo = aplicar_referencia(base, ref_fin=REF_FIN)
    completo_alterado = aplicar_referencia(alterado, ref_fin=REF_FIN)
    check("con la ventana completa el p75 si cambia",
          not completo["p75"].equals(completo_alterado["p75"]))

    # Ventanas distintas tienen que dar percentiles distintos.
    check("ref hasta 2014 y ref hasta 2022 dan p75 distintos",
          not corte["p75"].equals(completo["p75"]))


def test_columnas_predictoras() -> None:
    print("\ncolumnas_predictoras deja fuera lo que no se puede usar")
    df = aplicar_referencia(preparado())
    cols = columnas_predictoras(df)
    for prohibida in ("casos_grave", "casos_clasico", "brote", "es_inicio",
                      "anio", "mes", "divipola"):
        check(f"no incluye {prohibida}", prohibida not in cols)
    check(f"si incluye {SERIE_OBJETIVO}_lag_1", f"{SERIE_OBJETIVO}_lag_1" in cols)
    check("si incluye p75", "p75" in cols)


def main() -> int:
    for fn in (
        test_rolling_no_cruza_municipios,
        test_rezagos_son_meses_calendario,
        test_endemico,
        test_canal_y_etiqueta,
        test_referencia_expansiva,
        test_columnas_predictoras,
    ):
        fn()
    print()
    if fallos:
        print(f"FALLARON {len(fallos)}: {fallos}")
        return 1
    print("todo ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
