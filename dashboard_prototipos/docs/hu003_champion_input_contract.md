# HU003 — Adaptación mínima al contrato del Champion BIOMAC

## 1. Identificación

- **ID canónico:** HU003
- **Alias en backlog:** HU-INT-003
- **Nombre:** Adaptación mínima al contrato del Champion
- **Estado:** `[COMPLETADA — DESARROLLO / HANDOFF CONTRACTUAL REFORZADO]`
- **Prioridad:** ALTA
- **Tipo:** Backend / Integración / Preparación de inferencia
- **Metodología:** DWP (Deep Work Plan)
- **Dependencia previa:** HU002 — Carga mensual lista para inferencia `[COMPLETADA]`
- **Habilita:** HU004 — Adapter del Champion (`HU-INT-004`)
- **Gate posterior:** HU004 no debe aceptar ningún resultado Champion cuyo `feature_contract_version` o `feature_contract_sha256` difiera de los valores transportados por el `ChampionInput`/contexto operacional del mismo run.

### Fuentes de verdad

1. `dashboard_prototipos/docs/arquitectura.md`;
2. `dashboard_prototipos/docs/implementacion.md`;
3. `dashboard_prototipos/docs/API-sign.md`;
4. `dashboard_prototipos/docs/plan.md`;
5. `dashboard_prototipos/docs/diccionario-de-datos.md`;
6. `dashboard_prototipos/docs/HU-MVP-FastAPI-dashboard.md`;
7. `dashboard_prototipos/docs/hu002_carga_mensual_validacion.md`;
8. `dashboard_prototipos/docs/hu002_evidencia_implementacion.md`;
9. `api/app/domain/champion_feature_contract.py` integrado por HU002;
10. implementación FastAPI v2 bajo `api/`;
11. **fuente complementaria temporal del Champion:** PR #12, especialmente `model/xgb_clasico_meta.json`, scripts de entrenamiento/predicción y artefactos aprobados.

---

## 2. Contexto y decisión de alcance

El backlog original describe HU003 como una etapa de transformación de la carga mensual y contexto histórico hacia las features del Champion. Para la entrega académica inmediata se aprobó en HU002 una simplificación explícita:

> El archivo mensual ya contiene las features calculadas y listas para inferencia.

Por tanto, HU003 **no realizará feature engineering**. Su responsabilidad queda reducida a una adaptación mínima, determinista y desacoplada:

```text
ValidatedMonthlyUpload
→ seleccionar las 39 features contractuales
→ conservar orden contractual
→ convertir a representación numérica estable
→ asociar cada fila con su municipio
→ producir ChampionInput
```

El flujo del microproyecto queda:

```text
CSV mensual ya preparado
→ HU002: recepción + validación
→ HU003: ChampionInput
→ HU004: cargar/invocar Champion
→ HU005+: orquestación/persistencia
```

La construcción futura desde datos crudos continúa fuera de alcance:

```text
datos crudos
→ histórico
→ lags / rolling
→ canal / SIR / estacionalidad
→ features
→ ChampionInput
```

---

## 3. Historia de usuario

> **Como** servicio de inferencia BIOMAC, **quiero** convertir una carga mensual ya validada en la estructura exacta y ordenada que espera el Champion, **para** que HU004 pueda ejecutar inferencia sin conocer detalles del CSV ni repetir validaciones de HU002.

---

## 4. Objetivo verificable

Al finalizar HU003 deberá existir un componente reusable, puro y testeable que:

1. reciba únicamente un `ValidatedMonthlyUpload` producido por HU002;
2. no vuelva a parsear el CSV original como fuente principal;
3. use `CHAMPION_FEATURES` como única fuente del nombre y orden de features;
4. produzca una fila de inferencia para Bucaramanga `68001` y una para Cali `76001`;
5. conserve el orden municipal de forma explícita y determinista;
6. convierta las 39 features validadas a valores numéricos adecuados para consumo posterior;
7. no agregue, elimine, calcule, impute, escale ni derive features;
8. no incluya `divipola`, `anio`, `mes` dentro de la matriz de features;
9. no incluya targets o columnas futuras;
10. adjunte `reference_month` y metadata suficiente para trazabilidad;
11. adjunte versión/hash del feature contract de HU002;
12. falle de forma controlada si recibe un objeto inconsistente, incluso si normalmente HU002 debe impedirlo;
13. mantenga independencia de XGBoost, pickle, MLflow, DVC, AWS/S3 y del frontend;
14. no ejecute el Champion;
15. no modifique el endpoint público para fabricar una predicción o `201 COMPLETED`;
16. tenga pruebas unitarias/offline para ambos municipios y orden de features;
17. preserve la regresión completa de HU001/HU002;
18. deje un handoff inequívoco para HU004.

---

## 5. Contrato de entrada de HU003

HU003 acepta exclusivamente:

```text
ValidatedMonthlyUpload
```

El contrato integrado por HU002 contiene, como mínimo:

```text
reference_month
metadata
  original_name
  size_bytes
  sha256
  content_type
columns
rows
```

Cada elemento de `rows` ya está limitado por HU002 a:

```text
divipola
anio
mes
+ 39 CHAMPION_FEATURES
```

HU003 debe confiar en HU002 para las validaciones de transporte y dataset, pero conservar defensas de dominio para impedir que una instancia construida manualmente o corrupta genere un input silenciosamente inválido.

### Invariantes heredadas de HU002

- `reference_month` válido;
- exactamente Bucaramanga y Cali;
- una fila por municipio;
- mismo mes en ambas filas;
- features requeridas presentes;
- features numéricas, finitas y no nulas;
- targets/futuros excluidos del resultado efectivo;
- SHA-256 del archivo disponible.

HU003 no debe duplicar el parser CSV ni las reglas completas de validación de HU002.

---

## 6. Contrato de salida: `ChampionInput`

Definir un tipo de dominio inmutable equivalente a:

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

El nombre exacto puede ajustarse a las convenciones existentes, pero la semántica debe preservarse.

### 6.1 `municipalities`

Orden contractual para el MVP:

```text
("68001", "76001")
```

El orden no debe depender del orden accidental de las filas del CSV.

### 6.2 `feature_names`

Debe ser exactamente:

```python
CHAMPION_FEATURES
```

proveniente de:

```text
api/app/domain/champion_feature_contract.py
```

No copiar una segunda lista manual.

### 6.3 `rows`

Cada fila corresponde posicionalmente al municipio de `municipalities`.

Dimensión esperada actual:

```text
2 municipios × 39 features
```

Cada valor debe ser numérico y finito.

### 6.4 Trazabilidad

El resultado debe conservar:

- `reference_month`;
- `source_file_sha256`;
- `feature_contract_version`;
- `feature_contract_sha256`.

Estos dos últimos campos representan el **contrato efectivo del input usado por el run** y deben viajar intactos hasta HU004. No son metadata decorativa: HU004 debe compararlos contra la metadata contractual del Champion antes de aceptar su salida.

---

## 7. Decisiones de diseño

### 7.1 `ChampionInputBuilder` o servicio equivalente

Crear un componente focalizado, por ejemplo:

```text
api/app/domain/champion_input.py
```

o ubicación equivalente coherente con la arquitectura.

Interfaz conceptual:

```python
class ChampionInputBuilder:
    def build(self, upload: ValidatedMonthlyUpload) -> ChampionInput:
        ...
```

Debe ser puro:

- sin I/O de red;
- sin filesystem;
- sin estado global mutable;
- sin modelo;
- sin MLflow;
- sin pandas como requisito si una estructura estándar es suficiente.

### 7.2 Orden determinista de municipios

HU002 valida presencia y unicidad, pero HU003 debe imponer el orden contractual antes de crear la matriz.

Por ejemplo:

```text
68001 → fila 0
76001 → fila 1
```

Un CSV con Cali primero y Bucaramanga después debe producir exactamente el mismo `ChampionInput` lógico que el mismo CSV con filas invertidas.

### 7.3 Orden determinista de features

No utilizar `dict.values()`, orden del header CSV ni selección incidental.

La matriz se construye iterando explícitamente:

```python
for feature in CHAMPION_FEATURES
```

### 7.4 Conversión numérica

HU002 ya validó números finitos. HU003 debe realizar únicamente la conversión necesaria para el contrato del Champion, preferentemente a `float` salvo que el artefacto aprobado exija otro dtype.

No realizar:

- `fillna(0)`;
- normalización;
- escalado;
- encoding;
- clipping;
- redondeo;
- imputación;
- coerción silenciosa de errores.

### 7.5 Sin DataFrame obligatorio

HU003 debe producir un contrato de dominio independiente del framework del modelo.

No se debe acoplar el dominio a `xgboost.DMatrix`, `pandas.DataFrame` o `numpy.ndarray` si ese acoplamiento corresponde naturalmente a HU004.

HU004 podrá adaptar `ChampionInput` al framework requerido por el Champion.

### 7.6 Validaciones defensivas mínimas

Aunque HU002 garantiza el contrato, `ChampionInputBuilder` debe rechazar al menos:

- municipio requerido ausente;
- municipio inesperado;
- fila duplicada;
- feature contractual ausente;
- feature no convertible a número finito;
- `reference_month` vacío/inconsistente;
- hash/version de contrato incompatibles si estos forman parte del objeto de entrada futuro.

Estas defensas no deben convertirse en una segunda implementación completa de HU002.

### 7.7 Errores

Usar la infraestructura de errores existente.

Cuando HU003 se integre al flujo HTTP, el error debe poder mapearse a:

```text
CHAMPION_INPUT_INVALID
```

si dicho código ya existe en `API-sign.md`/schemas. Si no está disponible en el enum implementado, no inventar silenciosamente un nuevo código público: documentar la brecha o realizar la actualización contractual mínima y explícita respaldada por `API-sign.md`.

La etapa lógica para errores de HU003 es:

```text
PREPARING
```

No usar `VALIDATING` para fallos originados dentro de HU003.

---

## 8. Fuera de alcance

HU003 **no** debe implementar:

- lectura multipart;
- parsing general del CSV;
- SHA-256 del archivo original;
- validación de tamaño/extensión;
- lags;
- rolling windows;
- canal endémico;
- SIR;
- estacionalidad;
- generación de `mes_sin`/`mes_cos`;
- cálculo de P25/P75;
- construcción o recalculo de `brote`;
- imputación `fillna(0)`;
- contexto histórico;
- acceso a `features_mensual.parquet` durante runtime;
- pandas/numpy salvo necesidad contractual demostrada;
- `ChampionAdapter`;
- deserialización `.pkl`;
- carga de XGBoost/LightGBM/GAM;
- `predict`/`predict_proba`;
- calibración;
- thresholds;
- SHAP;
- MLflow;
- DVC;
- AWS/S3;
- persistencia;
- repositorios de runs/predicciones;
- `GET latest/history`;
- frontend/Lovable;
- entrenamiento o reentrenamiento;
- Docker/CI/CD.

---

## 9. Plan de implementación DWP

### T01 — Validar base integrada

- partir de `main` con HU002 mergeada;
- ejecutar suite API antes de cambios;
- comprobar que existe `champion_feature_contract.py`;
- comprobar que `ValidatedMonthlyUpload` expone filas filtradas y metadata.

### T02 — Auditar contrato real de HU002 y Champion

Contrastar:

- `ValidatedMonthlyUpload`;
- `CHAMPION_FEATURES`;
- versión/hash;
- orden municipal;
- contrato PR #12.

No modificar las 39 features salvo incompatibilidad demostrada.

### T03 — Definir `ChampionInput`

Crear tipo inmutable y framework-agnostic con:

- periodo;
- municipios;
- nombres de features;
- matriz/filas numéricas;
- versión/hash del contrato;
- hash fuente.

### T04 — Implementar builder puro

Construir `ChampionInputBuilder` o función equivalente:

```text
ValidatedMonthlyUpload → ChampionInput
```

sin I/O ni modelo.

### T05 — Imponer orden municipal

Garantizar siempre:

```text
68001, 76001
```

independientemente del orden del upload.

### T06 — Imponer orden de features

Garantizar exactamente `CHAMPION_FEATURES` y 39 valores por fila.

### T07 — Implementar defensas mínimas

Rechazar objetos inconsistentes y mapear error de preparación de forma estable.

### T08 — Mantener frontera HTTP incremental

No conectar aún Champion ni fabricar respuesta exitosa. El comportamiento temporal post-HU002 puede seguir en `CHAMPION_NOT_READY` hasta HU004/HU005.

HU003 no necesita convertir `/monthly-runs` en un flujo completo.

### T09 — Tests unitarios

Añadir tests focalizados para builder/contrato.

### T10 — Regresión HU001/HU002

Ejecutar toda la suite `api/tests` y comprobar que HU002 conserva comportamiento.

### T11 — Evidencia DWP

Crear:

```text
dashboard_prototipos/docs/hu003_evidencia_implementacion.md
```

con tareas, CA, AV, comandos, resultados y limitaciones.

### T12 — Auditoría final del diff

Ejecutar gates y comprobar ausencia de HU004+.

---

## 10. Criterios de aceptación CA01–CA18

### CA01 — Dependencia HU002

**Dado** `main` con HU002 integrada, **cuando** se ejecuta la suite base, **entonces** permanece verde antes de implementar HU003.

### CA02 — Entrada exclusiva

**Dado** un upload válido, **cuando** HU003 construye el input, **entonces** consume `ValidatedMonthlyUpload` y no vuelve a depender del archivo físico.

### CA03 — Contrato centralizado

**Dado** el contrato Champion, **cuando** se inspecciona HU003, **entonces** usa `CHAMPION_FEATURES` sin duplicar manualmente los 39 nombres.

### CA04 — Municipios exactos

**Dado** Bucaramanga y Cali, **cuando** se construye el input, **entonces** `municipalities == ("68001", "76001")`.

### CA05 — Orden independiente del CSV

**Dado** dos cargas lógicamente idénticas con filas invertidas, **cuando** se construyen los inputs, **entonces** el contenido lógico resultante es idéntico.

### CA06 — Features exactas

**Dado** un upload válido, **cuando** se construye el input, **entonces** `feature_names == CHAMPION_FEATURES`.

### CA07 — Dimensión

**Dado** el contrato actual, **cuando** se construye el input, **entonces** existen 2 filas × 39 valores.

### CA08 — Numérico y finito

**Dado** un objeto inconsistente construido fuera de HU002, **cuando** contiene valor no numérico/NaN/inf, **entonces** HU003 falla de forma controlada.

### CA09 — Sin identificadores dentro de features

**Dado** el input final, **cuando** se inspeccionan `feature_names`, **entonces** no aparecen `divipola`, `anio` ni `mes`.

### CA10 — Sin targets

**Dado** el input final, **cuando** se inspeccionan features, **entonces** no se incorporan targets/columnas futuras ajenas al contrato aprobado.

### CA11 — Trazabilidad

**Dado** un upload válido, **cuando** se crea `ChampionInput`, **entonces** conserva `reference_month`, hash fuente, versión y hash del feature contract.

### CA12 — Sin feature engineering

**Dado** el código HU003, **cuando** se audita, **entonces** no existen cálculos de lags, rolling, P25/P75, canal, SIR, estacionalidad o imputación.

### CA13 — Sin Champion

**Dado** HU003, **cuando** se importa/ejecuta, **entonces** no carga ni ejecuta modelos o librerías ML de inferencia.

### CA14 — Framework agnostic

**Dado** `ChampionInput`, **cuando** se inspecciona su contrato público, **entonces** no exige XGBoost/MLflow ni un tipo específico del framework del Champion.

### CA15 — Error de preparación

**Dado** un input inconsistente, **cuando** falla HU003, **entonces** el error es controlado y semánticamente corresponde a etapa `PREPARING` al mapearse al flujo.

### CA16 — Offline

**Dado** los tests HU003, **cuando** se ejecutan, **entonces** no requieren red, AWS, DVC, MLflow, modelos ni datasets reales.

### CA17 — Regresión

**Dado** HU001/HU002, **cuando** se ejecuta toda la suite API, **entonces** sus pruebas continúan pasando.

### CA18 — Scope

**Dado** el diff contra `main`, **cuando** se audita, **entonces** no contiene HU004+, frontend, modelos, datos o notebooks.

---

## 11. Autovalidaciones AV01–AV18

### AV01 — Baseline
Ejecutar `python -m pytest api/tests -q` antes de cambios. PASS si base verde.

### AV02 — Contrato compartido
Verificar por inspección/test que el builder importa `CHAMPION_FEATURES` y no redefine lista paralela.

### AV03 — Construcción válida
Construir un `ValidatedMonthlyUpload` sintético válido y comprobar `ChampionInput`.

### AV04 — Orden municipal
Invertir las filas de entrada. PASS si resultado mantiene 68001→76001.

### AV05 — Orden features
Comparar `feature_names` exactamente contra `CHAMPION_FEATURES`.

### AV06 — Dimensión
Comprobar 2 × 39.

### AV07 — Valores
Comprobar conversión numérica sin mutar valores.

### AV08 — No finitos
Inyectar `NaN`, `inf` o texto mediante objeto manual. PASS si falla controlado.

### AV09 — Municipio faltante
Crear objeto inconsistente sin Cali/Bucaramanga. PASS si falla.

### AV10 — Duplicado/extra
Crear objeto inconsistente con duplicado o municipio extra. PASS si falla.

### AV11 — Feature faltante
Eliminar feature de una fila. PASS si falla.

### AV12 — Trazabilidad
Verificar referencia, hash fuente, versión/hash contrato.

### AV13 — Sin columnas auxiliares
Comprobar que identifiers y targets no aparecen en `feature_names`.

### AV14 — Sin ML/I/O
Inspeccionar imports y ejecutar en proceso limpio. PASS sin modelos, MLflow, DVC, AWS ni filesystem.

### AV15 — Error stage
Provocar error de HU003 y verificar semántica `PREPARING` en el mapeo disponible.

### AV16 — Regresión HU002
Ejecutar pruebas de upload/multipart y confirmar comportamiento `503 CHAMPION_NOT_READY` temporal.

### AV17 — Gates técnicos
Ejecutar `compileall`, `pip check`, `git diff --check`.

### AV18 — Scope diff
Revisar `git diff --name-only main...HEAD` y comprobar alcance HU003.

---

## 12. Definition of Done

HU003 se considera `[COMPLETADA]` únicamente cuando:

- [ ] HU002 está integrada en `main`;
- [ ] existe un `ChampionInput` inmutable;
- [ ] existe builder/servicio puro desde `ValidatedMonthlyUpload`;
- [ ] se usa una única fuente para `CHAMPION_FEATURES`;
- [ ] el orden municipal es determinista;
- [ ] el orden de las 39 features es determinista;
- [ ] la salida actual es exactamente 2 × 39;
- [ ] valores numéricos se conservan sin feature engineering;
- [ ] identifiers no entran a la matriz;
- [ ] targets/futuros no entran a la matriz;
- [ ] reference month y hashes/versiones se preservan;
- [ ] defensas mínimas rechazan objetos inconsistentes;
- [ ] errores de HU003 representan etapa `PREPARING` cuando corresponda;
- [ ] no se carga/ejecuta Champion;
- [ ] no se añade dependencia ML innecesaria;
- [ ] no existe I/O externo;
- [ ] tests HU003 pasan;
- [ ] regresión HU001/HU002 pasa;
- [ ] `compileall` pasa;
- [ ] `pip check` pasa;
- [ ] `git diff --check` pasa;
- [ ] evidencia DWP existe;
- [ ] CA01–CA18 PASS;
- [ ] AV01–AV18 PASS;
- [ ] PR focalizado queda listo para auditoría;
- [ ] merge solo ocurre después de revisión humana.

---

## 13. Evidencia esperada

Crear `hu003_evidencia_implementacion.md` con:

1. commit/base utilizada;
2. contrato de entrada HU002 consumido;
3. estructura final de `ChampionInput`;
4. feature contract version/hash;
5. dimensión 2 × 39;
6. evidencia de orden municipal estable;
7. evidencia de orden de features estable;
8. pruebas de defensas mínimas;
9. matriz T01–T12;
10. matriz CA01–CA18;
11. matriz AV01–AV18;
12. comandos ejecutados;
13. resultados;
14. limitaciones;
15. diff final;
16. gate HU004.

---

## 14. Riesgos y mitigaciones

### R01 — Duplicar contrato de features
**Riesgo:** HU003 diverge de HU002/Champion.  
**Mitigación:** importar `CHAMPION_FEATURES` y metadata contractual centralizada.

### R02 — Orden accidental
**Riesgo:** una fila/feature se entrega en otra posición y cambia la predicción.  
**Mitigación:** ordenar explícitamente municipios y features.

### R03 — Feature engineering oculto
**Riesgo:** HU003 empieza a recalcular variables y retrasa la entrega.  
**Mitigación:** prohibición explícita; el CSV ya llega preparado.

### R04 — Acoplamiento prematuro a XGBoost
**Riesgo:** el dominio queda ligado a `.pkl`/DataFrame/XGBoost.  
**Mitigación:** `ChampionInput` framework-agnostic; adaptación del framework en HU004.

### R05 — Validaciones duplicadas
**Riesgo:** HU002/HU003 evolucionan de forma divergente.  
**Mitigación:** HU003 solo defensas de invariantes; no duplicar parser/transport rules.

### R06 — Cambios futuros del Champion
**Riesgo:** las 39 features cambian.  
**Mitigación:** versión/hash contractual y actualización conjunta cuando se promueva otro Champion.

### R07 — NaN vs `fillna(0)` del entrenamiento
**Riesgo:** código histórico del modelo usa `fillna(0)`, pero HU002 rechaza nulos.  
**Mitigación:** mantener contrato académico más estricto para la demo; no introducir imputación en HU003. Cualquier cambio se decide explícitamente después de la entrega.

---

## 15. Handoff a HU004

HU004 debe recibir únicamente:

```text
ChampionInput
├── reference_month
├── municipalities = (68001, 76001)
├── feature_names = CHAMPION_FEATURES
├── rows = 2 × 39 valores numéricos
├── feature_contract_version
├── feature_contract_sha256
└── source_file_sha256
```

HU004 será responsable de:

- cargar el artefacto Champion aprobado;
- comprobar compatibilidad de metadata/feature contract;
- exigir igualdad exacta de `feature_contract_version` y `feature_contract_sha256` entre el input/contexto del run y el Champion/resultado materializado;
- convertir `ChampionInput` al tipo que requiera el framework;
- invocar T+1/T+2 según contrato real;
- devolver output nativo + metadata sin inventar probabilidades/thresholds.

HU004 **no debe volver a parsear el CSV ni reconstruir el orden de features**.

---

## 16. Regla de cierre

HU003 no se considera terminada porque exista una lista de números. Debe demostrar que la frontera entre datos validados y modelo es reproducible:

```text
HU002 = ¿el archivo es válido y compatible?
HU003 = ¿puedo construir exactamente el input esperado?
HU004 = ejecutar/aceptar el Champion únicamente si declara el mismo contrato
```

Para el microproyecto actual, HU003 es deliberadamente pequeña. Su valor es eliminar ambigüedad de orden, estructura y trazabilidad antes de introducir el modelo real.

---

## 17. Hallazgo HU010 — septiembre 2026

La prueba HTTP real de HU010 encontró que el flujo podía finalizar `201 COMPLETED` aun cuando el contrato usado para validar el CSV y el declarado por la salida materializada PR12 eran distintos:

```text
Champion JSON
feature_contract_version = pr12-f5a2d39
feature_contract_sha256   = 3af245ede70851d1616439d80441e2ad6f5d3f6465b9798d6b67fed3adb3e3dc

CSV/API vigente
feature_contract_version = pr12-74e385c3
feature_contract_sha256   = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

Este hallazgo **no invalida el builder de HU003**: confirma que HU003 ya transporta la metadata necesaria, pero refuerza que esos valores constituyen el contrato efectivo del input y deben ser usados como gate obligatorio por HU004/HU005 antes de persistir un resultado. HU003 no debe “corregir” ni reemplazar hashes para forzar compatibilidad.