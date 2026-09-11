# HU006 — Evidencia de implementación

**Estado:** `[COMPLETADA — DESARROLLO]`

**Rama:** `docs/hu006-persistencia-trazabilidad`

**SHA base auditado:** `25a4d2c1` (el commit que contiene esta evidencia se identifica en el historial de la rama)

**Ámbito:** Entregable 2, local-only

## Resultado

HU006 implementa la promoción durable
`READY_TO_PERSIST → PERSISTING → COMPLETED` mediante SQLite. Un fallo durante la
escritura revierte la transacción completa y se traduce a
`PERSISTENCE_FAILED/PERSISTING`. También conserva runs `FAILED` sin snapshot.

Baseline previo: `148 passed, 1 warning in 1.07s`. Resultado final: `165 passed,
1 warning`. El warning conocido es `StarletteDeprecationWarning` por el
`TestClient` de FastAPI/httpx y no corresponde a HU006.

## Archivos y arquitectura

- `api/app/persistence/service.py`: frontera transaccional e idempotencia durable.
- `api/app/persistence/sqlite.py`: unidad de trabajo, schema y repositorios SQLite.
- `api/app/persistence/__init__.py`: exports públicos.
- `api/app/orchestration/ports.py`: puertos sustituibles de runs/predicciones.
- `api/app/orchestration/monthly.py`: timestamp nullable `completed_at`.
- `api/app/api/v2/monthly_runs.py` y `api/app/main.py`: composición HU005/HU006 y `201` posterior al commit.
- `api/app/core/config.py` y `.gitignore`: `BIOMAC_DB_PATH` y exclusión de runtime.
- `api/tests/test_persistence.py`, `test_monthly_runs.py`, `test_upload_config.py`: cobertura HU006.
- `dashboard_prototipos/docs/{API-sign.md,arquitectura.md,implementacion.md}`: contrato y estado.

Flujo implementado:

```text
POST → MonthlyPredictionOrchestrator → READY_TO_PERSIST
     → MonthlyRunPersistenceService → SQLiteUnitOfWork
       ├─ RunRepository
       └─ PredictionRepository
     → COMMIT → COMPLETED → 201
```

HU005 no importa `sqlite3`; API/orquestación no contienen SQL. Los servicios se
inyectan en `create_app`, por lo que los repositorios pueden sustituirse.

## Configuración y schema real

`BIOMAC_DB_PATH` define la ruta. El default relativo es `runtime/biomac.db`; no
hay rutas absolutas hardcodeadas. Tests usan `tmp_path`. Git ignora `.db`,
`.sqlite`, `.sqlite3`, WAL y SHM.

`runs`: `run_id` PK; request/status/stages/reference/source/idempotency; metadata
Champion/feature contract; timestamps created/finished/completed/DB; error
code/stage/message. `idempotency_key` tiene `UNIQUE` y admite `NULL`.

`predictions`: FK `run_id → runs.run_id` con foreign keys activas; campos reales
de municipio, horizonte, target, output y valores nullable; restricción
`UNIQUE(run_id, divipola, horizon)`.

## Transacción, idempotencia y recovery

Cada éxito ejecuta `BEGIN IMMEDIATE`, inserta el run como `PERSISTING`, inserta
predicciones, actualiza a `COMPLETED` y hace commit. Cualquier excepción hace
rollback. La prueba de predicción duplicada fuerza un fallo después de insertar
el run y verifica ausencia total del run parcial y conservación del COMPLETED
anterior.

La clave de HU005 no cambió. El lookup durable y el constraint único devuelven el
COMPLETED existente ante reintento y no duplican filas. Cambiar hash o versión del
Champion permite un run nuevo. Una segunda instancia, abierta contra el mismo
archivo después de cerrar la primera, recupera run y cuatro predicciones.

## POST y gap contractual

Con HU005/HU006 compuestos, un POST válido responde `201` únicamente después de
recuperar el resultado committed como `COMPLETED`. Una falla DB responde `500`
saneado con `PERSISTENCE_FAILED/PERSISTING`. La respuesta transitoria conserva
solo datos reales del candidato. La estructura enriquecida `forecasts` queda para
HU007/HU009, tal como se documentó en `API-sign.md`.

## Criterios de aceptación

| Criterio | Resultado | Evidencia |
|---|---|---|
| CA01–CA06 | PASS | baseline, SQLite local configurable, gitignore, init idempotente y FK activa |
| CA07–CA12 | PASS | PK/UNIQUE, atomicidad, COMPLETED post-commit y rollback probado |
| CA13–CA18 | PASS | reintento, variantes hash/Champion, FAILED, preservación y segunda instancia |
| CA19–CA24 | PASS | desacople, POST 201/error, datos reales, sin cloud y suite verde |

## Autovalidaciones

| Autovalidación | Resultado |
|---|---|
| AV01–AV05 | PASS — DB/tablas/init, COMPLETED, run y snapshot recuperables |
| AV06–AV10 | PASS — cuatro predicciones, thresholds, retry, hash y Champion |
| AV11–AV15 | PASS — rollback, FAILED, recovery, FK y UNIQUE de predicción |
| AV16–AV20 | PASS — 201 post-commit, error saneado, preservación, imports y ausencia cloud |
| AV21–AV22 | PASS — suites focal/completa, compileall y pip check |

## Comandos ejecutados

```bash
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m pytest api/tests/test_persistence.py api/tests/test_monthly_runs.py -q
.venv/bin/python -m pytest api/tests/test_monthly_runs.py -q
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m compileall -q api/app api/tests
.venv/bin/python -m pip check
```

Conteos finales: focal HU006 + endpoint `20 passed`; endpoint `7 passed`; suite
completa `165 passed`. `compileall` termina sin salida/error y `pip check` reporta
`No broken requirements found`.

## Gate HU007 y exclusiones

HU007 queda habilitada para implementar `GET /runs/{run_id}`, `latest` e
`history` mediante las consultas por run, snapshot e idempotency key ya
disponibles. También deberá cerrar la representación HTTP enriquecida final.

Confirmación explícita: HU006 no incorpora AWS, EC2, S3, RDS, Supabase, DVC,
MLflow, llamadas de red, servicios externos, locks distribuidos ni deployment
cloud.
