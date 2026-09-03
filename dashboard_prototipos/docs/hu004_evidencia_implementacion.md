# HU004 — Evidencia de implementación del Champion Adapter

**Fecha:** 2026-09-03  
**Rama:** `docs/hu004-champion-adapter`  
**Alcance ejecutado:** desarrollo local y pruebas offline. No se ejecutaron tareas AWS.

## Resultado

Se implementó la frontera estable `ChampionInput → ChampionAdapter → ChampionOutput`,
sin dependencias públicas de frameworks ML. La composición productiva queda de forma
explícita en `CHAMPION_NOT_READY`: no existe en esta rama un Champion aprobado y
desplegable que pueda conectarse sin inventar metadata o comportamiento.

## Auditoría del Champion

Se auditó el árbol actual y el commit `74e385c3` usado por PR #12. El árbol actual no
contiene `.whl`, joblib/pickle o artefacto Champion materializado. PR #12 conserva
pickles XGBoost T+1/T+2 y `model/xgb_clasico_meta.json`, pero esa metadata solo describe
el objetivo T+1 y threshold `0.61`; no declara versión de paquete/artefacto, checksum,
hash/version del feature contract ni una API pública estable. Además,
`scripts/generate_predictions.py` recalcula thresholds para modelos raw usando el set de
validación, por lo que no es un contrato de serving aprobado.

Dependencias pendientes del equipo de modelado:

- paquete `.whl` o artefactos T+1/T+2 aprobados y materializables;
- entry point de carga/predicción estable compatible con `ChampionRuntime`;
- nombre, versión, horizontes y tipo de output contractuales;
- `feature_contract_version` y `feature_contract_sha256` coincidentes con HU003;
- threshold/regla de clase por horizonte, o confirmación explícita de ausencia;
- checksum del artefacto y metadata MLflow si aplica.

## Estado T01–T17

| Tarea | Estado | Evidencia |
|---|---|---|
| T01 | PASS | suite base: 71 pruebas antes del cambio |
| T02 | PASS | auditoría de árbol actual y PR #12 documentada |
| T03 | PASS | contratos inmutables en `api/app/champion/models.py` |
| T04 | PASS | `ChampionAdapter` Protocol en `port.py` |
| T05 | PASS | versión y SHA se validan antes de `runtime.predict` |
| T06 | PASS (frontera) / PENDIENTE (Champion real) | loader final y default NOT READY; no fake productivo |
| T07 | PASS | lazy loading protegido por `Lock`, una carga por adapter |
| T08 | PASS | mapeo explícito municipio/horizonte y mes objetivo determinista |
| T09 | PASS | errores estables y saneados |
| T10 | PASS | 11 pruebas HU004 offline |
| T11 | PASS | 82 pruebas, compileall y pip check exitosos |
| T12 | PASS | este documento |
| T13 | PENDIENTE/MANUAL | requiere entrega/materialización final de modelado |
| T14 | PENDIENTE/MANUAL AWS | no ejecutada por instrucción |
| T15 | PENDIENTE/MANUAL AWS | requiere Champion real en EC2 |
| T16 | PENDIENTE/MANUAL AWS | no se levantó Uvicorn/infraestructura EC2 |
| T17 | PASS | diff limitado a HU004, tests y evidencia |

## Criterios CA01–CA20

| Criterio | Estado | Nota |
|---|---|---|
| CA01 | PASS | baseline 71/71 |
| CA02 | PASS | API pública recibe solo `ChampionInput` |
| CA03 | PASS | puerto/modelos sin tipos ML |
| CA04 | PENDIENTE MODELADO | metadata real no fue entregada; no se fabricó |
| CA05 | PASS | versión/SHA compatibles permiten inferencia fake |
| CA06 | PASS | ambos mismatches bloquean con `CHAMPION_INPUT_INVALID` |
| CA07 | PASS | mapping explícito 68001/Bucaramanga, 76001/Cali |
| CA08 | PASS | fake multi-horizon genera claves explícitas |
| CA09 | PASS | fake T+1-only produce solo dos salidas T+1 |
| CA10 | PASS | probabilidades se preservan sin transformación |
| CA11 | PASS | adapter no convierte otros outputs a probabilidad |
| CA12 | PASS | threshold contractual 0.61 preservado |
| CA13 | PASS | sin threshold, threshold y label quedan `None` |
| CA14 | PASS | contador de loader permanece en uno |
| CA15 | PASS | default productivo devuelve `CHAMPION_NOT_READY` |
| CA16 | PASS | fallo runtime devuelve `INFERENCE_FAILED` saneado |
| CA17 | PASS | camino de predicción no usa DVC/S3/MLflow/red |
| CA18 | PASS | pruebas focales completamente offline |
| CA19 | PASS | AWS y materialización quedan separadas |
| CA20 | PASS | interfaz estable lista para orquestación HU005 |

## Autovalidaciones AV01–AV18

| AV | Estado | Resultado |
|---|---|---|
| AV01 | PASS | suite base verde |
| AV02 | PASS | imports de frontera inspeccionados |
| AV03 | PASS | asignación a output congelado falla |
| AV04 | PASS | mismatch de versión bloqueado |
| AV05 | PASS | mismatch de hash bloqueado |
| AV06 | PASS | orden y asociación municipal verificados |
| AV07 | PASS | cuatro salidas T+1/T+2 |
| AV08 | PASS | dos salidas T+1, cero T+2 |
| AV09 | PASS | 0.72/0.34 preservados |
| AV10 | PASS | 0.61 preservado, sin fallback 0.5 |
| AV11 | PASS | loader ausente produce NOT READY |
| AV12 | PASS | excepción runtime produce INFERENCE_FAILED |
| AV13 | PASS | carga única en tres usos |
| AV14 | PASS | suite sin credenciales ni red |
| AV15 | PASS | 82 pruebas pasan |
| AV16 | PASS | compileall exitoso |
| AV17 | PASS | sin dependencias rotas |
| AV18 | PASS | alcance auditado, sin HU005+ ni secretos |

## Comandos y resultados exactos

```text
python -m pytest api/tests -q
→ no ejecutable: `.python-version` solicita Python 3.13.12 no instalado.

.venv/bin/python -m pytest api/tests -q  (baseline)
→ 71 passed, 1 warning in 0.46s

.venv/bin/python -m pytest api/tests/test_champion_adapter.py -q
→ 11 passed, 1 warning in 0.02s

.venv/bin/python -m pytest api/tests -q
→ 82 passed, 1 warning in 0.46s

.venv/bin/python -m compileall -q api/app api/tests
→ exit 0, sin salida

.venv/bin/python -m pip check
→ No broken requirements found.
```

La advertencia única es `StarletteDeprecationWarning` de la integración existente
`fastapi.testclient`/`httpx`; no corresponde a HU004.

## Archivos cambiados

- `api/app/champion/__init__.py`
- `api/app/champion/adapter.py`
- `api/app/champion/models.py`
- `api/app/champion/port.py`
- `api/tests/test_champion_adapter.py`
- `dashboard_prototipos/docs/hu004_evidencia_implementacion.md`

## Tareas explícitas para Mauricio en AWS

1. Recibir y verificar checksum/contrato del artefacto definitivo (T13).
2. Provisionar/configurar EC2, instalar dependencias y materializar el artefacto fuera de
   requests; ejecutar `dvc pull` solo durante deployment si aplica (T14).
3. Conectar un `ChampionLoader` real y ejecutar smoke test con Bucaramanga/Cali,
   registrando horizontes, probabilidades/clases y thresholds reales (T15).
4. Levantar Uvicorn, comprobar `/api/v2/health` y verificar readiness real (T16).

No se modificó `/monthly-runs`; continúa sin fabricar respuestas `COMPLETED`.
