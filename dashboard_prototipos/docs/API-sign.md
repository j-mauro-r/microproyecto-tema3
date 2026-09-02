# BIOMAC — Contrato de API para el dashboard

**Estado:** contrato objetivo para integración Dashboard ↔ FastAPI ↔ modelo  
**Versión del contrato:** `1.0.0`  
**Ruta del documento:** `dashboard_prototipos/docs/API-sign.md`

> Este documento es una especificación de interfaz. Los valores de los ejemplos son ilustrativos y **no deben interpretarse como resultados epidemiológicos reales**.

---

## 1. Objetivo

Definir un contrato estable para que el dashboard BIOMAC consuma predicciones reales del modelo sin depender de su implementación interna.

El contrato está diseñado para el alcance actual de BIOMAC:

- dengue grave;
- Bucaramanga (`68001`) y Cali (`76001`);
- granularidad mensual;
- horizontes `T+1` y `T+2`;
- salida binaria `NO_EXCESO / EXCESO` acompañada de probabilidad;
- canal endémico;
- explicabilidad local cuando esté disponible;
- trazabilidad del modelo y de los datos;
- métricas de desempeño globales y por municipio;
- historial de predicciones cuando exista.

### Principio de diseño

El frontend **no debe calcular resultados epidemiológicos ni transformar una probabilidad en una clase**. La API es la fuente de verdad para:

- `label`;
- `probability`;
- `threshold`;
- estado del canal endémico;
- métricas;
- SHAP;
- metadata del modelo.

El frontend solo presenta la información.

La API **no debe inventar un número futuro de casos** si el modelo únicamente clasifica exceso/no exceso.

---

## 2. Arquitectura esperada

```text
Dashboard BIOMAC
      |
      | HTTPS / JSON
      v
FastAPI
      |
      +--> validación de entrada
      +--> recuperación/preparación de features
      +--> modelo seleccionado
      +--> canal endémico
      +--> explicabilidad
      +--> metadata / métricas
      |
      v
Respuesta versionada
```

El dashboard no debe conocer nombres de archivos `.pkl`, rutas de MLflow ni detalles internos del pipeline.

---

## 3. Convenciones del contrato

- Base path: `/api/v1`
- Content type: `application/json`
- Fechas de mes: `YYYY-MM`
- Fechas/horas: ISO-8601 en UTC, por ejemplo `2026-09-01T23:20:00Z`
- Probabilidades y métricas: valores decimales entre `0.0` y `1.0`
- DIVIPOLA: string de 5 dígitos; nunca entero
- Campos JSON: `snake_case`
- Campos desconocidos en request: rechazados por Pydantic (`extra="forbid"`)
- Orden de claves JSON: se usa aquí para legibilidad; semánticamente el cliente no debe depender del orden
- `null`: significa que el dato fue contemplado por el contrato pero todavía no está disponible o no aplica

---

## 4. Endpoints

### 4.1 Health check

```http
GET /api/v1/health
```

No ejecuta inferencia.

Respuesta `200`:

```json
{
  "status": "ok",
  "service": "biomac-api",
  "api_version": "1.0.0"
}
```

### 4.2 Predicción para el dashboard

```http
POST /api/v1/predictions
Content-Type: application/json
```

Este es el endpoint principal que consume el dashboard.

Permite solicitar uno o varios municipios. Para la vista comparativa, el frontend puede enviar Bucaramanga y Cali en una sola solicitud.

---

## 5. Request

### 5.1 Ejemplo

```json
{
  "schema_version": "1.0.0",
  "municipality_codes": ["68001"],
  "reference_month": "2024-12",
  "horizons": ["T+1", "T+2"],
  "history_months": 3,
  "include_explanations": true,
  "include_prediction_history": true
}
```

### 5.2 Reglas

1. `municipality_codes` acepta únicamente municipios soportados por la versión desplegada del modelo.
2. Para el alcance actual, los valores esperados son `68001` y `76001`.
3. `reference_month` representa el último mes epidemiológico disponible para construir la inferencia.
4. Ninguna feature puede utilizar información posterior a `reference_month`.
5. `T+1` y `T+2` deben ser modelos/targets evaluados explícitamente para esos horizontes; no se permite simular T+2 extrapolando T+1.
6. Si el backend no tiene datos suficientes para la solicitud, debe responder con error controlado; no debe completar datos con mocks.

---

## 6. Response

### 6.1 Ejemplo

```json
{
  "schema_version": "1.0.0",
  "request_id": "5f28f4db-2f37-4fb4-8b5e-5882dd8b8218",
  "generated_at": "2026-09-01T23:20:00Z",
  "reference_month": "2024-12",
  "target": "severe_dengue_excess",
  "model": {
    "name": "biomac-xgboost",
    "version": "demo-1.0.0",
    "mlflow_run_id": "example-run-id",
    "trained_at": "2026-08-31T18:00:00Z",
    "training_period": "2007-2023",
    "test_period": "2024",
    "data_version": "example-dvc-version",
    "probabilities_calibrated": false,
    "global_metrics": {
      "recall": 0.81,
      "precision": 0.72,
      "f1": 0.76,
      "auroc": 0.89,
      "average_precision": 0.86,
      "false_alarm_rate": 0.18,
      "outbreak_onset_detection_rate": 0.64
    }
  },
  "forecasts": [
    {
      "municipality": {
        "id": "bucaramanga",
        "divipola": "68001",
        "name": "Bucaramanga",
        "department": "Santander"
      },
      "data_quality": {
        "status": "complete",
        "last_observed_month": "2024-12",
        "completeness": 0.98,
        "warnings": []
      },
      "current_status": {
        "reference_month": "2024-12",
        "observed_cases": 18,
        "p25": 8.0,
        "p50": 12.0,
        "p75": 20.0,
        "ratio_to_p75": 0.9,
        "endemic_zone": "ALERTA"
      },
      "predictions": [
        {
          "horizon": "T+1",
          "target_month": "2025-01",
          "label": "EXCESO",
          "probability": 0.67,
          "threshold": 0.61,
          "confidence_interval": null,
          "explanation": {
            "available": true,
            "method": "shap",
            "scope": "local",
            "top_features": [
              {
                "feature": "casos_grave_lag_1",
                "feature_value": 18.0,
                "shap_value": 0.21,
                "direction": "INCREASES_RISK"
              },
              {
                "feature": "zona_canal_lag1",
                "feature_value": 1.0,
                "shap_value": 0.13,
                "direction": "INCREASES_RISK"
              }
            ]
          }
        },
        {
          "horizon": "T+2",
          "target_month": "2025-02",
          "label": "NO_EXCESO",
          "probability": 0.54,
          "threshold": 0.61,
          "confidence_interval": null,
          "explanation": {
            "available": true,
            "method": "shap",
            "scope": "local",
            "top_features": [
              {
                "feature": "casos_grave_lag_2",
                "feature_value": 14.0,
                "shap_value": 0.09,
                "direction": "INCREASES_RISK"
              }
            ]
          }
        }
      ],
      "history": [
        {
          "month": "2024-10",
          "observed_cases": 11,
          "p25": 7.0,
          "p50": 10.0,
          "p75": 18.0,
          "is_excess": false
        },
        {
          "month": "2024-11",
          "observed_cases": 15,
          "p25": 8.0,
          "p50": 11.0,
          "p75": 19.0,
          "is_excess": false
        },
        {
          "month": "2024-12",
          "observed_cases": 18,
          "p25": 8.0,
          "p50": 12.0,
          "p75": 20.0,
          "is_excess": false
        }
      ],
      "evaluation": {
        "scope": "municipality",
        "evaluation_period": "2024",
        "sample_size": 12,
        "recall": 0.8,
        "precision": 0.67,
        "f1": 0.73,
        "false_alarm_rate": 0.2,
        "outbreak_onset_detection_rate": 0.6
      },
      "prediction_history": [
        {
          "generated_at": "2024-11-01T12:00:00Z",
          "reference_month": "2024-10",
          "horizon": "T+1",
          "target_month": "2024-11",
          "label": "NO_EXCESO",
          "probability": 0.42,
          "threshold": 0.61,
          "observed_label": "NO_EXCESO"
        }
      ],
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
      "name": "SIVIGILA",
      "category": "epidemiological",
      "cutoff_month": "2024-12"
    },
    {
      "name": "climate-source-used-by-model",
      "category": "climate",
      "cutoff_month": "2024-12"
    }
  ]
}
```

> Los números anteriores son deliberadamente ilustrativos. Una implementación real debe sustituirlos por resultados provenientes del pipeline/modelo y de las fuentes versionadas.

---

## 7. Diccionario de datos — Request

| Campo | Tipo | Requerido | Restricciones | Significado |
|---|---|---:|---|---|
| `schema_version` | string | Sí | SemVer; inicialmente `1.0.0` | Versión del contrato enviada por el cliente. |
| `municipality_codes` | array[string] | Sí | 1–2 elementos en esta fase; DIVIPOLA de 5 dígitos | Municipios para los que se solicita inferencia. |
| `reference_month` | string | Sí | `YYYY-MM` | Último mes con información disponible para la inferencia. |
| `horizons` | array[enum] | Sí | Valores: `T+1`, `T+2`; sin duplicados | Horizontes solicitados. |
| `history_months` | integer | No | `0..240`; default `36` | Cantidad de meses históricos que debe devolver la API. |
| `include_explanations` | boolean | No | default `true` | Solicita explicación local si el modelo la soporta. |
| `include_prediction_history` | boolean | No | default `false` | Solicita predicciones históricas almacenadas para auditoría. |

---

## 8. Diccionario de datos — Response

### 8.1 Nivel raíz

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `schema_version` | string | No | Versión del esquema de respuesta. |
| `request_id` | UUID string | No | Identificador único para trazabilidad de la solicitud. |
| `generated_at` | datetime | No | Instante UTC en el que se generó la respuesta. |
| `reference_month` | string | No | Mes de corte utilizado para inferencia. |
| `target` | enum/string | No | Target semántico. Para el alcance actual: `severe_dengue_excess`. |
| `model` | object | No | Metadata y métricas del modelo desplegado. |
| `forecasts` | array[object] | No | Resultado por municipio solicitado. |
| `data_sources` | array[object] | No | Fuentes que participaron realmente en la inferencia/contexto. |

### 8.2 `model`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `name` | string | No | Nombre lógico del modelo champion. |
| `version` | string | No | Versión desplegada del modelo. |
| `mlflow_run_id` | string | Sí | ID del run de MLflow asociado. |
| `trained_at` | datetime | No | Fecha/hora de entrenamiento. |
| `training_period` | string | No | Periodo usado para entrenamiento. |
| `test_period` | string | No | Periodo de evaluación final. |
| `data_version` | string | Sí | Versión/hash/tag de datos, preferiblemente DVC. |
| `probabilities_calibrated` | boolean | No | Indica si las probabilidades fueron calibradas formalmente. |
| `global_metrics` | object | Sí | Métricas del modelo en el conjunto global de evaluación. |

### 8.3 Métricas (`global_metrics` y `evaluation`)

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `recall` | float 0..1 | Sí | Proporción de excesos reales correctamente detectados. |
| `precision` | float 0..1 | Sí | Proporción de alertas positivas que fueron correctas. |
| `f1` | float 0..1 | Sí | Media armónica entre precision y recall. |
| `auroc` | float 0..1 | Sí | Capacidad discriminativa global; no reemplaza métricas por ciudad. |
| `average_precision` | float 0..1 | Sí | Área/resumen de precision-recall para la clase positiva. |
| `false_alarm_rate` | float 0..1 | Sí | Proporción de alertas positivas que constituyen falsas alarmas según la definición acordada. |
| `outbreak_onset_detection_rate` | float 0..1 | Sí | Proporción de inicios de episodio detectados. |
| `scope` | enum | Sí | Por ejemplo `municipality` o `global`. |
| `evaluation_period` | string | Sí | Periodo de datos sobre el que se calculan métricas. |
| `sample_size` | integer | Sí | Número de observaciones de la evaluación. |

### 8.4 `forecasts[].municipality`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `id` | enum/string | No | ID estable de frontend, inicialmente `bucaramanga` o `cali`. |
| `divipola` | string | No | Código DANE de 5 dígitos. |
| `name` | string | No | Nombre oficial del municipio. |
| `department` | string | No | Departamento. |

### 8.5 `forecasts[].data_quality`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `status` | enum | No | `complete`, `partial` o `stale`. |
| `last_observed_month` | string | No | Último mes epidemiológico realmente observado. |
| `completeness` | float 0..1 | Sí | Completitud de features requeridas para la inferencia. |
| `warnings` | array[string] | No | Advertencias relevantes; vacío si no existen. |

### 8.6 `forecasts[].current_status`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `reference_month` | string | No | Mes del estado epidemiológico actual. |
| `observed_cases` | integer >= 0 | No | Casos observados del target epidemiológico. |
| `p25` | float >= 0 | No | Percentil 25 del canal endémico. |
| `p50` | float >= 0 | No | Mediana del canal endémico. |
| `p75` | float >= 0 | No | Percentil 75; umbral epidemiológico de exceso definido por el proyecto. |
| `ratio_to_p75` | float >= 0 | Sí | `observed_cases / p75`; si `p75 = 0`, debe ser `null`. |
| `endemic_zone` | enum | No | `NORMAL`, `ENDEMIA`, `ALERTA` o `EXCESO`, según metodología vigente. |

### 8.7 `forecasts[].predictions[]`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `horizon` | enum | No | `T+1` o `T+2`. |
| `target_month` | string | No | Mes al que corresponde la predicción. |
| `label` | enum | No | `NO_EXCESO` o `EXCESO`. Calculado por backend usando `threshold`. |
| `probability` | float 0..1 | No | Probabilidad producida por el modelo para la clase `EXCESO`. |
| `threshold` | float 0..1 | No | Umbral validado que convierte probabilidad en clase. Nunca hardcodeado en frontend. |
| `confidence_interval` | array[float,float] | Sí | Intervalo de incertidumbre solo si existe una metodología válida. En caso contrario `null`. |
| `explanation` | object | No | Estado y contenido de la explicación de la inferencia. |

### 8.8 `predictions[].explanation`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `available` | boolean | No | Indica si existe explicación válida para esa inferencia. |
| `method` | enum/string | Sí | Ej. `shap`; `null` si `available=false`. |
| `scope` | enum | Sí | Para el dashboard debe ser `local` cuando se presente como explicación de esa predicción. |
| `top_features` | array[object] | No | Variables con mayor contribución para esa predicción. Vacío si no disponible. |

### 8.9 `top_features[]`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `feature` | string | No | Nombre técnico de la feature. |
| `feature_value` | number/string | Sí | Valor utilizado para la inferencia. |
| `shap_value` | float | Sí | Contribución SHAP local. Solo usar este nombre si realmente es SHAP. |
| `direction` | enum | Sí | `INCREASES_RISK` o `DECREASES_RISK`. |

### 8.10 `forecasts[].history[]`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `month` | string | No | Mes histórico. |
| `observed_cases` | integer >= 0 | No | Casos observados. |
| `p25` | float >= 0 | No | P25 del canal. |
| `p50` | float >= 0 | No | P50 del canal. |
| `p75` | float >= 0 | No | P75 del canal. |
| `is_excess` | boolean | No | `true` cuando `observed_cases > p75` según metodología del proyecto. |

### 8.11 `forecasts[].prediction_history[]`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `generated_at` | datetime | No | Momento en que se generó la predicción histórica. |
| `reference_month` | string | No | Corte usado en esa inferencia. |
| `horizon` | enum | No | `T+1` o `T+2`. |
| `target_month` | string | No | Mes que se intentó predecir. |
| `label` | enum | No | Clase predicha. |
| `probability` | float 0..1 | No | Probabilidad predicha. |
| `threshold` | float 0..1 | No | Threshold vigente en esa versión del modelo. |
| `observed_label` | enum | Sí | Resultado real conocido posteriormente; `null` mientras no exista observación. |

### 8.12 `forecasts[].decision_support`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `alert_level` | enum/string | No | Nivel de alerta derivado por reglas validadas, no inventado por UI. |
| `action_code` | string | No | Código estable de la recomendación. |
| `recommended_action` | string | No | Orientación no prescriptiva para apoyo a decisión. |
| `disclaimer` | string | No | Aclara alcance académico y no sustitución de vigilancia oficial. |

### 8.13 `data_sources[]`

| Campo | Tipo | Nulable | Significado |
|---|---|---:|---|
| `name` | string | No | Nombre de la fuente realmente utilizada. |
| `category` | enum | No | `epidemiological`, `climate`, `demographic` u otra controlada. |
| `cutoff_month` | string | Sí | Último periodo usado de esa fuente. |

---

## 9. Reglas semánticas obligatorias

### 9.1 Target

La respuesta debe identificar explícitamente qué fenómeno predice. Para el alcance actual:

```text
severe_dengue_excess
```

No debe etiquetarse como dengue grave una predicción cuyo modelo fue entrenado para dengue clásico.

### 9.2 Horizontes

`T+1` y `T+2` son resultados independientes y deben haber sido construidos/evaluados metodológicamente para esos horizontes.

### 9.3 Threshold

El `threshold` debe provenir del artefacto/configuración del modelo champion y estar asociado a su versión.

El frontend nunca debe asumir `0.5`.

### 9.4 Probabilidad

`probability` siempre representa:

```text
P(EXCESO | datos disponibles hasta reference_month)
```

Si no existe calibración formal, `probabilities_calibrated=false`.

### 9.5 SHAP

Solo utilizar `method="shap"` y el campo `shap_value` cuando se haya calculado SHAP real para la observación, ciudad y horizonte consultados.

Una importancia global de XGBoost no debe presentarse como SHAP local.

### 9.6 Clima

Una fuente/feature climática solo puede aparecer como utilizada o explicativa cuando tenga datos válidos en la inferencia real.

### 9.7 Datos observados vs. pronosticados

`history` contiene hechos observados y canal endémico. `predictions` contiene inferencias futuras.

No mezclar ambos conceptos en una misma variable.

---

## 10. Errores

Formato único de error:

```json
{
  "error": {
    "code": "UNSUPPORTED_MUNICIPALITY",
    "message": "Municipality 11001 is not supported by the deployed model.",
    "request_id": "5f28f4db-2f37-4fb4-8b5e-5882dd8b8218",
    "details": null
  }
}
```

Códigos HTTP esperados:

| HTTP | Uso |
|---:|---|
| `200` | Solicitud procesada correctamente. |
| `400` | Regla de negocio inválida. |
| `422` | Error de validación del schema Pydantic. |
| `429` | Límite de solicitudes excedido. |
| `500` | Error interno no recuperable. |
| `503` | Modelo, fuente de datos o dependencia temporalmente no disponible. |

Nunca devolver stack traces al cliente.

---

## 11. Seguridad mínima — fase académica

Los datos son agregados y el endpoint es únicamente de lectura/inferencia. Para esta fase se define seguridad mínima, evitando mecanismos que añadan complejidad sin proteger realmente el sistema.

### Obligatorio

1. **HTTPS en despliegue**. No publicar inferencias productivas por HTTP plano.
2. **CORS allowlist**, nunca `*` en despliegue. Permitir únicamente:
   - dominio desplegado del dashboard BIOMAC;
   - `localhost`/`127.0.0.1` para desarrollo.
3. **Validación estricta Pydantic** y rechazo de campos desconocidos.
4. **Rate limit básico por IP**, recomendado `60 requests/minute` para el prototipo.
5. API **read-only** para el dashboard; este contrato no incluye carga, edición ni eliminación de datos.
6. No registrar secretos ni payloads sensibles en logs.
7. No retornar rutas internas, stack traces, credenciales ni detalles del host.

### Autenticación

En esta fase **no se requiere autenticación de usuario** porque el prototipo consulta datos agregados no sensibles.

No se recomienda hardcodear una API key en el frontend: cualquier secreto incluido en JavaScript entregado al navegador deja de ser secreto.

Si posteriormente se incorpora un backend-for-frontend o acceso servidor-a-servidor, se podrá añadir `Authorization: Bearer <token>` o `X-API-Key` sin modificar el body del contrato.

---

## 12. Recomendación de implementación FastAPI

Modelos Pydantic sugeridos:

```text
PredictionRequest
PredictionResponse
ModelMetadata
GlobalMetrics
MunicipalityForecast
Municipality
DataQuality
CurrentStatus
Prediction
PredictionExplanation
ShapFeature
HistoricalPoint
MunicipalityEvaluation
PredictionHistoryPoint
DecisionSupport
DataSource
ApiError
```

Separación recomendada:

```text
app/
├── main.py
├── api/
│   └── v1/
│       ├── health.py
│       └── predictions.py
├── schemas/
│   ├── request.py
│   ├── response.py
│   └── errors.py
├── services/
│   ├── inference_service.py
│   ├── feature_service.py
│   ├── epidemiology_service.py
│   └── explanation_service.py
└── core/
    ├── config.py
    └── security.py
```

La ruta HTTP no debe contener lógica de modelado. Debe validar el request, delegar a servicios y serializar la respuesta.

---

## 13. Compatibilidad con el frontend actual

El frontend puede mantener su patrón `DengueRepository` y agregar una implementación HTTP:

```text
DengueRepository
├── MockDengueRepository   # UX/desarrollo
└── HttpDengueRepository   # FastAPI real
```

La transformación entre este contrato HTTP (`snake_case`) y los tipos internos del frontend puede hacerse exclusivamente dentro de `HttpDengueRepository`/adapter.

Los componentes React no deben conocer si los datos provienen de mocks o FastAPI.

---

## 14. Definition of Done del contrato

La integración se considera compatible cuando:

- FastAPI valida exactamente el request documentado;
- devuelve `T+1` y `T+2` reales para Bucaramanga y Cali;
- `label`, `probability` y `threshold` provienen del modelo/backend;
- el canal endémico proviene de datos reales;
- no se inventan casos futuros;
- SHAP solo se publica si es local y real;
- métricas globales y municipales están diferenciadas;
- metadata identifica modelo, versión, run y datos;
- los estados de error están controlados;
- el dashboard puede cambiar de mock a HTTP sin modificar sus componentes visuales.
