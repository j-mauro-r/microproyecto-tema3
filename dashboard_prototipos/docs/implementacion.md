# BIOMAC — Plan de implementación del flujo operativo de predicción

**Estado:** backlog objetivo  
**Versión:** `1.1.0`  
**Fuente arquitectónica:** `arquitectura.md`  
**Contrato API:** `API-sign.md`  

## 1. Alcance

Este plan implementa el flujo:

```text
analista carga archivo mensual
→ backend valida la carga
→ backend construye ChampionInput
→ ChampionAdapter ejecuta el Champion aprobado
→ se normaliza y persiste la salida
→ dashboard muestra el nuevo resultado
→ Refresh consulta el último resultado persistido
```

### Fuera de alcance

- entrenamiento/reentrenamiento;
- tuning;
- experimentación;
- comparación y selección de candidatos;
- promoción del Champion;
- cambios al algoritmo;
- definición de thresholds no entregados por el modelo/contrato;
- construcción operacional de features desde datos crudos durante esta entrega académica.

El equipo de dashboard/integración recibe un Champion aprobado o salidas materializadas compatibles.

### Decisión de alcance académico vigente

Para la entrega actual, el analista carga un CSV de un único mes **ya preparado con las features requeridas por el Champion**. El backend no calcula lags, rolling, canal endémico, SIR, estacionalidad ni otras features. Esa automatización se posterga a una HU posterior.

---

## 2. Arquitectura física de referencia para la implementación

La arquitectura lógica definida en `arquitectura.md` se despliega para el MVP de la siguiente forma:

```text
┌──────────────────────────────┐
│ Lovable                      │
│ Dashboard React BIOMAC       │
│ - upload mensual             │
│ - consulta latest/history    │
└──────────────┬───────────────┘
               │ HTTP(S) / JSON
               │ API_BASE_URL configurable
               v
┌─────────────────────────────────────────────┐
│ AWS EC2                                     │
│                                             │
│ FastAPI + Uvicorn                           │
│ ├─ HU001 contratos/API                      │
│ ├─ HU002 validación CSV                     │
│ ├─ HU003 ChampionInput                      │
│ ├─ HU004 ChampionAdapter                    │
│ ├─ HU005 orquestación                       │
│ ├─ HU006 persistencia                       │
│ └─ HU007 API read-only                      │
│                                             │
│ Champion T+1 / T+2                          │
│ - paquete `.whl` preferido o artefacto      │
│ - cargado detrás de ChampionAdapter         │
└──────────────┬──────────────────────────────┘
               │ deployment/materialización
               v
┌──────────────────────────────┐
│ DVC + AWS S3                 │
│ datasets / artefactos pesados│
└──────────────────────────────┘
```

### Reglas de deployment

- Lovable aloja únicamente el frontend; no ejecuta FastAPI ni el Champion.
- FastAPI/backend se despliega en AWS EC2.
- `ChampionAdapter` y Champion T+1/T+2 se ejecutan en la misma EC2 para el MVP.
- El frontend usa una `API_BASE_URL` configurable; no hardcodea IPs dentro de componentes.
- HTTPS es el objetivo. HTTP directo a IP/puerto solo se permite como excepción temporal de demo académica.
- FastAPI mantiene CORS con allowlist explícita del dominio Lovable y localhost de desarrollo.
- El Champion se entrega preferentemente como paquete instalable `.whl`, siguiendo el patrón trabajado en empaquetamiento; otros formatos quedan encapsulados por `ChampionAdapter`.
- DVC + S3 se usan para versionar/materializar datasets o artefactos pesados durante deployment. No debe ejecutarse `dvc pull` en cada request.
- MLflow conserva trazabilidad de experimentación/modelado, pero no forma parte del camino crítico de serving del MVP.
- La persistencia del MVP puede ser almacenamiento local estructurado detrás de interfaces de repositorio; podrá migrarse posteriormente a una base de datos sin modificar dashboard/API.

---

## 3. Orden de implementación

| Orden | HU | Nombre | Objetivo | Dependencias | Prioridad |
|---:|---|---|---|---|---|
| 1 | HU-INT-001 | Base FastAPI y contratos | Crear esqueleto API v2, configuración, health, schemas y errores comunes. | arquitectura/API | ALTA |
| 2 | HU-INT-002 | Carga mensual y validación | Recibir CSV mensual listo para inferencia y validar periodo, ciudades, contrato de features, tamaño y hash. | HU-INT-001 | ALTA |
| 3 | HU-INT-003 | Adaptación a ChampionInput | Seleccionar, ordenar y convertir las features ya preparadas al contrato exacto del Champion. | HU-INT-002 + contrato Champion | ALTA |
| 4 | HU-INT-004 | Adapter del Champion | Cargar/invocar el Champion aprobado y exponer metadata/output desacoplados del framework. | HU-INT-003 + artefacto Champion | ALTA |
| 5 | HU-INT-005 | Orquestación del run | Coordinar validación → preparación → inferencia → mapeo → persistencia con estados e idempotencia. | HU-INT-002/003/004 | ALTA |
| 6 | HU-INT-006 | Persistencia y trazabilidad | Guardar runs y snapshots exitosos/fallidos, manteniendo última predicción exitosa. | HU-INT-005 | ALTA |
| 7 | HU-INT-007 | API de consulta | Exponer latest, history y detalle de run sin ejecutar el modelo. | HU-INT-006 | ALTA |
| 8 | HU-INT-008 | Integración dashboard | Sustituir mocks, habilitar carga mensual, estados y Refresh read-only usando `API_BASE_URL`. | HU-INT-005/007 | ALTA |
| 9 | HU-INT-009 | Explicabilidad y metadata | Exponer threshold/regla, Champion, calidad, SHAP local/explicación solo cuando exista. | HU-INT-004/006 | MEDIA |
| 10 | HU-INT-010 | Pruebas E2E y cierre | Validar flujo completo y regresión de UI/contratos/deployment. | HU-INT-001..009 | ALTA |

---

# HU-INT-001 — Base FastAPI y contratos

**Como** equipo de integración  
**quiero** una API versionada y testeable  
**para** separar el dashboard de la lógica de inferencia.

## Alcance

- crear `api/app`;
- configuración por variables de entorno;
- `GET /api/v2/health`;
- schemas Pydantic de run, prediction y error;
- middleware de `request_id`;
- CORS configurable;
- manejo uniforme de excepciones;
- OpenAPI generado automáticamente.

## Consideraciones de deployment

- FastAPI debe poder ejecutarse con Uvicorn en EC2.
- CORS debe aceptar únicamente orígenes configurados; debe incluir el dominio real de Lovable en el ambiente de demo.
- secretos y configuración de infraestructura no se hardcodean en el repositorio.

## Criterios de aceptación

- CA01: health responde 200.
- CA02: campos desconocidos se rechazan donde aplique.
- CA03: errores no exponen stack trace ni rutas internas.
- CA04: configuración sensible no está versionada.
- CA05: pruebas básicas pasan en local.

---

# HU-INT-002 — Carga mensual lista para inferencia

**Como** analista actualizador  
**quiero** cargar el CSV del nuevo mes con features ya preparadas  
**para** iniciar una nueva predicción únicamente con datos compatibles con el Champion.

## Endpoint

`POST /api/v2/monthly-runs`

`multipart/form-data`:
- `file`;
- `reference_month`.

## Validaciones mínimas

- solo CSV UTF-8/UTF-8-SIG;
- tamaño máximo configurable;
- archivo no vacío;
- `reference_month` válido;
- exactamente Bucaramanga `68001` y Cali `76001`;
- una fila por municipio y un único mes;
- 39 features Champion presentes, numéricas, finitas y no nulas según contrato vigente;
- rechazo de columnas objetivo/futuras prohibidas como input efectivo;
- SHA-256 del archivo;
- no persistir el archivo dentro del repositorio Git.

## Criterios de aceptación

- CA01: archivo válido produce `ValidatedMonthlyUpload` reutilizable.
- CA02: archivo inválido produce error estable y comprensible.
- CA03: no se ejecuta el Champion si falla validación.
- CA04: se registra hash, nombre lógico, tamaño y periodo.
- CA05: no se construyen features ni se accede a modelos/cloud.

---

# HU-INT-003 — Adaptación mínima a `ChampionInput`

**Como** servicio de inferencia  
**quiero** convertir la carga mensual ya validada en la estructura exacta requerida por el Champion  
**para** ejecutar inferencia reproducible sin recalcular features ni reentrenar.

## Alcance vigente

Entrada:

```text
ValidatedMonthlyUpload
```

Salida:

```text
ChampionInput
```

Responsabilidades:

- usar exclusivamente la fuente centralizada `CHAMPION_FEATURES`;
- imponer orden municipal `68001`, `76001`;
- imponer el orden contractual exacto de las 39 features;
- convertir valores a representación numérica estable (`float`);
- preservar `reference_month`;
- preservar `source_file_sha256`;
- preservar `feature_contract_version` y `feature_contract_sha256`;
- excluir identificadores y targets de la matriz;
- bloquear inconsistencias con `CHAMPION_INPUT_INVALID` en etapa `PREPARING`.

## Restricción

HU003 **no realiza feature engineering**.

No puede:
- crear lags;
- crear rolling windows;
- calcular P25/P75;
- calcular canal/SIR/endemicidad;
- calcular `mes_sin`/`mes_cos`;
- imputar;
- escalar/normalizar;
- leer `features_mensual.parquet` en runtime;
- cargar o ejecutar el Champion.

La construcción automática desde datos crudos queda postergada para una HU futura.

## Criterios de aceptación

- CA01: la matriz coincide con el contrato del Champion.
- CA02: dimensión vigente 2 × 39.
- CA03: el orden del CSV no modifica el `ChampionInput` resultante.
- CA04: faltantes/no finitos/inconsistencias bloquean preparación.
- CA05: Bucaramanga y Cali se materializan siempre en orden contractual.
- CA06: salida inmutable y framework-agnostic.

---

# HU-INT-004 — Adapter del Champion

**Como** backend BIOMAC  
**quiero** consumir el Champion mediante una interfaz estable  
**para** evitar que API/dashboard dependan de XGBoost, MLflow, pickle u otro framework.

## Ubicación física para el MVP

`ChampionAdapter` y el Champion se ejecutan **dentro de la misma instancia AWS EC2 que FastAPI**.

No se crea un microservicio adicional para serving en esta fase.

```text
FastAPI / Orchestrator
        ↓
ChampionInput
        ↓
ChampionAdapter
        ↓
Champion T+1 / T+2 instalado/materializado en EC2
        ↓
ChampionOutput
```

## Contrato

```python
class ChampionAdapter:
    def metadata(self) -> ChampionMetadata: ...
    def predict(self, inference_input: ChampionInput) -> ChampionOutput: ...
```

## Fuente del Champion

Preferencia de deployment:

1. paquete Python versionado `.whl` instalable en el entorno de EC2;
2. artefacto `joblib`/pickle/XGBoost materializado durante deployment;
3. salida materializada equivalente mediante `MaterializedOutputAdapter` si el equipo de modelado no entrega artefacto ejecutable.

La estrategia elegida debe quedar detrás del adapter; FastAPI, orquestador y dashboard no conocen el mecanismo concreto.

DVC/S3 puede utilizarse para materializar el artefacto durante deployment, pero **no se consulta S3/DVC por cada predicción**.

MLflow puede aportar metadata/trazabilidad si existe, pero HU004 no depende de que el servidor MLflow esté disponible para cada request.

## Metadata mínima

- nombre;
- versión;
- horizontes soportados;
- identificador MLflow/run cuando exista;
- tipo de salida;
- threshold/regla de decisión real;
- `feature_contract_version`;
- `feature_contract_sha256`;
- fecha/hash del artefacto cuando aplique.

## Salida mínima

`ChampionOutput` debe representar únicamente datos producidos o respaldados por el Champion/contrato, por ejemplo:

- municipio/DIVIPOLA;
- horizonte `T+1`/`T+2`;
- `target_month`;
- salida nativa (`probability`, conteo o score según corresponda);
- clase solo cuando exista una regla/threshold contractual;
- threshold real cuando aplique;
- metadata del Champion.

No debe producir todavía el `PredictionSnapshot` final del dashboard; esa normalización pertenece a `ResultMapper`/HU005+.

## Criterios de aceptación

- CA01: el Champion se carga una vez por proceso cuando sea seguro hacerlo.
- CA02: T+1/T+2 se identifican explícitamente y no se inventa un horizonte ausente.
- CA03: `probability` solo existe si el Champion realmente la produce.
- CA04: no se inventa threshold por defecto; debe provenir del contrato/artefacto aprobado.
- CA05: error de carga produce `CHAMPION_NOT_READY`.
- CA06: incompatibilidad de feature contract bloquea inferencia.
- CA07: API/dashboard no importan tipos específicos del framework ML.
- CA08: si solo se reciben salidas materializadas, puede implementarse un adapter alterno sin cambiar endpoints/UI.
- CA09: ningún request ejecuta `dvc pull`, entrenamiento o acceso obligatorio a MLflow.
- CA10: existe prueba offline con `ChampionInput` de Bucaramanga/Cali y un fake/stub de Champion.

---

# HU-INT-005 — Orquestación del run mensual

**Como** analista  
**quiero** que una única carga coordine el proceso completo  
**para** obtener la nueva predicción sin ejecutar pasos manuales internos.

## Flujo

```text
RECEIVED
→ VALIDATING
→ PREPARING
→ INFERENCING
→ PERSISTING
→ COMPLETED
```

Ante error:

```text
cualquier estado → FAILED
```

## Responsabilidades

- generar `run_id`;
- registrar timestamps;
- ejecutar HU002 → HU003 → HU004 en orden;
- evitar pasos posteriores si falla uno;
- mapear salida del Champion al contrato BIOMAC;
- persistir solo un snapshot consistente;
- devolver la ejecución terminada en el MVP síncrono.

## Idempotencia

Clave lógica:

`reference_month + source_file_sha256 + champion_version`

## Criterios de aceptación

- CA01: una ejecución exitosa termina en `COMPLETED`.
- CA02: fallo termina en `FAILED` con etapa/código.
- CA03: reintento idéntico no genera predicciones contradictorias.
- CA04: una ejecución fallida no reemplaza la última exitosa.
- CA05: cada resultado permite reconstruir qué archivo y Champion se usaron.

---

# HU-INT-006 — Persistencia y trazabilidad

**Como** usuario y auditor  
**quiero** conservar cada ejecución  
**para** consultar la última predicción y su historial sin volver a ejecutar el modelo.

## Deployment MVP

La persistencia puede implementarse inicialmente con almacenamiento local estructurado en EC2, siempre detrás de `PredictionRepository`/`RunRepository` y fuera de rutas versionadas por Git.

La interfaz debe permitir migrar posteriormente a una base de datos sin cambiar el contrato de FastAPI ni el dashboard.

## Modelo mínimo

### Run
- `run_id`;
- `request_id`;
- `status`;
- `reference_month`;
- `source_file_sha256`;
- `created_at`, `completed_at`;
- `champion_version`;
- `error_code/error_stage` si aplica.

### Snapshot
- municipio;
- horizonte;
- target_month;
- clase;
- output nativo;
- threshold/regla;
- estado actual/canal;
- explicación si existe;
- metadata de calidad/modelo.

## Criterios de aceptación

- CA01: snapshot se persiste antes de responder éxito.
- CA02: `latest` solo toma runs `COMPLETED`.
- CA03: historial conserva versiones anteriores.
- CA04: almacenamiento queda detrás de una interfaz `PredictionRepository`.
- CA05: resultados runtime no se versionan accidentalmente en Git.

---

# HU-INT-007 — API de consulta read-only

**Como** usuario consultor  
**quiero** consultar resultados ya calculados  
**para** abrir o refrescar el dashboard sin ejecutar nuevamente el Champion.

## Endpoints

- `GET /api/v2/runs/{run_id}`
- `GET /api/v2/predictions/latest`
- `GET /api/v2/predictions/history`

Filtros permitidos según endpoint:
- municipio;
- horizonte;
- periodo;
- límite/paginación para historial.

## Criterios de aceptación

- CA01: `latest` devuelve el último snapshot exitoso.
- CA02: `Refresh` no llama ninguna operación de inferencia.
- CA03: historial ordena por corte/generación.
- CA04: si nunca existe una inferencia, se devuelve estado empty controlado.
- CA05: Bucaramanga y Cali pueden consultarse juntas o individualmente.

---

# HU-INT-008 — Integración del dashboard Lovable

**Como** analista/usuario  
**quiero** actualizar datos y consultar resultados desde la UI  
**para** operar BIOMAC sin depender de scripts manuales.

## Deployment frontend

El dashboard permanece desplegado en Lovable y consume la API remota de EC2 mediante:

```text
API_BASE_URL=https://<host-api-biomac>/api/v2
```

La URL debe configurarse por ambiente; no debe estar duplicada/hardcodeada en componentes.

FastAPI debe incluir el dominio real de Lovable en la allowlist CORS.

## Cambios frontend

- implementar `HttpDengueRepository`;
- eliminar mocks como fuente por defecto;
- acción `Actualizar datos`;
- selector de archivo y mes;
- confirmación antes de enviar;
- estado de procesamiento;
- éxito con `run_id` y corte;
- error con reintento seguro;
- tras éxito, ejecutar `GET latest`;
- botón `Refresh` solo ejecuta `GET latest`;
- conservar pantalla principal de decisión.

## Criterios de aceptación

- CA01: al abrir la página se consulta `latest` usando `API_BASE_URL`.
- CA02: upload válido actualiza la pantalla luego de inferencia exitosa.
- CA03: upload fallido no borra el resultado anterior.
- CA04: ninguna clase/probabilidad/SHAP/threshold se calcula en React.
- CA05: loading, empty, error y retry están implementados.
- CA06: CORS permite Lovable configurado y rechaza orígenes no autorizados.

---

# HU-INT-009 — Metadata, explicabilidad y calidad

**Como** usuario  
**quiero** conocer qué modelo y qué información sustentan la alerta  
**para** interpretar el resultado con trazabilidad.

## Alcance

- Champion nombre/versión;
- fecha de inferencia y corte;
- calidad/frescura;
- regla/threshold real;
- explicación local si existe;
- warnings cuando un dato opcional falte.

## Criterios de aceptación

- CA01: SHAP se etiqueta como tal solo cuando sea local y real.
- CA02: output no probabilístico no se presenta como `%`.
- CA03: metadata de entrenamiento se muestra solo como información recibida del Champion, no gestionada por este flujo.
- CA04: campos no disponibles son `null`/vacíos explícitos, nunca mocks.

---

# HU-INT-010 — Pruebas E2E, deployment y cierre

**Como** equipo BIOMAC  
**quiero** demostrar que el flujo completo es reproducible  
**para** cerrar la integración con evidencia técnica.

## Escenarios mínimos

1. health correcto en EC2;
2. CORS desde dominio Lovable permitido;
3. carga mensual válida desde frontend/API;
4. archivo inválido;
5. periodo inválido;
6. falta de columnas/features;
7. Champion no disponible;
8. incompatibilidad de contrato Champion;
9. inferencia T+1/T+2 exitosa;
10. fallo durante inferencia;
11. persistencia exitosa;
12. última predicción después de upload;
13. Refresh sin nueva inferencia;
14. historial de al menos dos runs;
15. reintento idéntico/idempotencia;
16. Bucaramanga y Cali;
17. contrato frontend/API;
18. no regresión de componentes visuales;
19. reinicio controlado de FastAPI/EC2 conserva configuración esperada;
20. deployment no requiere entrenamiento ni acceso a MLflow por request.

## Criterio de terminado

Se demuestra con evidencia automatizada y manual:

```text
Lovable
→ POST monthly-runs
→ FastAPI en EC2
→ HU002 validación
→ HU003 ChampionInput
→ HU004 Champion
→ snapshot COMPLETED
→ GET latest
→ dashboard Lovable
```

Luego se ejecuta `Refresh` y se verifica que el contador/log de inferencias no aumenta.

---

## 4. Secuencia de deployment del MVP

La secuencia objetivo es:

```text
1. Merge de código aprobado a main
2. EC2: git pull/clone del repositorio
3. Crear/activar entorno virtual
4. Instalar dependencias API
5. Materializar artefacto Champion:
   - instalar `.whl`, o
   - dvc pull durante deployment si aplica
6. Configurar variables de entorno:
   - API/CORS
   - rutas/versiones Champion
   - almacenamiento runtime
7. Ejecutar tests focales
8. Iniciar FastAPI/Uvicorn
9. Verificar GET /api/v2/health
10. Configurar `API_BASE_URL` del dashboard Lovable
11. Probar upload → inferencia → latest
12. Probar Refresh sin inferencia nueva
```

No forman parte del ciclo normal de request:
- `git pull`;
- `dvc pull`;
- instalación de paquetes;
- entrenamiento;
- consulta obligatoria a MLflow.

---

## 5. Definición global de terminado

El flujo se considera implementado cuando:

- Lovable opera como frontend y no contiene lógica ML;
- FastAPI está desplegado y accesible en EC2;
- `API_BASE_URL` y CORS conectan Lovable con FastAPI;
- no existen datos mock como fallback productivo;
- el upload mensual es el trigger normal de inferencia;
- HU002 valida el CSV ya preparado;
- HU003 produce un `ChampionInput` reproducible;
- HU004 ejecuta un Champion versionado/trazado sin acoplar la API al framework;
- una predicción exitosa queda persistida;
- `Refresh` es read-only;
- errores no destruyen el último resultado válido;
- Bucaramanga y Cali muestran T+1/T+2 únicamente según salidas reales;
- artefactos/datos pesados se versionan/materializan fuera del request normal;
- pruebas de contrato, integración, deployment y E2E pasan;
- entrenamiento y selección del Champion permanecen fuera de este alcance.

---

## 6. Decisión de implementación vigente — HU004 como frontera intercambiable

Esta sección tiene precedencia sobre referencias anteriores que describan la ejecución directa del Champion como única vía del MVP.

### Camino requerido para el MVP

HU004 implementará primero el consumo de la salida materializada de PR #12:

```text
ChampionResult PR12
→ MaterializedOutputAdapter
→ ChampionOutput
```

Este es el camino requerido para cerrar HU004 en el MVP.

### Camino futuro opcional

La ejecución directa permanece como evolución compatible:

```text
ChampionInput
→ ExecutableChampionAdapter
→ ChampionOutput
```

No es requisito para HU005 ni para cerrar el MVP. No debe utilizarse como fallback automático del camino materializado ni viceversa.

### Regla para HU005–HU010

A partir de HU005, el orquestador debe recibir un `ChampionOutputProvider` y llamar una
única operación `produce(context)`. Su resultado es siempre `ChampionOutput`. Las HUs
posteriores no pueden depender de `ChampionResult`, JSON físico,
`generate_champion_output.py`, pickle/XGBoost, `.whl` o de cómo se produjo la predicción.

Por tanto, los flujos posteriores deben conceptualizarse así:

```text
ChampionOutputProvider configurado
→ produce(context)
→ ChampionOutput
→ HU005 ResultMapper/orquestación
→ HU006 persistencia
→ HU007 API read-only
→ HU008 dashboard
→ HU009 metadata/explicabilidad
→ HU010 E2E
```

Cambiar en el futuro de `MaterializedOutputAdapter` a `ExecutableChampionAdapter` debe requerir únicamente cambios de HU004/composición/configuración, sin refactor estructural de HU005+.
