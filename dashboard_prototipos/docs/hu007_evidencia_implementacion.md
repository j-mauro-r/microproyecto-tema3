# HU007 — Evidencia de implementación

**Estado:** `[COMPLETADA — DESARROLLO]`

**Rama:** `docs/hu007-api-consulta-readonly`

**SHA base auditado:** `7abb7bdf` (el commit de implementación se identifica en el historial de la rama)

**Ámbito:** Entregable 2, local-only

## Baseline y resultado

Antes de implementar: `165 passed, 1 warning in 1.22s`. La validación final se
cerró con `29 passed, 1 warning in 0.52s` en la suite focal y `194 passed,
1 warning in 1.69s` en la suite completa. `compileall` terminó sin salida/error y
`pip check` reportó `No broken requirements found`. El único warning conocido es
`StarletteDeprecationWarning` de FastAPI `TestClient`/httpx.

## Arquitectura implementada

```text
FastAPI GET
  → RunQueryService / PredictionQueryService
  → PredictionQueryRepository
  → SQLitePredictionQueryRepository (mode=ro + PRAGMA query_only)
  → DTOs estrictos
  → JSON
```

- `api/app/api/v2/queries.py`: endpoints delgados.
- `api/app/query/service.py`: validación, semántica y mapping framework-neutral.
- `api/app/schemas/read_models.py`: DTOs `extra=forbid`.
- `api/app/persistence/sqlite.py`: único lugar con SQL de consulta.
- `api/app/main.py`: composición por `BIOMAC_DB_PATH`, independiente del Champion.
- `api/tests/test_read_queries.py`: comportamiento, errores y ausencia de efectos.
- `api/tests/test_health.py`: contrato OpenAPI actualizado.

## Endpoints y contratos

### `GET /api/v2/runs/{run_id}`

Recupera `COMPLETED` o `FAILED` con stages, timestamps, hash, versión Champion y
error saneado. Un run inexistente produce `404 RUN_NOT_FOUND`.

### `GET /api/v2/predictions/latest`

Acepta `municipality_codes` y `horizons` repetibles o CSV, con defaults de ambas
ciudades y ambos horizontes. Selecciona únicamente `COMPLETED` compatibles por
`completed_at DESC, run_id DESC`, y filtra el snapshot sin recalcular nada. Sin
resultado devuelve `404 PREDICTION_NOT_FOUND`.

### `GET /api/v2/predictions/history`

Acepta municipio, `horizon`, `from_month`, `to_month`, `limit` (20, 1..100) y
`offset` (0, >=0). Solo incluye `COMPLETED`, ordenados por `reference_month`,
`completed_at`, `run_id` descendentes. Aplica paginación a runs/snapshots. Vacío
devuelve `200`, `items=[]` y `returned=0`.

Las respuestas preservan exactamente `probability`, `expected_cases`,
`risk_score`, `label` y `decision_threshold`, incluidos `None` y thresholds
independientes. No incorporan P25/P50/P75, canal endémico, data quality, SHAP,
explanation, uncertainty ni historia sintética.

## Errores

- filtros inválidos: `400 INVALID_REQUEST` con razón estable;
- run ausente: `404 RUN_NOT_FOUND`;
- latest ausente: `404 PREDICTION_NOT_FOUND`;
- storage inaccesible: `500 PERSISTENCE_FAILED` saneado.

No se exponen SQL, stack traces o rutas locales.

## Cero inferencia y cero escrituras

Los tests instalan spies que fallarían si fueran llamados y ejecutan los tres GET:
cero llamadas al orquestador y al Champion. Antes y después comparan todos los
`run_id/status` y el conteo de predicciones: no hay cambios. El repositorio usa
URI SQLite `mode=ro` y `PRAGMA query_only`, por lo que tampoco puede escribir.

Una prueba de imports verifica que el query path no carga `xgboost`, `lightgbm`,
`mlflow`, `dvc` ni `boto3`.

## Criterios de aceptación

| Criterio | Resultado | Evidencia |
|---|---|---|
| CA01–CA05 | PASS | baseline, tres rutas, COMPLETED/FAILED y 404 run |
| CA06–CA11 | PASS | solo COMPLETED, orden/desempate, defaults, filtros y latest vacío |
| CA12–CA18 | PASS | history COMPLETED, orden, rango, filtros, paginación y errores 400 |
| CA19–CA24 | PASS | spies, DB inmutable, nullable real, SQL aislado, sin cloud y suite |

## Autovalidaciones

| Autovalidación | Resultado |
|---|---|
| AV01–AV05 | PASS — runs, 404, latest y FAILED no desplaza |
| AV06–AV10 | PASS — ciudad, horizonte y latest vacío |
| AV11–AV17 | PASS — orden, rango, paginación, vacío y validaciones |
| AV18–AV20 | PASS — cero inferencia/escritura e imports limpios |
| AV21–AV22 | PASS — compileall, pip check y suite completa |

## Comandos

```bash
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m pytest api/tests/test_read_queries.py -q
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m compileall -q api/app api/tests
.venv/bin/python -m pip check
```

## Pendientes HU008/HU009

HU008 puede consumir los tres GET, especialmente `latest` para apertura y
Refresh. HU009 debe añadir únicamente desde fuentes reales data quality,
current status, explicación y metadata/historia adicional, además de evolucionar
la respuesta mínima hacia `forecasts` si corresponde.

Confirmación explícita: HU007 no agrega AWS, EC2, S3, RDS, Supabase, Docker, DVC
runtime, MLflow serving, autenticación, Lovable/React, SHAP, feature engineering,
entrenamiento, inferencia ni servicios externos.
