# HU002 — Carga mensual y validación BIOMAC

## 1. Identificación

- **ID canónico:** HU002
- **Alias en backlog:** HU-INT-002
- **Nombre:** Carga mensual y validación BIOMAC
- **Estado:** `[PENDIENTE]`
- **Prioridad:** ALTA
- **Tipo:** Backend / Integración / Ingesta operacional
- **Metodología:** DWP (Deep Work Plan)
- **Dependencia previa:** HU001 — Base FastAPI y contratos BIOMAC `[COMPLETADA]`
- **Habilita:** HU003 — Preparación de entradas del Champion (`HU-INT-003`)
- **Gate posterior:** HU003 no debe iniciar hasta que una carga mensual pueda recibirse y validarse de forma determinista, segura, trazable y sin ejecutar el Champion.
- **Fuentes de verdad:**
  1. `dashboard_prototipos/docs/arquitectura.md`;
  2. `dashboard_prototipos/docs/implementacion.md`;
  3. `dashboard_prototipos/docs/API-sign.md`;
  4. `dashboard_prototipos/docs/plan.md`;
  5. `dashboard_prototipos/docs/diccionario-de-datos.md`;
  6. `dashboard_prototipos/docs/HU-MVP-FastAPI-dashboard.md`;
  7. `dashboard_prototipos/docs/hu001_base_fastapi_contratos.md`;
  8. `dashboard_prototipos/docs/hu001_evidencia_implementacion.md`;
  9. implementación FastAPI v2 ya integrada bajo `api/`.

---

## 2. Contexto y problema

HU001 estableció la frontera HTTP FastAPI v2, contratos Pydantic, `request_id`, CORS, errores uniformes y el endpoint `GET /api/v2/health`.

El siguiente paso del flujo BIOMAC es permitir que un analista entregue el archivo correspondiente al nuevo periodo mensual y que el backend determine, **antes de cualquier preparación de features o inferencia**, si esa entrada es técnicamente aceptable.

El flujo arquitectónico objetivo es:

```text
archivo mensual
→ validación
→ preparación
→ Champion
→ persistencia
→ dashboard
```

HU002 implementa exclusivamente el tramo:

```text
archivo mensual
→ recepción HTTP
→ validación técnica/temporal
→ metadata/hash de la carga
→ resultado de validación reutilizable por HU003
```

Esta HU **no prepara features, no ejecuta el Champion, no persiste predicciones y no completa todavía el flujo operacional end-to-end**.

### Restricción contractual importante

`API-sign.md` define `POST /api/v2/monthly-runs` como el endpoint público del flujo mensual completo y establece que una respuesta exitosa `201` representa un run terminado después de validación, preparación, inferencia y persistencia.

Por tanto, HU002 **no debe inventar un `201 COMPLETED`, una predicción, un Champion o un snapshot ficticio** solo para exponer anticipadamente el endpoint completo.

HU002 debe construir la capacidad reusable de recepción/validación necesaria para ese endpoint. La integración definitiva de esa validación dentro del flujo completo será responsabilidad de las HUs de preparación/orquestación.

Si se decide registrar `POST /api/v2/monthly-runs` durante HU002, el handler debe delegar exclusivamente en componentes reales y no simular etapas posteriores. Cualquier respuesta transitoria distinta del contrato 2.0.0 requeriría actualizar previamente `API-sign.md`; esta HU no autoriza esa desviación.

---

## 3. Historia de usuario

> **Como** analista actualizador de BIOMAC, **quiero** que el sistema reciba y valide el archivo correspondiente al nuevo periodo mensual, **para** impedir que datos inválidos, incompletos, fuera de periodo o no compatibles continúen hacia la preparación de inferencia y el Champion.

---

## 4. Objetivo verificable

Al finalizar HU002 deberá existir una implementación reusable que permita, sin modelos ni servicios externos:

1. recibir un archivo mensual mediante la frontera FastAPI usando `multipart/form-data`;
2. recibir `reference_month` en formato `YYYY-MM`;
3. aplicar un límite de tamaño configurable;
4. rechazar archivos vacíos;
5. validar formato/extensión mediante una allowlist explícita y configurable;
6. calcular SHA-256 sobre el contenido recibido;
7. registrar metadata técnica de la carga sin persistir el archivo en Git;
8. validar estructura mínima del dataset según el contrato de entrada disponible;
9. validar tipos básicos de columnas que pertenezcan realmente al contrato conocido;
10. identificar Bucaramanga (`68001`) y Cali (`76001`) cuando el contrato de carga las requiera;
11. detectar y bloquear datos posteriores al `reference_month` cuando exista una columna temporal interpretable según el contrato;
12. producir errores contractuales estables con `request_id` y etapa `VALIDATING`;
13. garantizar que una carga inválida no invoca preparación, Champion, MLflow, DVC, AWS ni persistencia;
14. producir un resultado de validación inmutable/reutilizable para HU003;
15. superar una suite focalizada completamente offline;
16. demostrar que HU002 no adelantó HU003+.

---

## 5. Decisiones de diseño

### 5.1 Separar transporte de validación

La lógica de validación no debe vivir directamente dentro del endpoint.

La solución debe separar al menos:

```text
FastAPI / multipart
        ↓
Upload boundary / parser
        ↓
MonthlyUploadValidator
        ↓
ValidatedMonthlyUpload
```

El componente reutilizable debe poder probarse sin servidor HTTP.

### 5.2 No inventar el contrato del archivo

Los documentos vigentes definen que deben validarse:

- formato permitido;
- tamaño;
- archivo no vacío;
- columnas obligatorias según contrato de entrada;
- tipos básicos;
- `reference_month`;
- identificación de Bucaramanga/Cali;
- ausencia de datos posteriores al corte.

Sin embargo, la documentación vigente **no define de forma canónica una única extensión ni el listado exacto de columnas del archivo mensual**.

Por lo tanto:

- la implementación debe centralizar un `MonthlyUploadContract` o configuración equivalente;
- extensión(es) y columnas requeridas deben declararse en un único lugar;
- Codex debe inspeccionar primero el repositorio para encontrar un contrato existente reutilizable;
- si no existe una definición inequívoca, **no debe inventar silenciosamente nombres de columnas**;
- debe implementar la infraestructura de validación y documentar la brecha exacta como dependencia para HU003/equipo de modelado;
- cualquier fixture usado en tests debe estar identificado como **sintético de contrato**, no como dato epidemiológico real.

### 5.3 No preparar features

Validar estructura no significa construir features.

HU002 puede:
- leer el archivo lo mínimo necesario para validar;
- identificar columnas, tipos, periodo y ciudades;
- calcular metadata/hash.

HU002 no puede:
- crear lags;
- rolling windows;
- percentiles/canal;
- imputaciones de modelado;
- matrices de features;
- orden de features del Champion.

Eso pertenece a HU003.

### 5.4 Archivo en memoria / almacenamiento temporal seguro

Para esta HU, el archivo no necesita almacenamiento persistente.

Preferencia:
- validar mediante bytes/stream recibido;
- evitar escribir a disco cuando no sea necesario;
- si una librería requiere archivo temporal, usar ubicación temporal del sistema y asegurar limpieza en `finally`/context manager;
- nunca escribir uploads en una carpeta versionada del repositorio.

### 5.5 SHA-256

El hash debe calcularse sobre el contenido real del archivo, no sobre:
- nombre;
- ruta;
- timestamp.

Debe producir una cadena hexadecimal SHA-256 estable.

### 5.6 `reference_month`

Debe validarse estrictamente como mes calendario:

```text
YYYY-MM
```

Ejemplos válidos:
- `2026-01`
- `2026-12`

Ejemplos inválidos:
- `2026-00`
- `2026-13`
- `26-01`
- `2026/01`
- `2026-1`

La representación interna puede normalizarse a un tipo fecha/periodo, pero el contrato HTTP conserva `YYYY-MM`.

### 5.7 Municipios soportados

Los códigos documentados para esta fase son:

- Bucaramanga: `68001`;
- Cali: `76001`.

La validación debe apoyarse en DIVIPOLA y no únicamente en strings de nombres cuando el dataset disponga del código.

No se debe ampliar silenciosamente el alcance a otros municipios.

### 5.8 Datos posteriores al corte

Si el contrato del archivo contiene información temporal por fila, ninguna observación usada como carga válida puede pertenecer a un periodo posterior a `reference_month`.

La HU debe implementar esta validación **solo cuando la semántica temporal del archivo pueda determinarse sin suposiciones**.

Si el contrato exacto de la columna temporal no está disponible, registrar la dependencia explícitamente; no inferir arbitrariamente una columna por similitud de nombre.

### 5.9 Idempotencia vs. validación

HU002 calcula `source_file_sha256`, que será insumo para la clave futura:

```text
reference_month + source_file_sha256 + champion_version
```

Pero HU002 **no puede resolver todavía la idempotencia completa**, porque `champion_version` y persistencia pertenecen a HUs posteriores.

HU002 no debe implementar una base de datos o repositorio de runs para anticipar esa lógica.

---

## 6. Alcance técnico

### 6.1 Configuración

Extender la configuración de HU001 solo con parámetros propios de carga, por ejemplo:

- tamaño máximo permitido;
- allowlist de extensiones/MIME si está soportada por el contrato;
- límites defensivos de parsing cuando aporten seguridad.

Reglas:
- valores centralizados;
- no hardcodeados en endpoint y validator por separado;
- sin secretos;
- wildcard no aplica como formato permitido;
- defaults conservadores y documentados.

### 6.2 Schemas/modelos de dominio de validación

Definir tipos equivalentes a:

```text
MonthlyUploadMetadata
ValidatedMonthlyUpload
UploadValidationIssue
MonthlyUploadContract
```

Responsabilidades mínimas del resultado validado:

- `reference_month`;
- `original_name`;
- `size_bytes`;
- `sha256`;
- `content_type` si aplica;
- formato detectado/aceptado;
- resumen estructural validado;
- municipios/cortes detectados solo cuando sean verificables;
- warnings no bloqueantes cuando el contrato permita alguno.

Evitar incorporar dataframes completos al schema HTTP si no son necesarios.

### 6.3 Servicio de validación

Crear un componente focalizado, por ejemplo:

```text
api/app/services/monthly_upload_validator.py
```

o ubicación equivalente coherente con la arquitectura.

Debe:

1. validar metadata del archivo;
2. aplicar límite de tamaño;
3. validar vacío;
4. validar extensión/formato;
5. calcular hash;
6. parsear de forma segura según el formato soportado;
7. validar estructura contra `MonthlyUploadContract`;
8. validar tipos básicos cuando estén definidos;
9. validar `reference_month`;
10. validar ciudades/códigos cuando estén definidos;
11. validar temporalidad cuando esté definida;
12. producir un único resultado validado o excepción de dominio estable.

### 6.4 Excepciones de dominio

Definir errores internos claros, por ejemplo:

- upload vacío;
- archivo demasiado grande;
- formato no soportado;
- parse inválido;
- columnas faltantes;
- tipos incompatibles;
- periodo inválido;
- municipio requerido ausente;
- dato futuro respecto al corte.

El mapeo HTTP debe usar los códigos existentes del contrato cuando correspondan:

- `INVALID_REQUEST`;
- `INVALID_UPLOAD`;
- `INSUFFICIENT_DATA` cuando sea semánticamente correcto.

No crear un catálogo paralelo de códigos públicos sin actualizar `API-sign.md`.

### 6.5 Frontera HTTP

Preparar la recepción contractual:

```http
POST /api/v2/monthly-runs
Content-Type: multipart/form-data
```

Campos:

- `file`;
- `reference_month`.

**Regla de integración incremental:** HU002 puede implementar el parser/router necesario para este endpoint, pero no debe devolver una falsa respuesta `201 COMPLETED` si todavía no existen preparación, inferencia y persistencia.

La solución preferida es dejar la validación reusable lista y conectar la respuesta final contractual cuando el orquestador exista. Si el endpoint se monta en HU002, su comportamiento debe mantenerse coherente con `API-sign.md`; ante imposibilidad, documentar el gate y no introducir una respuesta temporal no versionada.

### 6.6 CORS y método POST

HU001 configuró CORS inicialmente para `GET` porque solo existía health.

Al habilitar un endpoint de carga real, la configuración deberá permitir `POST` de forma explícita y mantener allowlist de orígenes.

No habilitar métodos innecesarios (`*`) por conveniencia.

### 6.7 Upload multipart

Añadir solo la dependencia mínima que FastAPI requiera para multipart si no existe en el entorno actual.

No agregar frameworks de almacenamiento, colas o bases de datos en HU002.

### 6.8 Logging y privacidad

La capa de validación puede registrar:

- `request_id`;
- etapa;
- tamaño;
- hash;
- periodo;
- resultado PASS/FAIL;
- código de error.

No registrar:
- contenido completo del archivo;
- credenciales;
- información innecesaria fila por fila.

---

## 7. Fuera de alcance

HU002 **no** debe implementar:

- creación de features;
- lags;
- rolling windows;
- canal endémico;
- imputación de modelado;
- `ChampionInputContract` definitivo;
- `InputService` de HU003;
- `ChampionAdapter`;
- carga de XGBoost/LightGBM/joblib/MLflow;
- inferencia;
- thresholds;
- SHAP;
- `MonthlyPredictionOrchestrator` completo;
- `ResultMapper`;
- `PredictionRepository`;
- `RunRepository` productivo;
- base de datos;
- persistencia de snapshots;
- `GET /runs/{run_id}`;
- `GET /predictions/latest`;
- `GET /predictions/history`;
- cambios en React/Lovable;
- entrenamiento/reentrenamiento;
- tuning;
- selección/promoción del Champion;
- AWS/S3/DVC como requisito de ejecución;
- CI/CD;
- Dockerización.

No debe modificar datos, notebooks o modelos existentes para conseguir que un fixture pase.

---

## 8. Plan de implementación / tareas DWP

### T01 — Actualizar base y validar HU001

**Cambio:** partir de `main` actualizado donde HU001 esté integrada.

**Validaciones mínimas:**

- `GET /api/v2/health` sigue disponible;
- tests HU001 pasan antes de modificar;
- working tree limpio.

**Resultado esperado:** HU002 parte de una frontera HTTP estable.

---

### T02 — Auditar contrato real de la carga

**Cambio:** inspeccionar repositorio y documentación buscando:

- formato real de archivo;
- columnas requeridas;
- columna temporal;
- DIVIPOLA;
- tipos básicos;
- restricciones de periodo.

**Resultado esperado:** tabla explícita de campos encontrados y brechas.

**Regla bloqueante:** no inventar columnas si la fuente de verdad no las define.

**Depende de:** T01.

---

### T03 — Extender configuración mínima

**Archivos:** `api/app/core/config.py` y pruebas correspondientes.

**Cambio:** añadir límites/allowlist necesarios para upload.

**Resultado esperado:** configuración centralizada y testeable.

**Depende de:** T02.

---

### T04 — Definir contrato de validación

**Archivos:** módulo de schemas/modelos de upload.

**Cambio:** definir metadata, resultado validado y contrato estructural sin incluir features de HU003.

**Resultado esperado:** tipos reutilizables por HTTP y HU003.

**Depende de:** T02-T03.

---

### T05 — Implementar validator puro

**Archivo sugerido:** `api/app/services/monthly_upload_validator.py`.

**Cambio:** implementar validaciones de tamaño, vacío, formato, hash, parsing, estructura, tipos, corte y municipios cuando el contrato lo permita.

**Resultado esperado:** validación ejecutable sin FastAPI/TestClient.

**Depende de:** T04.

---

### T06 — Integrar errores con envelope HU001

**Cambio:** mapear errores de validación a códigos públicos existentes y etapa `VALIDATING`.

**Resultado esperado:** respuestas sanitizadas con `request_id` coherente.

**Depende de:** T05.

---

### T07 — Preparar frontera multipart

**Archivos sugeridos:** `api/app/api/v2/monthly_runs.py` + wiring en `main.py` cuando sea contractualmente válido.

**Cambio:** recibir `file` y `reference_month`, delegar al validator y mantener endpoint delgado.

**Resultado esperado:** transporte desacoplado de validación.

**Depende de:** T05-T06.

---

### T08 — CORS POST y dependencia multipart

**Cambio:** permitir únicamente métodos/headers requeridos y añadir dependencia multipart mínima si FastAPI la exige.

**Resultado esperado:** preflight válido desde origen permitido sin ampliar CORS innecesariamente.

**Depende de:** T07.

---

### T09 — Implementar tests focalizados

**Archivos:** `api/tests/`.

Cubrir como mínimo:

- archivo válido según contrato disponible;
- archivo vacío;
- tamaño excedido;
- extensión/formato inválido;
- `reference_month` válido/inválido;
- SHA-256 determinista;
- columnas faltantes cuando el contrato las defina;
- tipos inválidos cuando el contrato los defina;
- Bucaramanga/Cali cuando sea verificable;
- fecha posterior al corte cuando sea verificable;
- error envelope y `request_id`;
- CORS POST;
- no ejecución de módulos ML;
- no escritura en árbol del repo;
- regresión HU001.

**Resultado esperado:** suite rápida y offline.

**Depende de:** T05-T08.

---

### T10 — Validar ausencia de HU003+

**Cambio:** auditar imports, nuevos archivos y diff.

**PASS:** no existen features, ChampionAdapter, MLflow, inferencia, repositorios productivos ni snapshots.

**Depende de:** T09.

---

### T11 — Crear evidencia DWP

**Archivo:**

`dashboard_prototipos/docs/hu002_evidencia_implementacion.md`

Debe registrar:

- contrato de carga encontrado;
- brechas no definidas por fuentes;
- configuración final;
- validaciones implementadas;
- CA/AV PASS/FAIL;
- comandos ejecutados;
- resultados de tests;
- limitaciones;
- diff;
- gate para HU003.

**Depende de:** T10.

---

### T12 — Validar PR focalizado

Ejecutar como mínimo:

```bash
python -m pytest api/tests -q
python -m compileall -q api
git diff --check main...HEAD
```

Revisar que no existan cambios fuera de:

- API HU002;
- tests;
- dependencias estrictamente necesarias;
- evidencia/documentación HU002.

**Resultado esperado:** PR listo para auditoría.

**Depende de:** T11.

---

## 9. Criterios de aceptación

### CA01 — Base HU001 preservada

**Dado** HU001 integrada,
**cuando** se implementa HU002,
**entonces** health, request ID, errores, configuración y OpenAPI existentes continúan funcionando.

### CA02 — `reference_month` estricto

**Dado** un mes de referencia,
**cuando** se valida,
**entonces** solo se acepta un mes calendario válido en formato `YYYY-MM`.

### CA03 — Archivo no vacío

**Dado** un upload de cero bytes,
**cuando** se valida,
**entonces** se rechaza como `INVALID_UPLOAD` y no continúa a etapas posteriores.

### CA04 — Tamaño máximo configurable

**Dado** un archivo mayor al límite configurado,
**cuando** se recibe,
**entonces** se rechaza de forma controlada sin cargar innecesariamente más contenido en memoria.

### CA05 — Formato permitido

**Dado** un archivo con formato no permitido por el contrato/configuración,
**cuando** se valida,
**entonces** se rechaza antes del parsing de negocio.

### CA06 — SHA-256 reproducible

**Dado** el mismo contenido,
**cuando** se calcula el hash en ejecuciones independientes,
**entonces** el SHA-256 es idéntico.

### CA07 — Metadata de carga

**Dado** un archivo aceptado,
**cuando** termina la validación,
**entonces** el resultado contiene al menos nombre original, tamaño, hash, periodo y tipo/formato cuando aplique.

### CA08 — Contrato estructural

**Dado** que las fuentes definen columnas obligatorias,
**cuando** falta una,
**entonces** el archivo se rechaza sin inventar una sustitución.

Si las fuentes no permiten definir aún columnas exactas, el criterio queda documentado como dependencia explícita y no se marca falsamente como PASS.

### CA09 — Tipos básicos

**Dado** que el contrato define tipos básicos,
**cuando** una columna esencial contiene un tipo incompatible,
**entonces** la carga se rechaza de forma controlada.

### CA10 — Municipios soportados

**Dado** un contrato que incluye DIVIPOLA,
**cuando** se valida la carga,
**entonces** Bucaramanga `68001` y Cali `76001` se reconocen según el alcance documentado y no se amplía silenciosamente a otros municipios.

### CA11 — Corte temporal

**Dado** un archivo con temporalidad verificable,
**cuando** una observación está después de `reference_month`,
**entonces** se rechaza o bloquea conforme a la regla documentada; nunca se utiliza silenciosamente.

### CA12 — Error contractual

**Dado** un upload inválido,
**cuando** FastAPI responde,
**entonces** utiliza `ErrorEnvelope`, `request_id`, código público existente y etapa `VALIDATING` cuando corresponda.

### CA13 — Sin Champion

**Dado** cualquier archivo válido o inválido,
**cuando** HU002 lo procesa,
**entonces** no se carga ni ejecuta Champion, XGBoost, LightGBM, MLflow o artefacto equivalente.

### CA14 — Sin persistencia de archivos

**Dado** una carga,
**cuando** finaliza la validación,
**entonces** el archivo no queda almacenado dentro del árbol Git del repositorio.

### CA15 — CORS POST mínimo

**Dado** un origen permitido,
**cuando** realiza preflight para el endpoint mensual,
**entonces** `POST` está permitido explícitamente; un origen no permitido sigue sin obtener `Access-Control-Allow-Origin`.

### CA16 — Endpoint delgado

**Dado** el handler multipart,
**cuando** se inspecciona,
**entonces** delega la validación a un servicio reusable y no contiene parsing/validación extensa inline.

### CA17 — Sin respuesta futura inventada

**Dado** que HU002 no ejecuta preparación/inferencia/persistencia,
**cuando** se revisa el comportamiento HTTP,
**entonces** no existe un `201 COMPLETED` con Champion/predicción/snapshot ficticios para aparentar el contrato final.

### CA18 — Tests focalizados

**Dado** un checkout local con dependencias de HU001/HU002,
**cuando** se ejecutan los tests API,
**entonces** pasan sin red externa, DVC, AWS, MLflow, Champion ni datasets reales.

### CA19 — Alcance del PR

**Dado** el diff contra `main`,
**cuando** se audita,
**entonces** no existen cambios de frontend, entrenamiento, modelos, notebooks o datos no requeridos por HU002.

### CA20 — Gate HU003

**Dado** HU002 terminada,
**cuando** HU003 recibe su salida,
**entonces** dispone de una entrada validada, metadata/hash y brechas explícitas del contrato, sin tener que duplicar validaciones de upload.

---

## 10. Autovalidaciones obligatorias

### AV01 — Regresión HU001

**Procedimiento:** ejecutar suite existente antes/después.

**PASS:** tests HU001 continúan verdes.

### AV02 — Configuración de upload

**Procedimiento:** cargar settings con defaults y overrides.

**PASS:** límite/formatos quedan centralizados y validan valores inválidos.

### AV03 — Mes válido

**Procedimiento:** probar meses válidos de enero/diciembre.

**PASS:** formato conservado `YYYY-MM`.

### AV04 — Mes inválido

**Procedimiento:** probar `2026-00`, `2026-13`, `2026/01`, `2026-1`.

**PASS:** todos rechazados.

### AV05 — Archivo vacío

**Procedimiento:** validar `b""`.

**PASS:** error `INVALID_UPLOAD` o excepción interna correctamente mapeada.

### AV06 — Tamaño

**Procedimiento:** usar límite pequeño de prueba y excederlo.

**PASS:** rechazo antes de etapa posterior.

### AV07 — Formato

**Procedimiento:** probar extensión/MIME aceptado y no aceptado según contrato configurado.

**PASS:** allowlist efectiva.

### AV08 — SHA-256

**Procedimiento:** calcular dos veces sobre mismos bytes y una vez sobre bytes distintos.

**PASS:** mismo contenido = mismo hash; contenido distinto = hash distinto.

### AV09 — Parsing seguro

**Procedimiento:** archivo sintácticamente corrupto para formato aceptado.

**PASS:** error controlado sin traceback público.

### AV10 — Columnas

**Procedimiento:** retirar una columna requerida si el contrato exacto fue encontrado.

**PASS:** rechazo explícito.

Si no existe contrato exacto, registrar `BLOCKED_BY_CONTRACT` y no inventar el test.

### AV11 — Tipos

**Procedimiento:** introducir tipo inválido en campo esencial definido.

**PASS:** rechazo explícito.

### AV12 — Municipios

**Procedimiento:** fixture contractual con DIVIPOLA soportado/no soportado cuando aplique.

**PASS:** alcance Bucaramanga/Cali respetado.

### AV13 — Leakage temporal de carga

**Procedimiento:** incluir periodo posterior a `reference_month` cuando exista campo temporal canónico.

**PASS:** fila/archivo no continúa.

### AV14 — Error envelope

**Procedimiento:** provocar error desde HTTP.

**PASS:** `request_id` coincide entre header/envelope y no hay detalles internos.

### AV15 — CORS POST

**Procedimiento:** preflight desde origen permitido y no permitido.

**PASS:** comportamiento esperado sin wildcard.

### AV16 — Sin side effects ML

**Procedimiento:** importar/ejecutar validator y endpoint en proceso limpio e inspeccionar módulos/conexiones relevantes.

**PASS:** cero MLflow/DVC/AWS/modelos cargados por HU002.

### AV17 — Sin archivo persistido

**Procedimiento:** capturar estado del árbol antes/después de tests de upload.

**PASS:** no aparecen uploads/runtime en rutas versionadas.

### AV18 — Endpoint delgado

**Procedimiento:** revisión estática/manual.

**PASS:** parser HTTP delega al servicio.

### AV19 — Contrato final no falsificado

**Procedimiento:** revisar respuestas y fixtures.

**PASS:** no hay Champion/snapshot/predicción ficticios presentados como ejecución real.

### AV20 — Scope diff

**Procedimiento:** `git diff --name-only main...HEAD`.

**PASS:** cambios limitados a HU002 y soporte mínimo.

---

## 11. Definition of Done (DoD)

HU002 se considera `[COMPLETADA]` únicamente cuando:

- [ ] HU001 está integrada y sin regresiones;
- [ ] existe configuración centralizada de upload;
- [ ] existe validación estricta de `reference_month`;
- [ ] archivo vacío se rechaza;
- [ ] tamaño máximo se aplica;
- [ ] formato permitido se controla mediante allowlist;
- [ ] SHA-256 se calcula sobre contenido real;
- [ ] metadata de carga queda disponible para HU003;
- [ ] estructura/tipos se validan hasta donde el contrato real lo permita;
- [ ] cualquier brecha de columnas/tipos está explícitamente documentada y no inventada;
- [ ] Bucaramanga/Cali se validan cuando la estructura fuente lo permita;
- [ ] datos posteriores al corte se bloquean cuando la temporalidad sea verificable;
- [ ] errores usan envelope HU001;
- [ ] CORS soporta POST solo cuando endpoint esté montado;
- [ ] endpoint/router es delgado y reusable;
- [ ] no se ejecuta Champion;
- [ ] no se construyen features;
- [ ] no se persisten predicciones;
- [ ] no se versionan uploads;
- [ ] no se fabrica una respuesta `COMPLETED`;
- [ ] pruebas focalizadas pasan;
- [ ] `compileall` pasa;
- [ ] `git diff --check` pasa;
- [ ] evidencia DWP HU002 existe;
- [ ] CA01–CA20 están PASS o las excepciones contractuales explícitamente bloqueadas están justificadas;
- [ ] AV01–AV20 están PASS o las dependencias de contrato están documentadas;
- [ ] PR focalizado queda listo para auditoría;
- [ ] merge se realiza solo después de revisión humana.

---

## 12. Evidencias esperadas

La implementación debe conservar como mínimo:

1. tabla del contrato de upload encontrado en el repositorio;
2. brechas contractuales que no pudieron resolverse sin suposición;
3. configuración de tamaño/formatos;
4. validator reusable;
5. schemas/modelos de carga;
6. tests unitarios del validator;
7. tests HTTP/multipart cuando el endpoint quede montado;
8. pruebas de `reference_month`;
9. pruebas de hash;
10. pruebas de CORS POST;
11. evidencia de no side effects ML;
12. evidencia de que no se escriben uploads al repo;
13. matriz CA01–CA20;
14. matriz AV01–AV20;
15. resultados `pytest`, `compileall`, `pip check` cuando aplique y `git diff --check`;
16. documento `hu002_evidencia_implementacion.md`.

---

## 13. Riesgos y mitigaciones

### R01 — Inventar columnas del archivo

**Riesgo:** implementar un contrato que no coincide con la salida real del proceso mensual.

**Mitigación:** T02 bloqueante, contrato centralizado y brechas explícitas.

### R02 — Mezclar validación con feature engineering

**Riesgo:** HU002 termina duplicando lógica de HU003/pipeline.

**Mitigación:** validator limitado a estructura/tipos/corte; prohibición de lags/rolling/canal.

### R03 — Leer archivos grandes completos sin límite

**Riesgo:** consumo excesivo de memoria.

**Mitigación:** límite configurable y lectura acotada/streaming cuando corresponda.

### R04 — Confiar en extensión

**Riesgo:** contenido incompatible con nombre permitido.

**Mitigación:** extensión allowlist + parsing real; MIME solo como señal adicional, nunca prueba única.

### R05 — Path traversal mediante nombre

**Riesgo:** usar `filename` como ruta de escritura.

**Mitigación:** nombre solo metadata; no construir rutas persistentes con él.

### R06 — Persistir accidentalmente PHI/datos runtime

**Riesgo:** uploads terminan en Git.

**Mitigación:** procesamiento en memoria/temp + AV17 + `.gitignore` solo como defensa secundaria.

### R07 — Adelantar idempotencia incompleta

**Riesgo:** crear lógica incorrecta sin `champion_version`/repository.

**Mitigación:** HU002 solo produce SHA-256; idempotencia completa en HU005/HU006.

### R08 — Fabricar `201 COMPLETED`

**Riesgo:** API aparenta inferencia inexistente.

**Mitigación:** CA17/AV19 bloqueantes y respeto de `API-sign.md`.

### R09 — Ampliar CORS excesivamente

**Riesgo:** permitir cualquier origen/método.

**Mitigación:** allowlist existente + POST explícito solamente.

### R10 — Tests dependientes de dataset real

**Riesgo:** suite lenta/no reproducible.

**Mitigación:** fixtures sintéticos mínimos derivados del contrato, claramente identificados.

---

## 14. Resultado esperado para HU003

HU003 debe recibir de HU002:

```text
ValidatedMonthlyUpload
├── reference_month
├── source_file metadata
│   ├── original_name
│   ├── size_bytes
│   ├── sha256
│   └── content_type/formato cuando aplique
├── estructura validada
├── municipios/corte verificados cuando sean contractuales
├── warnings permitidos
└── acceso seguro al contenido/datos parseados mediante una interfaz definida
```

HU003 utilizará esta salida para construir únicamente las entradas/features que el Champion requiera.

HU003 no deberá volver a implementar:

- tamaño;
- formato;
- vacío;
- hash;
- validación básica de periodo;
- validación estructural ya resuelta por HU002.

---

## 15. Regla de cierre

HU002 no se considera terminada por el simple hecho de que FastAPI acepte un archivo.

Debe demostrar que la entrada queda **controlada antes de entrar al pipeline de inferencia**, que las reglas no fueron inventadas fuera de las fuentes de verdad y que el sistema mantiene la frontera arquitectónica:

```text
HU002 = recepción + validación
HU003 = preparación de input/features
HU004 = Champion
HU005 = orquestación completa
HU006 = persistencia
```
