# HU004 — Adapter del Champion BIOMAC

## 1. Identificación

- **ID canónico:** HU004
- **Alias en backlog:** HU-INT-004
- **Nombre:** Adapter del Champion
- **Estado:** `[COMPLETADA — INTEGRACIÓN CHAMPION REAL VALIDADA]`
- **Deployment AWS:** `[FUERA DEL GATE DE CIERRE DEL ENTREGABLE 2]`
- **Integración Champion real:** `[COMPLETADA — FEATURE CONTRACT COMPATIBLE Y E2E APROBADO]`
- **Prioridad:** ALTA
- **Tipo:** Backend / Integración ML / Serving
- **Dependencia previa:** HU003 `[COMPLETADA]`
- **Habilita:** HU005+ mediante `ChampionService.produce(...)`.

## 2. Objetivo cerrado

HU004 desacopla FastAPI, orquestación y dashboard del mecanismo interno del modelo. La frontera estable es:

```text
ChampionService.produce(operational_context)
→ ChampionOutput
```

El MVP utiliza el modo materializado:

```text
ChampionResult PR12
→ MaterializedOutputAdapter
→ feature contract gate
→ ChampionOutput
```

El modo ejecutable se conserva como evolución futura y no existe fallback automático entre estrategias.

## 3. Contrato aprobado

La salida real del Champion conserva:

- `model_name` y `model_version`;
- `reference_month`;
- `feature_contract_version` y `feature_contract_sha256`;
- `output_type`;
- municipio y DIVIPOLA;
- horizonte T+1/T+2;
- `target_month`;
- `probability`;
- threshold por predicción/horizonte;
- `label`.

Para el Champion integrado:

```text
model_version             = pr12-f5a2d39
feature_contract_version  = pr12-74e385c3
feature_contract_sha256   = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

La lista contractual contiene 39 features y el mismo contrato aplica a T+1 y T+2.

## 4. Gate obligatorio implementado

Antes de aceptar un `ChampionOutput` debe cumplirse exactamente:

```text
champion.feature_contract_version == input.feature_contract_version
champion.feature_contract_sha256   == input.feature_contract_sha256
```

El gate está implementado para las fronteras materializada y ejecutable. Ante mismatch:

```text
HTTP 422
CHAMPION_INPUT_INVALID
stage = INFERENCING
reason = feature_contract_mismatch
run = FAILED
```

No se persiste un snapshot `COMPLETED` y el último snapshot válido permanece disponible.

## 5. Invariantes del MVP

Cuando el Champion declara T+1 y T+2 deben existir exactamente:

```text
68001 / T+1 — Bucaramanga
68001 / T+2 — Bucaramanga
76001 / T+1 — Cali
76001 / T+2 — Cali
```

También se valida:

- `reference_month` y `target_month`;
- ausencia de duplicados `(divipola, horizon)`;
- probabilidad y threshold en `[0,1]`;
- consistencia `probability >= threshold → EXCESO`, de lo contrario `NO_EXCESO`;
- preservación del threshold específico por horizonte;
- metadata contractual no vacía.

HU004 no recalibra, no reentrena, no modifica thresholds y no genera features.

## 6. Evidencia de cierre

Tras la corrección contractual del PR12 y su incorporación en `main`, el artefacto materializado usado para la prueba real contiene:

| Municipio | Horizonte | Probability | Threshold | Label |
|---|---|---:|---:|---|
| Bucaramanga | T+1 | 0.7347 | 0.34 | EXCESO |
| Bucaramanga | T+2 | 0.6724 | 0.27 | EXCESO |
| Cali | T+1 | 0.0132 | 0.34 | NO_EXCESO |
| Cali | T+2 | 0.0150 | 0.27 | NO_EXCESO |

El E2E real valida:

```text
POST /api/v2/monthly-runs
→ HTTP 201
→ run COMPLETED
→ 4 predictions persistidas
→ GET /api/v2/predictions/latest = 200
```

La suite local reportada en el cierre:

```text
api/tests/test_e2e_champion_real.py        2 passed
E2E local + Champion real                10 passed
api/tests completo                       216 passed
```

La cobertura negativa de mismatch permanece en `test_champion_service.py` y `test_champion_adapter.py`.

## 7. Fuera de alcance

No forman parte del cierre de HU004 para Entregable 2:

- reentrenamiento o tuning;
- calibración;
- feature engineering desde datos crudos;
- DVC/S3/MLflow por request;
- SHAP online;
- deployment AWS obligatorio;
- selección/promoción de nuevos modelos.

## 8. Definición de terminado

HU004 se considera **COMPLETADA** porque:

1. la frontera `ChampionService` es estable;
2. el modo materializado PR12 funciona con el Champion real;
3. el feature-contract gate está implementado;
4. mismatch queda bloqueado de forma controlada;
5. match real produce `201 COMPLETED`;
6. las cuatro predicciones reales se preservan sin transformación;
7. la suite API permanece verde.

La validación AWS queda como evolución posterior y no reabre esta HU dentro del alcance local del Entregable 2.
