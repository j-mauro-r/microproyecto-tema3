# HU001 — Base FastAPI y contratos BIOMAC

## 1. Identificación

- **ID canónico:** HU001
- **Alias en backlog:** HU-INT-001
- **Nombre:** Base FastAPI y contratos BIOMAC
- **Estado:** `[PENDIENTE]`
- **Prioridad:** ALTA
- **Tipo:** Backend / Integración / Fundacional
- **Metodología:** DWP (Deep Work Plan)
- **Dependencias previas:** documentación arquitectónica y contractual vigente
- **Habilita:** HU002 — Carga mensual y validación (`HU-INT-002`)
- **Gate posterior:** HU002 no debe iniciar hasta que la API v2 pueda levantarse, el contrato base esté versionado, el manejo de errores sea uniforme y las autovalidaciones de HU001 estén en PASS.
- **Fuentes de verdad:**
  1. `dashboard_prototipos/docs/arquitectura.md`;
  2. `dashboard_prototipos/docs/implementacion.md`;
  3. `dashboard_prototipos/docs/API-sign.md`;
  4. `dashboard_prototipos/docs/plan.md`;
  5. `dashboard_prototipos/docs/diccionario-de-datos.md`;
  6. `dashboard_prototipos/docs/HU-MVP-FastAPI-dashboard.md`.

### Contexto técnico actual del repositorio

- `api/` contiene únicamente `.gitkeep`; por tanto HU001 parte de una base API vacía.
- El repositorio utiliza `.python-version` como referencia de runtime.
- Existe `requirements.txt`; HU001 debe reutilizar la estrategia de dependencias existente y añadir únicamente dependencias mínimas necesarias para API y pruebas.
- No debe crearse una estrategia de empaquetamiento paralela sin necesidad demostrable.

---

## 2. Contexto y problema

La arquitectura objetivo de BIOMAC separa cuatro responsabilidades: dashboard, frontera HTTP FastAPI, orquestación de inferencia y Champion. La carga mensual será el trigger de una predicción futura, mientras que abrir el dashboard o presionar `Refresh` será una consulta read-only del último snapshot persistido.

Antes de implementar upload, preparación de features, ChampionAdapter, persistencia o integración del dashboard, el proyecto necesita una **frontera HTTP estable, versionada, testeable y segura**.

Actualmente `api/` no contiene una aplicación funcional. Si HU002–HU010 se implementaran directamente sobre esta base, cada HU podría introducir convenciones diferentes para configuración, versionamiento, schemas, errores, CORS y trazabilidad HTTP.

HU001 elimina ese riesgo creando la fundación común. No implementa inferencia ni simula disponibilidad de componentes que aún no existen.

---

## 3. Historia de usuario

> **Como** equipo de integración BIOMAC, **quiero** disponer de una API FastAPI v2 con configuración centralizada, contratos Pydantic, trazabilidad por `request_id`, CORS y errores uniformes, **para** que las siguientes HUs puedan implementar carga, inferencia, persistencia y consumo del dashboard sobre una frontera HTTP estable sin acoplarse al modelo Champion.

---

## 4. Objetivo verificable

Al finalizar HU001 deberá ser posible, desde un checkout limpio y sin datos/modelos:

1. importar y levantar la aplicación FastAPI;
2. consultar `GET /api/v2/health` y obtener HTTP 200;
3. exponer `api_version=2.0.0` conforme a `API-sign.md`;
4. declarar de forma veraz la readiness de Champion y storage, sin fingir disponibilidad;
5. generar un `request_id` por petición y devolverlo de forma trazable;
6. cargar configuración exclusivamente desde defaults no sensibles y variables de entorno;
7. configurar CORS mediante allowlist;
8. disponer de schemas Pydantic base para health, runs, Champion, prediction snapshot y error;
9. rechazar campos desconocidos en contratos estrictos donde aplique;
10. transformar errores en un envelope estable sin exponer stack traces, rutas internas ni secretos;
11. generar OpenAPI automáticamente;
12. ejecutar una suite focalizada de pruebas rápidas sin red, DVC, MLflow, datasets ni Champion;
13. demostrar que HU001 no implementó accidentalmente HU002+.

---

## 5. Alcance

### 5.1 Estructura base

Crear como mínimo una estructura equivalente a:

```text
api/
├── __init__.py
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── v2/
│   │       ├── __init__.py
│   │       └── health.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── request_context.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── request_id.py
│   └── schemas/
│       ├── __init__.py
│       ├── health.py
│       ├── runs.py
│       ├── predictions.py
│       └── errors.py
└── tests/
    ├── __init__.py
    ├── test_health.py
    ├── test_contracts.py
    └── test_errors.py
```

La estructura exacta puede ajustarse si Codex demuestra una alternativa más simple y coherente, pero debe conservar separación entre rutas, configuración, middleware y schemas.

### 5.2 Aplicación FastAPI

`api/app/main.py` será el composition root HTTP de esta HU.

Debe:
- crear la instancia `FastAPI`;
- declarar título, versión de API y metadata básica;
- registrar router `/api/v2`;
- registrar CORS;
- registrar middleware de `request_id`;
- registrar handlers uniformes de error;
- mantener `debug=False` por defecto;
- no cargar datasets, DVC, MLflow ni Champion durante import/startup.

### 5.3 Configuración

Centralizar configuración en `api/app/core/config.py` o equivalente.

Debe cubrir como mínimo:
- nombre del servicio;
- versión API `2.0.0`;
- environment (`local`, `test`, etc.);
- CORS origins;
- flag de debug, desactivado por defecto;
- límites/configuración que pertenezcan realmente a HU001.

Reglas:
- secretos reales no se versionan;
- no hardcodear credenciales;
- no usar CORS `*` como configuración productiva por defecto;
- variables de entorno deben tener nombres estables y documentados;
- si se actualiza `example.env`, solo deben agregarse claves no secretas o placeholders.

### 5.4 Health

Implementar:

`GET /api/v2/health`

Contrato base:

```json
{
  "status": "ok",
  "service": "biomac-api",
  "api_version": "2.0.0",
  "champion_ready": false,
  "storage_ready": false
}
```

En HU001 `champion_ready` y `storage_ready` **no deben ponerse en `true` por conveniencia**, porque ChampionAdapter y PredictionRepository pertenecen a HUs posteriores. La implementación debe quedar preparada para que esas señales sean sustituidas posteriormente por checks reales sin romper el contrato.

`status=ok` representa que la frontera HTTP está viva; no implica inferencia disponible.

### 5.5 `request_id`

Toda petición debe disponer de un identificador UUID válido generado por backend.

Como mínimo:
- crear un `request_id` cuando inicia la petición;
- mantenerlo accesible a handlers de error/logging;
- devolverlo en header `X-Request-ID`;
- incluirlo en envelopes de error;
- no depender de estado global mutable compartido entre requests.

HU001 no necesita implementar `run_id`; este se crea cuando HU002/HU005 introduzcan runs operacionales.

### 5.6 CORS

Configurar `CORSMiddleware` mediante allowlist proveniente de configuración.

Debe permitir desarrollo local cuando esté configurado y permitir añadir el dominio del dashboard por variable de entorno.

No considerar CORS como mecanismo de autenticación/autorización.

### 5.7 Schemas Pydantic base

Crear modelos reutilizables alineados con `API-sign.md` v2.0.0 y `diccionario-de-datos.md`.

Como mínimo deben existir tipos/schema para:
- `HealthResponse`;
- estados de run;
- `SourceFileMetadata`;
- `ChampionMetadata`;
- metadata básica de run;
- `TargetDefinition`;
- municipio;
- `DataQuality`;
- `CurrentStatus`;
- `ModelOutput`;
- `DecisionRule`;
- `Explanation` / top features;
- predicción por horizonte;
- forecast por municipio;
- `PredictionSnapshot`;
- `ErrorDetail` / `ErrorEnvelope`.

Reglas:
- utilizar `snake_case`;
- modelar nulabilidad según contrato, no llenar con valores simulados;
- T+1/T+2 deben ser enums/valores controlados cuando aporte validación;
- estados de run deben limitarse a `RECEIVED`, `VALIDATING`, `PREPARING`, `INFERENCING`, `PERSISTING`, `COMPLETED`, `FAILED`;
- contratos estrictos deben usar `extra="forbid"` donde aplique;
- no incorporar lógica epidemiológica dentro de validadores Pydantic.

### 5.8 Errores uniformes

Definir el envelope contractual:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Mensaje controlado",
    "request_id": "uuid",
    "run_id": null,
    "stage": null,
    "details": {}
  }
}
```

HU001 debe implementar como mínimo manejo uniforme para:
- errores de validación HTTP/Pydantic;
- `HTTPException`;
- excepciones inesperadas.

Debe dejar catálogo/tipos preparados para los códigos definidos en `API-sign.md`, sin implementar todavía las condiciones de negocio de HU002+.

Una excepción inesperada debe producir un mensaje genérico al cliente y nunca exponer stack trace, rutas absolutas, variables de entorno o secretos.

### 5.9 OpenAPI

FastAPI debe generar `/openapi.json` y documentación interactiva estándar.

La metadata debe identificar:
- servicio BIOMAC;
- versión `2.0.0`;
- endpoint health bajo `/api/v2`.

No documentar endpoints de HUs futuras como si ya estuvieran implementados.

### 5.10 Dependencias

Inspeccionar primero la estrategia actual del repositorio.

Añadir únicamente las dependencias mínimas para HU001, por ejemplo cuando sean necesarias:
- FastAPI;
- Uvicorn para ejecución local;
- Pydantic Settings o equivalente para configuración;
- pytest/httpx para pruebas.

No modificar dependencias de modelado ni versión Python para resolver problemas ajenos a HU001 sin autorización explícita.

Si alguna dependencia de API no soporta el runtime actual del repositorio, debe documentarse como blocker y proponerse la corrección mínima antes de alterar el runtime global.

### 5.11 Pruebas focalizadas

Crear pruebas rápidas que no requieran:
- datos;
- DVC/S3;
- MLflow;
- Champion;
- red externa;
- dashboard;
- entrenamiento.

Como mínimo probar:
1. import de `app`;
2. health 200;
3. schema exacto de health;
4. versión API;
5. `champion_ready=false` y `storage_ready=false` mientras no existan implementaciones reales;
6. presencia/formato de `X-Request-ID`;
7. dos requests producen IDs independientes;
8. CORS permitido para origen configurado;
9. rechazo de contrato con campo desconocido;
10. validación de enums críticos;
11. envelope de error de request inválido;
12. error inesperado no filtra detalles internos;
13. `/openapi.json` disponible;
14. ausencia de inicialización de ML/data/model al importar la API.

---

## 6. Fuera de alcance

HU001 **no** debe implementar:
- `POST /api/v2/monthly-runs` funcional;
- upload de archivos;
- validación del archivo mensual;
- cálculo de SHA-256 de uploads;
- `InputService`;
- construcción de features;
- canal endémico;
- `ChampionAdapter`;
- carga de artefactos MLflow/joblib/XGBoost;
- inferencia;
- `MonthlyPredictionOrchestrator`;
- `ResultMapper`;
- `PredictionRepository` o `RunRepository` productivos;
- persistencia;
- `GET /runs/{run_id}` funcional;
- `GET /predictions/latest` funcional;
- `GET /predictions/history` funcional;
- integración con Lovable/React;
- autenticación completa;
- Dockerización;
- CI/CD;
- entrenamiento, tuning, evaluación, selección o promoción del Champion.

Tampoco debe inventar datos epidemiológicos para completar schemas o tests. Los fixtures contractuales, cuando sean necesarios, deben estar marcados explícitamente como datos sintéticos de prueba.

---

## 7. Decisiones y restricciones técnicas

### 7.1 API v2 como frontera estable

Todas las rutas de esta línea funcional deben quedar bajo `/api/v2`. HU001 no debe revivir `/api/v1`.

### 7.2 SOLID pragmático

- rutas HTTP delegan y no acumulan lógica transversal;
- configuración tiene una responsabilidad clara;
- middleware de request ID es independiente;
- schemas no dependen de FastAPI endpoints concretos;
- evitar clases/abstracciones sin uso inmediato.

### 7.3 DRY

No duplicar:
- versión API;
- lectura de configuración;
- generación de `request_id`;
- envelope de error;
- enums de horizonte/estado;
- metadata común del Champion/run.

### 7.4 Sin side effects al importar

`import api.app.main` no debe:
- abrir archivos de datos;
- hacer `dvc pull`;
- conectarse a AWS;
- consultar MLflow;
- cargar el Champion;
- crear resultados runtime.

### 7.5 Contrato antes que implementación de negocio

Los schemas representan el contrato acordado, pero no deben simular comportamiento de HUs que aún no existen.

### 7.6 Seguridad mínima

- `debug=False` por defecto;
- CORS allowlist configurable;
- sin secretos en Git;
- errores sanitizados;
- no registrar payloads completos innecesariamente;
- no asumir que CORS protege el endpoint de upload futuro.

### 7.7 Git y alcance del PR

La implementación debe realizarse en una rama propia creada desde `main` actualizado.

El PR de HU001 debe ser focalizado. No debe mezclar cambios del dashboard, modelos, datos o HUs posteriores.

---

## 8. Plan de implementación / tareas DWP

### T01 — Crear rama y validar estado base

**Cambio:** crear rama `feature/hu001-fastapi-base-contracts` o equivalente desde `main` actualizado.

**Resultado esperado:** diff inicial limpio y `api/` confirmado como base sin implementación funcional.

---

### T02 — Auditar runtime y dependencias

**Cambio:** validar `.python-version`, `requirements.txt` y entorno local; identificar dependencias mínimas de HU001.

**Resultado esperado:** estrategia de dependencias explícita, sin cambios de runtime/modelado innecesarios.

**Depende de:** T01.

---

### T03 — Crear estructura de paquetes API

**Cambio:** crear módulos base bajo `api/app/` y `api/tests/`.

**Resultado esperado:** imports limpios y estructura coherente con `arquitectura.md`.

**Depende de:** T02.

---

### T04 — Implementar configuración centralizada

**Cambio:** implementar settings, versión API, environment y CORS configurable.

**Resultado esperado:** configuración testeable y sin secretos hardcodeados.

**Depende de:** T03.

---

### T05 — Implementar schemas contractuales

**Cambio:** crear schemas/enums base alineados con `API-sign.md` v2.0.0 y `diccionario-de-datos.md`.

**Resultado esperado:** contrato reutilizable por HU002–HU009 sin lógica epidemiológica.

**Depende de:** T03-T04.

---

### T06 — Implementar request ID y errores uniformes

**Cambio:** middleware/contexto de `request_id` y handlers de errores.

**Resultado esperado:** cada error puede trazarse sin filtrar detalles internos.

**Depende de:** T04-T05.

---

### T07 — Implementar aplicación y health

**Cambio:** composition root FastAPI, router `/api/v2` y `GET /health`.

**Resultado esperado:** API levantable sin datos/modelo; readiness futura reportada de forma honesta.

**Depende de:** T04-T06.

---

### T08 — Implementar pruebas focalizadas

**Cambio:** tests de health, contratos, request ID, CORS, errores y OpenAPI.

**Resultado esperado:** suite rápida e independiente de ML/data.

**Depende de:** T07.

---

### T09 — Ejecutar autovalidaciones

**Cambio:** ejecutar suite focalizada, import checks y validaciones de alcance.

**Resultado esperado:** AV01–AV15 en PASS o blocker explícito y reproducible.

**Depende de:** T08.

---

### T10 — Consolidar evidencia

**Archivo:** `dashboard_prototipos/docs/hu001_evidencia_implementacion.md`.

**Cambio:** documentar archivos modificados, comandos, resultados, decisiones, limitaciones y tabla CA/AV.

**Resultado esperado:** HU001 auditable sin depender de la conversación con Codex.

**Depende de:** T09.

---

### T11 — Revisar diff y abrir PR

**Cambio:** validar `git diff --check`, revisar alcance contra `main`, commit y PR focalizado.

**Resultado esperado:** PR contiene únicamente la fundación FastAPI HU001 y su evidencia.

**Depende de:** T10.

---

## 9. Criterios de aceptación

### CA01 — Aplicación importable

**Dado** un checkout limpio con dependencias instaladas,  
**cuando** se importa la aplicación FastAPI,  
**entonces** no ocurren errores ni side effects de datos/modelo.

### CA02 — Health disponible

**Dado** el servicio levantado,  
**cuando** se consulta `GET /api/v2/health`,  
**entonces** responde HTTP 200 con `status=ok`, `service=biomac-api` y `api_version=2.0.0`.

### CA03 — Readiness veraz

**Dado** que HU001 todavía no implementa ChampionAdapter ni storage,  
**cuando** se consulta health,  
**entonces** no se reporta falsamente readiness de esos componentes.

### CA04 — Request ID

**Dada** cualquier petición HTTP,  
**cuando** el backend la procesa,  
**entonces** devuelve un `X-Request-ID` UUID válido y distinto entre requests independientes.

### CA05 — Contratos Pydantic

**Dado** el contrato v2.0.0,  
**cuando** se instancian los schemas base,  
**entonces** respetan tipos, nulabilidad, enums y `snake_case` documentados.

### CA06 — Campos desconocidos

**Dado** un schema estricto,  
**cuando** recibe un campo no definido,  
**entonces** la validación lo rechaza donde aplique.

### CA07 — Estados de run controlados

**Dado** un `RunStatus`,  
**cuando** se intenta usar un estado fuera del catálogo contractual,  
**entonces** la validación falla.

### CA08 — Error uniforme

**Dado** un error HTTP/validación,  
**cuando** llega al cliente,  
**entonces** utiliza `ErrorEnvelope` con `code`, `message` y `request_id` estables.

### CA09 — Error inesperado seguro

**Dada** una excepción inesperada,  
**cuando** se transforma en respuesta HTTP,  
**entonces** no expone stack trace, ruta interna, secreto ni representación completa de la excepción.

### CA10 — CORS configurable

**Dado** un origen permitido configurado,  
**cuando** realiza una petición CORS válida,  
**entonces** recibe headers apropiados; un origen no permitido no obtiene autorización CORS.

### CA11 — Configuración segura

**Dado** el código versionado,  
**cuando** se revisan configuración y Git,  
**entonces** no existen credenciales/secretos reales ni CORS wildcard productivo por defecto.

### CA12 — OpenAPI

**Dado** el servicio,  
**cuando** se consulta `/openapi.json`,  
**entonces** existe un documento válido con versión API y health bajo `/api/v2`.

### CA13 — Tests focalizados

**Dado** el entorno local,  
**cuando** se ejecuta la suite de HU001,  
**entonces** todas las pruebas pasan sin red, datos, DVC, MLflow ni Champion.

### CA14 — Sin adelantar HU002+

**Dado** el diff de HU001,  
**cuando** se inspeccionan endpoints y servicios,  
**entonces** no existe upload funcional, inferencia, persistencia, ChampionAdapter, InputService ni integración React.

### CA15 — Compatibilidad con documentación

**Dado** `arquitectura.md`, `API-sign.md`, `plan.md`, `diccionario-de-datos.md`, `implementacion.md` y `HU-MVP-FastAPI-dashboard.md`,  
**cuando** se compara HU001 con ellos,  
**entonces** no introduce una semántica contradictoria de API, Refresh, Champion o alcance.

---

## 10. Autovalidaciones obligatorias

### AV01 — Import limpio

**Procedimiento:** importar `api.app.main` desde un proceso limpio.

**PASS:** aplicación importable sin acceso a datos/modelos/servicios externos.

---

### AV02 — Health contract

**Procedimiento:** invocar health con TestClient.

**PASS:** HTTP 200 y payload compatible con v2.0.0.

---

### AV03 — Readiness

**Procedimiento:** inspeccionar health en la implementación inicial.

**PASS:** Champion/storage no aparecen como disponibles sin implementación real.

---

### AV04 — Request ID

**Procedimiento:** ejecutar al menos dos requests y validar header UUID.

**PASS:** IDs válidos, independientes y disponibles para error handling.

---

### AV05 — Strict schemas

**Procedimiento:** añadir un campo desconocido a un modelo contractual estricto.

**PASS:** Pydantic rechaza el input.

---

### AV06 — Enums contractuales

**Procedimiento:** probar estados/horizontes válidos e inválidos.

**PASS:** solo se aceptan valores documentados.

---

### AV07 — Error envelope

**Procedimiento:** provocar un error controlado de request.

**PASS:** respuesta usa envelope contractual y contiene request ID.

---

### AV08 — Sanitización

**Procedimiento:** provocar una excepción interna en un contexto de prueba.

**PASS:** body público no contiene traceback, ruta absoluta ni texto sensible de la excepción.

---

### AV09 — CORS

**Procedimiento:** probar preflight/origen permitido y no permitido.

**PASS:** allowlist se respeta y no existe `*` productivo implícito.

---

### AV10 — OpenAPI

**Procedimiento:** consultar `/openapi.json`.

**PASS:** documento válido; health aparece bajo `/api/v2`; no aparecen endpoints futuros falsos.

---

### AV11 — Dependencias

**Procedimiento:** ejecutar instalación/check de dependencias según estrategia del repo y `pip check` cuando aplique.

**PASS:** sin conflictos introducidos por HU001 o cualquier conflicto preexistente queda diferenciado y documentado.

---

### AV12 — Suite focalizada

**Procedimiento:** ejecutar únicamente tests de HU001/API.

**PASS:** 100 % de tests HU001 pasan.

---

### AV13 — Sin servicios externos

**Procedimiento:** revisar tests/imports y, cuando sea viable, ejecutarlos sin credenciales AWS/MLflow.

**PASS:** HU001 funciona sin credenciales ni datos externos.

---

### AV14 — Scope check

**Procedimiento:** revisar `git diff --name-only` y `git diff --check` contra `main`.

**PASS:** cambios limitados a API base, dependencias/configuración mínima y evidencia HU001; no se modifican modelos, datos ni frontend.

---

### AV15 — Gobierno documental

**Procedimiento:** contrastar implementación contra las seis fuentes de verdad listadas en esta HU.

**PASS:** contrato `/api/v2`, readiness, errores, CORS y frontera con Champion son compatibles; cualquier discrepancia se reporta antes de cambiar documentos.

---

## 11. Definition of Done (DoD)

HU001 se considera `[COMPLETADA]` únicamente cuando:

- [ ] existe aplicación FastAPI importable bajo `api/app/`;
- [ ] `GET /api/v2/health` responde 200;
- [ ] API expone versión `2.0.0`;
- [ ] readiness de Champion/storage no se simula;
- [ ] configuración está centralizada;
- [ ] CORS usa allowlist configurable;
- [ ] existe `request_id` por request;
- [ ] schemas Pydantic base están implementados y probados;
- [ ] errores siguen envelope uniforme;
- [ ] excepciones inesperadas están sanitizadas;
- [ ] OpenAPI se genera correctamente;
- [ ] no existen secretos versionados;
- [ ] tests HU001 pasan localmente;
- [ ] pruebas no necesitan data/DVC/MLflow/Champion/red externa;
- [ ] no se implementaron responsabilidades de HU002+;
- [ ] `git diff --check` pasa;
- [ ] existe `hu001_evidencia_implementacion.md` con CA01–CA15 y AV01–AV15;
- [ ] PR de HU001 está focalizado, revisado y mergeado a `main`.

---

## 12. Evidencias esperadas

La implementación deberá conservar como mínimo:

1. árbol final de `api/`;
2. comando usado para levantar la API;
3. respuesta real de `/api/v2/health`;
4. ejemplo de `X-Request-ID`;
5. resultado de `/openapi.json` o validación equivalente;
6. resultado de tests focalizados;
7. resultado de `pip check` cuando aplique;
8. prueba de CORS permitido/no permitido;
9. prueba de error sanitizado;
10. tabla CA01–CA15;
11. tabla AV01–AV15;
12. diff final contra `main`;
13. listado de dependencias añadidas y justificación;
14. limitaciones/blockers identificados.

---

## 13. Riesgos y mitigaciones

### R01 — Sobrediseñar la API antes de HU002

**Mitigación:** implementar solo fundaciones y contratos; no crear servicios/orquestadores sin comportamiento requerido por HU001.

### R02 — Reportar Champion listo sin existir adapter

**Mitigación:** readiness falsa hasta que una HU posterior conecte un check real.

### R03 — Acoplar schemas a un modelo concreto

**Mitigación:** schemas representan el contrato BIOMAC y `output_type`; no importar XGBoost/MLflow en la capa contractual.

### R04 — Cambiar el runtime global para instalar FastAPI

**Mitigación:** validar compatibilidad primero; modificar runtime solo ante blocker demostrado y con decisión explícita separada.

### R05 — Exponer información interna en errores

**Mitigación:** handler global sanitizado + AV08 bloqueante.

### R06 — CORS demasiado permisivo

**Mitigación:** allowlist por configuración; no usar wildcard productivo.

### R07 — Duplicar constantes/contratos

**Mitigación:** versión API, enums y modelos comunes tienen una única fuente en código.

### R08 — Tests que dependen del stack ML

**Mitigación:** HU001 no importa módulos de modelado; tests unitarios/contractuales aislados.

### R09 — Contrato Pydantic demasiado rígido frente a futuras HUs

**Mitigación:** seguir nulabilidad y campos ya versionados en `API-sign.md`; cualquier cambio semántico exige gobierno documental y nueva versión cuando corresponda.

---

## 14. Resultado esperado para HU002

HU002 deberá recibir una base donde pueda implementar `POST /api/v2/monthly-runs` y validación de upload sin volver a decidir:

- cómo se instancia FastAPI;
- cuál es el prefijo `/api/v2`;
- cómo se configura CORS;
- cómo se genera `request_id`;
- cómo se cargan settings;
- cuál es el formato de error;
- cómo se representan run/status/source metadata;
- cómo se prueban endpoints;
- cómo se publica OpenAPI.

HU002 podrá concentrarse exclusivamente en recepción/validación del archivo mensual, `reference_month`, hash y errores de upload.

---

## 15. Evidencia de cierre

Se completa únicamente después de la implementación y auditoría final.

Debe registrar:
- PR y merge commit;
- resultado de CA01–CA15;
- resultado de AV01–AV15;
- comandos finales de validación;
- dependencias añadidas;
- limitaciones aceptadas;
- confirmación explícita de que HU002+ permanece fuera del diff.
