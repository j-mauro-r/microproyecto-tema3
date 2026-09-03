# HU004 — Evidencia de implementación del Champion Adapter

**Fecha:** 2026-09-03  
**Rama:** `docs/hu004-champion-adapter`  
**Estado actual:** `[COMPLETADA — DESARROLLO]`
**AWS:** no ejecutado.

## Resultado de la primera implementación

Se implementaron dos estrategias independientes que convergen en la misma frontera:

```text
PR12 ChampionResult → MaterializedOutputAdapter → ChampionOutput  (primaria MVP)
ChampionInput → LazyChampionAdapter → ChampionOutput             (alternativa futura)
```

No existe fallback entre ellas. La ruta materializada valida y mapea el resultado
contractual entregado por modelado sin ejecutar modelos. La composición ejecutable sin
provider configurado conserva `CHAMPION_NOT_READY`.

## Auditoría del Champion

Se auditó PR #12 hasta `2f874229` y se tomó, por decisión arquitectónica posterior, su
`dashboard_prototipos/JSON-dashboard.md` y `scripts/generate_champion_output.py` como
contrato de integración suministrado por modelado. El resultado declara metadata de
modelo/feature contract y cuatro predicciones probabilísticas con threshold por
horizonte. HU004 no copia ni ejecuta el generador: consume su `ChampionResult`.

Dependencias pendientes solo para habilitar la estrategia ejecutable futura:

- paquete `.whl` o artefactos T+1/T+2 aprobados y materializables;
- entry point de carga/predicción estable compatible con `ChampionRuntime`;
- nombre, versión, horizontes y tipo de output contractuales;
- `feature_contract_version` y `feature_contract_sha256` coincidentes con HU003;
- threshold/regla de clase por horizonte, o confirmación explícita de ausencia;
- checksum del artefacto y metadata MLflow si aplica.

## Estado T01–T17

| Tarea | Estado | Evidencia |
|---|---|---|
| T01 | PASS | suite base: 71 pruebas antes del cambio |
| T02 | PASS | auditoría de árbol actual y PR #12 documentada |
| T03 | PASS | contratos inmutables en `api/app/champion/models.py` |
| T04 | PASS | `ChampionAdapter` Protocol en `port.py` |
| T05 | PASS | versión y SHA se validan antes de `runtime.predict` |
| T06 | PASS | adapter materializado MVP y loader ejecutable alternativo; sin fallback |
| T07 | PASS | lazy loading protegido por `Lock`, una carga por adapter |
| T08 | PASS | mapeo PR12 explícito, sin depender del orden del array |
| T09 | PASS | errores estables y saneados |
| T10 | PASS | 45 pruebas HU004 offline (11 ejecutables + 34 materializadas) |
| T11 | PASS | suite completa y gates registrados abajo |
| T12 | PASS | este documento |
| T13 | PENDIENTE/MANUAL | requiere entrega/materialización final de modelado |
| T14 | PENDIENTE/MANUAL AWS | no ejecutada por instrucción |
| T15 | PENDIENTE/MANUAL AWS | requiere Champion real en EC2 |
| T16 | PENDIENTE/MANUAL AWS | no se levantó Uvicorn/infraestructura EC2 |
| T17 | PASS | diff limitado a HU004, tests y evidencia |

## Criterios CA01–CA20

| Criterio | Estado | Nota |
|---|---|---|
| CA01 | PASS | baseline 71/71 |
| CA02 | PASS | cada estrategia recibe solo su contrato y ambas emiten `ChampionOutput` |
| CA03 | PASS | puerto/modelos sin tipos ML |
| CA04 | PASS | metadata del ChampionResult PR12 se preserva exactamente |
| CA05 | PASS | versión/SHA compatibles permiten inferencia fake |
| CA06 | PASS | ambos mismatches bloquean con `CHAMPION_INPUT_INVALID` |
| CA07 | PASS | mapping explícito 68001/Bucaramanga, 76001/Cali |
| CA08 | PASS | fake multi-horizon genera claves explícitas |
| CA09 | PASS | fake T+1-only produce solo dos salidas T+1 |
| CA10 | PASS | probabilidades se preservan sin transformación |
| CA11 | PASS | adapter no convierte otros outputs a probabilidad |
| CA12 | PASS | thresholds distintos T+1/T+2 se preservan por predicción |
| CA13 | PASS | sin threshold, threshold y label quedan `None` |
| CA14 | PASS | contador de loader permanece en uno |
| CA15 | PASS | default productivo devuelve `CHAMPION_NOT_READY` |
| CA16 | PASS | fallo runtime devuelve `INFERENCE_FAILED` saneado |
| CA17 | PASS | camino de predicción no usa DVC/S3/MLflow/red |
| CA18 | PASS | pruebas focales completamente offline |
| CA19 | PASS | AWS y materialización quedan separadas |
| CA20 | PASS | ambas estrategias entregan únicamente `ChampionOutput` a HU005 |

## Autovalidaciones AV01–AV18

| AV | Estado | Resultado |
|---|---|---|
| AV01 | PASS | suite base verde |
| AV02 | PASS | imports de frontera inspeccionados |
| AV03 | PASS | asignación a output congelado falla |
| AV04 | PASS | mismatch de versión bloqueado |
| AV05 | PASS | mismatch de hash bloqueado |
| AV06 | PASS | orden y asociación municipal verificados |
| AV07 | PASS | cuatro salidas T+1/T+2 |
| AV08 | PASS | dos salidas T+1, cero T+2 |
| AV09 | PASS | 0.72/0.34 preservados |
| AV10 | PASS | 0.61 preservado, sin fallback 0.5 |
| AV11 | PASS | loader ausente produce NOT READY |
| AV12 | PASS | excepción runtime produce INFERENCE_FAILED |
| AV13 | PASS | carga única en tres usos |
| AV14 | PASS | suite sin credenciales ni red |
| AV15 | PASS | 116 pruebas pasan |
| AV16 | PASS | compileall exitoso |
| AV17 | PASS | sin dependencias rotas |
| AV18 | PASS | alcance auditado, sin HU005+ ni secretos |

## Comandos y resultados exactos

```text
python -m pytest api/tests -q
→ no ejecutable: `.python-version` solicita Python 3.13.12 no instalado.

.venv/bin/python -m pytest api/tests -q  (baseline)
→ 71 passed, 1 warning in 0.46s

.venv/bin/python -m pytest api/tests/test_champion_adapter.py -q
→ 11 passed, 1 warning in 0.02s

.venv/bin/python -m pytest api/tests/test_materialized_champion_adapter.py -q
→ 34 passed, 1 warning in 0.16s

.venv/bin/python -m pytest api/tests -q
→ 116 passed, 1 warning in 0.62s

.venv/bin/python -m compileall -q api/app api/tests
→ exit 0, sin salida

.venv/bin/python -m pip check
→ No broken requirements found.
```

## Archivos cambiados

- `api/app/champion/__init__.py`
- `api/app/champion/adapter.py`
- `api/app/champion/models.py`
- `api/app/champion/materialized.py`
- `api/app/champion/port.py`
- `api/tests/test_champion_adapter.py`
- `api/tests/test_materialized_champion_adapter.py`
- `dashboard_prototipos/docs/hu004_evidencia_implementacion.md`

Estos resultados, junto con la implementación materializada y sus 34 pruebas adicionales,
constituyen el cierre de desarrollo de HU004.

---

## Nuevo descubrimiento — PR #12

Una auditoría posterior del PR #12 confirmó que el equipo de modelado ya entrega una salida materializable explícita mediante:

```text
scripts/generate_champion_output.py
```

con contrato documentado en:

```text
dashboard_prototipos/JSON-dashboard.md
```

La salida `ChampionResult` contiene:

```text
model_name
model_version
reference_month
feature_contract_version
feature_contract_sha256
output_type
predictions[]
```

Y para cada predicción:

```text
divipola
municipality
horizon
target_month
probability
threshold
label
```

PR #12 valida cuatro combinaciones para el MVP:

```text
68001 T+1
68001 T+2
76001 T+1
76001 T+2
```

Por tanto, HU004 debe ser compatible de forma directa con este entregable y no esperar exclusivamente un futuro paquete `.whl`.

---

## Hallazgo técnico que reabre HU004

La primera implementación modeló:

```text
ChampionMetadata.decision_threshold
```

como un único threshold global.

PR #12 entrega:

```text
prediction.threshold
```

por predicción/horizonte.

Esto significa que T+1 y T+2 pueden conservar valores distintos y HU004 no debe copiar un threshold global a todas las predicciones.

### Nueva decisión

```text
PR12 prediction.threshold
→ ChampionPrediction.decision_threshold
```

El threshold deja de ser una propiedad global obligatoria del Champion.

---

## Nueva frontera requerida

HU004 debe soportar dos modos:

```text
A) ChampionInput
   → ExecutableChampionAdapter
   → ChampionOutput
```

```text
B) PR12 ChampionResult / JSON
   → MaterializedOutputAdapter
   → ChampionOutput
```

HU005 debe consumir únicamente `ChampionOutput` sin conocer el modo utilizado.

---

## Estado de tareas actualizado

| Tarea | Estado | Nota |
|---|---|---|
| baseline HU001–HU003 | PASS | 71 pruebas previas |
| contratos HU004 | PASS | threshold refactorizado por predicción |
| `ChampionAdapter` ejecutable | PASS | conserva compatibilidad y threshold por predicción |
| load-once | PASS | no cambia |
| feature contract validation | PASS | no cambia |
| errores base | PASS | no cambia |
| auditoría PR #12 | PASS | salida materializable confirmada |
| contrato `MaterializedChampionResult` | PASS | dataclasses estrictas e inmutables |
| `MaterializedOutputAdapter` | PASS | acepta objeto interno o Mapping PR12 |
| thresholds distintos T+1/T+2 | PASS | 0.61/0.67 de fixture preservados independientemente |
| validación PR12 municipio/horizonte/mes | PASS | combinaciones exactas y meses validados |
| regresión completa posterior | PASS | 116 pruebas API |
| deployment EC2 | PENDIENTE MAURICIO | sin cambios |
| smoke test real EC2 | PENDIENTE MAURICIO | sin cambios |

---

## Criterio actualizado de cierre Codex

La parte de desarrollo de HU004 se declara `[COMPLETADA — DESARROLLO]` al demostrarse:

```text
ChampionResult PR12 válido
→ MaterializedOutputAdapter
→ ChampionOutput
```

preservando correctamente:

- Bucaramanga/Cali;
- T+1/T+2;
- `target_month`;
- `probability`;
- threshold **por horizonte/predicción**;
- `label`;
- metadata del Champion;
- feature contract.

También debe conservarse la compatibilidad del camino ejecutable existente.

---

## Pruebas adicionales ejecutadas

La implementación incluye pruebas para:

1. fixture idéntico a la estructura de `ChampionResult` de PR #12;
2. cuatro combinaciones municipio/horizonte;
3. T+1 y T+2 con thresholds diferentes;
4. preservación exacta de probability;
5. preservación exacta de label;
6. array de predicciones desordenado;
7. predicción duplicada;
8. combinación faltante;
9. `target_month` incompatible con horizonte;
10. probability fuera de rango;
11. threshold fuera de rango;
12. label inconsistente;
13. output materializado sin acceso AWS/DVC/MLflow/modelo;
14. regresión del adapter ejecutable/load-once.

---

## Tareas AWS permanecen separadas

Mauricio conserva las tareas de infraestructura:

1. desplegar/configurar EC2;
2. instalar/materializar el mecanismo real acordado;
3. ejecutar smoke test con salida real PR #12 o Champion ejecutable;
4. levantar FastAPI/Uvicorn;
5. validar readiness y comunicación posterior.

Estas tareas no deben ser simuladas por Codex.

---

## Conclusión de evidencia

La implementación conserva el Champion ejecutable y añade la integración materializada
primaria del MVP. Por tanto:

```text
HU004 desarrollo = COMPLETADA
```

AWS, deployment y smoke tests reales permanecen separados y pendientes de Mauricio.

---

## Decisión arquitectónica registrada para el MVP

Se fija formalmente la siguiente decisión:

```text
MVP = Modo B
PR12 ChampionResult
→ MaterializedOutputAdapter
→ ChampionOutput
```

El `ExecutableChampionAdapter` queda como **alternativa futura compatible**, no como requisito de cierre actual.

### No es fallback

Los modos A y B no se encadenan. No debe existir lógica que intente un provider y, si falla, cambie silenciosamente al otro. El provider activo se selecciona por configuración/composición y cualquier fallo debe ser observable.

### Protección de HU005+

La decisión clave para evitar refactor futuro es:

```text
HU005+ depende solo de ChampionOutput
```

Por tanto, HU005, persistencia, API, dashboard, historial y explicabilidad no deben importar ni conocer `ChampionResult`, JSON PR #12, `generate_champion_output.py`, XGBoost, pickle, `.whl` o `ChampionInput` como detalle de serving.

Cuando se implemente Modo A en el futuro, la sustitución debe ocurrir únicamente dentro de HU004/composición. Si una HU posterior requiere cambios estructurales por ese reemplazo, se considerará una violación de esta decisión arquitectónica.
