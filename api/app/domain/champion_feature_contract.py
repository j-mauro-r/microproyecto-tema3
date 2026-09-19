"""Approved Champion input contract copied from PR #12 metadata.

This module contains data only: it never imports or loads the model artifact.
"""

from __future__ import annotations

import hashlib

CHAMPION_FEATURE_CONTRACT_SOURCE = (
    "PR #12 commit 74e385c3, model/xgb_clasico_meta.json blob 791f21d5"
)
CHAMPION_FEATURE_CONTRACT_VERSION = "pr12-74e385c3"

CHAMPION_FEATURES: tuple[str, ...] = (
    "temp_mean_c",
    "dewpoint_mean_c",
    "rain_mm_day",
    "soil_water_l1_mean",
    "surface_runoff_mm_day",
    "total_evaporation_mm_day_ecmwf",
    "wind_u_mean_ms",
    "wind_v_mean_ms",
    "solar_radiation_mj_m2_day",
    "casos_grave_lag_1",
    "casos_grave_lag_2",
    "casos_grave_lag_3",
    "casos_grave_lag_4",
    "casos_grave_lag_6",
    "casos_grave_roll3",
    "casos_clasico_lag_1",
    "casos_clasico_lag_2",
    "casos_clasico_lag_3",
    "casos_clasico_lag_4",
    "casos_clasico_lag_6",
    "casos_clasico_roll3",
    "temp_mean_c_lag_1",
    "temp_mean_c_lag_2",
    "temp_mean_c_lag_3",
    "rain_mm_day_lag_1",
    "rain_mm_day_lag_2",
    "rain_mm_day_lag_3",
    "mes_sin",
    "mes_cos",
    "p25",
    "p75",
    "zona_canal",
    "sir",
    "es_endemico",
    "brote",
    "p25_objetivo",
    "p75_objetivo",
    "zona_objetivo",
    "brote_lag_1",
)

CHAMPION_FEATURE_CONTRACT_SHA256 = hashlib.sha256(
    "\n".join(CHAMPION_FEATURES).encode("utf-8")
).hexdigest()

IDENTIFIER_COLUMNS: tuple[str, ...] = ("divipola", "anio", "mes")

# Labels and future outcomes excluded by the PR #12 training/generation code.
PROHIBITED_INPUT_COLUMNS: frozenset[str] = frozenset(
    {
        "objetivo",
        "casos_objetivo",
        "anio_objetivo",
        "mes_objetivo",
        "es_inicio",
        "__target_t2",
        "observed_label",
    }
)
