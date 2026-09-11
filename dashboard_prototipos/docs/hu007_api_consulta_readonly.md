# HU007 — API de consulta read-only

**Estado:** `[DEFINIDA — LISTA PARA IMPLEMENTACIÓN]`  
**Ámbito:** Entregable 2, local-only  
**Dependencia:** HU006 completada  
**Contrato base:** `API-sign.md`  
**Arquitectura:** `arquitectura.md`  
**Plan:** `implementacion.md`

---

## 1. Identificación

- **HU:** HU-INT-007
- **Nombre:** API de consulta read-only
- **Prioridad:** Alta
- **Actor principal:** usuario consultor / dashboard BIOMAC
- **Dependencias:** HU001, HU006
- **Habilita:** HU008 — integración dashboard

---

## 2. Historia de usuario

**Como** usuario consultor  
**quiero** consultar runs y predicciones ya persistidas  
**para** abrir o refrescar BIOMAC sin ejecutar nuevamente el Champion.

---

## 3. Objetivo verificable

Implementar endpoints HTTP `GET` sobre los datos durables de HU006, de forma que:

1. `GET /api/v2/runs/{run_id}` recupere trazabilidad de un run existente;
2. `GET /api/v2/predictions/latest` devuelva el último snapshot `COMPLETED` compatible con los filtros solicitados;
3. `GET /api/v2/predictions/history` devuelva historial persistido, paginado y ordenado;
4. ninguna consulta ejecute validación de upload, preparación de features, Champion, inferencia ni persistencia nueva;
5. ninguna respuesta fabrique campos epidemiológicos o de explicabilidad que HU006 no haya persistido.

---

## 4. Decisiones vigentes

### 4.1 Local-only

Para Entregable 2 la consulta usa únicamente SQLite local mediante la infraestructura de HU006.

Fuera de alcance:
- AWS;
- EC2;
- S3;
- RDS;
- Supabase;
- MLflow serving;
- DVC runtime;
- servicios externos;
- red distinta de la propia API local.

### 4.2 `Refresh` es estrictamente read-only

Abrir el dashboard o refrescarlo debe producir únicamente:

```text
Dashboard
→ GET /api/v2/predictions/latest
→ SQLite
→ JSON
```

Nunca:

```text
Refresh
→ ChampionService
→ inferencia
```

### 4.3 Fuente de verdad

HU007 lee únicamente runs/snapshots persistidos por HU006.

No reconstruye predicciones desde:
- CSV originales;
- PR12;
- modelos serializados;
- DVC;
- MLflow;
- backtesting;
- mocks.

### 4.4 No enriquecimiento ficticio

HU006 persiste `PredictionSnapshotCandidate`, que contiene datos reales del run/Champion y sus predicciones. HU007 no debe inventar para completar `PredictionSnapshot`:

- `data_quality`;
- `current_status`;
- P25/P50/P75 ausentes;
- historia epidemiológica no persistida;
- incertidumbre;
- SHAP/explicación;
- `target_definition` no respaldada por metadata persistida;
- metadata de entrenamiento inexistente.

Los enriquecimientos reales quedan para HU009 o para una evolución explícita del modelo de persistencia.

---

## 5. Arquitectura lógica

```text
FastAPI GET
   ↓
PredictionQueryService / RunQueryService
   ↓
Read repositories / ports
   ↓
SQLite HU006
   ↓
Read DTO / response mapper
   ↓
HTTP JSON
```

Reglas:
- endpoints delgados;
- SQL exclusivamente en infraestructura SQLite;
- services no importan `sqlite3`;
- API no importa ChampionService ni adapters;
- lectura no modifica estado durable.

---

## 6. Endpoints

### 6.1 `GET /api/v2/runs/{run_id}`

#### Propósito

Consultar la trazabilidad de un run persistido, exitoso o fallido.

#### Respuesta `200`

Debe incluir únicamente datos persistidos, por ejemplo:

```json
{
  "schema_version": "2.0.0",
  "request_id": "<request-id-http>",
  "run": {
    "run_id": "biomac-2026-08-abc123",
    "status": "COMPLETED",
    "reference_month": "2026-08",
    "stages": ["RECEIVED", "VALIDATING", "PREPARING", "INFERENCING", "MAPPING", "READY_TO_PERSIST", "PERSISTING", "COMPLETED"],
    "created_at": "2026-09-03T12:00:00Z",
    "finished_at": "2026-09-03T12:00:03Z",
    "completed_at": "2026-09-03T12:00:03Z",
    "source_file_sha256": "...",
    "champion_version": "...",
    "error": null
  }
}
```

Para run `FAILED`, `error` debe incluir `code`, `stage` y `message` saneado si existen.

#### No encontrado

`404 RUN_NOT_FOUND`.

---

### 6.2 `GET /api/v2/predictions/latest`

#### Propósito

Devolver el último snapshot persistido cuyo run esté `COMPLETED`.

#### Filtros HU007

- `municipality_codes`: opcional; uno o varios códigos entre `68001`, `76001`;
- `horizons`: opcional; `T+1`, `T+2`;

Los parámetros históricos definidos en `API-sign.md` (`history_months`, `include_explanations`) no deben generar datos inexistentes. En HU007 pueden:
- mantenerse aceptados con semántica explícita y sin enriquecimiento; o
- diferirse documentadamente a HU009 si aún no son consumibles.

La decisión implementada debe conservar compatibilidad hacia adelante y quedar documentada.

#### Semántica de `latest`

`latest` significa:

> snapshot asociado al run `COMPLETED` más reciente por `completed_at`; ante empate, usar orden determinista adicional por `run_id`.

Los filtros de municipio/horizonte se aplican al snapshot devuelto, no deben disparar una inferencia diferente.

#### Respuesta `200`

Contrato mínimo real:

```json
{
  "schema_version": "2.0.0",
  "request_id": "<request-id-http>",
  "prediction_snapshot": {
    "run_id": "...",
    "generated_at": "...",
    "reference_month": "YYYY-MM",
    "source_file_sha256": "...",
    "champion": {
      "name": "...",
      "version": "...",
      "output_type": "probability",
      "supported_horizons": ["T+1", "T+2"],
      "feature_contract_version": "...",
      "feature_contract_sha256": "..."
    },
    "predictions": []
  }
}
```

Cada predicción conserva:
- `divipola`;
- `municipality`;
- `horizon`;
- `target_month`;
- `output_type`;
- `probability` nullable;
- `expected_cases` nullable;
- `risk_score` nullable;
- `label` nullable;
- `decision_threshold` nullable.

#### Sin predicciones exitosas

`404 PREDICTION_NOT_FOUND` con error estable.

No usar `200` con una predicción mock.

---

### 6.3 `GET /api/v2/predictions/history`

#### Propósito

Consultar snapshots `COMPLETED` ya persistidos.

#### Filtros mínimos

- `municipality_codes`: opcional;
- `horizon`: opcional;
- `from_month`: opcional `YYYY-MM`;
- `to_month`: opcional `YYYY-MM`;
- `limit`: opcional, default `20`, rango `1..100`;
- `offset`: opcional, default `0`, `>=0`.

Reglas:
- `from_month <= to_month`;
- municipios permitidos: `68001`, `76001`;
- horizonte permitido: `T+1`, `T+2`;
- meses inválidos producen `400 INVALID_REQUEST`;
- filtros se aplican sobre datos persistidos, no sobre reconstrucciones.

#### Orden

Orden descendente por:

1. `reference_month`;
2. `completed_at`;
3. `run_id` como desempate determinista.

#### Respuesta `200`

```json
{
  "schema_version": "2.0.0",
  "request_id": "<request-id-http>",
  "items": [],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "returned": 0
  }
}
```

Cada `item` debe identificar como mínimo:
- `run_id`;
- `reference_month`;
- `generated_at`;
- `completed_at`;
- metadata Champion mínima;
- predicciones filtradas.

#### Historial vacío

Debe responder `200` con `items=[]` y paginación consistente.

Esto permite representar un estado empty sin tratar una colección vacía como fallo técnico.

---

## 7. Contratos read-only

Crear DTOs/schemas estrictos para las respuestas GET.

Recomendación:

```text
RunReadResponse
PredictionSnapshotReadResponse
PredictionHistoryResponse
PaginationMeta
```

Reglas:
- `extra="forbid"` donde aplique;
- ISO-8601 UTC;
- DIVIPOLA string de 5 dígitos;
- `probability` sigue nullable;
- nunca convertir `risk_score` o `expected_cases` a probabilidad;
- no recomputar `label` desde threshold en HU007;
- no recalcular `target_month`;
- preservar exactamente lo persistido.

---

## 8. Puertos y repositorios de lectura

HU007 debe ampliar/reutilizar las abstracciones existentes sin acoplar servicios a SQLite.

Capacidades requeridas conceptualmente:

### Runs

```python
get(run_id)
```

### Predictions / snapshots

```python
get_by_run_id(run_id)
get_latest_completed(...)
list_completed(...)
```

Puede existir un `PredictionQueryRepository` dedicado si evita inflar los puertos de escritura.

La decisión debe priorizar separación CQRS ligera:
- HU006: escritura/transacción;
- HU007: lectura/query.

No se requiere una infraestructura compleja de CQRS.

---

## 9. Restricción de side effects

Las operaciones GET no deben:

- insertar/update/delete SQLite;
- cambiar `RunStatus`;
- crear run_id;
- generar idempotency keys;
- tocar archivos runtime;
- ejecutar ChampionService;
- leer CSV de upload;
- ejecutar feature engineering;
- ejecutar PR12/modelos;
- acceder a cloud.

---

## 10. Errores

Reutilizar `ContractError` y `ErrorCode` existentes.

### `RUN_NOT_FOUND`
- HTTP `404`;
- para `GET /runs/{run_id}` inexistente.

### `PREDICTION_NOT_FOUND`
- HTTP `404`;
- para `latest` cuando no existe ningún run `COMPLETED` compatible.

### `INVALID_REQUEST`
- HTTP `400`;
- filtros inválidos;
- rangos de meses inválidos;
- municipio/horizonte fuera de contrato;
- limit/offset inválidos.

### `PERSISTENCE_FAILED`
- HTTP `500`;
- fallo real de acceso al storage.

No exponer:
- SQL;
- stack traces;
- rutas locales;
- secretos.

---

## 11. Alcance local del Entregable 2

HU007 debe poder probarse completamente con:

```text
FastAPI TestClient
+ SQLite tmp_path
+ snapshots/runs persistidos por HU006
```

No requiere la prueba funcional aplazada ni un Champion real para validar sus contratos read-only.

Las fixtures pueden construir/persistir resultados reales de dominio mediante HU006, pero no deben invocar inferencia durante los GET.

---

## 12. Fuera de alcance

No implementar en HU007:

- Lovable / React;
- sustitución de mocks frontend;
- upload nuevo;
- entrenamiento/reentrenamiento;
- inferencia;
- Champion executable/materialized;
- SHAP;
- explicación local;
- data quality calculada;
- canal endémico adicional;
- observados históricos no persistidos;
- exportación PDF/CSV;
- autenticación/autorización;
- Docker;
- AWS/cloud.

HU008 conectará el dashboard. HU009 abordará metadata/explicabilidad/calidad real adicional.

---

## 13. Tareas DWP

### T01 — Baseline
- ejecutar suite `api/tests`;
- registrar conteo y warnings antes de cambios.

### T02 — Read contracts
- definir schemas DTO estrictos;
- conservar nullability real.

### T03 — Query ports
- diseñar/ajustar puertos de lectura;
- separar queries de escritura cuando aporte claridad.

### T04 — SQLite read repository
- `get run`;
- `latest completed`;
- `history completed`;
- filtros y paginación;
- orden determinista.

### T05 — Query services
- implementar servicios framework-neutral;
- mapear not-found/storage failure.

### T06 — `GET /runs/{run_id}`
- 200/404;
- failed/completed;
- request_id HTTP.

### T07 — `GET /predictions/latest`
- filtros;
- solo `COMPLETED`;
- 404 empty;
- no inferencia.

### T08 — `GET /predictions/history`
- filtros;
- rango;
- limit/offset;
- `200 items=[]`.

### T09 — Composition root
- inyectar servicios read-only en `create_app`;
- configuración local SQLite existente.

### T10 — Regression
- tests focales;
- suite completa;
- compileall;
- pip check.

### T11 — Documentación/evidencia
- crear `hu007_evidencia_implementacion.md`;
- actualizar `API-sign.md`, `arquitectura.md`, `implementacion.md` solo si corresponde.

---

## 14. Criterios de aceptación CA01–CA24

| CA | Criterio |
|---|---|
| CA01 | Baseline previo registrado. |
| CA02 | Existen los tres endpoints GET contractuales. |
| CA03 | `GET /runs/{run_id}` recupera run `COMPLETED`. |
| CA04 | `GET /runs/{run_id}` recupera run `FAILED` con error saneado. |
| CA05 | Run inexistente devuelve `404 RUN_NOT_FOUND`. |
| CA06 | `latest` considera únicamente runs `COMPLETED`. |
| CA07 | `latest` selecciona el más reciente de forma determinista. |
| CA08 | `latest` permite ambas ciudades por defecto. |
| CA09 | `latest` filtra municipio sin recalcular predicción. |
| CA10 | `latest` filtra horizontes sin recalcular predicción. |
| CA11 | Sin `COMPLETED`, `latest` devuelve `404 PREDICTION_NOT_FOUND`. |
| CA12 | `history` devuelve únicamente runs `COMPLETED`. |
| CA13 | `history` ordena por corte/generación en descendente. |
| CA14 | `history` soporta `from_month`/`to_month`. |
| CA15 | `history` soporta filtro de municipio/horizonte. |
| CA16 | `history` soporta `limit`/`offset`. |
| CA17 | Historial vacío devuelve `200 items=[]`. |
| CA18 | Filtros inválidos devuelven `INVALID_REQUEST`. |
| CA19 | GET no invoca ChampionService ni orquestador de inferencia. |
| CA20 | GET no realiza escrituras en SQLite. |
| CA21 | Respuestas preservan nullable y outputs reales sin enriquecimiento ficticio. |
| CA22 | SQL permanece confinado a infraestructura SQLite. |
| CA23 | No existe dependencia AWS/cloud/MLflow/DVC/modelo en query path. |
| CA24 | Suite completa y documentación quedan verdes/versionadas. |

---

## 15. Autovalidaciones AV01–AV22

| AV | Procedimiento esperado |
|---|---|
| AV01 | Persistir un `COMPLETED` con HU006 y recuperarlo por run_id. |
| AV02 | Persistir un `FAILED` y recuperarlo con error. |
| AV03 | Consultar run inexistente y comprobar 404/código. |
| AV04 | Persistir dos `COMPLETED` y verificar que `latest` retorna el último. |
| AV05 | Insertar un `FAILED` más reciente y verificar que no desplaza `latest`. |
| AV06 | Filtrar `latest` por `68001`. |
| AV07 | Filtrar `latest` por `76001`. |
| AV08 | Filtrar `latest` por `T+1`. |
| AV09 | Filtrar `latest` por `T+2`. |
| AV10 | Validar `latest` vacío. |
| AV11 | Validar history ordenado desc. |
| AV12 | Validar `from_month` y `to_month`. |
| AV13 | Validar limit/offset. |
| AV14 | Validar history vacío. |
| AV15 | Validar municipio inválido. |
| AV16 | Validar horizonte inválido. |
| AV17 | Validar rango de meses inválido. |
| AV18 | Spy/fake demuestra cero llamadas a ChampionService durante GET. |
| AV19 | Verificar que cantidad/estado de filas SQLite no cambia después de GET. |
| AV20 | Import path HU007 no carga xgboost/lightgbm/mlflow/dvc/boto3. |
| AV21 | `compileall` y `pip check` PASS. |
| AV22 | Suite API completa PASS con conteos registrados. |

---

## 16. Definition of Done

HU007 puede marcarse `[COMPLETADA — DESARROLLO]` solo si:

- los tres endpoints GET existen;
- todos son read-only;
- `latest` nunca ejecuta Champion;
- `latest` solo usa `COMPLETED`;
- history consulta únicamente persistencia;
- filtros y paginación son deterministas;
- empty/not-found están diferenciados correctamente;
- no se fabrican campos para completar el dashboard;
- HU006 no pierde atomicidad ni idempotencia;
- no hay AWS/cloud;
- CA01–CA24 PASS;
- AV01–AV22 PASS;
- suite completa verde;
- evidencia versionada.

---

## 17. Gate hacia HU008

HU008 queda habilitada cuando el frontend pueda realizar de forma estable:

```text
GET /api/v2/predictions/latest
```

para apertura y Refresh, y pueda consultar:

```text
GET /api/v2/predictions/history
GET /api/v2/runs/{run_id}
```

sin que ninguna de esas operaciones ejecute el Champion.

La integración del dashboard debe consumir exactamente la información disponible; cualquier enriquecimiento adicional se abordará explícitamente en HU009 y no mediante mocks silenciosos.