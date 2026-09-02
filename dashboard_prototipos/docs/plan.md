# BIOMAC — Plan funcional del dashboard

**Estado:** especificación funcional objetivo  
**Versión:** `2.0.0`  
**Ámbito:** dashboard BIOMAC + flujo operacional de actualización mensual  
**Arquitectura:** `arquitectura.md`

## 1. Alcance vigente

BIOMAC presenta riesgo de exceso de dengue para Bucaramanga (`68001`) y Cali (`76001`), con granularidad mensual y horizontes T+1/T+2.

Definiciones vigentes documentadas:
- `casos_clasico` es la serie objetivo;
- `casos_grave` es predictor epidemiológico;
- no se suman;
- clase `EXCESO / NO_EXCESO`;
- el frontend no calcula features, canal, clase, threshold, probabilidad ni SHAP.

### Nueva decisión operacional

La inferencia se dispara cuando un analista carga un **nuevo periodo mensual válido**.

```text
Actualizar datos
→ API
→ validación/preparación
→ Champion aprobado
→ persistencia
→ dashboard
```

Abrir el dashboard o presionar `Refresh` consulta la última predicción persistida y **no ejecuta el Champion**.

El entrenamiento, tuning, comparación, selección y promoción del Champion permanecen fuera del alcance de este plan.

## 2. Módulos

- **ALERTA Y PRONÓSTICO:** pantalla principal de decisión.
- **HISTÓRICO Y EVALUACIÓN:** predicciones anteriores y contraste posterior.
- **MODELO Y DATOS:** calidad, fuentes, Champion y trazabilidad.
- **ACTUALIZACIÓN MENSUAL:** flujo iniciado desde una acción compacta `Actualizar datos`; puede implementarse como modal/panel y no requiere una pantalla principal adicional en el MVP.

## 3. Estados funcionales

`EXISTE`, `PARCIAL`, `MOCK`, `PENDIENTE`, `CORREGIR`, `ELIMINAR`.

Valor: `ALTO`, `MEDIO`.

## 4. Especificación funcional objetivo — 37 funcionalidades

| ID | Funcionalidad | Propósito | Estado | Valor | Ubicación |
|---|---|---|---|---|---|
| F01 | Encabezado operacional | Ciudad, corte, alcance, granularidad, horizontes y actualización. | PARCIAL | ALTO | Principal |
| F02 | Selector de ciudad | Bucaramanga/Cali actualizando la vista. | EXISTE | ALTO | Principal |
| F03 | Fecha de corte | Mostrar último mes observado usado. | PARCIAL | ALTO | Principal |
| F04 | Calidad y frescura | Completitud, retrasos y warnings. | PENDIENTE | ALTO | Principal compacto + Modelo y datos |
| F05 | Alerta principal T+2 | Clase real del Champion/backend. | MOCK | ALTO | Principal |
| F06 | Señal cuantitativa T+2 | Output nativo válido; probabilidad solo si aplica. | CORREGIR | ALTO | Principal |
| F07 | Incertidumbre | Mostrar solo si existe método válido. | MOCK | ALTO | Principal |
| F08 | Evolución T+1→T+2 | Comparar ambos horizontes reales. | MOCK | ALTO | Principal |
| F09 | Regla/threshold | Regla real y versionada. | CORREGIR | ALTO | Principal |
| F10 | Estado frente al canal | Casos actuales, P75 y relación. | PARCIAL | ALTO | Principal |
| F11 | Clasificación actual | Zona epidemiológica actual separada de predicción. | PARCIAL | ALTO | Principal |
| F12 | Comparativo de ciudades | T+1/T+2 para Bucaramanga/Cali. | MOCK | ALTO | Principal |
| F13 | Histórico + canal | Observados + percentiles disponibles + excesos. | PARCIAL | ALTO | Principal |
| F14 | Observado vs futuro | Separar historia de T+1/T+2. | EXISTE | ALTO | Principal |
| F15 | Eliminar proyección artificial | No inventar casos futuros desde probabilidad. | ELIMINAR | ALTO | Principal |
| F16 | Comparativa de riesgo | Comparar output real y regla por horizonte/ciudad. | CORREGIR | ALTO | Principal |
| F17 | Explicabilidad local | Explicar inferencia concreta cuando exista. | MOCK | ALTO | Principal |
| F18 | Impulsores epidemiológicos | Mostrar factores epidemiológicos reales. | MOCK | ALTO | Principal |
| F19 | Impulsores climáticos | Mostrar clima solo si fue usado y contribuye. | MOCK | MEDIO | Principal |
| F20 | Insights priorizados | Máximo tres mensajes derivados de resultados reales. | MOCK | ALTO | Principal |
| F21 | Orientación de acción | Apoyo no prescriptivo, separado del modelo. | MOCK | ALTO | Principal |
| F22 | Semántica de alerta | Texto+icono+color; actual vs futuro. | PARCIAL | MEDIO | Principal |
| F23 | Historial de pronósticos | Runs/snapshots previos persistidos. | PENDIENTE | ALTO | Histórico y evaluación |
| F24 | Pronosticado vs ocurrido | Aciertos, falsas alarmas y omisiones cuando haya observación. | PENDIENTE | ALTO | Histórico y evaluación |
| F25 | Desempeño del modelo | Métricas recibidas/validadas del Champion. | PENDIENTE | MEDIO | Modelo y datos |
| F26 | Trazabilidad | Champion, versión, run MLflow si existe, fechas y dato fuente. | PENDIENTE | ALTO | Modelo y datos |
| F27 | Procedencia de datos | Rol de clásico, grave y clima realmente usado. | PARCIAL | MEDIO | Modelo y datos |
| F28 | API → Champion | Integración real desacoplada mediante adapter. | PENDIENTE | ALTO | Infraestructura |
| F29 | Loading/error/empty/retry | Estados explícitos; nunca mock silencioso. | PARCIAL | ALTO | Principal/actualización |
| F30 | Última inferencia exitosa | Fecha/hora diferente del corte epidemiológico. | PENDIENTE | ALTO | Principal |
| F31 | Exportar snapshot | PDF/CSV con resultado y trazabilidad. | PENDIENTE | MEDIO | Principal |
| F32 | Responsive/accesibilidad | Contraste, etiquetas y uso sin depender del color. | PARCIAL | MEDIO | Principal |
| F33 | Mes de referencia | Mostrar/seleccionar corte soportado para consulta histórica. | PENDIENTE | ALTO | Principal/Historico |
| F34 | Actualizar datos | Acción explícita para cargar nuevo archivo mensual. | PENDIENTE | ALTO | Header/modal |
| F35 | Validación de carga | Mostrar validación, periodo, errores y confirmación antes de inferir. | PENDIENTE | ALTO | Actualización mensual |
| F36 | Estado de procesamiento | Mostrar procesamiento/éxito/fallo y `run_id`. | PENDIENTE | ALTO | Actualización mensual |
| F37 | Refresh read-only | Reconsultar `latest` sin ejecutar preparación ni Champion. | PENDIENTE | ALTO | Principal |

## 5. Pantalla principal

Debe responder:
1. ¿qué ciudad y corte estoy analizando?;
2. ¿cuál es el estado actual?;
3. ¿hay riesgo de exceso T+1/T+2?;
4. ¿qué salida/regla sustenta la alerta?;
5. ¿qué factores la explican, si existe explicación válida?;
6. ¿qué debería revisar/preparar?;
7. ¿cuándo se actualizó la información y cuál fue la última inferencia?;
8. ¿puedo actualizar los datos mensuales o refrescar solo la consulta?

La acción `Actualizar datos` debe estar separada visual y semánticamente de `Refresh`.

## 6. Flujo de actualización mensual

```text
Analista pulsa Actualizar datos
        ↓
Selecciona archivo + reference_month
        ↓
Dashboard confirma y envía
        ↓
POST /api/v2/monthly-runs
        ↓
VALIDATING → PREPARING → INFERENCING → PERSISTING
        ↓
COMPLETED
        ↓
Dashboard muestra resultado / consulta GET latest
```

Ante `FAILED`:
- se informa etapa/error;
- no se cambia silenciosamente a mocks;
- se conserva el último snapshot exitoso.

## 7. Flujo de consulta

```text
Abrir dashboard / Refresh
        ↓
GET /api/v2/predictions/latest
        ↓
Último snapshot COMPLETED
        ↓
Render UI
```

Este flujo es estrictamente read-only.

## 8. Reglas para el Champion

El producto recibe del equipo de modelado:
- artefacto ejecutable o salida materializada;
- nombre/versión;
- contrato de entrada/features;
- horizontes soportados;
- tipo de output;
- threshold/regla;
- explicación local si existe.

La capa dashboard/API no selecciona ni reentrena el Champion.

## 9. No agregar por defecto

- mapa para solo dos ciudades;
- panel climático independiente sin propósito decisional;
- probabilidades simuladas;
- score mostrado como porcentaje cuando no sea probabilidad;
- casos futuros inventados;
- SHAP simulado;
- métricas detalladas de modelado en la principal;
- botón `Refresh` que dispare inferencia;
- reentrenamiento desde la UI;
- reemplazo silencioso de una predicción válida por un run fallido.

## 10. Dependencias para implementación real

1. Champion explícito y accesible.
2. Contrato de entrada/features del Champion.
3. T+1/T+2 realmente soportados.
4. Output y regla/threshold documentados.
5. Transformaciones de inferencia reutilizables sin leakage.
6. Canal endémico reproducible si lo requiere la UI/regla.
7. Persistencia de runs/snapshots.
8. Contrato `API-sign.md` v2.0.0.
9. `PredictionRepository` y `ChampionAdapter` desacoplados.
10. Pruebas de contrato y E2E.

## 11. Fuente de verdad

- `arquitectura.md`: flujo y responsabilidades.
- `implementacion.md`: HUs y orden de ejecución.
- `plan.md`: comportamiento funcional/visual.
- `API-sign.md`: contrato HTTP.
- `diccionario-de-datos.md`: semántica de datos.
- Champion: salidas ML realmente disponibles.