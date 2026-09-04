# HU010 — Pruebas E2E y cierre de integración BIOMAC

**Estado:** `[IMPLEMENTADA — BLOQUEADA POR GOLDEN PR12]`
**Identificador:** `HU-INT-010`  
**Prioridad:** ALTA  
**Dependencias:** HU001–HU009 `[COMPLETADAS — DESARROLLO]`  
**Ámbito vigente:** Entregable 2, validación local reproducible; sin AWS/deployment productivo en esta HU  
**Frontend objetivo:** `dashboard_prototipos/dengue-watch-pro`  
**Backend objetivo:** `/api/v2`  
**Champion objetivo:** frontera HU004; para la prueba académica puede usarse la salida materializada real de PR #12  
**Documentos fuente:** `arquitectura.md`, `API-sign.md`, `diccionario-de-datos.md`, `implementacion.md`, `prueba-funcional-api.md`, HU001–HU009 y evidencias asociadas.

---

## 1. Contexto

HU001–HU009 implementaron el camino operativo BIOMAC:

```text
CSV mensual ya preparado
→ POST /api/v2/monthly-runs
→ HU002 validación
→ HU003 ChampionInput
→ HU004 ChampionService
→ HU005 orquestación
→ HU006 SQLite
→ HU007 latest/history/run
→ HU008 dashboard HTTP
→ HU009 metadata/calidad/contexto/explicación disponible
```

HU010 no agrega nueva lógica analítica. Su propósito es demostrar que las fronteras ya implementadas funcionan juntas de forma reproducible y cerrar las brechas de integración observadas antes de declarar terminado el MVP técnico del Entregable 2.

La prueba funcional existente en `prueba-funcional-api.md` es una pieza de esta HU, pero HU010 amplía la evidencia hasta el dashboard y los contratos read-only.

---

## 2. Historia de usuario

**Como** equipo BIOMAC  
**quiero** ejecutar una batería reproducible de pruebas E2E y de contrato sobre el flujo mensual completo  
**para** demostrar que una carga válida produce un snapshot persistido visible en el dashboard, que los errores no destruyen el último resultado válido y que las consultas no disparan inferencia.

---

## 3. Objetivo verificable

HU010 debe demostrar con evidencia automatizada y manual que:

1. FastAPI inicia con una composición local real y responde health;
2. un CSV válido del mismo corte que una salida Champion real/materializada produce `201 COMPLETED`;
3. Bucaramanga y Cali quedan persistidas con T+1/T+2 reales;
4. probability/threshold/label del API coinciden con la salida Champion usada;
5. `GET latest` devuelve el run recién completado sin ejecutar nueva inferencia;
6. `GET history` incorpora el nuevo run y mantiene orden/semántica de historial de predicciones;
7. `GET runs/{run_id}` devuelve la trazabilidad del run;
8. Refresh del dashboard hace exclusivamente GET latest;
9. un POST exitoso actualiza **latest e history** del frontend;
10. un POST fallido conserva el snapshot anterior;
11. reintento idéntico respeta idempotencia durable;
12. reiniciar FastAPI conserva resultados SQLite;
13. nullability/enrichments HU009 se preservan sin mocks;
14. la UI no calcula probability, threshold, label, canal, SHAP o calidad;
15. no se ejecutan entrenamiento, MLflow, DVC, S3 o scripts de modelado durante GET/Refresh;
16. toda evidencia puede reproducirse localmente desde instrucciones versionadas.

---

## 4. Decisión de alcance — local first

Aunque `implementacion.md` conserva una arquitectura futura Lovable → EC2, el alcance vigente del Entregable 2 es **local-only**.

HU010 NO despliega AWS ni exige infraestructura remota para poder cerrarse.

La validación física obligatoria es:

```text
Browser local / frontend local
        ↓ HTTP
FastAPI local
        ↓
SQLite local
        ↓
ChampionService configurado localmente
        ↓
Salida materializada real PR12 para la prueba funcional
```

Deployment/cloud queda como evolución posterior y puede documentarse como readiness, nunca marcarse PASS sin haberse ejecutado.

---

## 5. Principios de prueba

### D01 — No mocks en el E2E principal

El escenario happy-path principal debe usar:

- `HttpDengueRepository` real;
- FastAPI real;
- SQLite real temporal/local;
- contrato Champion real;
- salida materializada producida por PR12 o fixture derivada exactamente de una salida real registrada.

Mocks pueden usarse en unit tests ya existentes, pero no como evidencia del flujo E2E principal.

### D02 — No mezclar ramas

PR12 y `main` deben permanecer en checkouts/worktrees separados. La integración se hace mediante la frontera HU004, no mediante merge/cherry-pick para la prueba.

### D03 — Un único corte

CSV mensual, ChampionResult y `reference_month` deben corresponder al mismo periodo.

### D04 — Evidencia de correspondencia

Antes del POST deben registrarse los cuatro valores Champion esperados:

```text
divipola | horizon | target_month | probability | threshold | label
```

Después se comparan contra HTTP y SQLite.

### D05 — Read-only significa cero inferencia

`latest`, `history`, `runs/{id}` y Refresh no pueden invocar `ChampionService.produce` ni generar SHAP.

### D06 — Sin falsos PASS

Un escenario no ejecutado no puede documentarse como PASS. Debe quedar `NOT_RUN`, `BLOCKED` o `OUT_OF_SCOPE` con motivo.

---

## 6. Precondiciones

Antes de iniciar el E2E:

- `main` contiene HU001–HU009;
- suites API/frontend están verdes;
- PR12 real queda identificado por SHA;
- existen los artefactos necesarios para producir la salida Champion del periodo elegido;
- existe un CSV mensual válido HU002 del mismo corte;
- SQLite de prueba usa una ruta dedicada;
- archivos runtime están fuera de Git.

Si PR12 no puede materializar `features_mensual.parquet`, el escenario con salida nueva del modelo queda bloqueado y debe documentarse. No generar datos sintéticos para reemplazarlo.

---

## 7. Composición local E2E

HU010 debe consolidar un bootstrap reproducible para pruebas, reutilizando las dependencias existentes.

Debe quedar detrás de `runtime/`, `scripts/` de soporte de prueba o una utilidad de tests claramente no productiva.

Flujo:

```text
MaterializedChampionResultProvider
→ MaterializedChampionService
→ MonthlyPredictionOrchestrator
→ MonthlyRunPersistenceService
→ create_app(...)
→ Uvicorn/Test server
```

Reglas:

- no modificar `app = create_app()` global para introducir comportamiento de demo implícito;
- no hardcodear artefactos PR12 en producción;
- rutas runtime/config se proveen explícitamente;
- no fallback materialized ↔ executable.

---

## 8. Escenarios E2E obligatorios

### E01 — Health

```text
GET /api/v2/health
→ 200
```

Registrar readiness real.

### E02 — Primera carga válida

```text
POST /api/v2/monthly-runs
file=<monthly_REF_MONTH.csv>
reference_month=REF_MONTH
→ 201
→ COMPLETED
```

Validar `run_id`, hash, Champion version y cuatro predicciones.

### E03 — Correspondencia Champion → API

Para las cuatro combinaciones Bucaramanga/Cali × T+1/T+2 comprobar igualdad de:

- `target_month`;
- `probability` cuando aplica;
- `decision_threshold`;
- `label`;
- output type.

No usar tolerancias arbitrarias; si hay floats serializados, definir tolerancia numérica mínima explícita.

### E04 — Persistencia SQLite

Comprobar que el mismo `run_id` existe en:

- `runs`;
- `predictions`;
- enrichments HU009 cuando correspondan.

### E05 — Latest

```text
GET /api/v2/predictions/latest
→ 200
→ run_id == E02.run_id
```

Debe contener Bucaramanga/Cali y T+1/T+2 según el snapshot persistido.

### E06 — History

```text
GET /api/v2/predictions/history
```

Debe incluir el run completado y conservar el contrato de historial de predicciones.

### E07 — Run detail

```text
GET /api/v2/runs/{run_id}
→ 200
```

Validar estado `COMPLETED`, corte, hashes/timestamps y ausencia de datos internos sensibles.

### E08 — Idempotencia

Repetir exactamente mismo:

```text
reference_month + bytes archivo + Champion version
```

Debe recuperar/reconocer el mismo resultado lógico según contrato HU005/HU006 y no crear snapshots contradictorios.

Registrar cantidad de runs/predictions antes y después.

### E09 — Period conflict/datos diferentes

Mismo `reference_month` con archivo diferente no puede sobrescribir silenciosamente el snapshot previo.

Validar respuesta contractual vigente.

### E10 — Archivo inválido

Al menos:

- falta feature;
- municipio faltante;
- columna prohibida;
- mes distinto;
- valor NaN/no finito.

Debe fallar antes del Champion y conservar latest previo.

### E11 — Champion no disponible

Con provider explícitamente no disponible:

- run falla controladamente;
- latest previo permanece;
- no se crea snapshot exitoso nuevo.

### E12 — Reinicio de API

Detener FastAPI y levantarlo usando la misma DB.

Luego:

```text
GET latest
→ mismo último run COMPLETED
```

### E13 — Refresh read-only

Instrumentar `ChampionService` o contador equivalente.

```text
contador antes
→ GET latest / Refresh
→ contador después == antes
```

También cero POST desde botón Refresh.

### E14 — History read-only

`GET history` no incrementa contador de Champion y no escribe en DB.

### E15 — Frontend happy path

Con frontend apuntando a API local:

- apertura carga latest;
- selector Bucaramanga/Cali funciona;
- muestra T+1/T+2;
- metadata/calidad/contexto nullable se representa correctamente;
- no usa mocks.

### E16 — Upload frontend

Desde UI o prueba de integración navegador:

```text
Actualizar datos
→ CSV + mes
→ confirmación
→ POST
→ COMPLETED
→ latest actualizado
→ history actualizado
```

### E17 — Refresh frontend

Botón `Actualizar vista`:

- ejecuta latest;
- no ejecuta monthly-runs;
- no ejecuta history por necesidad de Refresh salvo decisión explícita;
- conserva stale snapshot ante error.

### E18 — Error frontend

Con backend devolviendo error controlado en upload:

- snapshot previo continúa visible;
- error saneado;
- retry disponible;
- sin fallback mock.

---

## 9. Corrección obligatoria detectada al cerrar HU009

HU009 agregó una query independiente de historial con `staleTime=5 min`, pero HU008/HU009 invalidan únicamente `latest` después de POST exitoso.

HU010 debe corregir:

```text
POST COMPLETED
→ invalidate latestPredictionKey
→ invalidate predictionHistoryKey
```

No es aceptable que el dashboard muestre una predicción nueva mientras el panel “Historial de predicciones” siga temporalmente desactualizado.

Pruebas obligatorias:

1. mutation exitosa invalida/refetchea latest;
2. mutation exitosa invalida/refetchea history;
3. mutation fallida no invalida un nuevo estado como si hubiera éxito;
4. Refresh manual sigue siendo latest-only.

---

## 10. Estrategia de automatización

HU010 debe priorizar pruebas automatizadas en dos capas:

### 10.1 API/integración Python

Agregar tests que compongan servicios reales con SQLite temporal y provider materializado controlado.

No reemplazar persistencia con mocks en estos escenarios.

### 10.2 Frontend/integración

Usar la infraestructura existente de Vitest/Testing Library para contratos y server-state.

Para browser E2E real puede introducirse Playwright **solo si aporta una prueba reproducible y estable**. Si no se introduce, la prueba navegador manual debe documentarse paso a paso y no presentarse como automatizada.

No agregar Cypress/Playwright únicamente para aumentar tooling sin ejecutar un escenario real.

---

## 11. Golden fixture

Para hacer reproducible el E2E sin depender de PR12 en cada corrida automática, HU010 puede crear un fixture pequeño de **ChampionResult** únicamente si:

1. fue capturado desde una salida real de PR12;
2. se documenta PR12 SHA;
3. se documenta `reference_month`;
4. se documenta hash del fixture;
5. no contiene datos sensibles/pesados;
6. no se modifica manualmente para hacer pasar tests.

Ese fixture prueba la frontera materializada HU004, no sustituye la prueba manual de generación real desde PR12.

Debe quedar claramente nombrado `golden`/`fixture`, nunca como predicción actual productiva.

---

## 12. Validación de contrato frontend/API

Agregar validaciones que detecten cambios incompatibles en:

- `schema_version`;
- prediction snapshot;
- Champion metadata;
- prediction outputs nullable;
- decision rule;
- explanation;
- data quality;
- current status;
- history;
- ErrorEnvelope.

Un campo HU009 ausente en snapshot legacy debe seguir funcionando.

---

## 13. Seguridad y limpieza

Comprobar:

- no secrets/env reales versionados;
- no CSV runtime versionado accidentalmente;
- no SQLite DB runtime versionada;
- no parquets/modelos agregados por HU010;
- no rutas locales de usuario en docs/fixtures;
- errores HTTP sin stacktrace/SQL/path interno;
- frontend sin `dangerouslySetInnerHTML`;
- no contenido completo del CSV en logs.

---

## 14. Performance mínimo de demo local

HU010 no es una HU de optimización, pero debe registrar tiempos observados de:

- health;
- POST mensual;
- latest;
- history.

No establecer SLOs ficticios. Solo documentar mediciones del ambiente de prueba para detectar bloqueos evidentes.

---

## 15. Evidencia requerida

Crear:

```text
dashboard_prototipos/docs/hu010_evidencia_e2e_cierre.md
```

Debe registrar:

- fecha;
- OS/Python/Node;
- SHA `main`/rama HU010;
- SHA PR12 usado;
- `reference_month`;
- hash CSV;
- hash ChampionResult golden/materializado;
- configuración no sensible;
- comandos ejecutados;
- resultados de suites;
- tabla E01–E18;
- comparación Champion vs API;
- evidencia SQLite;
- evidencia idempotencia;
- evidencia contador read-only;
- evidencia latest/history post upload;
- frontend/manual browser si aplica;
- tiempos observados;
- warnings;
- gaps/out-of-scope;
- CA/AV;
- veredicto final.

No incluir secretos ni archivos pesados.

---

## 16. Criterios de aceptación

### Flujo operativo

**CA01.** Health responde 200 con composición local de prueba.  
**CA02.** CSV válido produce run `COMPLETED`.  
**CA03.** API coincide con los cuatro resultados Champion del mismo corte.  
**CA04.** Snapshot se persiste antes del 201.  
**CA05.** Latest devuelve el run recién completado.  
**CA06.** History contiene el run recién completado.  
**CA07.** Run detail es trazable.  
**CA08.** Repetición idéntica respeta idempotencia.  
**CA09.** Archivo diferente del mismo periodo no sobrescribe silenciosamente.  
**CA10.** Reinicio de API conserva latest.

### Errores y resiliencia

**CA11.** Upload inválido no ejecuta Champion.  
**CA12.** Fallo Champion no reemplaza latest previo.  
**CA13.** Error de persistencia se devuelve saneado.  
**CA14.** Snapshot previo continúa consultable tras run fallido.

### Read-only

**CA15.** GET latest ejecuta cero Champion.  
**CA16.** GET history ejecuta cero Champion.  
**CA17.** GET run ejecuta cero Champion.  
**CA18.** Refresh frontend ejecuta cero POST/inferencia.

### Frontend

**CA19.** Apertura consume API real sin mocks.  
**CA20.** Bucaramanga/Cali y T+1/T+2 se muestran según response.  
**CA21.** POST exitoso actualiza latest.  
**CA22.** POST exitoso actualiza/invalida history.  
**CA23.** POST fallido conserva snapshot previo.  
**CA24.** Nullability HU009 se representa sin valores inventados.  
**CA25.** No existe cálculo ML/epidemiológico en React.

### Reproducibilidad/calidad

**CA26.** Existe golden fixture real o procedimiento reproducible PR12 documentado.  
**CA27.** Suite API completa pasa.  
**CA28.** Suite frontend completa pasa.  
**CA29.** Typecheck/lint/build pasan.  
**CA30.** `compileall`, `pip check` y `git diff --check` pasan.  
**CA31.** Evidencia E01–E18 está versionada.  
**CA32.** Ningún escenario no ejecutado se marca PASS.  
**CA33.** Runtime/secretos/artefactos pesados no quedan versionados.  
**CA34.** HU010 no introduce AWS/deployment productivo fuera del alcance vigente.  
**CA35.** Documentación final queda alineada con el comportamiento realmente probado.

---

## 17. Autovalidaciones

**AV01.** Registrar baseline API/frontend antes de cambios.  
**AV02.** Capturar SHA real PR12 y rama HU010.  
**AV03.** Validar CSV y ChampionResult comparten `reference_month`.  
**AV04.** Comparar las cuatro predicciones Champion ↔ POST/latest.  
**AV05.** Comprobar filas SQLite por mismo `run_id`.  
**AV06.** Repetir POST idéntico y contar runs/snapshots.  
**AV07.** Ejecutar POST conflictivo con archivo diferente.  
**AV08.** Ejecutar casos INVALID_UPLOAD.  
**AV09.** Ejecutar Champion unavailable.  
**AV10.** Reiniciar API y repetir latest.  
**AV11.** Instrumentar contador Champion para latest.  
**AV12.** Instrumentar contador Champion para history.  
**AV13.** Instrumentar contador Champion para run detail.  
**AV14.** Test hook: Refresh GET-only/POST cero.  
**AV15.** Test hook: POST success invalida latest.  
**AV16.** Test hook: POST success invalida history.  
**AV17.** Test hook: POST error conserva snapshot.  
**AV18.** Test DTO enriched y legacy.  
**AV19.** Test no-fallback mock.  
**AV20.** Revisar frontend por cálculos analíticos prohibidos.  
**AV21.** Ejecutar suite API completa.  
**AV22.** Ejecutar `compileall` y `pip check`.  
**AV23.** Ejecutar frontend test/typecheck/lint/build.  
**AV24.** Ejecutar `git diff --check`.  
**AV25.** Revisar `git status` por runtime/env/DB/CSV/parquet.  
**AV26.** Registrar tiempos observados.  
**AV27.** Verificar que los GET no importan/ejecutan DVC/S3/MLflow/modelos.  
**AV28.** Verificar ErrorEnvelope saneado.  
**AV29.** Verificar que history se denomina “Historial de predicciones”.  
**AV30.** Documentar explícitamente escenarios manuales vs automatizados.  
**AV31.** Actualizar `prueba-funcional-api.md` si la ejecución descubre comandos obsoletos.  
**AV32.** Alinear `implementacion.md` con cierre local real y deployment futuro.  
**AV33.** No marcar AWS/Lovable remoto PASS si no se ejecutó.  
**AV34.** Registrar veredicto de cierre del MVP técnico local.

---

## 18. Validaciones finales

Backend:

```bash
.venv/bin/python -m pytest api/tests -q
.venv/bin/python -m compileall -q api/app api/tests
.venv/bin/python -m pip check
```

Frontend, desde `dashboard_prototipos/dengue-watch-pro`:

```bash
npm test
npm run typecheck
npm run lint
npm run build
```

Repositorio:

```bash
git diff --check
git status --short
```

Si se agregan tests E2E de navegador, usar el comando real versionado en `package.json` y documentar versión/resultado exacto.

---

## 19. Definition of Done

HU010 puede declararse:

```text
[COMPLETADA — DESARROLLO / E2E LOCAL]
```

únicamente cuando:

- E01–E18 tienen resultado honesto;
- happy path HTTP real está demostrado;
- API/SQLite/Champion materializado están correlacionados;
- latest/history/run funcionan después del POST;
- idempotencia está demostrada;
- runs fallidos no destruyen latest;
- Refresh es read-only demostrado;
- history se actualiza después de POST exitoso;
- frontend consume API sin mocks;
- HU009 nullability se conserva;
- todas las suites quedan verdes;
- evidencia y hashes están versionados;
- no se incluyen secretos/runtime pesado;
- los escenarios cloud no ejecutados quedan fuera de alcance, no PASS.

---

## 20. Cierre del MVP técnico

Al cerrar HU010, la secuencia HU001–HU010 queda validada para **operación local académica reproducible**.

Esto NO significa automáticamente:

- producción;
- alta disponibilidad;
- seguridad pública completa;
- despliegue AWS;
- autenticación/RBAC;
- automatización de feature engineering desde datos crudos;
- reentrenamiento continuo;
- serving online directo del modelo.

Esas capacidades requieren historias posteriores si el proyecto evoluciona más allá del Entregable 2.

---

## 21. Regla final

> HU010 no agrega inteligencia nueva al sistema. Demuestra que la inteligencia ya producida por el Champion atraviesa correctamente contratos, persistencia, API y dashboard, y que consultar esa inteligencia no vuelve a ejecutarla.
