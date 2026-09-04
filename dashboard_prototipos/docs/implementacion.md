# BIOMAC — Plan de implementación del flujo operativo de predicción

**Estado:** MVP técnico local implementado y pruebas funcionales API cerradas  
**Versión:** `1.3.0`  
**Fuente arquitectónica:** `arquitectura.md`  
**Contrato API:** `API-sign.md`  
**Diccionario:** `diccionario-de-datos.md`  
**Alcance vigente:** Entregable 2, ejecución y validación local reproducible  

> Este documento resume el estado de HU001–HU010. Las HU detalladas permanecen como fuente específica de cada historia; ante discrepancias prevalecen arquitectura, contrato API, diccionario y la HU más reciente.

## 1. Flujo operativo cerrado

```text
analista carga CSV mensual ya preparado
→ backend valida la carga
→ backend construye ChampionInput
→ ChampionService obtiene ChampionOutput
→ backend valida feature contract input ↔ Champion
→ se mapea y persiste el snapshot
→ API expone latest/history/run
→ dashboard consume por HTTP
→ Refresh consulta únicamente el último snapshot persistido
```

Para Entregable 2 el CSV contiene las 39 features requeridas por el Champion. El backend no genera lags, rolling, canal endémico ni otras features desde datos crudos.

## 2. Alcance vigente

El cierre funcional es local-first:

```text
Dashboard React local
        ↓ HTTP
FastAPI local
        ↓
HU002–HU009
        ↓
SQLite local
        ↓
ChampionService materializado
```

El Champion real integrado proviene del trabajo de PR12 ya incorporado en `main`. AWS/EC2, deployment remoto, autenticación, entrenamiento, DVC/S3/MLflow por request y SHAP online quedan fuera del gate de cierre de HU010.

## 3. Estado de historias

| Orden | HU | Nombre | Estado |
|---:|---|---|---|
| 1 | HU-INT-001 | Base FastAPI y contratos | COMPLETADA |
| 2 | HU-INT-002 | Carga mensual y validación | COMPLETADA |
| 3 | HU-INT-003 | Adaptación a ChampionInput | COMPLETADA |
| 4 | HU-INT-004 | Adapter/servicio del Champion + feature contract gate | COMPLETADA |
| 5 | HU-INT-005 | Orquestación del run | COMPLETADA |
| 6 | HU-INT-006 | Persistencia y trazabilidad | COMPLETADA |
| 7 | HU-INT-007 | API de consulta | COMPLETADA |
| 8 | HU-INT-008 | Integración dashboard HTTP | COMPLETADA |
| 9 | HU-INT-009 | Metadata, calidad y explicabilidad | COMPLETADA |
| 10 | HU-INT-010 | Pruebas E2E y cierre local | COMPLETADA |

## 4. HU004 — integración Champion cerrada

Frontera estable:

```text
ChampionService.produce(operational_context)
→ ChampionOutput
```

MVP vigente:

```text
ChampionResult PR12
→ MaterializedOutputAdapter
→ feature contract gate
→ ChampionOutput
```

Contrato aprobado:

```text
model_version             = pr12-f5a2d39
feature_contract_version  = pr12-74e385c3
feature_contract_sha256   = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

El gate exige igualdad exacta de versión y SHA entre input/API y Champion. Un mismatch produce `CHAMPION_INPUT_INVALID`, `FAILED` y no permite persistir un snapshot `COMPLETED`.

## 5. HU010 — evidencia funcional final

El E2E real utiliza la salida Champion materializada del corte `2025-12` y valida:

```text
POST /api/v2/monthly-runs
→ HTTP 201
→ run COMPLETED
→ 4 predicciones persistidas
→ GET /api/v2/predictions/latest = 200
```

Predicciones preservadas:

| Municipio | Horizonte | Probability | Threshold | Label |
|---|---|---:|---:|---|
| Bucaramanga | T+1 | 0.7347 | 0.34 | EXCESO |
| Bucaramanga | T+2 | 0.6724 | 0.27 | EXCESO |
| Cali | T+1 | 0.0132 | 0.34 | NO_EXCESO |
| Cali | T+2 | 0.0150 | 0.27 | NO_EXCESO |

Resultados de cierre reportados:

```text
api/tests/test_e2e_champion_real.py → 2 passed
E2E local + Champion real         → 10 passed
api/tests completo                → 216 passed
git diff --check                  → limpio
```

La cobertura negativa de mismatch permanece en pruebas de `ChampionService` y `ChampionAdapter`.

## 6. Reglas operativas vigentes

- `GET latest`, `GET history`, `GET runs/{run_id}` y Refresh son read-only;
- ningún GET dispara Champion, entrenamiento, DVC/S3 o MLflow;
- SQLite permanece detrás de interfaces de persistencia;
- no existe fallback silencioso a mocks;
- threshold se conserva por predicción/horizonte;
- probability y label no son recalculados por frontend;
- datos no disponibles permanecen `null`/`available=false`;
- el feature contract gate es obligatorio antes de mapping/persistencia.

## 7. Cierre técnico del Entregable 2

Dentro del alcance local definido para Entregable 2:

```text
HU001–HU010: COMPLETADAS
FEATURE CONTRACT GATE: APROBADO
REAL CHAMPION E2E: APROBADO
API REGRESSION: APROBADO
PRUEBAS FUNCIONALES API: CERRADAS
```

Pendientes posteriores como AWS/EC2 productivo, CI formal, autenticación o automatización de deployment no reabren este cierre; deben gestionarse como nuevas mejoras o historias posteriores.
