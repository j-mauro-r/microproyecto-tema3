# HU004 — Evidencia de implementación del Champion Adapter

**Fecha:** 2026-09-03  
**Rama:** `docs/hu004-champion-adapter`  
**Estado actual:** `[EN AJUSTE — COMPATIBILIDAD PR12]`  
**AWS:** no ejecutado.

## Resultado de la primera implementación

La primera versión de HU004 implementó correctamente una frontera ejecutable:

```text
ChampionInput
→ LazyChampionAdapter
→ ChampionRuntime
→ ChampionOutput
```

con contratos framework-agnostic, validación del feature contract, load-once, errores controlados y pruebas offline.

Resultados obtenidos en esa iteración:

```text
baseline API: 71 passed
HU004 focal: 11 passed
suite API final: 82 passed
compileall: PASS
pip check: PASS
```

Estos resultados continúan siendo evidencia válida de la primera iteración, pero **ya no constituyen por sí solos el cierre final de HU004** debido al nuevo descubrimiento de integración descrito abajo.

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
| contratos HU004 iniciales | PASS PARCIAL | requieren refactor de threshold |
| `ChampionAdapter` ejecutable | PASS PARCIAL | conservar, ajustar threshold por predicción |
| load-once | PASS | no cambia |
| feature contract validation | PASS | no cambia |
| errores base | PASS | no cambia |
| auditoría PR #12 | PASS | salida materializable confirmada |
| contrato `MaterializedChampionResult` | PENDIENTE CODEX | nueva necesidad |
| `MaterializedOutputAdapter` | PENDIENTE CODEX | nueva necesidad |
| thresholds distintos T+1/T+2 | PENDIENTE CODEX | nuevo test obligatorio |
| validación PR12 municipio/horizonte/mes | PENDIENTE CODEX | nuevo alcance |
| regresión completa posterior | PENDIENTE CODEX | ejecutar tras ajuste |
| deployment EC2 | PENDIENTE MAURICIO | sin cambios |
| smoke test real EC2 | PENDIENTE MAURICIO | sin cambios |

---

## Criterio actualizado de cierre Codex

La parte de desarrollo de HU004 solo podrá volver a declararse `[COMPLETADA — DESARROLLO]` cuando se demuestre:

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

## Nuevas pruebas requeridas

La siguiente implementación Codex debe agregar como mínimo pruebas para:

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

La implementación inicial fue técnicamente válida para un Champion ejecutable, pero la auditoría actualizada de PR #12 reveló una integración más directa y útil para el dashboard.

Por esa razón:

```text
HU004 desarrollo = REABIERTA PARA AJUSTE PR12
```

El cierre anterior queda supersedido hasta implementar y probar `MaterializedOutputAdapter` y threshold por predicción/horizonte.