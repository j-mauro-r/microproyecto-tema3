"""
Pipeline de feature engineering — granularidad MENSUAL.
Correcciones aplicadas:
  - DIVIPOLA como clave de municipio (COD_DPTO_O + COD_MUN_O)
  - Canal endemico: ref 2007-2021, fix zona cuando P75=0
  - SIR: ref 2007-2021
  - Clima ERA5/CHIRPS por divipola (gee_environment_mensual.csv)
Uso:
    python src/features/build_features.py [--grave PATH] [--clasico PATH] [--gee PATH] [--output PATH]
"""
import argparse
import os
import numpy as np
import pandas as pd

GRAVE_CSV   = "data/processed/sivigila_dengue_grave_consolidado.csv"
CLASICO_CSV = "data/processed/sivigila_dengue_consolidado.csv"
GEE_CSV     = "data/processed/gee_environment_mensual.csv"
OUTPUT_CSV  = "data/processed/dengue_features_modelado.csv"

LAGS      = [1, 2, 3, 4, 6]
ROLL_WIN  = 3
REF_START = 2007
TRAIN_END = 2021

CLIMATE_COLS = [
    "rain_mm_day", "temp_mean_c", "dewpoint_mean_c",
    "soil_water_l1_mean", "solar_radiation_mj_m2_day", "wind_speed_ms",
]


def agg_monthly(df, col):
    df = df.copy()
    df["COD_DPTO_O"] = df["COD_DPTO_O"].astype(int)
    df["COD_MUN_O"]  = df["COD_MUN_O"].astype(int)
    df["divipola"]   = (df["COD_DPTO_O"].astype(str).str.zfill(2) +
                        df["COD_MUN_O"].astype(str).str.zfill(3))
    df["MES"] = pd.to_datetime(df["FEC_NOT"], errors="coerce").dt.month
    df = df.dropna(subset=["MES"])
    df["MES"] = df["MES"].astype(int)
    return (
        df.groupby(["divipola", "COD_DPTO_O", "COD_MUN_O",
                    "Departamento_ocurrencia", "ANO", "MES"])
        .size()
        .reset_index(name=col)
    )


def load_and_aggregate(grave_path, clasico_path):
    grave   = pd.read_csv(grave_path,   low_memory=False)
    clasico = pd.read_csv(clasico_path, low_memory=False)
    wk_grave   = agg_monthly(grave,   "grave")
    wk_clasico = agg_monthly(clasico, "clasico")
    wk = pd.merge(
        wk_grave, wk_clasico,
        on=["divipola", "COD_DPTO_O", "COD_MUN_O",
            "Departamento_ocurrencia", "ANO", "MES"],
        how="outer"
    ).fillna(0)
    wk[["grave", "clasico"]] = wk[["grave", "clasico"]].astype(int)
    return wk


def add_lags(wk, col, lags):
    wk = wk.sort_values(["divipola", "ANO", "MES"]).reset_index(drop=True)
    grp = wk.groupby("divipola")[col]
    for lag in lags:
        wk[f"{col}_lag_{lag}"] = grp.shift(lag)
    return wk


def add_rolling(wk, col, window=ROLL_WIN):
    grp = wk.groupby("divipola")[col]
    wk[f"{col}_roll{window}"] = (
        grp.shift(1).rolling(window, min_periods=1).sum()
        .reset_index(0, drop=True)
    )
    return wk


def add_climate(wk, gee_path):
    gee = pd.read_csv(gee_path, low_memory=False)
    gee["divipola"] = gee["divipola"].astype(str).str.zfill(5)
    cols = [c for c in CLIMATE_COLS if c in gee.columns]
    wk = wk.merge(gee[["divipola", "ANO", "MES"] + cols],
                  on=["divipola", "ANO", "MES"], how="left")
    wk = wk.sort_values(["divipola", "ANO", "MES"]).reset_index(drop=True)
    for lag in [1, 2, 3]:
        wk[f"temp_lag_{lag}"] = wk.groupby("divipola")["temp_mean_c"].shift(lag)
        wk[f"rain_lag_{lag}"] = wk.groupby("divipola")["rain_mm_day"].shift(lag)
    return wk


def add_temporal(wk):
    wk["mes_sin"]       = np.sin(wk["MES"] * 2 * np.pi / 12)
    wk["mes_cos"]       = np.cos(wk["MES"] * 2 * np.pi / 12)
    wk["anio_epidemia"] = wk["ANO"] - REF_START
    return wk


def add_endemic_canal(wk):
    mask = wk.groupby("divipola")["grave"].apply(
        lambda x: (x > 0).sum() >= 3 and x.sum() >= 50
    )
    wk["es_endemico"] = wk["divipola"].map(mask).astype(int)

    ref = wk[wk["ANO"].between(REF_START, TRAIN_END)]
    canal = (
        ref.groupby(["divipola", "MES"])["grave"]
        .quantile([0.25, 0.75]).unstack()
        .reset_index()
        .rename(columns={0.25: "p25", 0.75: "p75"})
    )
    wk = wk.merge(canal, on=["divipola", "MES"], how="left")

    grave_lag1 = wk["grave_lag_1"].fillna(0)
    p25 = wk["p25"].fillna(0)
    p75 = wk["p75"].fillna(0)

    wk["zona_canal_lag1"] = np.where(
        p75 == 0,
        np.where(grave_lag1 == 0, 0, 1),
        np.where(grave_lag1 < p25, 0,
                 np.where(grave_lag1 < p75, 1, 2))
    )
    return wk


def add_sir(wk):
    ref = (
        wk[wk["ANO"].between(REF_START, TRAIN_END)]
        .groupby(["divipola", "MES"])["grave"]
        .mean().reset_index()
        .rename(columns={"grave": "expected_grave"})
    )
    wk = wk.merge(ref, on=["divipola", "MES"], how="left")
    wk["sir_lag1"] = wk["grave_lag_1"] / wk["expected_grave"].replace(0, float("nan"))
    wk = wk.drop(columns=["expected_grave"])
    return wk


def build(args):
    print("Agregando SIVIGILA mensual por DIVIPOLA...")
    wk = load_and_aggregate(args.grave, args.clasico)
    print(f"  {len(wk):,} filas | {wk['divipola'].nunique()} municipios")

    print("Agregando rezagos y rolling...")
    for col in ["grave", "clasico"]:
        wk = add_lags(wk, col, LAGS)
        wk = add_rolling(wk, col)

    if os.path.exists(args.gee):
        print("Agregando clima ERA5/CHIRPS mensual...")
        wk = add_climate(wk, args.gee)
    else:
        print("GEE no disponible — columnas null")
        for c in ["temp_mean_c", "rain_mm_day"] + \
                 [f"temp_lag_{l}" for l in [1,2,3]] + \
                 [f"rain_lag_{l}" for l in [1,2,3]]:
            wk[c] = float("nan")

    print("Agregando features temporales...")
    wk = add_temporal(wk)

    print("Agregando canal endemico (ref 2007-2021, fix P75=0)...")
    wk = add_endemic_canal(wk)

    print("Agregando SIR (ref 2007-2021)...")
    wk = add_sir(wk)

    FEATURE_COLS = (
        [f"grave_lag_{l}"   for l in LAGS] +
        [f"clasico_lag_{l}" for l in LAGS] +
        [f"grave_roll{ROLL_WIN}", f"clasico_roll{ROLL_WIN}"] +
        ["temp_mean_c", "temp_lag_1", "temp_lag_2", "temp_lag_3"] +
        ["rain_mm_day", "rain_lag_1", "rain_lag_2", "rain_lag_3"] +
        ["mes_sin", "mes_cos", "anio_epidemia", "ANO", "MES"] +
        ["es_endemico", "zona_canal_lag1", "p25", "p75", "sir_lag1"]
    )
    IDS = ["divipola", "COD_MUN_O", "Departamento_ocurrencia", "ANO", "MES"]
    actual_ids = [c for c in IDS if c in wk.columns]

    keep = list(dict.fromkeys(actual_ids + ["grave"] + FEATURE_COLS))
    keep = [c for c in keep if c in wk.columns]
    out  = wk[keep].reset_index(drop=True)

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    out.to_csv(args.output, index=False)
    print(f"Dataset guardado: {args.output} ({len(out):,} filas x {len(out.columns)} cols)")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--grave",   default=GRAVE_CSV)
    parser.add_argument("--clasico", default=CLASICO_CSV)
    parser.add_argument("--gee",     default=GEE_CSV)
    parser.add_argument("--output",  default=OUTPUT_CSV)
    args = parser.parse_args()
    build(args)
