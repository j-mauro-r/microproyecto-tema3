# HU001 — Evidencia de implementación FastAPI base y contratos

**Rama:** `feature/hu001-fastapi-base-contracts`

**Base:** `main` actualizado en `4aefcddc` (PR #20 integrado)

**Fecha:** 2026-09-02

**Estado:** PASS, pendiente de revisión/merge del PR

## Alcance entregado

- Aplicación FastAPI v2 importable y sin inicialización de datos, modelos o servicios externos.
- Único endpoint productivo: `GET /api/v2/health`.
- Configuración centralizada desde defaults no sensibles y variables `BIOMAC_*`.
- CORS por allowlist explícita; wildcard rechazado.
- UUID backend por petición en `X-Request-ID` y contexto aislado.
- Handlers uniformes para validación, `HTTPException` y excepciones inesperadas.
- Contratos Pydantic estrictos de health, runs, Champion, snapshots y errores.
- OpenAPI 2.0.0 y 19 pruebas focalizadas sin red ni credenciales.

No se implementaron upload, inferencia, ChampionAdapter, servicios de preparación,
orquestación, persistencia, dashboard ni endpoints de HU002+.

## Dependencias

Se reutilizó `requirements.txt`. Se añadieron únicamente dependencias directas de HU001:

| Dependencia | Restricción | Justificación |
|---|---|---|
| FastAPI | `>=0.115,<1` | Frontera HTTP y OpenAPI |
| Uvicorn | `>=0.30,<1` | Ejecución local ASGI |
| pytest | `>=8,<10` | Suite focalizada |
| httpx | `>=0.27,<1` | Cliente HTTP de pruebas |

La validación local utilizó Python 3.12.11. `.python-version` declara 3.13.12,
no disponible localmente; no se cambió el runtime global porque no fue blocker.

Existe un conflicto preexistente en el manifiesto completo entre
`pandas==3.0.5` y `mlflow-skinny==2.22.0`. HU001 no lo modifica porque pertenece
al stack ML fuera de alcance. El entorno focalizado usado para HU001 reportó
`pip check: No broken requirements found`.

## Configuración

| Variable | Default |
|---|---|
| `BIOMAC_SERVICE_NAME` | `biomac-api` |
| `BIOMAC_ENVIRONMENT` | `local` |
| `BIOMAC_DEBUG` | `false` |
| `BIOMAC_CORS_ORIGINS` | localhost 3000, 5173 y 8050 |

`api_version=2.0.0` es constante contractual. Champion y storage reportan
`false` porque aún no existen checks reales.

## Comandos y resultados

```bash
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch feature/hu001-fastapi-base-contracts
git rebase main

.venv/bin/python -m pip install \
  'fastapi>=0.115,<1' 'uvicorn>=0.30,<1' \
  'pytest>=8,<10' 'httpx>=0.27,<1'

.venv/bin/python -c 'import api.app.main'
.venv/bin/python -m pytest api/tests -q
# 19 passed, 1 StarletteDeprecationWarning

.venv/bin/python -m pip check
# No broken requirements found.

git diff --name-only main...HEAD
git diff --check main...HEAD
```

Comando de ejecución local, no usado durante las pruebas:

```bash
.venv/bin/uvicorn api.app.main:app --host 127.0.0.1 --port 8000
```

Contrato health validado:

```json
{
  "status": "ok",
  "service": "biomac-api",
  "api_version": "2.0.0",
  "champion_ready": false,
  "storage_ready": false
}
```

## Criterios de aceptación

| Criterio | Estado | Evidencia |
|---|---|---|
| CA01 Aplicación importable | PASS | Proceso limpio importa `api.app.main` |
| CA02 Health disponible | PASS | Test HTTP 200 y payload exacto |
| CA03 Readiness veraz | PASS | Ambos componentes `false` |
| CA04 Request ID | PASS | UUID v4 diferentes en dos requests |
| CA05 Contratos Pydantic | PASS | Schemas versionados, tipados y nullable |
| CA06 Campos desconocidos | PASS | `extra="forbid"` probado |
| CA07 Estados controlados | PASS | Catálogo exacto y valor inválido rechazado |
| CA08 Error uniforme | PASS | Validación y HTTPException usan envelope |
| CA09 Error inesperado seguro | PASS | Mensaje, ruta y traceback internos ausentes |
| CA10 CORS configurable | PASS | Origen permitido/denegado probado |
| CA11 Configuración segura | PASS | Defaults no sensibles, sin wildcard/secretos |
| CA12 OpenAPI | PASS | Versión 2.0.0 y solo health v2 |
| CA13 Tests focalizados | PASS | 19/19 sin red/datos/credenciales |
| CA14 Sin adelantar HU002+ | PASS | Sin endpoints/servicios futuros |
| CA15 Compatibilidad documental | PASS | Contrato contrastado con seis documentos |

## Autovalidaciones

| AV | Estado | Resultado |
|---|---|---|
| AV01 Import limpio | PASS | Import sin módulos ML/data |
| AV02 Health contract | PASS | HTTP 200, schema exacto |
| AV03 Readiness | PASS | Champion/storage `false` |
| AV04 Request ID | PASS | Header UUID independiente |
| AV05 Strict schemas | PASS | Extra rechazado |
| AV06 Enums | PASS | RunStatus y T+1/T+2 validados |
| AV07 Error envelope | PASS | `INVALID_REQUEST` con request ID |
| AV08 Sanitización | PASS | Sin excepción/ruta/traceback públicos |
| AV09 CORS | PASS | Allowlist efectiva, sin `*` |
| AV10 OpenAPI | PASS | Solo `/api/v2/health` productivo |
| AV11 Dependencias | PASS | `pip check` limpio; conflicto manifiesto preexistente documentado |
| AV12 Suite focalizada | PASS | 19 passed |
| AV13 Sin servicios externos | PASS | Sin AWS, DVC, MLflow, datos o red |
| AV14 Scope check | PASS | Diff limitado a API, dependencias y evidencia |
| AV15 Gobierno documental | PASS | Semántica v2/readiness/frontera compatible |

## Diff contra `main`

Antes de esta evidencia: 25 archivos, 670 inserciones. Áreas modificadas:

```text
api/app/api/v2/health.py
api/app/core/{config,errors,request_context}.py
api/app/middleware/request_id.py
api/app/schemas/*.py
api/tests/*.py
requirements.txt
dashboard_prototipos/docs/hu001_evidencia_implementacion.md
```

No hay cambios en `src/`, `model/`, `data/`, notebooks ni frontend.

## Limitaciones y seguimiento

- La advertencia `StarletteDeprecationWarning` indica una transición futura de
  `TestClient` hacia `httpx2`; no causa fallos y no justifica ampliar HU001.
- Readiness permanecerá en `false` hasta que HUs posteriores implementen checks
  reales de Champion y storage.
- El conflicto ML preexistente del manifiesto completo debe resolverse fuera de
  este PR por el equipo responsable de dependencias de modelado.
- El merge queda deliberadamente fuera de esta ejecución.
