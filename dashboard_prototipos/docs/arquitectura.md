# BIOMAC — Arquitectura de integración Dashboard ↔ Champion

**Estado:** arquitectura objetivo para implementación  
**Versión:** `1.1.1`  
**Ámbito:** desde la carga mensual de datos hasta la visualización de la predicción  
**Fuera de alcance:** entrenamiento, experimentación, selección, promoción o reemplazo del modelo Champion

## 1. Objetivo

Definir cómo BIOMAC convierte una nueva carga mensual en una predicción visible y trazable en el dashboard sin acoplar el frontend a la implementación concreta del modelo.

El sistema parte de un **Champion ya entrenado, evaluado y entregado como artefacto desplegable o salida materializada equivalente**. Este alcance no modifica el pipeline de entrenamiento ni decide cuál modelo es Champion.

La arquitectura se documenta en dos vistas complementarias:

1. **Arquitectura lógica:** responsabilidades, contratos y flujo entre componentes de software.
2. **Arquitectura física / deployment:** ubicación de ejecución de cada componente, conectividad, artefactos y dependencias de infraestructura.

---

# Parte A — Arquitectura lógica

## 2. Principio central

La predicción se ejecuta **cuando un analista carga un nuevo periodo mensual válido**. Abrir el dashboard o presionar `Refresh` **no ejecuta el modelo**: únicamente consulta la última predicción persistida.

```text
Carga mensual válida -> procesamiento de inferencia -> Champion -> validación contractual -> persistencia -> dashboard

Refresh / apertura del dashboard -> consulta de última predicción persistida
```

Una salida Champion no es persistible únicamente por ser estructuralmente válida. Antes de mapping/persistencia debe comprobarse que su `feature_contract_version` y `feature_contract_sha256` coinciden exactamente con los del input efectivo del mismo run.

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
          ┌──────────────────────────┐
          │ FeatureContractGate      │
          │ version + sha256 iguales │
          └────────────┬─────────────┘
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

`FeatureContractGate` representa una responsabilidad lógica; puede implementarse dentro de HU004/ChampionService sin requerir necesariamente una clase con ese nombre.

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
4. invoca/obtiene la salida del Champion;
5. exige compatibilidad del feature contract mediante HU004;
6. normaliza su salida;
7. persiste el resultado;
8. marca el run como `completed` o `failed`;
9. devuelve al API un resultado trazable.

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
- compatibilidad con el contrato de features vigente;
- preservación de `feature_contract_version` y `feature_contract_sha256` como metadata efectiva del input del run.

### 5.5 `ChampionAdapter` / `ChampionService`

Aísla al resto del producto del framework ML concreto.

Contrato conceptual:

```python
class ChampionAdapter:
    def metadata(self) -> ChampionMetadata: ...
    def predict(self, inference_input) -> ChampionOutput: ...
```

El adapter puede cargar un artefacto de MLflow, `joblib`, XGBoost u otro formato, o adaptar una salida materializada, siempre que respete el contrato acordado.

Responsabilidad adicional obligatoria:

```text
champion.feature_contract_version == input.feature_contract_version
champion.feature_contract_sha256   == input.feature_contract_sha256
```

Si cualquiera difiere, la operación falla de forma controlada antes de `ResultMapper`/persistencia. El dashboard y los endpoints nunca deben conocer `predict_proba`, `Booster`, rutas MLflow ni detalles del framework/provider.

### 5.6 `ResultMapper`

Convierte la salida nativa del Champion al contrato BIOMAC **solo después de superar el gate contractual**.

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
- feature contract version/hash del Champion aceptado;
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
  +--> cargar/obtener Champion versionado
  +--> ejecutar/consumir inferencia T+1/T+2
  +--> comparar feature contract input ↔ Champion
  +--> mapear salida
  +--> persistir snapshot
  |
  v
FastAPI responde run COMPLETED
  |
  v
Dashboard consulta/muestra última predicción
```

Si cualquier etapa falla, incluido un mismatch contractual, no se sustituye la predicción previa ni se presentan mocks. La última predicción exitosa continúa disponible y la nueva ejecución queda registrada como fallida.

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
MAPPING
READY_TO_PERSIST
PERSISTING
COMPLETED
FAILED
```

El gate contractual puede ejecutarse dentro de `PREPARING`/`INFERENCING` sin añadir un estado público nuevo. Un mismatch debe terminar en `FAILED` y mapearse a `CHAMPION_INPUT_INVALID` según `API-sign.md`.

### Persistencia local HU006

Para el Entregable 2, `MonthlyRunPersistenceService` consume el resultado `READY_TO_PERSIST` de HU005 y coordina una unidad de trabajo SQLite. El SQL queda encapsulado en `api/app/persistence/sqlite.py`; API y orquestación dependen de los puertos `RunRepository` y `PredictionRepository`. `COMPLETED` se escribe dentro de la misma transacción que el run y el snapshot, inmediatamente antes del commit. La ruta se obtiene de `BIOMAC_DB_PATH` y la implementación no requiere red ni nube.

### Consulta read-only HU007

Los tres GET contractuales siguen `FastAPI → QueryService → QueryRepository → SQLite → DTO`. El repositorio abre conexiones SQLite `mode=ro` y activa `PRAGMA query_only`; no inicia unidades de trabajo ni transacciones de escritura. Los servicios de consulta no importan `sqlite3`, Champion, adapters u orquestación de inferencia. Por ello Refresh funciona aunque el runtime Champion no esté configurado, siempre que la base de `BIOMAC_DB_PATH` exista.

### Integración frontend HU008

El dashboard obtiene server state mediante React Query y `HttpDengueRepository`. `VITE_BIOMAC_API_BASE_URL` es la única configuración de origen y contiene el base path `/api/v2`. La apertura y Refresh llaman únicamente `GET /predictions/latest`. La acción separada `Actualizar datos` envía `multipart/form-data` a `POST /monthly-runs` y, tras `COMPLETED`, invalida/refetchea `latest`. Errores de Refresh o upload conservan el snapshot previo en memoria.

## 10. Idempotencia y consistencia

Una carga debe identificarse mediante:

```text
reference_month + source_file_sha256 + champion_version
```

Reglas:
- el mismo archivo/periodo/Champion reutiliza o identifica el mismo resultado lógico;
- un archivo diferente para un periodo ya procesado debe producir conflicto controlado, no sobrescritura silenciosa;
- una ejecución fallida nunca reemplaza el último snapshot exitoso;
- cada predicción debe señalar exactamente qué Champion la generó;
- un resultado con feature contract distinto al input del run nunca es elegible para `COMPLETED`, independientemente de la idempotencia.

## 11. Frontera con MLOps/modelado

### Dentro de alcance
- obtener/cargar el artefacto Champion aprobado o salida materializada;
- conocer su versión y contrato de features;
- preparar entradas de inferencia;
- ejecutar/consumir inferencia;
- comparar el contrato efectivo del input con el declarado por el Champion;
- interpretar la salida según metadata/regla entregada;
- persistir y exponer los resultados compatibles.

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

Si el equipo de modelado entrega únicamente **salidas materializadas** y no un artefacto ejecutable, `ChampionAdapter` deberá implementar un `MaterializedOutputAdapter`; el resto de la arquitectura no cambia. El modo materializado sigue sujeto al mismo gate de feature contract.

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

## 13. Decisiones arquitectónicas lógicas

1. **Trigger por carga mensual**, no por refresh.
2. **Champion preexistente** como dependencia externa del alcance.
3. **FastAPI + application service**, sin crear microservicios adicionales para el MVP.
4. **Persistir antes de mostrar** para tener trazabilidad e historial.
5. **Frontend pasivo epidemiológicamente**: presenta, no calcula.
6. **Adapter de Champion** para evitar acoplamiento con XGBoost/MLflow/u otro framework.
7. **Repositorio abstracto** para cambiar almacenamiento sin afectar API/UI.
8. **No sobrescribir resultados exitosos con fallos**.
9. **Contrato versionado** para permitir evolución independiente del Champion y el dashboard.
10. **Feature contract gate obligatorio** antes de mapping/persistencia para impedir combinar entradas y predicciones de contratos distintos.

---

# Parte B — Arquitectura física / deployment

## 14. Objetivo de deployment

Definir dónde se ejecuta físicamente cada componente del MVP académico y cómo se comunican, aplicando de forma directa los patrones practicados en los talleres de Git/GitHub, DVC/S3, MLflow, empaquetamiento de modelos y APIs sobre AWS EC2.

La arquitectura física del MVP prioriza simplicidad operativa, trazabilidad, reproducibilidad y bajo número de componentes desplegados.

## 15. Topología física del MVP

```text
┌──────────────────────────────────────────────┐
│ Lovable Cloud                               │
│ Dashboard BIOMAC React                      │
│ - UI / upload CSV / consulta resultados     │
│ - NO modelo / NO lógica epidemiológica      │
└──────────────────────┬───────────────────────┘
                       │ HTTPS + JSON / multipart
                       v
┌──────────────────────────────────────────────┐
│ AWS EC2 — servidor BIOMAC                   │
│ Ubuntu + entorno Python                     │
│                                              │
│ FastAPI / Uvicorn                           │
│ Backend BIOMAC                              │
│ ChampionAdapter + feature contract gate     │
│ Champion T+1 / T+2                          │
│ Persistencia MVP local estructurada         │
└──────────────────────┬───────────────────────┘
                       │ deployment controlado
                       v
┌──────────────────────────────────────────────┐
│ AWS S3 + DVC                                 │
│ datasets y artefactos versionados            │
└──────────────────────────────────────────────┘

GitHub: código, contratos, PR y metadata DVC
MLflow: experimentación/metadata; fuera del camino crítico HTTP
```

## 16. Ubicación de cada componente

| Componente | Ubicación física MVP | Responsabilidad |
|---|---|---|
| Dashboard BIOMAC | Lovable Cloud | frontend React y experiencia de usuario |
| FastAPI | AWS EC2 | frontera HTTP pública del backend |
| Backend BIOMAC | misma AWS EC2 que FastAPI | validación, preparación, orquestación, mapping y persistencia |
| ChampionAdapter | misma AWS EC2 | aislar carga/invocación del modelo y validar compatibilidad contractual |
| Champion T+1/T+2 | entorno Python de la EC2 o salida materializada configurada | inferencia/salida detrás de HU004 |
| Persistencia runtime MVP | almacenamiento local estructurado en EC2 detrás de repositorio abstracto | runs/snapshots para latest/history |
| DVC remote | AWS S3 | versionamiento de datasets y artefactos pesados |
| Git | GitHub | código, contratos, metadata DVC y colaboración vía PR |
| MLflow | entorno académico existente | experimentos y metadata; no serving HTTP del dashboard |

## 17. Comunicación Lovable → FastAPI

Lovable no ejecuta Python ni accede al modelo directamente. El frontend consume una URL pública configurable del backend, por ejemplo:

```text
BIOMAC_API_BASE_URL=https://<host-api-biomac>/api/v2
```

La base URL debe configurarse por ambiente y no hardcodearse en componentes React.

```text
Lovable
  ├── GET  {API_BASE_URL}/health
  ├── POST {API_BASE_URL}/monthly-runs
  ├── GET  {API_BASE_URL}/predictions/latest
  ├── GET  {API_BASE_URL}/predictions/history
  └── GET  {API_BASE_URL}/runs/{run_id}
```

Las consultas/respuestas usan JSON. La carga mensual usa `multipart/form-data`.

## 18. Exposición de FastAPI en EC2

FastAPI se ejecuta mediante Uvicorn en la instancia EC2. Para el entorno académico puede escuchar en un puerto configurable, siguiendo el patrón del Taller de APIs.

Ejemplo conceptual:

```text
Uvicorn: 0.0.0.0:8001
```

Reglas:
- puerto configurable por ambiente;
- Security Group abre solo puertos necesarios;
- `/api/v2/health` permite comprobar disponibilidad;
- el frontend usa la URL pública configurada, no la IP privada.

### 18.1 HTTPS

El contrato objetivo entre Lovable y FastAPI es **HTTPS**.

Para una demo académica temporal puede existir HTTP directo a EC2 si la infraestructura disponible no permite TLS a tiempo; se considera excepción temporal, no arquitectura objetivo.

Evolución preferida:

```text
Lovable
   ↓ HTTPS :443
Dominio / reverse proxy
   ↓ HTTP interno
Uvicorn / FastAPI
```

## 19. CORS

FastAPI mantiene una allowlist explícita de orígenes. Debe incluir como mínimo:
- dominio productivo/preview de BIOMAC en Lovable;
- localhost únicamente en desarrollo cuando sea necesario.

Ejemplo conceptual:

```text
https://dengue-watch-pro.lovable.app
http://localhost:5173
```

Reglas:
- no usar `*` en producción;
- habilitar solo métodos/headers requeridos;
- CORS no reemplaza autenticación/autorización.

## 20. Ubicación e instalación del Champion

Para el MVP, HU004 se ejecuta **en la misma EC2 que FastAPI/backend**. El provider puede ser ejecutable o materializado.

```text
FastAPI
  ↓
MonthlyPredictionOrchestrator
  ↓
ChampionService
  ↓
provider ejecutable o materializado
  ↓
feature contract gate
  ↓
ChampionOutput
```

No existe un request HTTP adicional entre FastAPI y el Champion en el MVP.

### 20.1 Forma preferida de entrega del modelo

Orden de preferencia funcional:
1. salida materializada PR12 compatible para el MVP vigente;
2. paquete Python instalable `.whl` con método de inferencia estable;
3. artefacto versionado (`joblib`/pickle/XGBoost u otro) detrás del `ChampionAdapter`.

Cualquier forma debe declarar `feature_contract_version` y `feature_contract_sha256` y superar el gate antes de producir un snapshot exitoso.

## 21. DVC + S3

DVC y S3 se mantienen como mecanismo de versionamiento/reproducción de artefactos pesados.

Responsabilidades:
- GitHub versiona `.dvc`, configuración no sensible y código;
- S3 conserva objetos físicos versionados por DVC;
- `dvc pull` materializa en un entorno autorizado la versión correspondiente;
- uploads operacionales y predicciones runtime no se convierten automáticamente en datasets DVC.

Durante deployment puede ejecutarse explícitamente:

```text
git checkout <versión>
dvc pull
instalar/cargar Champion aprobado
iniciar FastAPI
```

El request normal de predicción **no debe ejecutar `dvc pull`**.

## 22. MLflow en la arquitectura física

MLflow conserva su función de experiment tracking y metadata del modelado.

Para el MVP:
- FastAPI no entrena modelos;
- un request HTTP no depende de la UI de MLflow;
- `ChampionAdapter` puede consumir metadata/artefactos MLflow en una evolución futura;
- mientras el Champion sea paquete/artefacto local o salida materializada versionada, MLflow permanece fuera del camino crítico de serving.

## 23. Deployment reproducible de EC2

Secuencia objetivo:

```text
1. provisionar EC2 Ubuntu
2. clonar repositorio GitHub
3. seleccionar versión/rama aprobada
4. crear/activar entorno virtual Python
5. instalar dependencias del API
6. materializar artefactos necesarios (`dvc pull`) cuando aplique
7. instalar/configurar Champion/version explícita
8. ejecutar pruebas de compatibilidad contractual
9. iniciar FastAPI/Uvicorn
10. verificar GET /api/v2/health
11. configurar Security Group / CORS / URL del frontend
12. ejecutar prueba Lovable → API → Champion
```

Tox puede incorporarse como runner reproducible de tests/ejecución siguiendo los talleres, sin ser requisito del dominio en runtime.

## 24. Seguridad y configuración de infraestructura

Variables/configuración de deployment permanecen fuera del código de dominio:
- URL/orígenes CORS;
- puerto Uvicorn;
- ruta/configuración del Champion;
- credenciales DVC/S3;
- environment (`local`, `test`, `demo`).

Reglas:
- credenciales AWS no se versionan en Git;
- secretos no viajan al frontend;
- Lovable nunca recibe credenciales AWS/DVC/MLflow;
- solo FastAPI queda expuesta públicamente;
- S3/DVC y artefactos permanecen detrás del backend/deployment.

## 25. Decisiones de infraestructura del MVP

1. **Lovable aloja únicamente el frontend.**
2. **AWS EC2 aloja FastAPI, backend y ChampionAdapter.**
3. **HU004 resuelve el provider Champion** sin exponerlo al frontend.
4. **Frontend ↔ backend usa HTTP(S)** y contratos `/api/v2`.
5. **HTTPS es el objetivo**; HTTP directo con IP/puerto solo es excepción temporal de demo.
6. **CORS usa allowlist explícita** del dominio Lovable.
7. **Champion debe declarar feature contract version/hash** independientemente del formato de entrega.
8. **DVC + S3 versionan datasets/artefactos pesados**, pero no se invocan en cada inferencia.
9. **MLflow queda fuera del camino crítico de serving** mientras el modelo sea local y aprobado.
10. **Persistencia local detrás de interfaz** es suficiente para MVP; puede migrar después.
11. **No se requiere separar API y model serving en dos servidores** para esta entrega.
12. **Ningún resultado con feature contract incompatible se persiste como exitoso.**

## 26. Evolución posterior al MVP

```text
MVP
Lovable → EC2(FastAPI + Champion + persistencia local)

Evolución posible
Lovable → HTTPS/API Gateway/ALB
                ↓
              API
                ↓
        model-serving separado
                ↓
        base de datos administrada
```

La separación futura se adopta solo ante necesidades reales de escalamiento, disponibilidad, seguridad o ciclos de despliegue independientes.

## 27. Criterio de arquitectura terminada

La arquitectura se considera implementada cuando un archivo mensual válido recorre:

```text
Dashboard Lovable
→ HTTP(S) API pública
→ FastAPI en AWS EC2/local académico
→ validación/preparación
→ Champion provider HU004
→ feature contract gate PASS
→ persistencia
→ API
→ Dashboard
```

y una posterior apertura o `Refresh` recupera la misma predicción persistida sin volver a ejecutar el modelo.

Además, debe ser posible reproducir el servidor desde una versión conocida de Git/DVC, configurar una versión explícita del Champion y verificar `/api/v2/health` antes de habilitar el dashboard.

---

## 28. Decisión arquitectónica vigente — providers intercambiables de HU004

Esta sección tiene precedencia sobre referencias anteriores que presenten la ejecución local directa del modelo como única estrategia del MVP.

### 28.1 Contrato interno estable

La arquitectura lógica queda fijada así:

```text
                ┌──────────────────────────────┐
MVP / Modo B →  │ MaterializedChampionProvider │
                └──────────────┬───────────────┘
                               │
                               v
                       ChampionService
                               │
                               v
                    FeatureContractGate
                               │
                               v
                        ChampionOutput
                               │
                               v
                         HU005 y siguientes
                               ^
                               │
                ┌──────────────┴───────────────┐
Futuro / A  →   │ ExecutableChampionProvider  │
                └──────────────────────────────┘
```

`ChampionService.produce(ChampionOperationalContext) → ChampionOutput` es la frontera estable entre integración ML y aplicación, pero su contrato exige que el output retornado ya haya superado la compatibilidad de feature contract.

### 28.2 Estrategia del MVP

Para el MVP se adopta **Modo B**:

```text
PR12 ChampionResult
→ MaterializedOutputAdapter
→ feature contract gate
→ ChampionOutput
```

PR #12 ya produce los campos requeridos por el dashboard; por ello no se requiere duplicar la ejecución del modelo para completar el MVP.

### 28.3 Evolución futura

Modo A puede incorporarse posteriormente:

```text
ChampionInput
→ ExecutableChampionAdapter
→ feature contract gate
→ ChampionOutput
```

Su incorporación debe limitarse a HU004 y al composition root/configuración. No debe requerir cambios estructurales en orquestación, repositorios, contratos HTTP ni frontend.

### 28.4 Estrategias, no fallback

Los dos adapters son **alternativas configurables**. No existe fallback automático entre ellos. Si el provider activo falla, la ejecución falla de forma observable; no se cambia de estrategia silenciosamente.

### 28.5 Regla para componentes posteriores

`MonthlyPredictionOrchestrator` debe depender solo de `ChampionService`, `ChampionOperationalContext` y `ChampionOutput`; los componentes posteriores consumen `ChampionOutput`. Queda prohibido acoplar HU005+ a:

- estructura concreta `ChampionResult` de PR #12;
- archivos JSON físicos;
- scripts de modelado;
- XGBoost/pickle;
- paquetes `.whl`;
- detalles del provider activo.

Esta regla es el mecanismo explícito para permitir una migración posterior B → A sin refactoring transversal.

## 29. Enrichments persistidos HU009

`ResultMapper` construye calidad/contexto desde el mismo `ValidatedMonthlyUpload`, solicita explicación a un provider configurado y persiste todo en la transacción del snapshot. Los GET leen exclusivamente SQLite. La estrategia operacional es `UnavailableExplanationProvider`: los parquets de PR12 no están materializados en esta rama. El provider opcional exige feature contract, municipio, mes y horizonte exactos y nunca genera SHAP ni actúa como fallback.

## 30. Frontera E2E local HU010

HU010 verifica el sistema mediante composición explícita de pruebas, sin alterar `app = create_app()` ni introducir demo fallback. La persistencia es SQLite real y el Champion atraviesa `ChampionService` materializado. Las consultas y Refresh no alcanzan el Champion. La validación cloud queda fuera del cierre local.

El cierre HU010 exige dos evidencias adicionales: happy path con feature contract idéntico y escenario mismatch que falle antes de persistencia exitosa.

## 31. Hallazgo PR #33 — razón del gate contractual

La prueba HTTP real ejecutó correctamente health, POST, latest, history y run detail y persistió cuatro predicciones. Sin embargo, comparó:

```text
Champion JSON
feature_contract_version = pr12-f5a2d39
feature_contract_sha256   = 3af245ede70851d1616439d80441e2ad6f5d3f6465b9798d6b67fed3adb3e3dc

CSV/API vigente
feature_contract_version = pr12-74e385c3
feature_contract_sha256   = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

La arquitectura anterior preservaba metadata, pero no imponía igualdad. Eso permite combinar una entrada validada con un contrato y una predicción declarada bajo otro. La presente versión corrige la regla arquitectónica: **preservar metadata no basta; debe verificarse compatibilidad antes de `COMPLETED`.**