# BIOMAC — Plan funcional del dashboard

**Estado:** especificación funcional objetivo  
**Versión:** `1.3.0`  
**Ámbito:** dashboard BIOMAC

> Fuente de verdad funcional. Debe mantenerse alineada con `API-sign.md`, con las salidas reales del pipeline/modelo y con la implementación visual del dashboard.

## 1. Alcance vigente

BIOMAC estima **riesgo de exceso de dengue** para Bucaramanga y Cali, con granularidad mensual y horizontes T+1/T+2.

Definición vigente del pipeline:
- `casos_clasico` es la serie objetivo;
- `casos_grave` es predictor epidemiológico;
- las dos series **no se suman**;
- la clase es `EXCESO / NO_EXCESO`;
- el frontend no calcula features, canal, clase ni thresholds.

La UI debe presentar únicamente salidas reales del modelo. Si el champion produce una probabilidad calibrada, puede mostrarse como porcentaje; si produce otro tipo de salida, debe mostrarse con su unidad explícita. Nunca se deben fabricar probabilidades, conteos, SHAP o thresholds en frontend.

## 2. Convenciones

Estados funcionales: `EXISTE`, `PARCIAL`, `MOCK`, `PENDIENTE`, `CORREGIR`, `ELIMINAR`.  
Valor: `ALTO`, `MEDIO`.

Cobertura visual:
- `PRESENTE — PRINCIPAL`: ya aparece gráficamente en la pantalla principal.
- `PRESENTE — MEJORAR`: existe gráficamente, pero debe corregirse o completarse.
- `AGREGAR — PRINCIPAL`: falta y debe incorporarse en la pantalla principal.
- `AGREGAR — MENÚ: HISTÓRICO`: debe vivir en una vista secundaria de histórico/evaluación.
- `AGREGAR — MENÚ: MODELO Y DATOS`: debe vivir en una vista secundaria de trazabilidad, calidad y fuentes.
- `NO VISUAL — INFRAESTRUCTURA`: requisito técnico que habilita la UI, pero no necesita un panel permanente.

Módulos de navegación:
- `PANTALLA PRINCIPAL`: Alerta y pronóstico; concentra la decisión epidemiológica.
- `HISTÓRICO Y EVALUACIÓN`: seguimiento de predicciones anteriores y contraste contra lo ocurrido.
- `MODELO Y DATOS`: calidad, fuentes, trazabilidad, desempeño e infraestructura analítica.

## 3. Especificación funcional objetivo — 33 funcionalidades

| ID | Funcionalidad | Descripción y propósito | Estado actual | Valor | Cobertura visual / ubicación objetivo | Módulo |
|---|---|---|---|---|---|---|
| F01 | Encabezado operacional | Objetivo, ciudad, corte, granularidad, T+1/T+2 y actualización. | PARCIAL | ALTO | **PRESENTE — MEJORAR.** Ya existe encabezado y última actualización, pero aún dice “dengue grave” y debe mostrar el alcance canónico. | **PANTALLA PRINCIPAL** |
| F02 | Selector de ciudad | Bucaramanga/Cali actualizando toda la vista. | EXISTE | ALTO | **PRESENTE — PRINCIPAL.** Selector visible en la parte superior. | **PANTALLA PRINCIPAL** |
| F03 | Fecha de corte epidemiológico | Último mes observado usado en la inferencia. | PARCIAL | ALTO | **AGREGAR — PRINCIPAL.** Debe verse junto al selector/encabezado como “Datos hasta YYYY-MM”. | **PANTALLA PRINCIPAL** |
| F04 | Calidad y frescura | Completitud, retrasos y advertencias de SIVIGILA/clima. | PENDIENTE | ALTO | **AGREGAR — PRINCIPAL + detalle en MENÚ: MODELO Y DATOS.** En principal basta un estado compacto; el detalle va en módulo secundario. | **MODELO Y DATOS** |
| F05 | Alerta principal T+2 | `EXCESO/NO_EXCESO`, ciudad y mes objetivo; clase desde backend. | MOCK | ALTO | **PRESENTE — PRINCIPAL.** Existe tarjeta de alerta T+2. Debe cambiar de mock a salida real. | **PANTALLA PRINCIPAL** |
| F06 | Señal cuantitativa T+2 | Probabilidad válida u otra salida cuantitativa real del champion. | CORREGIR | ALTO | **PRESENTE — MEJORAR.** Existe tarjeta de probabilidad T+2; debe consumir la señal real y no asumir siempre probabilidad. | **PANTALLA PRINCIPAL** |
| F07 | Incertidumbre | Solo si existe método estadístico válido. | MOCK | ALTO | **PRESENTE — MEJORAR.** La tarjeta ya reserva espacio para IC 95%; debe mostrarse únicamente cuando backend entregue incertidumbre real. | **PANTALLA PRINCIPAL** |
| F08 | Evolución T+1→T+2 | Comparar clase, mes y salida real de ambos horizontes. | MOCK | ALTO | **PRESENTE — PRINCIPAL.** La tarjeta de señal muestra tendencia T+1→T+2 y el comparativo también expone ambos horizontes. | **PANTALLA PRINCIPAL** |
| F09 | Regla/threshold real | Threshold probabilístico o regla de decisión versionada. | CORREGIR | ALTO | **PRESENTE — MEJORAR.** La gráfica muestra referencia de 50%, pero hoy está hardcodeada; debe venir del backend. | **PANTALLA PRINCIPAL** |
| F10 | Estado frente al canal | Casos actuales, P75 y relación respecto al P75. | PARCIAL | ALTO | **PRESENTE — PRINCIPAL.** Existe tarjeta “Estado vs. canal endémico”. | **PANTALLA PRINCIPAL** |
| F11 | Clasificación actual | Zona epidemiológica actual, separada de la predicción. | PARCIAL | ALTO | **PRESENTE — MEJORAR.** La tarjeta del canal ya muestra una descripción/semántica; debe formalizar zona actual con datos reales. | **PANTALLA PRINCIPAL** |
| F12 | Comparativo de ciudades | T+1/T+2, clase y señal de riesgo para Bucaramanga/Cali. | MOCK | ALTO | **PRESENTE — PRINCIPAL.** Existe tabla comparativa interactiva de ambas ciudades. | **PANTALLA PRINCIPAL** |
| F13 | Histórico + canal endémico | Serie target + P25/P50/P75 + excesos históricos. | PARCIAL | ALTO | **PRESENTE — PRINCIPAL.** La gráfica actual ya incluye observados, P25, P50, P75 y excesos históricos. | **PANTALLA PRINCIPAL** |
| F14 | Observado vs futuro | Separación visual inequívoca entre historia y T+1/T+2. | EXISTE | ALTO | **PRESENTE — PRINCIPAL.** La gráfica sombrea la zona futura y marca el inicio del pronóstico. | **PANTALLA PRINCIPAL** |
| F15 | Eliminar proyección artificial | No inventar casos en frontend; mostrar conteo solo si lo produce backend. | ELIMINAR | ALTO | **PRESENTE — INCORRECTA; ELIMINAR.** La gráfica calcula actualmente `projected` a partir de probabilidad. Debe retirarse salvo que backend entregue conteo real. | **PANTALLA PRINCIPAL** |
| F16 | Gráfica comparativa de riesgo | Comparar outputs reales T+1/T+2 con unidad explícita. | CORREGIR | ALTO | **PRESENTE — MEJORAR.** Existe gráfica de barras T+1/T+2 por ciudad; debe usar output y threshold reales. | **PANTALLA PRINCIPAL** |
| F17 | Explicabilidad local | Factores de una inferencia concreta; SHAP solo si es SHAP local real. | MOCK | ALTO | **PRESENTE — MEJORAR.** Existe gráfica titulada SHAP, pero hoy representa importancia agregada; debe mostrar explicación local de ciudad + corte + horizonte. | **PANTALLA PRINCIPAL** |
| F18 | Impulsores epidemiológicos | Rezagos, rolling, SIR, canal, dengue grave, solo si explicación válida. | MOCK | ALTO | **PRESENTE — MEJORAR.** Pueden mostrarse dentro de la misma visual de explicabilidad; no crear una gráfica redundante. | **PANTALLA PRINCIPAL** |
| F19 | Impulsores climáticos | Mostrar clima solo si fue usado y contribuye a la inferencia. | MOCK | MEDIO | **PRESENTE — MEJORAR.** Deben aparecer dentro de la explicación cuando tengan contribución real; no crear panel climático independiente. | **PANTALLA PRINCIPAL** |
| F20 | Insights priorizados | Máximo tres mensajes derivados de resultados reales. | MOCK | ALTO | **PRESENTE — PRINCIPAL.** Existe panel de hasta tres insights; reemplazar mocks por reglas/resultados reales. | **PANTALLA PRINCIPAL** |
| F21 | Orientación de acción | Apoyo no prescriptivo validado por equipo/experto. | MOCK | ALTO | **PRESENTE — PRINCIPAL.** Existe tarjeta de recomendación dentro de “Insights y recomendaciones”. Debe validarse y alimentarse con reglas reales. | **PANTALLA PRINCIPAL** |
| F22 | Semántica de alerta | Texto + icono + color, diferenciando actual de futuro. | PARCIAL | MEDIO | **PRESENTE — PRINCIPAL.** Ya se usan texto, iconos, puntos y colores. Debe mantenerse accesible y coherente con estados reales. | **PANTALLA PRINCIPAL** |
| F23 | Historial de pronósticos | Persistir corte, horizonte, clase, output, regla y modelo. | PENDIENTE | ALTO | **AGREGAR — MENÚ: HISTÓRICO.** No debe ocupar la pantalla principal; requiere tabla/línea temporal de predicciones realizadas. | **HISTÓRICO Y EVALUACIÓN** |
| F24 | Pronosticado vs ocurrido | Aciertos, falsas alarmas y excesos omitidos. | PENDIENTE | ALTO | **AGREGAR — MENÚ: HISTÓRICO.** Vista de validación operacional vinculada al historial. | **HISTÓRICO Y EVALUACIÓN** |
| F25 | Desempeño del modelo | Recall, Precision, F1, falsas alarmas e inicios; por ciudad si es defendible. | PENDIENTE | MEDIO | **AGREGAR — MENÚ: MODELO Y DATOS.** Mantener fuera de la pantalla epidemiológica principal para no sobrecargarla. | **MODELO Y DATOS** |
| F26 | Trazabilidad | Champion por horizonte, versión, MLflow, fechas y versión DVC. | PENDIENTE | ALTO | **AGREGAR — MENÚ: MODELO Y DATOS.** En principal puede mostrarse solo una versión compacta; detalle completo en módulo secundario. | **MODELO Y DATOS** |
| F27 | Procedencia de datos | Clásico como target, grave como predictor y clima realmente usado. | PARCIAL | MEDIO | **AGREGAR — MENÚ: MODELO Y DATOS.** Fuente, corte y rol de cada dataset deben estar documentados en una vista secundaria. | **MODELO Y DATOS** |
| F28 | API → modelo real | FastAPI + artefactos finales desplegables T+1/T+2. | PENDIENTE | ALTO | **NO VISUAL — INFRAESTRUCTURA.** Habilita todas las salidas reales; no necesita un panel permanente. | **MODELO Y DATOS** |
| F29 | Loading/error/empty/retry | Estados explícitos; nunca mock como fallback silencioso. | PARCIAL | ALTO | **PRESENTE — MEJORAR.** Ya existe loading; faltan error, empty y retry en la pantalla principal. | **PANTALLA PRINCIPAL** |
| F30 | Última inferencia exitosa | Fecha/hora de inferencia distinta al corte epidemiológico. | PENDIENTE | ALTO | **AGREGAR — PRINCIPAL.** Mostrar de forma compacta cerca de “Última actualización”; detalle en trazabilidad. | **PANTALLA PRINCIPAL** |
| F31 | Exportar snapshot/reporte | PDF/CSV con resultados, canal, calidad y trazabilidad. | PENDIENTE | MEDIO | **AGREGAR — PRINCIPAL.** Acción/botón de exportación; no requiere módulo propio. | **PANTALLA PRINCIPAL** |
| F32 | Responsive/accesibilidad | Portátil/tablet, contraste, etiquetas y significado no dependiente de color. | PARCIAL | MEDIO | **PRESENTE — MEJORAR.** La implementación ya usa grids responsive y texto/iconos; falta auditoría completa de accesibilidad. | **PANTALLA PRINCIPAL** |
| F33 | Mes de referencia / histórico | Seleccionar `Actual`; backend usa solo datos hasta ese corte y genera T+1/T+2. | PENDIENTE | ALTO | **AGREGAR — PRINCIPAL.** Selector de mes junto al selector de ciudad; en producción debe iniciar en el último corte válido. | **PANTALLA PRINCIPAL** |

## 4. Distribución funcional por módulo

### Pantalla principal — Alerta y pronóstico

F01, F02, F03, F05, F06, F07, F08, F09, F10, F11, F12, F13, F14, F15, F16, F17, F18, F19, F20, F21, F22, F29, F30, F31, F32, F33.

La pantalla principal concentra contexto, estado actual, predicción, comparación, explicación y orientación de acción. Debe seguir siendo una pantalla de decisión y no una consola técnica.

### Histórico y evaluación

F23, F24.

Este módulo responde qué predijo BIOMAC anteriormente y qué ocurrió después.

### Modelo y datos

F04, F25, F26, F27, F28.

Este módulo agrupa calidad/frescura detallada, desempeño, trazabilidad, fuentes y estado de la integración técnica. F04 puede exponer además un indicador compacto en la pantalla principal, pero su módulo propietario es `Modelo y datos`.

## 5. Auditoría de la implementación visual actual

La pantalla principal actual ya contiene: encabezado, selector de ciudad, alerta T+2, probabilidad T+2 con tendencia contra T+1, estado frente al canal, comparativo Bucaramanga/Cali, histórico con canal endémico, separación observado/futuro, gráfica de riesgo T+1/T+2, visual de importancia/SHAP, insights y recomendación.

La arquitectura visual debe conservar una pantalla principal enfocada en decisión. No se deben trasladar a ella métricas detalladas de modelado, historial completo ni metadata técnica extensa.

### Menú objetivo mínimo

```text
BIOMAC
├── Alerta y pronóstico        ← PANTALLA PRINCIPAL
├── Histórico y evaluación
└── Modelo y datos
```

F31 debe ser una acción de exportación disponible desde la pantalla principal. F28 es infraestructura y se clasifica en `Modelo y datos` únicamente para mantener una ubicación funcional clara dentro de la arquitectura del producto; no requiere un panel permanente.

## 6. Flujo funcional objetivo

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
+ output nativo válido
+ regla/threshold
+ canal endémico
+ calidad
+ explicación local si existe
+ trazabilidad
        ↓
Dashboard presenta sin recalcular
```

## 7. Preguntas de la pantalla principal

1. ¿Qué ciudad y corte estoy analizando?
2. ¿Cuál es el estado actual?
3. ¿Hay riesgo de exceso en T+1/T+2?
4. ¿Qué salida y regla sustentan la alerta?
5. ¿Por qué se produjo, si existe explicación válida?
6. ¿Qué debería revisar/preparar?
7. ¿Qué tan frescos son los datos y cuándo se ejecutó la inferencia?

## 8. No agregar por defecto

- mapa con solo dos ciudades;
- clima sin propósito decisional;
- probabilidades simuladas;
- `risk_score` presentado como porcentaje si no es probabilidad;
- casos futuros inventados por frontend;
- SHAP simulado o coeficientes/importancias globales presentados como explicación local;
- métricas técnicas/modelado detalladas en la pantalla principal;
- KPIs redundantes;
- datos mock mezclados con reales sin identificación.

## 9. Dependencias para datos reales

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

## 10. Decisiones que la UI no debe inventar

- champion definitivo;
- output real de cada champion;
- threshold/regla de decisión;
- método de incertidumbre;
- método de explicación local;
- política final de acciones;
- suficiencia estadística de métricas por ciudad.

## 11. Relación con API

- `plan.md`: comportamiento funcional y ubicación visual.
- `API-sign.md`: interfaz técnica Dashboard ↔ FastAPI.
- pipeline/modelo: salidas realmente disponibles.

Si cambia target, output, regla de decisión o estructura de navegación, deben revisarse este plan y el contrato API antes de modificar la UI.
