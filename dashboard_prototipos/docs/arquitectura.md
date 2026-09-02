# BIOMAC — Arquitectura de integración Dashboard ↔ Champion

**Estado:** arquitectura objetivo para implementación  
**Versión:** `1.0.0`  
**Ámbito:** desde la carga mensual de datos hasta la visualización de la predicción  
**Fuera de alcance:** entrenamiento, experimentación, selección, promoción o reemplazo del modelo Champion

## 1. Objetivo

Definir cómo BIOMAC convierte una nueva carga mensual en una predicción visible y trazable en el dashboard sin acoplar el frontend a la implementación concreta del modelo.

El sistema parte de un **Champion ya entrenado, evaluado y entregado como artefacto desplegable**. Este alcance no modifica el pipeline de entrenamiento ni decide cuál modelo es Champion.

## 2. Principio central

La predicción se ejecuta **cuando un analista carga un nuevo periodo mensual válido**. Abrir el dashboard o presionar `Refresh` **no ejecuta el modelo**: únicamente consulta la última predicción persistida.

```text
Carga mensual válida -> procesamiento de inferencia -> Champion -> persistencia -> dashboard

Refresh / apertura del dashboard -> consulta de última predicción persistida
```

## 3. Actores

### Analista actualizador
Carga el archivo correspondiente al nuevo periodo y recibe el estado del procesamiento.

### Usuario consultor
Consulta alertas, T+1/T+2, canal endémico, explicación y trazabilidad. No necesita ejecutar el modelo.

### Equipo de modelado
Entrega el Champion y su contrato de entrada/salida. Entrenamiento y promoción permanecen fuera de esta arquitectura.

## 4. Componentes

```text
┌───────────────────────────────┐
│ Dashboard BIOMAC / Lovable    │
│ - consulta resultados         │
│ - carga archivo mensual       │
│ - muestra estado/errores      │
└───────────────┬───────────────┘
                │ HTTPS
                v
┌───────────────────────────────┐
│ FastAPI                       │
│ - endpoints                   │
│ - Pydantic                    │
│ - CORS / límites              │
└───────────────┬───────────────┘
                v
┌───────────────────────────────┐
│ MonthlyPredictionOrchestrator │
│ - coordina un run             │
│ - no contiene lógica ML       │
└───────┬──────────┬────────────┘
        │          │
        v          v
┌──────────────┐  ┌───────────────────┐
│ InputService │  │ ChampionAdapter   │
│ validación   │  │ carga/inferencia  │
│ preparación  │  │ contrato estable  │
└──────┬───────┘  └─────────┬─────────┘
       │                    │
       └──────────┬─────────┘
                  v
          ┌──────────────────┐
          │ ResultMapper     │
          │ normaliza salida │
          └────────┬─────────┘
                   v
          ┌──────────────────┐
          │ PredictionRepo   │
          │ snapshot/history │
          └────────┬─────────┘
                   v
          FastAPI -> Dashboard
```

## 5. Responsabilidades

### 5.1 Dashboard

Debe:
- permitir seleccionar y cargar el archivo mensual;
- mostrar progreso, éxito y errores controlados;
- consultar la última predicción al abrir o refrescar;
- presentar exclusivamente datos recibidos del backend.

No debe:
- construir features;
- ejecutar el Champion;
- calcular thresholds, clases o SHAP;
- inventar conteos/probabilidades;
- usar mocks como fallback silencioso.

### 5.2 FastAPI

Es la frontera HTTP. Valida request, archivo y parámetros, crea `request_id/run_id`, invoca el orquestador y transforma errores internos en respuestas estables.

No debe contener lógica de entrenamiento ni lógica epidemiológica dispersa en endpoints.

### 5.3 `MonthlyPredictionOrchestrator`

Coordina una ejecución mensual completa:
1. valida que el periodo sea procesable;
2. registra el inicio del run;
3. prepara las entradas de inferencia;
4. invoca el Champion;
5. normaliza su salida;
6. persiste el resultado;
7. marca el run como `completed` o `failed`;
8. devuelve al API un resultado trazable.

Debe ser idempotente por `reference_month + source_hash + champion_version`: una repetición idéntica no debe generar resultados contradictorios.

### 5.4 `InputService`

Su responsabilidad es producir **la entrada que el Champion necesita para inferencia** a partir de datos permitidos hasta el corte `t`.

Puede reutilizar transformaciones existentes del proyecto, pero solo las necesarias para inferencia. No entrena, ajusta ni selecciona modelos.

Debe validar:
- estructura y tipos;
- ciudades soportadas;
- periodo de referencia;
- completitud mínima;
- ausencia de información posterior a `t`;
- compatibilidad con el contrato de features del Champion.

### 5.5 `ChampionAdapter`

Aísla al resto del producto del framework ML concreto.

Contrato conceptual:

```python
class ChampionAdapter:
    def metadata(self) -> ChampionMetadata: ...
    def predict(self, inference_input) -> ChampionOutput: ...
```

El adapter puede cargar un artefacto de MLflow, `joblib`, XGBoost u otro formato, siempre que respete el contrato acordado.

El dashboard y los endpoints nunca deben conocer `predict_proba`, `Booster`, rutas MLflow ni detalles del framework.

### 5.6 `ResultMapper`

Convierte la salida nativa del Champion al contrato BIOMAC.

Solo puede exponer:
- clase `EXCESO/NO_EXCESO` si la regla está definida por el Champion/contrato;
- probabilidad si es una probabilidad válida;
- conteo esperado si el modelo realmente lo produce;
- threshold/regla versionada;
- explicación local únicamente cuando exista;
- metadata del Champion usado.

### 5.7 `PredictionRepository`

Persiste el resultado antes de considerarlo exitoso.

Mínimo por ejecución:
- `run_id`;
- `reference_month`;
- hash del archivo fuente;
- timestamps;
- estado del run;
- Champion nombre/versión/run_id;
- predicciones T+1/T+2;
- canal/estado actual necesarios para UI;
- calidad/advertencias;
- explicación disponible;
- errores si falla.

Para el MVP puede implementarse con almacenamiento local estructurado y una interfaz de repositorio que permita migrar posteriormente a una base de datos sin cambiar el dashboard.

## 6. Flujo principal — actualización mensual

```text
Analista
  |
  | selecciona archivo del nuevo mes
  v
Dashboard
  |
  | POST /api/v2/monthly-runs
  v
FastAPI
  |
  v
Orchestrator
  |
  +--> validar archivo/corte
  +--> preparar input del Champion
  +--> cargar Champion versionado
  +--> ejecutar inferencia T+1/T+2
  +--> mapear salida
  +--> persistir snapshot
  |
  v
FastAPI responde run COMPLETED
  |
  v
Dashboard consulta/muestra última predicción
```

Si cualquier etapa falla, no se sustituye la predicción previa ni se presentan mocks. La última predicción exitosa continúa disponible y la nueva ejecución queda registrada como fallida.

## 7. Flujo de consulta y Refresh

```text
Usuario abre dashboard / presiona Refresh
        |
        v
GET /api/v2/predictions/latest
        |
        v
PredictionRepository
        |
        v
Último snapshot COMPLETED
        |
        v
Dashboard
```

**Refresh es read-only.** No reconstruye features ni ejecuta el Champion.

## 8. Contratos API objetivo

### Salud
`GET /api/v2/health`

### Ejecutar actualización mensual
`POST /api/v2/monthly-runs`

`multipart/form-data`:
- `file`;
- `reference_month`;
- opcionalmente `force=false` solo para una futura operación administrativa. No se habilita en el MVP.

La respuesta se emite cuando finaliza el procesamiento del MVP. Si más adelante la duración exige procesamiento asíncrono, el contrato podrá evolucionar a `202 + polling` conservando `run_id`.

### Consultar un run
`GET /api/v2/runs/{run_id}`

### Consultar última predicción exitosa
`GET /api/v2/predictions/latest`

### Consultar historial
`GET /api/v2/predictions/history`

## 9. Estado de una ejecución

Estados permitidos:

```text
RECEIVED
VALIDATING
PREPARING
INFERENCING
PERSISTING
COMPLETED
FAILED
```

El dashboard puede mostrar el último estado conocido. En el MVP síncrono son especialmente útiles para trazabilidad y pruebas.

## 10. Idempotencia y consistencia

Una carga debe identificarse mediante:

```text
reference_month + source_file_sha256 + champion_version
```

Reglas:
- el mismo archivo/periodo/Champion reutiliza o identifica el mismo resultado lógico;
- un archivo diferente para un periodo ya procesado debe producir conflicto controlado, no sobrescritura silenciosa;
- una ejecución fallida nunca reemplaza el último snapshot exitoso;
- cada predicción debe señalar exactamente qué Champion la generó.

## 11. Frontera con MLOps/modelado

### Dentro de alcance
- obtener/cargar el artefacto Champion aprobado;
- conocer su versión y contrato de features;
- preparar entradas de inferencia;
- ejecutar inferencia;
- interpretar la salida según metadata/regla entregada;
- persistir y exponer los resultados.

### Fuera de alcance
- EDA;
- construcción de dataset de entrenamiento;
- entrenamiento o reentrenamiento;
- tuning;
- comparación de candidatos;
- evaluación para seleccionar Champion;
- registro/promoción del Champion;
- definición unilateral de threshold/calibración;
- modificación del algoritmo.

Si el equipo de modelado entrega únicamente **salidas materializadas** y no un artefacto ejecutable, `ChampionAdapter` deberá implementar un `MaterializedOutputAdapter`; el resto de la arquitectura no cambia.

## 12. Estructura técnica sugerida

```text
api/
├── app/
│   ├── main.py
│   ├── api/v2/
│   │   ├── health.py
│   │   ├── monthly_runs.py
│   │   ├── runs.py
│   │   └── predictions.py
│   ├── schemas/
│   │   ├── runs.py
│   │   ├── predictions.py
│   │   └── errors.py
│   ├── services/
│   │   ├── monthly_prediction_orchestrator.py
│   │   ├── input_service.py
│   │   └── result_mapper.py
│   ├── champion/
│   │   ├── port.py
│   │   └── adapter.py
│   ├── repositories/
│   │   ├── prediction_repository.py
│   │   └── run_repository.py
│   └── core/
│       └── config.py
└── tests/
```

## 13. Decisiones arquitectónicas

1. **Trigger por carga mensual**, no por refresh.
2. **Champion preexistente** como dependencia externa del alcance.
3. **FastAPI + application service**, sin crear microservicios adicionales para el MVP.
4. **Persistir antes de mostrar** para tener trazabilidad e historial.
5. **Frontend pasivo epidemiológicamente**: presenta, no calcula.
6. **Adapter de Champion** para evitar acoplamiento con XGBoost/MLflow/u otro framework.
7. **Repositorio abstracto** para cambiar almacenamiento sin afectar API/UI.
8. **No sobrescribir resultados exitosos con fallos**.
9. **Contrato versionado** para permitir evolución independiente del Champion y el dashboard.

## 14. Criterio de arquitectura terminada

La arquitectura se considera implementada cuando un archivo mensual válido puede recorrer el flujo completo:

```text
Dashboard -> API -> validación/preparación -> Champion -> persistencia -> API -> Dashboard
```

y una posterior apertura o acción `Refresh` recupera esa misma predicción persistida sin volver a ejecutar el modelo.