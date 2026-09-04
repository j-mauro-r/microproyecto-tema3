# HU004 — Adapter del Champion BIOMAC

## 1. Identificación

- **ID canónico:** HU004
- **Alias en backlog:** HU-INT-004
- **Nombre:** Adapter del Champion
- **Estado:** `[AJUSTE DE INTEGRACIÓN PENDIENTE — FEATURE CONTRACT GATE]`
- **Deployment AWS:** `[PENDIENTE]`
- **Integración Champion real:** `[PARCIAL — HTTP FUNCIONA, COMPATIBILIDAD CONTRACTUAL NO CERRADA]`
- **Prioridad:** ALTA
- **Tipo:** Backend / Integración ML / Serving
- **Metodología:** DWP (Deep Work Plan)
- **Dependencia previa:** HU003 — Adaptación mínima al contrato del Champion `[COMPLETADA]`
- **Habilita:** HU005 — Orquestación del run mensual (`HU-INT-005`)
- **Gate posterior:** HU005 puede iniciar al recibir `ChampionService`, pero ningún resultado puede alcanzar mapping/persistencia si el contrato de features declarado por el Champion no coincide exactamente con el contrato efectivo del input del run.

### Fuentes de verdad

1. `dashboard_prototipos/docs/arquitectura.md`;
2. `dashboard_prototipos/docs/implementacion.md`;
3. `dashboard_prototipos/docs/API-sign.md`;
4. `dashboard_prototipos/docs/plan.md`;
5. `dashboard_prototipos/docs/diccionario-de-datos.md`;
6. `dashboard_prototipos/docs/hu003_champion_input_contract.md`;
7. `api/app/domain/champion_input.py`;
8. `api/app/domain/champion_feature_contract.py`;
9. PR #12 `feat/dashboard-sat-dengue`, en especial:
   - `dashboard_prototipos/JSON-dashboard.md`;
   - `scripts/generate_champion_output.py`;
   - `scripts/generate_predictions.py`;
   - `scripts/generate_shap.py`;
   - artefactos T+1/T+2 que dicho PR utiliza para producir salidas.

---

## 2. Nuevo descubrimiento de integración

La auditoría actualizada de PR #12 confirma que el equipo de modelado ya entrega una **salida de inferencia materializable y consumible por backend**, no solo artefactos de entrenamiento.

El contrato práctico de PR #12 es:

```text
Champion / modelos T+1 y T+2
→ scripts/generate_champion_output.py
→ ChampionResult
→ JSON serializable
```

La salida incluye para el MVP:

```text
Bucaramanga 68001 T+1
Bucaramanga 68001 T+2
Cali        76001 T+1
Cali        76001 T+2
```

con, como mínimo:

```text
model_name
model_version
reference_month
feature_contract_version
feature_contract_sha256
output_type
predictions[].divipola
predictions[].municipality
predictions[].horizon
predictions[].target_month
predictions[].probability
predictions[].threshold
predictions[].label
```

Este descubrimiento cambia la estrategia de HU004: **ya no debemos asumir que la única integración válida será un `.whl` o un objeto de modelo cargado dentro del backend**.

HU004 debe soportar dos modos detrás de la misma frontera:

```text
MODO A — ejecución directa
ChampionInput
→ ExecutableChampionAdapter
→ ChampionRuntime
→ ChampionOutput

MODO B — salida materializada PR12
ChampionResult / JSON
→ MaterializedOutputAdapter
→ ChampionOutput
```

FastAPI, HU005 y el dashboard no deben conocer cuál modo se utilizó.

---

## 3. Historia de usuario

> **Como** backend BIOMAC, **quiero** consumir de manera estable las salidas reales entregadas por el equipo de modelado en PR #12 o por un Champion ejecutable equivalente, **para** exponer en el dashboard predicciones T+1/T+2 de Bucaramanga y Cali con probabilidad, threshold y clase sin acoplar la API al mecanismo interno del modelo.

---

## 4. Objetivo verificable

Al finalizar HU004 deberá existir una capa que:

1. mantenga una interfaz estable `ChampionAdapter`;
2. soporte entrada ejecutable `ChampionInput → ChampionOutput`;
3. soporte adaptación de `ChampionResult`/JSON de PR #12 → `ChampionOutput`;
4. preserve `model_name`, `model_version`, `reference_month`, `feature_contract_version`, `feature_contract_sha256` y `output_type`;
5. preserve exactamente municipio, horizonte y `target_month` de cada predicción;
6. preserve `probability` sin recalibrarla ni transformarla;
7. preserve **threshold por predicción/horizonte**;
8. preserve `label` cuando venga del contrato de PR #12 y valide su consistencia;
9. no copie un único threshold global a T+1 y T+2 salvo que el contrato entregue explícitamente el mismo valor para ambos;
10. no invente T+2, probability, threshold, label, SHAP, expected_cases o risk_score;
11. valide que las cuatro combinaciones Bucaramanga/Cali × T+1/T+2 estén presentes cuando el contrato declare ambos horizontes;
12. valide `target_month` contra `reference_month + horizon`;
13. valide rangos `[0,1]` para probabilidad/threshold cuando apliquen;
14. valide duplicados por `(divipola, horizon)`;
15. permita consumir un dict/objeto Python sin requerir escribir un archivo JSON físico;
16. permita opcionalmente leer JSON materializado para demo/prueba;
17. mantenga DVC/S3/MLflow fuera de cada request;
18. no implemente entrenamiento ni preparación de datos;
19. no persista todavía `PredictionSnapshot`;
20. deje un handoff estable para HU005;
21. compare obligatoriamente `feature_contract_version` y `feature_contract_sha256` del Champion con los del input/contexto operacional del mismo run;
22. rechace de forma controlada cualquier mismatch antes de mapping/persistencia y sin fabricar `COMPLETED`.

---

## 5. Alcance funcional para el dashboard

HU004 debe garantizar que el backend pueda obtener los datos ML necesarios para las tarjetas y alertas del dashboard:

| Dato | Fuente PR #12 | Uso en dashboard |
|---|---|---|
| `divipola` | `ChampionResult.predictions[]` | identificar Bucaramanga/Cali |
| `municipality` | `ChampionResult.predictions[]` | nombre visible |
| `horizon` | `T+1` / `T+2` | separar horizonte |
| `target_month` | por predicción | mes pronosticado |
| `probability` | por predicción | probabilidad de exceso |
| `threshold` | por predicción | regla de decisión real |
| `label` | `EXCESO/NO_EXCESO` | alerta principal |
| `model_name` | nivel Champion | trazabilidad |
| `model_version` | nivel Champion | trazabilidad |
| `reference_month` | nivel Champion | corte de información |
| `output_type` | nivel Champion | interpretación correcta |
| feature contract version/hash | nivel Champion | compatibilidad técnica y gate del run |

### Información complementaria de PR #12

PR #12 también genera:

- `prediction_history.parquet`, con historial de predicciones;
- salidas SHAP locales por municipio/horizonte.

Estos artefactos **no son obligatorios para cerrar la frontera base de HU004**. Se consumirán posteriormente cuando HU006/HU007/HU009 implementen persistencia, consulta histórica y explicabilidad. HU004 solo debe evitar bloquear su incorporación futura.

---

## 6. Contratos de dominio HU004

### 6.1 `ChampionMetadata`

El threshold deja de ser una propiedad global obligatoria del Champion.

Contrato objetivo:

```python
@dataclass(frozen=True, slots=True)
class ChampionMetadata:
    name: str
    version: str
    supported_horizons: tuple[str, ...]
    output_type: str
    feature_contract_version: str
    feature_contract_sha256: str
    mlflow_run_id: str | None = None
    artifact_sha256: str | None = None
```

Reglas:

- no almacenar `decision_threshold` global si la fuente puede entregar thresholds diferentes por horizonte;
- si en el futuro un Champion declara un threshold global real, el adapter puede materializarlo en cada `ChampionPrediction`, pero nunca asumirlo;
- `supported_horizons` se deriva de la salida/metadata real.

### 6.2 `ChampionPrediction`

Contrato objetivo:

```python
@dataclass(frozen=True, slots=True)
class ChampionPrediction:
    divipola: str
    municipality: str
    horizon: str
    target_month: str
    output_type: str
    probability: float | None = None
    expected_cases: float | None = None
    risk_score: float | None = None
    label: str | None = None
    decision_threshold: float | None = None
```

`decision_threshold` pertenece a la predicción/horizonte.

Para PR #12:

```text
prediction.threshold
→ ChampionPrediction.decision_threshold
```

### 6.3 `ChampionOutput`

```python
@dataclass(frozen=True, slots=True)
class ChampionOutput:
    reference_month: str
    predictions: tuple[ChampionPrediction, ...]
    metadata: ChampionMetadata
    source_file_sha256: str | None = None
```

`source_file_sha256` puede ser `None` en una adaptación de salida materializada si ese valor no viene de PR #12. HU005 debe adjuntarlo desde la carga mensual cuando el flujo operativo parta de HU002/HU003.

### 6.4 Contrato materializado PR #12

`MaterializedChampionResult` y `MaterializedChampionPrediction` representan de forma inmutable y estricta el contrato de `dashboard_prototipos/JSON-dashboard.md` suministrado por modelado. `MaterializedOutputAdapter.from_result(...)` acepta ese objeto interno o un `Mapping` equivalente y produce `ChampionOutput` sin ejecutar modelos.

Para el contrato probabilístico MVP exige exactamente las claves `68001/T+1`, `68001/T+2`, `76001/T+1`, `76001/T+2`, valida meses, rangos finitos, nombres de municipio y la regla `probability >= threshold → EXCESO`. Cada `prediction.threshold` se mapea a su propio `ChampionPrediction.decision_threshold`.

---

## 7. Contrato de entrada materializada PR #12

HU004 debe definir un modelo interno estricto para validar el objeto recibido desde PR #12.

Forma lógica:

```python
class MaterializedChampionPrediction:
    divipola: str
    municipality: str
    horizon: Literal["T+1", "T+2"]
    target_month: str
    probability: float | None
    threshold: float | None
    label: str | None

class MaterializedChampionResult:
    model_name: str
    model_version: str
    reference_month: str
    feature_contract_version: str
    feature_contract_sha256: str
    output_type: str
    predictions: tuple[MaterializedChampionPrediction, ...]
```

Puede implementarse con dataclass/Pydantic, pero debe ser framework-agnostic respecto al modelo.

### Reglas de validación

Para `output_type == "probability"`:

- `probability` debe existir y estar en `[0,1]`;
- `threshold` debe existir si el `label` deriva de threshold;
- `label` debe ser consistente con la comparación contractual;
- para PR #12 actual, la regla observada es `probability >= threshold`;
- no hardcodear `0.61`; consumir el valor entregado por cada predicción.

---

## 8. Interfaces de integración

### 8.0 Frontera única para HU005+

```python
class ChampionService(Protocol):
    def produce(self, context: ChampionOperationalContext) -> ChampionOutput: ...
```

`ChampionOperationalContext` solo contiene datos operacionales: periodo, hash fuente y, cuando existe, la carga validada de HU002. No expone `ChampionInput` ni `MaterializedChampionResult`. `build_champion_service` selecciona una estrategia y sus resolvers inyectados. Dentro de HU004, `MaterializedChampionResultProvider` obtiene el resultado PR12 o `ChampionInputProvider` delega la preparación a HU003. No hay fallback.

Para ambos modos, el contexto debe permitir recuperar el contrato efectivo del input (`feature_contract_version` + `feature_contract_sha256`) o construirlo mediante HU003. La estrategia activa no puede aceptar un `ChampionOutput` hasta comprobar igualdad exacta con la metadata del Champion.

### 8.1 Puerto estable

```python
class ChampionAdapter(Protocol):
    def metadata(self) -> ChampionMetadata: ...
    def predict(self, inference_input: ChampionInput) -> ChampionOutput: ...
```

Se conserva para el camino de inferencia directa.

### 8.2 Adapter de salida materializada

Agregar una frontera equivalente a:

```python
class MaterializedOutputAdapter:
    def from_result(
        self,
        result: MaterializedChampionResult | Mapping[str, object],
        *,
        source_file_sha256: str | None = None,
    ) -> ChampionOutput:
        ...
```

Esta clase no ejecuta modelos. Solo valida y normaliza una salida ya producida.

### 8.3 Provider opcional

Para desacoplar HU004 de `scripts/generate_champion_output.py`, puede definirse:

```python
class ChampionResultProvider(Protocol):
    def get_result(self, reference_month: str) -> MaterializedChampionResult: ...
```

Implementaciones futuras posibles:

```text
PythonCallableChampionResultProvider
JsonFileChampionResultProvider
PackageChampionResultProvider
```

No usar subprocess como contrato principal si el código de PR #12 puede exponer una función Python estable. Subprocess solo sería aceptable como transición/demo explícita.

---

## 9. Compatibilidad exacta con PR #12

HU004 debe mapear:

```text
PR12 model_name                 → ChampionMetadata.name
PR12 model_version              → ChampionMetadata.version
PR12 reference_month            → ChampionOutput.reference_month
PR12 feature_contract_version   → ChampionMetadata.feature_contract_version
PR12 feature_contract_sha256    → ChampionMetadata.feature_contract_sha256
PR12 output_type                → ChampionMetadata.output_type
PR12 prediction.divipola        → ChampionPrediction.divipola
PR12 prediction.municipality    → ChampionPrediction.municipality
PR12 prediction.horizon         → ChampionPrediction.horizon
PR12 prediction.target_month    → ChampionPrediction.target_month
PR12 prediction.probability     → ChampionPrediction.probability
PR12 prediction.threshold       → ChampionPrediction.decision_threshold
PR12 prediction.label           → ChampionPrediction.label
```

### Invariantes PR #12 para MVP

Cuando `supported_horizons == ("T+1", "T+2")`, el conjunto exacto esperado es:

```text
("68001", "T+1")
("68001", "T+2")
("76001", "T+1")
("76001", "T+2")
```

No depender del orden del array.

### Gate de feature contract

Antes de devolver `ChampionOutput` como válido para un run debe cumplirse:

```text
champion.feature_contract_version == input.feature_contract_version
champion.feature_contract_sha256   == input.feature_contract_sha256
```

La comparación aplica tanto a Modo A como a Modo B. En el modo materializado, no basta con que el JSON sea internamente válido: debe demostrarse que fue generado con el mismo contrato con el que la API validó/preparó la entrada operacional.

---

## 10. Threshold por horizonte — decisión obligatoria

La implementación anterior de HU004 utilizaba:

```text
ChampionMetadata.decision_threshold
```

como valor único global.

Esa decisión queda **revocada** porque PR #12 entrega `threshold` dentro de cada predicción y puede existir un valor diferente para T+1 y T+2.

La nueva regla es:

```text
prediction.threshold
→ ChampionPrediction.decision_threshold
```

Nunca:

```text
metadata.threshold
→ copiar a todas las predicciones
```

salvo que la fuente contractual indique explícitamente que el threshold es global y único.

---

## 11. Validaciones obligatorias

Antes de entregar `ChampionOutput`, HU004 debe validar:

1. `reference_month` con formato `YYYY-MM`;
2. `target_month` matemáticamente consistente con horizonte;
3. `divipola` solo `68001`/`76001` para MVP;
4. no duplicados `(divipola, horizon)`;
5. horizontes solo T+1/T+2;
6. presencia de cuatro combinaciones cuando ambos horizontes estén declarados;
7. `probability` finita y `[0,1]` cuando output sea probabilístico;
8. `threshold` finito y `[0,1]` cuando exista;
9. `label` solo valores contractuales soportados;
10. consistencia `probability`, `threshold`, `label`;
11. `feature_contract_version` no vacío;
12. `feature_contract_sha256` no vacío;
13. `model_name/model_version` no vacíos;
14. ausencia de campos ML inventados;
15. igualdad exacta entre `feature_contract_version` del Champion y del input/contexto del run;
16. igualdad exacta entre `feature_contract_sha256` del Champion y del input/contexto del run.

Error por salida materializada inválida o mismatch contractual debe producir un run fallido antes de persistencia exitosa.

---

## 12. Manejo de errores

### `CHAMPION_NOT_READY`

Usar cuando el provider/artefacto necesario para obtener la salida no esté disponible.

### `CHAMPION_INPUT_INVALID`

Usar para incompatibilidades del contrato de entrada, incluyendo mismatch de `feature_contract_version` o `feature_contract_sha256` entre el input efectivo del run y la metadata del Champion. El detalle debe identificar `reason=feature_contract_mismatch` y puede incluir valores esperados/recibidos sin exponer secretos.

### `INFERENCE_FAILED`

Usar cuando la ejecución directa o la obtención de la salida Champion falla por causa técnica no contractual.

### Salida materializada inválida

Si `ChampionResult` existe pero viola el contrato, HU004 debe fallar de forma controlada. Un mismatch de feature contract no debe degradarse a warning ni permitirse llegar a `COMPLETED`.

---

## 13. Fuera de alcance

HU004 no evalúa ni modifica:

- entrenamiento;
- selección de modelos;
- tuning;
- calidad epidemiológica del target;
- preparación de features del equipo de modelado;
- calibración del modelo;
- corrección de posibles fugas de datos;
- persistencia de snapshots;
- historial HTTP;
- frontend Lovable;
- autenticación;
- infraestructura EC2;
- DVC pull por request;
- MLflow online por request;
- generación de SHAP;
- ResultMapper completo de HU005+.

HU004 acepta como verdad de integración las salidas que PR #12 declara solo cuando además son compatibles con el contrato efectivo del input del run.

---

## 14. Plan de implementación DWP actualizado

### T01 — Mantener baseline HU001–HU003

Ejecutar suite API antes de cambios.

### T02 — Auditar contrato de salida PR #12

Usar `JSON-dashboard.md` y `generate_champion_output.py` como referencia concreta de salida.

### T03 — Refactorizar `ChampionMetadata`

Eliminar dependencia de un threshold global.

### T04 — Refactorizar `ChampionPrediction`

Agregar/preservar `municipality` y threshold por predicción.

### T05 — Mantener adapter ejecutable

Conservar `LazyChampionAdapter` para futura integración directa, corrigiendo su manejo de threshold para que el runtime pueda entregar threshold por predicción.

### T06 — Implementar `MaterializedChampionResult`

Contrato interno estricto para la salida PR #12.

### T07 — Implementar `MaterializedOutputAdapter`

Mapear PR #12 → `ChampionOutput` sin ejecutar el modelo.

### T08 — Validar horizonte/mes/municipio/duplicados

No depender del orden del JSON.

### T09 — Validar probability/threshold/label

No recalibrar, no recomputar thresholds, no usar 0.5/0.61 hardcodeados.

### T10 — Tests PR #12

Agregar fixtures que reproduzcan exactamente la estructura de `ChampionResult` con thresholds T+1 y T+2 distintos.

### T11 — Test de compatibilidad de thresholds

Demostrar que T+1 y T+2 pueden conservar thresholds diferentes.

### T12 — Test materialized → ChampionOutput

Validar cuatro predicciones correctas para Bucaramanga/Cali.

### T13 — Test de salida inválida

Cubrir duplicados, mes incorrecto, probabilidad fuera de rango, label inconsistente y combinación faltante.

### T14 — Regresión API

```bash
python -m pytest api/tests -q
python -m compileall -q api/app api/tests
python -m pip check
```

### T15 — Actualizar evidencia DWP

Registrar resultados reales y dejar la dependencia AWS separada.

### T16 — Deployment AWS

Pendiente Mauricio: materializar el mecanismo acordado y ejecutar smoke test real en EC2.

### T17 — Handoff HU005

HU005 debe invocar exclusivamente `ChampionService.produce(context)` y recibir `ChampionOutput`, sin distinguir si vino de ejecución directa o de salida PR #12.

### T18 — Implementar gate de feature contract

Comparar versión y SHA-256 del contrato efectivo del input contra la metadata del Champion en ambos providers. Ante mismatch, fallar de forma controlada antes de mapping/persistencia.

### T19 — Tests del gate

Cubrir al menos: match exacto PASS; versión distinta FAIL; hash distinto FAIL; ambos distintos FAIL; latest previo preservado; ningún snapshot nuevo `COMPLETED`.

---

## 15. Criterios de aceptación actualizados CA01–CA26

- **CA01:** suite baseline permanece verde.
- **CA02:** `ChampionAdapter` sigue desacoplado de frameworks ML.
- **CA03:** `MaterializedOutputAdapter` consume la estructura PR #12.
- **CA04:** `ChampionMetadata` no obliga a un threshold global.
- **CA05:** threshold se conserva por predicción/horizonte.
- **CA06:** T+1 y T+2 pueden tener thresholds diferentes sin pérdida de información.
- **CA07:** probability se preserva exactamente salvo serialización numérica normal.
- **CA08:** label se preserva y valida contra threshold.
- **CA09:** Bucaramanga/Cali quedan inequívocamente asociadas.
- **CA10:** T+1/T+2 quedan inequívocamente asociados.
- **CA11:** `target_month` se valida matemáticamente.
- **CA12:** no se aceptan duplicados `(divipola,horizon)`.
- **CA13:** si se esperan ambos horizontes deben existir cuatro predicciones.
- **CA14:** no se inventa un threshold ausente.
- **CA15:** no se inventa T+2.
- **CA16:** output no probabilístico no se convierte a probability.
- **CA17:** materialized adapter no ejecuta DVC/S3/MLflow/modelo.
- **CA18:** ejecución directa conserva load-once.
- **CA19:** errores se saneán sin secretos/path internos.
- **CA20:** tests funcionan sin AWS/red.
- **CA21:** `ChampionService`, `ChampionOperationalContext` y `ChampionOutput` son la frontera de HU005.
- **CA22:** ambos providers son intercambiables para el mismo consumer y no existe fallback.
- **CA23:** match exacto de feature contract permite continuar.
- **CA24:** mismatch de versión impide `COMPLETED`.
- **CA25:** mismatch de SHA-256 impide `COMPLETED`.
- **CA26:** un mismatch conserva latest previo y no persiste un snapshot exitoso nuevo.

---

## 16. Autovalidaciones actualizadas AV01–AV24

- **AV01:** baseline API PASS.
- **AV02:** imports de puerto sin ML frameworks.
- **AV03:** contratos inmutables.
- **AV04:** fixture PR #12 válido se acepta estructuralmente.
- **AV05:** thresholds T+1/T+2 distintos se preservan.
- **AV06:** cuatro claves municipio/horizonte exactas.
- **AV07:** array desordenado produce output ordenado/estable o inequívoco.
- **AV08:** duplicado se rechaza.
- **AV09:** combinación faltante se rechaza cuando se esperan ambos horizontes.
- **AV10:** target_month incorrecto se rechaza.
- **AV11:** probability fuera de rango se rechaza.
- **AV12:** threshold fuera de rango se rechaza.
- **AV13:** label inconsistente se rechaza.
- **AV14:** sin threshold no se fabrica threshold/label.
- **AV15:** T+1-only no produce T+2.
- **AV16:** camino materializado no requiere modelo/AWS/red.
- **AV17:** camino ejecutable conserva load-once.
- **AV18:** suite API completa PASS.
- **AV19:** compileall/pip check PASS.
- **AV20:** diff no adelanta infraestructura.
- **AV21:** contrato idéntico PASS.
- **AV22:** versión distinta produce `CHAMPION_INPUT_INVALID`/FAILED.
- **AV23:** SHA distinto produce `CHAMPION_INPUT_INVALID`/FAILED.
- **AV24:** latest previo y conteos SQLite permanecen consistentes tras mismatch.

---

## 17. Definición de terminado — desarrollo

HU004 estuvo implementada para adaptación estructural PR12, pero el hallazgo HU010 reabre un ajuste contractual específico. HU004 vuelve a `[COMPLETADA — DESARROLLO]` solo cuando el gate de feature contract esté implementado y probado para la estrategia materializada y la ejecutable equivalente.

---

## 18. Definición de terminado — deployment

La validación AWS se cierra cuando en EC2 pueda demostrarse al menos uno de estos caminos reales:

```text
A) ChampionInput → Champion ejecutable → ChampionOutput
```

ó

```text
B) ChampionResult PR12 real → MaterializedOutputAdapter → ChampionOutput
```

En ambos casos se debe demostrar Bucaramanga/Cali × T+1/T+2 con probability, threshold y label reales cuando esos campos formen parte del contrato, y feature contract idéntico al input operacional.

---

## 19. Handoff a HU005

HU005 no debe consumir directamente scripts, pickle, JSON específico de PR #12 ni XGBoost.

Debe recibir exclusivamente:

```text
ChampionOutput
```

y a partir de él coordinar:

```text
run_id
estado
ResultMapper
persistencia
PredictionSnapshot
respuesta API
```

El `ChampionOutput` recibido debe haber superado previamente el gate de compatibilidad contractual de HU004.

---

## 20. Decisión vigente de integración — precedencia sobre secciones anteriores

Esta sección fija la decisión arquitectónica vigente para evitar ambigüedad entre los dos modos descritos en HU004.

### MVP: Modo B obligatorio

Para el MVP académico BIOMAC, la integración primaria y requerida es:

```text
PR12 ChampionResult / JSON
→ MaterializedOutputAdapter
→ feature contract gate
→ ChampionOutput
```

La razón es práctica: PR #12 ya entrega las salidas que necesita el dashboard (`probability`, `threshold`, `label`, `target_month`, municipio y horizonte). HU004 debe aprovechar ese contrato en lugar de duplicar la ejecución del modelo, pero no puede aceptar una salida generada bajo otro contrato de features.

### Evolución futura: Modo A opcional

El camino ejecutable se conserva como alternativa futura:

```text
ChampionInput
→ ExecutableChampionAdapter
→ feature contract gate
→ ChampionOutput
```

Implementar o desplegar Modo A **no es requisito para cerrar el MVP**. Cuando se adopte, debe reemplazar al provider activo mediante composición/configuración, no mediante cambios en HU005+.

### No existe fallback automático A → B

Los modos A y B son estrategias intercambiables, no una cadena de contingencia. Está prohibido intentar A y, ante error, cambiar silenciosamente a B. Un fallo del provider activo debe producir el error contractual correspondiente para preservar trazabilidad.

### Contrato estable hacia HU005+

Desde HU005 en adelante, ninguna HU puede depender de:

- `ChampionResult` específico de PR #12;
- archivos JSON físicos;
- `generate_champion_output.py`;
- pickle/XGBoost;
- `.whl`;
- `ChampionInput` como detalle del mecanismo de serving.

La única operación ML permitida para HU005+ es:

```text
ChampionService.produce(operational_context) → ChampionOutput
```

En consecuencia, cambiar de Modo B a Modo A debe limitarse a HU004 y a la composición/configuración de dependencias. `ResultMapper`, persistencia, API, dashboard e historial deben permanecer sin refactoring estructural.

---

## 21. Hallazgo HU010 — incompatibilidad real detectada

La ejecución HTTP real con Uvicorn y SQLite completó técnicamente el flujo, pero evidenció que la implementación actual acepta metadata contractual distinta:

```text
Champion JSON
feature_contract_version = pr12-f5a2d39
feature_contract_sha256   = 3af245ede70851d1616439d80441e2ad6f5d3f6465b9798d6b67fed3adb3e3dc

CSV/API vigente
feature_contract_version = pr12-74e385c3
feature_contract_sha256   = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

El adapter preserva ambas metadata, pero hoy no demuestra que la predicción corresponda al mismo contrato de entrada. Por ello **HTTP 201 + cuatro predicciones no basta para cerrar HU004/HU010**. La corrección requerida es el gate documentado en las secciones 9, 11 y 12; no se deben reescribir hashes ni editar el JSON para forzar coincidencia.