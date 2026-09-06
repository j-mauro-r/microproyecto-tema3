"""
Arma el CSV de carga mensual que recibe el API a partir del panel de variables.

Toma las columnas del contrato del champion importandolas del propio API, de
modo que si el contrato cambia este script falla en vez de generar un archivo
que el validador rechace despues.

Uso:
    python scripts/generate_monthly_input.py --mes 2025-12
    python scripts/generate_monthly_input.py --mes 2025-12 --out carga.csv
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from api.app.domain.champion_feature_contract import (  # noqa: E402
    CHAMPION_FEATURES,
    IDENTIFIER_COLUMNS,
    PROHIBITED_INPUT_COLUMNS,
)

RAIZ = Path(__file__).resolve().parents[1]
PANEL = RAIZ / "data" / "processed" / "features_mensual.parquet"
CIUDADES = ["68001", "76001"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mes", required=True, help="Mes de referencia, formato AAAA-MM")
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--out", type=Path, default=RAIZ / "runtime" / "carga_mensual.csv")
    args = ap.parse_args(argv)

    anio, mes = (int(x) for x in args.mes.split("-"))
    df = pd.read_parquet(args.panel)
    df["divipola"] = df["divipola"].astype(str)

    filas = df[
        df["divipola"].isin(CIUDADES) & (df["anio"] == anio) & (df["mes"] == mes)
    ]
    if filas.empty:
        raise SystemExit(f"El panel no tiene filas de {args.mes} para {CIUDADES}")

    columnas = list(IDENTIFIER_COLUMNS) + list(CHAMPION_FEATURES)
    faltan = [c for c in columnas if c not in filas.columns]
    if faltan:
        raise SystemExit(f"Al panel le faltan columnas del contrato: {faltan}")

    salida = filas[columnas].copy()
    prohibidas = set(salida.columns) & PROHIBITED_INPUT_COLUMNS
    if prohibidas:
        raise SystemExit(f"Se colaron columnas prohibidas: {sorted(prohibidas)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    salida.to_csv(args.out, index=False)
    print(f"{len(salida)} filas, {len(columnas)} columnas -> {args.out}")
    print(salida[["divipola", "anio", "mes", "casos_clasico_lag_1", "p75", "brote"]].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
