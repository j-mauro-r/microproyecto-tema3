# BIOMAC — Diccionario de datos para API y dashboard

**Estado:** especificación canónica de datos  
**Versión:** `1.0.0`  
**Ámbito:** FastAPI ↔ Dashboard BIOMAC  
**Documentos relacionados:** `plan.md` v1.3.0 y `API-sign.md` v1.1.0

> Este documento define la semántica, origen, formato, disponibilidad y consumo funcional de los datos que alimentarán el API y las 33 funcionalidades del dashboard. No sustituye el contrato técnico de `API-sign.md`; lo complementa como catálogo de datos.

## 1. Alcance vigente

BIOMAC estima **riesgo de exceso de dengue** para Bucaramanga (`68001`) y Cali (`76001`), con granularidad mensual y horizontes `T+1` y `T+2`.

Definiciones canónicas:
- `casos_clasico` es la serie objetivo vigente;
- `casos_grave` es predictor epidemiológico y **no se suma** a `casos_clasico`;
- exceso = `casos_clasico > P75` del municipio y mes objetivo;
- clase de salida = `EXCESO / NO_EXCESO`;
- el frontend no calcula features, canal endémico, clase, probabilidad, threshold ni SHAP;
- la API debe devolver únicamente resultados producidos o derivados de forma reproducible por pipeline/modelo/backend.

## 2. Convenciones del diccionario

### Estado de disponibilidad

- `DISPONIBLE PR12`: existe una salida o insumo equivalente en PR #12.
- `PARCIAL`: existe parte de la información, pero requiere adaptación, persistencia o consolidación para el API.
- `PENDIENTE`: no se identifica todavía una salida suficiente en PR #12.
- `DERIVABLE BACKEND`: puede obtenerse de datos disponibles sin inferencia nueva, pero debe calcularlo el backend.
- `CONFIGURACIÓN`: proviene del contrato, configuración o catálogo y no del modelo.

### Módulos

- `PANTALLA PRINCIPAL`
- `HISTÓRICO Y EVALUACIÓN`
- `MODELO Y DATOS`
- `TRANSVERSAL`

### Reglas de nulabilidad

`Nullable = Sí` significa que el campo pertenece al contrato, pero puede ser `null` cuando el método/modelo desplegado no lo produzca. `null` nunca debe reemplazarse silenciosamente por un mock.

---

## 3. Diccionario — Request y contexto de inferencia

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `schema_version` | Versión del contrato | Versión SemVer usada para interpretar request/response. | contexto | string | SemVer | Sí / No | `1.1.0` o compatible | API | transversal | configuración | F28 | MODELO Y DATOS | `1.1.0` | CONFIGURACIÓN | contrato API |
| `municipality_codes[]` | Municipios solicitados | DIVIPOLA de las ciudades consultadas. | contexto | array[string] | 5 dígitos | Sí / No | `68001`, `76001` | request/catálogo | actual | validación catálogo | F02, F12, F33 | PANTALLA PRINCIPAL | `["68001","76001"]` | CONFIGURACIÓN | request_id |
| `reference_month` | Mes de referencia | Mes considerado “actual” para construir la inferencia sin usar información posterior. | contexto | string | `YYYY-MM` | Sí / No | mes soportado | request/pipeline | corte `t` | máximo dato permitido = t | F03, F14, F23, F30, F33 | PANTALLA PRINCIPAL | `2024-12` | DISPONIBLE PR12 / PARCIAL para modo arbitrario | request_id + data_version |
| `horizons[]` | Horizontes solicitados | Horizontes de predicción requeridos. | contexto | array[enum] | — | Sí / No | `T+1`, `T+2` | request | futuro | artefacto evaluado por horizonte | F05, F08, F12, F16, F33 | PANTALLA PRINCIPAL | `["T+1","T+2"]` | DISPONIBLE PR12 | model_version por H |
| `history_months` | Ventana histórica | Número de meses históricos que devuelve el API. | contexto | integer | meses | No / No | `0..240` | request | histórico | selección de ventana | F13, F23 | PANTALLA PRINCIPAL / HISTÓRICO Y EVALUACIÓN | `36` | CONFIGURACIÓN | request_id |
| `include_explanations` | Solicitar explicaciones | Indica si se solicita explicación local cuando esté disponible. | contexto | boolean | — | No / No | `true/false` | request | T+1/T+2 | configuración | F17-F19 | PANTALLA PRINCIPAL | `true` | CONFIGURACIÓN | request_id |
| `include_prediction_history` | Solicitar historial | Indica si la respuesta debe incluir inferencias históricas persistidas. | contexto | boolean | — | No / No | `true/false` | request | histórico | configuración | F23, F24 | HISTÓRICO Y EVALUACIÓN | `true` | CONFIGURACIÓN | request_id |
| `request_id` | ID de solicitud | Identificador único de una petición/inferencia. | contexto | UUID | UUID | Sí / No | UUID v4 | FastAPI | transversal | generado por API | F26, F30 | MODELO Y DATOS | `d312a52d-...` | DERIVABLE BACKEND | logs/API |
| `generated_at` | Última inferencia | Fecha/hora UTC en que se generó la respuesta. | contexto | datetime | ISO-8601 UTC | Sí / No | timestamp válido | FastAPI | inferencia | reloj servidor | F01, F30 | PANTALLA PRINCIPAL | `2026-09-02T18:30:00Z` | DERIVABLE BACKEND | request_id |

---

## 4. Diccionario — Definición del target

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `target_definition.business_target` | Objetivo de negocio | Nombre estable del problema que comunica BIOMAC. | modelo | string | — | Sí / No | `dengue_excess_risk` | configuración | transversal | catálogo | F01, F26 | PANTALLA PRINCIPAL / MODELO Y DATOS | `dengue_excess_risk` | CONFIGURACIÓN | schema_version |
| `target_definition.target_series` | Serie objetivo | Serie epidemiológica utilizada para definir el exceso. | modelo | string | — | Sí / No | `casos_clasico` | pipeline | actual/futuro | definición canónica | F01, F27 | MODELO Y DATOS | `casos_clasico` | DISPONIBLE PR12 | data_version |
| `target_definition.predictor_series[]` | Series epidemiológicas predictoras | Series adicionales usadas como features. | modelo | array[string] | — | Sí / No | incluye `casos_grave` | pipeline | histórico hasta t | feature engineering | F18, F27 | MODELO Y DATOS | `["casos_grave"]` | DISPONIBLE PR12 | data_version |
| `target_definition.series_are_summed` | Regla de consolidación | Confirma que clásico y grave no se suman. | modelo | boolean | — | Sí / No | `false` | configuración | transversal | siempre `false` definición vigente | F27 | MODELO Y DATOS | `false` | CONFIGURACIÓN | schema_version |
| `target_definition.excess_rule` | Definición de exceso | Regla epidemiológica usada para generar la clase objetivo. | canal/modelo | string | — | Sí / No | versión controlada | pipeline | mes objetivo | `casos_clasico > P75` | F05, F09, F10, F11, F22, F26 | TRANSVERSAL | `casos_clasico_above_p75` | DISPONIBLE PR12 | data_version + rule_version |

---

## 5. Diccionario — Municipio y calidad de datos

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `forecasts[].municipality.divipola` | Código municipio | Identificador DANE de municipio. | contexto | string | 5 dígitos | Sí / No | `68001`,`76001` | SIVIGILA/catálogo | actual | normalización DIVIPOLA | F02, F12 | PANTALLA PRINCIPAL | `68001` | DISPONIBLE PR12 | data_version |
| `forecasts[].municipality.name` | Ciudad | Nombre del municipio. | contexto | string | texto | Sí / No | catálogo | SIVIGILA/catálogo | actual | lookup DIVIPOLA | F01, F02, F05, F12 | PANTALLA PRINCIPAL | `Bucaramanga` | DISPONIBLE PR12 | data_version |
| `forecasts[].municipality.department` | Departamento | Departamento del municipio. | contexto | string | texto | Sí / Sí | catálogo | SIVIGILA | actual | lookup | F01, F27 | MODELO Y DATOS | `Santander` | DISPONIBLE PR12 | data_version |
| `forecasts[].data_quality.status` | Estado de calidad | Semáforo consolidado de disponibilidad/calidad de entradas. | calidad | enum | — | Sí / No | `complete`,`partial`,`degraded` | backend/pipeline | corte t | reglas de completitud | F04, F29 | MODELO Y DATOS | `complete` | PENDIENTE | data_version + quality_rule |
| `forecasts[].data_quality.last_observed_month` | Último mes observado | Último mes con dato epidemiológico válido usado. | calidad | string | `YYYY-MM` | Sí / No | ≤ reference_month | pipeline | actual | máximo periodo válido | F03, F04 | PANTALLA PRINCIPAL / MODELO Y DATOS | `2024-12` | PARCIAL | data_version |
| `forecasts[].data_quality.epidemiological_completeness` | Completitud epidemiológica | Proporción de campos/periodos epidemiológicos esperados disponibles. | calidad | float | proporción | No / Sí | `[0,1]` | pipeline | corte t | regla versionada | F04 | MODELO Y DATOS | `1.0` | PENDIENTE | quality_rule + data_version |
| `forecasts[].data_quality.climate_completeness` | Completitud climática | Proporción de datos climáticos requeridos disponibles. | calidad | float | proporción | No / Sí | `[0,1]` | ERA5/GEE pipeline | corte t | cobertura features clima | F04, F19, F27 | MODELO Y DATOS | `0.96` | PARCIAL | data_version |
| `forecasts[].data_quality.warnings[]` | Advertencias de datos | Lista de anomalías o faltantes relevantes para interpretar la inferencia. | calidad | array[string] | texto | Sí / No | lista | backend/pipeline | corte t | validaciones | F04, F29 | MODELO Y DATOS | `[]` | PENDIENTE | request_id + data_version |

---

## 6. Diccionario — Estado epidemiológico actual y canal endémico

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `current_status.reference_month` | Mes actual epidemiológico | Mes del estado observado presentado. | canal | string | `YYYY-MM` | Sí / No | = reference_month | pipeline | t | selección temporal | F03, F10, F11 | PANTALLA PRINCIPAL | `2024-12` | DISPONIBLE PR12 | data_version |
| `current_status.observed_cases` | Casos observados | Conteo de `casos_clasico` del mes de referencia. | canal | integer | casos | Sí / No | `>=0` | SIVIGILA | t | agregación municipio-mes | F10, F13 | PANTALLA PRINCIPAL | `142` | DISPONIBLE PR12 | data_version |
| `current_status.p25` | P25 canal | Percentil 25 del canal para municipio/mes calendario. | canal | float | casos | No / Sí | `>=0` | feature pipeline | t | referencia epidemiológica vigente | F11, F13 | PANTALLA PRINCIPAL | `92` | DISPONIBLE PR12 | data_version + canal_version |
| `current_status.p50` | P50 canal | Mediana del canal endémico. | canal | float | casos | No / Sí | `>=0` | feature pipeline | t | percentil 50 | F11, F13 | PANTALLA PRINCIPAL | `121` | PENDIENTE/por confirmar en pipeline final | canal_version |
| `current_status.p75` | P75 canal | Umbral de exceso del mes actual. | canal | float | casos | Sí / No | `>=0` | feature pipeline | t | percentil 75 | F09-F13 | PANTALLA PRINCIPAL | `158` | DISPONIBLE PR12 | data_version + canal_version |
| `current_status.ratio_to_p75` | Relación con P75 | Proximidad del conteo observado al umbral de exceso. | canal | float | ratio | No / Sí | `>=0` | backend | t | `observed_cases / p75` | F10 | PANTALLA PRINCIPAL | `0.899` | DERIVABLE BACKEND | request_id + canal_version |
| `current_status.endemic_zone` | Zona epidemiológica actual | Clasificación del estado actual respecto al canal. | canal | enum | — | Sí / No | `NORMAL`,`ENDEMICO`,`ALERTA`,`EXCESO` según definición vigente | feature pipeline/backend | t | comparación P25/P50/P75 | F10, F11, F22 | PANTALLA PRINCIPAL | `ALERTA` | PARCIAL | canal_version |

---

## 7. Diccionario — Predicciones T+1/T+2

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `predictions[].horizon` | Horizonte | Identifica si el resultado corresponde a T+1 o T+2. | predicción | enum | — | Sí / No | `T+1`,`T+2` | champion | futuro | modelo específico H | F05, F08, F12, F16 | PANTALLA PRINCIPAL | `T+2` | DISPONIBLE PR12 | model_version + run_id |
| `predictions[].target_month` | Mes objetivo | Mes calendario pronosticado. | predicción | string | `YYYY-MM` | Sí / No | reference + H | backend | T+1/T+2 | suma de meses | F05, F08, F14, F16, F23 | PANTALLA PRINCIPAL | `2025-02` | DISPONIBLE PR12 | request_id |
| `predictions[].label` | Alerta de exceso | Clase final emitida por backend/champion. | predicción | enum | — | Sí / No | `EXCESO`,`NO_EXCESO` | champion/backend | T+1/T+2 | output vs threshold/regla | F05, F08, F12, F22-F24 | PANTALLA PRINCIPAL | `EXCESO` | DISPONIBLE PR12 | model_version + threshold_version |
| `predictions[].model_output.type` | Tipo de salida | Define cómo interpretar la señal cuantitativa. | predicción | enum | — | Sí / No | `probability`,`expected_count`,`risk_score` u otro versionado | champion | T+1/T+2 | metadata artefacto | F06, F08, F16, F26 | TRANSVERSAL | `probability` | DISPONIBLE PR12 para clasificadores | model_version |
| `predictions[].model_output.probability` | Probabilidad de exceso | Probabilidad de clase EXCESO cuando el champion produce/calibra una probabilidad válida. | predicción | float | proporción | No / Sí | `[0,1]` | champion/calibrador | T+1/T+2 | `predict_proba` + calibración si aplica | F06-F09, F12, F16, F20 | PANTALLA PRINCIPAL | `0.78` | DISPONIBLE PR12 | model_version + calibration_method |
| `predictions[].model_output.expected_cases` | Casos esperados | Conteo esperado futuro si el champion es un modelo de conteo. | predicción | float | casos | No / Sí | `>=0` | champion | T+1/T+2 | salida nativa modelo de conteo | F06, F08, F15, F16 | PANTALLA PRINCIPAL | `236.4` | PENDIENTE para champion clasificador PR12 | model_version |
| `predictions[].model_output.risk_score` | Score de riesgo | Score continuo válido para ordenar riesgo; no debe mostrarse como probabilidad salvo calibración. | predicción | float | adimensional | No / Sí | definición del modelo | champion/backend | T+1/T+2 | salida/model-derived | F06, F08, F12, F16 | PANTALLA PRINCIPAL | `1.08` | PARCIAL | model_version + score_definition |
| `predictions[].decision_rule.type` | Tipo de regla | Tipo de regla usada para transformar salida en clase. | predicción | enum | — | Sí / No | `probability_threshold`,`p75_multiplier`, etc. | modelo/config | T+1/T+2 | metadata champion | F09, F22, F23 | PANTALLA PRINCIPAL | `probability_threshold` | DISPONIBLE PR12 | threshold_version |
| `predictions[].decision_rule.probability_threshold` | Threshold probabilístico | Umbral del champion clasificador para emitir EXCESO. | predicción | float | proporción | No / Sí | `[0,1]` | entrenamiento/MLflow | T+1/T+2 | selección en validación | F09, F16, F23, F25 | TRANSVERSAL | `0.61` | DISPONIBLE PR12 | run_id + model_version |
| `predictions[].decision_rule.target_month_p75` | P75 mes objetivo | Umbral epidemiológico correspondiente al mes futuro. | canal | float | casos | No / Sí | `>=0` | feature/canal pipeline | T+1/T+2 | canal municipio-mes objetivo | F09, F10, F16 | PANTALLA PRINCIPAL | `219` | DISPONIBLE PR12/PARCIAL API | canal_version |
| `predictions[].decision_rule.multiplier_k` | Multiplicador de regla | Multiplicador usado por modelos/reglas de conteo frente a P75. | predicción | float | factor | No / Sí | `>0` | configuración/modelo | T+1/T+2 | regla versionada | F09 | PANTALLA PRINCIPAL | `1.0` | PENDIENTE si no aplica al champion | rule_version |
| `predictions[].decision_rule.decision_threshold_cases` | Threshold en casos | Umbral final expresado en casos para regla de conteo. | predicción | float | casos | No / Sí | `>=0` | backend | T+1/T+2 | `k × target_month_p75` | F09, F16 | PANTALLA PRINCIPAL | `219` | DERIVABLE BACKEND si aplica | rule_version |
| `predictions[].uncertainty` | Incertidumbre | Intervalo/medida de incertidumbre solo si existe método estadístico válido. | predicción | object | depende método | No / Sí | método versionado | modelo | T+1/T+2 | bootstrap/conformal/intervalo válido | F07 | PANTALLA PRINCIPAL | `null` | PENDIENTE | model_version + uncertainty_method |

---

## 8. Diccionario — Explicabilidad local

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `predictions[].explanation.available` | Explicación disponible | Indica si existe explicación local válida para esa inferencia. | SHAP | boolean | — | Sí / No | `true/false` | backend | T+1/T+2 | disponibilidad de artefacto | F17-F19 | PANTALLA PRINCIPAL | `true` | DISPONIBLE PR12 | model_version + shap_artifact |
| `predictions[].explanation.method` | Método explicativo | Método usado para atribución. | SHAP | enum/string | — | No / Sí | `shap` u otro aprobado | pipeline explicabilidad | T+1/T+2 | método real | F17 | PANTALLA PRINCIPAL | `shap` | DISPONIBLE PR12 | explainer_version |
| `predictions[].explanation.scope` | Alcance explicación | Distingue explicación local de importancia global. | SHAP | enum | — | No / Sí | `local` | pipeline explicabilidad | inferencia individual | debe ser local para F17 | F17 | PANTALLA PRINCIPAL | `local` | DISPONIBLE PR12 | model_version |
| `top_features[].feature` | Variable explicativa | Nombre de la feature que contribuye a la inferencia. | SHAP | string | — | No / No | feature registrada | SHAP + feature pipeline | T+1/T+2 | top-N por magnitud | F17-F19 | PANTALLA PRINCIPAL | `casos_clasico_lag_1` | DISPONIBLE PR12 | feature_schema + model_version |
| `top_features[].feature_value` | Valor observado de feature | Valor de la variable para la inferencia evaluada. | SHAP | number/string | según feature | No / Sí | dominio feature | feature pipeline | corte t | valor fila inferencia | F17-F19 | PANTALLA PRINCIPAL | `146` | PARCIAL | data_version |
| `top_features[].shap_value` | Contribución SHAP | Magnitud y signo de contribución al output del modelo. | SHAP | float | escala del modelo | No / No | real | SHAP | T+1/T+2 | TreeExplainer/explicador válido | F17-F19 | PANTALLA PRINCIPAL | `0.37` | DISPONIBLE PR12 | shap_artifact + model_version |
| `top_features[].direction` | Dirección de contribución | Etiqueta interpretable del signo de contribución. | SHAP | enum | — | No / Sí | `increase`,`decrease`,`neutral` | backend | T+1/T+2 | signo de SHAP | F17-F20 | PANTALLA PRINCIPAL | `increase` | DERIVABLE BACKEND | request_id |
| `top_features[].group` | Grupo de variable | Clasifica la feature como epidemiológica, climática, estacional, canal, etc. | SHAP | enum | — | No / Sí | catálogo feature | backend/catálogo | transversal | mapeo feature→grupo | F18, F19 | PANTALLA PRINCIPAL | `epidemiological` | DERIVABLE BACKEND | feature_schema |

---

## 9. Diccionario — Serie histórica y canal

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `history[].month` | Mes histórico | Periodo observado de la serie. | histórico | string | `YYYY-MM` | Sí / No | ≤ reference_month | SIVIGILA/pipeline | histórico | selección ventana | F13, F14 | PANTALLA PRINCIPAL | `2024-11` | DISPONIBLE PR12 | data_version |
| `history[].observed_cases` | Casos históricos | Casos clásicos observados del municipio/mes. | histórico | integer | casos | Sí / No | `>=0` | SIVIGILA | histórico | agregación mensual | F13, F14 | PANTALLA PRINCIPAL | `130` | DISPONIBLE PR12 | data_version |
| `history[].p25` | P25 histórico | Percentil 25 correspondiente a ese mes. | histórico | float | casos | No / Sí | `>=0` | canal pipeline | histórico | canal versionado | F13 | PANTALLA PRINCIPAL | `85` | DISPONIBLE PR12 | canal_version |
| `history[].p50` | P50 histórico | Mediana correspondiente a ese mes. | histórico | float | casos | No / Sí | `>=0` | canal pipeline | histórico | canal versionado | F13 | PANTALLA PRINCIPAL | `112` | PENDIENTE/por confirmar | canal_version |
| `history[].p75` | P75 histórico | Umbral de exceso correspondiente a ese mes. | histórico | float | casos | Sí / No | `>=0` | canal pipeline | histórico | canal versionado | F13 | PANTALLA PRINCIPAL | `151` | DISPONIBLE PR12 | canal_version |
| `history[].is_excess` | Exceso histórico | Indica si el mes observado superó su P75. | histórico | boolean | — | Sí / No | `true/false` | pipeline | histórico | `observed_cases > p75` | F13, F24 | PANTALLA PRINCIPAL / HISTÓRICO Y EVALUACIÓN | `false` | DISPONIBLE PR12 | canal_version |

---

## 10. Diccionario — Historial de predicciones y evaluación operacional

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `prediction_history[].generated_at` | Fecha de predicción | Momento en que se generó la inferencia histórica. | histórico | datetime | UTC | Sí / No | timestamp | persistencia/API | histórico | guardado al inferir | F23, F30 | HISTÓRICO Y EVALUACIÓN | `2026-09-01T10:00:00Z` | DISPONIBLE PR12 como snapshot/backtest; PARCIAL operacional | request_id |
| `prediction_history[].reference_month` | Corte histórico | Mes de datos usado cuando se emitió la predicción. | histórico | string | `YYYY-MM` | Sí / No | histórico | persistencia | t histórico | guardado al inferir | F23, F24, F33 | HISTÓRICO Y EVALUACIÓN | `2024-06` | DISPONIBLE PR12 | data_version |
| `prediction_history[].horizon` | Horizonte histórico | Horizonte de la predicción almacenada. | histórico | enum | — | Sí / No | T+1/T+2 | persistencia | futuro histórico | guardado | F23, F24 | HISTÓRICO Y EVALUACIÓN | `T+2` | DISPONIBLE PR12 | model_version |
| `prediction_history[].target_month` | Mes predicho | Mes al que correspondía la alerta histórica. | histórico | string | `YYYY-MM` | Sí / No | > reference_month | persistencia | futuro histórico | reference + H | F23, F24 | HISTÓRICO Y EVALUACIÓN | `2024-08` | DISPONIBLE PR12 | request_id |
| `prediction_history[].label` | Clase predicha | EXCESO/NO_EXCESO que emitió el modelo. | histórico | enum | — | Sí / No | `EXCESO`,`NO_EXCESO` | champion | histórico | output vs regla | F23, F24 | HISTÓRICO Y EVALUACIÓN | `EXCESO` | DISPONIBLE PR12 | model_version |
| `prediction_history[].probability` | Probabilidad histórica | Probabilidad registrada en esa inferencia, si aplica. | histórico | float | proporción | No / Sí | `[0,1]` | champion | histórico | output guardado | F23, F24 | HISTÓRICO Y EVALUACIÓN | `0.74` | DISPONIBLE PR12 | calibration_method |
| `prediction_history[].decision_threshold` | Threshold histórico | Threshold usado en esa inferencia. | histórico | float | proporción/casos | Sí / No | según regla | model metadata | histórico | valor versionado | F23, F24 | HISTÓRICO Y EVALUACIÓN | `0.61` | DISPONIBLE PR12 | threshold_version |
| `prediction_history[].model_version` | Modelo histórico | Versión exacta del modelo que produjo la predicción. | histórico | string | — | Sí / No | versión registrada | MLflow/model registry | histórico | artefacto activo | F23, F26 | HISTÓRICO Y EVALUACIÓN | `xgb-T2-v3` | DISPONIBLE PR12/PARCIAL versión formal | MLflow run/model version |
| `prediction_history[].observed_label` | Resultado observado | Clase real observada posteriormente para el mes objetivo. | histórico | enum | — | No / Sí | `EXCESO`,`NO_EXCESO` | SIVIGILA/pipeline | posterior al target | observado vs P75 | F24 | HISTÓRICO Y EVALUACIÓN | `NO_EXCESO` | DISPONIBLE PR12 bajo supuesto de alineación correcta | data_version |
| `prediction_history[].outcome_type` | Tipo de resultado | Clasifica la predicción como acierto, falsa alarma, omisión o verdadero negativo. | histórico | enum | — | No / Sí | `TP`,`FP`,`FN`,`TN` | backend | histórico evaluado | label vs observed_label | F24 | HISTÓRICO Y EVALUACIÓN | `FP` | DERIVABLE BACKEND | request/model/data versions |

---

## 11. Diccionario — Métricas de desempeño

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `evaluation.scope` | Alcance evaluación | Nivel al que corresponden las métricas. | métricas | enum | — | Sí / No | `global`,`municipality` | evaluación | test | partición evaluada | F25 | MODELO Y DATOS | `municipality` | DISPONIBLE PR12 | run_id |
| `evaluation.evaluation_period` | Periodo evaluación | Ventana temporal usada para medir desempeño. | métricas | string | `YYYY-YYYY` | Sí / No | periodo válido | evaluación | test | partición temporal | F25, F26 | MODELO Y DATOS | `2023-2025` | DISPONIBLE PR12/PARCIAL según versión final | run_id |
| `evaluation.sample_size` | Muestra evaluada | Número de observaciones usadas para métricas. | métricas | integer | observaciones | Sí / No | `>=0` | evaluación | test | conteo | F25 | MODELO Y DATOS | `36` | DISPONIBLE PR12 | run_id |
| `evaluation.recall` | Sensibilidad | Proporción de excesos reales detectados. | métricas | float | proporción | No / Sí | `[0,1]` | evaluación | test/H | `TP/(TP+FN)` | F25 | MODELO Y DATOS | `0.82` | DISPONIBLE PR12 | run_id + model_version |
| `evaluation.precision` | Precisión | Proporción de alertas emitidas que fueron exceso real. | métricas | float | proporción | No / Sí | `[0,1]` | evaluación | test/H | `TP/(TP+FP)` | F25 | MODELO Y DATOS | `0.76` | DISPONIBLE PR12 | run_id |
| `evaluation.f1` | F1 | Media armónica Recall/Precision. | métricas | float | proporción | No / Sí | `[0,1]` | evaluación | test/H | F1 | F25 | MODELO Y DATOS | `0.79` | DISPONIBLE PR12 | run_id |
| `evaluation.false_alarm_rate` | Tasa falsas alarmas | Proporción de negativos reales clasificados como exceso. | métricas | float | proporción | No / Sí | `[0,1]` | evaluación | test/H | `FP/(FP+TN)` | F24, F25 | MODELO Y DATOS | `0.12` | DISPONIBLE PR12 | run_id |
| `evaluation.auroc` | AUROC | Capacidad de discriminación global del score. | métricas | float | área | No / Sí | `[0,1]` | evaluación | test/H | ROC AUC | F25 | MODELO Y DATOS | `0.90` | DISPONIBLE PR12 | run_id |
| `evaluation.average_precision` | Average Precision | Área-resumen de precision-recall para evento desbalanceado. | métricas | float | área | No / Sí | `[0,1]` | evaluación | test/H | AP | F25 | MODELO Y DATOS | `0.88` | DISPONIBLE PR12 | run_id |
| `evaluation.outbreak_onsets` | Inicios reales | Número de inicios de episodio de exceso en evaluación. | métricas | integer | eventos | No / Sí | `>=0` | evaluación | test/H | transición 0→1 | F25 | MODELO Y DATOS | `22` | DISPONIBLE PR12 | run_id + data_version |
| `evaluation.outbreak_onsets_detected` | Inicios detectados | Inicios reales correctamente anticipados. | métricas | integer | eventos | No / Sí | `>=0` | evaluación | test/H | predicción positiva sobre inicio | F25 | MODELO Y DATOS | `14` | DISPONIBLE PR12 | run_id |
| `evaluation.onset_detect_rate` | Tasa detección de inicios | Proporción de inicios detectados. | métricas | float | proporción | No / Sí | `[0,1]` | evaluación/backend | test/H | detectados/inicios | F25 | MODELO Y DATOS | `0.64` | DISPONIBLE PR12 | run_id |

---

## 12. Diccionario — Modelo, MLflow y trazabilidad

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `models[].horizon` | Horizonte del artefacto | Horizonte específico servido por el artefacto. | modelo | enum | — | Sí / No | T+1/T+2 | MLflow | H | registro artefacto | F08, F26 | MODELO Y DATOS | `T+1` | DISPONIBLE PR12 | model registry |
| `models[].name` | Nombre del modelo | Nombre lógico/registrado del champion. | modelo | string | — | Sí / No | registrado | MLflow | H | alias champion | F26 | MODELO Y DATOS | `dengue-xgb-clasico-T1` | DISPONIBLE PR12 | MLflow registry |
| `models[].version` | Versión de modelo | Versión inmutable del artefacto servido. | modelo | string/int | — | Sí / No | registro MLflow | MLflow | H | model registry version | F26 | MODELO Y DATOS | `3` | PARCIAL hasta registro definitivo | MLflow registry |
| `models[].alias` | Alias de despliegue | Alias operacional del artefacto. | modelo | string | — | No / Sí | `champion` | MLflow | H | alias registry | F26, F28 | MODELO Y DATOS | `champion` | DISPONIBLE PR12 | registry |
| `models[].mlflow_run_id` | Run MLflow | ID del experimento que generó/registró artefacto. | modelo | string | — | No / Sí | run válido | MLflow | H | run activo | F26 | MODELO Y DATOS | `abc123...` | DISPONIBLE PR12 | MLflow |
| `models[].trained_at` | Fecha entrenamiento | Fecha/hora del entrenamiento del artefacto final. | modelo | datetime | UTC | Sí / No | timestamp | MLflow | H | metadata run | F26 | MODELO Y DATOS | `2026-09-02T15:00:00Z` | PARCIAL | run_id |
| `models[].training_period` | Periodo entrenamiento | Ventana temporal usada para ajustar el modelo. | modelo | string | años/meses | Sí / No | periodo | pipeline/MLflow | histórico | metadata | F26 | MODELO Y DATOS | `2007-2022` | DISPONIBLE PR12/PARCIAL según corrida final | run_id |
| `models[].test_period` | Periodo test | Ventana reservada para evaluación final. | modelo | string | años/meses | No / Sí | periodo | pipeline/MLflow | histórico | metadata | F25, F26 | MODELO Y DATOS | `2023-2025` | DISPONIBLE PR12/PARCIAL | run_id |
| `models[].data_version` | Versión de datos | Hash/revisión DVC de los datos usados. | modelo | string | hash/rev | No / Sí | revisión válida | DVC | histórico | metadata pipeline | F26, F27 | MODELO Y DATOS | `dvc:abc123` | PENDIENTE/PARCIAL | DVC |
| `models[].feature_schema_version` | Versión de features | Identifica el esquema exacto de variables de entrada. | modelo | string | SemVer/hash | No / Sí | versión | pipeline | H | catálogo features | F18, F19, F26 | MODELO Y DATOS | `features-1.0.0` | PARCIAL | data/model version |
| `models[].output_type` | Tipo de salida del champion | Indica si produce probabilidad, conteo o score. | modelo | enum | — | Sí / No | catálogo | MLflow/model metadata | H | metadata artefacto | F06, F16, F26 | MODELO Y DATOS | `probability` | DISPONIBLE PR12 | model_version |
| `models[].calibrated` | Probabilidad calibrada | Indica si la probabilidad fue calibrada formalmente. | modelo | boolean | — | No / Sí | true/false | calibración | H | metadata calibrador | F06, F07, F26 | MODELO Y DATOS | `true` | DISPONIBLE PR12 | calibration_method |
| `models[].calibration_method` | Método calibración | Método usado para calibrar probabilidades. | modelo | string | — | No / Sí | `isotonic`, etc. | calibración | H | metadata artefacto | F06, F26 | MODELO Y DATOS | `isotonic` | DISPONIBLE PR12 | calibrated artifact |

---

## 13. Diccionario — Fuentes de datos

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `data_sources[].name` | Fuente | Nombre de la fuente efectivamente usada. | fuentes | string | texto | Sí / No | catálogo | pipeline/config | corte t | metadata | F27 | MODELO Y DATOS | `SIVIGILA dengue clásico` | DERIVABLE BACKEND | data_version |
| `data_sources[].category` | Rol de fuente | Rol funcional de cada dataset. | fuentes | enum | — | Sí / No | `epidemiological_target`,`epidemiological_predictor`,`climate` | catálogo | transversal | mapping fuente→rol | F27 | MODELO Y DATOS | `epidemiological_target` | CONFIGURACIÓN | data_version |
| `data_sources[].cutoff_month` | Corte de fuente | Último mes utilizado de esa fuente. | fuentes | string | `YYYY-MM` | Sí / No | ≤ reference_month | pipeline | t | máximo periodo válido | F03, F04, F27 | MODELO Y DATOS | `2024-12` | PARCIAL | data_version |
| `data_sources[].version` | Versión de fuente | Revisión/hash del artefacto de datos. | fuentes | string | hash/rev | No / Sí | versión | DVC | histórico | metadata | F26, F27 | MODELO Y DATOS | `abc123` | PENDIENTE/PARCIAL | DVC |

---

## 14. Diccionario — Insights y apoyo a decisión

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `insights[].priority` | Prioridad insight | Ordena los mensajes más importantes para el analista. | decisión | integer/enum | — | No / No | 1..3 | backend reglas | actual/T+1/T+2 | reglas versionadas | F20 | PANTALLA PRINCIPAL | `1` | PENDIENTE | rule_version |
| `insights[].title` | Título insight | Resumen corto del hallazgo. | decisión | string | texto | No / No | máximo definido | backend reglas | actual/T+1/T+2 | derivado de outputs reales | F20 | PANTALLA PRINCIPAL | `Riesgo T+2 elevado` | PENDIENTE | request_id + rule_version |
| `insights[].detail` | Detalle insight | Explicación breve y verificable del hallazgo. | decisión | string | texto | No / No | — | backend reglas | actual/T+1/T+2 | reglas + datos | F20 | PANTALLA PRINCIPAL | `La señal T+2 supera el threshold...` | PENDIENTE | request_id |
| `decision_support.alert_level` | Nivel de apoyo | Clasificación no prescriptiva para priorizar revisión. | decisión | enum | — | No / Sí | catálogo validado | backend reglas | T+1/T+2 | política validada | F21, F22 | PANTALLA PRINCIPAL | `VIGILANCIA` | PENDIENTE | policy_version |
| `decision_support.action_code` | Código de acción | Código estable para la recomendación mostrada. | decisión | string | — | No / Sí | catálogo | backend reglas | T+1/T+2 | política validada | F21 | PANTALLA PRINCIPAL | `REVIEW_AND_MONITOR` | PENDIENTE | policy_version |
| `decision_support.recommended_action` | Orientación de acción | Texto no prescriptivo de apoyo al análisis. | decisión | string | texto | No / Sí | contenido validado | backend/reglas | T+1/T+2 | catálogo de acciones | F21 | PANTALLA PRINCIPAL | `Revisar evolución epidemiológica...` | PENDIENTE | policy_version |
| `decision_support.disclaimer` | Descargo académico | Aclara límites del prototipo. | decisión | string | texto | Sí / No | texto aprobado | configuración | transversal | constante versionada | F21, F22 | PANTALLA PRINCIPAL | `Prototipo académico...` | CONFIGURACIÓN | schema_version |

---

## 15. Diccionario — Estados técnicos del frontend/API

| JSON path / campo | Nombre funcional | Semántica | Grupo | Tipo | Unidad / formato | Oblig. / nullable | Valores / rango | Origen | Horizonte / corte | Regla de cálculo | Funcionalidades | Módulo | Ejemplo | Disponibilidad | Trazabilidad |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `health.status` | Estado API | Disponibilidad general del servicio. | técnico | enum | — | Sí / No | `ok`,`degraded` | FastAPI | actual | health check | F28, F29 | MODELO Y DATOS | `ok` | DERIVABLE BACKEND | service version |
| `health.model_ready` | Modelo listo | Indica si los champions necesarios pueden cargar/inferir. | técnico | boolean | — | Sí / No | true/false | FastAPI/MLflow | actual | validación startup | F28, F29 | MODELO Y DATOS | `true` | DERIVABLE BACKEND | model registry |
| `error.code` | Código de error | Identificador estable de error para UI. | técnico | string | — | condicional / No | catálogo | FastAPI | transversal | excepción controlada | F29 | TRANSVERSAL | `INSUFFICIENT_DATA` | DERIVABLE BACKEND | request_id |
| `error.message` | Mensaje de error | Mensaje seguro y comprensible para UI/logs. | técnico | string | texto | condicional / No | — | FastAPI | transversal | manejo errores | F29 | TRANSVERSAL | `No hay datos suficientes...` | DERIVABLE BACKEND | request_id |
| `error.details` | Detalle error | Datos técnicos no sensibles que permiten resolver el problema. | técnico | object | JSON | condicional / Sí | — | FastAPI | transversal | manejo errores | F29 | TRANSVERSAL | `null` | DERIVABLE BACKEND | request_id |

---

## 16. Campos no provenientes directamente del modelo

Varias funcionalidades del dashboard requieren información que **no debe considerarse salida del champion**:

- F04 calidad/frescura: pipeline y reglas de calidad;
- F13 histórico/canal: SIVIGILA + feature/canal pipeline;
- F20 insights: reglas backend sobre outputs reales;
- F21 orientación de acción: política validada por equipo/experto;
- F23/F24 historial operacional: persistencia de inferencias + observados posteriores;
- F26/F27 trazabilidad/fuentes: MLflow, DVC y metadata;
- F29 estados de error: FastAPI/frontend;
- F30 última inferencia: servidor/API;
- F31 exportación: servicio de reporte/frontend;
- F32 accesibilidad: frontend.

El API puede consolidar estos datos en una misma respuesta aunque provengan de subsistemas distintos.

## 17. Mapeo de cobertura de las 33 funcionalidades

| Funcionalidad | Insumos principales del diccionario | Módulo |
|---|---|---|
| F01 | target, municipality, generated_at, horizons | PANTALLA PRINCIPAL |
| F02 | municipality.* | PANTALLA PRINCIPAL |
| F03 | reference_month, last_observed_month, data_sources.cutoff_month | PANTALLA PRINCIPAL |
| F04 | data_quality.*, data_sources.* | MODELO Y DATOS |
| F05 | predictions.horizon/target_month/label | PANTALLA PRINCIPAL |
| F06 | model_output.* | PANTALLA PRINCIPAL |
| F07 | uncertainty | PANTALLA PRINCIPAL |
| F08 | predictions T+1 + T+2 | PANTALLA PRINCIPAL |
| F09 | decision_rule.* | PANTALLA PRINCIPAL |
| F10 | current_status.observed_cases/p75/ratio_to_p75 | PANTALLA PRINCIPAL |
| F11 | current_status.p25/p50/p75/endemic_zone | PANTALLA PRINCIPAL |
| F12 | forecasts[] + predictions[] | PANTALLA PRINCIPAL |
| F13 | history[] | PANTALLA PRINCIPAL |
| F14 | reference_month + history.month + target_month | PANTALLA PRINCIPAL |
| F15 | model_output real; ausencia de cálculo frontend | PANTALLA PRINCIPAL |
| F16 | model_output + decision_rule por H/ciudad | PANTALLA PRINCIPAL |
| F17 | explanation.* + top_features.* | PANTALLA PRINCIPAL |
| F18 | top_features group epidemiological | PANTALLA PRINCIPAL |
| F19 | top_features group climate | PANTALLA PRINCIPAL |
| F20 | insights[] + predictions/explanation | PANTALLA PRINCIPAL |
| F21 | decision_support.* | PANTALLA PRINCIPAL |
| F22 | label + current_status.endemic_zone + decision_support | PANTALLA PRINCIPAL |
| F23 | prediction_history[] | HISTÓRICO Y EVALUACIÓN |
| F24 | prediction_history.label/observed_label/outcome_type | HISTÓRICO Y EVALUACIÓN |
| F25 | evaluation.* | MODELO Y DATOS |
| F26 | models.* + request_id + data_version | MODELO Y DATOS |
| F27 | target_definition + data_sources[] | MODELO Y DATOS |
| F28 | schema_version + health + models + errors | MODELO Y DATOS |
| F29 | health + error + data_quality.warnings | PANTALLA PRINCIPAL |
| F30 | generated_at + request_id | PANTALLA PRINCIPAL |
| F31 | todos los campos de snapshot + trazabilidad | PANTALLA PRINCIPAL |
| F32 | no requiere nuevo dato; semántica de labels/estados debe ser explícita | PANTALLA PRINCIPAL |
| F33 | municipality_codes + reference_month + horizons | PANTALLA PRINCIPAL |

## 18. Brechas de datos identificadas frente a PR #12

Bajo el supuesto de que las predicciones del champion fueron calculadas correctamente, PR #12 aporta una base fuerte para predicción, probabilidades, thresholds, SHAP, métricas, historial de backtesting y MLflow. Para cerrar el contrato funcional completo todavía deben consolidarse o producirse principalmente:

1. `data_quality.*` y reglas de frescura/completitud;
2. P50 canónico del canal, si no queda materializado en el dataset final;
3. método válido de `uncertainty`, si se decide mantener F07;
4. persistencia operacional de `prediction_history` más allá del backtesting;
5. metadata DVC/data_version completa;
6. reglas validadas de `insights` y `decision_support`;
7. catálogo/versionamiento estable de reglas, features y thresholds;
8. endpoints FastAPI que consoliden los campos anteriores.

## 19. Regla de gobierno del diccionario

Un campo nuevo o modificado debe actualizar simultáneamente, cuando corresponda:

1. este diccionario;
2. `API-sign.md` si cambia request/response;
3. `plan.md` si cambia una funcionalidad o su módulo;
4. schemas Pydantic/FastAPI;
5. tipos/adaptadores del dashboard;
6. pruebas de contrato.

Nunca se debe modificar la semántica de un campo existente sin versionar el contrato.