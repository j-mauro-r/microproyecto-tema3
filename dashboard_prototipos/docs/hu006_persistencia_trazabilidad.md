# HU006 — Persistencia local y trazabilidad del run mensual

**Estado:** `[DEFINIDA — PENDIENTE IMPLEMENTACIÓN]`  
**Ámbito:** local-only para Entregable 2  
**Dependencia:** HU005 completada  
**Fuera de alcance:** AWS, EC2, S3, servicios administrados, deployment cloud, HU007 read-only API

---

## 1. Contexto

HU005 deja un run exitoso en memoria con estado:

```text
READY_TO_PERSIST
```

y entrega:

- `MonthlyRunResult`;
- `PredictionSnapshotCandidate`;
- `run_id`;
- `request_id`;
- `reference_month`;
- `source_file_sha256`;
- `champion_version`;
- `idempotency_key`;
- timestamps;
- salida trazable del Champion.

HU006 debe hacer durable ese resultado localmente, resolver reintentos de manera determinista y habilitar la transición contractual:

```text
READY_TO_PERSIST
→ PERSISTING
→ COMPLETED
```

Ante fallo de persistencia:

```text
PERSISTING
→ FAILED
```

La última ejecución exitosa previamente persistida no puede ser reemplazada ni dañada por una nueva ejecución fallida.

---

## 2. Historia de usuario

**Como** analista y usuario consultor de BIOMAC  
**quiero** que cada run mensual y su snapshot queden almacenados localmente de forma consistente y trazable  
**para** poder recuperar la última predicción válida, auditar ejecuciones y evitar duplicados al repetir una misma carga.

---

## 3. Objetivo verificable

Implementar una capa de persistencia local basada en **SQLite**, detrás de los puertos definidos por HU005, que permita:

1. persistir runs exitosos y fallidos;
2. persistir snapshots únicamente cuando el run pueda completarse consistentemente;
3. garantizar unicidad durable de la clave de idempotencia;
4. recuperar el mismo resultado ante un reintento idéntico sin volver a ejecutar inferencia;
5. promover `READY_TO_PERSIST → COMPLETED` solo después de una escritura durable exitosa;
6. mantener trazabilidad entre archivo fuente, Champion, predicciones y run;
7. sobrevivir al reinicio del proceso local;
8. permitir que HU007 implemente `latest`, `history` y detalle de run sin cambiar el almacenamiento.

---

## 4. Decisiones cerradas

### 4.1 Persistencia local

Para Entregable 2 se utilizará **SQLite local**.

Razones:

- no requiere infraestructura externa;
- permite unicidad durable mediante constraints;
- ofrece transacciones ACID;
- simplifica historial, recuperación e idempotencia;
- es suficiente para el volumen académico del MVP;
- puede reemplazarse posteriormente detrás de interfaces de repositorio.

No utilizar archivos JSON como storage principal productivo de HU006.

### 4.2 Ubicación runtime

La ruta del archivo SQLite debe ser configurable mediante variable de entorno/configuración, por ejemplo:

```text
BIOMAC_DB_PATH=<ruta-local>
```

Reglas:

- no hardcodear una ruta absoluta;
- no escribir la base dentro de una ruta versionada por Git;
- el archivo `.db`, `.sqlite`, WAL, SHM u otros archivos runtime deben quedar ignorados por Git;
- tests deben usar base temporal aislada.

### 4.3 Separación de responsabilidades

```text
HU005
orquesta inferencia y produce READY_TO_PERSIST
        ↓
HU006
PersistenceService / Unit of Work
        ↓
RunRepository + PredictionRepository
        ↓
SQLite
        ↓
COMPLETED
```

HU006 no debe modificar lógica ML, validación del CSV ni `ResultMapper`.

### 4.4 Idempotencia

La clave lógica definida en HU005 se mantiene sin cambios:

```text
SHA256(reference_month + source_file_sha256 + champion_version)
```

HU006 implementa la **garantía durable**.

Debe existir una restricción única equivalente a:

```text
UNIQUE(idempotency_key)
```

para runs que representen una ejecución lógica persistida.

Un reintento con la misma key debe recuperar el resultado existente y no generar un segundo snapshot contradictorio.

### 4.5 Atomicidad

Persistir un run exitoso y su snapshot debe ser una única unidad lógica transaccional.

No es válido quedar con:

```text
run COMPLETED
sin snapshot
```

o con:

```text
snapshot nuevo
pero run no durable/inconsistente
```

Si falla la transacción:

- rollback;
- no reemplazar la última predicción válida;
- retornar error controlado de persistencia.

### 4.6 `COMPLETED`

`COMPLETED` solo existe después de persistencia durable exitosa.

HU005 no puede emitirlo por sí sola.

### 4.7 API

HU006 puede completar la composición de:

```text
POST /api/v2/monthly-runs
```

para que una ejecución válida termine en:

```text
201 CREATED
status = COMPLETED
```

únicamente cuando:

```text
validación
→ ChampionService
→ mapping
→ persistencia durable
```

hayan finalizado correctamente.

Los endpoints read-only `latest`, `history` y `GET /runs/{run_id}` completos pertenecen a HU007.

---

## 5. Arquitectura objetivo

```text
POST /api/v2/monthly-runs
        ↓
MonthlyPredictionOrchestrator (HU005)
        ↓
MonthlyRunResult READY_TO_PERSIST
        ↓
MonthlyRunPersistenceService (HU006)
        ↓
transaction
  ├─ RunRepository
  └─ PredictionRepository
        ↓
SQLite local
        ↓
MonthlyRunResult COMPLETED
        ↓
201
```

Reintento idéntico:

```text
POST misma carga
→ HU006 consulta idempotency_key
→ encuentra COMPLETED previo
→ devuelve resultado durable existente
→ NO crea duplicado
```

La composición debe evitar ejecutar nuevamente el Champion cuando la idempotency key pueda resolverse antes de inferencia con la información disponible. Si por la arquitectura actual la versión Champion solo se conoce después de HU004, no fabricar una optimización prematura: mantener corrección primero y documentar la limitación. La deduplicación durable posterior a inferencia sigue siendo obligatoria.

---

## 6. Modelo mínimo de persistencia

### 6.1 Tabla `runs`

Campos mínimos:

- `run_id` TEXT PRIMARY KEY;
- `request_id` TEXT NULL;
- `status` TEXT NOT NULL;
- `reference_month` TEXT NOT NULL;
- `source_file_sha256` TEXT NULL;
- `idempotency_key` TEXT NULL;
- `champion_name` TEXT NULL;
- `champion_version` TEXT NULL;
- `feature_contract_version` TEXT NULL;
- `feature_contract_sha256` TEXT NULL;
- `created_at` TEXT NOT NULL;
- `finished_at` TEXT NOT NULL;
- `completed_at` TEXT NULL;
- `error_code` TEXT NULL;
- `error_stage` TEXT NULL;
- `error_message` TEXT NULL;
- `created_db_at` TEXT NOT NULL.

Restricción mínima:

```text
UNIQUE(idempotency_key)
```

cuando la key no sea `NULL`.

No almacenar stack traces.

### 6.2 Tabla `predictions`

Una fila por predicción/horizonte del snapshot candidato.

Campos mínimos:

- `run_id` TEXT NOT NULL;
- `divipola` TEXT NOT NULL;
- `municipality` TEXT NOT NULL;
- `horizon` TEXT NOT NULL;
- `target_month` TEXT NOT NULL;
- `output_type` TEXT NOT NULL;
- `probability` REAL NULL;
- `expected_cases` REAL NULL;
- `risk_score` REAL NULL;
- `label` TEXT NULL;
- `decision_threshold` REAL NULL;
- `generated_at` TEXT NOT NULL.

Claves/restricciones:

```text
FOREIGN KEY(run_id) REFERENCES runs(run_id)
UNIQUE(run_id, divipola, horizon)
```

No fabricar campos inexistentes del Champion.

### 6.3 Snapshot

El snapshot persistido de HU006 debe conservar exactamente la evidencia disponible en `PredictionSnapshotCandidate`.

No enriquecer todavía con:

- SHAP si no existe;
- canal endémico si no está disponible;
- data quality inventada;
- historia sintética;
- probabilidades sustitutas;
- thresholds por defecto.

Esos enriquecimientos solo pueden incorporarse cuando exista una fuente contractual real.

---

## 7. Puertos y contratos

Reutilizar/extender los Protocols introducidos en HU005 sin acoplar dominio a SQLite.

Conceptualmente:

```python
class RunRepository(Protocol):
    def find_by_idempotency_key(self, key: str) -> PersistedRun | None: ...
    def get(self, run_id: str) -> PersistedRun | None: ...
    def save(self, run: PersistedRun) -> None: ...

class PredictionRepository(Protocol):
    def save_snapshot(self, snapshot: PredictionSnapshotCandidate) -> None: ...
    def get_by_run_id(self, run_id: str) -> PersistedSnapshot | None: ...
```

La forma exacta puede ajustarse al código existente, pero:

- API/orquestador no deben importar `sqlite3`;
- SQL pertenece a infraestructura/persistencia;
- los repositorios deben poder sustituirse en tests;
- HU007 debe poder consultar sin conocer SQL.

---

## 8. Servicio de persistencia

Crear una frontera explícita, por ejemplo:

```python
class MonthlyRunPersistenceService:
    def persist(self, result: MonthlyRunResult) -> PersistedMonthlyRunResult:
        ...
```

Reglas:

1. solo acepta `READY_TO_PERSIST` para camino exitoso;
2. requiere snapshot e idempotency key para completar;
3. consulta duplicado durable;
4. si existe un `COMPLETED` con la misma key, devuelve el existente;
5. si no existe, abre transacción;
6. persiste run + predicciones;
7. marca `COMPLETED` dentro de la misma transacción;
8. commit;
9. devuelve representación durable;
10. ante error hace rollback y emite `PERSISTENCE_FAILED/PERSISTING`.

Para runs `FAILED` provenientes de HU005, HU006 debe poder registrar la trazabilidad del fallo sin crear snapshot.

---

## 9. Política de errores

Reutilizar `ContractError`, `ErrorCode` y `RunStatus` existentes.

### Persistencia

Error esperado:

```text
ErrorCode.PERSISTENCE_FAILED
stage = PERSISTING
```

No exponer:

- SQL;
- nombres de tablas internos en respuestas públicas;
- rutas privadas completas;
- stack trace;
- datos sensibles.

Errores de constraint por reintento concurrente deben resolverse como idempotencia cuando exista un resultado `COMPLETED` compatible, no como duplicado corrupto.

---

## 10. Consistencia e idempotencia

### Reintento idéntico

Dada la misma combinación:

```text
reference_month
source_file_sha256
champion_version
```

Debe existir como máximo un resultado lógico `COMPLETED`.

### Cambio de archivo

Mismo mes + hash diferente:

```text
nueva idempotency_key
→ nuevo run permitido
```

### Cambio de Champion

Mismo mes + mismo archivo + nueva versión Champion:

```text
nueva idempotency_key
→ nuevo run permitido
```

### Run fallido

Un run `FAILED` no se considera última predicción exitosa.

Una falla de persistencia no elimina ni altera runs `COMPLETED` previos.

---

## 11. Recuperación tras reinicio

La base SQLite debe permitir:

```text
proceso termina
→ proceso inicia de nuevo
→ se abre misma DB
→ runs COMPLETED siguen disponibles
```

No depender de diccionarios, caches o estado global en memoria como fuente de verdad.

Los tests deben demostrar recuperación usando dos instancias de repositorio/servicio contra la misma base temporal.

---

## 12. Concurrencia mínima

No se requiere optimización de alta concurrencia para Entregable 2.

Sí se requiere consistencia ante dos intentos cercanos con la misma idempotency key.

Se permite usar transacciones SQLite y constraints como mecanismo principal.

No implementar locks distribuidos.

WAL puede configurarse si aporta valor, pero no es requisito si aumenta complejidad sin necesidad.

---

## 13. Integración con `POST /monthly-runs`

Al finalizar HU006, el comportamiento temporal de HU005:

```text
503 PERSISTENCE_FAILED
```

debe retirarse del camino válido.

Camino válido:

```text
POST archivo válido
→ HU005 READY_TO_PERSIST
→ HU006 persiste
→ COMPLETED
→ HTTP 201
```

Camino inválido/fallido:

- conservar errores contractuales ya existentes;
- no devolver `201`;
- no reemplazar la última predicción exitosa.

El response `201` debe respetar `API-sign.md`; no inventar campos que el backend aún no pueda respaldar. Si el schema final exige enriquecimientos pertenecientes a HU007/HU009, usar el contrato mínimo existente compatible y documentar el gap en lugar de fabricar valores.

---

## 14. Fuera de alcance

HU006 NO debe implementar:

- AWS/EC2/S3;
- RDS/DynamoDB/Supabase;
- Docker/deployment si no es requerido por tests locales;
- DVC runtime;
- MLflow serving;
- entrenamiento/reentrenamiento;
- cambios al Champion;
- feature engineering;
- endpoints completos `latest/history`;
- SHAP nuevo;
- autenticación;
- migración a DB administrada;
- background jobs/colas;
- cache distribuido.

---

## 15. Tareas DWP

### T01 — Baseline

- ejecutar suite API completa antes de modificar código;
- registrar conteo exacto y warnings.

### T02 — Contratos persistidos

- definir modelos framework-neutral para run/snapshot durable;
- evitar duplicación innecesaria con contratos HU005.

### T03 — SQLite configuration

- incorporar `BIOMAC_DB_PATH` o configuración equivalente;
- default seguro para desarrollo local;
- asegurar exclusión Git de archivos runtime.

### T04 — Inicialización de schema

- crear schema `runs` + `predictions`;
- foreign keys activas;
- constraints de unicidad;
- inicialización idempotente.

### T05 — Repositorios SQLite

- implementar `RunRepository`;
- implementar `PredictionRepository`;
- SQL encapsulado fuera de API/orquestación.

### T06 — Transacción

- implementar unidad transaccional para run + snapshot;
- rollback ante error.

### T07 — Idempotencia durable

- lookup por `idempotency_key`;
- impedir duplicados;
- devolver `COMPLETED` existente en reintentos.

### T08 — Runs fallidos

- persistir trazabilidad de `FAILED` sin snapshot;
- preservar código/etapa/mensaje saneado.

### T09 — Persistence service

- crear frontera `READY_TO_PERSIST → COMPLETED`;
- encapsular repositorios/transaction.

### T10 — Endpoint POST

- componer HU005 + HU006;
- eliminar placeholder temporal de persistencia;
- responder `201` solo tras commit.

### T11 — Recovery

- demostrar persistencia tras recrear repositorios/proceso lógico.

### T12 — Tests

- unitarios;
- integración SQLite temporal;
- endpoint;
- regresión completa.

### T13 — Evidencia

- crear `hu006_evidencia_implementacion.md`;
- registrar CA/AV, comandos, resultados y pendientes HU007.

---

## 16. Criterios de aceptación CA01–CA24

| CA | Criterio |
|---|---|
| CA01 | Baseline previo queda registrado. |
| CA02 | Persistencia usa SQLite local y no cloud. |
| CA03 | Ruta DB es configurable y no hardcodeada. |
| CA04 | Archivos runtime SQLite quedan fuera de Git. |
| CA05 | Schema se inicializa idempotentemente. |
| CA06 | Foreign keys están habilitadas. |
| CA07 | `run_id` es único. |
| CA08 | `idempotency_key` tiene unicidad durable. |
| CA09 | Predicción es única por `run_id + divipola + horizon`. |
| CA10 | Run y snapshot exitoso se guardan transaccionalmente. |
| CA11 | `COMPLETED` solo se emite después del commit. |
| CA12 | Rollback evita estados parciales. |
| CA13 | Reintento idéntico no crea segundo resultado lógico. |
| CA14 | Cambio de hash permite nueva ejecución. |
| CA15 | Cambio de Champion permite nueva ejecución. |
| CA16 | Run fallido se registra sin snapshot. |
| CA17 | Fallo de persistencia no altera último `COMPLETED` previo. |
| CA18 | Datos sobreviven a recrear la instancia de repositorio. |
| CA19 | HU005 no importa `sqlite3` ni SQL. |
| CA20 | `POST /monthly-runs` devuelve 201 solo tras persistencia exitosa. |
| CA21 | Errores de persistencia usan `PERSISTENCE_FAILED/PERSISTING`. |
| CA22 | No se fabrican datos de predicción/enriquecimiento. |
| CA23 | No existe dependencia AWS/DVC/MLflow/red. |
| CA24 | Suite completa y evidencia quedan verdes/versionadas. |

---

## 17. Autovalidaciones AV01–AV22

| AV | Procedimiento esperado |
|---|---|
| AV01 | Crear DB temporal y verificar tablas requeridas. |
| AV02 | Ejecutar inicialización dos veces sin fallo. |
| AV03 | Guardar `READY_TO_PERSIST` y obtener `COMPLETED`. |
| AV04 | Verificar run durable por `run_id`. |
| AV05 | Verificar snapshot durable por `run_id`. |
| AV06 | Verificar cuatro predicciones PR12 cuando el fixture las contiene. |
| AV07 | Verificar thresholds independientes preservados. |
| AV08 | Repetir misma idempotency key y comprobar ausencia de duplicado. |
| AV09 | Cambiar hash y comprobar nuevo run permitido. |
| AV10 | Cambiar Champion y comprobar nuevo run permitido. |
| AV11 | Forzar fallo entre run/snapshot y comprobar rollback. |
| AV12 | Persistir FAILED y comprobar ausencia de snapshot. |
| AV13 | Recrear repositorio contra misma DB y recuperar datos. |
| AV14 | Verificar foreign key activa. |
| AV15 | Verificar constraint `run_id/divipola/horizon`. |
| AV16 | Endpoint válido responde 201 únicamente tras commit. |
| AV17 | Falla DB produce error saneado PERSISTENCE_FAILED/PERSISTING. |
| AV18 | Último COMPLETED previo permanece intacto tras fallo. |
| AV19 | Imports de orquestación HU005 siguen sin SQLite/cloud. |
| AV20 | No existen credenciales/rutas cloud nuevas. |
| AV21 | Suite focal HU006 pasa. |
| AV22 | Suite API, compileall y pip check pasan. |

---

## 18. Definition of Done

HU006 puede marcarse:

```text
[COMPLETADA — DESARROLLO]
```

solo cuando:

- SQLite local está implementado detrás de repositorios;
- inicialización de schema es reproducible;
- run + snapshot son atómicos;
- idempotencia durable está garantizada;
- reintentos no duplican resultados;
- `COMPLETED` requiere persistencia exitosa;
- `POST /monthly-runs` deja de usar el placeholder 503 para el camino válido;
- los datos sobreviven al reinicio lógico;
- runs fallidos son trazables sin snapshot ficticio;
- no existe AWS/cloud en el alcance;
- CA01–CA24 PASS;
- AV01–AV22 PASS;
- regresión API completa verde;
- evidencia versionada.

---

## 19. Evidencia requerida

Crear:

```text
dashboard_prototipos/docs/hu006_evidencia_implementacion.md
```

Debe contener:

- SHA/rama auditada;
- baseline;
- archivos modificados;
- arquitectura implementada;
- ubicación/configuración SQLite;
- schema real;
- evidencia de transacción/rollback;
- evidencia de idempotencia;
- evidencia de recovery;
- pruebas endpoint;
- CA01–CA24;
- AV01–AV22;
- comandos y conteos exactos;
- warnings;
- pendientes HU007;
- confirmación explícita de ausencia de AWS/cloud.

---

## 20. Comandos mínimos de validación

Codex debe adaptar nombres exactos a los tests creados y ejecutar al menos:

```bash
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m pytest api/tests/test_persistence*.py api/tests/test_monthly_runs.py -q
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m compileall -q api/app api/tests
.venv/bin/python -m pip check
```

Si el glob no existe, ejecutar explícitamente los archivos HU006 creados.

---

## 21. Gate hacia HU007

HU007 puede comenzar cuando HU006 entregue una frontera durable capaz de consultar, como mínimo:

```text
run por run_id
snapshot por run_id
run COMPLETED por idempotency_key
```

HU007 añadirá las consultas HTTP read-only:

```text
GET /api/v2/runs/{run_id}
GET /api/v2/predictions/latest
GET /api/v2/predictions/history
```

sin ejecutar nuevamente el Champion.
