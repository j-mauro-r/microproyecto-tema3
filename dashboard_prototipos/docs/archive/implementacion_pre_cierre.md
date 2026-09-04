# BIOMAC — Plan de implementación del flujo operativo de predicción

**Estado:** plan vigente del MVP técnico local  
**Versión:** `1.2.1`  
**Fuente arquitectónica:** `arquitectura.md`  
**Contrato API:** `API-sign.md`  
**Diccionario:** `diccionario-de-datos.md`  
**Alcance vigente:** Entregable 2, ejecución y validación local reproducible  

> Este documento resume el orden, alcance y estado de HU001–HU010. Los documentos `hu00x_*.md` son la especificación detallada de cada historia. Ante discrepancias, prevalecen la arquitectura, el contrato API, el diccionario de datos y la HU específica más reciente.

## 1. Alcance vigente

El flujo operativo implementado para el Entregable 2 es:

```text
analista carga CSV mensual ya preparado
→ backend valida la carga
→ backend construye ChampionInput
→ ChampionService obtiene ChampionOutput
→ backend valida feature contract input ↔ Champion
→ se mapea y persiste el snapshot
→ dashboard consulta/muestra el resultado
→ Refresh consulta únicamente el último snapshot persistido
```

### Decisión de alcance académico vigente

Para esta entrega, el analista carga un CSV de un único mes **ya preparado con las features requeridas por el Champion**. El backend no construye lags, rolling, canal endémico, SIR, estacionalidad ni otras features desde datos crudos.

La integración obligatoria y el cierre de HU010 son **local-only**:

```text
Dashboard React local
        ↓ HTTP
FastAPI local
        ↓
HU002–HU009
        ↓
SQLite local
        ↓
ChampionService configurado localmente
```

El Champion puede consumirse detrás de HU004 mediante salida materializada real de PR #12 o mediante una estrategia ejecutable equivalente. HU005+ no dependen del mecanismo concreto.

### Fuera de alcance del cierre HU010

- AWS/EC2 como gate de aceptación;
- deployment remoto de Lovable;
- S3/RDS como runtime obligatorio;
- autenticación/RBAC;
- entrenamiento/reentrenamiento;
- tuning, experimentación o promoción de Champion;
- feature engineering desde datos crudos;
- SHAP online;
- `dvc pull`, entrenamiento o acceso obligatorio a MLflow durante requests.

Estos elementos pueden formar parte de una evolución posterior, pero **no se documentan como PASS ni como requisito para cerrar HU010 si no fueron ejecutados**.

---

## 2. Arquitectura física vigente y arquitectura futura

### 2.1 Arquitectura obligatoria para el Entregable 2

```text
┌─────────────────────────────────────┐
│ Dashboard React BIOMAC local        │
│ - upload mensual                    │
│ - latest/history                    │
│ - Refresh read-only                 │
└─────────────────┬───────────────────┘
                  │ HTTP / JSON
                  │ VITE_BIOMAC_API_BASE_URL
                  v
┌─────────────────────────────────────┐
│ FastAPI + Uvicorn local             │
│ ├─ HU001 contratos/API              │
│ ├─ HU002 validación CSV             │
│ ├─ HU003 ChampionInput              │
│ ├─ HU004 ChampionService + gate     │
│ ├─ HU005 orquestación               │
│ ├─ HU006 SQLite                     │
│ ├─ HU007 API read-only              │
│ └─ HU009 enrichments                │
└─────────────────┬───────────────────┘
                  │
                  v
┌─────────────────────────────────────┐
│ SQLite local + Champion provider    │
│ materializado/ejecutable            │
└─────────────────────────────────────┘
```

Reglas vigentes:

- `VITE_BIOMAC_API_BASE_URL` es configurable y no se hardcodea en componentes;
- SQLite permanece detrás de interfaces de repositorio;
- el upload mensual es el trigger de una nueva ejecución;
- `GET latest`, `GET history`, `GET runs/{run_id}` y Refresh son read-only;
- no existe fallback productivo a mocks;
- datos no disponibles permanecen `null`/`available=false`;
- ningún GET ejecuta Champion, genera SHAP, accede a DVC/S3 ni entrena modelos;
- `feature_contract_version` y `feature_contract_sha256` deben coincidir entre input/API y Champion antes de mapping/persistencia;
- un mismatch contractual produce `FAILED`, no `COMPLETED`.

### 2.2 Arquitectura futura de deployment — referencia, no gate actual

Una evolución posterior puede desplegar:

```text
Lovable / frontend remoto
        ↓ HTTPS
FastAPI + Champion en EC2
        ↓
persistencia/artefactos materializados
```

DVC/S3 puede utilizarse durante deployment para materializar datos/artefactos, y MLflow puede aportar trazabilidad. Ninguno forma parte del ciclo normal de request. Esta arquitectura futura **no reemplaza el alcance local vigente de HU010**.

---

## 3. Orden y estado de implementación

| Orden | HU | Nombre | Objetivo | Dependencias | Estado |
|---:|---|---|---|---|---|
| 1 | HU-INT-001 | Base FastAPI y contratos | API v2, configuración, health, schemas y errores comunes. | arquitectura/API | COMPLETADA |
| 2 | HU-INT-002 | Carga mensual y validación | Validar CSV mensual ya preparado, periodo, ciudades, 39 features y hash. | HU001 | COMPLETADA |
| 3 | HU-INT-003 | Adaptación a ChampionInput | Ordenar/convertir la carga validada al contrato exacto del Champion y transportar version/hash. | HU002 | COMPLETADA — HANDOFF REFORZADO |
| 4 | HU-INT-004 | Adapter/servicio del Champion | Exponer `ChampionOutput` detrás de una frontera estable e intercambiable y validar compatibilidad contractual. | HU003 + Champion | AJUSTE PENDIENTE |
| 5 | HU-INT-005 | Orquestación del run | Coordinar validación → preparación → Champion → mapping. | HU002/003/004 | COMPLETADA |
| 6 | HU-INT-006 | Persistencia y trazabilidad | Persistir runs/snapshots e idempotencia durable en SQLite. | HU005 | COMPLETADA |
| 7 | HU-INT-007 | API de consulta | `latest`, `history` y detalle de run sin ejecutar Champion. | HU006 | COMPLETADA |
| 8 | HU-INT-008 | Integración dashboard | Sustituir mocks por HTTP, upload y Refresh read-only. | HU005/007 | COMPLETADA |
| 9 | HU-INT-009 | Metadata, calidad y explicabilidad | Enriquecer solo con información real/nullable y explicación local cuando exista. | HU004/006/007/008 | COMPLETADA |
| 10 | HU-INT-010 | Pruebas E2E y cierre local | Validar HU001–HU009 de extremo a extremo y cerrar el MVP técnico local. | HU001–HU009 | BLOQUEADA — FEATURE CONTRACT MISMATCH |

---

# HU-INT-001 — Base FastAPI y contratos

**Como** equipo de integración, **quiero** una API versionada y testeable **para** separar el dashboard de la lógica de inferencia.

Alcance implementado:

- `/api/v2`;
- `GET /health`;
- configuración por variables de entorno;
- middleware `request_id`;
- CORS configurable;
- schemas y errores estables;
- OpenAPI automático.

Criterios esenciales: health 200, errores saneados, configuración sensible fuera de Git y pruebas locales verdes.

---

# HU-INT-002 — Carga mensual lista para inferencia

`POST /api/v2/monthly-runs` recibe `file` + `reference_month`.

El contrato vigente exige:

- CSV UTF-8/UTF-8-SIG no vacío;
- periodo `YYYY-MM`;
- exactamente Bucaramanga `68001` y Cali `76001`;
- una fila por municipio;
- 39 features Champion presentes, numéricas, finitas y no nulas;
- rechazo de columnas objetivo/futuras prohibidas;
- SHA-256 de la carga;
- ningún acceso a cloud/modelos durante validación.

HU002 **no realiza feature engineering**.

---

# HU-INT-003 — Adaptación mínima a ChampionInput

Entrada:

```text
ValidatedMonthlyUpload
```

Salida:

```text
ChampionInput
```

Responsabilidades:

- fuente centralizada `CHAMPION_FEATURES`;
- orden municipal `68001`, `76001`;
- orden exacto de 39 features;
- conversión numérica estable;
- preservación de corte, hash y feature contract;
- exclusión de IDs/targets de la matriz.

HU003 no crea lags/rolling/percentiles/canal, no imputa, no lee `features_mensual.parquet` en runtime y no ejecuta el Champion.

### Ajuste documental derivado de HU010

`feature_contract_version` y `feature_contract_sha256` producidos/transportados por HU003 son el contrato efectivo del input del run. HU003 no debe reemplazarlos ni alinearlos artificialmente con el Champion. HU004 debe usarlos para la comparación obligatoria antes de aceptar la salida.

---

# HU-INT-004 — Frontera del Champion

HU004 expone una frontera estable mediante `ChampionService`/`ChampionOutput` para evitar que FastAPI, orquestación y dashboard dependan de XGBoost, pickle, MLflow, JSON físico o una estrategia concreta.

## Camino vigente del MVP

```text
ChampionResult PR12
→ MaterializedOutputAdapter
→ feature contract gate
→ ChampionOutput
```

## Camino compatible futuro

```text
ChampionInput
→ ExecutableChampionAdapter
→ feature contract gate
→ ChampionOutput
```

No existe fallback automático entre estrategias.

`ChampionOutput` conserva únicamente datos respaldados por la fuente real: municipio, horizonte, target month, output nativo, probability cuando existe, threshold real por horizonte, label cuando corresponde y metadata del Champion.

### Gate obligatorio pendiente

Antes de entregar un output válido debe cumplirse:

```text
champion.feature_contract_version == input.feature_contract_version
champion.feature_contract_sha256   == input.feature_contract_sha256
```

Si no coincide:

```text
FAILED
CHAMPION_INPUT_INVALID
reason = feature_contract_mismatch
```

No debe alcanzarse mapping/persistencia exitosa ni `201 COMPLETED`.

DVC/S3/MLflow no forman parte obligatoria de cada request.

---

# HU-INT-005 — Orquestación del run mensual

Flujo lógico:

```text
RECEIVED
→ VALIDATING
→ PREPARING
→ INFERENCING
→ CONTRACT CHECK
→ MAPPING
→ READY_TO_PERSIST
```

Ante error:

```text
cualquier estado → FAILED
```

HU005 genera trazabilidad, coordina HU002/HU003/HU004 y produce `PredictionSnapshotCandidate`. La idempotencia lógica usa:

```text
reference_month + source_file_sha256 + champion_version
```

La persistencia durable pertenece a HU006.

---

# HU-INT-006 — Persistencia y trazabilidad

**Estado:** `[COMPLETADA — DESARROLLO]`

HU006 usa SQLite local configurable mediante `BIOMAC_DB_PATH` detrás de interfaces de repositorio.

La transición exitosa es:

```text
READY_TO_PERSIST → PERSISTING → COMPLETED
```

Run y predicciones se confirman transaccionalmente antes de devolver HTTP 201. Un fallo produce rollback y error controlado.

`latest` solo puede provenir de runs `COMPLETED`; runtime DB/artefactos no se versionan en Git.

---

# HU-INT-007 — API de consulta read-only

**Estado:** `[COMPLETADA — DESARROLLO]`

Endpoints:

- `GET /api/v2/runs/{run_id}`;
- `GET /api/v2/predictions/latest`;
- `GET /api/v2/predictions/history`.

Las consultas usan servicios/repo de lectura SQLite y no dependen de Champion. `latest` selecciona el último run `COMPLETED`; `history` conserva orden determinista y filtros/paginación.

Regla crítica:

```text
GET / Refresh
→ lectura persistida
→ cero inferencia
```

---

# HU-INT-008 — Integración dashboard

**Estado:** `[COMPLETADA — DESARROLLO]`

La composición normal usa `HttpDengueRepository` y `VITE_BIOMAC_API_BASE_URL`.

Comportamiento:

- apertura → `GET latest`;
- `Actualizar datos` → `POST monthly-runs`;
- POST exitoso → refetch de datos canónicos;
- Refresh → únicamente `GET latest`;
- errores conservan el último snapshot válido;
- no existe fallback silencioso a mocks;
- React no calcula probability, label, threshold, canal, SHAP ni features.

Para HU010, un POST exitoso debe invalidar/refetchear **latest e history**; Refresh manual continúa latest-only.

El deployment remoto de Lovable es evolución posterior y no es gate de cierre del Entregable 2.

---

# HU-INT-009 — Metadata, explicabilidad y calidad

**Estado:** `[COMPLETADA — DESARROLLO]`

HU009 agrega de forma aditiva y trazable:

- metadata opcional del Champion;
- `decision_rule` por predicción;
- `data_quality`;
- `current_status` parcial cuando existe fuente válida;
- explicación local únicamente cuando existe evidencia exacta;
- warnings visibles;
- historial presentado como **Historial de predicciones**.

Disponibilidad vigente:

- `data_quality`: disponible desde la entrada validada;
- `p25`, `p75`, `zona_canal`: disponibles desde el corte contractual;
- `observed_cases`, `p50`, `ratio_to_p75` y completitudes por grupo: `null` cuando no existe fuente contractual suficiente;
- SHAP local: `available=false` en operación actual si no están materializados los parquets compatibles.

Una importancia global nunca se presenta como SHAP local. Snapshots HU006 legacy continúan siendo legibles sin inventar enrichments.

---

# HU-INT-010 — Pruebas E2E y cierre local

**Estado:** `[IMPLEMENTADA — BLOQUEADA POR FEATURE CONTRACT MISMATCH]`

**Como** equipo BIOMAC, **quiero** demostrar que HU001–HU009 funcionan juntas de forma reproducible **para** cerrar el MVP técnico local con evidencia verificable.

Documento detallado:

```text
dashboard_prototipos/docs/hu010_e2e_cierre_integracion.md
```

## Objetivo

Validar el flujo:

```text
CSV mensual válido
→ POST monthly-runs
→ HU002/HU003
→ ChampionService HU004
→ feature contract gate
→ HU005
→ HU006 SQLite
→ GET latest/history/run
→ Dashboard HTTP
```

La prueba académica usa una salida materializada real de PR #12, manteniendo PR12 y `main`/rama de integración en checkouts separados.

## Escenarios obligatorios

HU010 cubre, como mínimo:

1. health local;
2. POST válido → `201 COMPLETED` solo con contratos coincidentes;
3. correspondencia Champion ↔ API para Bucaramanga/Cali × T+1/T+2;
4. persistencia SQLite del mismo run;
5. `GET latest`;
6. `GET history`;
7. `GET runs/{run_id}`;
8. idempotencia durable;
9. mismo periodo con contenido diferente sin sobrescritura silenciosa;
10. uploads inválidos antes de Champion;
11. Champion no disponible y preservación del latest previo;
12. reinicio de FastAPI conservando SQLite;
13. latest/Refresh con contador de Champion sin incremento;
14. history read-only;
15. frontend happy path;
16. upload frontend → latest + history actualizados;
17. Refresh frontend latest-only;
18. error frontend sin pérdida del snapshot ni fallback mock;
19. feature contract mismatch → `FAILED`, sin nuevo snapshot `COMPLETED`.

## Corrección de integración incluida en HU010

Después de un POST `COMPLETED`:

```text
invalidate latestPredictionKey
+
invalidate predictionHistoryKey
```

El botón Refresh manual sigue ejecutando únicamente `latest`.

## Reglas de evidencia

- un escenario no ejecutado no puede marcarse PASS;
- estados válidos: `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`, `OUT_OF_SCOPE`;
- golden fixture solo si deriva de una salida real PR12 con SHA, periodo y hash documentados;
- no se inventan predicciones para automatizar E2E;
- no se editan hashes/versiones contractuales para forzar compatibilidad;
- Browser E2E puede automatizarse con Playwright solo si se implementa y ejecuta de forma reproducible; de lo contrario se documenta como manual;
- AWS/deployment remoto se marca `OUT_OF_SCOPE`, no PASS.

## Definition of Done HU010

HU010 puede declararse:

```text
[COMPLETADA — DESARROLLO / E2E LOCAL]
```

cuando:

- el POST real produce `COMPLETED` con feature contract idéntico;
- Champion/API/SQLite coinciden;
- mismatch contractual falla controladamente;
- latest/history/run funcionan;
- idempotencia está demostrada;
- fallos conservan latest;
- reinicio conserva datos;
- GET/Refresh demuestran cero Champion;
- POST exitoso actualiza latest e history;
- frontend no usa mocks ni lógica analítica;
- nullability HU009 se conserva;
- suites backend/frontend están verdes;
- evidencia E2E queda versionada;
- no se versionan secretos, DB, CSV, parquets o modelos runtime;
- infraestructura cloud no se presenta como validada sin haberse ejecutado.

---

## 4. Secuencia de validación local del MVP

La secuencia vigente de cierre es:

```text
1. Main/rama contiene HU001–HU009 aprobadas
2. Crear/activar entorno Python local
3. Ejecutar baseline API
4. Preparar SQLite dedicada de prueba
5. Materializar/configurar ChampionService local
6. Preparar CSV mensual compatible HU002
7. Comparar feature contract input/API ↔ Champion
8. Levantar FastAPI/Uvicorn local
9. Verificar GET /api/v2/health
10. Configurar VITE_BIOMAC_API_BASE_URL del frontend local
11. Ejecutar POST → COMPLETED solo si contrato coincide
12. Verificar latest/history/run y SQLite
13. Ejecutar mismatch → FAILED controlado
14. Verificar idempotencia/errores/restart/read-only
15. Ejecutar frontend y pruebas de integración
16. Registrar evidencia y resultados reales
```

No forman parte del ciclo normal de request:

- `git pull`;
- `dvc pull`;
- instalación de paquetes;
- entrenamiento;
- consulta obligatoria a MLflow;
- generación de SHAP.

### Secuencia futura de deployment — fuera del cierre actual

Una futura fase podrá incluir clone/pull en EC2, materialización de artefactos, configuración CORS/HTTPS, despliegue del frontend y pruebas remotas. Ese trabajo no condiciona la finalización de HU010 local.

---

## 5. Definición global de terminado — Entregable 2

El **MVP técnico local** se considera cerrado cuando:

- HU001–HU009 están completadas, incluido el ajuste contractual de HU004;
- HU010 demuestra el flujo E2E local con evidencia reproducible;
- `HttpDengueRepository` es la fuente normal del dashboard;
- el upload mensual dispara la nueva ejecución;
- HU002 valida el CSV ya preparado;
- HU003 produce un `ChampionInput` reproducible y conserva feature contract version/hash;
- HU004 entrega `ChampionOutput` trazable detrás de una frontera intercambiable y bloquea mismatches;
- una predicción exitosa se persiste antes del 201;
- `latest`, `history`, `run` y Refresh leen resultados persistidos sin inferencia;
- errores no destruyen el último resultado válido;
- Bucaramanga y Cali muestran T+1/T+2 solo según salidas reales;
- metadata/enrichments respetan nullability y disponibilidad real;
- no existe fallback productivo a mocks;
- entrenamiento, selección de Champion y feature engineering desde datos crudos permanecen fuera de alcance;
- pruebas y evidencia local están versionadas.

### Readiness de producción futuro

No forma parte de la definición de terminado del Entregable 2. Incluye, entre otros:

- deployment remoto;
- HTTPS y dominio;
- CORS del dominio real;
- autenticación/autorización;
- estrategia durable de infraestructura/backup;
- observabilidad/SLO;
- CI/CD y pruebas de deployment.

---

## 6. Regla arquitectónica HU004 para HU005–HU010

A partir de HU005, el sistema recibe un `ChampionService` y entrega un `ChampionOperationalContext` neutral a `produce(...)`. El resultado es `ChampionOutput` únicamente si superó el gate contractual.

HU005–HU010 no pueden depender estructuralmente de `ChampionResult`, JSON físico, `generate_champion_output.py`, pickle/XGBoost, `.whl` o de cómo se produjo la predicción.

Flujo conceptual:

```text
ChampionService configurado en HU004
→ produce(operational_context)
→ validar feature contract
→ ChampionOutput
→ HU005 ResultMapper/orquestación
→ HU006 persistencia
→ HU007 API read-only
→ HU008 dashboard
→ HU009 metadata/explicabilidad
→ HU010 E2E local
```

Cambiar de `MaterializedOutputAdapter` a `ExecutableChampionAdapter` debe requerir cambios de HU004/composición/configuración, no un refactor estructural de HU005+.

---

## 7. Estado al continuar HU010

- HU001–HU002 y HU005–HU009: `[COMPLETADAS — DESARROLLO]`.
- HU003: `[COMPLETADA — DESARROLLO / HANDOFF CONTRACTUAL REFORZADO]`.
- HU004: `[AJUSTE DE INTEGRACIÓN PENDIENTE — FEATURE CONTRACT GATE]`.
- HU010: `[IMPLEMENTADA — BLOQUEADA POR FEATURE CONTRACT MISMATCH]`.
- Persistencia actual: SQLite local.
- Frontend: React + `HttpDengueRepository` + React Query.
- Explicación SHAP operacional: unavailable salvo que se materialice/configure una fuente local compatible.
- Deployment AWS/Lovable remoto: evolución posterior, fuera del gate HU010.

## 8. Resultado de implementación HU010

Se validaron dos niveles:

```text
pytest -q api/tests/test_e2e_champion_real.py
8 passed, 1 warning

pytest -q api/tests/test_e2e_local.py api/tests/test_e2e_champion_real.py
16 passed, 1 warning
```

Además se levantó FastAPI con Uvicorn real y se ejecutó HTTP mediante `httpx`, sin `TestClient`:

```text
GET  /api/v2/health                 200
POST /api/v2/monthly-runs           201
GET  /api/v2/predictions/latest     200
GET  /api/v2/predictions/history    200
GET  /api/v2/runs/{run_id}          200
run.status                           COMPLETED
predictions                          4
```

Persistencia observada:

```text
runs                     1
predictions              4
snapshot_quality         1
current_status           2
prediction_enrichments   4
champion_enrichments     1
```

Las cuatro probabilidades/thresholds/labels coincidieron con `champion_output.json`. Sin embargo, el E2E descubrió esta incompatibilidad:

```text
Champion JSON
feature_contract_version = pr12-f5a2d39
feature_contract_sha256   = 3af245ede70851d1616439d80441e2ad6f5d3f6465b9798d6b67fed3adb3e3dc

CSV/API vigente
feature_contract_version = pr12-74e385c3
feature_contract_sha256   = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

El adapter materializado preserva la metadata, pero la implementación actual no exige igualdad antes de devolver `COMPLETED`. Por ello:

```text
Infra/API HTTP:                APROBADO
Persistencia SQLite:           APROBADA
Correspondencia de outputs:    APROBADA
Feature contract Model→API:    NO APROBADO
HTTP E2E REAL:                 NO APROBADO
HU010:                         BLOQUEADA
```

El siguiente ajuste es implementar el gate HU004, alinear el contrato canónico entre PR12 y API sin reescribir metadata artificialmente y repetir el happy path + escenario mismatch.