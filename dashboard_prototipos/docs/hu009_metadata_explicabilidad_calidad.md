# HU009 — Metadata, explicabilidad, calidad y contexto real de la alerta

**Estado:** `[IMPLEMENTADA — PENDIENTE AUDITORÍA]`
**Identificador:** `HU-INT-009`  
**Prioridad:** MEDIA  
**Dependencias:** HU004, HU006, HU007, HU008  
**Ámbito vigente:** Entregable 2, ejecución local; sin AWS/deployment en esta HU  
**Frontend objetivo:** `dashboard_prototipos/dengue-watch-pro`  
**Backend objetivo:** `/api/v2`  
**Documentos fuente:** `arquitectura.md`, `API-sign.md`, `diccionario-de-datos.md`, `implementacion.md`, HU004–HU008

---

## 1. Contexto

HU008 dejó conectado el dashboard BIOMAC con FastAPI y eliminó los mocks como fuente productiva. Actualmente el frontend puede mostrar de forma real:

- `run_id`;
- `generated_at`;
- `reference_month`;
- metadata mínima del Champion;
- predicciones Bucaramanga/Cali T+1/T+2;
- `probability`, `expected_cases`, `risk_score`, `label` y `decision_threshold` cuando existen.

Los paneles de canal endémico, explicabilidad, historia y calidad permanecen explícitamente como no disponibles porque HU006/HU007 persistieron y expusieron únicamente el snapshot mínimo demostrable.

La arquitectura y el diccionario objetivo, sin embargo, contemplan información complementaria necesaria para interpretar una alerta:

```text
PredictionSnapshot
├─ Champion / trazabilidad
├─ data_quality
├─ current_status
├─ predictions
│  ├─ model_output
│  ├─ decision_rule
│  └─ explanation
└─ history / contexto disponible
```

HU009 cierra esa brecha **sin fabricar información**. Toda metadata, calidad, estado epidemiológico, regla o explicación deberá tener una fuente demostrable y trazable.

---

## 2. Historia de usuario

**Como** usuario de BIOMAC  
**quiero** conocer qué modelo, regla, calidad de datos y evidencia explicativa sustentan cada alerta  
**para** interpretar la predicción con trazabilidad y distinguir claramente información disponible de información ausente.

---

## 3. Objetivo verificable

Al finalizar HU009 debe ser posible consultar un snapshot persistido y comprobar que:

1. la metadata del Champion corresponde exactamente al artefacto/salida usada;
2. la regla/threshold mostrada es la persistida para cada horizonte;
3. la calidad/frescura proviene de la entrada validada del mismo run;
4. el estado epidemiológico actual se expone solo cuando los datos fuente necesarios están realmente disponibles;
5. una explicación se marca `available=true` únicamente si existe evidencia local para el municipio + corte + horizonte exactos;
6. SHAP se etiqueta como SHAP únicamente cuando `method=shap` y `scope=local`;
7. una importancia global nunca se presenta como explicación local;
8. campos no demostrables permanecen `null`, `available=false` o se omiten de forma contractual;
9. el dashboard deja de mostrar “Información no disponible” solo para los bloques que realmente reciben datos válidos;
10. `Refresh` continúa siendo estrictamente read-only y no calcula SHAP, percentiles, calidad ni inferencia.

---

## 4. Principio rector

> HU009 enriquece el snapshot únicamente con información demostrable. No convierte deuda de datos en valores por defecto.

Queda prohibido:

- inventar `p50`;
- asumir `threshold=0.5`;
- derivar `label` en frontend;
- convertir `risk_score` en probabilidad;
- usar `casos_clasico_lag_1` como si fueran casos observados del mes actual;
- llamar “SHAP local” a importancia global;
- generar explicaciones con datos de otro corte;
- completar calidad con porcentajes arbitrarios;
- usar mocks/fallback productivo;
- ejecutar entrenamiento, tuning o selección de Champion.

---

## 5. Fuentes reales disponibles y límites actuales

### 5.1 Champion / predicción

HU004 ya entrega y HU006 persiste:

- nombre/versión Champion;
- tipo de salida;
- horizontes;
- feature contract version/hash;
- predicciones;
- probability/expected_cases/risk_score;
- label;
- threshold por predicción/horizonte.

HU009 debe reutilizar esos valores, no reconstruirlos.

### 5.2 Entrada validada

HU002 conserva por run un `ValidatedMonthlyUpload` con:

- `reference_month`;
- hash/metadata del archivo;
- Bucaramanga y Cali;
- las 39 features del contrato;
- todas numéricas, finitas y no nulas.

Es válido derivar metadata de calidad únicamente desde hechos comprobables de esa validación.

### 5.3 Estado epidemiológico

El contrato Champion vigente contiene features como `p25`, `p75` y `zona_canal` dentro del corte de entrada. Esos valores pueden utilizarse como contexto del mes de referencia si su semántica se confirma contra el contrato/documentación.

`observed_cases` del target actual no debe reconstruirse desde un lag. Si el CSV fuente contiene una columna contextual real como `casos_clasico`, HU009 puede preservarla mediante una frontera de contexto separada del `ChampionInput`. Si no existe, `current_status` debe quedar parcial/no disponible según el contrato final.

`p50` no debe inventarse si la fuente actual no lo entrega.

### 5.4 SHAP local PR12

PR12 contiene `scripts/generate_shap.py`, cuyo contrato declara artefactos locales:

```text
model/shap_local_T1.parquet
model/shap_local_T2.parquet
```

con filas asociadas a `divipola`, `anio`, `mes` y valores `shap_<feature>`.

HU009 puede incorporar una estrategia de explicación materializada, pero únicamente si:

- el artefacto está materializado/configurado explícitamente;
- puede localizar la fila exacta del municipio + periodo + horizonte;
- los features corresponden al contrato del Champion usado;
- no existe ambigüedad temporal.

Si no se cumplen esas condiciones:

```text
explanation.available = false
```

sin fallback.

### 5.5 Historia

HU007 ya expone historial de **predicciones persistidas** mediante `GET /predictions/history`.

HU009 puede consumir ese historial en frontend como “Historial de predicciones”. No debe renombrarlo como historial epidemiológico observado.

El histórico epidemiológico `observed_cases/p25/p50/p75/is_excess` solo podrá exponerse cuando exista una fuente real y persistida con esa semántica.

---

## 6. Arquitectura objetivo

```text
POST monthly-runs
    |
    v
HU002 ValidatedMonthlyUpload
    |
    +--> QualityContextBuilder
    |
    +--> CurrentStatusContextBuilder (solo datos reales disponibles)
    |
    v
HU004 ChampionService
    |
    +--> ChampionOutput
    |
    +--> optional LocalExplanationProvider
    |
    v
HU005 ResultMapper / Snapshot Enricher
    |
    v
HU006 SQLite
    |
    v
HU007 Query Services
    |
    v
GET latest/history
    |
    v
HU008 React / HttpDengueRepository
    |
    v
Panels de metadata / calidad / contexto / explicación / historial
```

Regla estructural:

- el orquestador no importa pandas, SHAP, XGBoost ni SQLite;
- el frontend no importa lógica ML;
- los providers opcionales quedan detrás de puertos;
- persistencia y consulta siguen desacopladas del origen concreto de la explicación.

---

## 7. Contratos de dominio objetivo

Los nombres concretos pueden variar, pero la semántica debe ser equivalente.

### 7.1 `DataQualitySnapshot`

```python
@dataclass(frozen=True, slots=True)
class DataQualitySnapshot:
    status: str
    last_observed_month: str
    epidemiological_completeness: float | None
    climate_completeness: float | None
    warnings: tuple[str, ...]
```

Reglas:

- `last_observed_month` debe corresponder al corte real del run;
- métricas de completitud solo se calculan si existe una definición explícita de numerador/denominador;
- no asumir porcentajes arbitrarios;
- un archivo HU002 aceptado permite afirmar que las 39 features requeridas son numéricas, finitas y no nulas;
- si no puede demostrarse separación epidemiológica/climática, esos porcentajes quedan `None` y se documenta warning/limitación.

### 7.2 `CurrentStatusSnapshot`

```python
@dataclass(frozen=True, slots=True)
class CurrentStatusSnapshot:
    reference_month: str
    observed_cases: float | None
    p25: float | None
    p50: float | None
    p75: float | None
    ratio_to_p75: float | None
    endemic_zone: str | None
```

Reglas:

- `p25/p75/zona` solo desde campos contractuales reales;
- `p50=None` si no existe fuente;
- `observed_cases=None` si no existe columna contextual real del target;
- `ratio_to_p75` se calcula únicamente en backend si `observed_cases` y `p75>0` existen;
- frontend no recalcula ratio ni zona.

Si la semántica de `zona_canal` no puede demostrarse contra el target vigente, no mapearla silenciosamente.

### 7.3 `DecisionRuleSnapshot`

```python
@dataclass(frozen=True, slots=True)
class DecisionRuleSnapshot:
    type: str
    probability_threshold: float | None
    target_month_p75: float | None
    decision_threshold_cases: float | None
    version: str | None
```

Para el Champion probabilístico vigente:

- el threshold debe provenir del `CandidatePrediction.decision_threshold` ya persistido;
- no copiar un threshold entre T+1/T+2;
- `type="probability_threshold"` solo si `output_type=probability` y existe threshold real;
- campos no respaldados quedan `None`.

### 7.4 `LocalExplanation`

```python
@dataclass(frozen=True, slots=True)
class LocalExplanation:
    available: bool
    method: str | None
    scope: str | None
    top_features: tuple[ExplanationFeature, ...]
```

```python
@dataclass(frozen=True, slots=True)
class ExplanationFeature:
    feature: str
    value: float | str | None
    contribution: float
    group: str | None
```

Invariantes:

```text
available=false
→ method=None
→ scope=None
→ top_features=()
```

Si `available=true`:

- debe haber al menos una feature;
- `scope` debe ser `local`;
- contributions deben ser finitas;
- el artefacto debe corresponder al mismo Champion/feature contract cuando esa metadata esté disponible;
- para `method=shap`, la explicación debe corresponder a una inferencia concreta, no a agregación global.

---

## 8. Frontera de explicabilidad

Crear un puerto framework-agnostic equivalente a:

```python
class LocalExplanationProvider(Protocol):
    def get_explanation(
        self,
        *,
        reference_month: str,
        divipola: str,
        horizon: str,
        champion_metadata: ChampionMetadata,
    ) -> LocalExplanation: ...
```

Implementaciones posibles:

### `UnavailableExplanationProvider`

Devuelve exclusivamente:

```text
available=false
```

Debe ser explícito, nunca un fallback silencioso desde un provider fallido.

### `MaterializedShapExplanationProvider`

Puede leer artefactos locales previamente materializados/configurados.

Debe:

- resolver T+1/T+2 explícitamente;
- buscar `divipola + anio + mes` exactos;
- ordenar top features por `abs(contribution)`;
- preservar signo de contribution;
- no usar PNG como fuente numérica;
- no generar SHAP durante `GET latest`;
- no ejecutar el modelo;
- no recalcular SHAP por request;
- no descargar desde S3/DVC en request.

La materialización de archivos es configuración/deployment, no lógica HTTP.

---

## 9. Persistencia

HU009 debe extender la persistencia SQLite sin romper HU006/HU007.

Se permiten tablas nuevas o columnas/JSON estructurados, pero se recomienda separar responsabilidades, por ejemplo:

```text
runs
predictions
snapshot_quality
current_status
prediction_explanations
```

Requisitos:

- relaciones por `run_id` y, para explicación, `(run_id, divipola, horizon)`;
- `FOREIGN KEY`;
- escritura dentro de la misma unidad de trabajo del snapshot exitoso cuando el enriquecimiento pertenezca al run;
- `latest` nunca mezcla enriquecimientos de runs distintos;
- un fallo al obtener una explicación opcional no puede reemplazar una predicción válida con datos falsos;
- decidir explícitamente cuándo un fallo de enrichment es fatal y cuándo se degrada a `available=false + warning`;
- schema inicializable de forma idempotente;
- bases existentes de HU006 deben seguir siendo legibles/migrables en local.

No guardar artefactos SHAP completos dentro de SQLite si solo se requieren top features por inferencia.

---

## 10. API read-only enriquecida

Mantener endpoints existentes:

```text
GET /api/v2/predictions/latest
GET /api/v2/predictions/history
GET /api/v2/runs/{run_id}
```

No crear un endpoint que ejecute explicabilidad bajo demanda.

### 10.1 `latest`

Debe poder exponer de forma aditiva y compatible:

- metadata Champion;
- `data_quality`;
- `current_status` por municipio cuando exista;
- `decision_rule` por predicción;
- `explanation` por predicción;
- warnings.

Los campos existentes de HU007/HU008 no deben cambiar de significado.

### 10.2 `history`

Conservar la semántica de historial de snapshots/predicciones persistidas.

Si se agregan enriquecimientos al history:

- deben pertenecer al mismo run de cada item;
- respetar paginación/filtros existentes;
- no reconstruir historia epidemiológica desde lags.

### 10.3 Compatibilidad

El contrato puede evolucionar de forma aditiva dentro de v2.

HU008 debe continuar funcionando si un snapshot antiguo no tiene enrichments:

```text
campo ausente/null
→ UI “No disponible”
```

No migrar datos históricos inventando valores.

---

## 11. Dashboard

HU009 debe evolucionar el dashboard sin romper la integración HU008.

### 11.1 Metadata y trazabilidad

Mostrar como mínimo cuando exista:

- Champion nombre/versión;
- corte `reference_month`;
- fecha/hora de inferencia;
- run_id;
- output_type;
- feature contract version;
- threshold por horizonte.

No presentar metadata de entrenamiento como si fuera gestionada por el dashboard.

### 11.2 Calidad

Reemplazar el placeholder de calidad por información real:

- status;
- last observed month;
- completitud solo si existe;
- warnings.

Warnings deben ser visibles y no solo estar en tooltip.

### 11.3 Estado actual / canal

Mostrar únicamente campos reales recibidos del backend.

Si `current_status` es parcial:

- mostrar valores disponibles;
- indicar explícitamente los ausentes;
- no reconstruirlos en React.

### 11.4 Explicabilidad

Para la ciudad seleccionada y cada horizonte:

- si `available=false`: “Explicación local no disponible para esta predicción”;
- si `available=true`: mostrar top features, contribution y método;
- usar etiqueta “SHAP local” únicamente si `method=shap` y `scope=local`;
- diferenciar contributions positivas/negativas sin afirmar causalidad;
- no generar recomendaciones clínicas/epidemiológicas automáticas desde SHAP.

### 11.5 Historial

Consumir `GET /predictions/history` para presentar historia de predicciones reales si aporta valor.

Etiquetar claramente:

```text
Historial de predicciones
```

No “Historial epidemiológico” salvo que exista esa fuente real.

---

## 12. Tratamiento de información ausente

Estados obligatorios:

```text
available
partial
unavailable
```

No es necesario introducir ese enum literalmente si los DTOs nullable lo expresan con claridad.

Reglas:

- ausencia de explanation no es error del dashboard;
- ausencia de p50 no bloquea latest;
- ausencia de observed_cases no autoriza derivarlo;
- artefacto SHAP no configurado → `available=false`;
- artefacto configurado pero corrupto/incompatible → warning/error controlado según la frontera definida, nunca datos parciales sin trazabilidad.

---

## 13. Errores

Reutilizar `ErrorEnvelope` existente.

Si se necesita código nuevo para una dependencia opcional, preferir no ampliar la taxonomía salvo que exista una falla operacional diferenciable y accionable.

Para errores de consulta/persistencia mantener:

- `PERSISTENCE_FAILED`;
- `PREDICTION_NOT_FOUND`;
- `INTERNAL_ERROR`.

No exponer rutas locales de artefactos, SQL, stacktrace o contenido completo del CSV.

---

## 14. Seguridad y privacidad

HU009 no agrega autenticación ni cloud.

Debe garantizar:

- sin AWS credentials;
- sin tokens;
- sin paths internos expuestos al frontend;
- sin serializar las 39 features completas al navegador por defecto;
- top features solo contiene lo necesario para explicación;
- no guardar CSV en frontend;
- no publicar archivos SHAP completos en `public/`.

---

## 15. Fuera de alcance

HU009 NO implementa:

- entrenamiento/reentrenamiento;
- generación de SHAP online;
- cálculo SHAP en FastAPI por request;
- selección/promoción Champion;
- AWS/EC2/S3 deployment;
- `dvc pull` por request;
- MLflow server obligatorio por request;
- auth/RBAC;
- feature engineering desde datos crudos;
- imputación de datos faltantes;
- recomendaciones médicas;
- causalidad a partir de SHAP;
- E2E completo/deployment HU010.

---

## 16. Tareas de implementación

### T01 — Baseline y auditoría de fuentes

Antes de tocar código:

- ejecutar tests API/frontend actuales;
- inspeccionar contratos HU004/HU006/HU007/HU008;
- inspeccionar PR12 `generate_shap.py` y artefactos reales disponibles;
- documentar qué enrichments pueden ser `available=true` hoy y cuáles no.

### T02 — Contratos de dominio

Definir tipos inmutables para:

- quality;
- current status;
- decision rule;
- explanation/top features;
- warnings.

### T03 — Quality builder

Construir calidad únicamente desde hechos del upload validado.

### T04 — Contexto epidemiológico

Mapear únicamente campos con semántica demostrable del corte.

Si se preservan columnas contextuales del CSV:

- mantenerlas fuera del `ChampionInput`;
- declarar allowlist explícita;
- no relajar validaciones HU002.

### T05 — Explanation provider

Crear puerto y provider materializado opcional.

No ejecutar SHAP en request.

### T06 — Snapshot enrichment

Adjuntar enrichments al mismo run/snapshot sin modificar predicciones nativas.

### T07 — Persistencia SQLite

Persistir enrichments con integridad referencial e idempotencia.

### T08 — Query API

Extender DTOs/latest/history de manera aditiva y read-only.

### T09 — Frontend HTTP DTO/map

Agregar campos opcionales al `HttpDengueRepository` sin inventar defaults.

### T10 — UI

Reemplazar placeholders solo cuando exista información real.

### T11 — Historia de predicciones

Consumir `GET /predictions/history` si se incorpora visualmente.

### T12 — Tests

Cubrir dominio, persistencia, API, repository frontend y UI.

### T13 — Documentación/evidencia

Actualizar fuentes canónicas y crear evidencia HU009.

---

## 17. Criterios de aceptación

### Metadata y regla

**CA01.** Champion nombre/versión/output type/feature contract provienen del snapshot real.  
**CA02.** El threshold se conserva por municipio/horizonte y nunca se reemplaza por `0.5`.  
**CA03.** Output no probabilístico nunca se presenta como porcentaje.  
**CA04.** Metadata opcional ausente permanece `null`/no disponible.

### Calidad

**CA05.** `data_quality.last_observed_month` corresponde al mismo corte del run.  
**CA06.** Toda métrica de completitud tiene cálculo/documentación reproducible.  
**CA07.** No se inventan porcentajes de completitud.  
**CA08.** Warnings persistidos llegan al frontend sin ocultarse.

### Estado actual

**CA09.** P25/P75/zona se exponen solo si su semántica está demostrada para el corte/target.  
**CA10.** `observed_cases` no se deriva desde lags.  
**CA11.** `p50` permanece nulo si no existe fuente real.  
**CA12.** `ratio_to_p75` solo se calcula backend cuando existen observed_cases y p75 válido.  
**CA13.** React no calcula percentiles, ratio ni zona.

### Explicabilidad

**CA14.** `available=true` exige explicación exacta para municipio + corte + horizonte.  
**CA15.** SHAP solo se etiqueta como tal con `method=shap` y `scope=local`.  
**CA16.** Importancia global nunca se presenta como SHAP local.  
**CA17.** Top features preserva contribution real y su signo.  
**CA18.** Provider ausente produce `available=false`, no mocks.  
**CA19.** GET latest/history no ejecuta modelo ni cálculo SHAP.  
**CA20.** Ningún request ejecuta DVC/S3/MLflow obligatorio.

### Persistencia/API

**CA21.** Enrichments quedan asociados al mismo `run_id` que la predicción.  
**CA22.** latest nunca mezcla calidad/explicación de otro run.  
**CA23.** snapshots HU006 antiguos siguen siendo consultables.  
**CA24.** API v2 evoluciona aditivamente y preserva nullability.  
**CA25.** Historial de predicciones conserva su semántica y no se presenta como historia epidemiológica.

### Dashboard

**CA26.** Paneles muestran información real cuando existe y estado no disponible cuando no.  
**CA27.** Warnings de calidad son visibles.  
**CA28.** Explicabilidad no afirma causalidad.  
**CA29.** Refresh continúa ejecutando solo GET.  
**CA30.** No reaparecen mocks ni cálculos analíticos en React.

### Calidad técnica

**CA31.** Suite API completa queda verde.  
**CA32.** Tests/typecheck/lint/build frontend quedan verdes.  
**CA33.** No se agregan secretos, cloud ni runtime ML al frontend.  
**CA34.** Existe evidencia versionada suficiente para auditoría.

---

## 18. Autovalidaciones

**AV01.** Baseline exacto API/frontend registrado.  
**AV02.** Inspección de fuentes PR12 y disponibilidad real de SHAP documentada.  
**AV03.** Test metadata Champion preservada.  
**AV04.** Test thresholds T+1/T+2 independientes.  
**AV05.** Test output no probabilístico no se formatea como porcentaje.  
**AV06.** Test quality corte correcto.  
**AV07.** Test completeness solo bajo definición reproducible.  
**AV08.** Test warnings round-trip persistencia → API → frontend.  
**AV09.** Test current status no usa lag como observed_cases.  
**AV10.** Test p50 ausente permanece null.  
**AV11.** Test ratio solo cuando p75>0 y observed_cases existe.  
**AV12.** Test explanation unavailable sin provider.  
**AV13.** Test explanation exacta por municipio/periodo/horizonte.  
**AV14.** Test mismatch temporal no devuelve explanation.  
**AV15.** Test SHAP top features ordenadas por abs contribution preservando signo.  
**AV16.** Test no global importance como local.  
**AV17.** Test latest read-only: cero Champion/SHAP generation.  
**AV18.** Test history read-only.  
**AV19.** Test enrichments pertenecen al mismo run.  
**AV20.** Test compatibilidad DB/snapshot anterior sin enrichments.  
**AV21.** Test frontend no fabrica defaults.  
**AV22.** Test UI available/unavailable/partial.  
**AV23.** Test Refresh sigue GET-only.  
**AV24.** Buscar imports frontend: sin shap/xgboost/pandas/ML.  
**AV25.** Buscar runtime request: sin `dvc pull`, S3 ni MLflow obligatorio.  
**AV26.** Ejecutar suite API completa.  
**AV27.** Ejecutar tests/typecheck/lint/build frontend.  
**AV28.** `git diff --check` y ausencia de artefactos/runtime accidentalmente versionados.

---

## 19. Estrategia mínima de pruebas

### Backend

Cubrir al menos:

1. quality desde upload válido;
2. metadata opcional nula;
3. current status con fuente completa;
4. current status parcial;
5. p50 no disponible;
6. ratio p75 válido;
7. p75 cero/nulo;
8. explanation provider unavailable;
9. SHAP local exacto T+1;
10. SHAP local exacto T+2;
11. Bucaramanga/Cali independientes;
12. mismatch de corte;
13. mismatch de horizonte;
14. artefacto corrupto/incompatible;
15. top features/signo;
16. persistencia enrichments;
17. lectura latest;
18. lectura history;
19. snapshot legacy sin enrichments;
20. cero ejecución ML en GET.

### Frontend

Cubrir al menos:

1. DTO enriquecido;
2. DTO legacy/minimal;
3. quality disponible;
4. quality warnings;
5. current status parcial;
6. explanation unavailable;
7. explanation SHAP local;
8. contribution positiva/negativa;
9. threshold independiente;
10. output no probabilístico;
11. historial de predicciones;
12. Refresh GET-only;
13. no mocks;
14. build producción.

---

## 20. Evidencia requerida

Crear:

```text
dashboard_prototipos/docs/hu009_evidencia_implementacion.md
```

Debe registrar:

- rama/PR/SHA;
- baseline;
- fuentes reales encontradas;
- disponibilidad efectiva de SHAP;
- decisiones de `available=true/false`;
- contratos agregados;
- persistencia/migración SQLite;
- API enriquecida;
- mapping frontend;
- paneles actualizados;
- tests exactos;
- warnings;
- CA01–CA34;
- AV01–AV28;
- gaps que permanecen para HU010 u otra HU.

No afirmar que existe una fuente si solo existe como ejemplo documental.

---

## 21. Documentación a mantener alineada

Actualizar cuando la implementación lo requiera:

- `dashboard_prototipos/docs/API-sign.md`;
- `dashboard_prototipos/docs/arquitectura.md`;
- `dashboard_prototipos/docs/diccionario-de-datos.md`;
- `dashboard_prototipos/docs/implementacion.md`;
- `dashboard_prototipos/dengue-watch-pro/README.md`.

Si el contrato real difiere del esquema objetivo previo, documentar explícitamente la diferencia en lugar de simular compatibilidad.

---

## 22. Definition of Done

HU009 puede declararse `[COMPLETADA — DESARROLLO]` únicamente cuando:

- metadata y thresholds provienen de fuentes reales;
- calidad/frescura es reproducible y persistida;
- current status solo expone datos demostrables;
- no se deriva observed_cases desde lags;
- p50 no se inventa;
- explanation local respeta municipio+corte+horizonte;
- SHAP se etiqueta correctamente o queda unavailable;
- enrichments persisten con el mismo run;
- latest/history continúan read-only;
- snapshots antiguos siguen siendo consultables;
- dashboard representa available/partial/unavailable;
- no existen mocks/fallback productivos;
- no se ejecuta ML/SHAP/DVC/S3 en GET;
- API tests quedan verdes;
- frontend test/typecheck/lint/build quedan verdes;
- CA01–CA34 PASS;
- AV01–AV28 PASS;
- evidencia está versionada.

---

## 23. Gate hacia HU010

HU010 podrá ejecutar E2E del flujo completo cuando HU009 haya demostrado que un snapshot puede viajar:

```text
upload
→ ChampionOutput
→ persistencia
→ enrichments reales disponibles
→ GET latest/history
→ dashboard
```

HU010 será responsable del E2E/deployment final. HU009 permanece local-only.

---

## 24. Regla final

> La explicabilidad aumenta confianza solo cuando es trazable. En BIOMAC, “no disponible” es una respuesta válida y preferible a una explicación, percentil, calidad o contexto inventado.
