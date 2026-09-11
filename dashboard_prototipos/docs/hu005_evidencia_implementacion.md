# HU005 — Evidencia de implementación

**Fecha:** 2026-09-03
**Estado:** `[COMPLETADA — DESARROLLO]`
**Ámbito:** local-only; sin AWS ni persistencia durable

## Flujo implementado

```text
MonthlyRunCommand → MonthlyPredictionOrchestrator
→ MonthlyUploadValidator (HU002)
→ ChampionOperationalContext → ChampionService (HU004)
→ ChampionOutput → ResultMapper
→ PredictionSnapshotCandidate
→ MonthlyRunResult READY_TO_PERSIST
```

Ante fallos, el resultado termina `FAILED`, conserva código/etapa y no ejecuta etapas
posteriores. Los errores inesperados se saneán. `COMPLETED` queda reservado para HU006.

## Decisiones

- `RunStatus` se extendió compatiblemente con `MAPPING` y `READY_TO_PERSIST`.
- Se creó `PredictionSnapshotCandidate`: el snapshot HTTP final exige datos de calidad,
  canal y estado epidemiológico que HU005 no posee; no se fabricaron placeholders.
- La clave lógica es SHA-256 determinista de periodo, hash fuente y versión Champion,
  sin estado global ni garantía durable.
- `RunRepository` y `PredictionRepository` son solo Protocols para HU006.
- El endpoint válido sigue en 503 hasta HU006, ahora con
  `PERSISTENCE_FAILED/PERSISTING`, no con el placeholder `CHAMPION_NOT_READY`.
- HU005 solo conoce `ChampionService`, `ChampionOperationalContext` y `ChampionOutput`.

## Archivos modificados

- `api/app/orchestration/__init__.py`
- `api/app/orchestration/monthly.py`
- `api/app/orchestration/ports.py`
- `api/app/schemas/runs.py`
- `api/app/schemas/errors.py`
- `api/app/api/v2/monthly_runs.py`
- `api/tests/test_monthly_orchestrator.py`
- `api/tests/test_monthly_runs.py`
- `dashboard_prototipos/docs/hu005_orquestacion_run_mensual.md`
- `dashboard_prototipos/docs/hu005_evidencia_implementacion.md`

## Criterios de aceptación CA01–CA22

| CA | Estado | Evidencia |
|---|---|---|
| CA01 | PASS | baseline: 134 pruebas |
| CA02 | PASS | orquestador framework-neutral implementado |
| CA03 | PASS | run_id generado por ejecución |
| CA04 | PASS | request_id preservado |
| CA05 | PASS | timestamps coherentes y UTC inyectables |
| CA06 | PASS | secuencia VALIDATING→PREPARING→INFERENCING→MAPPING |
| CA07 | PASS | única frontera ML: ChampionService |
| CA08 | PASS | sin imports/branching de estrategia HU004 |
| CA09 | PASS | ChampionOutput pasa por ResultMapper |
| CA10 | PASS | mapper solo copia datos demostrables |
| CA11 | PASS | probability/threshold/label preservados |
| CA12 | PASS | no se inventan horizontes |
| CA13 | PASS | key usa periodo+hash+versión |
| CA14 | PASS | key determinista y sensible a cada componente |
| CA15 | PASS | sin idempotencia durable/global |
| CA16 | PASS | fallo bloquea etapas posteriores |
| CA17 | PASS | códigos y etapas contractuales preservados |
| CA18 | PASS | errores inesperados saneados |
| CA19 | PASS | éxito termina READY_TO_PERSIST |
| CA20 | PASS | no existe storage productivo |
| CA21 | PASS | sin AWS/DVC/S3/MLflow/red |
| CA22 | PASS | suite verde y evidencia versionada |

## Autovalidaciones AV01–AV20

| AV | Estado | Resultado |
|---|---|---|
| AV01 | PASS | import limpio sin ML/cloud/storage |
| AV02 | PASS | contratos inmutables |
| AV03 | PASS | run_id verificable |
| AV04 | PASS | request_id preservado |
| AV05 | PASS | created < generated < finished |
| AV06 | PASS | secuencia de estados exacta |
| AV07 | PASS | ChampionService invocado una vez |
| AV08 | PASS | dependencia exclusiva de facade HU004 |
| AV09 | PASS | T+1/T+2 reales preservados |
| AV10 | PASS | thresholds 0.61/0.67 del fixture preservados |
| AV11 | PASS | expected_cases sin probability fabricada |
| AV12 | PASS | misma terna produce misma key |
| AV13 | PASS | cambio de periodo cambia key |
| AV14 | PASS | cambio de hash cambia key |
| AV15 | PASS | cambio de versión cambia key |
| AV16 | PASS | validación fallida evita Champion |
| AV17 | PASS | Champion fallido evita mapper |
| AV18 | PASS | sin escrituras o repositorios concretos |
| AV19 | PASS | pruebas focales y regresión pasan |
| AV20 | PASS | compileall y pip check pasan |

## Comandos y resultados

```text
.venv/bin/python -m pytest api/tests -q  # baseline
→ 134 passed, 1 warning in 0.89s

.venv/bin/python -m pytest api/tests/test_monthly_orchestrator.py api/tests/test_monthly_runs.py -q
→ 16 passed, 1 warning in 0.16s

.venv/bin/python -m pytest api/tests -q
→ 148 passed, 1 warning in 0.95s

.venv/bin/python -m compileall -q api/app api/tests
→ exit 0, sin salida

.venv/bin/python -m pip check
→ No broken requirements found.
```

La advertencia única es `StarletteDeprecationWarning` de la integración existente
FastAPI TestClient/httpx y no fue introducida por HU005.

## Pendientes HU006

1. Implementar repositorios durables para runs y snapshots.
2. Aplicar unicidad/idempotencia durable y resolver reintentos.
3. Persistir el candidato antes de pasar `READY_TO_PERSIST → COMPLETED`.
4. Componer el orquestador en el endpoint y habilitar `201 COMPLETED` solo tras guardar.
5. Implementar consultas `latest`, `history` y recuperación tras reinicio según alcance.

No se implementó ni simuló AWS, EC2, S3, deployment, SQLite, JSON durable o base de datos.
