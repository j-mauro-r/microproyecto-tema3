# BIOMAC — Plan de implementación del flujo operativo de predicción

**Estado:** backlog objetivo  
**Versión:** `1.0.0`  
**Fuente arquitectónica:** `arquitectura.md`  
**Contrato API:** `API-sign.md`  

## 1. Alcance

Este plan implementa el flujo:

```text
analista carga archivo mensual
→ backend valida/prepara datos
→ se ejecuta el Champion existente
→ se normaliza y persiste la salida
→ dashboard muestra el nuevo resultado
→ Refresh consulta el último resultado persistido
```

### Fuera de alcance

- entrenamiento/reentrenamiento;
- tuning;
- experimentación;
- comparación y selección de candidatos;
- promoción del Champion;
- cambios al algoritmo;
- definición de thresholds no entregados por el modelo/contrato.

El equipo de dashboard/integración recibe un Champion aprobado o salidas materializadas compatibles.

## 2. Orden de implementación

| Orden | HU | Nombre | Objetivo | Dependencias | Prioridad |
|---:|---|---|---|---|---|
| 1 | HU-INT-001 | Base FastAPI y contratos | Crear esqueleto API v2, configuración, health, schemas y errores comunes. | arquitectura/API | ALTA |
| 2 | HU-INT-002 | Carga mensual y validación | Recibir archivo mensual, validar formato, periodo, ciudades, tamaño y hash. | HU-INT-001 | ALTA |
| 3 | HU-INT-003 | Preparación para inferencia | Transformar la carga y contexto histórico en el contrato de entrada del Champion sin entrenamiento. | HU-INT-002 + contrato Champion | ALTA |
| 4 | HU-INT-004 | Adapter del Champion | Cargar/invocar el Champion aprobado y exponer metadata/output desacoplados del framework. | HU-INT-003 + artefacto Champion | ALTA |
| 5 | HU-INT-005 | Orquestación del run | Coordinar validación → preparación → inferencia → mapeo → persistencia con estados e idempotencia. | HU-INT-002/003/004 | ALTA |
| 6 | HU-INT-006 | Persistencia y trazabilidad | Guardar runs y snapshots exitosos/fallidos, manteniendo última predicción exitosa. | HU-INT-005 | ALTA |
| 7 | HU-INT-007 | API de consulta | Exponer latest, history y detalle de run sin ejecutar el modelo. | HU-INT-006 | ALTA |
| 8 | HU-INT-008 | Integración dashboard | Sustituir mocks, habilitar carga mensual, estados y Refresh read-only. | HU-INT-005/007 | ALTA |
| 9 | HU-INT-009 | Explicabilidad y metadata | Exponer threshold/regla, Champion, calidad, SHAP local/explicación solo cuando exista. | HU-INT-004/006 | MEDIA |
| 10 | HU-INT-010 | Pruebas E2E y cierre | Validar flujo completo y regresión de UI/contratos. | HU-INT-001..009 | ALTA |

---

# HU-INT-001 — Base FastAPI y contratos

**Como** equipo de integración  
**quiero** una API versionada y testeable  
**para** separar el dashboard de la lógica de inferencia.

## Alcance

- crear `api/app`;
- configuración por variables de entorno;
- `GET /api/v2/health`;
- schemas Pydantic de run, prediction y error;
- middleware de `request_id`;
- CORS configurable;
- manejo uniforme de excepciones;
- OpenAPI generado automáticamente.

## Criterios de aceptación

- CA01: health responde 200.
- CA02: campos desconocidos se rechazan donde aplique.
- CA03: errores no exponen stack trace ni rutas internas.
- CA04: configuración sensible no está versionada.
- CA05: pruebas básicas pasan en local.

---

# HU-INT-002 — Carga mensual y validación

**Como** analista actualizador  
**quiero** cargar el archivo del nuevo mes  
**para** iniciar una nueva predicción únicamente con datos válidos.

## Endpoint

`POST /api/v2/monthly-runs`

`multipart/form-data`:
- `file`;
- `reference_month`.

## Validaciones mínimas

- extensión/formato permitido;
- tamaño máximo configurable;
- archivo no vacío;
- columnas obligatorias según contrato de entrada;
- tipos básicos;
- `reference_month` válido;
- Bucaramanga/Cali identificables;
- no aceptar información posterior al corte;
- SHA-256 del archivo;
- conflicto controlado para cargas incompatibles de un periodo ya procesado.

## Criterios de aceptación

- CA01: archivo válido continúa al siguiente servicio.
- CA02: archivo inválido produce error estable y comprensible.
- CA03: no se ejecuta el Champion si falla validación.
- CA04: se registra hash, nombre lógico, tamaño y periodo.
- CA05: no se persiste el archivo dentro del repositorio Git.

---

# HU-INT-003 — Preparación de entradas del Champion

**Como** servicio de inferencia  
**quiero** transformar la carga mensual en la estructura exacta requerida por el Champion  
**para** ejecutar inferencia reproducible sin reentrenar.

## Alcance

- definir `ChampionInputContract`;
- reutilizar transformaciones existentes cuando sean compatibles;
- construir únicamente features necesarias para inferencia;
- respetar corte temporal `t`;
- verificar nombres, orden, tipos y nulabilidad de features;
- registrar versión/hash del contrato de features;
- producir diagnóstico de calidad.

## Restricción

Esta HU **no** modifica el pipeline de entrenamiento. Si una transformación necesaria no está disponible como código reutilizable, debe reportarse como dependencia con el equipo de modelado antes de duplicar lógica.

## Criterios de aceptación

- CA01: la matriz de entrada coincide con el contrato del Champion.
- CA02: ninguna feature usa datos posteriores al corte.
- CA03: faltantes esenciales bloquean inferencia.
- CA04: transformaciones deterministas producen el mismo resultado para la misma entrada.
- CA05: existe prueba con Bucaramanga y Cali.

---

# HU-INT-004 — Adapter del Champion

**Como** backend BIOMAC  
**quiero** consumir un Champion mediante una interfaz estable  
**para** evitar que API/dashboard dependan de XGBoost, MLflow u otro framework.

## Contrato

```python
class ChampionAdapter:
    def metadata(self) -> ChampionMetadata: ...
    def predict(self, inference_input) -> ChampionOutput: ...
```

## Metadata mínima

- nombre;
- versión;
- horizonte soportado;
- identificador MLflow/run cuando exista;
- tipo de salida;
- threshold/regla de decisión;
- contrato de features;
- fecha/hash del artefacto cuando aplique.

## Criterios de aceptación

- CA01: el Champion se carga una vez por proceso cuando sea seguro hacerlo.
- CA02: T+1/T+2 se identifican explícitamente.
- CA03: `probability` solo existe si el Champion realmente la produce.
- CA04: no se inventa un threshold por defecto.
- CA05: error de carga produce `CHAMPION_NOT_READY`.
- CA06: si solo se reciben salidas materializadas, puede implementarse un adapter alterno sin cambiar endpoints/UI.

---

# HU-INT-005 — Orquestación del run mensual

**Como** analista  
**quiero** que una única carga coordine el proceso completo  
**para** obtener la nueva predicción sin ejecutar pasos manuales internos.

## Flujo

```text
RECEIVED
→ VALIDATING
→ PREPARING
→ INFERENCING
→ PERSISTING
→ COMPLETED
```

Ante error:

```text
cualquier estado → FAILED
```

## Responsabilidades

- generar `run_id`;
- registrar timestamps;
- ejecutar servicios en orden;
- evitar pasos posteriores si falla uno;
- mapear salida del Champion al contrato BIOMAC;
- persistir solo un snapshot consistente;
- devolver la ejecución terminada en el MVP síncrono.

## Idempotencia

Clave lógica:

`reference_month + source_file_sha256 + champion_version`

## Criterios de aceptación

- CA01: una ejecución exitosa termina en `COMPLETED`.
- CA02: fallo termina en `FAILED` con etapa/código.
- CA03: reintento idéntico no genera predicciones contradictorias.
- CA04: una ejecución fallida no reemplaza la última exitosa.
- CA05: cada resultado permite reconstruir qué archivo y Champion se usaron.

---

# HU-INT-006 — Persistencia y trazabilidad

**Como** usuario y auditor  
**quiero** conservar cada ejecución  
**para** consultar la última predicción y su historial sin volver a ejecutar el modelo.

## Modelo mínimo

### Run
- `run_id`;
- `request_id`;
- `status`;
- `reference_month`;
- `source_file_sha256`;
- `created_at`, `completed_at`;
- `champion_version`;
- `error_code/error_stage` si aplica.

### Snapshot
- municipio;
- horizonte;
- target_month;
- clase;
- output nativo;
- threshold/regla;
- estado actual/canal;
- explicación si existe;
- metadata de calidad/modelo.

## Criterios de aceptación

- CA01: snapshot se persiste antes de responder éxito.
- CA02: `latest` solo toma runs `COMPLETED`.
- CA03: historial conserva versiones anteriores.
- CA04: almacenamiento queda detrás de una interfaz `PredictionRepository`.
- CA05: resultados runtime no se versionan accidentalmente en Git.

---

# HU-INT-007 — API de consulta read-only

**Como** usuario consultor  
**quiero** consultar resultados ya calculados  
**para** abrir o refrescar el dashboard sin ejecutar nuevamente el Champion.

## Endpoints

- `GET /api/v2/runs/{run_id}`
- `GET /api/v2/predictions/latest`
- `GET /api/v2/predictions/history`

Filtros permitidos según endpoint:
- municipio;
- horizonte;
- periodo;
- límite/paginación para historial.

## Criterios de aceptación

- CA01: `latest` devuelve el último snapshot exitoso.
- CA02: `Refresh` no llama ninguna operación de inferencia.
- CA03: historial ordena por corte/generación.
- CA04: si nunca existe una inferencia, se devuelve estado empty controlado.
- CA05: Bucaramanga y Cali pueden consultarse juntas o individualmente.

---

# HU-INT-008 — Integración del dashboard

**Como** analista/usuario  
**quiero** actualizar datos y consultar resultados desde la UI  
**para** operar BIOMAC sin depender de scripts manuales.

## Cambios frontend

- implementar `HttpDengueRepository`;
- eliminar mocks como fuente por defecto;
- acción `Actualizar datos`;
- selector de archivo y mes;
- confirmación antes de enviar;
- estado de procesamiento;
- éxito con `run_id` y corte;
- error con reintento seguro;
- tras éxito, ejecutar `GET latest`;
- botón `Refresh` solo ejecuta `GET latest`;
- conservar pantalla principal de decisión.

## Criterios de aceptación

- CA01: al abrir la página se consulta `latest`.
- CA02: upload válido actualiza la pantalla luego de inferencia exitosa.
- CA03: upload fallido no borra el resultado anterior.
- CA04: ninguna clase/probabilidad/SHAP/threshold se calcula en React.
- CA05: loading, empty, error y retry están implementados.

---

# HU-INT-009 — Metadata, explicabilidad y calidad

**Como** usuario  
**quiero** conocer qué modelo y qué información sustentan la alerta  
**para** interpretar el resultado con trazabilidad.

## Alcance

- Champion nombre/versión;
- fecha de inferencia y corte;
- calidad/frescura;
- regla/threshold real;
- explicación local si existe;
- warnings cuando un dato opcional falte.

## Criterios de aceptación

- CA01: SHAP se etiqueta como tal solo cuando sea local y real.
- CA02: output no probabilístico no se presenta como `%`.
- CA03: metadata de entrenamiento se muestra solo como información recibida del Champion, no gestionada por este flujo.
- CA04: campos no disponibles son `null`/vacíos explícitos, nunca mocks.

---

# HU-INT-010 — Pruebas end-to-end y cierre

**Como** equipo BIOMAC  
**quiero** demostrar que el flujo completo es reproducible  
**para** cerrar la integración con evidencia técnica.

## Escenarios mínimos

1. health correcto;
2. carga mensual válida;
3. archivo inválido;
4. periodo inválido;
5. falta de columnas/features;
6. Champion no disponible;
7. inferencia T+1/T+2 exitosa;
8. fallo durante inferencia;
9. persistencia exitosa;
10. última predicción después de upload;
11. Refresh sin nueva inferencia;
12. historial de al menos dos runs;
13. reintento idéntico/idempotencia;
14. Bucaramanga y Cali;
15. contrato frontend/API;
16. no regresión de componentes visuales.

## Criterio de terminado

Se demuestra con evidencia automatizada y manual:

```text
archivo mensual
→ POST monthly-runs
→ Champion
→ snapshot COMPLETED
→ GET latest
→ dashboard
```

Luego se ejecuta `Refresh` y se verifica que el contador/log de inferencias no aumenta.

## 3. Definición global de terminado

El flujo se considera implementado cuando:

- no existen datos mock como fallback productivo;
- el upload mensual es el trigger normal de inferencia;
- el Champion utilizado está versionado/trazado;
- una predicción exitosa queda persistida;
- `Refresh` es read-only;
- errores no destruyen el último resultado válido;
- Bucaramanga y Cali muestran T+1/T+2 según salidas reales;
- pruebas de contrato y E2E pasan;
- entrenamiento y selección del Champion permanecen fuera de este alcance.