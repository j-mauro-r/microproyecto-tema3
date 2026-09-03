# HU004 — Adapter del Champion BIOMAC

## 1. Identificación

- **ID canónico:** HU004
- **Alias en backlog:** HU-INT-004
- **Nombre:** Adapter del Champion
- **Estado:** `[COMPLETADA — DESARROLLO]`
- **Deployment AWS:** `[PENDIENTE]`
- **Integración Champion real:** `[PENDIENTE MODELADO/AWS]`
- **Prioridad:** ALTA
- **Tipo:** Backend / Integración ML / Serving
- **Metodología:** DWP (Deep Work Plan)
- **Dependencia previa:** HU003 — Adaptación mínima al contrato del Champion `[COMPLETADA]`
- **Habilita:** HU005 — Orquestación del run mensual (`HU-INT-005`)
- **Gate posterior:** HU005 puede iniciar usando la interfaz estable `ChampionAdapter` y `ChampionOutput`; la validación con Champion real y deployment permanece como gate separado de modelado/AWS.

### Fuentes de verdad

1. `dashboard_prototipos/docs/arquitectura.md`;
2. `dashboard_prototipos/docs/implementacion.md`;
3. `dashboard_prototipos/docs/API-sign.md`;
4. `dashboard_prototipos/docs/plan.md`;
5. `dashboard_prototipos/docs/diccionario-de-datos.md`;
6. `dashboard_prototipos/docs/HU-MVP-FastAPI-dashboard.md`;
7. `dashboard_prototipos/docs/hu003_champion_input_contract.md`;
8. `dashboard_prototipos/docs/hu003_evidencia_implementacion.md`;
9. `api/app/domain/champion_input.py`;
10. `api/app/domain/champion_feature_contract.py`;
11. contrato/artefacto Champion aprobado entregado por el equipo de modelado;
12. PR #12 únicamente como fuente complementaria temporal mientras el Champion definitivo no esté materializado en `main`.

---

## 2. Contexto y decisión de alcance

HU003 termina en un objeto estable y framework-agnostic:

```text
ChampionInput
- reference_month
- municipalities
- feature_names
- rows 2 × 39
- feature_contract_version
- feature_contract_sha256
- source_file_sha256
```

HU004 debe tomar ese contrato y encapsular completamente la interacción con el Champion.

El flujo objetivo es:

```text
ChampionInput
→ ChampionAdapter
→ Champion aprobado T+1/T+2
→ ChampionOutput
```

La arquitectura física vigente define que, para el MVP académico:

```text
Lovable
  ↓ HTTP(S)
FastAPI + backend BIOMAC en AWS EC2
  ↓ llamada Python interna
ChampionAdapter + Champion en la misma EC2
```

No se crea un microservicio adicional de model serving en esta HU.

El Champion puede entregarse preferentemente como paquete Python versionado `.whl` o, si el equipo de modelado lo requiere, como artefacto `joblib`/pickle/XGBoost materializado durante deployment. La diferencia queda encapsulada detrás del adapter.

---

## 3. Historia de usuario

> **Como** backend BIOMAC, **quiero** consumir el Champion aprobado mediante una interfaz estable y desacoplada del framework ML, **para** ejecutar inferencia sobre `ChampionInput` sin que FastAPI, HU005 o el dashboard conozcan detalles de XGBoost, MLflow, pickle, DVC o rutas físicas de artefactos.

---

## 4. Objetivo verificable

Al finalizar HU004 deberá existir una capa reusable y testeable que:

1. reciba exclusivamente `ChampionInput` como entrada pública de inferencia;
2. exponga una interfaz estable `ChampionAdapter`;
3. exponga metadata mínima del Champion mediante `ChampionMetadata`;
4. produzca un `ChampionOutput` independiente del framework concreto;
5. valide compatibilidad del `feature_contract_version` y `feature_contract_sha256` antes de inferir;
6. preserve la correspondencia exacta entre municipio, horizonte y salida;
7. represente T+1 y T+2 únicamente cuando el Champion realmente los soporte;
8. exponga `probability` únicamente si la salida nativa es probabilística;
9. no invente threshold, probabilidad, label, T+2 ni metadata faltante;
10. convierta fallos de carga/configuración en `CHAMPION_NOT_READY`;
11. convierta fallos durante la predicción en `INFERENCE_FAILED`;
12. cargue/reutilice el Champion una vez por proceso cuando sea seguro;
13. no ejecute entrenamiento, tuning, selección ni promoción;
14. no ejecute `dvc pull` durante una request;
15. no requiera acceso online a MLflow durante cada inferencia;
16. no persista resultados;
17. no construya `PredictionSnapshot`;
18. permita pruebas offline mediante fake/stub sin artefacto real;
19. permita sustituir el mecanismo de carga sin cambiar FastAPI/HU005;
20. deje documentadas por separado las tareas de código y las tareas manuales de AWS/deployment.

---

## 5. Contrato de entrada

HU004 acepta:

```python
ChampionInput
```

producido por HU003.

### Invariantes esperadas

- `municipalities == ("68001", "76001")`;
- `feature_names` coincide exactamente con `CHAMPION_FEATURES`;
- dos filas;
- 39 valores por fila;
- valores numéricos finitos;
- `feature_contract_version` presente;
- `feature_contract_sha256` presente;
- `source_file_sha256` presente;
- `reference_month` válido.

HU004 no debe volver a implementar el parser CSV ni recalcular las validaciones completas de HU002/HU003. Sí debe validar compatibilidad con el Champion cargado antes de invocarlo.

---

## 6. Contratos de salida

### 6.1 `ChampionMetadata`

Definir un tipo inmutable equivalente a:

```python
@dataclass(frozen=True, slots=True)
class ChampionMetadata:
    name: str
    version: str
    supported_horizons: tuple[str, ...]
    output_type: str
    feature_contract_version: str
    feature_contract_sha256: str
    decision_threshold: float | None = None
    mlflow_run_id: str | None = None
    artifact_sha256: str | None = None
```

Reglas:

- `supported_horizons` solo incluye horizontes reales;
- `decision_threshold=None` si el Champion no entrega una regla contractual;
- `mlflow_run_id=None` si no existe o no forma parte del artefacto entregado;
- `artifact_sha256=None` solo cuando no sea técnicamente aplicable;
- no usar valores ficticios para completar metadata.

### 6.2 `ChampionPrediction`

Tipo conceptual por municipio/horizonte:

```python
@dataclass(frozen=True, slots=True)
class ChampionPrediction:
    divipola: str
    horizon: str
    target_month: str
    output_type: str
    probability: float | None
    expected_cases: float | None
    risk_score: float | None
    label: str | None
    decision_threshold: float | None
```

No todos los campos deben poblarse. Deben respetar el `output_type` real.

### 6.3 `ChampionOutput`

```python
@dataclass(frozen=True, slots=True)
class ChampionOutput:
    reference_month: str
    predictions: tuple[ChampionPrediction, ...]
    metadata: ChampionMetadata
    source_file_sha256: str
```

El output no es todavía el JSON final del dashboard ni el `PredictionSnapshot` de `API-sign.md`.

La normalización completa para persistencia/API corresponde a `ResultMapper` y HU005+.

---

## 7. Interfaz del adapter

Contrato mínimo:

```python
class ChampionAdapter(Protocol):
    def metadata(self) -> ChampionMetadata:
        ...

    def predict(self, inference_input: ChampionInput) -> ChampionOutput:
        ...
```

La implementación concreta puede llamarse, por ejemplo:

```text
PackagedChampionAdapter
```

si consume un paquete `.whl`, o:

```text
ArtifactChampionAdapter
```

si carga artefactos serializados.

No acoplar nombres públicos a XGBoost si no es imprescindible.

---

## 8. Decisiones de diseño

### 8.1 Separación puerto/adapter

Ubicación sugerida coherente con arquitectura:

```text
api/app/champion/
├── port.py
├── models.py
└── adapter.py
```

Responsabilidades:

- `port.py`: interfaz/Protocol;
- `models.py`: `ChampionMetadata`, `ChampionPrediction`, `ChampionOutput`;
- `adapter.py`: implementación concreta.

### 8.2 Framework encapsulado

Solo el adapter concreto puede conocer detalles como:

- `predict_proba`;
- `xgboost.Booster`;
- `joblib.load`;
- módulos específicos del paquete Champion;
- rutas locales del artefacto.

No deben aparecer en:

- routes FastAPI;
- schemas HTTP;
- HU003;
- frontend;
- `MonthlyPredictionOrchestrator`.

### 8.3 Compatibilidad del feature contract

Antes de inferencia se debe comprobar:

```text
ChampionInput.feature_contract_version
== ChampionMetadata.feature_contract_version
```

y:

```text
ChampionInput.feature_contract_sha256
== ChampionMetadata.feature_contract_sha256
```

Una incompatibilidad debe bloquear inferencia.

No intentar adaptar automáticamente columnas incompatibles.

### 8.4 Carga del Champion

El Champion debe cargarse una sola vez por proceso cuando la librería/formato lo permita.

Patrones permitidos:

- inicialización del adapter durante composición de la aplicación;
- lazy loading thread-safe con cache interna inmutable;
- factory configurada por settings.

Evitar cargar el artefacto en cada llamada a `predict()`.

### 8.5 Estrategia preferida `.whl`

Si el equipo de modelado entrega un paquete instalable:

```text
model_biomac-X.Y.Z-py3-none-any.whl
```

la EC2 lo instala durante deployment y el adapter importa una API pública del paquete.

El paquete debe encapsular, idealmente:

- carga del modelo;
- transformación específica estrictamente necesaria dentro del paquete, si aplica;
- predicción;
- metadata contractual.

HU004 no define cómo el equipo de modelado empaqueta internamente el Champion; solo define la interfaz de integración requerida.

### 8.6 Artefactos DVC/S3

Si existen artefactos pesados versionados por DVC:

```text
deployment
→ dvc pull
→ artefacto disponible localmente en EC2
→ adapter carga ruta local
```

Está prohibido:

```text
request
→ dvc pull
→ inferencia
```

### 8.7 MLflow

MLflow puede ser fuente de trazabilidad/versionado durante modelado o deployment, pero el serving del MVP no debe requerir que un tracking server esté online en cada request.

Metadata MLflow puede viajar materializada junto con el Champion.

### 8.8 T+1 y T+2

HU004 no presupone que un único objeto de modelo genere ambos horizontes.

Son válidas, entre otras, estas implementaciones internas:

```text
modelo_T1 + modelo_T2
```

ó

```text
un modelo multi-horizon
```

El adapter debe ocultar esa diferencia.

Si el artefacto aprobado solo soporta T+1, HU004 debe exponer solo T+1 y reportar la brecha; no derivar ni simular T+2.

### 8.9 Threshold y label

La regla de decisión debe provenir del Champion/contrato aprobado.

Prohibido:

```python
threshold = 0.5
```

como fallback arbitrario.

Si existe threshold contractual:

```text
probability >= threshold → label contractual
```

Si no existe threshold, `label` y `decision_threshold` deben permanecer `None` salvo que el Champion entregue directamente una clase válida.

### 8.10 Mes objetivo

`target_month` debe calcularse de manera determinista desde `reference_month` y `horizon`, salvo que el Champion entregue explícitamente ese dato.

No usar la fecha actual del servidor para determinar el mes objetivo.

---

## 9. Manejo de errores

### 9.1 `CHAMPION_NOT_READY`

Aplicar cuando:

- artefacto/paquete configurado no está disponible;
- import del Champion falla;
- metadata mínima no puede cargarse;
- el modelo no puede inicializarse;
- configuración requerida está ausente.

Etapa lógica:

```text
INFERENCING
```

### 9.2 `CHAMPION_INPUT_INVALID`

Aplicar cuando el input entregado a HU004 viola el contrato necesario para inferencia o no coincide con el feature contract del Champion.

Etapa lógica preferida:

```text
PREPARING
```

si el error se detecta antes de invocar el modelo.

### 9.3 `INFERENCE_FAILED`

Aplicar cuando el Champion estaba disponible y la ejecución de inferencia falla inesperadamente.

Etapa:

```text
INFERENCING
```

No exponer stack traces, rutas internas ni secretos en respuestas públicas.

---

## 10. Fuera de alcance

HU004 **no** debe implementar:

- upload multipart;
- parsing CSV;
- validación completa HU002;
- creación de `ChampionInput`;
- feature engineering;
- entrenamiento/reentrenamiento;
- tuning;
- selección/promoción Champion;
- registro de nuevos experimentos MLflow;
- descarga DVC dentro de request;
- persistencia de runs/snapshots;
- `PredictionRepository`;
- `ResultMapper` completo;
- `GET latest/history`;
- integración Lovable;
- autenticación;
- Nginx/HTTPS;
- creación/configuración de EC2;
- apertura de Security Groups;
- instalación manual en EC2;
- systemd/supervisor;
- Docker/CI/CD salvo que ya exista infraestructura y sea estrictamente necesario;
- SHAP local;
- explicación epidemiológica;
- mocks como fallback productivo.

---

## 11. Plan de implementación DWP

### T01 — Validar base integrada

- partir de `main` con HU003 mergeada;
- ejecutar suite `api/tests` antes de cambios;
- confirmar `ChampionInput` y `champion_feature_contract.py`.

**Responsable:** Codex/desarrollo.

### T02 — Auditar el contrato real del Champion

Confirmar con los artefactos disponibles:

- formato de entrega (`.whl`, joblib, pickle, XGBoost u otro);
- entry point/API pública de predicción;
- T+1/T+2 soportados;
- `predict`/`predict_proba` o salida equivalente;
- threshold real;
- `feature_contract_version`;
- `feature_contract_sha256`;
- nombre/versión;
- metadata MLflow si existe.

Si un dato no existe, documentarlo; no inventarlo.

**Responsable:** Codex puede auditar repositorio; equipo de modelado debe resolver datos faltantes.

### T03 — Crear modelos de dominio HU004

Implementar tipos inmutables:

- `ChampionMetadata`;
- `ChampionPrediction`;
- `ChampionOutput`.

**Responsable:** Codex.

### T04 — Crear puerto `ChampionAdapter`

Crear interfaz/Protocol estable sin dependencias de XGBoost/MLflow.

**Responsable:** Codex.

### T05 — Implementar validación de compatibilidad

Validar versión/hash del feature contract antes de inferencia.

**Responsable:** Codex.

### T06 — Implementar adapter concreto

Si el Champion real está disponible en el repositorio o como paquete instalable accesible durante desarrollo, implementar el adapter real.

Si todavía no está disponible, implementar:

- puerto definitivo;
- factory/configuración necesaria;
- fake/stub exclusivo para tests;
- adapter real como integración pendiente explícita, sin fabricar outputs productivos.

**Responsable:** Codex para código disponible; equipo de modelado para artefacto faltante.

### T07 — Carga única/reutilización

Garantizar que el Champion no se deserializa por cada predicción.

**Responsable:** Codex.

### T08 — Mapear output nativo a `ChampionOutput`

Preservar:

- municipio;
- horizonte;
- mes objetivo;
- output real;
- threshold/label solo si existen;
- metadata contractual.

**Responsable:** Codex.

### T09 — Manejo de errores

Integrar `CHAMPION_NOT_READY`, `CHAMPION_INPUT_INVALID` e `INFERENCE_FAILED` usando infraestructura existente.

**Responsable:** Codex.

### T10 — Tests offline

Crear pruebas sin AWS que cubran:

- metadata;
- 2 × 39 válido;
- Bucaramanga/Cali;
- orden estable;
- T+1/T+2 soportados por fake;
- output probabilístico;
- threshold contractual;
- feature contract incompatible;
- Champion no disponible;
- inferencia fallida;
- carga única del Champion;
- ausencia de DVC/MLflow/network por request.

**Responsable:** Codex.

### T11 — Regresión completa API

Ejecutar:

```bash
python -m pytest api/tests -q
python -m compileall -q api/app api/tests
python -m pip check
```

**Responsable:** Codex/local.

### T12 — Evidencia DWP de desarrollo

Crear:

```text
dashboard_prototipos/docs/hu004_evidencia_implementacion.md
```

con:

- tareas ejecutadas;
- CA/AV;
- comandos;
- resultados;
- artefactos usados;
- limitaciones;
- dependencias todavía pendientes de AWS/modelado.

**Responsable:** Codex.

### T13 — Preparar paquete/artefacto para deployment

Si existe `.whl`, conservar versión y checksum. Si depende de DVC, asegurar que metadata `.dvc` está versionada y el artefacto puede recuperarse con `dvc pull`.

No incluir credenciales AWS en Git.

**Responsable:** equipo de modelado + Mauricio para validación/deployment.

### T14 — Provisionar/configurar EC2

En AWS:

1. iniciar/crear la EC2 definida para el MVP;
2. conectar por SSH;
3. actualizar repositorio;
4. crear/activar `.venv`;
5. instalar dependencias;
6. instalar paquete `.whl` si aplica;
7. configurar DVC/S3 si aplica;
8. ejecutar `dvc pull` una vez durante deployment;
9. configurar variables de entorno;
10. ejecutar pruebas HU004 en EC2.

**Responsable:** Mauricio / tarea manual AWS.

### T15 — Validación real del Champion en EC2

Ejecutar un smoke test con `ChampionInput` válido para Bucaramanga y Cali y verificar el output real sin pasar todavía por el dashboard.

Registrar evidencia de:

- versión Champion;
- feature contract;
- horizontes reales;
- salida real;
- threshold real si existe.

**Responsable:** Mauricio, apoyado por código/scripts preparados por Codex.

### T16 — Arranque FastAPI en EC2

Levantar FastAPI/Uvicorn y verificar:

```text
GET /api/v2/health
```

`champion_ready` deberá reflejar el estado real del adapter una vez integrado según contrato existente.

La conexión completa `POST /monthly-runs → HU002 → HU003 → HU004 → persistencia` corresponde principalmente a HU005/HU006; HU004 no debe fabricar `COMPLETED` antes de esas HUs.

**Responsable:** Mauricio para infraestructura; Codex puede preparar configuración/scripts si ya existen patrones del repo.

### T17 — Auditoría final del diff

Comprobar que HU004 no implementó accidentalmente HU005+ ni infraestructura AWS hardcodeada.

**Responsable:** Codex + revisión humana.

---

## 12. Criterios de aceptación CA01–CA20

### CA01 — Dependencia HU003

**Dado** `main` con HU003 integrada, **cuando** se ejecuta la suite base, **entonces** permanece verde antes de HU004.

### CA02 — Entrada pública estable

**Dado** un `ChampionInput`, **cuando** se invoca HU004, **entonces** el adapter no depende del CSV original.

### CA03 — Puerto desacoplado

**Dado** el diseño HU004, **cuando** se inspecciona la interfaz, **entonces** no expone tipos de XGBoost/MLflow/pickle.

### CA04 — Metadata real

**Dado** un Champion disponible, **cuando** se solicita metadata, **entonces** nombre, versión, horizontes, output type y feature contract provienen de configuración/artefacto real.

### CA05 — Feature contract compatible

**Dado** un input compatible, **cuando** se predice, **entonces** versión/hash coinciden con el Champion antes de ejecutar inferencia.

### CA06 — Feature contract incompatible

**Dado** hash o versión incompatibles, **cuando** se intenta predecir, **entonces** la inferencia se bloquea de forma controlada.

### CA07 — Municipios preservados

**Dado** el input de HU003, **cuando** se genera `ChampionOutput`, **entonces** las salidas conservan correspondencia inequívoca con `68001` y `76001`.

### CA08 — Horizonte explícito

**Dado** un Champion multi-horizon, **cuando** devuelve predicciones, **entonces** cada salida indica `T+1` o `T+2` explícitamente.

### CA09 — No inventar T+2

**Dado** un Champion que solo soporta T+1, **cuando** HU004 genera output, **entonces** no fabrica T+2.

### CA10 — Probabilidad real

**Dado** un Champion probabilístico, **cuando** produce `ChampionOutput`, **entonces** `probability` corresponde a su salida real y está en rango válido.

### CA11 — No falsa probabilidad

**Dado** un output no probabilístico, **cuando** se mapea la salida, **entonces** no se transforma arbitrariamente en porcentaje/probabilidad.

### CA12 — Threshold contractual

**Dado** un threshold aprobado, **cuando** se genera output, **entonces** se utiliza ese valor y no un fallback `0.5`.

### CA13 — Threshold ausente

**Dado** un Champion sin threshold, **cuando** se genera output, **entonces** threshold/label permanecen ausentes salvo clase nativa explícita.

### CA14 — Carga única

**Dado** múltiples predicciones en un mismo proceso, **cuando** se invoca el adapter repetidamente, **entonces** el artefacto no se recarga innecesariamente por request.

### CA15 — Champion no disponible

**Dado** un artefacto/paquete ausente o inválido, **cuando** se inicializa/invoca el adapter, **entonces** se produce `CHAMPION_NOT_READY` controlado.

### CA16 — Fallo de inferencia

**Dado** un Champion cargado que falla al predecir, **cuando** ocurre el error, **entonces** se produce `INFERENCE_FAILED` sin exponer detalles sensibles.

### CA17 — Sin operaciones cloud por request

**Dado** una predicción normal, **cuando** se ejecuta, **entonces** no se llama DVC/S3/MLflow como requisito del camino crítico.

### CA18 — Test offline

**Dado** un fake Champion, **cuando** se ejecutan tests localmente, **entonces** HU004 puede validarse sin AWS ni red.

### CA19 — Infraestructura separada

**Dado** el cierre de desarrollo local, **cuando** se revisa la evidencia, **entonces** las tareas EC2/DVC/S3/install quedan registradas separadamente y no hardcodeadas en código.

### CA20 — Handoff HU005

**Dado** HU004 completada, **cuando** inicia HU005, **entonces** existe una operación estable `ChampionInput → ChampionOutput` que puede ser orquestada sin conocer el framework ML.

---

## 13. Autovalidaciones AV01–AV18

### AV01 — Suite base

**Procedimiento:** ejecutar suite API antes de cambios.  
**PASS:** cero regresiones preexistentes atribuibles a HU004.

### AV02 — Imports de frontera

**Procedimiento:** revisar `api/app/champion/`.  
**PASS:** `port.py` y modelos no importan XGBoost/MLflow/DVC/AWS.

### AV03 — Inmutabilidad

**Procedimiento:** intentar modificar `ChampionMetadata`/`ChampionOutput`.  
**PASS:** contratos inmutables.

### AV04 — Feature version mismatch

**Procedimiento:** alterar versión en fixture.  
**PASS:** inferencia bloqueada.

### AV05 — Feature hash mismatch

**Procedimiento:** alterar SHA en fixture.  
**PASS:** inferencia bloqueada.

### AV06 — Orden municipal

**Procedimiento:** usar `ChampionInput` de HU003.  
**PASS:** resultados asociados correctamente a 68001/76001.

### AV07 — T+1/T+2

**Procedimiento:** fake con dos horizontes.  
**PASS:** cuatro salidas máximas esperadas para 2 municipios × 2 horizontes, si el contrato fake soporta ambos.

### AV08 — T+1 solamente

**Procedimiento:** fake T+1-only.  
**PASS:** no aparece T+2.

### AV09 — Probabilidad

**Procedimiento:** fake probabilístico.  
**PASS:** probability preservada sin recalibración arbitraria.

### AV10 — Threshold

**Procedimiento:** threshold distinto de 0.5.  
**PASS:** se usa el contractual.

### AV11 — Champion ausente

**Procedimiento:** configurar loader inexistente.  
**PASS:** `CHAMPION_NOT_READY`.

### AV12 — Excepción de predicción

**Procedimiento:** fake que lanza excepción.  
**PASS:** `INFERENCE_FAILED`.

### AV13 — Load once

**Procedimiento:** contador en fake loader + varias predicciones.  
**PASS:** carga única según estrategia definida.

### AV14 — Sin red/cloud

**Procedimiento:** ejecutar tests en entorno sin credenciales AWS/MLflow.  
**PASS:** suite focal HU004 pasa.

### AV15 — Suite completa

**Procedimiento:** `python -m pytest api/tests -q`.  
**PASS:** toda la suite API pasa.

### AV16 — Compileall

**Procedimiento:** `python -m compileall -q api/app api/tests`.  
**PASS:** salida exitosa.

### AV17 — Dependencias

**Procedimiento:** `python -m pip check`.  
**PASS:** sin dependencias rotas.

### AV18 — Diff scope

**Procedimiento:** inspeccionar diff.  
**PASS:** no incluye HU005+, credenciales, infraestructura sensible ni resultados runtime.

---

## 14. Definición de terminado — desarrollo

HU004 puede marcar su **parte de desarrollo** `[COMPLETADA]` cuando:

- existe `ChampionAdapter` estable;
- existen contratos inmutables de metadata/output;
- existe validación del feature contract;
- errores están controlados;
- hay tests offline completos;
- suite API permanece verde;
- existe evidencia DWP;
- el código no depende de AWS para probarse;
- no se inventan salidas del Champion;
- el handoff a HU005 está documentado.

**Estado actual:** `[COMPLETADA — DESARROLLO]` según la evidencia DWP del PR #25. El Champion real aún no ha sido entregado con un contrato de serving definitivo, por lo que no se declara validación real de modelo ni deployment completado.

---

## 15. Definición de terminado — infraestructura/deployment

La validación de deployment asociada a HU004 queda completada cuando Mauricio haya demostrado en AWS EC2:

```text
repo actualizado
→ entorno Python instalado
→ Champion real instalado/materializado
→ metadata cargable
→ ChampionInput real/smoke fixture
→ ChampionAdapter
→ ChampionOutput real
```

Debe quedar evidencia de:

- versión del Champion;
- mecanismo de instalación/carga;
- feature contract version/hash;
- horizontes soportados;
- threshold real si existe;
- ejecución satisfactoria para Bucaramanga/Cali;
- ausencia de credenciales en Git.

Esta evidencia puede incorporarse posteriormente al documento `hu004_evidencia_implementacion.md`.

---

## 16. Riesgos y controles

| Riesgo | Impacto | Control |
|---|---|---|
| Champion definitivo no disponible | HU004 no puede validar inferencia real | Implementar puerto/tests con fake y dejar integración real como gate explícito |
| T+2 no existe realmente | Dashboard podría mostrar información falsa | No exponer T+2 hasta artefacto contractual real |
| Threshold inconsistente entre metadata/scripts | Labels incorrectos | Fuente única contractual; no usar valores inferidos |
| Feature contract cambia | Inferencia silenciosamente inválida | Validar versión + SHA antes de predict |
| Cargar modelo por request | Latencia/uso de memoria | Load once por proceso |
| DVC/S3 en request | Fragilidad y latencia | Materializar solo en deployment |
| Dependencia online de MLflow | Serving indisponible si MLflow cae | Metadata materializada/local |
| Framework se filtra al backend | Acoplamiento | Port/adapter y modelos de dominio |
| Credenciales AWS versionadas | Riesgo de seguridad | variables de entorno/credenciales locales; nunca Git |

---

## 17. Handoff a HU005

HU005 debe recibir como dependencia una operación estable:

```text
ValidatedMonthlyUpload
→ HU003 ChampionInput
→ HU004 ChampionAdapter.predict()
→ ChampionOutput
```

HU005 será responsable de coordinar estados, `run_id`, idempotencia, `ResultMapper`, persistencia y respuesta del run.

HU004 no debe adelantar esas responsabilidades.