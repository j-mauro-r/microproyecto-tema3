# BIOMAC — Contrato de API para dashboard e inferencia operacional

**Estado:** contrato objetivo  
**Versión del contrato:** `2.0.1`  
**Base path:** `/api/v2`  
**Documentos relacionados:** `arquitectura.md`, `implementacion.md`, `plan.md`, `diccionario-de-datos.md`

> Los ejemplos son ilustrativos. El backend nunca debe fabricar resultados epidemiológicos para completar el contrato.

## 1. Alcance

La API cubre dos flujos distintos:

1. **Actualización mensual:** un analista carga un archivo válido; el backend prepara la entrada, ejecuta/consume el Champion ya aprobado, valida compatibilidad contractual, persiste el resultado y devuelve el estado del run.
2. **Consulta:** abrir el dashboard o presionar `Refresh` recupera la última predicción persistida sin volver a ejecutar el Champion.

El entrenamiento, tuning, comparación, selección y promoción del Champion están fuera de este contrato.

## 2. Principios

- El dashboard presenta; no calcula features, canal, clase, threshold, probabilidad ni SHAP.
- La carga mensual es el trigger normal de inferencia.
- `Refresh` es read-only.
- La API consume un Champion preexistente y versionado.
- Una ejecución fallida no reemplaza la última predicción exitosa.
- `probability` solo se informa si la salida del Champion es realmente probabilística.
- T+1/T+2 solo se exponen cuando están soportados por el Champion.
- No se utilizan datos posteriores al `reference_month`.
- No se usan mocks como fallback ante errores.
- Un resultado Champion solo puede considerarse válido para un run si su `feature_contract_version` y `feature_contract_sha256` coinciden exactamente con el contrato efectivo del input validado/preparado para ese mismo run.
- Un mismatch contractual nunca se degrada a warning ni puede terminar en `201 COMPLETED`.

## 3. Convenciones

- JSON: `snake_case`.
- Mes: `YYYY-MM`.
- Fecha/hora: ISO-8601 UTC.
- DIVIPOLA: string de 5 dígitos.
- Campos desconocidos en schemas JSON: rechazados cuando aplique (`extra="forbid"`).
- `null`: dato contemplado pero no disponible/no aplicable.
- Versionamiento: SemVer.
- Upload: `multipart/form-data`.
- Consultas: `application/json`.

## 4. Endpoints

| Método | Ruta | Propósito | ¿Ejecuta Champion? |
|---|---|---|---:|
| GET | `/api/v2/health` | Salud de API y disponibilidad del Champion | No |
| POST | `/api/v2/monthly-runs` | Procesar nueva carga mensual | **Sí** |
| GET | `/api/v2/runs/{run_id}` | Consultar estado/trazabilidad de un run | No |
| GET | `/api/v2/predictions/latest` | Última predicción exitosa | No |
| GET | `/api/v2/predictions/history` | Historial persistido | No |

No existe un endpoint de `Refresh` que ejecute inferencia.

---

## 5. `GET /api/v2/health`

Respuesta `200`:

```json
{
  "status": "ok",
  "service": "biomac-api",
  "api_version": "2.0.0",
  "champion_ready": true,
  "storage_ready": true
}
```

`champion_ready=true` significa que el adapter puede acceder al Champion configurado y a su metadata mínima. No implica que se haya ejecutado una nueva predicción ni que una carga concreta ya haya superado el gate de feature contract.

---

## 6. `POST /api/v2/monthly-runs`

### 6.1 Request

`Content-Type: multipart/form-data`

Campos:

| Campo | Tipo | Req. | Regla |
|---|---|---:|---|
| `file` | file | Sí | formato/tamaño permitido; no vacío |
| `reference_month` | string | Sí | `YYYY-MM`; nuevo corte a procesar |

El endpoint es síncrono en el MVP: responde cuando el run termina en `COMPLETED` o falla de forma controlada. Si el tiempo de proceso exige asincronía en una fase posterior, `run_id` permitirá evolucionar a `202 + polling`.

### 6.2 Flujo interno contractual

```text
RECEIVED
→ VALIDATING
→ PREPARING
→ INFERENCING
→ CONTRACT_CHECK
→ MAPPING
→ READY_TO_PERSIST
→ PERSISTING
→ COMPLETED
```

`CONTRACT_CHECK` puede implementarse internamente dentro de HU004/HU005 sin convertirse en un nuevo estado público obligatorio, pero su semántica es un gate requerido antes de mapping/persistencia.

Ante fallo:

```text
cualquier etapa → FAILED
```

### 6.2.1 Gate obligatorio de feature contract

Para el mismo run debe cumplirse:

```text
champion.feature_contract_version == input.feature_contract_version
champion.feature_contract_sha256   == input.feature_contract_sha256
```

El `input` corresponde al contrato efectivo usado por HU002/HU003 para validar/preparar la carga. El `champion` corresponde a la metadata de la salida materializada o ejecutable recibida por HU004.

Si alguno difiere:

```text
run → FAILED
error.code → CHAMPION_INPUT_INVALID
error.stage → PREPARING o INFERENCING según el punto de detección
error.details.reason → feature_contract_mismatch
```

No se persiste un snapshot exitoso nuevo y `latest` conserva el último run `COMPLETED` anterior.

### 6.3 Respuesta exitosa `201`

```json
{
  "schema_version": "2.0.0",
  "request_id": "d312a52d-ae4b-4df1-a568-778a998252b2",
  "run": {
    "run_id": "biomac-2026-08-a1b2c3d4",
    "status": "COMPLETED",
    "reference_month": "2026-08",
    "created_at": "2026-09-02T18:30:00Z",
    "completed_at": "2026-09-02T18:30:07Z",
    "source_file": {
      "original_name": "datos_agosto_2026.csv",
      "sha256": "example-sha256",
      "size_bytes": 183421
    },
    "champion": {
      "name": "biomac-champion",
      "version": "1.3.0",
      "mlflow_run_id": "optional-run-id",
      "output_type": "probability",
      "supported_horizons": ["T+1", "T+2"],
      "feature_contract_version": "1.0.0",
      "feature_contract_sha256": "example-feature-contract-sha256"
    }
  },
  "prediction_snapshot": {
    "generated_at": "2026-09-02T18:30:07Z",
    "reference_month": "2026-08",
    "forecasts": []
  }
}
```

`prediction_snapshot.forecasts` usa el mismo schema descrito en la sección 10.

**Contrato transitorio HU006.** Mientras HU007/HU009 no suministren los enrichments de `forecasts`, el `201` de HU006 devuelve únicamente evidencia real: metadata mínima del run/Champion y `prediction_snapshot.predictions` con las filas producidas por `PredictionSnapshotCandidate`. No se fabrican data quality, historia, explicación, canal endémico ni thresholds ausentes. HU007 deberá normalizar la lectura al contrato final de la sección 10.

### 6.4 Idempotencia

Clave lógica:

```text
reference_month + source_file.sha256 + champion.version
```

Una repetición idéntica debe recuperar/reconocer el resultado lógico existente o responder de forma consistente. Un archivo diferente para un periodo ya procesado no puede sobrescribir silenciosamente un resultado anterior.

La idempotencia no reemplaza la validación contractual: un run con feature contract incompatible debe fallar incluso si `reference_month` y Champion version son conocidos.

---

## 7. `GET /api/v2/runs/{run_id}`

Respuesta `200`:

```json
{
  "schema_version": "2.0.0",
  "request_id": "3c2d...",
  "run": {
    "run_id": "biomac-2026-08-a1b2c3d4",
    "status": "COMPLETED",
    "reference_month": "2026-08",
    "stage": "PERSISTING",
    "created_at": "2026-09-02T18:30:00Z",
    "completed_at": "2026-09-02T18:30:07Z",
    "source_file_sha256": "example-sha256",
    "champion_version": "1.3.0",
    "error": null
  }
}
```

Para `COMPLETED`, `stage` puede ser `null` o `COMPLETED`. Para `FAILED`, `error` debe indicar etapa y código.

---

## 8. `GET /api/v2/predictions/latest`

### 8.1 Query params

| Campo | Tipo | Req. | Valores |
|---|---|---:|---|
| `municipality_codes` | string repetible/csv | No | `68001`,`76001`; default ambas |
| `horizons` | string repetible/csv | No | `T+1`,`T+2`; default ambas |

`history_months` e `include_explanations` quedan diferidos a HU009: HU007 no los acepta ni fabrica historia o explicaciones que no estén persistidas.

### 8.2 Semántica

Devuelve el último snapshot cuyo run terminó `COMPLETED`.

**No ejecuta preparación ni inferencia.** Este endpoint es la fuente para:
- apertura inicial del dashboard;
- botón `Refresh`;
- actualización automática posterior a un upload exitoso.

La respuesta HU007 usa el contrato mínimo real documentado en 6.3: `prediction_snapshot` contiene run, timestamps, corte, hash fuente, Champion y `predictions` planas con outputs nullable preservados. El schema enriquecido de la sección 10 es el objetivo compatible hacia adelante de HU009.

---

## 9. `GET /api/v2/predictions/history`

Filtros mínimos:
- `municipality_codes`;
- `horizon`;
- `from_month`;
- `to_month`;
- `limit`;
- `offset`.

Devuelve snapshots persistidos, no backtesting reconstruido bajo demanda.

Orden: `reference_month DESC`, `completed_at DESC`, `run_id DESC`. `limit` vale 20 por defecto (1..100) y `offset` vale 0 por defecto. Una colección vacía responde `200` con `items=[]`; `latest` vacío responde `404 PREDICTION_NOT_FOUND`.

---

## 10. Schema de `PredictionSnapshot`

```json
{
  "schema_version": "2.0.0",
  "run_id": "biomac-2026-08-a1b2c3d4",
  "generated_at": "2026-09-02T18:30:07Z",
  "reference_month": "2026-08",
  "target_definition": {
    "business_target": "dengue_excess_risk",
    "target_series": "casos_clasico",
    "predictor_series": ["casos_grave"],
    "series_are_summed": false,
    "excess_rule": "model_contract"
  },
  "champion": {
    "name": "biomac-champion",
    "version": "1.3.0",
    "mlflow_run_id": "optional-run-id",
    "output_type": "probability",
    "supported_horizons": ["T+1", "T+2"],
    "feature_contract_version": "1.0.0",
    "feature_contract_sha256": "example-feature-contract-sha256"
  },
  "forecasts": [
    {
      "municipality": {
        "divipola": "68001",
        "name": "Bucaramanga",
        "department": "Santander"
      },
      "data_quality": {
        "status": "complete",
        "last_observed_month": "2026-08",
        "epidemiological_completeness": 1.0,
        "climate_completeness": 0.96,
        "warnings": []
      },
      "current_status": {
        "reference_month": "2026-08",
        "observed_cases": 142,
        "p25": 92.0,
        "p50": 121.0,
        "p75": 158.0,
        "ratio_to_p75": 0.899,
        "endemic_zone": "ALERTA"
      },
      "predictions": [
        {
          "horizon": "T+1",
          "target_month": "2026-09",
          "label": "EXCESO",
          "model_output": {
            "type": "probability",
            "probability": 0.78,
            "expected_cases": null,
            "risk_score": null
          },
          "decision_rule": {
            "type": "probability_threshold",
            "probability_threshold": 0.61,
            "target_month_p75": 219.0,
            "decision_threshold_cases": null
          },
          "uncertainty": null,
          "explanation": {
            "available": false,
            "method": null,
            "scope": null,
            "top_features": []
          }
        }
      ],
      "history": [
        {
          "month": "2026-08",
          "observed_cases": 142,
          "p25": 92.0,
          "p50": 121.0,
          "p75": 158.0,
          "is_excess": false
        }
      ]
    }
  ]
}
```

Los valores anteriores son únicamente ejemplos de estructura.

HU009 expone estos enrichments de forma aditiva. En el entorno local vigente, `data_quality` y el contexto contractual `p25/p75/zona_canal` están disponibles; `observed_cases`, `p50` y `ratio_to_p75` permanecen nulos. La explicación queda `available=false` mientras no exista un parquet SHAP configurado y compatible.

## 11. Reglas de campos críticos

### `champion`

Describe el artefacto aprobado utilizado para el run. La API **lee** esta metadata; no entrena ni promueve el modelo.

`feature_contract_version` y `feature_contract_sha256` identifican el contrato de entrada bajo el cual el Champion declara haber producido la salida. Ambos deben coincidir con el contrato efectivo del input de ese run antes de aceptar el resultado.

### `model_output`

- `type=probability`: puede poblar `probability`.
- `type=expected_count`: puede poblar `expected_cases`.
- `risk_score`: solo si el Champion/mapper define un score válido.
- un score nunca debe convertirse arbitrariamente a probabilidad.

### `decision_rule`

La regla debe provenir del contrato/modelo aprobado. No se usa `0.50` por defecto.

### `explanation`

Para explicar una inferencia concreta:
- `available=true`;
- `scope=local`;
- `method` explícito;
- top features correspondientes exactamente a municipio + corte + horizonte.

Una importancia global no se etiqueta como SHAP local.

### `data_quality`

Resume la calidad de la entrada utilizada para ese run. Warnings no deben ocultarse en frontend.

---

## 12. Estados y errores

Formato uniforme:

```json
{
  "error": {
    "code": "INVALID_UPLOAD",
    "message": "El archivo no contiene las columnas requeridas.",
    "request_id": "d312...",
    "run_id": "biomac-2026-08-a1b2c3d4",
    "stage": "VALIDATING",
    "details": {
      "missing_columns": ["example"]
    }
  }
}
```

Códigos mínimos:

- `400 INVALID_REQUEST`
- `400 INVALID_UPLOAD`
- `404 RUN_NOT_FOUND`
- `404 PREDICTION_NOT_FOUND`
- `409 PERIOD_CONFLICT`
- `422 INSUFFICIENT_DATA`
- `422 CHAMPION_INPUT_INVALID`
- `503 CHAMPION_NOT_READY`
- `500 PREPARATION_FAILED`
- `500 INFERENCE_FAILED`
- `500 PERSISTENCE_FAILED`
- `500 INTERNAL_ERROR`

Para mismatch de feature contract se reutiliza `422 CHAMPION_INPUT_INVALID` con:

```json
{
  "details": {
    "reason": "feature_contract_mismatch",
    "expected_version": "...",
    "received_version": "...",
    "expected_sha256": "...",
    "received_sha256": "..."
  }
}
```

Los nombres `expected/received` deben documentarse de forma consistente en implementación/tests; el principio obligatorio es exponer la incompatibilidad sin stacktrace ni secretos.

Una respuesta de error no activa mocks.

## 13. Seguridad mínima

1. HTTPS en ambientes expuestos.
2. CORS allowlist del dashboard y localhost de desarrollo.
3. Validación estricta de archivos y parámetros.
4. Límite de tamaño de upload configurable.
5. Rechazar extensiones/tipos no permitidos.
6. No confiar en el nombre del archivo como identificador.
7. Hash SHA-256 de la carga para trazabilidad/idempotencia.
8. No versionar uploads ni resultados runtime en Git.
9. Logs con `request_id/run_id`, etapa, latencia y código; sin secretos ni datos innecesarios.
10. En un despliegue público, el endpoint de upload debe quedar protegido. Autenticación completa puede implementarse en una fase posterior del proyecto académico, pero no debe asumirse que CORS equivale a autorización.

## 14. Compatibilidad Dashboard ↔ API

1. El frontend consume `/predictions/latest` al abrir y refrescar.
2. El frontend llama `/monthly-runs` solo por acción explícita de actualización.
3. Tras `COMPLETED`, la UI vuelve a consultar `latest` o utiliza el snapshot retornado y luego sincroniza con `latest`.
4. Ante `FAILED`, incluida incompatibilidad de feature contract, la UI conserva el último snapshot exitoso y muestra el error de la actualización.
5. La UI se adapta a `output_type`.
6. Campos `null` se ocultan o muestran como no disponibles; nunca se reemplazan por mocks.

HU008 implementa esta compatibilidad con `HttpDengueRepository`. La configuración del navegador es `VITE_BIOMAC_API_BASE_URL` (incluye `/api/v2`, sin slash final). El cliente no establece `Content-Type` del multipart y usa el error estable `PREDICTION_NOT_FOUND` para distinguir el estado empty de una falla técnica.

## 15. Frontera con el Champion

El backend requiere del equipo de modelado:
- artefacto ejecutable o salida materializada equivalente;
- nombre/versión;
- horizontes soportados;
- contrato de features/entrada (`feature_contract_version` + `feature_contract_sha256`);
- tipo de salida;
- regla/threshold;
- método de explicación si existe.

Si falta alguno de estos elementos, la API debe reportar la dependencia; no debe inferirla por conveniencia.

La existencia de metadata no basta: el backend debe compararla con el contrato efectivo del input del run.

## 16. Fuente de verdad

Ante discrepancias:

1. `arquitectura.md` define responsabilidades y flujo.
2. `plan.md` define comportamiento funcional/visual.
3. este archivo define el contrato HTTP.
4. `diccionario-de-datos.md` define semántica de campos.
5. el Champion define qué salidas ML existen realmente.
6. la UI nunca simula una salida faltante.

---

## 17. Agnosticismo del contrato HTTP frente al provider HU004

La API `/api/v2` no distingue ni expone cómo HU004 obtuvo `ChampionOutput`.

Para el MVP, el provider activo será:

```text
ChampionResult PR12
→ MaterializedOutputAdapter
→ feature contract gate
→ ChampionOutput
```

En una evolución futura podrá ser:

```text
ChampionInput
→ ExecutableChampionAdapter
→ feature contract gate
→ ChampionOutput
```

Los endpoints, schemas HTTP, `PredictionSnapshot`, persistencia y frontend deben comportarse igual en ambos casos.

### Regla contractual

`POST /monthly-runs` significa **obtener una nueva salida Champion válida y contractualmente compatible para el run**, no necesariamente deserializar/ejecutar un modelo dentro del proceso FastAPI. El detalle pertenece a HU004.

La capa de orquestación de la API solo puede invocar `ChampionService.produce(ChampionOperationalContext)` y recibir `ChampionOutput`. No puede contener branching del tipo `if materialized` / `if executable`, ni importar adapters concretos, JSON PR #12, XGBoost, pickle o paquetes de modelo.

### Sin fallback silencioso

El provider HU004 activo se define por configuración/composición. Si falla, el run falla con el error contractual correspondiente. La API no cambia automáticamente de provider porque hacerlo comprometería trazabilidad y reproducibilidad.

---

## 18. Hallazgo HU010 que origina la versión 2.0.1

La prueba HTTP real de PR #33 demostró que el flujo podía devolver `201 COMPLETED` con cuatro predicciones aunque los contratos declarados fueran distintos:

```text
Champion JSON
feature_contract_version = pr12-f5a2d39
feature_contract_sha256   = 3af245ede70851d1616439d80441e2ad6f5d3f6465b9798d6b67fed3adb3e3dc

CSV/API vigente
feature_contract_version = pr12-74e385c3
feature_contract_sha256   = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

La respuesta HTTP y la persistencia fueron técnicamente correctas, pero no demuestran que esas predicciones correspondan al mismo contrato de entrada. Esta versión contractual introduce el gate obligatorio descrito en 6.2.1 sin autorizar la edición artificial de hashes/metadata.