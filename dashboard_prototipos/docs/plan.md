# BIOMAC — Plan funcional del dashboard

**Estado:** especificación funcional objetivo  
**Versión:** `1.1.0`  
**Ámbito:** dashboard BIOMAC

> Fuente de verdad funcional. Debe mantenerse alineada con `API-sign.md` y con las salidas reales del pipeline/modelo.

## 1. Alcance vigente

BIOMAC estima **riesgo de exceso de dengue** para Bucaramanga y Cali, con granularidad mensual y horizontes T+1/T+2.

Definición vigente del pipeline:
- `casos_clasico` es la serie objetivo;
- `casos_grave` es predictor epidemiológico;
- las dos series **no se suman**;
- la clase es `EXCESO / NO_EXCESO`;
- el frontend no calcula features, canal, clase ni thresholds.

La especificación ya no presupone que todo modelo entregue probabilidad. El Poisson actual produce **conteo esperado** y una regla frente al P75. La UI debe soportar `expected_cases`, `probability` cuando sea válida y `risk_score` sin presentarlo como porcentaje.

## 2. Convenciones

Estados: `EXISTE`, `PARCIAL`, `MOCK`, `PENDIENTE`, `CORREGIR`, `ELIMINAR`.  
Valor: `ALTO`, `MEDIO`.

## 3. Especificación funcional objetivo — 33 funcionalidades

| ID | Funcionalidad | Descripción y propósito | Estado actual | Valor |
|---|---|---|---|---|
| F01 | Encabezado operacional | Objetivo, ciudad, corte, granularidad, T+1/T+2 y actualización. | PARCIAL | ALTO |
| F02 | Selector de ciudad | Bucaramanga/Cali actualizando toda la vista. | EXISTE | ALTO |
| F03 | Fecha de corte epidemiológico | Último mes observado usado en la inferencia. | PARCIAL | ALTO |
| F04 | Calidad y frescura | Completitud, retrasos y advertencias de SIVIGILA/clima. | PENDIENTE | ALTO |
| F05 | Alerta principal T+2 | `EXCESO/NO_EXCESO`, ciudad y mes objetivo; clase desde backend. | MOCK | ALTO |
| F06 | Señal cuantitativa T+2 | Probabilidad si existe; en Poisson, conteo esperado y score frente al P75. | CORREGIR | ALTO |
| F07 | Incertidumbre | Solo si existe método estadístico válido. | MOCK | ALTO |
| F08 | Evolución T+1→T+2 | Comparar clase, mes y salida real de ambos horizontes. | MOCK | ALTO |
| F09 | Regla/threshold real | Para Poisson `k × P75`; para clasificador, threshold probabilístico. | CORREGIR | ALTO |
| F10 | Estado frente al canal | Casos actuales, P75 y relación respecto al P75. | PARCIAL | ALTO |
| F11 | Clasificación actual | Zona epidemiológica actual, separada de la predicción. | PARCIAL | ALTO |
| F12 | Comparativo de ciudades | T+1/T+2, clase y señal de riesgo para Bucaramanga/Cali. | MOCK | ALTO |
| F13 | Histórico + canal endémico | Serie target + P25/P50/P75 + excesos históricos. | PARCIAL | ALTO |
| F14 | Observado vs futuro | Separación visual inequívoca entre historia y T+1/T+2. | EXISTE | ALTO |
| F15 | Eliminar proyección artificial | No inventar casos en frontend; mostrar conteo solo si lo produce backend. | ELIMINAR | ALTO |
| F16 | Gráfica comparativa de riesgo | Comparar outputs reales T+1/T+2 con unidad explícita. | CORREGIR | ALTO |
| F17 | Explicabilidad local | Factores de una inferencia concreta; SHAP solo si es SHAP local real. | MOCK | ALTO |
| F18 | Impulsores epidemiológicos | Rezagos, rolling, SIR, canal, dengue grave, solo si explicación válida. | MOCK | ALTO |
| F19 | Impulsores climáticos | Mostrar clima solo si fue usado y contribuye a la inferencia. | MOCK | MEDIO |
| F20 | Insights priorizados | Máximo tres mensajes derivados de resultados reales. | MOCK | ALTO |
| F21 | Orientación de acción | Apoyo no prescriptivo validado por equipo/experto. | MOCK | ALTO |
| F22 | Semántica de alerta | Texto + icono + color, diferenciando actual de futuro. | PARCIAL | MEDIO |
| F23 | Historial de pronósticos | Persistir corte, horizonte, clase, output, regla y modelo. | PENDIENTE | ALTO |
| F24 | Pronosticado vs ocurrido | Aciertos, falsas alarmas y excesos omitidos. | PENDIENTE | ALTO |
| F25 | Desempeño del modelo | Recall, Precision, F1, falsas alarmas e inicios; por ciudad si es defendible. | PENDIENTE | MEDIO |
| F26 | Trazabilidad | Champion por horizonte, versión, MLflow, fechas y versión DVC. | PENDIENTE | ALTO |
| F27 | Procedencia de datos | Clásico como target, grave como predictor y clima realmente usado. | PARCIAL | MEDIO |
| F28 | API → modelo real | FastAPI + artefactos finales desplegables T+1/T+2. | PENDIENTE | ALTO |
| F29 | Loading/error/empty/retry | Estados explícitos; nunca mock como fallback silencioso. | PARCIAL | ALTO |
| F30 | Última inferencia exitosa | Fecha/hora de inferencia distinta al corte epidemiológico. | PENDIENTE | ALTO |
| F31 | Exportar snapshot/reporte | PDF/CSV con resultados, canal, calidad y trazabilidad. | PENDIENTE | MEDIO |
| F32 | Responsive/accesibilidad | Portátil/tablet, contraste, etiquetas y significado no dependiente de color. | PARCIAL | MEDIO |
| F33 | Mes de referencia / histórico | Seleccionar `Actual`; backend usa solo datos hasta ese corte y genera T+1/T+2. | PENDIENTE | ALTO |

## 4. Flujo funcional objetivo

```text
Ciudad + mes de referencia
        ↓
FastAPI valida request
        ↓
Datos disponibles hasta t
  ├─ casos_clasico → target vigente
  ├─ casos_grave   → predictor
  └─ clima         → predictor si disponible
        ↓
Features reproducibles sin leakage
        ↓
Modelo final T+1 / T+2
        ↓
EXCESO/NO_EXCESO
+ output nativo (expected_cases o probability)
+ risk_score si aplica
+ regla/threshold
+ canal endémico
+ calidad
+ explicación local si existe
+ trazabilidad
        ↓
Dashboard presenta sin recalcular
```

## 5. Preguntas de la pantalla principal

1. ¿Qué ciudad y corte estoy analizando?
2. ¿Cuál es el estado actual?
3. ¿Hay riesgo de exceso en T+1/T+2?
4. ¿Qué salida y regla sustentan la alerta?
5. ¿Por qué se produjo, si existe explicación válida?
6. ¿Qué debería revisar/preparar?
7. ¿Qué tan frescos y trazables son datos/modelos?

## 6. No agregar por defecto

- mapa con solo dos ciudades;
- clima sin propósito decisional;
- probabilidades simuladas;
- `risk_score` mostrado como porcentaje;
- casos futuros inventados por frontend;
- SHAP simulado o coeficientes globales como explicación local;
- KPIs redundantes;
- datos mock mezclados con reales sin identificación.

## 7. Dependencias para datos reales

1. Target versionado: `casos_clasico`; `casos_grave` predictor; sin suma.
2. Artefactos finales desplegables/evaluados T+1 y T+2.
3. Champion explícito por horizonte.
4. Features sin leakage.
5. Canal reproducible con P25/P50/P75.
6. Regla de decisión versionada.
7. Métricas globales y por ciudad cuando sean defendibles.
8. Clima con cobertura suficiente antes de atribuir efecto.
9. Probabilidad solo si es una salida válida.
10. Explicación local válida para F17–F19.
11. Persistencia de inferencias para F23/F24.
12. Metadata de modelo/datos/inferencia.
13. DVC alineado con datos procesados.
14. Contrato FastAPI `API-sign.md` v1.1.0 o compatible.

## 8. Decisiones pendientes que la UI no debe inventar

- champion definitivo;
- permanencia o reemplazo de Poisson;
- disponibilidad de probabilidad válida;
- método de incertidumbre;
- método de explicación local;
- política final de acciones;
- suficiencia estadística de métricas por ciudad.

## 9. Relación con API

- `plan.md`: comportamiento funcional.
- `API-sign.md`: interfaz técnica Dashboard ↔ FastAPI.
- pipeline/modelo: salidas realmente disponibles.

Si cambia target, output o regla de decisión, deben actualizarse ambos documentos antes de modificar la UI.
