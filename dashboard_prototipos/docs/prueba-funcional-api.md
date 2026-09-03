# BIOMAC — Prueba funcional local de API con salida materializada del Champion

**Estado:** guía de ejecución manual  
**Ámbito:** local-only, posterior a HU006  
**PR de trabajo:** `#27` — `docs/hu006-persistencia-trazabilidad`  
**Modelo/salida Champion:** PR `#12` — `feat/dashboard-sat-dengue`  
**Objetivo:** comprobar por HTTP que una carga mensual válida recorre FastAPI → HU002/HU005/HU004 → HU006/SQLite y devuelve un run `COMPLETED` con las salidas reales materializadas del Champion.

---

## 1. Qué valida esta prueba

Esta primera prueba funcional no busca todavía ejecutar XGBoost directamente dentro del proceso de FastAPI. Usa la estrategia **materializada** aprobada en HU004:

```text
PR12 / Champion real
        ↓
generate_champion_output.py
        ↓
ChampionResult JSON materializado
        ↓
FastAPI local
        ↓
ChampionService — estrategia MATERIALIZED
        ↓
ChampionOutput
        ↓
HU005 ResultMapper
        ↓
HU006 SQLite
        ↓
HTTP 201 COMPLETED
```

También se carga por HTTP un CSV mensual compatible con HU002 para el **mismo `reference_month`** del JSON materializado.

La prueba confirma:

- que FastAPI está levantado y recibe multipart/form-data;
- que HU002 acepta el CSV real del periodo;
- que HU005 ejecuta el flujo y llega al ChampionService;
- que HU004 consume el `ChampionResult` producido por PR12 sin inventar datos;
- que T+1/T+2, probabilidades, thresholds y labels llegan al backend;
- que HU006 persiste run + predicciones en SQLite;
- que el API responde `201` únicamente después del commit;
- que la salida HTTP y SQLite corresponden al mismo run.

No valida todavía:

- ejecución online de XGBoost desde FastAPI;
- Lovable;
- AWS;
- `latest/history` de HU007;
- reentrenamiento;
- feature engineering desde datos crudos.

---

## 2. Respuesta clave: ¿cómo apunta el API a PR12 si el API está en `main`?

**El API no debe importar ni ejecutar código directamente desde otra rama Git.**

Git no combina dos ramas automáticamente dentro del mismo working tree. Además, mezclar PR12 con `main` mediante cherry-pick/merge solo para hacer una prueba introduciría cambios de modelado todavía no aprobados en la rama principal.

Para esta prueba se usa la frontera contractual diseñada en HU004:

```text
PR12
  └─ produce un ChampionResult JSON versionado por metadata

main / PR27
  └─ consume ese JSON mediante MaterializedChampionResultProvider
```

Por tanto, la conexión entre ambos no es:

```text
FastAPI → rama PR12 de GitHub
```

sino:

```text
PR12 checkout local separado
→ genera artefacto JSON
→ copiar artefacto a runtime local del API
→ FastAPI consume ese artefacto
```

Esto permite probar el contrato real sin fusionar PR12 en `main`.

### 2.1 Uso de `git worktree`

Se recomienda tener dos carpetas locales simultáneas:

```text
microproyecto-tema3/          ← API / main o PR27
microproyecto-tema3-pr12/     ← PR12 del modelo
```

Ambas pertenecen al mismo repositorio Git, pero cada carpeta queda en un commit/rama diferente.

**Importante:** en el momento de redactar esta guía el head observado de PR12 es:

```text
2f87422941c63ca3ea8dac485da5307fbaea11b9
```

Antes de la prueba debe verificarse nuevamente el SHA del PR12 y registrar el SHA realmente usado como evidencia.

---

# 3. Preparación antes de iniciar

## Paso 0 — Gate de HU006

**Dónde:** GitHub.

Antes de la prueba:

1. PR27 debe haber pasado auditoría.
2. HU006 debe estar `[COMPLETADA — DESARROLLO]`.
3. Si PR27 ya fue aprobado, hacer merge y usar `main` actualizado.
4. Si se decide probar antes del merge, ejecutar el API desde `docs/hu006-persistencia-trazabilidad` y dejarlo explícito en la evidencia.

Resultado esperado:

```text
POST /api/v2/monthly-runs
→ HU005 READY_TO_PERSIST
→ HU006 PERSISTING
→ SQLite COMMIT
→ COMPLETED
→ HTTP 201
```

---

## Paso 1 — Actualizar el checkout del API

**Dónde:** VS Code → Terminal, dentro de la carpeta principal `microproyecto-tema3`.

Si PR27 ya fue mergeado:

```bash
git switch main
git pull --ff-only origin main
git status
```

Debe terminar con working tree limpio.

Si PR27 todavía no ha sido mergeado:

```bash
git fetch origin
git switch docs/hu006-persistencia-trazabilidad
git pull --ff-only origin docs/hu006-persistencia-trazabilidad
git status
```

Registrar:

```bash
git rev-parse HEAD
```

Ese SHA corresponde al backend realmente probado.

---

## Paso 2 — Preparar el entorno Python del API

**Dónde:** VS Code → Terminal, checkout del API.

Activar el entorno virtual existente del proyecto. Ejemplo macOS/Linux:

```bash
source .venv/bin/activate
```

Validar:

```bash
python --version
python -m pip check
python -m pytest api/tests -q
```

No continuar si la suite está roja.

---

## Paso 3 — Crear carpetas runtime locales

**Dónde:** VS Code → Terminal, checkout del API.

```bash
mkdir -p runtime/functional/champion
mkdir -p runtime/functional/input
```

Estos archivos son runtime de prueba y **no deben versionarse**.

Antes de continuar comprobar:

```bash
git status --short
```

La base SQLite está cubierta por los patrones `.db/.sqlite`; los JSON/CSV de esta prueba no deben agregarse a Git. Si aparecen como untracked, no ejecutar `git add` sobre ellos.

---

# 4. Preparar PR12 sin tocar la rama del API

## Paso 4 — Descargar referencias y capturar el SHA real de PR12

**Dónde:** VS Code → Terminal, checkout principal del repositorio.

```bash
git fetch origin feat/dashboard-sat-dengue
```

Obtener el SHA:

```bash
git rev-parse origin/feat/dashboard-sat-dengue
```

Guardar ese valor en la evidencia de la prueba como:

```text
PR12_CHAMPION_SHA=<sha>
```

No asumir que el SHA histórico de esta guía continúa siendo el último.

---

## Paso 5 — Crear un worktree separado para PR12

**Dónde:** VS Code → Terminal, desde `microproyecto-tema3`.

Suponiendo que la carpeta hermana no existe:

```bash
git worktree add --detach ../microproyecto-tema3-pr12 origin/feat/dashboard-sat-dengue
```

Validar:

```bash
cd ../microproyecto-tema3-pr12
git status
git rev-parse HEAD
```

El SHA debe ser el registrado en el paso anterior.

**No hacer merge, rebase ni cherry-pick entre PR12 y el checkout del API para esta prueba.**

---

# 5. Preparar las dependencias del Champion en PR12

## Paso 6 — Validar artefactos necesarios

**Dónde:** VS Code → Explorer y Terminal, carpeta `microproyecto-tema3-pr12`.

El generador de PR12 necesita como mínimo:

```text
data/processed/features_mensual.parquet
model/xgb_clasico_calibrated.pkl
model/xgb_clasico_T2_calibrated.pkl
scripts/generate_champion_output.py
```

Validar:

```bash
ls -lh data/processed/features_mensual.parquet
ls -lh model/xgb_clasico_calibrated.pkl
ls -lh model/xgb_clasico_T2_calibrated.pkl
ls -lh scripts/generate_champion_output.py
```

Si `features_mensual.parquet` no existe porque está gestionado fuera de Git, **detener la prueba y materializar exactamente la versión de datos requerida por PR12** siguiendo el mecanismo definido por el equipo. No sustituirlo por un archivo parecido ni generar datos ficticios.

---

## Paso 7 — Preparar el entorno Python de PR12

**Dónde:** VS Code → Terminal, worktree PR12.

Usar un entorno separado del API para evitar contaminar dependencias. Ejemplo:

```bash
python -m venv .venv-pr12
source .venv-pr12/bin/activate
```

Instalar las dependencias requeridas por PR12 conforme al repositorio. Como mínimo el script necesita NumPy, pandas, pyarrow, scikit-learn/XGBoost y dependencias del artefacto serializado.

Antes de generar salida, validar que Python puede importar el script:

```bash
python scripts/generate_champion_output.py --help
```

---

# 6. Elegir un periodo de prueba

## Paso 8 — Seleccionar `reference_month`

**Dónde:** Terminal, worktree PR12.

Para la primera prueba se recomienda utilizar un mes que exista en `features_mensual.parquet` para **Bucaramanga 68001 y Cali 76001** y para el cual PR12 pueda generar T+1/T+2.

Puede dejarse que PR12 seleccione el último mes disponible ejecutando primero:

```bash
python scripts/generate_champion_output.py --out /tmp/champion_probe.json
```

Luego inspeccionar:

```bash
cat /tmp/champion_probe.json
```

Tomar el valor:

```json
"reference_month": "YYYY-MM"
```

En el resto de esta guía se representa como:

```text
REF_MONTH=YYYY-MM
```

El CSV enviado al API y el ChampionResult JSON **deben usar exactamente el mismo periodo**.

---

# 7. Generar la salida real materializada de PR12

## Paso 9 — Generar ChampionResult JSON

**Dónde:** Terminal, worktree PR12.

Ejemplo:

```bash
REF_MONTH=2025-08
python scripts/generate_champion_output.py \
  --reference-month "$REF_MONTH" \
  --out "champion_output_${REF_MONTH}.json"
```

Inspeccionar:

```bash
cat "champion_output_${REF_MONTH}.json"
```

Debe contener:

- `model_name`;
- `model_version`;
- `reference_month`;
- `feature_contract_version`;
- `feature_contract_sha256`;
- `output_type`;
- cuatro predicciones esperadas:
  - Bucaramanga T+1;
  - Bucaramanga T+2;
  - Cali T+1;
  - Cali T+2;
- `probability`;
- `threshold`;
- `label`;
- `target_month`.

Guardar como evidencia los cuatro pares:

```text
municipio | horizonte | probability | threshold | label | target_month
```

Estos son los valores contra los cuales se comparará FastAPI.

---

# 8. Generar el CSV mensual que HU002 recibirá

## Paso 10 — Crear un CSV con el mismo corte y las features del Champion

**Dónde:** VS Code → Terminal, worktree PR12.

El CSV no debe ser inventado. Se extrae del mismo `features_mensual.parquet` usado por PR12.

Crear temporalmente el script `/tmp/export_biomac_month.py` o ejecutarlo desde una consola Python. Ejemplo:

```python
import sys
import pandas as pd

sys.path.insert(0, "scripts")
import generate_champion_output as champion

REF_YEAR = 2025
REF_MONTH = 8

_, _, features, _ = champion._load_champion(1)
df = pd.read_parquet("data/processed/features_mensual.parquet")

rows = df[
    (df["anio"] == REF_YEAR)
    & (df["mes"] == REF_MONTH)
    & (df["divipola"].astype(str).isin(["68001", "76001"]))
].copy()

if len(rows) != 2:
    raise SystemExit(f"Se esperaban 2 filas y se encontraron {len(rows)}")

if len(features) != 39:
    raise SystemExit(f"Se esperaban 39 features y PR12 reporta {len(features)}")

output = rows[["divipola", "anio", "mes", *features]].copy()
output.to_csv(f"monthly_{REF_YEAR}-{REF_MONTH:02d}.csv", index=False)

print("Filas:", len(output))
print("Features:", len(features))
print("Archivo:", f"monthly_{REF_YEAR}-{REF_MONTH:02d}.csv")
```

Ajustar `REF_YEAR` y `REF_MONTH` al periodo elegido.

Ejecutar:

```bash
python /tmp/export_biomac_month.py
```

Validar visualmente el archivo en **VS Code → Explorer** y verificar:

- 2 filas;
- Bucaramanga `68001`;
- Cali `76001`;
- mismo año/mes;
- 39 features;
- sin columnas target/futuras añadidas manualmente.

**Nota:** HU002 actualmente exige features numéricas, finitas y no nulas. Si el archivo generado contiene NaN, detener la prueba y revisar la compatibilidad del contrato; no rellenar con cero manualmente para “hacer pasar” el API.

---

# 9. Llevar los artefactos a runtime del API

## Paso 11 — Copiar JSON y CSV

**Dónde:** Terminal, worktree PR12.

Suponiendo que ambas carpetas son hermanas:

```bash
cp "champion_output_${REF_MONTH}.json" \
  ../microproyecto-tema3/runtime/functional/champion/

cp "monthly_${REF_MONTH}.csv" \
  ../microproyecto-tema3/runtime/functional/input/
```

Regresar al checkout del API:

```bash
cd ../microproyecto-tema3
```

Validar:

```bash
ls -lh runtime/functional/champion/
ls -lh runtime/functional/input/
```

---

# 10. Gate importante: composición local de FastAPI

## Paso 12 — Entender por qué `uvicorn api.app.main:app` no es suficiente por sí solo

**Dónde:** VS Code → Explorer, archivo `api/app/main.py`.

En HU006, `create_app()` permite inyectar `monthly_orchestrator`, pero la instancia global:

```python
app = create_app()
```

no configura por defecto una estrategia materializada ni un `MonthlyPredictionOrchestrator` real.

Por ello, si se ejecuta directamente:

```bash
uvicorn api.app.main:app
```

el endpoint puede responder que la persistencia/pipeline no está compuesto, aunque HU002/HU006 estén correctamente implementados.

Para esta prueba se requiere un **bootstrap local de composición**. Este bootstrap no cambia el dominio ni mezcla PR12 con `main`; solo conecta dependencias existentes para la ejecución manual.

---

## Paso 13 — Crear `runtime/functional_bootstrap.py`

**Dónde:** VS Code → Explorer, checkout del API.

Crear localmente:

```text
runtime/functional_bootstrap.py
```

Contenido:

```python
import json
import os
from pathlib import Path

from api.app.champion.service import (
    CallableMaterializedChampionResultProvider,
    build_champion_service,
)
from api.app.core.config import get_settings
from api.app.domain.monthly_uploads import MonthlyUploadContract, MonthlyUploadValidator
from api.app.main import create_app
from api.app.orchestration.monthly import MonthlyPredictionOrchestrator

settings = get_settings()
output_dir = Path(
    os.getenv("BIOMAC_CHAMPION_OUTPUT_DIR", "runtime/functional/champion")
)

validator = MonthlyUploadValidator(
    max_bytes=settings.upload_max_bytes,
    contract=MonthlyUploadContract(
        allowed_extensions=settings.upload_allowed_extensions,
    ),
)


def resolve_materialized_result(reference_month: str):
    path = output_dir / f"champion_output_{reference_month}.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"No existe ChampionResult materializado para {reference_month}: {path}"
        )
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


champion_service = build_champion_service(
    "materialized",
    materialized_result_provider=CallableMaterializedChampionResultProvider(
        resolve_materialized_result
    ),
)

orchestrator = MonthlyPredictionOrchestrator(
    validator=validator,
    champion_service=champion_service,
)

app = create_app(
    settings=settings,
    monthly_upload_validator=validator,
    monthly_orchestrator=orchestrator,
)
```

### Regla

Este archivo es un bootstrap manual de prueba. **No hacer commit automático de él** como parte de HU006 sin una decisión explícita del equipo. Su objetivo es levantar la composición local para esta prueba funcional.

---

# 11. Configurar SQLite para la prueba

## Paso 14 — Definir la base de datos funcional

**Dónde:** VS Code → Terminal, checkout del API.

```bash
export BIOMAC_DB_PATH="runtime/functional/biomac-functional.db"
export BIOMAC_CHAMPION_OUTPUT_DIR="runtime/functional/champion"
```

Para una ejecución desde cero, eliminar únicamente la DB funcional de pruebas:

```bash
rm -f runtime/functional/biomac-functional.db \
      runtime/functional/biomac-functional.db-wal \
      runtime/functional/biomac-functional.db-shm
```

No eliminar otras bases locales del proyecto.

---

# 12. Levantar FastAPI

## Paso 15 — Arrancar Uvicorn

**Dónde:** VS Code → Terminal 1, checkout del API, con `.venv` activado.

```bash
PYTHONPATH=. uvicorn functional_bootstrap:app \
  --app-dir runtime \
  --host 127.0.0.1 \
  --port 8001
```

Para esta prueba inicial es preferible **no usar `--reload`**, así se evita reiniciar el proceso mientras se recopila evidencia.

Esperado:

```text
Uvicorn running on http://127.0.0.1:8001
```

Mantener esta terminal abierta.

---

# 13. Validar health

## Paso 16 — Probar disponibilidad

**Dónde:** VS Code → Terminal 2.

```bash
curl -i http://127.0.0.1:8001/api/v2/health
```

Esperado:

```text
HTTP/1.1 200 OK
```

Si health falla, no ejecutar todavía la carga mensual.

---

# 14. Ejecutar la prueba funcional por HTTP

## Paso 17 — Enviar el CSV

**Dónde:** VS Code → Terminal 2.

```bash
REF_MONTH=2025-08

curl -i -X POST \
  -F "reference_month=${REF_MONTH}" \
  -F "file=@runtime/functional/input/monthly_${REF_MONTH}.csv;type=text/csv" \
  http://127.0.0.1:8001/api/v2/monthly-runs
```

Ajustar `REF_MONTH` al periodo realmente preparado.

### Resultado esperado

```text
HTTP/1.1 201 Created
```

El JSON debe incluir como mínimo:

```text
schema_version
request_id
run.run_id
run.status = COMPLETED
run.reference_month
run.source_file_sha256
run.champion_version
prediction_snapshot
prediction_snapshot.predictions
```

Guardar la respuesta completa como evidencia local:

```bash
curl -s -X POST \
  -F "reference_month=${REF_MONTH}" \
  -F "file=@runtime/functional/input/monthly_${REF_MONTH}.csv;type=text/csv" \
  http://127.0.0.1:8001/api/v2/monthly-runs \
  | python -m json.tool \
  > runtime/functional/api-response.json
```

**Nota de idempotencia:** esta segunda llamada usa el mismo archivo, periodo y Champion; HU006 debe resolverla sin crear un resultado lógico contradictorio.

---

# 15. Comparar API contra PR12

## Paso 18 — Comparación manual obligatoria

**Dónde:** VS Code → Explorer.

Abrir lado a lado:

```text
runtime/functional/champion/champion_output_<REF_MONTH>.json
runtime/functional/api-response.json
```

Comparar para cada ciudad/horizonte:

| Campo | PR12 | API | Debe coincidir |
|---|---|---|---|
| divipola | sí | sí | exacto |
| municipality | sí | sí | exacto |
| horizon | T+1/T+2 | T+1/T+2 | exacto |
| target_month | sí | sí | exacto |
| probability | sí | sí | exacto |
| threshold | `threshold` | `decision_threshold` | mismo valor |
| label | sí | sí | exacto |

El cambio de nombre contractual:

```text
PR12 threshold → API decision_threshold
```

es válido siempre que el valor numérico se preserve.

No aceptar como PASS si:

- falta T+2;
- aparece un threshold diferente;
- cambia la probabilidad;
- cambia el label;
- se inventa `expected_cases`;
- se presenta una probabilidad cuando PR12 no la entregó.

---

# 16. Validar SQLite

## Paso 19 — Inspeccionar la base local

**Dónde:** VS Code → Terminal 2.

Si macOS tiene `sqlite3` disponible:

```bash
sqlite3 runtime/functional/biomac-functional.db
```

Dentro de SQLite:

```sql
.tables
.headers on
.mode column

SELECT
  run_id,
  status,
  reference_month,
  source_file_sha256,
  idempotency_key,
  champion_version
FROM runs;

SELECT
  run_id,
  divipola,
  municipality,
  horizon,
  target_month,
  probability,
  decision_threshold,
  label
FROM predictions
ORDER BY divipola, horizon;
```

Esperado:

- run `COMPLETED`;
- un único resultado lógico para la misma idempotency key;
- cuatro predicciones para PR12 cuando T+1/T+2 estén disponibles;
- valores iguales al JSON del Champion.

Salir:

```sql
.quit
```

Si `sqlite3` CLI no está instalado, puede usarse una extensión visual de VS Code o una consulta Python local; no es necesario modificar la aplicación.

---

# 17. Probar recuperación tras reinicio

## Paso 20 — Reiniciar FastAPI

**Dónde:** Terminal 1.

Detener Uvicorn:

```text
Ctrl+C
```

Volver a iniciarlo con las mismas variables:

```bash
PYTHONPATH=. uvicorn functional_bootstrap:app \
  --app-dir runtime \
  --host 127.0.0.1 \
  --port 8001
```

La DB no debe eliminarse.

Repetir la misma carga del Paso 17.

Esperado:

- la base previamente creada sigue siendo la fuente de verdad;
- no aparece un segundo resultado lógico contradictorio para la misma idempotency key;
- el flujo sigue respondiendo consistentemente.

La consulta HTTP read-only del histórico queda para HU007, por lo que en esta prueba la verificación de recuperación se realiza contra SQLite y el comportamiento idempotente del POST.

---

# 18. Evidencia mínima a guardar

Crear localmente una carpeta:

```text
runtime/functional/evidence/
```

Guardar o documentar:

1. SHA del backend probado.
2. SHA exacto de PR12.
3. `reference_month`.
4. salida de `pytest api/tests -q` previa.
5. salida de `/health`.
6. `ChampionResult JSON` de PR12.
7. CSV usado como upload.
8. respuesta HTTP `201 COMPLETED`.
9. comparación de las cuatro predicciones.
10. consulta `runs` SQLite.
11. consulta `predictions` SQLite.
12. evidencia de segundo POST/reinicio sin duplicación contradictoria.

No subir automáticamente estos archivos runtime al repositorio. Si se desea conservar evidencia académica en Git, crear posteriormente un documento Markdown sanitizado con únicamente resultados necesarios y sin artefactos pesados/runtime.

---

# 19. Criterios PASS/FAIL

## PASS

La prueba se considera exitosa únicamente si:

- FastAPI levanta localmente;
- `/health` responde 200;
- el CSV es aceptado;
- `POST /monthly-runs` responde 201;
- el run termina `COMPLETED`;
- `champion_version` corresponde al Champion materializado utilizado;
- existen las predicciones esperadas BUC/Cali × T+1/T+2;
- `probability`, threshold y label coinciden con PR12;
- SQLite contiene el mismo run/snapshot;
- repetir el request no crea resultados contradictorios;
- no se usa AWS ni red externa para inferencia/persistencia.

## FAIL

Detener y registrar el fallo si ocurre cualquiera de estos casos:

- `503 CHAMPION_NOT_READY`;
- `503 PERSISTENCE_FAILED` por composición ausente;
- mismatch de `reference_month`;
- mismatch de `source_file_sha256`;
- feature contract incompatible;
- falta T+1 o T+2 cuando PR12 sí los produjo;
- probabilidad/threshold/label diferentes del JSON fuente;
- `201` antes de persistencia;
- run `COMPLETED` sin predictions;
- duplicación contradictoria tras reintento;
- uso accidental de mocks/fallback.

---

# 20. Troubleshooting rápido

### FastAPI devuelve `PERSISTENCE_FAILED` inmediatamente

Revisar que se esté levantando:

```text
functional_bootstrap:app
```

y no simplemente:

```text
api.app.main:app
```

La instancia global no compone automáticamente el Champion materializado.

### `ChampionResult` no encontrado

Verificar:

```bash
ls runtime/functional/champion/champion_output_${REF_MONTH}.json
```

y la variable:

```bash
echo "$BIOMAC_CHAMPION_OUTPUT_DIR"
```

### El API rechaza el CSV por features

No modificar el CSV manualmente para saltar el contrato. Comparar las 39 features de PR12 con el contrato central de HU002/HU003 y registrar la incompatibilidad.

### PR12 genera salida pero el API reporta `source_file_sha256_mismatch`

La estrategia materializada y el orquestador preservan trazabilidad del archivo fuente. Si el JSON de PR12 no incorpora el hash del CSV cargado en el mismo sentido contractual, revisar la composición/materialized adapter antes de alterar datos. No desactivar la validación para conseguir un PASS.

### PR12 cambió desde que se redactó esta guía

Volver a:

```bash
git fetch origin feat/dashboard-sat-dengue
git rev-parse origin/feat/dashboard-sat-dengue
```

Crear el worktree con el SHA que se quiere auditar y registrar ese SHA. La prueba siempre debe ser reproducible contra una versión exacta.

---

# 21. Resultado esperado de esta primera prueba

Al finalizar tendremos evidencia funcional de:

```text
PR12 ChampionResult real
           ↓
FastAPI local
           ↓
HU002 validación del archivo
           ↓
HU005 orquestación
           ↓
HU004 frontera Materialized
           ↓
HU006 persistencia SQLite
           ↓
201 COMPLETED
```

Esta prueba es el primer puente funcional entre el trabajo de modelado de PR12 y el backend de integración sin requerir que PR12 haya sido fusionado en `main`.

El siguiente nivel, cuando se decida, será sustituir la salida materializada por la estrategia ejecutable para comprobar:

```text
CSV → ChampionInput → modelo/calibrador → ChampionOutput → SQLite
```

sin cambiar el contrato HTTP ni el dashboard.
