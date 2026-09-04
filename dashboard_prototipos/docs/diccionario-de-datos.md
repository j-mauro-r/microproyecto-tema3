# BIOMAC — Diccionario de datos para API y dashboard

**Estado:** especificación canónica de datos  
**Versión:** `2.0.0`  
**Ámbito:** carga mensual → inferencia con Champion → persistencia → dashboard  
**Documentos relacionados:** `arquitectura.md`, `implementacion.md`, `plan.md` v2.0.0 y `API-sign.md` v2.0.0

## 1. Principios

- `casos_clasico` es la serie objetivo vigente documentada.
- `casos_grave` es predictor epidemiológico y no se suma a `casos_clasico`.
- La capa de integración no entrena ni selecciona el Champion.
- El frontend no calcula features, canal, clase, probability, threshold ni SHAP.
- La carga mensual dispara una nueva inferencia; `Refresh` solo consulta el último snapshot exitoso.
- `null` significa dato contemplado pero no disponible/no aplicable; nunca se reemplaza silenciosamente por mocks.

## 2. Grupos de datos

1. **Carga mensual:** archivo y periodo que inician el run.
2. **Run:** trazabilidad del procesamiento.
3. **Champion:** metadata del modelo aprobado consumido por la integración.
4. **Calidad/entrada:** información necesaria para validar y preparar inferencia.
5. **Predicción:** salida normalizada T+1/T+2.
6. **Estado epidemiológico e histórico:** datos que contextualizan la alerta.
7. **Explicación:** factores locales solo si existen realmente.
8. **Persistencia/consulta:** snapshots usados por latest/history.

---

## 3. Carga mensual

| Campo | Tipo | Req./nullable | Semántica | Origen | Consumidor |
|---|---|---|---|---|---|
| `file` | file | Sí / No | Archivo del nuevo periodo mensual. | Dashboard | POST monthly-runs |
| `reference_month` | string `YYYY-MM` | Sí / No | Mes considerado corte `t`. | Usuario/request | InputService |
| `source_file.original_name` | string | Sí / No | Nombre recibido solo para trazabilidad, no como identificador. | API | Run |
| `source_file.size_bytes` | integer | Sí / No | Tamaño del archivo. | API | Validación/auditoría |
| `source_file.sha256` | string | Sí / No | Hash de contenido para trazabilidad/idempotencia. | API | Orchestrator/Run |
| `source_file.content_type` | string | No / Sí | Tipo MIME detectado/aceptado. | API | Validación |

### Reglas

- No usar el nombre del archivo para idempotencia.
- Un archivo inválido no llega al Champion.
- Datos posteriores a `reference_month` deben rechazarse o excluirse mediante una regla explícita del InputService; nunca usarse silenciosamente.

---

## 4. Run operacional

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `run_id` | string/UUID | Sí / No | Identificador estable de una ejecución mensual. |
| `request_id` | UUID | Sí / No | Identificador de la petición HTTP. |
| `status` | enum | Sí / No | `RECEIVED`, `VALIDATING`, `PREPARING`, `INFERENCING`, `PERSISTING`, `COMPLETED`, `FAILED`. |
| `stage` | enum | No / Sí | Etapa activa o etapa donde ocurrió un fallo. |
| `reference_month` | string | Sí / No | Corte usado en la inferencia. |
| `created_at` | datetime UTC | Sí / No | Inicio del run. |
| `completed_at` | datetime UTC | No / Sí | Finalización del run. |
| `source_file_sha256` | string | Sí / No | Hash del archivo asociado. |
| `champion_version` | string | Sí / No | Versión exacta del Champion usado. |
| `error_code` | string | No / Sí | Código estable de fallo. |
| `error_message` | string | No / Sí | Mensaje controlado para diagnóstico. |

### Idempotencia

Clave lógica:

`reference_month + source_file_sha256 + champion_version`

Un run `FAILED` no puede convertirse en la fuente de `predictions/latest`.

---

## 5. Metadata del Champion

| Campo | Tipo | Req./nullable | Semántica | Origen |
|---|---|---|---|---|
| `champion.name` | string | Sí / No | Nombre lógico del Champion. | Equipo/model registry |
| `champion.version` | string | Sí / No | Versión exacta desplegada. | Equipo/model registry |
| `champion.mlflow_run_id` | string | No / Sí | Run de MLflow si existe. | MLflow/metadata |
| `champion.artifact_id` | string | No / Sí | Identificador/ruta lógica del artefacto. | Configuración |
| `champion.output_type` | enum/string | Sí / No | Ej. `probability`, `expected_count`, `score`. | Contrato Champion |
| `champion.supported_horizons[]` | array[enum] | Sí / No | `T+1`, `T+2` realmente soportados. | Contrato Champion |
| `champion.feature_contract_version` | string | Sí / No | Versión del contrato de entrada/features. | Contrato Champion |
| `champion.decision_rule_version` | string | No / Sí | Versión de threshold/regla. | Contrato Champion |
| `champion.explanation_method` | string | No / Sí | Método local válido si existe. | Contrato Champion |

### Regla de gobierno

Esta metadata se **consume**; no se produce mediante entrenamiento dentro del alcance Dashboard/API.

---

## 6. Entrada de inferencia y calidad

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `input_contract_version` | string | Sí / No | Versión del schema que espera el Champion. |
| `feature_names[]` | array[string] | Sí / No | Features requeridas por el Champion. |
| `feature_snapshot_hash` | string | No / Sí | Hash de la entrada preparada para trazabilidad. |
| `data_quality.status` | enum | Sí / No | `complete`, `partial`, `degraded`. |
| `data_quality.last_observed_month` | string | Sí / No | Último mes epidemiológico realmente utilizado. |
| `data_quality.epidemiological_completeness` | float 0..1 | No / Sí | Completitud epidemiológica. |
| `data_quality.climate_completeness` | float 0..1 | No / Sí | Completitud climática si aplica. |
| `data_quality.warnings[]` | array[string] | Sí / No | Advertencias relevantes. |

El backend debe bloquear la inferencia si faltan campos esenciales según el contrato del Champion.

---

## 7. Definición del target

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `target_definition.business_target` | string | Sí / No | `dengue_excess_risk`. |
| `target_definition.target_series` | string | Sí / No | Serie sobre la que se define el exceso; actualmente `casos_clasico`. |
| `target_definition.predictor_series[]` | array[string] | Sí / No | Series adicionales usadas como features; incluye `casos_grave` si el Champion la usa. |
| `target_definition.series_are_summed` | boolean | Sí / No | `false` bajo la definición vigente. |
| `target_definition.excess_rule` | string | Sí / No | Regla versionada entregada por el contrato del modelo/pipeline. |

---

## 8. Municipio

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `municipality.divipola` | string | Sí / No | `68001` Bucaramanga o `76001` Cali. |
| `municipality.name` | string | Sí / No | Nombre de ciudad. |
| `municipality.department` | string | No / Sí | Departamento. |

---

## 9. Estado epidemiológico actual

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `current_status.reference_month` | string | Sí / No | Corte `t`. |
| `current_status.observed_cases` | integer/float | No / Sí | Casos observados de la serie target en `t`; nunca se reconstruye desde lags. |
| `current_status.p25` | float | No / Sí | P25 del canal si está disponible. |
| `current_status.p50` | float | No / Sí | P50 del canal si está disponible. |
| `current_status.p75` | float | No / Sí | P75 del canal/umbral epidemiológico si aplica. |
| `current_status.ratio_to_p75` | float | No / Sí | `observed_cases / p75`, derivado backend cuando P75 > 0. |
| `current_status.endemic_zone` | enum/string | No / Sí | Zona actual según regla documentada. |

El frontend no recalcula percentiles ni zona.

---

## 10. Predicción

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `predictions[].horizon` | enum | Sí / No | `T+1` o `T+2`. |
| `predictions[].target_month` | string | Sí / No | Mes futuro correspondiente. |
| `predictions[].label` | enum | Sí / No | `EXCESO` / `NO_EXCESO` cuando el contrato del Champion define clase. |
| `predictions[].model_output.type` | string | Sí / No | Tipo real de salida. |
| `predictions[].model_output.probability` | float 0..1 | No / Sí | Solo si es probabilidad válida. |
| `predictions[].model_output.expected_cases` | float | No / Sí | Solo si el Champion produce conteo esperado. |
| `predictions[].model_output.risk_score` | float | No / Sí | Score continuo si existe; no equivale a probabilidad. |
| `predictions[].uncertainty` | object | No / Sí | Solo si existe método válido. |

### Reglas

- `risk_score` nunca se presenta como `%` salvo que su definición sea una probabilidad.
- No crear `expected_cases` multiplicando casos observados por probabilidad.
- No convertir un output nativo a clase usando `0.50` por defecto.

---

## 11. Regla de decisión

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `decision_rule.type` | string | Sí / No | Ej. `probability_threshold`, `p75_multiplier`. |
| `decision_rule.probability_threshold` | float 0..1 | No / Sí | Threshold real del Champion si aplica. |
| `decision_rule.target_month_p75` | float | No / Sí | P75 del mes objetivo si la regla lo usa. |
| `decision_rule.multiplier_k` | float | No / Sí | Multiplicador si aplica. |
| `decision_rule.decision_threshold_cases` | float | No / Sí | Umbral en casos para modelos de conteo. |
| `decision_rule.version` | string | No / Sí | Versión de la regla. |

---

## 12. Explicación local

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `explanation.available` | boolean | Sí / No | Existe explicación válida para esta inferencia. |
| `explanation.method` | string | No / Sí | Ej. `shap`. |
| `explanation.scope` | string | No / Sí | Debe ser `local` para explicar una inferencia concreta. |
| `explanation.top_features[]` | array | Sí / No | Factores principales. |
| `top_features[].feature` | string | Sí / No | Nombre de feature. |
| `top_features[].value` | number/string | No / Sí | Valor de feature si procede. |
| `top_features[].contribution` | float | No / Sí | Contribución del método. |
| `top_features[].group` | enum/string | No / Sí | `epidemiological`, `climate`, otro. |

Una importancia global no se etiqueta como explicación SHAP local.

---

## 13. Histórico epidemiológico

| Campo | Tipo | Req./nullable | Semántica |
|---|---|---|---|
| `history[].month` | string | Sí / No | Mes histórico. |
| `history[].observed_cases` | number | Sí / No | Casos observados. |
| `history[].p25` | number | No / Sí | P25. |
| `history[].p50` | number | No / Sí | P50. |
| `history[].p75` | number | No / Sí | P75. |
| `history[].is_excess` | boolean | No / Sí | Exceso histórico según regla vigente/versionada. |

---

## 14. Snapshot persistido

Un `PredictionSnapshot` debe conservar como mínimo:

| Campo | Req. | Propósito |
|---|---:|---|
| `run_id` | Sí | Vínculo con ejecución. |
| `generated_at` | Sí | Momento de inferencia. |
| `reference_month` | Sí | Corte epidemiológico. |
| `source_file_sha256` | Sí | Linaje de entrada. |
| `champion` | Sí | Modelo exacto utilizado. |
| `target_definition` | Sí | Semántica de target. |
| `forecasts[]` | Sí | Resultado por municipio. |
| `data_quality` | Sí | Calidad/advertencias relevantes. |

Solo snapshots asociados a runs `COMPLETED` pueden ser candidatos a `latest`.

---

## 15. Consulta `latest`

`GET /api/v2/predictions/latest` devuelve el snapshot `COMPLETED` más reciente según `completed_at/generated_at`.

No crea:
- nuevos runs;
- nuevas features;
- nuevas predicciones;
- nuevos artefactos.

Este endpoint alimenta la apertura y el botón `Refresh`.

---

## 16. Historial de predicciones

Cada registro histórico debe permitir reconstruir:
- qué se predijo;
- para qué ciudad/horizonte/mes;
- qué Champion se usó;
- con qué archivo/corte;
- cuándo se generó;
- qué output/regla produjo la clase.

Cuando exista observación posterior, podrá agregarse `observed_label/outcome_type` para F24 sin modificar el resultado original.

---

## 17. Errores

| Código | Etapa típica | Significado |
|---|---|---|
| `INVALID_REQUEST` | recepción | Parámetros inválidos. |
| `INVALID_UPLOAD` | validación | Archivo inválido. |
| `PERIOD_CONFLICT` | validación | Conflicto con periodo ya procesado. |
| `INSUFFICIENT_DATA` | preparación | Datos insuficientes. |
| `CHAMPION_INPUT_INVALID` | preparación | Input incompatible con contrato. |
| `CHAMPION_NOT_READY` | inferencia | Artefacto/adapter no disponible. |
| `PREPARATION_FAILED` | preparación | Fallo técnico preparando inputs. |
| `INFERENCE_FAILED` | inferencia | Fallo al ejecutar Champion. |
| `PERSISTENCE_FAILED` | persistencia | No se pudo guardar snapshot/run. |
| `PREDICTION_NOT_FOUND` | consulta | No existe snapshot exitoso. |

Todo error debe poder asociarse con `request_id` y, cuando ya exista, `run_id`.

---

## 18. Mapeo funcional principal

| Funcionalidad | Datos clave |
|---|---|
| F03 Fecha de corte | `reference_month`, `last_observed_month` |
| F04 Calidad/frescura | `data_quality.*` |
| F05/F08 Alerta T+1/T+2 | `predictions[].horizon/label/target_month` |
| F06/F16 Señal cuantitativa | `model_output.*` |
| F09 Threshold | `decision_rule.*` |
| F10/F11 Canal actual | `current_status.*` |
| F13 Histórico | `history[]` |
| F17-F19 Explicabilidad | `explanation.*` |
| F23/F24 Historial | snapshots persistidos |
| F26 Trazabilidad | `run_id`, Champion, hash fuente, timestamps |
| F29 Estados | run `status/stage/error` |
| F30 Última inferencia | `generated_at/completed_at` |
| F34 Actualizar datos | `file`, `reference_month` |
| F35 Validación carga | source metadata + errores |
| F36 Estado procesamiento | `run.status/stage/run_id` |
| F37 Refresh | `GET predictions/latest` |

---

## 19. Brechas/dependencias antes de implementar

La capa de integración necesita confirmar con el equipo de modelado:

1. artefacto Champion o formato de salidas materializadas;
2. versión/nombre del Champion;
3. contrato exacto de entrada/features;
4. transformaciones reutilizables para inferencia;
5. T+1/T+2 realmente soportados;
6. tipo de output por horizonte;
7. threshold/regla de decisión;
8. explicación local disponible o no;
9. metadata mínima de trazabilidad.

No deben completarse estas brechas mediante suposiciones del frontend/backend.

## 20. Gobierno

Un cambio semántico debe revisar simultáneamente:
1. `arquitectura.md` si cambia el flujo/responsabilidad;
2. `plan.md` si cambia funcionalidad/UI;
3. `API-sign.md` si cambia HTTP/schema;
4. este diccionario;
5. schemas Pydantic;
6. tipos/adaptadores del dashboard;
7. pruebas de contrato.

El entrenamiento del modelo no forma parte de este gobierno documental; solo el contrato con el Champion y sus salidas.
