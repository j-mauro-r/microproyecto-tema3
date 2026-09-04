# HU008 — Integración del dashboard BIOMAC con FastAPI

**Estado:** `[DEFINIDA — PENDIENTE IMPLEMENTACIÓN]`  
**Identificador:** `HU-INT-008`  
**Prioridad:** ALTA  
**Dependencias:** HU005, HU006, HU007  
**Ámbito vigente:** Entregable 2, ejecución local; sin AWS/deployment en esta HU  
**Frontend objetivo:** `dashboard_prototipos/dengue-watch-pro`  
**Backend objetivo:** `/api/v2`  
**Documentos fuente:** `arquitectura.md`, `API-sign.md`, `implementacion.md`, `plan.md`, HU001–HU007

---

## 1. Contexto

HU001–HU007 construyeron la frontera FastAPI, la carga mensual, el contrato del Champion, la orquestación, la persistencia local SQLite y las consultas read-only. El dashboard React ya posee una abstracción `DengueRepository`, pero su punto de composición continúa usando `MockDengueRepository` como fuente por defecto.

HU008 conecta ambas partes sin trasladar lógica epidemiológica o de Machine Learning al frontend.

La arquitectura objetivo para esta HU es:

```text
Dashboard React
   |
   | HttpDengueRepository
   | API_BASE_URL configurable
   v
FastAPI /api/v2
   |
   +--> GET /predictions/latest     apertura / Refresh
   +--> GET /predictions/history    historial cuando la UI lo solicite
   +--> GET /runs/{run_id}          trazabilidad
   +--> POST /monthly-runs          actualización mensual
   |
   v
Persistencia / orquestación ya implementadas
```

Principio central:

> Abrir el dashboard o presionar Refresh solo consulta resultados persistidos. La inferencia se dispara únicamente mediante la carga mensual explícita.

---

## 2. Historia de usuario

**Como** analista/usuario de BIOMAC  
**quiero** que el dashboard consuma la API real y permita cargar un nuevo archivo mensual  
**para** consultar predicciones persistidas y actualizar el corte sin depender de mocks o scripts manuales.

---

## 3. Objetivo verificable

Al terminar HU008 debe ser posible ejecutar el dashboard local apuntando a una instancia FastAPI configurable y comprobar que:

1. al abrir la aplicación se ejecuta `GET /api/v2/predictions/latest`;
2. el botón `Refresh` vuelve a ejecutar únicamente `GET latest`;
3. un analista puede seleccionar un CSV y `reference_month` y enviarlos mediante `POST /api/v2/monthly-runs`;
4. si el POST termina exitosamente, el frontend consulta nuevamente `GET latest` y presenta el resultado persistido;
5. si cualquier request falla, no se sustituyen los datos válidos anteriores por mocks;
6. la UI representa explícitamente `loading`, `success`, `empty`, `error` y `retry`;
7. ningún componente React calcula clase, probabilidad, threshold, canal, SHAP o valores faltantes.

---

## 4. Decisiones de diseño

### D01 — HTTP como fuente por defecto

La implementación por defecto de `DengueRepository` pasa a ser HTTP.

```text
DengueRepository
      ^
      |
HttpDengueRepository   <-- default runtime
```

`MockDengueRepository` puede conservarse para pruebas Storybook/desarrollo explícito si aporta valor, pero:

- no puede ser fallback ante error de API;
- no puede activarse silenciosamente;
- no puede ser la fuente por defecto del build normal;
- cualquier modo mock debe ser explícito mediante configuración de desarrollo.

### D02 — `API_BASE_URL` configurable

El frontend usa una única variable de ambiente, preferiblemente:

```text
VITE_BIOMAC_API_BASE_URL=http://127.0.0.1:8001/api/v2
```

Reglas:

- normalizar slash final;
- no hardcodear IP/host en componentes;
- no duplicar base URL;
- fallar de manera comprensible si falta/configura mal;
- no incluir secretos en variables `VITE_*`.

### D03 — DTO HTTP separado del modelo de UI

Los JSON de FastAPI no deben consumirse directamente dentro de componentes.

Implementar una frontera equivalente a:

```text
HTTP JSON
  -> API DTO
  -> parser/validator ligero
  -> mapper
  -> View model / dominio frontend
  -> React
```

La implementación debe respetar los contratos reales vigentes de HU006/HU007 y no asumir todavía los enriquecimientos finales de HU009.

### D04 — HU008 no fabrica campos que HU007 no expone

HU007 persiste/expone actualmente metadata mínima y predicciones. Por tanto HU008 no puede inventar para satisfacer el diseño previo:

- P25/P50/P75 ausentes;
- estado actual/canal endémico ausente;
- data quality ausente;
- SHAP/explanation ausente;
- incertidumbre ausente;
- historial epidemiológico ausente;
- probabilidad cuando `probability=null`;
- threshold cuando `decision_threshold=null`;
- label cuando `label=null`.

Cuando un panel existente depende de información no disponible, debe usar un estado explícito del tipo “Información no disponible en esta versión” o quedar oculto de forma controlada según el patrón visual existente. Nunca debe reutilizar mocks para llenar el hueco.

HU009 cerrará los enriquecimientos respaldados por fuentes reales.

### D05 — Refresh es estrictamente read-only

```text
Refresh
  -> invalidate/refetch latest
  -> GET /predictions/latest
```

No puede llamar:

- POST `/monthly-runs`;
- endpoint de run para provocar procesamiento;
- lógica de inferencia;
- scripts/modelos.

### D06 — La actualización mensual es una acción separada y explícita

Debe existir una acción `Actualizar datos` que solicite:

- archivo `.csv`;
- `reference_month` en formato `YYYY-MM`;
- confirmación del usuario antes del POST.

No se requiere autenticación en HU008.

### D07 — POST exitoso -> GET latest

El POST puede devolver snapshot, pero la fuente canónica para refrescar la vista después de actualizar será `GET latest`.

```text
POST COMPLETED
  -> conservar run_id para mensaje/trazabilidad
  -> invalidar/refetch latest
  -> renderizar latest persistido
```

Esto prueba la misma ruta que usará una futura apertura/Refresh y evita dos fuentes de verdad en frontend.

### D08 — Error de actualización no borra el snapshot anterior

Si ya existe información visible y el POST falla:

```text
último snapshot válido permanece visible
+
mensaje de error de actualización
+
acción Reintentar
```

No resetear la pantalla completa a empty.

### D09 — React Query conserva el control de server state

Mantener `@tanstack/react-query` como mecanismo de consulta/mutación.

Usar query keys estables. Sugerencia:

```text
["biomac", "predictions", "latest", filtros]
["biomac", "predictions", "history", filtros]
["biomac", "runs", runId]
```

La acción de upload debe ser una mutation.

### D10 — Sin despliegue cloud en esta HU

Aunque `arquitectura.md` describe el deployment futuro Lovable -> EC2, HU008 se implementa y valida localmente.

Fuera de alcance actual:

- AWS;
- EC2;
- DNS/HTTPS;
- Docker;
- secrets manager;
- autenticación;
- infraestructura cloud.

La única preparación para despliegue es mantener `API_BASE_URL` configurable y CORS compatible con configuración por ambiente.

---

## 5. Alcance funcional

### 5.1 Apertura inicial

Al montar la pantalla principal:

```text
GET /api/v2/predictions/latest
```

Default contractual:

- Bucaramanga `68001`;
- Cali `76001`;
- T+1 y T+2.

No enviar filtros innecesarios si los defaults del backend ya coinciden.

Estados:

#### Loading inicial

- mostrar loader/skeleton existente o equivalente;
- no renderizar mocks mientras espera.

#### Success

- mapear únicamente datos reales;
- selector Bucaramanga/Cali opera sobre el snapshot recibido.

#### Empty

HU007 devuelve `404 PREDICTION_NOT_FOUND` cuando nunca existe un snapshot compatible.

La UI debe interpretarlo como un estado vacío de producto, no como crash:

```text
Aún no hay predicciones disponibles.
Carga el primer periodo mensual para generar una predicción.
```

Debe ofrecer `Actualizar datos`.

#### Error técnico

Errores diferentes a `PREDICTION_NOT_FOUND`, incluyendo red o `PERSISTENCE_FAILED`, deben mostrar estado de error y `Reintentar`.

No mostrar stack trace ni respuesta cruda.

---

### 5.2 Refresh

Debe existir una acción visible `Refresh` / `Actualizar vista` consistente con el diseño actual.

Comportamiento:

1. refetch `latest`;
2. mostrar estado de refreshing sin destruir la vista anterior;
3. si éxito, sustituir por snapshot nuevo;
4. si falla, conservar snapshot anterior y mostrar aviso no destructivo.

No dispara POST.

---

### 5.3 Actualizar datos

Flujo mínimo:

```text
usuario pulsa Actualizar datos
 -> selecciona CSV
 -> selecciona/ingresa YYYY-MM
 -> frontend valida solo reglas UX básicas
 -> confirma
 -> POST multipart/form-data
 -> espera respuesta
 -> si COMPLETED: muestra éxito + run_id + refetch latest
 -> si falla: conserva latest anterior + mensaje controlado
```

#### Validaciones UX permitidas

Frontend puede validar únicamente para mejorar interacción:

- archivo seleccionado;
- extensión `.csv`;
- `reference_month` con forma `YYYY-MM`;
- no enviar si faltan campos.

La validación autoritativa sigue siendo FastAPI/HU002.

Frontend NO debe validar o recalcular:

- las 39 features;
- valores epidemiológicos;
- municipio exacto;
- hash;
- leakage;
- reglas Champion.

### 5.4 Multipart

Request:

```text
POST {API_BASE_URL}/monthly-runs
Content-Type: generado automáticamente por browser

FormData:
  file=<File>
  reference_month=YYYY-MM
```

No establecer manualmente el boundary de `Content-Type`.

### 5.5 Respuesta de actualización

En éxito, presentar como mínimo:

- mensaje de actualización completada;
- `run_id`;
- `reference_month`;
- estado `COMPLETED`.

Luego ejecutar `latest` y usar esa consulta como contenido de la pantalla.

En error, mapear el `ErrorEnvelope` estable del API cuando exista:

- `INVALID_REQUEST`;
- `INVALID_UPLOAD`;
- `CHAMPION_NOT_READY`;
- `CHAMPION_INPUT_INVALID`;
- `PREPARATION_FAILED`;
- `INFERENCE_FAILED`;
- `MAPPING_FAILED`;
- `PERSISTENCE_FAILED`;
- `INTERNAL_ERROR`.

No es necesario diseñar mensajes diferentes para todos si una taxonomía más pequeña y clara preserva el código técnico para soporte.

---

## 6. Contratos frontend mínimos

### 6.1 Cliente HTTP

Crear una utilidad central equivalente a:

```ts
interface BiomacApiClient {
  getLatest(...): Promise<PredictionSnapshotReadResponse>;
  getHistory(...): Promise<PredictionHistoryResponse>;
  getRun(runId: string): Promise<RunReadResponse>;
  createMonthlyRun(file: File, referenceMonth: string): Promise<MonthlyRunResponse>;
}
```

No es obligatorio usar exactamente esta interfaz si la arquitectura actual favorece integrar estas operaciones en `HttpDengueRepository`.

### 6.2 `DengueRepository`

Evolucionar el contrato actual de forma cohesionada. Debe soportar al menos:

- recuperar latest;
- recuperar información por ciudad desde latest sin una segunda fuente de verdad;
- actualizar datos mensuales;
- Refresh mediante latest;
- history/run si ya son requeridos por la UI de HU008 o dejar preparados métodos claros para el siguiente uso.

Evitar mantener `getDashboard()` con semántica ficticia si fuerza a inventar datos que el backend no entrega. Es válido evolucionarlo a un contrato más explícito si se actualizan sus consumidores y tests.

### 6.3 Parsing defensivo

No es requisito incorporar una nueva dependencia de schema validation. Puede usarse TypeScript + validación manual focalizada.

Debe detectar al menos:

- response no JSON cuando se esperaba JSON;
- envelope de error;
- ausencia de campos críticos como `prediction_snapshot`, `run_id`, `predictions`;
- valores inesperados de horizonte/divipola cuando comprometan la UI.

Un payload inválido debe producir error controlado, nunca datos inventados.

---

## 7. Mapeo a la UI actual

### Datos que HU008 sí puede mostrar con HU007

- `run_id`;
- `generated_at`;
- `reference_month`;
- `source_file_sha256` si se decide exponerlo en trazabilidad;
- Champion `name`, `version`, `output_type`, horizontes y feature contract;
- por ciudad/horizonte:
  - `target_month`;
  - `probability` si no es null;
  - `expected_cases` si no es null;
  - `risk_score` si no es null;
  - `label` si no es null;
  - `decision_threshold` si no es null.

### Datos que deben quedar como “no disponibles” hasta HU009

- canal endémico actual completo;
- calidad/frescura calculada;
- SHAP local/explicación;
- uncertainty;
- historia epidemiológica enriquecida;
- recomendaciones derivadas de información no persistida.

### Regla para `output_type`

Si `output_type="probability"` y `probability` existe, puede mostrarse como porcentaje usando solo formato visual:

```text
0.78 -> 78%
```

Formatear no es recalcular.

Si `probability=null`, no convertir `risk_score` o `expected_cases` en porcentaje.

---

## 8. Estados de interfaz obligatorios

HU008 debe cubrir de forma visible:

1. `loading_initial`;
2. `success`;
3. `empty`;
4. `error_initial`;
5. `refreshing`;
6. `refresh_error_with_stale_data`;
7. `upload_idle`;
8. `upload_submitting`;
9. `upload_success`;
10. `upload_error_with_previous_data`.

La nomenclatura interna puede variar.

---

## 9. Manejo de errores

### Error HTTP/API

Crear un error frontend estable equivalente a:

```ts
class BiomacApiError extends Error {
  status: number;
  code?: string;
  requestId?: string;
  details?: unknown;
}
```

No propagar detalles peligrosos a la UI.

### `PREDICTION_NOT_FOUND`

En `latest`:

```text
404 + PREDICTION_NOT_FOUND -> empty
```

No tratar todos los 404 como empty.

### Offline / connection refused

Mostrar:

```text
No fue posible conectar con BIOMAC API.
```

con reintento.

---

## 10. Seguridad y configuración

- no agregar secretos al frontend;
- `VITE_BIOMAC_API_BASE_URL` es configuración pública, no secreto;
- no usar `dangerouslySetInnerHTML` para mensajes del backend;
- no imprimir contenido completo del CSV en consola;
- no almacenar el CSV en localStorage/sessionStorage;
- no persistir responses sensibles fuera del cache normal en memoria de React Query;
- no introducir credenciales AWS ni tokens.

---

## 11. Accesibilidad y UX mínima

Sin rediseñar el dashboard completo:

- input file con label accesible;
- input/selector de mes con label;
- botones disabled durante submit cuando corresponda;
- estado de carga anunciado visualmente;
- error legible y accionable;
- éxito legible;
- no depender solo del color para estados;
- foco razonable al abrir/cerrar modal/dialog de actualización si existe.

---

## 12. Fuera de alcance

HU008 NO implementa:

- cambios al modelo Champion;
- ejecución directa de XGBoost/LightGBM;
- features en React;
- cálculo de canal endémico;
- SHAP;
- recomendaciones epidemiológicas nuevas;
- data quality calculada;
- auth/RBAC;
- AWS/EC2/S3/RDS;
- Docker/deployment;
- WebSocket/polling;
- background jobs;
- reentrenamiento;
- dashboards MLOps;
- exportación PDF/CSV;
- rediseño visual completo.

---

## 13. Tareas de implementación

### T01 — Baseline

- ejecutar tests/lint/build actuales del dashboard;
- registrar conteos y warnings antes de modificar.

### T02 — Contratos API TypeScript

- definir DTOs de HU006/HU007;
- definir `ErrorEnvelope` frontend;
- preservar campos nullable.

### T03 — Configuración

- implementar lector único de `VITE_BIOMAC_API_BASE_URL`;
- documentar `.env.example` sin secretos;
- validar URL de forma controlada.

### T04 — Cliente HTTP

- centralizar `fetch`/HTTP;
- status handling;
- JSON parsing;
- AbortSignal cuando sea razonable;
- no introducir axios salvo justificación real.

### T05 — `HttpDengueRepository`

- implementar latest;
- history/run si corresponde al contrato evolucionado;
- upload mensual;
- mapear DTO -> frontend.

### T06 — Composition root

- hacer HTTP la fuente por defecto;
- mock solo en modo explícito de desarrollo/test;
- cero fallback silencioso.

### T07 — Hook server-state

- evolucionar `useDengueDashboard` o reemplazarlo por hooks cohesionados;
- query latest;
- mutation upload;
- refresh;
- invalidation/refetch post upload.

### T08 — UI estados

- loading;
- empty;
- initial error/retry;
- refreshing;
- stale data + refresh error;
- upload success/error.

### T09 — UI actualización mensual

- archivo;
- mes;
- confirmación;
- submit;
- feedback;
- run_id.

### T10 — Eliminar dependencia funcional de mocks

- asegurar que componentes productivos no importan `src/mocks` ni `MockDengueRepository`;
- no borrar fixtures que sigan siendo útiles para tests.

### T11 — Tests

- cliente HTTP;
- repository;
- hooks;
- integración UI principal;
- no-fallback;
- Refresh read-only;
- upload -> refetch latest;
- nullability.

### T12 — Documentación y evidencia

- actualizar documentos afectados;
- crear evidencia HU008;
- registrar comandos y resultados exactos.

---

## 14. Criterios de aceptación

### Integración y configuración

**CA01.** Existe una única configuración `API_BASE_URL` por ambiente y no hay hosts hardcodeados en componentes.  
**CA02.** La fuente normal del dashboard es `HttpDengueRepository`.  
**CA03.** `MockDengueRepository` no funciona como fallback ante errores de red/API.  
**CA04.** Al abrir la pantalla principal se consulta `GET /predictions/latest`.  
**CA05.** El frontend puede ejecutarse apuntando a una API local mediante `.env`/variable de ambiente.

### Latest / Refresh

**CA06.** `latest` exitoso renderiza solo información proveniente del response.  
**CA07.** `404 PREDICTION_NOT_FOUND` se representa como empty controlado.  
**CA08.** Error técnico inicial se representa con retry.  
**CA09.** Refresh llama exclusivamente `GET latest`.  
**CA10.** Durante Refresh se conserva el snapshot anterior.  
**CA11.** Error de Refresh no reemplaza ni borra el snapshot anterior.

### Upload

**CA12.** Existe acción explícita `Actualizar datos`.  
**CA13.** La acción solicita CSV y `reference_month`.  
**CA14.** Se solicita confirmación antes de enviar.  
**CA15.** El browser envía `multipart/form-data` con `file` y `reference_month`.  
**CA16.** El frontend no fija manualmente el boundary multipart.  
**CA17.** Un POST exitoso muestra `run_id/reference_month/COMPLETED`.  
**CA18.** Después de éxito se vuelve a consultar `GET latest`.  
**CA19.** Error de POST conserva la predicción previa.  
**CA20.** El error de POST se presenta saneado y permite retry seguro.

### Integridad analítica

**CA21.** React no calcula probability, label o threshold.  
**CA22.** `probability=null` no se transforma en porcentaje usando otro campo.  
**CA23.** `expected_cases` y `risk_score` preservan su significado nativo.  
**CA24.** Campos no disponibles de HU009 no se completan con mocks/placeholders numéricos.  
**CA25.** No se calculan P25/P50/P75, canal, SHAP, uncertainty o data quality en frontend.

### Calidad

**CA26.** Loading, success, empty, error y retry están cubiertos por tests.  
**CA27.** Build, lint/typecheck y tests del dashboard pasan.  
**CA28.** La suite API existente continúa verde o no es modificada innecesariamente.  
**CA29.** No se agregan secretos/cloud/runtime ML al frontend.  
**CA30.** Existe evidencia versionada suficiente para auditoría.

---

## 15. Autovalidaciones

**AV01.** Buscar `MockDengueRepository` y comprobar que no es la fuente normal de runtime.  
**AV02.** Buscar `localhost`, `127.0.0.1`, IPs y `/api/v2` en componentes para detectar hardcode duplicado.  
**AV03.** Test: apertura -> exactamente una consulta latest esperada.  
**AV04.** Test: latest 404 PREDICTION_NOT_FOUND -> empty.  
**AV05.** Test: latest 500 -> error + retry.  
**AV06.** Test: retry exitoso recupera pantalla.  
**AV07.** Test: Refresh hace GET y no POST.  
**AV08.** Test: Refresh mantiene datos mientras carga.  
**AV09.** Test: Refresh fallido conserva datos previos.  
**AV10.** Test: upload construye FormData correcto.  
**AV11.** Test: upload requiere file y mes.  
**AV12.** Test: confirmación cancela POST cuando usuario cancela.  
**AV13.** Test: POST COMPLETED -> refetch latest.  
**AV14.** Test: POST error -> latest previo permanece.  
**AV15.** Test: error envelope conserva `code`/`request_id` de forma saneada.  
**AV16.** Test: probability null permanece null/no porcentaje.  
**AV17.** Test: expected_cases/risk_score no se reinterpretan.  
**AV18.** Test: campos de HU009 ausentes no se rellenan desde mocks.  
**AV19.** Revisión de imports: frontend no carga librerías/modelos ML.  
**AV20.** Revisión de configuración: `.env.example` sin secretos.  
**AV21.** Ejecutar lint/typecheck/build.  
**AV22.** Ejecutar suite dashboard completa.  
**AV23.** Ejecutar suite API si el PR toca contratos compartidos/backend.  
**AV24.** Verificar `git status` y ausencia de runtime/env local accidentalmente versionado.

---

## 16. Estrategia mínima de pruebas

Usar la infraestructura de tests ya disponible en el dashboard. Para HTTP, preferir mocks del transporte (`fetch`) o una herramienta existente en el proyecto; no introducir un servidor real únicamente para unit tests.

Casos mínimos:

1. configuración base URL válida;
2. configuración ausente/inválida;
3. latest success con 4 predicciones;
4. latest solo con valores nullable;
5. latest empty;
6. latest 400/500;
7. network error;
8. retry;
9. Refresh success;
10. Refresh error con datos previos;
11. upload valid UX;
12. upload sin file;
13. upload sin mes;
14. upload cancelado;
15. FormData correcto;
16. POST success;
17. POST success refetch latest;
18. POST invalid upload;
19. POST internal/persistence error;
20. POST error conserva snapshot;
21. selector Bucaramanga/Cali sobre respuesta real;
22. T+1/T+2 preservados;
23. threshold independiente por horizonte preservado;
24. probability null;
25. expected_cases/risk_score nullables;
26. no fallback mock;
27. no cálculo analítico frontend;
28. componentes no dependen directamente del transporte HTTP;
29. build producción;
30. regresión de UI principal.

---

## 17. Evidencia requerida

Crear:

```text
dashboard_prototipos/docs/hu008_evidencia_implementacion.md
```

Debe registrar:

- rama y SHA;
- baseline frontend;
- arquitectura implementada;
- `API_BASE_URL`;
- contratos TypeScript;
- `HttpDengueRepository`;
- query/mutation flow;
- comportamiento opening/Refresh;
- comportamiento upload;
- tratamiento de empty/error;
- prueba de no-fallback;
- prueba de nullability;
- CA01–CA30;
- AV01–AV24;
- comandos ejecutados;
- conteos exactos de tests;
- lint/typecheck/build;
- warnings conocidos;
- pendientes reales para HU009/HU010.

No registrar tokens, archivos `.env` reales ni datos sensibles.

---

## 18. Documentos a mantener alineados

Actualizar solo si la implementación introduce información factual nueva:

- `dashboard_prototipos/docs/API-sign.md`;
- `dashboard_prototipos/docs/arquitectura.md`;
- `dashboard_prototipos/docs/implementacion.md`;
- README del dashboard para configuración local.

No cambiar contratos backend sin necesidad justificada por HU008.

---

## 19. Definition of Done

HU008 puede declararse `[COMPLETADA — DESARROLLO]` únicamente cuando:

- HTTP es la fuente por defecto;
- `API_BASE_URL` es configurable;
- apertura consume latest;
- Refresh es read-only;
- upload usa POST explícito;
- éxito de upload refetchea latest;
- fallo de upload/Refresh conserva datos anteriores;
- empty/error/retry son visibles;
- no existe fallback silencioso a mocks;
- no se inventan campos no disponibles;
- nullability se preserva;
- ningún cálculo ML/epidemiológico se mueve a React;
- tests frontend quedan verdes;
- lint/typecheck/build quedan verdes;
- API no sufre regresiones si fue tocada;
- CA01–CA30 están PASS;
- AV01–AV24 están PASS;
- evidencia queda versionada.

---

## 20. Gate hacia HU009 y HU010

### HU009

Queda habilitada para enriquecer el snapshot con información real de:

- data quality/frescura;
- current status/canal endémico;
- metadata adicional;
- explicación local cuando exista;
- historia epidemiológica respaldada por fuentes reales.

HU009 no debe ser necesaria para demostrar que HU008 consume FastAPI correctamente.

### HU010

Queda habilitada posteriormente para pruebas E2E del flujo completo y cierre de integración/deployment.

---

## 21. Regla final

> HU008 integra transporte, estado de aplicación y experiencia de actualización. No corrige, completa ni interpreta la salida del modelo. Si FastAPI no entrega un dato, el dashboard lo muestra como no disponible; nunca lo inventa.
