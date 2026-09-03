# HU002 — Carga mensual lista para inferencia BIOMAC

## 1. Identificación

- **ID canónico:** HU002
- **Alias en backlog:** HU-INT-002
- **Nombre:** Carga mensual lista para inferencia BIOMAC
- **Estado:** `[PENDIENTE]`
- **Prioridad:** ALTA
- **Tipo:** Backend / Integración / Ingesta operacional
- **Metodología:** DWP (Deep Work Plan)
- **Dependencia previa:** HU001 — Base FastAPI y contratos BIOMAC `[COMPLETADA]`
- **Habilita:** HU003 — Adaptación mínima al contrato del Champion (`HU-INT-003`)
- **Gate posterior:** HU003 no debe iniciar hasta que la API pueda recibir y validar de forma determinista un CSV de un único mes, listo para inferencia, con Bucaramanga y Cali.

### Fuentes de verdad

1. `dashboard_prototipos/docs/arquitectura.md`;
2. `dashboard_prototipos/docs/implementacion.md`;
3. `dashboard_prototipos/docs/API-sign.md`;
4. `dashboard_prototipos/docs/plan.md`;
5. `dashboard_prototipos/docs/diccionario-de-datos.md`;
6. `dashboard_prototipos/docs/HU-MVP-FastAPI-dashboard.md`;
7. `dashboard_prototipos/docs/hu001_base_fastapi_contratos.md`;
8. implementación FastAPI v2 bajo `api/`;
9. **fuente complementaria temporal:** PR #12, especialmente `model/xgb_clasico_meta.json`, `scripts/train_clasico_model.py`, `scripts/generate_predictions.py` y `src/features/build_features.py`, para identificar la estructura ya usada por el modelo evaluado.

---

## 2. Decisión de alcance para el microproyecto

Para cumplir la entrega académica inmediata se adopta una simplificación deliberada:

> **El analista no cargará datos crudos. Cargará un CSV correspondiente a un único mes, extraído del dataset de features ya preparado y utilizado para evaluar el modelo.**

El archivo llegará con las variables necesarias ya calculadas y listas para ser entregadas al pipeline del Champion.

Por tanto, en esta versión:

```text
CSV de un mes ya preparado
→ HU002: validación
→ HU003: selección/orden mínimo del input
→ HU004: Champion
```

Se posterga para una HU posterior la construcción operacional desde datos crudos:

```text
datos mensuales crudos
→ histórico
→ lags
→ rolling
→ canal endémico / SIR
→ estacionalidad
→ ChampionInput
```

Esta simplificación es una decisión de alcance del microproyecto y no redefine la arquitectura futura de BIOMAC.

---

## 3. Historia de usuario

> **Como** analista actualizador de BIOMAC, **quiero** cargar un CSV de un único mes con las features ya preparadas para Bucaramanga y Cali, **para** que el backend valide que el archivo es compatible con el Champion antes de iniciar la inferencia.

---

## 4. Objetivo verificable

Al finalizar HU002 el sistema deberá poder:

1. recibir `POST /api/v2/monthly-runs` mediante `multipart/form-data` con `file` y `reference_month`;
2. aceptar exclusivamente CSV en esta versión;
3. validar `reference_month` con formato estricto `YYYY-MM`;
4. rechazar archivo vacío o por encima del tamaño configurable;
5. calcular SHA-256 sobre los bytes reales;
6. parsear el CSV de forma segura;
7. comprobar que todo el archivo corresponde a **un único mes**;
8. comprobar que el mes del archivo coincide con `reference_month`;
9. exigir `divipola`, `anio` y `mes`;
10. exigir exactamente el alcance municipal del MVP: Bucaramanga `68001` y Cali `76001`;
11. rechazar otros municipios, duplicados por municipio/mes o ausencia de alguno de los dos;
12. exigir las features del Champion documentadas por el artefacto/metadata de PR #12;
13. comprobar que dichas features sean numéricas y utilizables por el modelo;
14. rechazar columnas objetivo/futuras que no deban entregarse como entrada de inferencia;
15. producir `ValidatedMonthlyUpload` con metadata/hash y datos validados para HU003;
16. no crear lags, rolling, canal, SIR, estacionalidad ni otras features;
17. no ejecutar Champion, MLflow, DVC, AWS ni persistencia;
18. preservar contratos, errores, `request_id`, CORS y OpenAPI de HU001;
19. superar tests offline;
20. dejar CA01–CA20 y AV01–AV20 en PASS antes del merge.

---

## 5. Contrato operativo aprobado del archivo mensual

### 5.1 Formato

Para el microproyecto se adopta:

```text
.csv
Content-Type esperado: text/csv o equivalente aceptado por FastAPI
Encoding: UTF-8 / UTF-8-SIG
```

No se habilitan XLSX, Parquet u otros formatos en HU002.

### 5.2 Granularidad

El archivo representa **un solo `reference_month`**.

Para el MVP debe contener exactamente una observación por municipio soportado:

```text
68001 — Bucaramanga
76001 — Cali
```

Resultado esperado: **2 filas válidas**, salvo que el contrato real del Champion requiera explícitamente más de una fila por municipio para ese mismo corte. En tal caso Codex debe detenerse y documentar la incompatibilidad antes de ampliar silenciosamente este contrato.

### 5.3 Identificadores obligatorios

- `divipola`: string de 5 dígitos;
- `anio`: entero de cuatro dígitos;
- `mes`: entero `1..12`.

La combinación `anio` + `mes` de todas las filas debe coincidir con `reference_month`.

### 5.4 Features requeridas

La fuente contractual para las features es la metadata del Champion usada en PR #12, actualmente `model/xgb_clasico_meta.json`.

La implementación **no debe mantener una segunda lista manual divergente** si puede leer/centralizar la misma definición contractual en código/configuración.

La lista observada en PR #12 incluye actualmente:

```text
temp_mean_c
dewpoint_mean_c
rain_mm_day
soil_water_l1_mean
surface_runoff_mm_day
total_evaporation_mm_day_ecmwf
wind_u_mean_ms
wind_v_mean_ms
solar_radiation_mj_m2_day
casos_grave_lag_1
casos_grave_lag_2
casos_grave_lag_3
casos_grave_lag_4
casos_grave_lag_6
casos_grave_roll3
casos_clasico_lag_1
casos_clasico_lag_2
casos_clasico_lag_3
casos_clasico_lag_4
casos_clasico_lag_6
casos_clasico_roll3
temp_mean_c_lag_1
temp_mean_c_lag_2
temp_mean_c_lag_3
rain_mm_day_lag_1
rain_mm_day_lag_2
rain_mm_day_lag_3
mes_sin
mes_cos
p25
p75
zona_canal
sir
es_endemico
brote
p25_objetivo
p75_objetivo
zona_objetivo
brote_lag_1
```

**Regla:** antes de codificar, Codex debe contrastar esta lista contra el estado real del PR #12/artefacto Champion y usar la fuente vigente. Si existe divergencia, la metadata del artefacto aprobado prevalece y debe documentarse en evidencia.

### 5.5 Tipos

- `divipola`: string 5 dígitos;
- `anio`, `mes`: enteros;
- features Champion: numéricas;
- valores no numéricos en features requeridas: error bloqueante;
- `NaN`/vacíos en features requeridas: para esta versión simplificada deben rechazarse, salvo que el contrato explícito del Champion demuestre que son aceptados sin transformación adicional.

HU002 no debe imputar, escalar, convertir categorías ni reemplazar faltantes para hacer pasar el archivo.

### 5.6 Columnas prohibidas como entrada

El archivo no debe utilizar como entrada al Champion etiquetas o resultados futuros. Deben rechazarse como mínimo cuando aparezcan como parte del input efectivo:

```text
objetivo
casos_objetivo
anio_objetivo
mes_objetivo
es_inicio
__target_t2
observed_label
```

Las columnas auxiliares pueden existir físicamente en una extracción del dataset únicamente si el validator las ignora explícitamente y demuestra que **nunca se entregan al Champion**. La opción preferida para el archivo de demo es exportar solo identificadores + features requeridas.

---

## 6. Separación de responsabilidades

### HU002 sí hace

```text
multipart
→ límite de tamaño
→ CSV
→ reference_month
→ estructura
→ municipios
→ tipos
→ features requeridas
→ columnas prohibidas
→ SHA-256
→ ValidatedMonthlyUpload
```

### HU002 no hace

- lags;
- rolling windows;
- percentiles;
- canal endémico;
- SIR;
- estacionalidad;
- feature engineering;
- imputación;
- entrenamiento;
- selección de modelo;
- inferencia;
- persistencia.

### HU003 queda simplificada a

```text
ValidatedMonthlyUpload
→ seleccionar features exactas
→ ordenar según contrato Champion
→ construir ChampionInput
```

La construcción automática de features desde datos crudos se moverá a una HU posterior a la entrega académica.

---

## 7. Diseño técnico esperado

Mantener separación:

```text
FastAPI / multipart
        ↓
MonthlyUploadValidator
        ↓
ValidatedMonthlyUpload
        ↓
HU003
```

`MonthlyUploadValidator` debe ser testeable sin servidor HTTP y sin modelos.

Debe centralizar un `MonthlyUploadContract` o equivalente con:

- `allowed_extensions=(".csv",)`;
- municipios soportados `("68001", "76001")`;
- columnas identificadoras;
- feature contract del Champion;
- columnas prohibidas;
- tamaño máximo;
- reglas de único mes y unicidad municipal.

No duplicar la lista de features en endpoint, validator y tests.

---

## 8. Comportamiento HTTP incremental

`API-sign.md` define que `201 COMPLETED` corresponde al flujo completo validación → preparación → inferencia → persistencia.

HU002 todavía **no debe fabricar ese éxito**.

Mientras HU003+ no exista, una carga válida puede continuar usando un error controlado de dependencia downstream, por ejemplo:

```text
503 CHAMPION_NOT_READY
```

siempre que:

- la validación haya terminado realmente;
- el error sea explícito;
- no se presente como predicción;
- no se construya snapshot ficticio;
- la evidencia deje claro que es comportamiento incremental temporal.

Cuando HU005 integre el flujo completo, esta respuesta transitoria deberá desaparecer.

---

## 9. Plan DWP

### T01 — Sincronizar rama y validar regresión HU001

- trabajar en `feature/hu002-monthly-upload-validation` y PR #22;
- rebase con `main` si aplica;
- ejecutar suite API existente.

### T02 — Confirmar contrato Champion desde PR #12

- inspeccionar `model/xgb_clasico_meta.json`;
- contrastar con scripts que cargan el modelo;
- obtener features y orden vigente;
- documentar cualquier divergencia.

### T03 — Actualizar `MonthlyUploadContract`

Definir CSV, columnas identificadoras, municipios, features requeridas y columnas prohibidas.

### T04 — Implementar validación de mes único

- `reference_month` válido;
- todas las filas corresponden a ese mes;
- ningún otro periodo.

### T05 — Implementar validación municipal

- exactamente `68001` y `76001`;
- sin municipios extra;
- sin duplicados;
- ninguno faltante.

### T06 — Implementar validación de features

- todas las features requeridas presentes;
- tipos numéricos;
- reglas explícitas para faltantes;
- no cálculo de features.

### T07 — Proteger contra targets/leakage operacional

Garantizar que etiquetas/targets no sean enviadas como features al Champion.

### T08 — Preservar hash, límites, errores y CORS

Mantener comportamiento ya desarrollado en HU002/HU001.

### T09 — Actualizar endpoint delgado

El endpoint solo recibe, delega y devuelve error downstream temporal hasta HU003+; no ejecuta modelo.

### T10 — Actualizar tests

Agregar escenarios positivos y negativos del contrato aprobado.

### T11 — Actualizar evidencia DWP

Actualizar `dashboard_prototipos/docs/hu002_evidencia_implementacion.md` eliminando el estado anterior `BLOCKED_BY_CONTRACT`.

### T12 — Gates finales y PR

Ejecutar suite, compileall, pip check, diff check y auditoría de alcance. Push al **mismo PR #22**. No crear otro PR. No hacer merge.

---

## 10. Criterios de aceptación CA01–CA20

- **CA01:** regresión HU001 pasa.
- **CA02:** `reference_month` estricto `YYYY-MM`.
- **CA03:** archivo vacío rechazado.
- **CA04:** límite máximo aplicado antes de procesamiento posterior.
- **CA05:** solo `.csv` aceptado.
- **CA06:** SHA-256 determinista.
- **CA07:** metadata conserva nombre seguro, bytes, hash y periodo.
- **CA08:** faltante de cualquier feature requerida produce error controlado.
- **CA09:** feature requerida con tipo no numérico produce error controlado.
- **CA10:** archivo válido contiene `68001` y `76001`, sin otros municipios ni duplicados.
- **CA11:** todas las filas corresponden exactamente a `reference_month`.
- **CA12:** targets/columnas prohibidas no llegan al input efectivo del Champion.
- **CA13:** validator no calcula features ni hace imputación.
- **CA14:** carga inválida no invoca Champion/ML/cloud/persistencia.
- **CA15:** error conserva `request_id` y etapa `VALIDATING`.
- **CA16:** CORS permite POST únicamente para orígenes configurados.
- **CA17:** carga válida no fabrica `201 COMPLETED` antes del pipeline real.
- **CA18:** validator es reusable y testeable sin FastAPI.
- **CA19:** tests focalizados pasan offline.
- **CA20:** PR permanece limitado a HU002, evidencia y soporte mínimo.

**Regla de cierre:** CA01–CA20 deben quedar en `PASS`; ya no se acepta `BLOCKED_BY_CONTRACT` para CA08–CA11 porque el contrato académico simplificado quedó aprobado.

---

## 11. Autovalidaciones AV01–AV20

- **AV01:** suite HU001 sigue verde.
- **AV02:** settings de upload válidos.
- **AV03:** enero/diciembre válidos.
- **AV04:** meses inválidos rechazados.
- **AV05:** vacío rechazado.
- **AV06:** oversized rechazado.
- **AV07:** CSV aceptado y otra extensión rechazada.
- **AV08:** SHA-256 igual para mismos bytes y distinto para contenido diferente.
- **AV09:** CSV corrupto produce error controlado.
- **AV10:** retirar una feature Champion y comprobar rechazo.
- **AV11:** introducir string inválido en feature numérica y comprobar rechazo.
- **AV12:** probar Buca+Cali válido, municipio faltante, duplicado y tercero no soportado.
- **AV13:** probar fila con mes distinto a `reference_month` y comprobar rechazo.
- **AV14:** probar presencia de target/prohibida y verificar que no se entrega a ChampionInput.
- **AV15:** `request_id` coincide header/envelope.
- **AV16:** CORS POST permitido/denegado según allowlist.
- **AV17:** import/ejecución sin MLflow/DVC/AWS/modelos.
- **AV18:** no se escriben uploads al repositorio.
- **AV19:** una carga válida no devuelve éxito ficticio ni predicción.
- **AV20:** `git diff --name-only main...HEAD` confirma alcance.

**Regla de cierre:** AV01–AV20 deben quedar en `PASS`; ya no se acepta `BLOCKED_BY_CONTRACT` para AV10–AV13.

---

## 12. Definition of Done

HU002 podrá marcarse `[COMPLETADA]` únicamente cuando:

- [ ] contrato CSV de un mes implementado;
- [ ] features Champion obtenidas desde fuente contractual centralizada;
- [ ] Bucaramanga y Cali validadas;
- [ ] mes único validado contra `reference_month`;
- [ ] tipos numéricos validados;
- [ ] targets prohibidos controlados;
- [ ] hash/tamaño/vacío/CORS/request_id preservados;
- [ ] no se construyen features;
- [ ] no se ejecuta Champion;
- [ ] no se persiste ninguna predicción;
- [ ] CA01–CA20 `PASS`;
- [ ] AV01–AV20 `PASS`;
- [ ] `python -m pytest api/tests -q` PASS;
- [ ] `python -m compileall -q api` PASS;
- [ ] `python -m pip check` PASS o incompatibilidad preexistente documentada;
- [ ] `git diff --check main...HEAD` PASS;
- [ ] evidencia DWP actualizada;
- [ ] auditoría humana aprobada;
- [ ] merge solo después de auditoría.

---

## 13. Evidencia obligatoria

`dashboard_prototipos/docs/hu002_evidencia_implementacion.md` debe actualizarse con:

1. fuente exacta del feature contract del Champion;
2. lista/hash/versión de features utilizada;
3. contrato CSV final;
4. ejemplo sintético mínimo de Buca+Cali;
5. pruebas de único mes;
6. pruebas de municipios;
7. pruebas de columnas requeridas;
8. pruebas de tipos;
9. pruebas de targets prohibidos;
10. hash/tamaño/formato;
11. CA01–CA20 todos PASS;
12. AV01–AV20 todos PASS;
13. comandos y resultados;
14. diff final;
15. confirmación de que lags/rolling/feature engineering quedan postergados.

---

## 14. Fuera de alcance

HU002 no implementa:

- cálculo de lags;
- rolling windows;
- canal endémico;
- SIR;
- estacionalidad;
- generación automática de features;
- histórico operacional;
- ChampionAdapter;
- carga del modelo;
- inferencia;
- MLflow;
- DVC/AWS/S3;
- persistencia;
- latest/history;
- dashboard;
- entrenamiento/reentrenamiento;
- tuning;
- promoción de modelos.

La automatización de features desde datos crudos deberá planificarse en una HU posterior a la entrega académica.

---

## 15. Resultado esperado para HU003

HU003 recibirá:

```text
ValidatedMonthlyUpload
├── reference_month
├── source_file metadata/hash
├── exactamente Bucaramanga y Cali
├── identifiers: divipola, anio, mes
└── features Champion ya preparadas y validadas
```

HU003 deberá limitarse inicialmente a:

```text
seleccionar features
→ ordenarlas según Champion contract
→ construir ChampionInput
```

No debe recalcular las features ya presentes en el archivo del microproyecto.
