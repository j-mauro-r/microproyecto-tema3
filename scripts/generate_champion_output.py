"""
Genera el JSON de salida del Champion hacia el backend BIOMAC.
Contrato: dashboard_prototipos/JSON-dashboard.md

Uso:
  python scripts/generate_champion_output.py                        # ultimo mes disponible
  python scripts/generate_champion_output.py --reference-month 2025-08
  python scripts/generate_champion_output.py --out champion_output.json
"""
import argparse
import hashlib
import json
import os
import pickle
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import date

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.dirname(__file__))
from model_utils import PlattCalibrator  # needed for pkl deserialization

ROOT      = os.path.join(os.path.dirname(__file__), "..")
DATA_PATH = os.path.join(ROOT, "data", "processed", "features_mensual.parquet")
MODEL_DIR = os.path.join(ROOT, "model")

CITIES = {"68001": "Bucaramanga", "76001": "Cali"}
PROHIBIDAS = {
    "divipola", "municipio", "departamento", "periodo",
    "anio", "mes", "casos_grave", "casos_clasico", "es_inicio",
    "objetivo", "casos_objetivo", "anio_objetivo", "mes_objetivo", "__target_t2",
}
MODEL_NAME = "biomac-champion"


@dataclass
class ModelPrediction:
    divipola: str
    municipality: str
    horizon: str
    target_month: str
    probability: float
    threshold: float
    label: str


@dataclass
class ChampionResult:
    model_name: str
    model_version: str
    reference_month: str
    feature_contract_version: str
    feature_contract_sha256: str
    output_type: str
    predictions: list


def _git_sha() -> str:
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, stderr=subprocess.DEVNULL,
        ).decode().strip()
        return f"pr12-{sha}"
    except Exception:
        return "pr12-unknown"


def _load_champion(horizonte: int):
    """Returns (model, calibrator, features, threshold)."""
    name = "xgb_clasico_calibrated.pkl" if horizonte == 1 else f"xgb_clasico_T{horizonte}_calibrated.pkl"
    path = os.path.join(MODEL_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Champion T+{horizonte} no encontrado: {path}")
    with open(path, "rb") as fh:
        pkg = pickle.load(fh)
    return pkg["model"], pkg["calibrator"], pkg["features"], float(pkg["best_threshold"])


def _validate(result: dict):
    preds = result["predictions"]
    assert len(preds) == 4, f"Se esperaban 4 predicciones, hay {len(preds)}"
    keys = {(p["divipola"], p["horizon"]) for p in preds}
    assert ("68001", "T+1") in keys, "Falta Bucaramanga T+1"
    assert ("68001", "T+2") in keys, "Falta Bucaramanga T+2"
    assert ("76001", "T+1") in keys, "Falta Cali T+1"
    assert ("76001", "T+2") in keys, "Falta Cali T+2"
    seen = set()
    for p in preds:
        key = (p["divipola"], p["horizon"])
        assert key not in seen, f"Prediccion duplicada: {key}"
        seen.add(key)
        assert 0.0 <= p["probability"] <= 1.0, f"probability fuera de [0,1]: {p['probability']}"
        assert 0.0 <= p["threshold"] <= 1.0,   f"threshold fuera de [0,1]: {p['threshold']}"
        expected_label = "EXCESO" if p["probability"] >= p["threshold"] else "NO_EXCESO"
        assert p["label"] == expected_label, (
            f"label inconsistente: prob={p['probability']} thr={p['threshold']} "
            f"label={p['label']} esperado={expected_label}"
        )
    json.dumps(result)  # must be JSON-serializable


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference-month", help="YYYY-MM (default: ultimo mes disponible)")
    parser.add_argument("--out", help="Archivo JSON de salida (default: stdout)")
    args = parser.parse_args()

    df = pd.read_parquet(DATA_PATH)
    feature_cols = [
        c for c in df.columns
        if c not in PROHIBIDAS and pd.api.types.is_numeric_dtype(df[c])
    ]

    if args.reference_month:
        ref_year, ref_month = map(int, args.reference_month.split("-"))
    else:
        latest = df[df["divipola"].astype(str).isin(CITIES)].sort_values(["anio", "mes"]).iloc[-1]
        ref_year, ref_month = int(latest["anio"]), int(latest["mes"])

    reference_month = f"{ref_year}-{ref_month:02d}"
    ref_rows = df[
        (df["anio"] == ref_year) &
        (df["mes"] == ref_month) &
        df["divipola"].astype(str).isin(CITIES)
    ]

    if ref_rows.empty:
        sys.exit(f"ERROR: sin datos para {reference_month} en Bucaramanga/Cali")

    m1, c1, f1, thr1 = _load_champion(1)
    m2, c2, f2, thr2 = _load_champion(2)

    version = _git_sha()
    fsha    = hashlib.sha256(",".join(f1).encode()).hexdigest()

    predictions = []
    for div in sorted(CITIES):
        city = CITIES[div]
        row = ref_rows[ref_rows["divipola"].astype(str) == div]
        if row.empty:
            print(f"AVISO: {city} ({div}) sin datos en {reference_month}", file=sys.stderr)
            continue
        for horizonte, model, cal, feats, thr in [
            (1, m1, c1, f1, thr1),
            (2, m2, c2, f2, thr2),
        ]:
            X      = row[feats].fillna(0)
            p_raw  = float(model.predict_proba(X)[:, 1][0])
            prob   = float(cal.transform(np.array([p_raw]))[0])
            t_date = date(ref_year, ref_month, 1) + relativedelta(months=horizonte)
            label  = "EXCESO" if prob >= thr else "NO_EXCESO"
            predictions.append(asdict(ModelPrediction(
                divipola=div,
                municipality=city,
                horizon=f"T+{horizonte}",
                target_month=t_date.strftime("%Y-%m"),
                probability=round(prob, 4),
                threshold=round(thr, 4),
                label=label,
            )))

    result = asdict(ChampionResult(
        model_name=MODEL_NAME,
        model_version=version,
        reference_month=reference_month,
        feature_contract_version=version,
        feature_contract_sha256=fsha,
        output_type="probability",
        predictions=predictions,
    ))

    _validate(result)

    json_str = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(json_str)
        print(f"Guardado: {args.out}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
