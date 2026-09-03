# HU002 — Evidencia de implementación DWP

Fecha: 2026-09-02
Rama: `feature/hu002-monthly-upload-validation`
PR: [#22](https://github.com/j-mauro-r/microproyecto-tema3/pull/22)

## Resultado

HU002 implementa una frontera multipart delgada y un validador offline reusable. La
configuración de producción falla de forma cerrada porque las fuentes no fijan un
formato mensual canónico. No se devuelve un `201`: una carga válida bajo un contrato
inyectado termina en `503 CHAMPION_NOT_READY`, etapa `VALIDATING`, hasta que HU003+
implemente el resto del pipeline real.

## Fuentes revisadas completamente

- `hu002_carga_mensual_validacion.md` (fuente de verdad)
- `arquitectura.md`, `implementacion.md`, `API-sign.md`, `plan.md`
- `diccionario-de-datos.md`, `HU-MVP-FastAPI-dashboard.md`
- `hu001_base_fastapi_contratos.md`, `hu001_evidencia_implementacion.md`
- implementación y tests bajo `api/`

## T02 — Contrato real y brechas

| Elemento | Evidencia encontrada | Estado |
|---|---|---|
| Transporte | `multipart/form-data`: `file` y `reference_month` | Definido |
| Mes de referencia | mes calendario estricto `YYYY-MM` | Definido |
| Metadata | nombre original, bytes, SHA-256; content type cuando aplique | Definido |
| Municipios de alcance | Bucaramanga `68001`, Cali `76001` | Definido, pero sin columna mensual canónica |
| Formato/extensión | no hay una extensión mensual única e inequívoca | Brecha |
| Columnas obligatorias | no existe lista canónica del archivo operacional | Brecha |
| Campo temporal | no está identificado para el archivo mensual | Brecha |
| Campo DIVIPOLA | no está identificado para el archivo mensual | Brecha |
| Tipos básicos | no existe esquema de tipos del archivo mensual | Brecha |
| Restricción fila-periodo | se exige evitar futuro, pero falta campo temporal canónico | Brecha |

Los CSV/paneles usados por entrenamiento no se reinterpretaron como contrato de la
carga operacional. La allowlist por defecto es deliberadamente vacía. Los tests usan
un contrato CSV sintético e inyectado únicamente para probar la infraestructura; no
lo presentan como contrato productivo.

## T01–T12

| Tarea | Estado | Evidencia |
|---|---|---|
| T01 | PASS | `main` actualizado en la base; HU001: 19 tests verdes antes de cambios |
| T02 | PASS | auditoría y tabla de brechas anterior |
| T03 | PASS | límite y allowlist centralizados, con overrides y validación |
| T04 | PASS | contrato, metadata y resultado inmutables y reusables |
| T05 | PASS | validador puro sin FastAPI, red ni disco |
| T06 | PASS | `ContractError` mapeado a `ErrorEnvelope`, `request_id`, `VALIDATING` |
| T07 | PASS | handler multipart delega al validador |
| T08 | PASS | CORS mínimo GET/POST y `python-multipart` |
| T09 | PASS | 40 tests offline verdes |
| T10 | PASS | auditoría sin HU003+, ML, DVC, AWS, S3 ni persistencia |
| T11 | PASS | este documento |
| T12 | PASS | gates finales indicados abajo |

## Criterios de aceptación CA01–CA20

| Criterio | Estado | Nota |
|---|---|---|
| CA01 | PASS | health, request ID, errores, settings y OpenAPI preservados |
| CA02 | PASS | mes estricto y calendario válido |
| CA03 | PASS | cero bytes → `INVALID_UPLOAD` |
| CA04 | PASS | límite configurable y lectura HTTP acotada |
| CA05 | PASS | allowlist explícita; producción falla cerrada |
| CA06 | PASS | SHA-256 determinista |
| CA07 | PASS | nombre seguro, tamaño, hash, periodo y content type |
| CA08 | BLOCKED_BY_CONTRACT | no hay columnas mensuales canónicas |
| CA09 | BLOCKED_BY_CONTRACT | no hay tipos mensuales canónicos |
| CA10 | BLOCKED_BY_CONTRACT | códigos definidos, columna DIVIPOLA no definida |
| CA11 | BLOCKED_BY_CONTRACT | regla reusable, columna temporal no definida |
| CA12 | PASS | envelope contractual, etapa y request ID coherentes |
| CA13 | PASS | no se importa ni ejecuta Champion/ML |
| CA14 | PASS | contenido solo en memoria; sin escritura |
| CA15 | PASS | POST permitido solo para origen explícito |
| CA16 | PASS | transporte separado del validador |
| CA17 | PASS | carga válida configurada responde 503, nunca éxito ficticio |
| CA18 | PASS | suite focalizada offline |
| CA19 | PASS | diff limitado a API, tests, dependencia y docs HU002 |
| CA20 | PASS | entrega bytes validados, metadata/hash y brechas explícitas |

Resultado: **16 PASS, 0 FAIL, 4 BLOCKED_BY_CONTRACT**.

## Autovalidaciones AV01–AV20

| AV | Estado | Evidencia |
|---|---|---|
| AV01 | PASS | regresión HU001 incluida en los 40 tests |
| AV02 | PASS | defaults/overrides y valores inseguros probados |
| AV03 | PASS | meses válidos aceptados por el validador |
| AV04 | PASS | formatos y meses calendario inválidos rechazados |
| AV05 | PASS | archivo vacío rechazado |
| AV06 | PASS | límite puro y frontera HTTP probados |
| AV07 | PASS | extensión aceptada/rechazada bajo contrato inyectado |
| AV08 | PASS | hash igual/diferente verificado |
| AV09 | PASS | UTF-8/CSV corrupto produce error controlado |
| AV10 | BLOCKED_BY_CONTRACT | prueba reusable existe; falta lista real de columnas |
| AV11 | BLOCKED_BY_CONTRACT | faltan tipos contractuales; no se inventaron |
| AV12 | BLOCKED_BY_CONTRACT | infraestructura limita 68001/76001; falta campo real |
| AV13 | BLOCKED_BY_CONTRACT | infraestructura rechaza futuro; falta campo real |
| AV14 | PASS | request ID coincide en header/envelope |
| AV15 | PASS | preflight permitido y origen ajeno sin allow-origin |
| AV16 | PASS | auditoría estática sin módulos o conexiones ML/cloud |
| AV17 | PASS | tests no crean archivos de carga |
| AV18 | PASS | revisión manual del handler |
| AV19 | PASS | no hay `201 COMPLETED` ni entidades futuras ficticias |
| AV20 | PASS | `git diff --name-only main...HEAD` revisado |

Resultado: **16 PASS, 0 FAIL, 4 BLOCKED_BY_CONTRACT**.

## Configuración y dependencia

- `BIOMAC_UPLOAD_MAX_BYTES`: entero positivo; default 10 MiB.
- `BIOMAC_UPLOAD_ALLOWED_EXTENSIONS`: allowlist explícita; default vacío.
- `python-multipart>=0.0.9,<1`; versión validada localmente: `0.0.32`.
- Contrato inyectable para columnas, temporalidad y municipio cuando las fuentes lo definan.

## Comandos y resultados

```text
git fetch origin --prune                                      PASS
git merge-base HEAD origin/main                              b5868302 (base actual)
.venv/bin/python -m pytest api/tests -q                      40 passed, 1 warning
.venv/bin/python -m compileall -q api                        PASS
.venv/bin/python -m pip check                                No broken requirements found
git diff --check main...HEAD                                 PASS
git diff --name-only main...HEAD                             scope HU002 esperado
```

La única advertencia es una deprecación de `starlette.testclient` respecto de `httpx`;
no es conflicto de dependencias ni fallo funcional de HU002.

## Diff y limitaciones

El diff contiene `api/app` (configuración, dominio, error, route y wiring), `api/tests`,
`requirements.txt` y los documentos HU002. No toca frontend, datos, notebooks,
entrenamiento ni modelos. No usa MLflow, DVC, AWS/S3, inferencia o persistencia.

La API no puede aceptar productivamente un formato hasta resolver las brechas. El
soporte parser CSV existe como capacidad explícitamente configurable y testeable,
pero no se activa por defecto ni afirma que CSV sea el formato contractual.

## Gate HU003

Antes de habilitar un formato productivo o continuar a preparación debe aprobarse un
contrato inequívoco con: extensión/formato, columnas, tipos, campo temporal, campo
DIVIPOLA y reglas de presencia/periodo. HU003 podrá consumir
`ValidatedMonthlyUpload` sin duplicar tamaño, vacío, allowlist, hash o metadata; no
debe avanzar mientras CA08–CA11/AV10–AV13 permanezcan bloqueados.
