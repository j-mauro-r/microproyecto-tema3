# HU002 — Evidencia de implementación DWP

Fecha: 2026-09-02
Rama: `feature/hu002-monthly-upload-validation`
PR: [#22](https://github.com/j-mauro-r/microproyecto-tema3/pull/22)
Estado: **PASS**

## Resultado

HU002 recibe un CSV UTF-8/UTF-8-SIG de un único mes, exige exactamente una fila
de Bucaramanga y una de Cali, valida las 39 features numéricas del Champion y
produce un `ValidatedMonthlyUpload` en memoria. No calcula features ni carga o
ejecuta modelos. El endpoint conserva temporalmente `503 CHAMPION_NOT_READY`
después de una validación exitosa y nunca fabrica un `201 COMPLETED`.

## Fuente y auditoría del contrato Champion

Fuente complementaria: PR #12, head `74e385c3`:

- `model/xgb_clasico_meta.json`, blob Git `791f21d5`;
- `scripts/train_clasico_model.py`;
- `scripts/generate_predictions.py`;
- `scripts/calibrate_models.py`;
- `src/features/build_features.py`;
- inspección estática, sin deserializar, de los artefactos XGBoost.

La metadata define 39 features. Los 39 nombres aparecen en el mismo orden en
`xgb_clasico.pkl`, `xgb_clasico_T1.pkl`, `xgb_clasico_T2.pkl` y
`xgb_clasico_calibrated.pkl`. Los scripts consumen `model.feature_names_in_` o
el campo `features` del paquete calibrado. **No se encontró divergencia.**

Hashes SHA-256 observados:

- contrato ordenado (`"\n".join(feature_names)`):
  `786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba`;
- artefacto T+1 canónico: `ddc8f6eeaf1bc2af304d3759c783e88d58576937ce7c62148b4c9280bab93f9d`;
- artefacto T+2: `47bed65a6e4670b98ed682b3f13b718aa89321ad1ef7feb232a6e3c063278a91`.

La definición se centralizó en `api/app/domain/champion_feature_contract.py`
con versión `pr12-74e385c3`; validator, endpoint y tests no mantienen listas
paralelas.

### Features, en orden contractual

```text
temp_mean_c
dewpoint_mean_c
rain_mm_day
soil_water_l1_mean
surface_runoff_mm_day
total_evaporation_mm_day_ecmwf
wind_u_mean_ms
wind_v_mean_ms
solar_radiation_mj_m2_day
casos_grave_lag_1
casos_grave_lag_2
casos_grave_lag_3
casos_grave_lag_4
casos_grave_lag_6
casos_grave_roll3
casos_clasico_lag_1
casos_clasico_lag_2
casos_clasico_lag_3
casos_clasico_lag_4
casos_clasico_lag_6
casos_clasico_roll3
temp_mean_c_lag_1
temp_mean_c_lag_2
temp_mean_c_lag_3
rain_mm_day_lag_1
rain_mm_day_lag_2
rain_mm_day_lag_3
mes_sin
mes_cos
p25
p75
zona_canal
sir
es_endemico
brote
p25_objetivo
p75_objetivo
zona_objetivo
brote_lag_1
```

## Contrato CSV final

| Regla | Implementación |
|---|---|
| Formato | solo `.csv`, default productivo `(".csv",)` |
| Encoding | UTF-8 o UTF-8-SIG estricto |
| Identificadores | `divipola`, `anio`, `mes` |
| Periodo | todas las filas coinciden exactamente con `reference_month` |
| Granularidad | dos filas: una `68001` y una `76001` |
| Unicidad | sin municipio/mes duplicado ni municipio adicional |
| Features | las 39 anteriores, presentes y numéricas finitas |
| Faltantes | vacío, `NaN`, `inf` y `-inf` rechazados; no hay imputación |
| Prohibidas | `objetivo`, `casos_objetivo`, `anio_objetivo`, `mes_objetivo`, `es_inicio`, `__target_t2`, `observed_label` |
| Seguridad | límite configurable, nombre reducido a basename, lectura acotada |
| Trazabilidad | nombre, content type, tamaño y SHA-256 de bytes originales |

El resultado conserva solo identificadores + features requeridas en sus filas
efectivas. Ninguna columna auxiliar puede incorporarse accidentalmente al input
que recibirá HU003.

### Ejemplo sintético mínimo

El fixture automatizado genera exclusivamente datos contractuales de prueba:

```csv
divipola,anio,mes,<39 features en el orden contractual>
68001,2026,1,<39 valores numéricos sintéticos>
76001,2026,1,<39 valores numéricos sintéticos>
```

No representa observaciones epidemiológicas reales ni se versiona como dataset.

## T01–T12

| Tarea | Estado | Evidencia |
|---|---|---|
| T01 | PASS | fetch/switch/pull ff-only; regresión inicial 40 tests |
| T02 | PASS | metadata, scripts y artefactos PR #12 contrastados sin carga de modelo |
| T03 | PASS | contrato centralizado CSV/identificadores/features/targets |
| T04 | PASS | `anio+mes` exactos y un solo `reference_month` |
| T05 | PASS | exactamente 68001/76001, sin ausencias/extras/duplicados |
| T06 | PASS | 39 features obligatorias, numéricas, finitas y no nulas |
| T07 | PASS | siete targets/futuros rechazados y filas efectivas filtradas |
| T08 | PASS | tamaño, vacío, hash, envelope, request ID y CORS preservados |
| T09 | PASS | endpoint multipart delgado; validación delegada, sin modelo |
| T10 | PASS | 54 tests rápidos y offline |
| T11 | PASS | evidencia reemplazada por este documento |
| T12 | PASS | gates finales y diff focalizado |

## CA01–CA20

| CA | Estado | Evidencia |
|---|---|---|
| CA01 | PASS | health/OpenAPI/errores HU001 continúan verdes |
| CA02 | PASS | regex y mes calendario estricto |
| CA03 | PASS | cero bytes → `INVALID_UPLOAD` |
| CA04 | PASS | lectura HTTP corta al exceder límite |
| CA05 | PASS | solo `.csv` habilitado |
| CA06 | PASS | SHA-256 determinista probado |
| CA07 | PASS | nombre seguro, bytes, hash, periodo y content type |
| CA08 | PASS | cualquier feature faltante se rechaza |
| CA09 | PASS | string, vacío, NaN e infinitos se rechazan |
| CA10 | PASS | exactamente Buca+Cali, una fila por municipio |
| CA11 | PASS | todas las filas coinciden con el corte |
| CA12 | PASS | targets rechazados y resultado efectivo filtrado |
| CA13 | PASS | no cálculo ni imputación de features |
| CA14 | PASS | sin Champion, ML/cloud o persistencia |
| CA15 | PASS | request ID y `VALIDATING` contractuales |
| CA16 | PASS | CORS POST solo para allowlist |
| CA17 | PASS | válido → 503 temporal, nunca 201 ficticio |
| CA18 | PASS | validator puro y reusable |
| CA19 | PASS | suite completa offline |
| CA20 | PASS | diff limitado a HU002 |

Resultado: **20 PASS, 0 FAIL, 0 BLOCKED**.

## AV01–AV20

| AV | Estado | Evidencia |
|---|---|---|
| AV01 | PASS | regresión HU001 incluida |
| AV02 | PASS | settings y default `.csv` probados |
| AV03 | PASS | enero y diciembre válidos |
| AV04 | PASS | meses inválidos rechazados |
| AV05 | PASS | vacío rechazado |
| AV06 | PASS | oversized rechazado |
| AV07 | PASS | CSV válido y XLSX rechazado |
| AV08 | PASS | hash igual/diferente comprobado |
| AV09 | PASS | CSV/UTF-8 corrupto controlado |
| AV10 | PASS | feature retirada produce `missing_columns` |
| AV11 | PASS | feature inválida produce `invalid_numeric_features` |
| AV12 | PASS | válido, faltantes, duplicado y tercero probados |
| AV13 | PASS | fila de otro mes rechazada |
| AV14 | PASS | targets rechazados antes de resultado efectivo |
| AV15 | PASS | request ID coincide entre header/envelope |
| AV16 | PASS | CORS permitido/denegado probado |
| AV17 | PASS | import limpio sin MLflow/DVC/AWS/modelos |
| AV18 | PASS | validación solo en memoria; árbol permanece limpio |
| AV19 | PASS | carga válida sin éxito/predicción ficticia |
| AV20 | PASS | alcance revisado con diff contra main |

Resultado: **20 PASS, 0 FAIL, 0 BLOCKED**.

## Comandos y resultados

```text
git fetch origin --prune                                      PASS
git switch feature/hu002-monthly-upload-validation           PASS
git pull --ff-only origin feature/hu002-monthly-upload-validation PASS
python -m pytest api/tests -q                                 54 passed, 1 warning
python -m compileall -q api                                   PASS
python -m pip check                                           No broken requirements found
git diff --check main...HEAD                                  PASS
git diff --name-only main...HEAD                              alcance HU002 esperado
```

La advertencia única es `StarletteDeprecationWarning` de `TestClient`/`httpx` y
no afecta el contrato ni indica una dependencia rota.

## Limitaciones y gate HU003

- HU002 no interpreta MIME como prueba de contenido; extensión y parsing UTF-8
  real son autoritativos.
- El contrato proviene del artefacto temporal de PR #12; un nuevo Champion debe
  actualizar versión, lista/hash y pruebas de forma conjunta.
- HU003 recibirá bytes/filas ya validados y se limitará a seleccionar y ordenar
  estas features para construir `ChampionInput`.
- Lags, rolling, canal, SIR, `mes_sin`/`mes_cos` y demás feature engineering
  permanecen explícitamente postergados. HU002 solo valida valores precalculados.
- No se cargó/deserializó ningún pickle, no se ejecutó Champion y no se usaron
  MLflow, DVC, AWS/S3, datasets reales ni persistencia.

## Diff final

El cambio incremental de la nueva definición modifica únicamente contrato y
validator bajo `api/app/domain`, default CSV en configuración, tests HU002 y
esta evidencia. El diff total del PR conserva además la ruta multipart, wiring,
errores, dependencia `python-multipart` y la propia definición HU002. No hay
cambios en `src/`, `scripts/`, `model/`, datos, notebooks o frontend.
