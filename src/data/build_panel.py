"""
Construye el panel mensual de casos de dengue por municipio.

De los CSV crudos de SIVIGILA y de las variables climaticas produce un unico
archivo con una fila por municipio y mes, con los conteos de dengue clasico y
dengue grave y las variables climaticas promediadas al mes.

El panel se construye completo: los municipios-mes sin casos quedan en cero en
lugar de faltar, que es lo que necesita el canal endemico.

Uso:
    python -m src.data.build_panel
    python -m src.data.build_panel --sample 50000     # prueba rapida
    python -m src.data.build_panel --raw ruta/a/crudos --out ruta/salida.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Solo estas columnas de las 69 del archivo.
COLS_SIVIGILA = [
    "COD_DPTO_O",
    "COD_MUN_O",
    "Departamento_ocurrencia",
    "Municipio_ocurrencia",
    "ANO",
    "SEMANA",
    "FEC_NOT",
    "INI_SIN",
    "AJUSTE",
    "TIP_CAS",
]

ANIO_MIN = 2007
ANIO_MAX = 2025

# Codigos DANE de departamento. SIVIGILA usa COD_DPTO_O = 01 para casos
# importados del exterior, y ahi COD_MUN_O guarda el codigo ISO del pais
# (862 Venezuela, 076 Brasil, 604 Peru). El 00 es procedencia desconocida.
DEPARTAMENTOS_DANE = {
    "05", "08", "11", "13", "15", "17", "18", "19", "20", "23", "25", "27",
    "41", "44", "47", "50", "52", "54", "63", "66", "68", "70", "73", "76",
    "81", "85", "86", "88", "91", "94", "95", "97", "99",
}


# --------------------------------------------------------------------------- #
# Utilidades
# --------------------------------------------------------------------------- #

def construir_divipola(df: pd.DataFrame) -> pd.Series:
    """
    Devuelve el codigo DIVIPOLA de cinco digitos.

    COD_MUN_O es el consecutivo dentro del departamento, no una llave unica:
    el codigo 001 lo comparten Cali (76001), Bucaramanga (68001), Barranquilla
    (08001) y treinta municipios mas.
    """
    dpto = df["COD_DPTO_O"].astype("Int64").astype(str).str.zfill(2)
    mun = df["COD_MUN_O"].astype("Int64").astype(str).str.zfill(3)
    return (dpto + mun).where(df["COD_DPTO_O"].notna() & df["COD_MUN_O"].notna())


def parsear_fecha(serie: pd.Series) -> pd.Series:
    """
    Convierte las fechas de SIVIGILA a datetime.

    El formato es '16/09/2007 12:00:00 a. m.', dia/mes/anio. Sin declararlo,
    pandas cae a dateutil y asume mes/dia en todas las fechas con dia <= 12.
    """
    solo_fecha = serie.astype(str).str.split(" ").str[0]
    return pd.to_datetime(solo_fecha, format="%d/%m/%Y", errors="coerce")


def cargar_evento(ruta: Path, etiqueta: str, sample: int | None) -> pd.DataFrame:
    """Lee un CSV de SIVIGILA y devuelve una fila por caso con su mes y municipio."""
    if not ruta.exists():
        raise FileNotFoundError(f"No se encontro {ruta}")

    disponibles = pd.read_csv(ruta, nrows=0).columns
    usar = [c for c in COLS_SIVIGILA if c in disponibles]
    faltantes = set(COLS_SIVIGILA) - set(usar)
    if faltantes:
        print(f"  aviso: {ruta.name} no trae {sorted(faltantes)}")

    df = pd.read_csv(ruta, usecols=usar, nrows=sample, low_memory=False)
    print(f"  {etiqueta}: {len(df):,} registros leidos")

    df["divipola"] = construir_divipola(df)

    # Inicio de sintomas antes que fecha de notificacion, que depende del
    # retraso del sistema de vigilancia.
    fecha = parsear_fecha(df["INI_SIN"])
    if "FEC_NOT" in df.columns:
        fecha = fecha.fillna(parsear_fecha(df["FEC_NOT"]))

    df["anio"] = fecha.dt.year
    df["mes"] = fecha.dt.month

    antes = len(df)
    df = df.dropna(subset=["divipola", "anio", "mes"])
    sin_datos = antes - len(df)

    antes = len(df)
    df = df[df["anio"].between(ANIO_MIN, ANIO_MAX)]
    fuera_rango = antes - len(df)

    antes = len(df)
    df = df[df["divipola"].str[:2].isin(DEPARTAMENTOS_DANE)]
    no_municipio = antes - len(df)

    if sin_datos:
        print(f"    descartados {sin_datos:,} sin municipio o fecha valida")
    if fuera_rango:
        print(f"    descartados {fuera_rango:,} fuera de {ANIO_MIN}-{ANIO_MAX}")
    if no_municipio:
        print(f"    descartados {no_municipio:,} de exterior o procedencia desconocida")

    df["anio"] = df["anio"].astype(int)
    df["mes"] = df["mes"].astype(int)
    return df


def catalogo_municipios(*frames: pd.DataFrame) -> pd.DataFrame:
    """Tabla de referencia divipola -> nombre de municipio y departamento."""
    cols = ["divipola", "Municipio_ocurrencia", "Departamento_ocurrencia"]
    partes = [f[[c for c in cols if c in f.columns]] for f in frames]
    cat = pd.concat(partes, ignore_index=True).dropna(subset=["divipola"])
    cat = cat.drop_duplicates(subset=["divipola"], keep="first")
    return cat.rename(
        columns={
            "Municipio_ocurrencia": "municipio",
            "Departamento_ocurrencia": "departamento",
        }
    )


def contar_por_mes(df: pd.DataFrame, nombre: str) -> pd.DataFrame:
    return (
        df.groupby(["divipola", "anio", "mes"])
        .size()
        .rename(nombre)
        .reset_index()
    )


def panel_completo(divipolas, anio_min: int, anio_max: int) -> pd.DataFrame:
    """Todas las combinaciones municipio x anio x mes."""
    idx = pd.MultiIndex.from_product(
        [sorted(divipolas), range(anio_min, anio_max + 1), range(1, 13)],
        names=["divipola", "anio", "mes"],
    )
    return idx.to_frame(index=False)


# --------------------------------------------------------------------------- #
# Clima
# --------------------------------------------------------------------------- #

def cargar_clima(ruta: Path, sample: int | None) -> pd.DataFrame | None:
    """
    Agrega las variables climaticas a nivel municipio-mes.

    Soporta los dos formatos que ha manejado el equipo:

    - El de MODIS, con ADM2_CODE (codigo GAUL de la FAO) y lst_celsius. Ese
      codigo NO es DIVIPOLA, asi que no se puede cruzar por codigo y hay que
      recurrir al nombre, perdiendo municipios en el camino.
    - El de ERA5, con mpio_cdpmp (DIVIPOLA real) y varias variables. Este es el
      que conviene usar.
    """
    if not ruta.exists():
        print(f"  aviso: no se encontro {ruta}, el panel queda sin clima")
        return None

    cols = pd.read_csv(ruta, nrows=0).columns.tolist()

    if "mpio_cdpmp" in cols:
        return _clima_era5(ruta, cols, sample)
    if "ADM2_CODE" in cols:
        return _clima_modis(ruta, sample)

    print(f"  aviso: no reconozco el formato de {ruta.name}, columnas: {cols[:8]}")
    return None


def _clima_era5(ruta: Path, cols: list[str], sample: int | None) -> pd.DataFrame:
    numericas = [
        c
        for c in cols
        if c
        not in {
            "date", "year", "month", "day_of_year",
            "dpto_ccdgo", "dpto_cnmbr", "mpio_ccdgo", "mpio_cdpmp", "mpio_cnmbr",
        }
    ]
    usar = ["mpio_cdpmp", "date"] + numericas
    df = pd.read_csv(
        ruta, usecols=usar, nrows=sample, dtype={"mpio_cdpmp": str}, low_memory=False
    )
    print(f"  clima (ERA5): {len(df):,} filas, {len(numericas)} variables")

    fecha = pd.to_datetime(df["date"], errors="coerce")
    df["anio"] = fecha.dt.year
    df["mes"] = fecha.dt.month
    df = df.rename(columns={"mpio_cdpmp": "divipola"})
    df["divipola"] = df["divipola"].str.zfill(5)

    agg = (
        df.dropna(subset=["divipola", "anio", "mes"])
        .groupby(["divipola", "anio", "mes"])[numericas]
        .mean()
        .reset_index()
    )
    agg["anio"] = agg["anio"].astype(int)
    agg["mes"] = agg["mes"].astype(int)
    return agg


def _clima_modis(ruta: Path, sample: int | None) -> pd.DataFrame:
    valor = "lst_celsius"
    cols = pd.read_csv(ruta, nrows=0).columns
    if valor not in cols:
        valor = "mean"
    df = pd.read_csv(
        ruta,
        usecols=["ADM2_NAME", "fecha", valor],
        nrows=sample,
        encoding="latin-1",
        low_memory=False,
    )
    print(f"  clima (MODIS): {len(df):,} filas")
    print("    OJO: este archivo usa codigos GAUL, no DIVIPOLA. El cruce va por")
    print("    nombre de municipio y pierde alrededor del 20% de los municipios.")
    print("    Conviene migrar al archivo de ERA5.")

    fecha = pd.to_datetime(df["fecha"], errors="coerce")
    df["anio"] = fecha.dt.year
    df["mes"] = fecha.dt.month
    df["mun_key"] = normalizar_nombre(df["ADM2_NAME"])

    return (
        df.dropna(subset=["mun_key", "anio", "mes"])
        .groupby(["mun_key", "anio", "mes"])[valor]
        .mean()
        .rename("temp_superficie_c")
        .reset_index()
        .astype({"anio": int, "mes": int})
    )


def normalizar_nombre(serie: pd.Series) -> pd.Series:
    """Mayusculas sin tildes ni espacios sobrantes, para cruzar por nombre."""
    return (
        serie.astype(str)
        .str.upper()
        .str.normalize("NFKD")
        .str.encode("ascii", errors="ignore")
        .str.decode("utf-8")
        .str.strip()
    )


# --------------------------------------------------------------------------- #
# Principal
# --------------------------------------------------------------------------- #

def construir(raw: Path, salida: Path, sample: int | None = None) -> pd.DataFrame:
    print("Leyendo SIVIGILA")
    clasico = cargar_evento(raw / "dengue.csv", "dengue clasico", sample)
    grave = cargar_evento(raw / "dengue_grave.csv", "dengue grave", sample)

    cat = catalogo_municipios(clasico, grave)
    print(f"\nMunicipios distintos: {cat['divipola'].nunique():,}")

    print("\nArmando el panel")
    conteo_clasico = contar_por_mes(clasico, "casos_clasico")
    conteo_grave = contar_por_mes(grave, "casos_grave")

    municipios = set(conteo_clasico["divipola"]) | set(conteo_grave["divipola"])
    anio_min = int(min(conteo_clasico["anio"].min(), conteo_grave["anio"].min()))
    anio_max = int(max(conteo_clasico["anio"].max(), conteo_grave["anio"].max()))

    panel = panel_completo(municipios, anio_min, anio_max)
    panel = panel.merge(conteo_clasico, on=["divipola", "anio", "mes"], how="left")
    panel = panel.merge(conteo_grave, on=["divipola", "anio", "mes"], how="left")
    panel[["casos_clasico", "casos_grave"]] = (
        panel[["casos_clasico", "casos_grave"]].fillna(0).astype(int)
    )
    panel = panel.merge(cat, on="divipola", how="left")
    print(f"  {len(panel):,} filas ({panel['divipola'].nunique():,} municipios "
          f"x {anio_max - anio_min + 1} anios x 12 meses)")

    print("\nLeyendo clima")
    clima = cargar_clima(raw / "google_earth_engine.csv", sample)
    if clima is not None:
        if "divipola" in clima.columns:
            panel = panel.merge(clima, on=["divipola", "anio", "mes"], how="left")
            llave = "divipola"
        else:
            panel["mun_key"] = normalizar_nombre(panel["municipio"])
            panel = panel.merge(clima, on=["mun_key", "anio", "mes"], how="left")
            panel = panel.drop(columns=["mun_key"])
            llave = "nombre normalizado"
        cols_clima = [c for c in clima.columns if c not in
                      {"divipola", "mun_key", "anio", "mes"}]
        cobertura = panel[cols_clima[0]].notna().mean() * 100 if cols_clima else 0
        print(f"  cruzado por {llave}, cobertura {cobertura:.1f}%")

    panel = panel.sort_values(["divipola", "anio", "mes"]).reset_index(drop=True)
    panel["periodo"] = pd.to_datetime(
        dict(year=panel["anio"], month=panel["mes"], day=1)
    )

    salida.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(salida, index=False)
    print(f"\nGuardado {salida}  ({salida.stat().st_size / 1e6:.1f} MB)")

    resumen(panel)
    return panel


def resumen(panel: pd.DataFrame) -> None:
    print("\nResumen")
    print(f"  periodo            : {panel['anio'].min()} - {panel['anio'].max()}")
    print(f"  municipios         : {panel['divipola'].nunique():,}")
    print(f"  filas              : {len(panel):,}")
    print(f"  casos clasico      : {panel['casos_clasico'].sum():,}")
    print(f"  casos grave        : {panel['casos_grave'].sum():,}")
    print(f"  meses sin grave    : {(panel['casos_grave'] == 0).mean() * 100:.1f}%")

    for cod, nom in [("68001", "Bucaramanga"), ("76001", "Cali")]:
        s = panel[panel["divipola"] == cod]
        if s.empty:
            print(f"  {nom:12s}: no aparece en el panel")
            continue
        print(f"  {nom:12s}: {len(s)} meses | {s['casos_grave'].sum():,} graves | "
              f"{(s['casos_grave'] == 0).mean() * 100:.0f}% meses en cero")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw", type=Path, default=Path("data/raw"))
    ap.add_argument("--out", type=Path, default=Path("data/processed/panel_mensual.parquet"))
    ap.add_argument("--sample", type=int, default=None,
                    help="Leer solo N filas de cada archivo, para pruebas rapidas")
    args = ap.parse_args(argv)

    if args.sample:
        print(f"MODO PRUEBA: {args.sample:,} filas por archivo\n")

    construir(args.raw, args.out, args.sample)
    return 0


if __name__ == "__main__":
    sys.exit(main())
