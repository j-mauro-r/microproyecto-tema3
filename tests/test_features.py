"""
Verificacion de src/features/build_features.

    python -m tests.test_features

Cada prueba corresponde a un error concreto que ya ocurrio, salvo la de
"nada ve el futuro", que es la red que deberia atrapar los que no han ocurrido.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.build_features import (
    NO_PREDICTORAS,
    REF_FIN,
    REF_INICIO,
    SERIE_OBJETIVO,
    agregar_endemico,
    agregar_rezagos,
    agregar_rolling,
    agregar_temporales,
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
    df["temp_mean_c"] = 20 + rng.random(len(df)) * 10
    df["rain_mm_day"] = rng.gamma(2, 2, len(df))
    return df.sort_values(["divipola", "anio", "mes"]).reset_index(drop=True)


def preparado(**kw) -> pd.DataFrame:
    df = panel_minimo(**kw)
    for col in ("casos_grave", "casos_clasico"):
        df = agregar_rezagos(df, col)
        df = agregar_rolling(df, col)
    for col in ("temp_mean_c", "rain_mm_day"):
        for r in (1, 2, 3):
            df[f"{col}_lag_{r}"] = df.groupby("divipola")[col].shift(r)
    return agregar_temporales(df)


def test_rolling_no_cruza_municipios() -> None:
    print("\nel rolling no se pasa de un municipio al siguiente")
    df = pd.DataFrame({
        "divipola": ["A"] * 5 + ["B"] * 5,
        "anio": [2007] * 10,
        "mes": list(range(1, 6)) * 2,
        "casos_grave": [1, 2, 3, 4, 5, 100, 200, 300, 400, 500],
    })
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


def test_canal() -> None:
    print("\ncanal endemico")
    df = preparado(municipios=("68001", "76001", "99999"))
    df.loc[(df["divipola"] == "99999") & (df["anio"] <= REF_FIN), SERIE_OBJETIVO] = 0
    df = aplicar_referencia(df)

    check("p25 nunca es mayor que p75", bool((df["p25"] <= df["p75"]).all()))
    check("la zona solo toma valores 0, 1 y 2", set(df["zona_canal"].unique()) <= {0, 1, 2})
    check("brote es el mes en curso por encima del p75",
          bool((df["brote"] == (df[SERIE_OBJETIVO] > df["p75"]).astype(int)).all()))
    ceros = df[df["p75"] == 0]
    check("cuando p75 es 0, la zona nunca es 2",
          bool(ceros["zona_canal"].isin([0, 1]).all()), f"({len(ceros)} filas)")


def test_umbral_del_mes_objetivo() -> None:
    """
    El canal es estacional: el umbral que hay que cruzar es el del mes que se
    predice, no el del mes en curso. Si los dos coincidieran, el baseline del
    canal y el de persistencia serian la misma regla.
    """
    print("\nel umbral del mes objetivo es el del mes que se predice")
    base = preparado(municipios=("68001", "76001"))

    for h in (1, 2):
        d = aplicar_referencia(base.copy(), horizonte=h)
        esperado = d.groupby("divipola")["p75"].shift(-h)
        hay = esperado.notna()
        check(f"con horizonte {h}, p75_objetivo es el p75 de t+{h}",
              bool(d.loc[hay, "p75_objetivo"].equals(esperado[hay])))

    d = aplicar_referencia(base.copy(), horizonte=1)
    check("zona_objetivo solo toma valores 0, 1 y 2",
          set(d["zona_objetivo"].unique()) <= {0, 1, 2})
    check("p25_objetivo nunca es mayor que p75_objetivo",
          bool((d["p25_objetivo"] <= d["p75_objetivo"]).all()))
    check("p75_objetivo entra como predictora", "p75_objetivo" in columnas_predictoras(d))


def test_horizonte() -> None:
    print("\nel horizonte es un parametro, no algo implicito")
    base = preparado(municipios=("68001",))

    for h in (1, 2, 3):
        d = aplicar_referencia(base.copy(), horizonte=h)
        esperado = d.groupby("divipola")["brote"].shift(-h)
        check(f"con horizonte {h}, objetivo es el brote de t+{h}",
              bool(d["objetivo"].equals(esperado)))
        check(f"  las ultimas {h} filas del municipio quedan sin etiqueta",
              bool(d["objetivo"].tail(h).isna().all()) and int(d["objetivo"].isna().sum()) == h)

    d3 = aplicar_referencia(base.copy(), horizonte=3)
    fila = d3[(d3["anio"] == 2020) & (d3["mes"] == 11)].iloc[0]
    check("noviembre de 2020 con horizonte 3 apunta a febrero de 2021",
          int(fila["anio_objetivo"]) == 2021 and int(fila["mes_objetivo"]) == 2,
          f"= {int(fila['anio_objetivo'])}-{int(fila['mes_objetivo']):02d}")

    d1 = aplicar_referencia(base.copy(), horizonte=1)
    check("cambiar el horizonte cambia la etiqueta",
          not d1["objetivo"].equals(d3["objetivo"]))

    try:
        aplicar_referencia(base.copy(), horizonte=0)
        check("horizonte 0 lanza error", False, "no lanzo error")
    except ValueError:
        check("horizonte 0 lanza error", True, "lanza ValueError")


def test_inicios() -> None:
    print("\ninicios de brote sobre el mes objetivo")
    d = aplicar_referencia(preparado(municipios=("68001",)), horizonte=1)
    con = d[d["objetivo"].notna()]
    # Con horizonte 1, el mes previo al objetivo es el mes de la fila.
    esperado = ((con["objetivo"] == 1) & (con["brote"] == 0)).astype(int)
    check("es_inicio es objetivo sin brote en el mes de la fila",
          bool(con["es_inicio"].astype(int).equals(esperado)))
    check("todo inicio tiene objetivo 1",
          bool(con.loc[con["es_inicio"] == 1, "objetivo"].eq(1).all()))
    check("sin etiqueta no hay inicio",
          bool(d.loc[d["objetivo"].isna(), "es_inicio"].isna().all()))


def test_nada_ve_el_futuro() -> None:
    """
    La red de seguridad. Se corrompe todo lo posterior a un corte y se exige
    que nada calculado hasta ese corte se mueva.
    """
    print("\nnada ve el futuro")
    corte = 2018
    base = preparado()

    sucio = base.copy()
    posterior = sucio["anio"] > corte
    for col in sucio.columns:
        if col in ("divipola", "anio", "mes"):
            continue
        if pd.api.types.is_numeric_dtype(sucio[col]):
            sucio.loc[posterior, col] = 999_999

    limpio_d = aplicar_referencia(base, ref_fin=corte)
    sucio_d = aplicar_referencia(sucio, ref_fin=corte)

    cols = columnas_predictoras(limpio_d)
    hasta_corte = limpio_d["anio"] <= corte
    distintas = [
        c for c in cols
        if not limpio_d.loc[hasta_corte, c].equals(sucio_d.loc[hasta_corte, c])
    ]
    check(f"ninguna de las {len(cols)} predictoras cambia en las filas hasta {corte}",
          not distintas, str(distintas[:6]))

    obj = limpio_d["anio_objetivo"] <= corte
    check("la etiqueta no cambia cuando el mes objetivo es anterior al corte",
          bool(limpio_d.loc[obj, "objetivo"].equals(sucio_d.loc[obj, "objetivo"])))
    check("es_inicio tampoco",
          bool(limpio_d.loc[obj, "es_inicio"].equals(sucio_d.loc[obj, "es_inicio"])))

    # Contraprueba: despues del corte si tiene que notarse, o la prueba de
    # arriba estaria pasando porque el corrompido no hizo nada.
    despues = limpio_d["anio"] > corte
    check("despues del corte los valores si cambian",
          not limpio_d.loc[despues, cols[0]].equals(sucio_d.loc[despues, cols[0]]))


def test_fold_no_pierde_meses() -> None:
    """
    Al recalcular la etiqueta sobre un recorte, la ultima fila de cada
    municipio se quedaba sin objetivo y el fold perdia observaciones.
    """
    print("\nun fold conserva los doce meses de cada municipio")
    from src.models.baseline import recalcular_fold

    municipios = ("68001", "76001")
    panel = preparado(municipios=municipios)
    for h in (1, 2):
        d = recalcular_fold(panel, 2018, h)
        val = d[d["anio_objetivo"] == 2018]
        check(f"con horizonte {h} el fold trae 12 meses por municipio",
              len(val) == 12 * len(municipios), f"= {len(val)}")
        check(f"  y ninguno se queda sin etiqueta",
              bool(val["objetivo"].notna().all()),
              f"({int(val['objetivo'].isna().sum())} sin etiqueta)")
        check(f"  ningun mes objetivo se sale de 2018",
              bool((val["anio_objetivo"] == 2018).all()))


def test_columnas_predictoras() -> None:
    print("\ncolumnas_predictoras deja fuera lo que no se puede usar")
    df = aplicar_referencia(preparado())
    cols = columnas_predictoras(df)

    for prohibida in sorted(NO_PREDICTORAS):
        if prohibida in df.columns:
            check(f"no incluye {prohibida}", prohibida not in cols)

    # Lo que el modelo si conoce al momento de predecir.
    for permitida in (SERIE_OBJETIVO, "brote", "zona_canal", "sir", "p75",
                      f"{SERIE_OBJETIVO}_lag_1", "temp_mean_c", "mes_sin"):
        check(f"si incluye {permitida}", permitida in cols)


def main() -> int:
    for fn in (
        test_rolling_no_cruza_municipios,
        test_rezagos_son_meses_calendario,
        test_endemico,
        test_canal,
        test_umbral_del_mes_objetivo,
        test_horizonte,
        test_inicios,
        test_nada_ve_el_futuro,
        test_fold_no_pierde_meses,
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
