"""
Entrenamiento y registro de experimentos en MLflow.

El modelo predice el CONTEO de casos del mes objetivo, no la etiqueta binaria.
Ese conteo se vuelve alerta comparandolo contra p75_objetivo, que es el mismo
umbral con el que se define la etiqueta y el mismo que usan los baselines. Asi
las tres cosas son comparables, y de paso el tablero puede mostrar el numero de
casos esperado y no solo un semaforo.

    modelo -> casos esperados en t+H -> alerta si superan el P75 de ese mes

Cada corrida se valida con la misma validacion cruzada temporal del baseline:
ocho folds de ventana expansiva, cada uno recalculando el canal con los anios
anteriores. Se registran las dos vistas de metricas, la agregada y la de
inicios de brote, mas los baselines como corridas aparte para que la
comparacion dentro de MLflow los incluya.

El servidor se indica con --tracking-uri o con la variable de entorno
MLFLOW_TRACKING_URI. Sin ninguna de las dos, escribe en ./mlruns y todo
funciona igual sin red.

Uso:
    python -m src.models.train --tracking-uri http://IP:5000
    python -m src.models.train --alphas 0.01 0.1 1 10
    python -m src.models.train --alphas 0.1 --umbrales 0.8 1 1.2 1.5 2
    python -m src.models.train --incluir-baselines
    python -m src.models.train --incluir-prueba        # una sola vez, al final
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import PoissonRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.evaluation.metrics import (
    inicios_vs_continuaciones,
    metricas_alerta,
    tabla_comparativa,
    tabla_inicios,
)
from src.evaluation.splits import ANIO_FIN_TRAIN, ANIO_PRIMER_FOLD, folds_temporales
from src.features.build_features import (
    REF_INICIO,
    SERIE_OBJETIVO,
    columnas_predictoras,
)
from src.models.baseline import (
    COL_ANIO,
    MUNICIPIOS,
    filas_de_fold,
    predicciones,
    puntajes,
)

EXPERIMENTO = "sat-dengue"
ALPHAS = [0.01, 0.1, 1.0, 10.0]

# Multiplicador del umbral de alerta. Con 1.0 se alerta cuando los casos
# esperados superan el P75 del mes objetivo, que es el mismo corte que define
# la etiqueta. Ese corte esta calibrado para la etiqueta, no para la
# prediccion: a horizontes largos el modelo predice por encima de el y emite
# de mas. Barrer este valor mueve el punto de operacion sin cambiar el modelo,
# y por eso el PR-AUC no se mueve con el, solo la sensibilidad y la precision.
UMBRALES = [1.0]


def construir_modelo(alpha: float) -> Pipeline:
    """
    Poisson regularizado sobre variables estandarizadas.

    La imputacion por mediana es para los rezagos de los primeros meses de cada
    municipio y para el SIR cuando el promedio historico es cero. El escalado
    importa porque el Poisson penaliza los coeficientes y sin escalar la
    penalizacion caeria distinto segun las unidades de cada variable.
    """
    return Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("escalar", StandardScaler()),
        ("poisson", PoissonRegressor(alpha=alpha, max_iter=2000)),
    ])


def alerta_desde_conteo(
    casos_esperados: np.ndarray, umbral: np.ndarray, k: float = 1.0
) -> tuple[np.ndarray, np.ndarray]:
    """
    Convierte el conteo predicho en alerta y en puntaje continuo.

    Se alerta cuando los casos esperados superan k veces el umbral del mes
    objetivo. El puntaje es cuantas veces se espera alcanzar ese umbral, sin
    el multiplicador: sirve para el PR-AUC, que necesita un orden y no una
    decision ya tomada, y se lee solo. 1,4 es "espero un 40% por encima de lo
    normal para ese mes".
    """
    seguro = np.where(umbral > 0, umbral, 1.0)
    return (casos_esperados > k * umbral).astype(int), casos_esperados / seguro


def evaluar_en_folds(df: pd.DataFrame, alpha: float, k: float,
                     horizonte: int, cols: list[str]) -> dict:
    """Entrena y valida fold por fold, y devuelve todo lo acumulado."""
    y_todos, pred_todos, score_todos, ini_todos = [], [], [], []
    por_fold = []
    coeficientes = None

    for anio, _, _ in folds_temporales(df, col_anio=COL_ANIO):
        train, val = filas_de_fold(df, anio, horizonte)
        train = train[train["casos_objetivo"].notna()]
        if train.empty or val.empty:
            continue

        modelo = construir_modelo(alpha)
        modelo.fit(train[cols], train["casos_objetivo"])
        esperados = modelo.predict(val[cols])
        pred, score = alerta_desde_conteo(esperados, val["p75_objetivo"].to_numpy(), k)

        y = val["objetivo"].to_numpy()
        y_todos.append(y)
        pred_todos.append(pred)
        score_todos.append(score)
        ini_todos.append(val["es_inicio"].to_numpy())

        fila = {"fold": anio, "ref": f"{REF_INICIO}-{anio - 1}",
                "train": len(train), "val": len(val),
                "brotes": int(y.sum()), "inicios": int(val["es_inicio"].sum())}
        if y.sum():
            r = metricas_alerta(y, pred, score)
            fila |= {k: round(r[k], 3) for k in
                     ("sensibilidad", "precision", "f1", "tasa_falsas_alarmas")}
        por_fold.append(fila)
        coeficientes = modelo.named_steps["poisson"].coef_

    return {
        "y": np.concatenate(y_todos),
        "pred": np.concatenate(pred_todos),
        "score": np.concatenate(score_todos),
        "inicio": np.concatenate(ini_todos),
        "por_fold": pd.DataFrame(por_fold),
        "coeficientes": coeficientes,
    }


def registrar(nombre: str, params: dict, res: dict, cols: list[str] | None = None) -> dict:
    """Una corrida de MLflow con sus parametros, metricas y artefactos."""
    metricas = metricas_alerta(res["y"], res["pred"], res.get("score"))
    inicios = inicios_vs_continuaciones(res["y"], res["pred"], res["inicio"])

    registrables = {
        k: v for k, v in metricas.items()
        if isinstance(v, (int, float)) and not (isinstance(v, float) and np.isnan(v))
    }
    registrables |= {f"ini_{k}": v for k, v in inicios.items()}
    if inicios["inicios"]:
        registrables["sens_inicios"] = inicios["inicios_detectados"] / inicios["inicios"]

    with mlflow.start_run(run_name=nombre):
        mlflow.log_params(params)
        mlflow.log_metrics(registrables)

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            if not res["por_fold"].empty:
                res["por_fold"].to_csv(tmp / "folds.csv", index=False)
                mlflow.log_artifact(str(tmp / "folds.csv"))
            if cols is not None and res.get("coeficientes") is not None:
                pesos = (
                    pd.DataFrame({"variable": cols, "coeficiente": res["coeficientes"]})
                    .assign(magnitud=lambda d: d["coeficiente"].abs())
                    .sort_values("magnitud", ascending=False)
                    .drop(columns="magnitud")
                )
                pesos.to_csv(tmp / "coeficientes.csv", index=False)
                mlflow.log_artifact(str(tmp / "coeficientes.csv"))
            (tmp / "variables.json").write_text(json.dumps(cols or [], indent=2))
            mlflow.log_artifact(str(tmp / "variables.json"))

    return metricas | {f"ini_{k}": v for k, v in inicios.items()}


def baselines_en_folds(df: pd.DataFrame, horizonte: int) -> dict[str, dict]:
    """Los mismos baselines del modulo baseline, sobre los mismos folds."""
    acum: dict[str, dict[str, list]] = {}
    inicios = []
    for anio, _, _ in folds_temporales(df, col_anio=COL_ANIO):
        _, val = filas_de_fold(df, anio, horizonte)
        if val.empty:
            continue
        inicios.append(val["es_inicio"].to_numpy())
        sc = puntajes(val)
        for nombre, pred in predicciones(val).items():
            a = acum.setdefault(nombre, {"y": [], "pred": [], "score": []})
            a["y"].append(val["objetivo"].to_numpy())
            a["pred"].append(pred)
            n = len(pred)
            a["score"].append(sc[nombre] if sc[nombre] is not None else np.full(n, np.nan))

    ini = np.concatenate(inicios)
    salida = {}
    for nombre, a in acum.items():
        score = np.concatenate(a["score"])
        salida[nombre] = {
            "y": np.concatenate(a["y"]),
            "pred": np.concatenate(a["pred"]),
            "score": None if np.isnan(score).all() else score,
            "inicio": ini,
            "por_fold": pd.DataFrame(),
        }
    return salida


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", type=Path,
                    default=Path("data/processed/features_mensual.parquet"))
    ap.add_argument("--tracking-uri", default=os.environ.get("MLFLOW_TRACKING_URI"))
    ap.add_argument("--experimento", default=EXPERIMENTO)
    ap.add_argument("--alphas", type=float, nargs="+", default=ALPHAS)
    ap.add_argument("--umbrales", type=float, nargs="+", default=UMBRALES,
                    help="Multiplicadores del P75 para disparar la alerta")
    ap.add_argument("--incluir-baselines", action="store_true",
                    help="Registrar tambien los baselines como corridas")
    ap.add_argument("--todos-los-municipios", action="store_true")
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
        alcance = ", ".join(MUNICIPIOS.values())
    else:
        alcance = f"{df['divipola'].nunique()} municipios"

    # Sin recortar por anio_objetivo: recalcular_fold necesita los meses del
    # anio validado para poder correr la etiqueta hacia adelante. Los folds solo
    # entrenan con anio_objetivo < anio y llegan hasta ANIO_FIN_TRAIN, asi que
    # la prueba nunca entra.
    cols = columnas_predictoras(df)

    if args.tracking_uri:
        mlflow.set_tracking_uri(args.tracking_uri)
    print(f"MLflow  : {mlflow.get_tracking_uri()}")
    print(f"Alcance : {alcance}")
    print(f"Horizonte {horizonte} mes(es), {len(cols)} variables, "
          f"objetivo {SERIE_OBJETIVO}")
    mlflow.set_experiment(args.experimento)

    resumen = {}

    if args.incluir_baselines:
        print("\nRegistrando baselines")
        for nombre, res in baselines_en_folds(df, horizonte).items():
            resumen[nombre] = registrar(
                nombre,
                {"modelo": "baseline", "regla": nombre, "horizonte": horizonte,
                 "alcance": alcance, "serie_objetivo": SERIE_OBJETIVO},
                res,
            )
            print(f"  {nombre}")

    for alpha in args.alphas:
        for k in args.umbrales:
            sufijo = f"_k{k:g}" if len(args.umbrales) > 1 or k != 1.0 else ""
            nombre = f"poisson_a{alpha:g}{sufijo}_h{horizonte}"
            print(f"\nEntrenando {nombre}")
            res = evaluar_en_folds(df, alpha, k, horizonte, cols)
            resumen[nombre] = registrar(
                nombre,
                {"modelo": "poisson", "alpha": alpha, "umbral_k": k,
                 "horizonte": horizonte, "alcance": alcance,
                 "serie_objetivo": SERIE_OBJETIVO, "n_variables": len(cols),
                 "ref_inicio": REF_INICIO,
                 "folds": f"{ANIO_PRIMER_FOLD}-{ANIO_FIN_TRAIN}",
                 "umbral": f"{k:g} x p75 del mes objetivo"},
                res, cols,
            )
            if not res["por_fold"].empty:
                print(res["por_fold"].to_string(index=False))

    print("\n" + "=" * 70)
    print("RESUMEN, agregado de los folds")
    print(tabla_comparativa(
        {k: {m: v for m, v in r.items() if not m.startswith("ini_")}
         for k, r in resumen.items()}
    ).to_string())
    print("\ninicios de brote")
    print(tabla_inicios(
        {k: {m[4:]: v for m, v in r.items() if m.startswith("ini_")}
         for k, r in resumen.items()}
    ).to_string())
    print(f"\nCorridas registradas en el experimento '{args.experimento}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
