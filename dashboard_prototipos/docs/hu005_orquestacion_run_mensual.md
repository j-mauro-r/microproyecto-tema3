# HU005 — Orquestación del run mensual

**Estado:** `[COMPLETADA — DESARROLLO]`
**Versión:** `1.0.0`  
**Ámbito:** ejecución local para Entregable 2  
**Dependencias:** HU002, HU003, HU004  
**Siguiente HU:** HU006 — Persistencia y trazabilidad

---

## 1. Contexto

BIOMAC ya dispone de las piezas necesarias para validar una carga mensual y obtener una salida ML desacoplada del mecanismo concreto de serving:

```text
HU002 → ValidatedMonthlyUpload
HU003 → ChampionInput
HU004 → ChampionService / ChampionOutput
```

HU004 cerró la frontera pública para las capas posteriores mediante:

```text
ChampionService.produce(ChampionOperationalContext)
→ ChampionOutput
```

HU005 debe unir estas capacidades en un único flujo de aplicación, sin introducir persistencia durable ni infraestructura cloud.

Para el Entregable 2, toda la implementación y validación se realiza **localmente**. AWS, EC2, S3, deployment remoto y smoke tests de infraestructura quedan fuera de alcance.

---

## 2. Historia de usuario

**Como** analista que actualiza BIOMAC  
**quiero** que una carga mensual válida sea procesada por un único orquestador  
**para** obtener un resultado de predicción trazable, consistente y preparado para persistirse posteriormente, sin ejecutar pasos manuales internos.

---

## 3. Objetivo verificable

Implementar un `MonthlyPredictionOrchestrator` framework-neutral que coordine el ciclo lógico de un run mensual:

```text
RECEIVED
→ VALIDATING
→ PREPARING
→ INFERENCING
→ MAPPING
→ READY_TO_PERSIST
```

Ante cualquier error:

```text
cualquier etapa → FAILED
```

HU005 debe producir en memoria un resultado completo del run, incluyendo metadata, estados, `run_id`, timestamps, `ChampionOutput` normalizado y una clave de idempotencia lógica.

HU005 **no debe** escribir todavía en almacenamiento durable ni habilitar un `201 COMPLETED` productivo en `POST /api/v2/monthly-runs`.

---

## 4. Decisiones arquitectónicas vigentes

### 4.1 Frontera ML obligatoria

HU005 no conoce estrategias materializada/ejecutable ni tipos internos de serving.

La única operación ML permitida es:

```text
ChampionService.produce(ChampionOperationalContext)
→ ChampionOutput
```

HU005 no debe importar ni construir para seleccionar estrategia:

- `ChampionInput` como decisión A/B;
- `MaterializedChampionResult`;
- `MaterializedOutputAdapter`;
- `MaterializedChampionProvider`;
- `ExecutableChampionProvider`;
- lógica condicional por provider.

### 4.2 Separación HU005 / HU006

HU005 **orquesta y produce el resultado lógico**.

HU006 **implementa persistencia durable y trazabilidad histórica**.

HU005 puede definir/consumir puertos de repositorio requeridos por el diseño futuro, pero no debe implementar SQLite, JSON durable, base de datos ni almacenamiento en archivos.

### 4.3 Ejecución local

Para Entregable 2:

- no AWS;
- no EC2;
- no S3 operacional;
- no deployment remoto;
- no credenciales cloud;
- no dependencia de MLflow en runtime;
- no red requerida para pruebas HU005.

### 4.4 Endpoint HTTP

HU005 no debe declarar éxito productivo persistido en `POST /api/v2/monthly-runs` antes de HU006.

La integración del endpoint puede prepararse, pero el flujo HTTP definitivo con `201 COMPLETED` queda condicionado a que HU006 garantice persistencia antes de responder éxito.

---

## 5. Flujo objetivo

```text
MonthlyRunCommand
        │
        ▼
MonthlyPredictionOrchestrator
        │
        ├─ RECEIVED
        │
        ├─ HU002 / validación
        │      ↓
        │  ValidatedMonthlyUpload
        │
        ├─ PREPARING
        │      ↓
        │  ChampionOperationalContext
        │
        ├─ INFERENCING
        │      ↓
        │  ChampionService.produce(...)
        │      ↓
        │  ChampionOutput
        │
        ├─ MAPPING
        │      ↓
        │  ResultMapper
        │      ↓
        │  PredictionSnapshot candidato
        │
        └─ READY_TO_PERSIST
               ↓
          MonthlyRunResult
```

Si cualquier paso falla:

```text
MonthlyRunResult(status=FAILED, error_code, error_stage, ...)
```

No se ejecutan pasos posteriores al error.

---

## 6. Alcance funcional

HU005 debe implementar:

1. `MonthlyPredictionOrchestrator`.
2. Contrato de comando/entrada del run.
3. Generación de `run_id`.
4. Timestamps de inicio/finalización lógica.
5. Máquina de estados del run.
6. Coordinación de validación mensual existente.
7. Construcción de `ChampionOperationalContext`.
8. Invocación exclusiva de `ChampionService`.
9. `ResultMapper` de `ChampionOutput` a contrato BIOMAC intermedio/final de snapshot.
10. Resultado inmutable del run.
11. Regla de idempotencia lógica.
12. Puertos requeridos para que HU006 implemente persistencia/idempotencia durable sin modificar la lógica central de HU005.
13. Errores controlados por etapa.
14. Tests unitarios y de integración local del flujo.

---

## 7. Fuera de alcance

HU005 no implementa:

- SQLite;
- archivos JSON persistentes;
- base de datos;
- repositorios durables concretos;
- `latest` / `history`;
- recuperación de runs tras reiniciar proceso;
- garantía durable de idempotencia;
- dashboard/Lovable;
- AWS/EC2/S3;
- deployment;
- entrenamiento/reentrenamiento;
- feature engineering;
- selección/promoción de Champion;
- acceso obligatorio a MLflow;
- SHAP nuevo;
- explicaciones inventadas;
- fallback entre providers HU004;
- `201 COMPLETED` productivo antes de HU006.

---

## 8. Contratos propuestos

Los nombres exactos pueden ajustarse durante implementación si se preserva la responsabilidad.

### 8.1 Comando

```python
@dataclass(frozen=True, slots=True)
class MonthlyRunCommand:
    reference_month: str
    source_file_name: str
    source_bytes: bytes
    request_id: str | None = None
```

El orquestador puede reutilizar el contrato real que ya recibe HU002 y evitar duplicación innecesaria.

### 8.2 Resultado del run

Conceptualmente:

```python
@dataclass(frozen=True, slots=True)
class MonthlyRunResult:
    run_id: str
    request_id: str | None
    status: RunStatus
    reference_month: str
    source_file_sha256: str | None
    idempotency_key: str | None
    champion_version: str | None
    created_at: datetime
    finished_at: datetime | None
    snapshot: PredictionSnapshot | None
    error_code: ErrorCode | None
    error_stage: RunStatus | None
```

No copiar mecánicamente si los schemas existentes ya resuelven parte del contrato.

### 8.3 ResultMapper

Contrato conceptual:

```python
class ResultMapper(Protocol):
    def map(
        self,
        validated_upload: ValidatedMonthlyUpload,
        champion_output: ChampionOutput,
    ) -> PredictionSnapshot: ...
```

El mapper solo transforma información respaldada por HU002/HU004 y contratos existentes.

No puede inventar:

- probabilidades;
- thresholds;
- T+2;
- expected cases;
- SHAP;
- calidad o canal no disponibles.

---

## 9. Estados

HU005 utilizará los estados ya definidos cuando sea posible y evitará duplicar enums.

Secuencia lógica esperada:

```text
RECEIVED
VALIDATING
PREPARING
INFERENCING
MAPPING
READY_TO_PERSIST
FAILED
```

Si los schemas actuales no contienen `MAPPING` o `READY_TO_PERSIST`, se debe decidir durante implementación si:

1. extender el enum de forma compatible; o
2. mantener los estados públicos existentes y usar subetapas internas.

La elección debe evitar romper HU001–HU004 y `API-sign.md`.

Decisión implementada: `RunStatus` se extendió con `MAPPING` y `READY_TO_PERSIST`.
Es una extensión compatible; `PERSISTING` y `COMPLETED` conservan su semántica y quedan
reservados para HU006.

`COMPLETED` queda reservado para un run cuyo snapshot ya haya sido persistido durablemente por HU006.

---

## 10. Idempotencia

HU005 define la regla lógica:

```text
reference_month + source_file_sha256 + champion_version
```

Debe producir una representación determinista, por ejemplo un `idempotency_key` estable.

Responsabilidades HU005:

- calcular/normalizar la clave;
- exponerla en el resultado del run;
- definir el puerto necesario para consultar duplicados si el diseño lo requiere.

Responsabilidades HU006:

- almacenar la clave;
- garantizar unicidad durable;
- resolver reintentos tras reinicios;
- recuperar un resultado previo persistido cuando corresponda.

HU005 no debe simular idempotencia durable con estado global mutable.

---

## 11. Puertos para HU006

HU005 puede definir contratos, sin implementaciones durables, por ejemplo:

```python
class RunRepository(Protocol):
    def find_by_idempotency_key(self, key: str): ...
    def save_run(self, run): ...

class PredictionRepository(Protocol):
    def save_snapshot(self, snapshot): ...
```

La forma final debe minimizar acoplamiento y respetar DIP.

Durante HU005 los tests pueden usar fakes/in-memory **solo como doubles de prueba**, no como persistencia productiva.

---

## 12. ResultMapper y PredictionSnapshot

El mapper debe transformar `ChampionOutput` al contrato BIOMAC definido en `API-sign.md` hasta donde la información real disponible lo permita.

Debe preservar, cuando exista:

- `reference_month`;
- municipio/DIVIPOLA;
- T+1/T+2;
- `target_month`;
- tipo de salida;
- `probability`;
- `expected_cases`;
- `risk_score`;
- `label`;
- threshold por predicción;
- Champion name/version;
- feature contract version/hash;
- source file hash.

Los campos de canal endémico, calidad, historia o explicación solo se incluyen si existen de forma verificable en la entrada disponible.

No crear placeholders que aparenten datos reales.

Decisión implementada: HU005 produce `PredictionSnapshotCandidate`, un contrato de
aplicación inmutable que contiene exclusivamente predicciones y metadata demostrables.
No fuerza los campos epidemiológicos obligatorios del `PredictionSnapshot` HTTP final;
HU006/HU007 podrán completar ese contrato solo con fuentes reales.

---

## 13. Manejo de errores

HU005 debe preservar `ContractError` y códigos existentes cuando provengan de HU002/HU003/HU004.

Debe asociar cada fallo a una etapa observable.

Ejemplos:

- upload inválido → `VALIDATING`;
- input/contexto inválido → `PREPARING`;
- Champion no disponible → `INFERENCING`;
- inferencia inválida → `INFERENCING`;
- mapeo incompatible → `MAPPING`;
- error no esperado → error sanitizado, sin stack trace en contrato público.

Nunca continuar al paso siguiente después de un fallo.

---

## 14. Tareas DWP

### T01 — Baseline

- ejecutar suite API completa antes de modificar;
- registrar conteo y warnings conocidos.

### T02 — Auditar contratos existentes

- `RunStatus`;
- errores;
- schemas de run;
- `PredictionSnapshot`;
- endpoint `monthly-runs`;
- HU002 validator;
- `ChampionService` HU004.

### T03 — Crear contratos HU005

- comando;
- resultado;
- puertos;
- interfaces del mapper/orchestrator.

### T04 — Implementar `ResultMapper`

- mapping estricto;
- sin datos fabricados;
- thresholds por horizonte preservados.

### T05 — Implementar idempotency key lógica

- determinista;
- basada en periodo + hash + Champion version.

### T06 — Implementar `MonthlyPredictionOrchestrator`

- estados;
- timestamps;
- `run_id`;
- validación;
- `ChampionOperationalContext`;
- `ChampionService`;
- mapper;
- resultado en memoria.

### T07 — Manejo de fallos por etapa

- preservar errores conocidos;
- sanitizar inesperados;
- no ejecutar pasos posteriores.

### T08 — Fakes de prueba

- validators/services/repos únicamente como test doubles;
- sin almacenamiento productivo.

### T09 — Tests de flujo exitoso

- Bucaramanga/Cali;
- T+1/T+2 según Champion;
- metadata;
- thresholds independientes;
- idempotency key.

### T10 — Tests de fallos

- validación;
- preparación;
- Champion no disponible;
- inferencia;
- mapping.

### T11 — Tests de desacoplamiento

- HU005 no conoce provider A/B;
- no ML frameworks;
- no cloud;
- no DVC/MLflow/red.

### T12 — Integración HTTP controlada

- retirar dependencia conceptual del placeholder `CHAMPION_NOT_READY` donde corresponda;
- no responder todavía éxito productivo persistido antes de HU006.

### T13 — Evidencia

Crear:

```text
dashboard_prototipos/docs/hu005_evidencia_implementacion.md
```

con CA, AV, comandos, resultados y pendientes HU006.

---

## 15. Criterios de aceptación CA01–CA22

| CA | Criterio |
|---|---|
| CA01 | baseline previo queda registrado |
| CA02 | existe `MonthlyPredictionOrchestrator` framework-neutral |
| CA03 | genera `run_id` por ejecución nueva |
| CA04 | preserva `request_id` cuando existe |
| CA05 | registra timestamps de inicio/finalización lógica |
| CA06 | una carga válida atraviesa VALIDATING → PREPARING → INFERENCING → MAPPING |
| CA07 | HU005 invoca ML únicamente mediante `ChampionService` |
| CA08 | HU005 no conoce estrategias materializada/ejecutable |
| CA09 | `ChampionOutput` se transforma mediante `ResultMapper` |
| CA10 | mapper no fabrica campos no soportados |
| CA11 | probability/threshold/label reales se preservan |
| CA12 | horizontes no soportados no se inventan |
| CA13 | idempotency key usa periodo + source hash + Champion version |
| CA14 | clave de idempotencia es determinista |
| CA15 | HU005 no implementa garantía durable de idempotencia |
| CA16 | fallo de una etapa bloquea etapas posteriores |
| CA17 | error conserva código/etapa cuando proviene de contratos existentes |
| CA18 | error inesperado queda sanitizado |
| CA19 | resultado exitoso termina `READY_TO_PERSIST`, no `COMPLETED` durable |
| CA20 | no existe storage productivo en HU005 |
| CA21 | no existe dependencia AWS/DVC/S3/MLflow/red en ejecución HU005 |
| CA22 | suite completa permanece verde y evidencia queda documentada |

---

## 16. Autovalidaciones AV01–AV20

| AV | Procedimiento esperado |
|---|---|
| AV01 | importar HU005 en subprocess limpio sin frameworks ML/cloud |
| AV02 | validar contratos inmutables cuando aplique |
| AV03 | run válido genera `run_id` |
| AV04 | `request_id` se preserva |
| AV05 | timestamps son consistentes |
| AV06 | secuencia de llamadas respeta orden del flujo |
| AV07 | Champion se invoca exactamente una vez por run válido |
| AV08 | mismo consumer funciona independientemente de provider HU004 |
| AV09 | mapper preserva T+1/T+2 reales |
| AV10 | mapper preserva thresholds distintos por horizonte |
| AV11 | mapper no crea probability cuando no existe |
| AV12 | idempotency key es estable para misma terna lógica |
| AV13 | cambio de periodo cambia la clave |
| AV14 | cambio de hash cambia la clave |
| AV15 | cambio de Champion version cambia la clave |
| AV16 | fallo en validación evita Champion |
| AV17 | fallo en Champion evita mapping posterior |
| AV18 | no se escribe storage durable |
| AV19 | pruebas focales y suite API completa pasan |
| AV20 | compileall y pip check pasan |

---

## 17. Definition of Done

HU005 puede marcarse `[COMPLETADA — DESARROLLO]` únicamente cuando:

1. existe un orquestador único y testeable;
2. HU005 utiliza la frontera neutral `ChampionService`;
3. `ResultMapper` produce un snapshot contractual sin inventar datos;
4. los estados y errores son observables;
5. existe `run_id`, timestamps e idempotency key lógica;
6. el flujo funciona completamente en memoria/local;
7. no hay persistencia durable productiva;
8. no hay AWS ni dependencia cloud;
9. no se declara `COMPLETED` productivo antes de persistir;
10. CA01–CA22 y AV01–AV20 quedan verificados;
11. suite de regresión está verde;
12. evidencia HU005 está versionada.

---

## 18. Gate hacia HU006

HU006 podrá comenzar cuando HU005 entregue establemente:

```text
MonthlyRunResult
+ PredictionSnapshot candidato
+ idempotency_key
+ contratos de repositorio necesarios
```

HU006 deberá agregar:

```text
READY_TO_PERSIST
→ persistir Run
→ persistir Snapshot
→ garantizar idempotencia durable
→ COMPLETED
```

Solo después de HU006 el endpoint `POST /api/v2/monthly-runs` podrá responder éxito productivo garantizando que el resultado ya fue persistido.

---

## 19. Riesgos y controles

| Riesgo | Control |
|---|---|
| duplicar responsabilidades HU004 | invocar solo `ChampionService` |
| mover persistencia a HU005 | storage durable explícitamente fuera de alcance |
| fabricar datos del dashboard | mapper estricto y tests negativos |
| confundir run lógico con durable | `READY_TO_PERSIST` antes de HU006 |
| idempotencia falsa en memoria | HU005 solo define clave/regla |
| acoplarse a PR12 | HU005 solo conoce `ChampionOutput` |
| introducir infraestructura innecesaria | Entregable 2 local-only |

---

## 20. Resultado esperado

Al cerrar HU005 deberá ser posible demostrar localmente:

```text
archivo mensual válido
→ validación
→ ChampionService
→ ChampionOutput real/fake contractual
→ ResultMapper
→ MonthlyRunResult READY_TO_PERSIST
```

sin AWS, sin almacenamiento durable y sin que HU005 conozca cómo HU004 obtiene la salida del Champion.
