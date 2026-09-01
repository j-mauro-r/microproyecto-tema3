"""
Particion temporal del panel.

    entrenamiento : 2007 - 2022
    prueba        : 2023 - 2025

La particion es temporal, no aleatoria. Repartir los meses al azar dejaria
datos de 2024 en entrenamiento y de 2015 en prueba, con lo que el modelo
aprenderia del futuro para predecir el pasado.

No hay un anio fijo de validacion. Los hiperparametros se escogen con
validacion cruzada temporal sobre el entrenamiento (folds_temporales), porque
en Bucaramanga y Cali los anios 2017, 2018, 2021 y 2022 no tienen ningun mes
por encima del canal endemico. Cualquier anio suelto puede quedarse sin
positivos y dejar la validacion sin nada que medir. Los folds vacios igual
sirven: miden falsas alarmas.

Cada fold recalcula el canal con su propia ventana de referencia
(build_features.aplicar_referencia con ref_fin = anio - 1). Un p75 calculado
hasta 2022 y usado para validar 2015 ya vio ocho anios de futuro, y como la
etiqueta es casos > p75, la fuga alcanzaria tambien a la etiqueta.

La prueba abarca 2023, 2024 y 2025 para cubrir los tres regimenes: subida,
epidemia (2024 es el anio con mas casos de la serie) y descenso. Con solo un
anio epidemico, un modelo que alerta siempre saldria bien.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import pandas as pd

ANIO_FIN_TRAIN = 2022
ANIOS_TEST = (2023, 2024, 2025)
ANIO_PRIMER_FOLD = 2015


@dataclass(frozen=True)
class ParticionTemporal:
    train: pd.DataFrame
    test: pd.DataFrame
    col_anio: str = "anio"

    def __iter__(self):
        return iter((self.train, self.test))

    @property
    def total(self) -> int:
        return len(self.train) + len(self.test)

    def rango(self, parte: str) -> tuple[int, int]:
        df = getattr(self, parte)
        if df.empty:
            return (0, 0)
        return (int(df[self.col_anio].min()), int(df[self.col_anio].max()))

    def resumen(self, col_objetivo: str | None = None) -> pd.DataFrame:
        filas = []
        for parte in ("train", "test"):
            df = getattr(self, parte)
            ini, fin = self.rango(parte)
            fila = {
                "particion": parte,
                "anios": "vacio" if not ini else (str(ini) if ini == fin else f"{ini}-{fin}"),
                "filas": len(df),
                "pct": round(100 * len(df) / max(self.total, 1), 1),
            }
            if col_objetivo and col_objetivo in df.columns and len(df):
                positivos = int(df[col_objetivo].sum())
                fila["positivos"] = positivos
                fila["tasa_positivos"] = round(100 * positivos / len(df), 2)
            filas.append(fila)

        tabla = pd.DataFrame(filas)
        print(tabla.to_string(index=False))

        if col_objetivo and col_objetivo in self.test.columns:
            if len(self.test) and self.test[col_objetivo].sum() == 0:
                print("  AVISO: la prueba no tiene positivos, no hay nada que evaluar")
        return tabla


def split_temporal(
    df: pd.DataFrame,
    anio_fin_train: int = ANIO_FIN_TRAIN,
    anios_test: tuple[int, ...] = ANIOS_TEST,
    col_anio: str = "anio",
) -> ParticionTemporal:
    """Separa entrenamiento y prueba por anio, fallando si el corte tiene fuga."""
    if col_anio not in df.columns:
        raise KeyError(f"El panel no tiene la columna '{col_anio}'")

    test = set(anios_test)
    invasores = {a for a in test if a <= anio_fin_train}
    if invasores:
        raise ValueError(
            f"Los anios {sorted(invasores)} quedarian en entrenamiento y en prueba"
        )

    anio = df[col_anio]
    p = ParticionTemporal(
        train=df[anio <= anio_fin_train].copy(),
        test=df[anio.isin(test)].copy(),
        col_anio=col_anio,
    )

    for parte in ("train", "test"):
        if getattr(p, parte).empty:
            raise ValueError(
                f"La particion '{parte}' quedo vacia. El panel va de "
                f"{int(anio.min())} a {int(anio.max())}"
            )

    anios_panel = {int(a) for a in anio.dropna().unique()}
    sin_usar = sorted(anios_panel - {a for a in anios_panel if a <= anio_fin_train} - test)
    if sin_usar:
        print(f"  aviso: los anios {sin_usar} no quedaron en ninguna particion")

    return p


def folds_temporales(
    df: pd.DataFrame,
    anio_primer_fold: int = ANIO_PRIMER_FOLD,
    anio_fin_train: int = ANIO_FIN_TRAIN,
    col_anio: str = "anio",
) -> Iterator[tuple[int, pd.DataFrame, pd.DataFrame]]:
    """
    Validacion cruzada temporal de ventana expansiva sobre el entrenamiento.

    Cada fold entrena con todos los anios anteriores y valida sobre uno solo.
    Devuelve (anio de validacion, entrenamiento, validacion).
    """
    if anio_primer_fold > anio_fin_train:
        raise ValueError(
            f"anio_primer_fold ({anio_primer_fold}) es posterior al fin del "
            f"entrenamiento ({anio_fin_train})"
        )
    for anio in range(anio_primer_fold, anio_fin_train + 1):
        train = df[df[col_anio] < anio]
        val = df[df[col_anio] == anio]
        if len(train) and len(val):
            yield anio, train, val


def verificar_sin_fuga(p: ParticionTemporal) -> None:
    """Confirma que ningun anio aparece en entrenamiento y en prueba."""
    train = set(p.train[p.col_anio].unique())
    test = set(p.test[p.col_anio].unique())
    comun = train & test
    if comun:
        raise AssertionError(f"Los anios {sorted(comun)} estan en las dos particiones")
    if max(train) >= min(test):
        raise AssertionError("El entrenamiento no termina antes de la prueba")
