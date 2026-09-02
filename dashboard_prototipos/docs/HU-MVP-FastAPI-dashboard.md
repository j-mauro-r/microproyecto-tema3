# HU MVP — FastAPI + dashboard para flujo mensual de inferencia BIOMAC

**ID:** HU-API-MVP-01  
**Estado:** ACTUALIZADA  
**Prioridad:** ALTA  
**Tipo:** Backend / Integración / Dashboard  
**Dependencias:** `arquitectura.md`, `implementacion.md`, `API-sign.md`, `plan.md`, `diccionario-de-datos.md`  

## 1. Historia de usuario

**Como** analista que actualiza BIOMAC,  
**quiero** cargar el archivo correspondiente al nuevo periodo mensual,  
**para** que el backend valide los datos, prepare la entrada requerida por el Champion, ejecute inferencia, persista el resultado y actualice el dashboard sin intervención manual sobre el modelo.

## 2. Objetivo MVP

Implementar el primer flujo operacional completo:

```text
Dashboard
→ carga archivo mensual
→ FastAPI
→ validación/preparación
→ Champion existente
→ salida T+1/T+2
→ persistencia
→ dashboard
```

La apertura del dashboard y `Refresh` consultan el último resultado persistido y **no ejecutan nuevamente el Champion**.

## 3. Frontera del alcance

### Dentro de alcance

- recepción del archivo mensual;
- validación técnica y temporal;
- preparación de entradas de inferencia;
- consumo del Champion aprobado;
- mapeo de salida al contrato BIOMAC;
- persistencia de runs/resultados;
- consulta latest/history;
- integración con la pantalla principal;
- trazabilidad y errores.

### Fuera de alcance

- creación del dataset de entrenamiento;
- entrenamiento/reentrenamiento;
- tuning;
- comparación de candidatos;
- selección/promoción del Champion;
- cambios al algoritmo;
- definición de thresholds/calibración no entregados por el Champion.

## 4. Decisión de arquitectura

Se reemplaza la decisión anterior de una **Snapshot API exclusivamente read-only** por un flujo operacional donde la carga mensual es el trigger normal de inferencia.

```text
             ┌──────────── Refresh / apertura ────────────┐
             │                                             v
Dashboard ───┼─ POST monthly-runs ─> FastAPI ─> Orchestrator ─> InputService
             │                                        │         │
             │                                        │         v
             │                                        │     ChampionAdapter
             │                                        │         │
             │                                        │         v
             │                                        └──> persistencia
             │                                             │
             └──────── GET predictions/latest <────────────┘
```

FastAPI no entrena modelos. `ChampionAdapter` encapsula el artefacto aprobado o, si el equipo de modelado entrega resultados materializados, un adapter equivalente.

## 5. Endpoints mínimos

### `GET /api/v2/health`

Indica disponibilidad del servicio y del Champion.

### `POST /api/v2/monthly-runs`

`multipart/form-data`:
- `file`;
- `reference_month`.

Responsabilidad:
1. validar;
2. preparar input;
3. ejecutar Champion;
4. mapear salida;
5. persistir;
6. responder run finalizado.

### `GET /api/v2/runs/{run_id}`

Retorna trazabilidad y estado de una ejecución.

### `GET /api/v2/predictions/latest`

Devuelve la última predicción exitosa. Es el endpoint normal para abrir/refrescar el dashboard.

### `GET /api/v2/predictions/history`

Devuelve resultados históricos persistidos.

## 6. Estados del run

```text
RECEIVED
VALIDATING
PREPARING
INFERENCING
PERSISTING
COMPLETED
FAILED
```

Una ejecución fallida nunca reemplaza la última predicción exitosa.

## 7. Reglas de integración

1. El frontend no construye features, canal, clase, threshold ni SHAP.
2. `Refresh` solo llama `GET /predictions/latest`.
3. El modelo se ejecuta normalmente después de una nueva carga mensual válida.
4. El backend no inventa salidas que el Champion no produzca.
5. `probability` se muestra como porcentaje solo cuando sea una probabilidad válida.
6. SHAP se expone únicamente si existe explicación local real.
7. T+1 y T+2 deben corresponder a salidas realmente soportadas por el Champion.
8. Cada resultado debe incluir Champion/versión y corte usados.
9. No se aceptan datos posteriores a `reference_month` para construir la inferencia.
10. Un fallo conserva disponible el último snapshot `COMPLETED`.
11. Los archivos cargados y resultados runtime no se versionan en Git.
12. No se habilita reentrenamiento desde la UI.

## 8. Funcionalidad del dashboard impactada

La HU activa o corrige principalmente:

- selector de ciudad;
- fecha de corte;
- alerta T+2;
- salida T+1/T+2;
- regla/threshold real;
- estado frente al canal;
- comparativo Bucaramanga/Cali;
- histórico/canal;
- explicabilidad si existe;
- loading/error/empty/retry;
- última inferencia;
- nueva acción `Actualizar datos`;
- estado del procesamiento;
- `Refresh` read-only.

## 9. Criterios de aceptación

### CA01 — Health
`GET /api/v2/health` responde 200 y declara si el Champion está disponible.

### CA02 — Carga mensual válida
Un archivo válido para un nuevo `reference_month` recorre validación, preparación, inferencia y persistencia, finalizando `COMPLETED`.

### CA03 — Carga inválida
Un archivo inválido produce error controlado y no invoca el Champion.

### CA04 — Champion
La inferencia utiliza exactamente el Champion configurado y registra su versión.

### CA05 — T+1/T+2
La respuesta contiene únicamente horizontes que el Champion soporte realmente.

### CA06 — Persistencia
El resultado queda almacenado antes de responder éxito.

### CA07 — Latest
Después de una ejecución exitosa, `GET /predictions/latest` devuelve ese snapshot.

### CA08 — Refresh
Presionar `Refresh` actualiza la UI desde `GET latest` y no genera un nuevo run de inferencia.

### CA09 — Fallo seguro
Si una nueva carga falla, el dashboard puede continuar mostrando la última predicción exitosa junto con el error de actualización.

### CA10 — Sin cálculos epidemiológicos en React
No existen cálculos frontend de clase, threshold, casos futuros, SHAP ni probabilidad.

### CA11 — Trazabilidad
Cada resultado incluye `run_id`, `generated_at`, `reference_month`, hash de fuente y Champion/version.

### CA12 — Pruebas
Existen pruebas para health, upload válido/inválido, inferencia, persistencia, latest, history, fallo del Champion y Refresh sin inferencia.

## 10. Estructura sugerida

```text
api/
├── app/
│   ├── main.py
│   ├── api/v2/
│   │   ├── health.py
│   │   ├── monthly_runs.py
│   │   ├── runs.py
│   │   └── predictions.py
│   ├── schemas/
│   ├── services/
│   │   ├── monthly_prediction_orchestrator.py
│   │   ├── input_service.py
│   │   └── result_mapper.py
│   ├── champion/
│   │   ├── port.py
│   │   └── adapter.py
│   ├── repositories/
│   │   ├── run_repository.py
│   │   └── prediction_repository.py
│   └── core/config.py
└── tests/
```

## 11. Relación con las HUs detalladas

Esta HU describe el MVP funcional completo. Para implementación incremental, la fuente de verdad del backlog es `implementacion.md`, con HUs `HU-INT-001` a `HU-INT-010`.