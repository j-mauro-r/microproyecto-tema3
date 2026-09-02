# BIOMAC — Contrato de API para el dashboard

**Estado:** contrato objetivo para integración Dashboard ↔ FastAPI ↔ modelo  
**Versión del contrato:** `1.1.0`  
**Ruta:** `dashboard_prototipos/docs/API-sign.md`

> Fuente de verdad técnica para la integración. Los valores de los ejemplos son ilustrativos y no representan resultados epidemiológicos reales.

---

## 1. Alcance vigente

BIOMAC estima **riesgo de exceso de dengue** para Bucaramanga (`68001`) y Cali (`76001`) con granularidad mensual y horizontes `T+1` y `T+2`.

### Definición operacional vigente

- La serie epidemiológica usada actualmente como **target cuantitativo** es `casos_clasico`.
- `casos_grave` se conserva como **variable predictora**.
- Las dos series son independientes y **no se suman**.
- El producto comunica el resultado como **riesgo de exceso de dengue**; la API debe exponer explícitamente qué serie produjo el target para evitar ambigüedad.
- El exceso se determina respecto al canal endémico del mes objetivo.
- La arquitectura de modelado debe impedir data leakage: para un corte `t`, solo se usan datos disponibles hasta `t`.

### Salida principal

La salida mínima por horizonte es:

1. `EXCESO` / `NO_EXCESO`;
2. mes objetivo;
3. señal cuantitativa de riesgo producida realmente por el modelo;
4. threshold/regla de decisión usada;
5. trazabilidad del modelo y datos.

La implementación Poisson actual produce un **conteo esperado**, no una probabilidad calibrada. Por tanto, `probability` es opcional y solo puede informarse cuando el modelo desplegado la produzca mediante un método estadísticamente válido.

---

## 2. Principios del contrato

El frontend **no debe**:

- construir features;
- calcular P25/P50/P75;
- determinar la zona endémica;
- transformar un score en `EXCESO/NO_EXCESO`;
- inventar casos futuros a partir de una probabilidad;
- denominar SHAP a una importancia global o a coeficientes del modelo.

FastAPI es la fuente de verdad para resultados epidemiológicos, inferencia, regla de decisión y metadata.

El dashboard solo presenta la respuesta.

---

## 3. Arquitectura esperada

```text
Dashboard BIOMAC
      |
      | HTTPS / JSON
      v
FastAPI
      |
      +--> validación Pydantic
      +--> selección de ciudad y mes de referencia
      +--> recuperación de datos hasta t
      +--> construcción reproducible de features
      +--> modelo T+1 / modelo T+2
      +--> canal endémico
      +--> metadata / métricas / explicación
      |
      v
Respuesta versionada
```

La API debe encapsular rutas de archivos, serialización, MLflow, DVC y detalles internos del pipeline.

---

## 4. Convenciones

- Base path: `/api/v1`
- Content type: `application/json`
- Mes: `YYYY-MM`
- Fecha/hora: ISO-8601 UTC
- DIVIPOLA: string de 5 dígitos
- JSON: `snake_case`
- Requests con campos desconocidos: rechazados (`extra="forbid"`)
- `null`: dato contemplado pero no disponible/no aplicable
- El consumidor no debe depender del orden de las claves JSON
- Versionamiento del contrato: SemVer

---

## 5. Endpoints

### 5.1 Health

```http
GET /api/v1/health
```

Respuesta `200`:

```json
{
  "status": "ok",
  "service": "biomac-api",
  "api_version": "1.1.0",
  "model_ready": true
}
```

### 5.2 Predicciones

```http
POST /api/v1/predictions
Content-Type: application/json
```

Permite solicitar una o ambas ciudades y uno o ambos horizontes.

---

## 6. Request

### 6.1 Ejemplo

```json
{
  "schema_version": "1.1.0",
  "municipality_codes": ["68001", "76001"],
  "reference_month": "2024-12",
  "horizons": ["T+1", "T+2"],
  "history_months": 36,
  "include_explanations": true,
  "include_prediction_history": false
}
```

### 6.2 Reglas

1. `municipality_codes`: únicamente municipios soportados por el modelo desplegado.
2. `reference_month`: mes considerado `Actual` para la inferencia.
3. Ninguna feature puede incorporar información posterior a `reference_month`.
4. Cada horizonte debe corresponder a un artefacto o estrategia de inferencia evaluada explícitamente para ese `H`.
5. No se permite obtener `T+2` extrapolando visualmente `T+1`.
6. Si faltan datos esenciales, la API responde error controlado; nunca sustituye silenciosamente con mocks.
7. En producción, el frontend puede enviar por defecto el último corte válido; en modo histórico puede enviar un corte anterior.

---

## 7. Response

### 7.1 Ejemplo

```json
{
  "schema_version": "1.1.0",
  "request_id": "d312a52d-ae4b-4df1-a568-778a998252b2",
  "generated_at": "2026-09-02T02:30:00Z",
  "reference_month": "2024-12",
  "target_definition": {
    "business_target": "dengue_excess_risk",
    "target_series": "casos_clasico",
    "predictor_series": ["casos_grave"],
    "series_are_summed": false,
    "excess_rule": "expected_or_observed_cases_above_target_month_endemic_threshold"
  },
  "models": [
    {
      "horizon": "T+1",
      "name": "biomac-poisson",
      "version": "example-1.0.0",
      "mlflow_run_id": "example-run-t1",
      "trained_at": "2026-09-01T15:00:00Z",
      "training_period": "2007-2022",
      "test_period": "2023-2025",
      "data_version": "example-dvc-rev",
      "output_type": "expected_count"
    },
    {
      "horizon": "T+2",
      "name": "biomac-poisson",
      "version": "example-1.0.0",
      "mlflow_run_id": "example-run-t2",
      "trained_at": "2026-09-01T15:20:00Z",
      "training_period": "2007-2022",
      "test_period": "2023-2025",
      "data_version": "example-dvc-rev",
      "output_type": "expected_count"
    }
  ],
  "forecasts": [
    {
      "municipality": {
        "divipola": "68001",
        "name": "Bucaramanga",
        "department": "Santander"
      },
      "data_quality": {
        "status": "complete",
        "last_observed_month": "2024-12",
        "epidemiological_completeness": 1.0,
        "climate_completeness": 0.96,
        "warnings": []
      },
      "current_status": {
        "reference_month": "2024-12",
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
          "target_month": "2025-01",
          "label": "EXCESO",
          "model_output": {
            "type": "expected_count",
            "expected_cases": 236.4,
            "probability": null,
            "risk_score": 1.079
          },
          "decision_rule": {
            "type": "p75_multiplier",
            "target_month_p75": 219.0,
            "multiplier_k": 1.0,
            "decision_threshold_cases": 219.0
          },
          "uncertainty": null,
          "explanation": {
            "available": false,
            "method": null,
            "scope": null,
            "top_features": []
          }
        },
        {
          "horizon": "T+2",
          "target_month": "2025-02",
          "label": "NO_EXCESO",
          "model_output": {
            "type": "expected_count",
            "expected_cases": 221.1,
            "probability": null,
            "risk_score": 0.906
          },
          "decision_rule": {
            "type": "p75_multiplier",
            "target_month_p75": 244.0,
            "multiplier_k": 1.0,
            "decision_threshold_cases": 244.0
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
          "month": "2024-12",
          "observed_cases": 142,
          "p25": 92.0,
          "p50": 121.0,
          "p75": 158.0,
          "is_excess": false
        }
      ],
      "evaluation": {
        "scope": "municipality",
        "evaluation_period": "2023-2025",
        "sample_size": 36,
        "recall": null,
        "precision": null,
        "f1": null,
        "false_alarm_rate": null,
        "outbreak_onsets": null,
        "outbreak_onsets_detected": null
      },
      "prediction_history": [],
      "decision_support": {
        "alert_level": "VIGILANCIA",
        "action_code": "REVIEW_AND_MONITOR",
        "recommended_action": "Revisar la evolución epidemiológica y mantener vigilancia reforzada.",
        "disclaimer": "Prototipo académico. No sustituye la vigilancia epidemiológica oficial ni una decisión sanitaria profesional."
      }
    }
  ],
  "data_sources": [
    {
      "name": "SIVIGILA dengue clásico",
      "category": "epidemiological_target",
      "cutoff_month": "2024-12"
    },
    {
      "name": "SIVIGILA dengue grave",
      "category": "epidemiological_predictor",
      "cutoff_month": "2024-12"
    },
    {
      "name": "ERA5 / Google Earth Engine",
      "category": "climate",
      "cutoff_month": "2024-12"
    }
  ]
}
```

---

## 8. Diccionario de datos — Request

| Campo | Tipo | Req. | Restricciones | Significado |
|---|---|---:|---|---|
| `schema_version` | string | Sí | SemVer | Versión del contrato solicitada. |
| `municipality_codes` | array[string] | Sí | 1–2 en esta fase | DIVIPOLA de municipios solicitados. |
| `reference_month` | string | Sí | `YYYY-MM` | Mes considerado `Actual`. |
| `horizons` | array[enum] | Sí | `T+1`, `T+2` | Horizontes a inferir. |
| `history_months` | integer | No | `0..240`, default `36` | Historia a devolver. |
| `include_explanations` | boolean | No | default `true` | Solicita explicación si existe. |
| `include_prediction_history` | boolean | No | default `false` | Solicita inferencias históricas persistidas. |

---

## 9. Diccionario de datos — Response

### 9.1 Raíz

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `schema_version` | string | No | Versión de respuesta. |
| `request_id` | UUID | No | Trazabilidad de la solicitud. |
| `generated_at` | datetime | No | Fecha/hora de inferencia. |
| `reference_month` | string | No | Corte usado. |
| `target_definition` | object | No | Define semánticamente y técnicamente el target. |
| `models` | array | No | Artefacto usado por horizonte. |
| `forecasts` | array | No | Resultado por municipio. |
| `data_sources` | array | No | Fuentes realmente usadas. |

### 9.2 `target_definition`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `business_target` | string | No | `dengue_excess_risk`. |
| `target_series` | string | No | Serie sobre la que se define/modela actualmente el exceso: `casos_clasico`. |
| `predictor_series` | array[string] | No | Otras series epidemiológicas usadas como features; incluye `casos_grave`. |
| `series_are_summed` | boolean | No | Debe ser `false` con la definición vigente. |
| `excess_rule` | string | No | Regla de exceso versionada. |

### 9.3 `models[]`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `horizon` | enum | No | `T+1` o `T+2`. |
| `name` | string | No | Nombre lógico del modelo desplegado. |
| `version` | string | No | Versión del artefacto. |
| `mlflow_run_id` | string | Sí | Run de MLflow. |
| `trained_at` | datetime | No | Entrenamiento del artefacto final. |
| `training_period` | string | No | Periodo de entrenamiento. |
| `test_period` | string | Sí | Evaluación final. |
| `data_version` | string | Sí | Revisión/hash DVC. |
| `output_type` | enum | No | `expected_count`, `probability` u otro tipo versionado. |

### 9.4 `data_quality`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `status` | enum | No | `complete`, `partial`, `degraded`. |
| `last_observed_month` | string | No | Último mes realmente observado. |
| `epidemiological_completeness` | float 0..1 | Sí | Completitud epidemiológica. |
| `climate_completeness` | float 0..1 | Sí | Completitud climática. |
| `warnings` | array[string] | No | Advertencias relevantes. |

### 9.5 `current_status`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `reference_month` | string | No | Mes actual consultado. |
| `observed_cases` | number | No | Casos de la serie target vigente. |
| `p25` | number | Sí | Percentil 25 del canal. |
| `p50` | number | Sí | Mediana del canal. |
| `p75` | number | No | Percentil 75. |
| `ratio_to_p75` | float | No | `observed_cases / p75`. |
| `endemic_zone` | enum | No | Categoría epidemiológica actual. |

### 9.6 `predictions[]`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `horizon` | enum | No | `T+1` / `T+2`. |
| `target_month` | string | No | Mes futuro predicho. |
| `label` | enum | No | `EXCESO` / `NO_EXCESO`. |
| `model_output` | object | No | Salida nativa del modelo. |
| `decision_rule` | object | No | Regla que genera la clase. |
| `uncertainty` | object | Sí | Solo si existe método válido. |
| `explanation` | object | No | Explicación local o `available=false`. |

### 9.7 `model_output`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `type` | enum | No | `expected_count` o `probability`. |
| `expected_cases` | float | Sí | Conteo esperado si el modelo lo produce. |
| `probability` | float 0..1 | Sí | Solo si existe probabilidad válida. |
| `risk_score` | float | Sí | Score continuo comparable dentro del mismo modelo/horizonte. Para Poisson puede ser `expected_cases / p75`. |

> `risk_score` **no es una probabilidad** y no debe mostrarse con símbolo `%`.

### 9.8 `decision_rule`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `type` | enum | No | Ej. `p75_multiplier` o `probability_threshold`. |
| `target_month_p75` | float | Sí | P75 del mes objetivo. |
| `multiplier_k` | float | Sí | Multiplicador aplicado al P75 en modelos de conteo. |
| `decision_threshold_cases` | float | Sí | Umbral final en casos. |
| `probability_threshold` | float 0..1 | Sí | Solo para modelos probabilísticos. |

### 9.9 `explanation`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `available` | boolean | No | Indica si existe explicación local válida. |
| `method` | enum/string | Sí | Ej. `shap`, `linear_contribution`. |
| `scope` | enum | Sí | Debe ser `local` para explicar una inferencia concreta. |
| `top_features` | array | No | Factores principales. |

Si solo existen coeficientes/importancias globales, deben exponerse en otra vista y nunca etiquetarse como explicación local.

### 9.10 Métricas

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `recall` | float 0..1 | Sí | Sensibilidad de EXCESO. |
| `precision` | float 0..1 | Sí | Precisión de alertas. |
| `f1` | float 0..1 | Sí | Balance Precision/Recall. |
| `false_alarm_rate` | float 0..1 | Sí | Tasa de falsas alarmas. |
| `outbreak_onsets` | integer | Sí | Inicios reales observados. |
| `outbreak_onsets_detected` | integer | Sí | Inicios detectados. |
| `sample_size` | integer | Sí | Observaciones evaluadas. |

Las métricas deben poder devolverse específicamente para Bucaramanga y Cali cuando existan suficientes observaciones.

---

## 10. Historial de predicciones

Cuando se implemente persistencia, cada inferencia histórica debe conservar como mínimo:

```json
{
  "generated_at": "2025-01-02T12:00:00Z",
  "reference_month": "2024-12",
  "horizon": "T+2",
  "target_month": "2025-02",
  "label": "NO_EXCESO",
  "expected_cases": 221.1,
  "probability": null,
  "risk_score": 0.906,
  "model_version": "example-1.0.0",
  "observed_label": null
}
```

Esto soporta auditoría y `pronosticado vs. ocurrido`.

---

## 11. Errores

Formato único:

```json
{
  "error": {
    "code": "INSUFFICIENT_DATA",
    "message": "No hay suficientes datos para construir las features del mes solicitado.",
    "request_id": "d312a52d-ae4b-4df1-a568-778a998252b2",
    "details": {
      "municipality_code": "68001",
      "reference_month": "2007-01"
    }
  }
}
```

Códigos mínimos:

- `400 INVALID_REQUEST`
- `404 MUNICIPALITY_NOT_SUPPORTED`
- `409 INFERENCE_NOT_AVAILABLE`
- `422 INSUFFICIENT_DATA`
- `503 MODEL_NOT_READY`
- `500 INTERNAL_ERROR`

Nunca devolver mocks como fallback ante errores.

---

## 12. Seguridad mínima para esta fase

1. HTTPS en ambientes expuestos.
2. CORS mediante allowlist del dominio del dashboard y localhost de desarrollo.
3. Validación estricta con Pydantic.
4. Límites de tamaño de request y rate limiting básico si la API es pública.
5. Logs con `request_id`, endpoint, latencia y código HTTP; no registrar secretos.
6. API de inferencia read-only para el dashboard.
7. No almacenar credenciales en Git.
8. No incluir API keys secretas en código frontend: cualquier secreto enviado al navegador deja de ser secreto.

Para esta fase académica no es obligatorio implementar autenticación de usuario si el servicio solo expone datos públicos agregados y se encuentra bajo infraestructura controlada. Si posteriormente se habilitan operaciones de carga, administración o datos sensibles, deberán protegerse con autenticación/autorización separada.

---

## 13. Estructura FastAPI recomendada

```text
api/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── v1/
│   │       └── predictions.py
│   ├── schemas/
│   │   ├── health.py
│   │   ├── prediction_request.py
│   │   └── prediction_response.py
│   ├── services/
│   │   ├── inference_service.py
│   │   ├── feature_service.py
│   │   └── history_service.py
│   └── core/
│       └── config.py
└── tests/
```

Separar schemas, rutas y lógica de inferencia facilita pruebas, empaquetamiento y sustitución de modelos.

---

## 14. Reglas de compatibilidad Dashboard ↔ API

1. El dashboard consume el contrato, no el tipo concreto de modelo.
2. `probability` puede ser `null`; la UI debe adaptarse al tipo de salida.
3. `expected_cases` solo puede mostrarse si proviene directamente del modelo/backend.
4. Para Poisson, el dashboard puede mostrar conteo esperado, P75 del mes objetivo y `risk_score`; nunca debe transformar `risk_score` en porcentaje.
5. Si un futuro champion es clasificador probabilístico, podrá usar `probability` y `probability_threshold` sin cambiar la estructura principal.
6. T+1 y T+2 deben identificar su propio modelo/run/versión cuando sean artefactos distintos.
7. `SHAP` solo puede mostrarse cuando `explanation.method="shap"` y `scope="local"`.
8. El frontend no debe utilizar datos posteriores al corte para el modo histórico.

---

## 15. Dependencias antes de habilitar datos reales

La API real no debe declararse lista hasta contar con:

- definición versionada del target;
- artefactos finales desplegables para T+1 y T+2;
- selección explícita del modelo/champion por horizonte;
- features reproducibles sin leakage;
- canal endémico reproducible;
- métricas globales y por ciudad cuando sean estadísticamente defendibles;
- DVC/versión de datos alineada;
- estrategia explícita para probabilidades, si se quieren mostrar;
- explicación local válida, si se quiere mostrar;
- pruebas unitarias y contract tests de FastAPI.

---

## 16. Fuente de verdad

Ante discrepancias:

1. `plan.md` define el comportamiento funcional esperado.
2. Este archivo define la interfaz técnica Dashboard ↔ FastAPI.
3. El pipeline/modelo define qué salidas pueden producirse realmente.
4. La UI nunca debe simular una salida faltante para aparentar cumplimiento.
