# HU010 — Evidencia E2E y cierre de integración local

**Fecha:** 2026-09-03  
**Estado:** `BLOCKED` para cierre final por falta de golden real PR12  
**Rama / PR:** `docs/hu010-e2e-cierre-local` / `#32`  
**Base main:** `6d668cbc6676a51b07c657bc1cdd2033f3b8d402`  
**PR12:** `2f87422941c63ca3ea8dac485da5307fbaea11b9`  
**SHA de implementación HU010:** `0585ea3e` (el commit documental queda como tip del PR).

## Ambiente

- OS: `macOS-26.5.2-arm64-arm-64bit`
- Python: `3.12.11`
- Node: `v22.22.3`; npm: `10.9.8`
- `reference_month` automatizado: `2026-01`
- CSV controlado HU002 SHA-256:
  `2e70e86b25b0b2a3aa152922cd9df5bf35e3a67a66776d752b4223ca1bdead89`
- Resultado materializado controlado SHA-256 canónico:
  `b593e7112beee90e8decfc4a72978c8b8e1afab2d84378de321202d5a3f41996`

El resultado controlado vive en el test y valida el contrato/fronteras; **no es un
golden epidemiológico ni se presenta como salida real de PR12**.

## Baseline

- API: 202 passed, 1 warning en 2.45 s; compileall PASS; pip check limpio.
- Frontend: 5 archivos, 30 tests PASS en 881 ms; typecheck PASS.
- Lint: 0 errores, 9 warnings Fast Refresh heredados.
- Build: PASS; warnings conocidos `vite-tsconfig-paths` e `inlineDynamicImports`.

## Golden PR12

La rama PR12 conserva generador y modelos calibrados, pero no contiene
`data/processed/features_mensual.parquet`; tampoco existe una salida ChampionResult
real versionada. Por las reglas HU010 no se inventó ni adaptó un fixture.

```text
Generación ChampionResult real: BLOCKED
Golden real automatizado: BLOCKED
Procedimiento reproducible: dashboard_prototipos/docs/prueba-funcional-api.md
```

## E2E automatizado

`api/tests/test_e2e_local.py` usa FastAPI/TestClient, validator, ChampionService
materializado, orquestador, persistence service y SQLite temporal reales. Solo el
resolver Champion entrega un resultado contractual controlado.

| Escenario | Estado | Evidencia |
|---|---|---|
| E01 health | PASS | GET real 200 |
| E02 POST válido → COMPLETED | PASS | HTTP 201 posterior al commit SQLite |
| E03 Champion real PR12 ↔ API | BLOCKED | falta fuente parquet/salida real; comparación contractual de cuatro claves sí pasa |
| E04 SQLite | PASS | run, 4 predictions y cuatro tablas HU009 por mismo run_id |
| E05 latest | PASS | mismo run_id del POST |
| E06 history | PASS | contiene el run completado |
| E07 run detail | PASS | estado/corte/hash trazables |
| E08 idempotencia | PASS | POST idéntico devuelve mismo run; 1 run/4 predictions |
| E09 bytes diferentes | PASS | nuevo run; no sobrescribe; 2 runs/8 predictions |
| E10 inválidos | PASS | missing feature/city, prohibida, mes y NaN fallan antes de Champion |
| E11 Champion unavailable | PASS | 503 saneado; latest previo preservado |
| E12 restart | PASS | nueva app sobre misma DB devuelve mismo latest |
| E13 latest read-only | PASS | contador Champion no cambia tras GET |
| E14 history/run read-only | PASS | contador no cambia y DB no recibe snapshots nuevos |
| E15 frontend happy path | PASS | Vitest repository/hook/UI: latest, ciudades, horizontes y HU009 |
| E16 upload frontend | PASS | mutation exitosa refetchea latest e history |
| E17 Refresh frontend | PASS | latest-only; POST/history cero; stale snapshot preservado |
| E18 error frontend | PASS | snapshot anterior, mensaje saneado y retry sin mock |

## Correspondencia contractual controlada

| DIVIPOLA | Horizonte | Target | Probability | Threshold | Label |
|---|---|---:|---:|---:|---|
| 68001 | T+1 | 2026-02 | 0.72 | 0.61 | EXCESO |
| 68001 | T+2 | 2026-03 | 0.58 | 0.67 | NO_EXCESO |
| 76001 | T+1 | 2026-02 | 0.43 | 0.61 | NO_EXCESO |
| 76001 | T+2 | 2026-03 | 0.75 | 0.67 | EXCESO |

La prueba exige igualdad exacta entre provider, POST/latest y SQLite; no recalcula
ni usa 0.5. Estos números son control de integración, no evidencia epidemiológica.

## Frontend y corrección HU009

POST `COMPLETED` invalida en paralelo `latestPredictionKey` y
`predictionHistoryKey`. Los tests demuestran refetch de ambas queries. Error POST
no invalida ninguna. Refresh manual llama solo latest y no llama POST/history.

## Browser

No se agregó Playwright: `NOT_RUN`. La cobertura de integración frontend se ejecutó
con Vitest/Testing Library. La prueba navegador manual permanece documentada y no
se marca PASS automatizado.

## Performance observacional local

Una corrida aislada, sin SLO contractual:

| Operación | Tiempo observado |
|---|---:|
| health | 1.338 ms |
| POST mensual | 6.609 ms |
| latest | 4.046 ms |
| history | 1.567 ms |

## Resultados finales

- `.venv/bin/python -m pytest api/tests -q`: **210 passed, 1 warning in 2.51s**.
- `.venv/bin/python -m compileall -q api/app api/tests`: PASS.
- `.venv/bin/python -m pip check`: `No broken requirements found.`
- `npm test`: **5 archivos, 30 tests PASS**, 785 ms.
- `npm run typecheck`: PASS.
- `npm run lint`: PASS, 0 errores y 9 warnings Fast Refresh heredados.
- `npm run build`: PASS; warnings `vite-tsconfig-paths` e
  `inlineDynamicImports` ya documentados.
- Warning backend: `StarletteDeprecationWarning` por httpx/TestClient.

## CA01–CA35

| Criterios | Estado | Evidencia |
|---|---|---|
| CA01–CA02 | PASS | health y POST real sobre stack local controlado |
| CA03 | BLOCKED | no hay salida real PR12 reproducible en el checkout |
| CA04–CA10 | PASS | commit, latest/history/run, idempotencia, bytes distintos y restart |
| CA11–CA18 | PASS | uploads/fallo Champion saneados y contador read-only |
| CA19–CA25 | PASS | repository HTTP default, UI/hook, invalidaciones y nullability |
| CA26 | BLOCKED | procedimiento existe; golden real no disponible |
| CA27–CA30 | PASS | matriz final y git diff check |
| CA31–CA32 | PASS | E01–E18 versionados con estados honestos |
| CA33–CA35 | PASS | inspección de artefactos/secretos, cloud fuera de alcance y docs alineados |

## AV01–AV34

| AV | Estado | Evidencia |
|---|---|---|
| AV01–AV02 | PASS | baseline y SHAs registrados |
| AV03 | BLOCKED | falta CSV/ChampionResult real del mismo periodo PR12 |
| AV04 | BLOCKED | comparación real; comparación contractual controlada sí ejecutada |
| AV05–AV13 | PASS | SQL, idempotencia, inválidos, unavailable, restart y contador |
| AV14–AV17 | PASS | tests hook Refresh, invalidación latest/history y error POST |
| AV18–AV20 | PASS | DTO legacy/enriched, no fallback e inspección React |
| AV21–AV24 | PASS | suites, compileall/pip y diff check |
| AV25 | PASS | status/scan sin runtime/env/DB/CSV/parquet nuevos |
| AV26 | PASS | tiempos observados arriba |
| AV27–AV29 | PASS | GET sin ML/cloud, ErrorEnvelope e historial bien rotulado |
| AV30 | PASS | navegador `NOT_RUN`, no presentado como automatizado |
| AV31–AV32 | PASS | guía funcional e implementación actualizadas |
| AV33 | PASS | AWS/Lovable remoto `OUT_OF_SCOPE` |
| AV34 | BLOCKED | MVP local no puede cerrarse totalmente sin evidencia Champion real |

## Veredicto

La integración técnica local y todos sus escenarios controlados están verdes. El
veredicto HU010 permanece **BLOCKED**, no `[COMPLETADA]`, exclusivamente hasta que
se ejecute la guía PR12 con el dataset materializado y se capture un
ChampionResult real del mismo corte que el CSV. AWS/deployment es `OUT_OF_SCOPE`.
