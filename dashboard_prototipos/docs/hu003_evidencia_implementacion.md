# HU003 — Evidencia de implementación DWP

Fecha: 2026-09-02
Rama: `feature/hu003-champion-input-contract`
PR: [#23](https://github.com/j-mauro-r/microproyecto-tema3/pull/23)
Base: `e5e05ace` (`main`, merge de HU002)
Estado: **PASS**

## Resultado

HU003 implementa la adaptación pura y determinista:

```text
ValidatedMonthlyUpload
→ selección de CHAMPION_FEATURES
→ orden municipal 68001, 76001
→ orden contractual de features
→ conversión float finita
→ ChampionInput
```

No se modificó `/monthly-runs`: después de una carga válida conserva el error
temporal `503 CHAMPION_NOT_READY` y no fabrica predicciones ni `201 COMPLETED`.

## Contrato consumido

La entrada exclusiva es `ValidatedMonthlyUpload` de HU002. El builder consume
sus filas ya parseadas/filtradas y metadata; no vuelve a leer el archivo físico.

La única fuente de nombres y orden es `CHAMPION_FEATURES` en
`api/app/domain/champion_feature_contract.py`:

- versión: `pr12-74e385c3`;
- SHA-256: `786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba`;
- dimensión vigente: 2 municipios × 39 features;
- orden municipal: `("68001", "76001")`.

## ChampionInput final

```python
@dataclass(frozen=True, slots=True)
class ChampionInput:
    reference_month: str
    municipalities: tuple[str, ...]
    feature_names: tuple[str, ...]
    rows: tuple[tuple[float, ...], ...]
    feature_contract_version: str
    feature_contract_sha256: str
    source_file_sha256: str
```

Es inmutable y no depende de pandas, numpy, XGBoost, MLflow ni tipos propios de
un framework de inferencia. Identificadores (`divipola`, `anio`, `mes`) y
targets/futuros no aparecen en `feature_names` ni en la matriz.

## Orden y conservación de valores

- Dos uploads idénticos con filas invertidas producen el mismo objeto lógico.
- El builder indexa por DIVIPOLA y materializa siempre Bucaramanga antes de Cali.
- Cada fila se construye iterando explícitamente `CHAMPION_FEATURES`.
- Los valores se convierten con `float` y se conservan sin redondeo, clipping,
  normalización, escalado o imputación.
- Las pruebas asignan valores distinguibles por municipio/posición y verifican
  extremos de cada fila, además de la dimensión 2×39.

## Defensas de dominio

Objetos `ValidatedMonthlyUpload` construidos manualmente se rechazan con
`CHAMPION_INPUT_INVALID`, etapa `PREPARING`, ante:

- municipio faltante, inesperado o duplicado;
- feature ausente;
- texto no numérico, NaN, `inf` o `-inf`;
- `reference_month` vacío o inválido;
- `anio`/`mes` de una fila inconsistente con `reference_month`.

Estas defensas no duplican parsing, extensión, tamaño, hash ni las validaciones
de transporte de HU002.

## T01–T12

| Tarea | Estado | Evidencia |
|---|---|---|
| T01 | PASS | base `e5e05ace`; 54 tests verdes antes de cambios |
| T02 | PASS | contrato HU002/Champion contrastado, 39 features sin cambios |
| T03 | PASS | `ChampionInput` frozen/slots y framework-agnostic |
| T04 | PASS | `ChampionInputBuilder.build(upload)` puro |
| T05 | PASS | orden fijo 68001→76001 |
| T06 | PASS | `CHAMPION_FEATURES` y 39 valores exactos por fila |
| T07 | PASS | defensas controladas en etapa `PREPARING` |
| T08 | PASS | frontera HTTP intacta, sin 201 ni predicción |
| T09 | PASS | 17 tests HU003 focalizados |
| T10 | PASS | suite API completa: 71 tests |
| T11 | PASS | este documento de evidencia |
| T12 | PASS | gates técnicos, seguridad y alcance verificados |

## CA01–CA18

| CA | Estado | Evidencia |
|---|---|---|
| CA01 | PASS | HU002 está mergeada; baseline verde |
| CA02 | PASS | entrada exclusiva `ValidatedMonthlyUpload`, sin archivo físico |
| CA03 | PASS | importa `CHAMPION_FEATURES`, sin lista paralela |
| CA04 | PASS | municipios exactos 68001/76001 |
| CA05 | PASS | inversión de filas produce resultado idéntico |
| CA06 | PASS | `feature_names is CHAMPION_FEATURES` |
| CA07 | PASS | matriz 2×39 |
| CA08 | PASS | texto/NaN/inf/-inf rechazados |
| CA09 | PASS | identifiers ausentes de features |
| CA10 | PASS | targets/futuros ausentes de features/matriz |
| CA11 | PASS | periodo y tres campos de trazabilidad preservados |
| CA12 | PASS | auditoría sin feature engineering o imputación |
| CA13 | PASS | import limpio sin modelos/librerías ML |
| CA14 | PASS | tuplas y floats estándar, sin framework ML |
| CA15 | PASS | `CHAMPION_INPUT_INVALID`, `PREPARING` |
| CA16 | PASS | tests offline sin filesystem/red/datasets |
| CA17 | PASS | suite HU001/HU002 completa verde |
| CA18 | PASS | diff sin HU004+, frontend/model/data/notebooks |

Resultado: **18 PASS, 0 FAIL**.

## AV01–AV18

| AV | Estado | Evidencia |
|---|---|---|
| AV01 | PASS | baseline 54 tests |
| AV02 | PASS | import y aserción de identidad de `CHAMPION_FEATURES` |
| AV03 | PASS | construcción válida probada |
| AV04 | PASS | filas invertidas, mismo resultado |
| AV05 | PASS | orden exacto de features |
| AV06 | PASS | 2 filas × 39 valores |
| AV07 | PASS | valores posicionales conservados como float |
| AV08 | PASS | texto y no finitos rechazados |
| AV09 | PASS | municipio faltante rechazado |
| AV10 | PASS | duplicado y extra rechazados |
| AV11 | PASS | feature faltante rechazada |
| AV12 | PASS | referencia/hash fuente/versión/hash preservados |
| AV13 | PASS | identifiers y targets excluidos |
| AV14 | PASS | proceso limpio sin ML/cloud/DataFrame/pickle |
| AV15 | PASS | error de preparación comprobado |
| AV16 | PASS | multipart conserva 503 temporal |
| AV17 | PASS | pytest/compileall/pip/diff verdes |
| AV18 | PASS | scope diff limitado a HU003 |

Resultado: **18 PASS, 0 FAIL**.

## Comandos y resultados

```text
git fetch origin --prune                                      PASS
git switch feature/hu003-champion-input-contract             PASS
git pull --ff-only origin feature/hu003-champion-input-contract PASS
python -m pytest api/tests -q                                 71 passed, 1 warning
python -m compileall -q api                                   PASS
python -m pip check                                           No broken requirements found
git diff --check main...HEAD                                  PASS
git diff --name-only main...HEAD                              alcance HU003 esperado
```

La advertencia única es `StarletteDeprecationWarning` de TestClient/httpx; no
es un conflicto ni afecta HU003.

## Seguridad, alcance y limitaciones

- No hay secrets, filesystem, red ni estado global mutable en HU003.
- No se añadieron dependencias; la biblioteca estándar es suficiente.
- No se leen parquet/pickle ni se importan pandas/numpy/XGBoost/MLflow/DVC/AWS.
- No hay `predict`, `predict_proba`, ChampionAdapter, persistencia o endpoints.
- El contrato sigue vinculado al Champion temporal de PR #12; una promoción
  futura exige actualizar versión/hash en la fuente central de HU002.
- HU003 confía en HU002 para transporte/parsing/hash; sus checks son defensas de
  invariantes, no un segundo `MonthlyUploadValidator`.

## Confirmación de NO feature engineering

HU003 no calcula lags, rolling, P25/P75, canal, SIR, endemicidad, `brote`,
`mes_sin`, `mes_cos` ni ninguna otra variable. Tampoco rellena nulos, escala,
normaliza, recorta o redondea. Solo selecciona, ordena y convierte features ya
preparadas y validadas.

## Diff final y gate HU004

El diff contra `main` contiene la definición DWP HU003, el módulo de dominio,
sus tests y esta evidencia. No contiene `model/`, `data/`, notebooks, scripts de
entrenamiento o frontend/dashboard.

HU004 puede iniciar cuando la revisión humana confirme este contrato. Debe
consumir `ChampionInput`, verificar versión/hash contra el artefacto, adaptar
las tuplas al framework y ejecutar el Champion. No debe volver a parsear CSV,
reordenar features ni implementar feature engineering.
