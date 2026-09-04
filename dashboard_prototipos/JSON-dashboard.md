# BIOMAC — JSON de salida del modelo hacia backend/dashboard

## 1. Propósito

Este documento define una **salida JSON mínima y estable** que el equipo de modelado puede producir para que el backend BIOMAC la consuma y posteriormente la transforme al contrato del dashboard.

Está escrito con enfoque **AI First**: una IA de desarrollo (por ejemplo Claude Code) debe poder leer este archivo y entender qué construir, qué no inventar y cómo validar la salida.

> **Importante:** los valores numéricos usados en los ejemplos son ilustrativos. No representan resultados epidemiológicos reales y no deben copiarse como predicciones del modelo.

---

## 2. Decisión de integración

### Formato esperado

La salida del modelo hacia el backend será **JSON**.

Motivos:

- la salida ya no es un dataset de entrenamiento sino un resultado de inferencia;
- permite transportar predicciones, horizonte, threshold y metadata en una estructura explícita;
- puede validarse fácilmente con Pydantic/FastAPI;
- evita depender de posiciones de columnas como ocurriría con CSV;
- es adecuado para intercambiar información entre modelo, backend y API.

### Flujo objetivo

```text
Champion / modelo
        ↓
JSON de inferencia definido en este documento
        ↓
ChampionAdapter / backend BIOMAC
        ↓
normalización + trazabilidad + persistencia
        ↓
PredictionSnapshot de la API
        ↓
Dashboard
```

El modelo **NO tiene que producir directamente todo el JSON final del dashboard**. El backend agregará información que no pertenece al modelo, por ejemplo `run_id`, timestamps, estado del procesamiento, historial y metadata operativa.

---

## 3. Contrato mínimo esperado

El modelo debe producir un objeto con esta forma lógica:

```json
{
  "model_name": "biomac-champion",
  "model_version": "1.0.0",
  "reference_month": "2025-12",
  "feature_contract_version": "pr12-74e385c3",
  "feature_contract_sha256": "786ef0b5be829efe763e6c3eea385f90660e5bc191bf1469e02885d02e95e5ba",
  "output_type": "probability",
  "predictions": [
    {
      "divipola": "68001",
      "municipality": "Bucaramanga",
      "horizon": "T+1",
      "target_month": "2026-01",
      "probability": 0.78,
      "threshold": 0.61,
      "label": "EXCESO"
    },
    {
      "divipola": "68001",
      "municipality": "Bucaramanga",
      "horizon": "T+2",
      "target_month": "2026-02",
      "probability": 0.66,
      "threshold": 0.61,
      "label": "EXCESO"
    },
    {
      "divipola": "76001",
      "municipality": "Cali",
      "horizon": "T+1",
      "target_month": "2026-01",
      "probability": 0.43,
      "threshold": 0.61,
      "label": "NO_EXCESO"
    },
    {
      "divipola": "76001",
      "municipality": "Cali",
      "horizon": "T+2",
      "target_month": "2026-02",
      "probability": 0.58,
      "threshold": 0.61,
      "label": "NO_EXCESO"
    }
  ]
}
```

---

## 4. Significado de cada campo

### Nivel modelo

| Campo | Tipo | Obligatorio | Significado |
|---|---|---:|---|
| `model_name` | string | Sí | Nombre lógico del Champion utilizado. |
| `model_version` | string | Sí | Versión identificable del modelo/artefacto. |
| `reference_month` | string `YYYY-MM` | Sí | Último mes observado utilizado para la inferencia. |
| `feature_contract_version` | string | Sí | Versión del contrato de entrada utilizado por el modelo. |
| `feature_contract_sha256` | string | Sí | Hash del orden/lista de features para validar compatibilidad. |
| `output_type` | string | Sí | Tipo real de salida del modelo. Para el Champion actual se espera `probability` si realmente existe `predict_proba`. |
| `predictions` | array | Sí | Predicciones generadas por municipio y horizonte. |

### Nivel predicción

| Campo | Tipo | Obligatorio | Significado |
|---|---|---:|---|
| `divipola` | string de 5 dígitos | Sí | Código DANE del municipio. MVP: `68001` o `76001`. |
| `municipality` | string | Sí | Nombre legible del municipio. |
| `horizon` | `T+1` / `T+2` | Sí | Horizonte de la predicción. |
| `target_month` | string `YYYY-MM` | Sí | Mes futuro al que corresponde la predicción. |
| `probability` | float `0..1` | Condicional | Probabilidad real generada por el modelo. Solo incluir si el modelo realmente entrega probabilidad. |
| `threshold` | float `0..1` | Sí para clasificación por probabilidad | Umbral real aprobado para convertir la probabilidad en clase. No usar `0.5` por defecto si el modelo usa otro threshold. |
| `label` | string | Sí | Resultado derivado del threshold: `EXCESO` o `NO_EXCESO`. |

---

## 5. Reglas obligatorias

1. `reference_month` debe representar el mismo corte de datos utilizado para construir el input del modelo.
2. `target_month` debe corresponder matemáticamente al horizonte:
   - T+1 = mes siguiente al `reference_month`;
   - T+2 = dos meses después.
3. Para el MVP deben existir resultados para:
   - Bucaramanga (`68001`) T+1;
   - Bucaramanga (`68001`) T+2;
   - Cali (`76001`) T+1;
   - Cali (`76001`) T+2.
4. `probability` debe pertenecer al rango `[0,1]` y debe provenir realmente del modelo.
5. `threshold` debe provenir del modelo/experimento aprobado. **No inventarlo.**
6. `label` debe ser consistente con la regla contractual. Ejemplo:

```text
probability > threshold  → EXCESO
probability <= threshold → NO_EXCESO
```

Si el modelo aprobado define otra comparación (`>=`, por ejemplo), usar esa regla exacta y documentarla.
7. No generar probabilidades artificiales a partir de scores que no sean probabilísticos.
8. No incluir SHAP ni explicaciones locales salvo que se calculen realmente para esa predicción específica.
9. No incluir datos de entrenamiento completos ni las 39 features dentro de este JSON: el backend ya conoce el contrato de entrada y solo necesita la salida de inferencia y su trazabilidad.
10. La misma entrada + mismo artefacto del modelo debe producir una salida determinista salvo que el modelo tenga comportamiento explícitamente estocástico documentado.

---

## 6. Qué NO debe generar el modelo

El modelo no es responsable de producir estos campos operativos del backend/dashboard:

```text
request_id
run_id
created_at
completed_at
status
source_file metadata completa
estado de persistencia
history
HTTP status codes
mensajes de API
```

Tampoco debe inventar:

```text
SHAP
probability
threshold
expected_cases
risk_score
```

si el artefacto aprobado no los produce o no existe una regla explícita para derivarlos.

---

## 7. Contrato Python recomendado

Claude/Codex puede implementar primero un contrato interno equivalente usando `dataclass`, `TypedDict` o Pydantic.

Ejemplo conceptual:

```python
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

class ModelPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    divipola: str
    municipality: str
    horizon: Literal["T+1", "T+2"]
    target_month: str
    probability: float = Field(ge=0.0, le=1.0)
    threshold: float = Field(ge=0.0, le=1.0)
    label: Literal["EXCESO", "NO_EXCESO"]


class ChampionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_name: str
    model_version: str
    reference_month: str
    feature_contract_version: str
    feature_contract_sha256: str
    output_type: Literal["probability"]
    predictions: list[ModelPrediction]
```

Este código es orientativo. Antes de implementarlo debe contrastarse con la salida real de los modelos T+1/T+2.

---

## 8. Ejemplo de serialización

La función que ejecuta el modelo debería poder terminar con algo equivalente a:

```python
result = {
    "model_name": MODEL_NAME,
    "model_version": MODEL_VERSION,
    "reference_month": reference_month,
    "feature_contract_version": FEATURE_CONTRACT_VERSION,
    "feature_contract_sha256": FEATURE_CONTRACT_SHA256,
    "output_type": "probability",
    "predictions": predictions,
}

return result
```

Si se necesita materializar el resultado como archivo para una prueba/manual demo:

```python
import json

with open("champion_output.json", "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
```

En integración normal con el backend, no es obligatorio escribir físicamente un archivo: el adapter puede recibir directamente el objeto Python y validarlo antes de exponerlo.

---

## 9. Validaciones automáticas mínimas

La implementación del modelo debería tener tests que comprueben como mínimo:

- JSON serializable;
- `reference_month` válido;
- exactamente Bucaramanga y Cali en el MVP;
- T+1 y T+2 presentes para ambas ciudades;
- exactamente 4 predicciones en el MVP;
- `target_month` correcto para cada horizonte;
- probability finita y dentro de `[0,1]`;
- threshold finito y dentro de `[0,1]`;
- `label` consistente con probability + threshold;
- no existen predicciones duplicadas por `(divipola, horizon)`;
- `feature_contract_version/hash` coinciden con el contrato utilizado por el artefacto;
- salida repetible para la misma entrada/artefacto cuando aplique.

---

## 10. Instrucciones AI First para Claude Code

Cuando una IA implemente la salida del Champion debe seguir este orden:

### Paso 1 — Inspeccionar antes de modificar

Leer y contrastar:

```text
model/xgb_clasico_meta.json
scripts/generate_predictions.py
scripts/train_clasico_model.py
scripts/calibrate_models.py
src/features/build_features.py
dashboard_prototipos/JSON-dashboard.md
```

Determinar explícitamente:

- artefacto T+1 real;
- artefacto T+2 real;
- método de carga;
- lista/orden de features;
- método real de predicción (`predict`, `predict_proba`, etc.);
- threshold real de cada horizonte;
- versión/hash que identificarán el artefacto.

### Paso 2 — No asumir

Si alguno de estos elementos no puede demostrarse desde el repositorio/artefacto:

```text
probability
threshold
modelo T+1
modelo T+2
model_version
```

la IA debe **detener esa parte de la implementación y reportar la brecha**, no rellenarla con valores arbitrarios.

### Paso 3 — Implementar la frontera

Crear una función o componente que transforme la salida nativa del modelo en el contrato de este documento.

Ejemplo conceptual:

```text
ChampionInput
→ modelo T+1/T+2
→ salida nativa
→ validación
→ ChampionResult
→ JSON
```

### Paso 4 — Probar

Agregar tests unitarios del contrato y una prueba con Bucaramanga/Cali.

### Paso 5 — Evidencia

Documentar:

- artefactos utilizados;
- hashes/versiones;
- threshold(s);
- método de inferencia;
- ejemplo de salida real;
- tests ejecutados;
- cualquier limitación.

---

## 11. Prompt sugerido para Claude Code

```text
Lee dashboard_prototipos/JSON-dashboard.md como fuente de verdad del contrato
modelo → backend de BIOMAC.

Antes de modificar código inspecciona los artefactos y scripts reales del modelo
para identificar los modelos T+1/T+2, su método de carga, feature contract,
probability y threshold reales.

Implementa una salida JSON compatible con ChampionResult sin inventar ningún
campo ML. Si probability, threshold, versión o algún horizonte no puede
comprobarse desde el artefacto/código, reporta la brecha y no generes un valor
por defecto.

El resultado del MVP debe contener exactamente Bucaramanga (68001) y Cali
(76001), cada una con T+1 y T+2, cuando ambos horizontes estén realmente
soportados.

Agrega validaciones/tests para:
- schema;
- serialización JSON;
- municipios;
- horizontes;
- target_month;
- probability;
- threshold;
- consistencia del label;
- duplicados;
- feature contract version/hash.

No implementes backend FastAPI, persistencia, dashboard, reentrenamiento ni
feature engineering como parte de esta tarea.
```

---

## 12. Definición de terminado

La integración del modelo está lista para ser consumida por BIOMAC cuando exista una prueba reproducible que produzca un objeto equivalente a:

```text
ChampionInput
→ Champion
→ ChampionResult válido
→ json.dumps(...)
```

para Bucaramanga y Cali, con T+1/T+2 reales, metadata trazable y sin valores ML inventados.

A partir de ese punto el backend puede implementar `ChampionAdapter` y mapear `ChampionResult` al `PredictionSnapshot` definido por la API BIOMAC.