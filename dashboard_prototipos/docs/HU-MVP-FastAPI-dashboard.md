# HU MVP — FastAPI para habilitar la pantalla principal de BIOMAC

**ID:** HU-API-MVP-01  
**Estado:** PROPUESTA  
**Prioridad:** ALTA  
**Tipo:** Backend / Integración  
**Módulo:** Pantalla principal — Alerta y pronóstico  
**Dependencias:** PR #12, `API-sign.md`, `plan.md`, `diccionario-de-datos.md`  

## 1. Historia de usuario

**Como** analista que consulta el sistema BIOMAC,  
**quiero** que la pantalla principal del dashboard consuma una API FastAPI alimentada con las salidas reales ya disponibles del pipeline/modelo,  
**para** visualizar predicciones T+1/T+2, estado epidemiológico, canal endémico y explicaciones sin depender de mocks ni cálculos inventados en el frontend.

## 2. Objetivo MVP

Implementar la primera integración real **Dashboard → FastAPI → salidas precomputadas/modeladas de PR #12**.

El MVP no busca construir todavía una plataforma completa de inferencia productiva. Su objetivo es poner en funcionamiento la pantalla principal actual usando artefactos y datasets ya generados por el pipeline.

La API será la fuente de verdad para clase, probabilidad, threshold, meses objetivo, estado frente al canal, histórico y SHAP disponible. El frontend únicamente presentará la respuesta.

## 3. Fuentes de verdad

La implementación debe respetar, en este orden:

1. `dashboard_prototipos/docs/API-sign.md`: contrato técnico Dashboard ↔ FastAPI.
2. `dashboard_prototipos/docs/diccionario-de-datos.md`: semántica, tipos, origen y consumidores de cada dato.
3. `dashboard_prototipos/docs/plan.md`: funcionalidades, ubicación visual y alcance del dashboard.
4. PR #12 (`feat/dashboard-sat-dengue`): artefactos, predicciones, métricas, SHAP y datasets disponibles.

Ante una contradicción entre código frontend y estos documentos, no se debe preservar el mock: debe prevalecer el contrato/documentación vigente.

## 4. Decisión de arquitectura para el MVP

Se implementará inicialmente una **Snapshot API**.

```text
Dashboard React
      |
      | POST /api/v1/predictions
      v
FastAPI
      |
      +--> prediction_history / outputs T+1-T+2
      +--> features_mensual / canal e histórico
      +--> SHAP local T+1-T+2
      +--> metadata modelo / threshold
      |
      v
Response compatible con API-sign.md
```

FastAPI no debe reentrenar modelos ni reconstruir experimentos. Para esta HU consumirá las salidas ya materializadas de PR #12. Una HU posterior podrá reemplazar el acceso a snapshots por inferencia online contra los champions registrados en MLflow sin modificar el contrato del dashboard.

## 5. Insumos de PR #12 a reutilizar

Los nombres concretos deben validarse contra el HEAD que finalmente se integre, pero el MVP debe reutilizar las siguientes categorías de salida ya creadas por PR #12:

| Insumo | Uso en FastAPI |
|---|---|
| Predicciones T+1/T+2 | `label`, `probability`, `target_month`, `reference_month` |
| Threshold por horizonte | Regla de decisión mostrada por el dashboard |
| `prediction_history.parquet` o equivalente | Consulta por ciudad, corte e horizonte |
| `features_mensual.parquet` | Casos observados, canal, histórico y features de contexto |
| SHAP local T+1/T+2 | Explicación de una inferencia concreta |
| Metadata/artefactos del modelo | Modelo, versión, horizonte, calibración y trazabilidad básica |
| Métricas registradas | Disponibles para futuras vistas; no son foco visual del MVP |

No se deben volver a crear probabilidades, SHAP, thresholds o conteos futuros en React.

## 6. Alcance funcional del MVP

Esta HU tiene como meta **activar con datos reales los componentes que ya existen gráficamente en la pantalla principal**, no implementar las 33 funcionalidades completas.

| Funcionalidad `plan.md` | Alcance en esta HU | Resultado esperado |
|---|---|---|
| F01 Encabezado operacional | PARCIAL | API entrega `generated_at`, `reference_month` y target vigente. |
| F02 Selector de ciudad | SÍ | Una misma respuesta puede incluir Bucaramanga y Cali. |
| F05 Alerta principal T+2 | SÍ | Clase real `EXCESO/NO_EXCESO`. |
| F06 Señal cuantitativa T+2 | SÍ | Probabilidad real/calibrada disponible en PR #12. |
| F08 Evolución T+1→T+2 | SÍ | T+1 y T+2 en la misma consulta. |
| F09 Threshold real | SÍ | Threshold viene del artefacto/salida, nunca hardcodeado en frontend. |
| F10 Estado frente al canal | SÍ | Casos actuales, P75 y relación frente a P75. |
| F11 Clasificación actual | SÍ/PARCIAL | Zona disponible según datos existentes. |
| F12 Comparativo de ciudades | SÍ | Bucaramanga y Cali en el response. |
| F13 Histórico + canal | PARCIAL | Observados + P25/P75; P50 será nullable si PR #12 no lo materializa. |
| F14 Observado vs futuro | SÍ | API diferencia historia de meses objetivo T+1/T+2. |
| F15 Eliminar proyección artificial | SÍ | Se elimina del frontend el cálculo de casos proyectados basado en probabilidad. |
| F16 Comparativa de riesgo | SÍ | Probabilidad T+1/T+2 por ciudad. |
| F17 Explicabilidad local | SÍ | SHAP local por ciudad + corte + horizonte cuando exista. |
| F18 Impulsores epidemiológicos | SÍ | Top SHAP epidemiológicos. |
| F19 Impulsores climáticos | SÍ | Solo si aparecen realmente entre las contribuciones SHAP. |
| F20 Insights priorizados | PARCIAL | Pueden construirse reglas simples desde datos reales; no usar mocks. |
| F21 Orientación de acción | PARCIAL | Solo mensaje no prescriptivo/prototipo, separado del modelo. |
| F22 Semántica de alerta | SÍ | Frontend utiliza clase/threshold reales. |
| F29 Loading/error/empty/retry | SÍ | Integración debe implementar estados explícitos. |
| F30 Última inferencia | SÍ | `generated_at` diferenciado de `reference_month`. |
| F32 Responsive/accesibilidad | NO CAMBIO | No debe degradarse la implementación actual. |

## 7. Fuera de alcance

Quedan fuera de esta HU:

- inferencia online/reentrenamiento bajo demanda;
- carga mensual de nuevos archivos por el analista;
- persistencia productiva en base de datos;
- autenticación de usuarios;
- módulo `Histórico y evaluación` completo (F23/F24);
- módulo `Modelo y datos` completo (F04/F25/F26/F27/F28 visual);
- exportación PDF/CSV (F31);
- selector histórico completo F33 para cualquier mes arbitrario;
- generación de intervalos de incertidumbre si PR #12 no los produce;
- decisiones sanitarias prescriptivas.

## 8. Endpoints mínimos

### `GET /api/v1/health`

Debe indicar como mínimo:

```json
{
  "status": "ok",
  "service": "biomac-api",
  "api_version": "1.1.0",
  "model_ready": true
}
```

`model_ready=true` significa que los artefactos/snapshots requeridos para responder predicciones están cargados y disponibles.

### `POST /api/v1/predictions`

Request mínimo:

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

El response debe seguir `API-sign.md`. Para el MVP deben poblarse obligatoriamente las secciones que alimentan la pantalla principal: metadata raíz, municipio, estado actual, predicciones T+1/T+2, regla de decisión, histórico y explicación cuando exista.

## 9. Reglas de integración

1. `casos_clasico` es el target vigente y `casos_grave` predictor; no se suman.
2. La API solo sirve Bucaramanga (`68001`) y Cali (`76001`) en esta fase.
3. El frontend no puede usar `0.50` como threshold fijo: utiliza el valor recibido.
4. `probability` solo se presenta como porcentaje cuando la salida usada por el champion corresponde a probabilidad válida/calibrada.
5. `confidence_interval`/`uncertainty` será `null` si no existe cálculo real.
6. SHAP se devuelve únicamente cuando exista la fila local que corresponda a municipio + corte + horizonte.
7. Si falta SHAP, histórico o P50, la API usa `null`/lista vacía conforme al contrato; nunca inventa valores.
8. No se crean casos futuros multiplicando casos observados por una probabilidad.
9. `generated_at` representa ejecución/materialización de la predicción; `reference_month` representa el corte epidemiológico.
10. Errores de archivos, ciudad, corte o artefactos deben producir errores controlados y observables.

## 10. Criterios de aceptación

### CA01 — Servicio disponible

**Dado** que los artefactos requeridos existen,  
**cuando** se consulta `GET /api/v1/health`,  
**entonces** responde HTTP 200 con `status=ok` y `model_ready=true`.

### CA02 — Consulta Bucaramanga

**Dado** un `reference_month` disponible para Bucaramanga,  
**cuando** se solicita T+1 y T+2,  
**entonces** la API retorna ambos horizontes con `target_month`, `label`, `probability` cuando aplique y threshold real.

### CA03 — Consulta Cali

Mismo comportamiento de CA02 para DIVIPOLA `76001`.

### CA04 — Comparación de ciudades

**Cuando** se solicitan `68001` y `76001`,  
**entonces** una única respuesta contiene los resultados necesarios para poblar `CityComparisonTable` y `ForecastProbabilityChart`.

### CA05 — Canal e histórico

**Entonces** cada ciudad incluye historia observada y canal disponible para alimentar `HistoricalSeriesChart`; campos no materializados, como P50 si continúa ausente, deben ser `null` y la UI debe ocultarlos sin fallar.

### CA06 — SHAP local

**Dado** que existe SHAP local para la inferencia,  
**entonces** la API devuelve `explanation.method="shap"`, `scope="local"` y top features asociados al corte/horizonte exactos.

### CA07 — Sin cálculos epidemiológicos en React

Se elimina del frontend cualquier cálculo de:

- casos futuros artificiales;
- threshold fijo 50%;
- clase `EXCESO/NO_EXCESO`;
- SHAP/importancia simulada.

### CA08 — Manejo de ausencia de datos

Un corte/municipio sin datos suficientes no activa mocks. La API devuelve error controlado o campos nulos conforme a `API-sign.md`; el dashboard muestra estado `error` o `empty` y opción de reintento.

### CA09 — Compatibilidad del repositorio frontend

Se crea `HttpDengueRepository` (o equivalente) implementando la interfaz existente de acceso a datos. El cambio `MockDengueRepository → HttpDengueRepository` no requiere reescribir los componentes visuales.

### CA10 — Contrato validado

Los schemas Pydantic del endpoint corresponden con `API-sign.md`/`diccionario-de-datos.md`, rechazan campos desconocidos y generan OpenAPI automáticamente.

### CA11 — Pruebas

Existen pruebas automatizadas mínimas para:

- health 200;
- request válido Bucaramanga;
- request válido Cali;
- ambas ciudades;
- T+1/T+2;
- corte no disponible;
- municipio no soportado;
- artefacto faltante;
- respuesta sin explicación disponible;
- esquema de respuesta.

### CA12 — Seguridad mínima

CORS está restringido al origen configurado del dashboard y localhost/desarrollo; no se exponen rutas internas, secretos, stack traces ni archivos del servidor.

## 11. Estructura sugerida

```text
api/
├── app/
│   ├── main.py
│   ├── api/v1/
│   │   ├── health.py
│   │   └── predictions.py
│   ├── schemas/
│   │   ├── request.py
│   │   ├── response.py
│   │   └── errors.py
│   ├── repositories/
│   │   ├── prediction_repository.py
│   │   ├── epidemiology_repository.py
│   │   └── shap_repository.py
│   ├── services/
│   │   └── dashboard_service.py
│   └── core/
│       └── config.py
└── tests/
```

La ruta debe limitarse a validar/delegar/serializar. La lectura de parquet/model metadata no debe implementarse directamente dentro del controlador.

## 12. Tareas técnicas sugeridas

| # | Tarea | Resultado |
|---|---|---|
| T01 | Crear paquete FastAPI y configuración | Aplicación ejecutable localmente. |
| T02 | Implementar schemas Pydantic | Contrato v1.1.0 validado. |
| T03 | Implementar repositories para outputs PR12 | Lectura encapsulada de prediction/history/features/SHAP. |
| T04 | Implementar `DashboardService` | Ensambla response sin lógica visual. |
| T05 | Crear `/health` | Readiness verificable. |
| T06 | Crear `/predictions` | Respuesta para una/dos ciudades y T+1/T+2. |
| T07 | Implementar errores controlados | 400/422/500/503 según contrato. |
| T08 | Configurar CORS/env | Orígenes y paths configurables. |
| T09 | Crear pruebas FastAPI | Criterios CA01–CA12 cubiertos. |
| T10 | Crear `HttpDengueRepository` en dashboard | Sustituye mocks por API. |
| T11 | Retirar proyección artificial/threshold hardcodeado | Frontend solo presenta backend. |
| T12 | Implementar loading/error/empty/retry | F29 operativo. |
| T13 | Documentar ejecución local | README/comandos reproducibles. |

## 13. Definición de terminado (DoD)

La HU se considera terminada cuando:

- FastAPI inicia de forma reproducible en local.
- Swagger/OpenAPI expone `/api/v1/health` y `/api/v1/predictions`.
- Bucaramanga y Cali reciben resultados T+1/T+2 procedentes de salidas reales de PR #12.
- Los componentes actuales de la pantalla principal consumen `HttpDengueRepository` y dejan de depender de `MockDengueRepository` para el flujo normal.
- Alerta, probabilidad, threshold, canal, histórico y SHAP mostrados provienen de FastAPI.
- No existen casos futuros, probabilidades, thresholds ni SHAP fabricados en el frontend.
- Ausencias de datos producen estados explícitos, no fallback silencioso a mocks.
- Pruebas backend pasan.
- Build/tests focalizados del dashboard pasan.
- La implementación continúa compatible con `API-sign.md`, `diccionario-de-datos.md` y `plan.md`.

## 14. Evolución posterior

Este MVP debe permitir reemplazar internamente la estrategia:

```text
SnapshotRepository
        ↓
MLflowChampionInferenceRepository
```

sin modificar el contrato HTTP ni los componentes del dashboard. De esta forma, la siguiente etapa podrá ejecutar inferencia online con los champions T+1/T+2, incorporar nuevos cortes mensuales y persistir predicciones operacionales sin rehacer la integración frontend.
