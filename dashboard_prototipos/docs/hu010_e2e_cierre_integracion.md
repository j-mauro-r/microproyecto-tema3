# HU010 — Pruebas E2E y cierre de integración BIOMAC

**Estado:** `[COMPLETADA — E2E LOCAL Y CHAMPION REAL APROBADOS]`  
**Identificador:** `HU-INT-010`  
**Prioridad:** ALTA  
**Dependencias:** HU001–HU009 `[COMPLETADAS]`  
**Ámbito vigente:** Entregable 2, validación local reproducible  
**Frontend objetivo:** `dashboard_prototipos/dengue-watch-pro`  
**Backend objetivo:** `/api/v2`  
**Champion objetivo:** salida materializada real integrada desde PR12  

## 1. Objetivo de cierre

HU010 demuestra que el flujo operativo del MVP funciona de extremo a extremo sin mocks en el escenario principal:

```text
CSV mensual válido
→ POST /api/v2/monthly-runs
→ validación HU002
→ ChampionInput HU003
→ ChampionService + feature contract gate HU004
→ orquestación HU005
→ persistencia SQLite HU006
→ latest/history/run HU007
→ consumo HTTP del dashboard HU008
→ metadata/calidad HU009
```

El alcance de cierre es local-first. AWS/deployment remoto no es gate del Entregable 2.

## 2. Precondición contractual resuelta

El bloqueo anterior por `feature_contract_mismatch` fue corregido en PR12 y el cambio quedó incorporado en `main`.

Contrato vigente y verificado:

```text
feature_contract_version = pr12-74e385c3
feature_contract_sha256  = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

El Champion real y la API declaran exactamente esos mismos identificadores.

La cobertura negativa se conserva: cualquier versión o SHA distinto produce `CHAMPION_INPUT_INVALID`, run `FAILED` y cero snapshot exitoso nuevo.

## 3. Evidencia Champion real

El escenario principal utiliza `runtime/functional/champion_output.json`, derivado de la salida real del Champion, con corte `2025-12`.

Predicciones esperadas y preservadas:

| Municipio | Horizonte | Target | Probability | Threshold | Label |
|---|---|---|---:|---:|---|
| Bucaramanga | T+1 | 2026-01 | 0.7347 | 0.34 | EXCESO |
| Bucaramanga | T+2 | 2026-02 | 0.6724 | 0.27 | EXCESO |
| Cali | T+1 | 2026-01 | 0.0132 | 0.34 | NO_EXCESO |
| Cali | T+2 | 2026-02 | 0.0150 | 0.27 | NO_EXCESO |

No se recalculan probabilidades, thresholds ni labels dentro del test.

## 4. Resultado E2E real

El test `api/tests/test_e2e_champion_real.py` valida:

```text
POST /api/v2/monthly-runs
→ 201
→ run.status = COMPLETED
→ reference_month = 2025-12
→ 4 predicciones
→ persistencia SQLite
→ GET /api/v2/predictions/latest = 200
→ latest.run_id == run recién completado
```

También comprueba persistencia de enrichments existentes y correspondencia de las cuatro predicciones contra el JSON real.

## 5. Cobertura negativa obligatoria

El cierre no elimina las pruebas de incompatibilidad contractual. Permanecen cubiertas en:

- `api/tests/test_champion_service.py`;
- `api/tests/test_champion_adapter.py`.

Se valida que mismatch de versión, SHA o ambos:

```text
→ CHAMPION_INPUT_INVALID
→ stage INFERENCING
→ FAILED
→ no snapshot COMPLETED nuevo
```

## 6. Resultados de pruebas

Evidencia local final registrada:

```text
pytest -q api/tests/test_e2e_champion_real.py
→ 2 passed

E2E local + Champion real
→ 10 passed

pytest -q api/tests
→ 216 passed
```

Controles adicionales reportados:

```text
git diff --check → limpio
```

Existe una advertencia de deprecación preexistente Starlette/httpx que no afecta el resultado funcional.

## 7. Criterios de aceptación cerrados

Se consideran aprobados para el alcance API/local:

1. health y composición local reproducible;
2. POST válido con contrato compatible produce `201 COMPLETED`;
3. Bucaramanga y Cali quedan persistidas con T+1/T+2;
4. probability/threshold/label coinciden con Champion real;
5. `latest` devuelve el run recién completado;
6. persistencia SQLite conserva el snapshot;
7. feature contract del Champion coincide con el input/API;
8. mismatch contractual sigue fallando de forma controlada;
9. read-only no requiere inferencia nueva;
10. la suite API completa permanece verde.

## 8. Alcance no bloqueante posterior

No son requisito para mantener HU010 cerrada dentro del Entregable 2:

- deployment AWS/EC2;
- infraestructura productiva;
- autenticación/RBAC;
- MLflow/DVC/S3 durante requests;
- reentrenamiento;
- SHAP online;
- automatización CI inexistente actualmente en GitHub.

Estos elementos se gestionan como evolución posterior.

## 9. Definición de terminado

HU010 queda **COMPLETADA** porque el flujo API real con el Champion corregido pasó el happy path, la persistencia y `latest`, mientras la cobertura negativa del feature-contract gate continúa vigente.

**Veredicto:**

```text
REAL CHAMPION CONTRACT MATCH: APROBADO
REAL CHAMPION E2E: APROBADO
API REGRESSION: APROBADO
PRUEBAS FUNCIONALES API: CERRADAS
```
