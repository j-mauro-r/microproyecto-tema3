"""
Verificacion de src/features/build_features.

    python -m tests.test_features

Cada prueba de aqui existe por un error concreto que ya ocurrio. No son
pruebas decorativas: son las que impiden que vuelva a pasar.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.build_features import (
    REF_FIN,
    REF_INICIO,
    agregar_canal,
    agregar_endemico,
    agregar_etiqueta,
    agregar_rezagos,
    agregar_rolling,
    columnas_predictoras,
)

fallos: list[str] = []


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    print(f"  {'ok   ' if condicion else 'FALLA'} {nombre} {detalle}")
    if not condicion:
        fallos.append(nombre)


def panel_minimo(anios=range(2007, 2026), municipios=("68001", "76001")) -> pd.DataFrame:
    filas = []
    for m in municipios:
        for a in anios:
            for mes in range(1, 13):
                filas.append({"divipola": m, "anio": a, "mes": mes})
    df = pd.DataFrame(filas)
    rng = np.random.default_rng(1)
    df["casos_grave"] = rng.integers(0, 12, len(df))
    df["casos_clasico"] = rng.integers(0, 200, len(df))
    return df.sort_values(["divipola", "anio", "mes"]).reset_index(drop=True)


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
    # La primera fila de B no tiene mes anterior dentro de B: tiene que ser nula.
    check("la primera fila del segundo municipio es nula", pd.isna(b[0]), f"= {b[0]}")
    # La segunda solo puede haber visto los 100 casos de la primera fila de B.
    check("la segunda solo suma casos de su propio municipio", b[1] == 100.0, f"= {b[1]}")
    check("el tercero suma 100 + 200", b[2] == 300.0, f"= {b[2]}")


def test_rezagos_son_meses_calendario() -> None:
    print("\nlos rezagos son el mes calendario anterior, no la fila anterior")
    df = panel_minimo(anios=[2007, 2008], municipios=("68001",))
    df = agregar_rezagos(df, "casos_grave")
    # Con el panel completo, el rezago 1 de cada fila tiene que ser exactamente
    # el valor de la fila anterior en el tiempo.
    esperado = df["casos_grave"].shift(1)
    igual = df["casos_grave_lag_1"].iloc[1:].eq(esperado.iloc[1:]).all()
    check("lag_1 coincide con el mes anterior", bool(igual))
    check("la primera fila no tiene rezago", pd.isna(df["casos_grave_lag_1"].iloc[0]))
    check("lag_6 existe y arranca en la fila 7", pd.isna(df["casos_grave_lag_6"].iloc[5])
          and pd.notna(df["casos_grave_lag_6"].iloc[6]))


def test_endemico() -> None:
    print("\nendemicidad: diez anios con casos y doscientos acumulados")
    df = panel_minimo(municipios=("sostenido", "concentrado", "disperso", "tardio"))
    df["casos_clasico"] = 0

    dentro = df["anio"].between(REF_INICIO, REF_FIN)
    # Doce anios con casos y muchos acumulados: endemico.
    df.loc[(df.divipola == "sostenido") & dentro & (df.anio <= REF_INICIO + 11), "casos_clasico"] = 30
    # Mil casos pero concentrados en cinco anios: no llega a los diez anios.
    df.loc[(df.divipola == "concentrado") & dentro & (df.anio <= REF_INICIO + 4), "casos_clasico"] = 200
    # Catorce anios con casos pero solo uno al mes: no llega a los doscientos.
    df.loc[(df.divipola == "disperso") & dentro & (df.mes == 1), "casos_clasico"] = 1
    # Todos sus casos despues de la referencia: si se mirara la serie completa
    # saldria endemico.
    df.loc[(df.divipola == "tardio") & ~dentro, "casos_clasico"] = 500

    ref = df[dentro]
    marca = agregar_endemico(df.copy(), ref).groupby("divipola")["es_endemico"].first()
    check("doce anios con casos y 4.320 acumulados es endemico", marca["sostenido"] == 1)
    check("mil casos en cinco anios NO es endemico", marca["concentrado"] == 0)
    check("catorce anios con 14 casos NO es endemico", marca["disperso"] == 0)
    check("casos solo despues de la referencia NO es endemico", marca["tardio"] == 0)


def test_canal_y_etiqueta() -> None:
    print("\ncanal endemico y etiqueta de brote")
    df = panel_minimo(municipios=("68001", "76001", "99999"))
    # Un municipio sin un solo caso en la referencia, para forzar P75 = 0.
    df.loc[(df["divipola"] == "99999") & (df["anio"] <= REF_FIN), "casos_grave"] = 0
    df = agregar_rezagos(df, "casos_grave")
    ref = df[df["anio"].between(REF_INICIO, REF_FIN)]
    df = agregar_canal(df, ref)
    df = agregar_etiqueta(df)

    check("p25 nunca es mayor que p75", bool((df["p25"] <= df["p75"]).all()))
    check("la zona solo toma valores 0, 1 y 2",
          set(df["zona_canal_lag1"].unique()) <= {0, 1, 2})
    check("brote es exactamente casos_grave > p75",
          bool((df["brote"] == (df["casos_grave"] > df["p75"]).astype(int)).all()))
    check("brote_lag_1 es brote corrido un mes",
          bool((df.groupby("divipola")["brote"].shift(1).fillna(0).astype(int)
                == df["brote_lag_1"]).all()))
    check("no quedan nulos en la etiqueta", bool(df["brote"].notna().all()))

    # Con P75 = 0 no hay tres zonas: o hubo casos el mes pasado o no.
    solo_ceros = df[df["p75"] == 0]
    if len(solo_ceros):
        ok = solo_ceros["zona_canal_lag1"].isin([0, 1]).all()
        check("cuando p75 es 0, la zona nunca es 2", bool(ok))
    else:
        print("  (sin casos de p75 = 0 en este panel de prueba)")


def test_columnas_predictoras() -> None:
    print("\ncolumnas_predictoras deja fuera lo que no se puede usar")
    df = panel_minimo()
    df = agregar_rezagos(df, "casos_grave")
    ref = df[df["anio"].between(REF_INICIO, REF_FIN)]
    df = agregar_canal(df, ref)
    df = agregar_etiqueta(df)
    cols = columnas_predictoras(df)

    for prohibida in ("casos_grave", "brote", "anio", "mes", "divipola"):
        check(f"no incluye {prohibida}", prohibida not in cols)
    check("si incluye casos_grave_lag_1", "casos_grave_lag_1" in cols)
    check("si incluye p75", "p75" in cols)


def main() -> int:
    for fn in (
        test_rolling_no_cruza_municipios,
        test_rezagos_son_meses_calendario,
        test_endemico,
        test_canal_y_etiqueta,
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
