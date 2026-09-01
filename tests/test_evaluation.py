"""
Verificacion de src/evaluation. No necesita pytest ni dependencias extra.

    python -m tests.test_evaluation

Los valores esperados de metricas_alerta se calcularon a mano sobre casos de
diez y seis observaciones, y ademas se contrastaron uno por uno contra
scikit-learn (precision_score, recall_score, f1_score, accuracy_score,
confusion_matrix y average_precision_score) antes de escribirlos aqui. Se dejan
fijos para que el test no dependa de sklearn, que no esta en requirements.txt.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from src.evaluation.metrics import (
    metricas_alerta,
    metricas_por_grupo,
    promedio_precision,
    tabla_comparativa,
)
from src.evaluation.splits import folds_temporales, split_temporal, verificar_sin_fuga

fallos: list[str] = []


def check(nombre: str, condicion: bool, detalle: str = "") -> None:
    print(f"  {'ok   ' if condicion else 'FALLA'} {nombre} {detalle}")
    if not condicion:
        fallos.append(nombre)


def cerca(a: float, b: float, tol: float = 1e-12) -> bool:
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    return abs(a - b) < tol


def test_metricas_caso_conocido() -> None:
    print("\nmetricas_alerta sobre un caso calculado a mano")
    #        i:  0  1  2  3  4  5  6  7  8  9
    y_real = [0, 0, 0, 0, 1, 1, 1, 0, 0, 1]
    y_pred = [0, 0, 1, 0, 1, 1, 0, 0, 1, 0]
    # verdaderos positivos en 4 y 5, falsos positivos en 2 y 8,
    # falsos negativos en 6 y 9, el resto verdaderos negativos.
    r = metricas_alerta(y_real, y_pred)
    esperado = {
        "n": 10,
        "brotes_reales": 4,
        "alertas_emitidas": 4,
        "vp": 2, "fp": 2, "vn": 4, "fn": 2,
        "sensibilidad": 0.5,          # 2 de los 4 brotes
        "precision": 0.5,             # 2 de las 4 alertas
        "f1": 0.5,
        "especificidad": 4 / 6,
        "tasa_falsas_alarmas": 2 / 6,
        "exactitud": 0.6,
        "tasa_base": 0.4,
    }
    for clave, valor in esperado.items():
        check(clave, cerca(float(r[clave]), float(valor)), f"= {r[clave]}")
    check("sin y_score no hay pr_auc", math.isnan(r["pr_auc"]))


def test_pr_auc() -> None:
    print("\npromedio_precision")
    # Ordenado por score: 1, 0, 1, 1, 0, 0
    # precision en cada positivo: 1/1, 2/3, 3/4  ->  (1 + 2/3 + 3/4) / 3
    y = [1, 0, 1, 1, 0, 0]
    s = [0.9, 0.8, 0.7, 0.4, 0.3, 0.1]
    check("caso conocido", cerca(promedio_precision(y, s), (1 + 2 / 3 + 3 / 4) / 3),
          f"= {promedio_precision(y, s):.6f}")

    # Un ranking perfecto da 1.0 sin importar el desbalance.
    check("ranking perfecto", cerca(promedio_precision([1, 1, 0, 0, 0], [.9, .8, .3, .2, .1]), 1.0))
    # Con todos los scores iguales, el modelo no ordena nada: queda la tasa base.
    check("todos empatados", cerca(promedio_precision([1, 0, 1, 0], [.5] * 4), 0.5))
    check("sin positivos da nan", math.isnan(promedio_precision([0, 0, 0], [.1, .2, .3])))


def test_metricas_degeneradas() -> None:
    print("\ncasos degenerados, que son los que rompen el codigo de verdad")
    y = [0] * 90 + [1] * 10

    nunca = metricas_alerta(y, [0] * 100)
    check("el que nunca alerta tiene exactitud 0.90", cerca(nunca["exactitud"], 0.90))
    check("  ...y sensibilidad 0", cerca(nunca["sensibilidad"], 0.0))
    check("  ...y precision indefinida", math.isnan(nunca["precision"]))
    check("  ...y f1 = 0", cerca(nunca["f1"], 0.0))

    siempre = metricas_alerta(y, [1] * 100)
    check("el que siempre alerta detecta todo", cerca(siempre["sensibilidad"], 1.0))
    check("  ...con 100% de falsas alarmas", cerca(siempre["tasa_falsas_alarmas"], 1.0))

    perfecto = metricas_alerta(y, y)
    check("prediccion perfecta da f1 = 1", cerca(perfecto["f1"], 1.0))


def test_validaciones() -> None:
    print("\nvalidaciones de entrada")
    casos = [
        ("longitudes distintas", lambda: metricas_alerta([0, 1], [0, 1, 1])),
        ("valores que no son 0/1", lambda: metricas_alerta([0, 1], [0, 5])),
        ("nulos", lambda: metricas_alerta([0, 1], [0, np.nan])),
    ]
    for nombre, fn in casos:
        try:
            fn()
            check(nombre, False, "no lanzo error")
        except ValueError:
            check(nombre, True, "lanza ValueError")


def _panel_falso() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n_anios = 2026 - 2007
    n = n_anios * 24
    return pd.DataFrame(
        {
            "anio": np.repeat(np.arange(2007, 2026), 24),
            "divipola": ["68001", "76001"] * (n // 2),
            "alerta": (rng.random(n) < 0.2).astype(int),
        }
    )


def test_split() -> None:
    print("\nsplit_temporal")
    panel = _panel_falso()
    p = split_temporal(panel)
    check("train 2007-2022", p.rango("train") == (2007, 2022))
    check("test 2023-2025", p.rango("test") == (2023, 2025))
    check("no se pierde ninguna fila", p.total == len(panel), f"{p.total} de {len(panel)}")
    check("prueba con 72 meses", len(p.test) == 72, f"{len(p.test)}")
    verificar_sin_fuga(p)
    check("verificar_sin_fuga no encuentra solapes", True)

    train, test = p
    check("se puede desempaquetar", len(train) + len(test) == len(panel))


def test_split_rechaza_cortes_malos() -> None:
    print("\nsplit_temporal rechaza cortes con fuga")
    panel = _panel_falso()
    casos = [
        ("anio de prueba dentro del entrenamiento", dict(anio_fin_train=2023)),
        ("particion vacia", dict(anios_test=(2030,))),
        ("columna de anio inexistente", dict(col_anio="year")),
    ]
    for nombre, kw in casos:
        try:
            split_temporal(panel, **kw)
            check(nombre, False, "no lanzo error")
        except (ValueError, KeyError):
            check(nombre, True, "lanza error")


def test_folds() -> None:
    print("\nfolds_temporales")
    panel = _panel_falso()
    folds = list(folds_temporales(panel))
    check("un fold por anio de 2015 a 2022", [f[0] for f in folds] == list(range(2015, 2023)))

    ok_creciente = all(len(folds[i][1]) < len(folds[i + 1][1]) for i in range(len(folds) - 1))
    check("la ventana de entrenamiento crece", ok_creciente)

    ok_orden = all(tr["anio"].max() < va["anio"].min() for _, tr, va in folds)
    check("cada fold entrena solo con anios anteriores", ok_orden)

    ok_val = all(va["anio"].nunique() == 1 for _, _, va in folds)
    check("cada validacion es un solo anio", ok_val)

    try:
        list(folds_temporales(panel, anio_primer_fold=2030))
        check("primer fold posterior al fin del train", False, "no lanzo error")
    except ValueError:
        check("primer fold posterior al fin del train", True, "lanza ValueError")


def test_tablas() -> None:
    print("\ntablas de salida")
    panel = _panel_falso()
    y = panel["alerta"].to_numpy()
    rng = np.random.default_rng(7)
    pred = (rng.random(len(panel)) < 0.25).astype(int)

    tabla = tabla_comparativa(
        {"nunca alerta": metricas_alerta(y, np.zeros_like(y)),
         "aleatorio": metricas_alerta(y, pred, rng.random(len(panel)))}
    )
    check("tabla_comparativa devuelve una fila por modelo", len(tabla) == 2)
    check("las columnas de conteo quedan enteras", tabla["vp"].dtype.kind in "iu")

    panel = panel.assign(pred=pred)
    por_mun = metricas_por_grupo(panel, "divipola", "alerta", "pred")
    check("metricas_por_grupo separa los dos municipios", len(por_mun) == 2)
    check("  ...y los meses cuadran", (por_mun["n"] == len(panel) // 2).all())


def main() -> int:
    for fn in (
        test_metricas_caso_conocido,
        test_pr_auc,
        test_metricas_degeneradas,
        test_validaciones,
        test_split,
        test_split_rechaza_cortes_malos,
        test_folds,
        test_tablas,
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
