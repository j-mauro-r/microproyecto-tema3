# BIOMAC — Prueba funcional visual del dashboard antes del merge de PR #33

**Estado:** plan manual de validación pre-merge  
**Rama objetivo de ejecución:** `test/api-functional-e2e-local` (PR #33)  
**Dashboard:** `dashboard_prototipos/dengue-watch-pro`  
**Backend:** FastAPI `/api/v2`  
**Modo Champion del MVP:** salida materializada mediante `api.app.functional`  
**Objetivo:** demostrar visualmente, con evidencia antes/después, que una carga mensual aceptada por la API actualiza el snapshot persistido y que el dashboard refleja correctamente ciudad, horizonte, probabilidad, threshold, label, trazabilidad e historial.

---

## 1. Conclusiones del análisis del dashboard

El dashboard vigente funciona así:

```text
Browser
→ DengueDashboard
→ useDengueDashboard
→ React Query
→ HttpDengueRepository
→ FastAPI /api/v2
```

Características relevantes para esta prueba:

1. La ruta principal es `/`.
2. La fuente normal de datos es `HttpDengueRepository`; no existe fallback automático a mocks.
3. La URL de API se configura exclusivamente con:

```text
VITE_BIOMAC_API_BASE_URL=http://127.0.0.1:8001/api/v2
```

4. Al abrir el dashboard se ejecuta inmediatamente `GET /predictions/latest`.
5. También se consulta `GET /predictions/history?limit=12`.
6. La ciudad seleccionada por defecto es Bucaramanga (`68001`).
7. El selector permite alternar Bucaramanga/Cali.
8. Cada ciudad muestra tarjetas separadas T+1 y T+2 con:
   - `label`;
   - `probability`;
   - `decision_threshold`;
   - `target_month`;
   - datos opcionales cuando existen.
9. El dashboard no recalcula el label: presenta el resultado recibido de la API.
10. `Actualizar datos` abre un diálogo, exige CSV + mes `YYYY-MM`, solicita confirmación y ejecuta `POST /monthly-runs`.
11. Un POST exitoso invalida y vuelve a consultar `latest` e `history`.
12. `Actualizar vista` solo vuelve a consultar `latest`; no dispara inferencia ni un POST nuevo.
13. El encabezado presenta corte, Champion y versión; además se muestran `run_id` y `feature_contract_version`.
14. Si la API no está disponible, la UI muestra `BIOMAC API no disponible`.
15. Si la API responde que aún no hay snapshot persistido, la UI muestra `Sin predicciones`.

### Implicación importante para la evidencia inicial

No existe un estado de “dashboard completo sin interactuar con API”: al montar la página se intenta `GET latest` automáticamente.

Por tanto, la evidencia inicial correcta se divide en dos fotografías:

- **E00 — API apagada:** demostrar que el dashboard local no usa mocks ni datos falsos y muestra `BIOMAC API no disponible`.
- **E01 — API encendida + SQLite vacío:** demostrar el estado real anterior a la primera carga: `Sin predicciones`.

Esto es más sólido que intentar capturar datos simulados como supuesto estado inicial.

---

## 2. Definición de “alerta” para los tres escenarios

Para esta prueba visual se usa **T+2 como estado principal de alerta de la ciudad**, porque el objetivo del dashboard prioriza el horizonte de dos meses.

Regla de clasificación del escenario:

```text
T+2 label = EXCESO     → ciudad con alerta
T+2 label = NO_EXCESO  → ciudad sin alerta
```

T+1 también debe registrarse y fotografiarse, pero no determina la clasificación principal del escenario.

Escenarios mínimos:

| Escenario | Cali T+2 | Bucaramanga T+2 |
|---|---|---|
| S01 | `EXCESO` | `NO_EXCESO` |
| S02 | `NO_EXCESO` | `EXCESO` |
| S03 | `NO_EXCESO` | `NO_EXCESO` |

El Champion real actualmente materializado para `2025-12` corresponde a **S02**: Bucaramanga en `EXCESO` y Cali en `NO_EXCESO`.

---

## 3. Regla de integridad de los escenarios

La prueba debe priorizar salidas **reales del Champion**.

Para cada escenario se debe seleccionar un `reference_month` distinto y generar desde el mismo periodo:

```text
features_mensual.parquet
├─ ChampionResult JSON
└─ CSV mensual con las 39 features
```

No editar manualmente `probability`, `threshold`, `label`, `feature_contract_version` ni `feature_contract_sha256` para forzar un resultado.

### Gate

Antes de ejecutar S01/S02/S03 se deben identificar meses reales que produzcan los tres patrones requeridos.

Si el historial disponible del modelo no contiene alguno de ellos:

- marcar ese escenario como `BLOCKED — patrón no observado en datos/modelo disponibles`;
- no fabricar una salida y presentarla como evidencia del modelo;
- opcionalmente puede hacerse una prueba visual con fixture controlado, pero debe etiquetarse explícitamente como **prueba de UI/contrato**, no como evidencia de inferencia real.

La prueba completa “modelo real → API → dashboard” solo puede cerrarse si los tres escenarios usan salidas reales.

---

# 4. Preparación

## Paso P01 — Usar la rama correcta

**Dónde:** Terminal, raíz del repositorio.

```bash
git fetch origin
git switch test/api-functional-e2e-local
git status
git rev-parse HEAD
```

**Resultado esperado:** working tree limpio y rama de PR #33 activa.

**Evidencia P01:** captura de terminal con rama, SHA y `working tree clean`.

---

## Paso P02 — Preparar carpeta de evidencia runtime

**Dónde:** Terminal, raíz del repositorio.

```bash
mkdir -p runtime/dashboard-test/evidence
mkdir -p runtime/dashboard-test/scenarios
mkdir -p runtime/dashboard-test/input
```

Los archivos bajo `runtime/` no deben versionarse.

Convención de nombres recomendada:

```text
E00-dashboard-api-off.png
E01-dashboard-empty.png
S01-cali.png
S01-bucaramanga.png
S01-receipt.png
S02-cali.png
S02-bucaramanga.png
S02-receipt.png
S03-cali.png
S03-bucaramanga.png
S03-receipt.png
E99-history-final.png
```

---

## Paso P03 — Configurar el dashboard local

**Dónde:** `dashboard_prototipos/dengue-watch-pro/`.

Crear o validar `.env.local`:

```text
VITE_BIOMAC_API_BASE_URL=http://127.0.0.1:8001/api/v2
```

Ejecutar el frontend:

```bash
cd dashboard_prototipos/dengue-watch-pro
pnpm dev --host 127.0.0.1
```

Si las dependencias no están instaladas, instalarlas sin agregar un lockfile nuevo al repositorio, por ejemplo:

```bash
pnpm install --lockfile=false
```

Luego abrir la URL que entregue Vite, normalmente:

```text
http://127.0.0.1:5173/
```

**Evidencia P03:** terminal de Vite mostrando que el dashboard está disponible localmente.

---

# 5. Evidencia inicial antes de cargas

## Paso E00 — Dashboard con API apagada

**Dónde:** Browser local.

Precondición: FastAPI NO debe estar ejecutándose en el puerto `8001`.

1. Abrir/recargar el dashboard.
2. Esperar a que termine el intento de conexión.
3. Verificar que aparece:

```text
BIOMAC API no disponible
```

4. Verificar que no aparecen predicciones simuladas de Bucaramanga/Cali.

**Evidencia:** `E00-dashboard-api-off.png`.

**Qué demuestra:** el dashboard no hace fallback silencioso a mocks.

---

## Paso E01 — API activa con base nueva y sin predicciones

**Dónde:** Terminal API + Browser.

Crear una SQLite limpia:

```bash
rm -f runtime/dashboard-test/biomac-dashboard-test.db
```

Preparar inicialmente un ChampionResult válido; puede usarse el actual `champion_output.json` solo para permitir levantar la composición funcional:

```bash
cp champion_output.json runtime/dashboard-test/scenarios/bootstrap.json
```

Levantar FastAPI:

```bash
export BIOMAC_DB_PATH="$PWD/runtime/dashboard-test/biomac-dashboard-test.db"
export BIOMAC_FUNCTIONAL_CHAMPION_OUTPUT="$PWD/runtime/dashboard-test/scenarios/bootstrap.json"
export BIOMAC_CORS_ORIGINS="http://127.0.0.1:5173,http://localhost:5173"
uvicorn api.app.functional:app --host 127.0.0.1 --port 8001
```

Validar health:

```bash
curl -s http://127.0.0.1:8001/api/v2/health
```

En el browser, recargar el dashboard.

**Resultado esperado:**

```text
Sin predicciones
Aún no hay predicciones disponibles...
```

**Evidencia:** `E01-dashboard-empty.png`.

**Qué demuestra:** existe conexión real dashboard → FastAPI, pero aún no hay snapshot previo a la primera carga.

---

# 6. Descubrir y preparar los tres escenarios reales

## Paso D01 — Identificar meses candidatos

**Dónde:** Terminal, raíz del repositorio con entorno Python del modelo disponible.

Se necesita:

```text
data/processed/features_mensual.parquet
model/xgb_clasico_calibrated.pkl
model/xgb_clasico_T2_calibrated.pkl
scripts/generate_champion_output.py
```

Si `features_mensual.parquet` no está materializado, obtener la versión correcta mediante el mecanismo del equipo antes de continuar.

Listar meses disponibles para ambas ciudades y generar ChampionResult para meses candidatos.

Para cada salida registrar:

```text
reference_month
Cali T+1 label/probability/threshold
Cali T+2 label/probability/threshold
Bucaramanga T+1 label/probability/threshold
Bucaramanga T+2 label/probability/threshold
```

Seleccionar tres meses **distintos** que cumplan S01, S02 y S03 según T+2.

S02 puede partir de la salida real ya validada `2025-12` si el CSV del mismo corte puede materializarse correctamente.

**Evidencia D01:** tabla de selección de escenarios con mes y cuatro predicciones de cada uno.

---

## Paso D02 — Generar los tres ChampionResult

**Dónde:** Terminal, raíz del repositorio.

Para cada mes seleccionado:

```bash
python scripts/generate_champion_output.py \
  --reference-month "YYYY-MM" \
  --out "runtime/dashboard-test/scenarios/S0X_YYYY-MM.json"
```

Validar en cada JSON:

- `model_name`;
- `model_version`;
- `reference_month`;
- `feature_contract_version`;
- `feature_contract_sha256`;
- 4 predicciones;
- probabilities/thresholds/labels esperados.

Contrato esperado actualmente:

```text
feature_contract_version = pr12-74e385c3
feature_contract_sha256   = 786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba
```

No continuar si algún JSON no cumple el contrato.

---

## Paso D03 — Generar el CSV correspondiente a cada escenario

**Dónde:** Terminal, raíz del repositorio.

Para cada `reference_month`, extraer del mismo `features_mensual.parquet`:

```text
2 filas
- 68001 Bucaramanga
- 76001 Cali

39 features Champion
mismo año/mes del ChampionResult
sin targets/futuros prohibidos
sin NaN/no finitos
```

Guardar como:

```text
runtime/dashboard-test/input/S01_YYYY-MM.csv
runtime/dashboard-test/input/S02_YYYY-MM.csv
runtime/dashboard-test/input/S03_YYYY-MM.csv
```

**Gate:** JSON y CSV de cada escenario deben corresponder al mismo corte real.

---

# 7. Ejecución de cada escenario

## Regla de reinicio del API

`api.app.functional` carga el ChampionResult al iniciar el proceso. Por tanto, para cambiar de S01 → S02 → S03 se debe detener Uvicorn y reiniciarlo apuntando al JSON del escenario siguiente.

Se conserva la **misma SQLite** para evidenciar crecimiento del historial.

---

## Escenario S01 — Cali con alerta / Bucaramanga normal

### S01.1 Levantar API con ChampionResult S01

**Dónde:** Terminal API.

```bash
export BIOMAC_DB_PATH="$PWD/runtime/dashboard-test/biomac-dashboard-test.db"
export BIOMAC_FUNCTIONAL_CHAMPION_OUTPUT="$PWD/runtime/dashboard-test/scenarios/S01_YYYY-MM.json"
export BIOMAC_CORS_ORIGINS="http://127.0.0.1:5173,http://localhost:5173"
uvicorn api.app.functional:app --host 127.0.0.1 --port 8001
```

### S01.2 Cargar CSV desde el dashboard

**Dónde:** Browser.

1. Clic en **Actualizar datos**.
2. Seleccionar `runtime/dashboard-test/input/S01_YYYY-MM.csv`.
3. Seleccionar exactamente el mismo `YYYY-MM` como mes de referencia.
4. Clic **Confirmar actualización**.
5. Aceptar la confirmación del navegador.
6. Esperar mensaje:

```text
Actualización completada: <run_id> · YYYY-MM · COMPLETED
```

**Evidencia:** `S01-receipt.png`.

### S01.3 Evidencia visual Cali

1. Seleccionar **Cali**.
2. Verificar T+1 y T+2 contra el JSON S01.
3. Confirmar especialmente:

```text
Cali T+2 = EXCESO
```

4. Incluir en la captura encabezado/corte y tarjetas de predicción.

**Evidencia:** `S01-cali.png`.

### S01.4 Evidencia visual Bucaramanga

1. Seleccionar **Bucaramanga**.
2. Verificar T+1 y T+2 contra el JSON S01.
3. Confirmar:

```text
Bucaramanga T+2 = NO_EXCESO
```

**Evidencia:** `S01-bucaramanga.png`.

### S01.5 Verificar latest/history

**Dónde:** Browser + Terminal opcional.

La UI debe haber actualizado automáticamente `latest` e `history` después del POST.

Validación HTTP opcional:

```bash
curl -s http://127.0.0.1:8001/api/v2/predictions/latest
curl -s "http://127.0.0.1:8001/api/v2/predictions/history?limit=12"
```

Registrar `run_id`, `reference_month` y Champion version.

---

## Escenario S02 — Bucaramanga con alerta / Cali normal

Repetir el mismo procedimiento usando S02.

Resultado T+2 obligatorio:

```text
Cali         = NO_EXCESO
Bucaramanga  = EXCESO
```

Para el Champion real actualmente validado en `2025-12`, los valores conocidos son:

```text
Bucaramanga T+1 = 0.7347 / threshold 0.34 / EXCESO
Bucaramanga T+2 = 0.6724 / threshold 0.27 / EXCESO
Cali         T+1 = 0.0132 / threshold 0.34 / NO_EXCESO
Cali         T+2 = 0.0150 / threshold 0.27 / NO_EXCESO
```

**Evidencias mínimas:**

- `S02-receipt.png`
- `S02-cali.png`
- `S02-bucaramanga.png`

Después de S02, `Historial de predicciones` debe contener al menos los runs S01 y S02.

---

## Escenario S03 — Cali y Bucaramanga sin alertas

Repetir el procedimiento usando S03.

Resultado T+2 obligatorio:

```text
Cali         = NO_EXCESO
Bucaramanga  = NO_EXCESO
```

**Evidencias mínimas:**

- `S03-receipt.png`
- `S03-cali.png`
- `S03-bucaramanga.png`

Después de S03, el historial debe contener los tres runs completados.

---

# 8. Evidencia final de historial y Refresh

## Paso E99 — Historial final

**Dónde:** Browser.

Capturar `Historial de predicciones` mostrando S01, S02 y S03 con sus respectivos meses/runs.

**Evidencia:** `E99-history-final.png`.

---

## Paso R01 — Validar que Actualizar vista es read-only

**Dónde:** Browser + API/SQLite.

1. Registrar el número de runs antes del Refresh:

```bash
sqlite3 runtime/dashboard-test/biomac-dashboard-test.db \
  "SELECT COUNT(*) FROM runs;"
```

2. En el dashboard, clic **Actualizar vista**.
3. Confirmar que se mantiene el mismo `run_id` visible.
4. Consultar nuevamente:

```bash
sqlite3 runtime/dashboard-test/biomac-dashboard-test.db \
  "SELECT COUNT(*) FROM runs;"
```

El conteo debe ser idéntico.

**Evidencia R01:** captura de dashboard después del Refresh + terminal con conteos iguales.

---

# 9. Matriz de evidencias obligatorias

| ID | Evidencia | Qué demuestra |
|---|---|---|
| P01 | rama/SHA/worktree limpio | trazabilidad del código probado |
| P03 | Vite local | dashboard ejecutado localmente |
| E00 | API apagada | no existe fallback a mocks |
| E01 | API activa + DB vacía | estado real antes de primera carga |
| D01 | tabla de meses/resultados | procedencia real de los tres escenarios |
| S01-R | receipt COMPLETED | POST exitoso escenario 1 |
| S01-C | Cali | alerta T+2 en Cali |
| S01-B | Bucaramanga | normal T+2 en Bucaramanga |
| S02-R | receipt COMPLETED | POST exitoso escenario 2 |
| S02-C | Cali | normal T+2 en Cali |
| S02-B | Bucaramanga | alerta T+2 en Bucaramanga |
| S03-R | receipt COMPLETED | POST exitoso escenario 3 |
| S03-C | Cali | normal T+2 en Cali |
| S03-B | Bucaramanga | normal T+2 en Bucaramanga |
| E99 | historial con 3 runs | persistencia y actualización de history |
| R01 | Refresh sin nuevo run | Refresh read-only |

---

# 10. Criterios de aceptación

La prueba se declara **CERRADA / APROBADA** únicamente si se cumplen todos los criterios:

### Configuración y estado inicial

- **CA01:** el dashboard inicia localmente en `/`.
- **CA02:** con API apagada muestra error de conexión y no mocks.
- **CA03:** con API activa y SQLite vacío muestra `Sin predicciones`.
- **CA04:** `VITE_BIOMAC_API_BASE_URL` apunta a `http://127.0.0.1:8001/api/v2`.

### Integración API/dashboard

- **CA05:** cada uno de S01/S02/S03 finaliza en `COMPLETED`.
- **CA06:** cada escenario genera un `run_id` trazable.
- **CA07:** después del POST el dashboard actualiza automáticamente `latest`.
- **CA08:** después del POST el historial también se actualiza.
- **CA09:** el header muestra el `reference_month` del escenario activo y Champion correcto.
- **CA10:** `feature_contract_version` visible corresponde al contrato vigente.

### Correspondencia visual

- **CA11:** S01 muestra Cali T+2 `EXCESO` y Bucaramanga T+2 `NO_EXCESO`.
- **CA12:** S02 muestra Cali T+2 `NO_EXCESO` y Bucaramanga T+2 `EXCESO`.
- **CA13:** S03 muestra ambas ciudades T+2 `NO_EXCESO`.
- **CA14:** T+1 y T+2 de cada ciudad coinciden con el ChampionResult correspondiente.
- **CA15:** probability y threshold mostrados coinciden con la salida materializada sin recálculo del frontend.
- **CA16:** el selector de ciudad cambia correctamente entre Bucaramanga y Cali sin crear un nuevo run.

### Persistencia/read-only

- **CA17:** al finalizar existen al menos tres runs `COMPLETED` correspondientes a S01/S02/S03.
- **CA18:** el historial muestra los tres periodos/runs.
- **CA19:** `Actualizar vista` no crea un nuevo run.
- **CA20:** un Refresh conserva el mismo snapshot si no hubo nueva carga.

### Integridad de la evidencia

- **CA21:** cada escenario usa JSON y CSV del mismo `reference_month`.
- **CA22:** no se editaron manualmente labels/probabilities/thresholds/hashes para obtener un PASS.
- **CA23:** los tres escenarios provienen de salidas reales del Champion para declarar cerrada la prueba E2E modelo→dashboard.
- **CA24:** se conservaron todas las capturas obligatorias de la matriz de evidencias.

---

# 11. Resultado final a registrar

Completar al terminar:

```text
Rama / SHA probado:
Dashboard URL:
API URL:
SQLite utilizada:
Champion model_version:
Feature contract version:
Feature contract sha256:

S01 reference_month:
S01 run_id:
S01 resultado: PASS / FAIL / BLOCKED

S02 reference_month:
S02 run_id:
S02 resultado: PASS / FAIL / BLOCKED

S03 reference_month:
S03 run_id:
S03 resultado: PASS / FAIL / BLOCKED

Refresh read-only: PASS / FAIL
Historial 3 runs: PASS / FAIL

DASHBOARD LOCAL BASELINE: APROBADO / NO APROBADO
DASHBOARD ↔ API INTEGRATION: APROBADO / NO APROBADO
THREE ALERT SCENARIOS: APROBADO / NO APROBADO
VISUAL FUNCTIONAL TEST: CERRADA / NO CERRADA
```

---

## 12. Alcance de la conclusión

Esta prueba valida el flujo visible:

```text
CSV mensual real
→ FastAPI
→ ChampionResult materializado real
→ SQLite
→ latest/history
→ HttpDengueRepository
→ React Query
→ Dashboard
```

No demuestra ejecución online de XGBoost dentro de FastAPI, porque el MVP de PR #33 usa el modo materializado. La inferencia real se produce previamente al generar cada `ChampionResult`; la prueba demuestra que sus resultados se propagan sin alteración desde la frontera Champion hasta la interfaz visual.
