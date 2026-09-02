# BIOMAC — Plan funcional del dashboard

**Estado:** especificación funcional objetivo  
**Versión:** `1.0.0`  
**Ámbito:** dashboard BIOMAC  
**Ruta:** `dashboard_prototipos/docs/plan.md`

> Este documento está escrito para ser legible tanto por personas como por agentes de IA. Debe utilizarse como fuente de verdad funcional para la evolución del dashboard, salvo que una decisión posterior del equipo la reemplace explícitamente.

---

## 1. Decisión de alcance vigente

BIOMAC **ya no pronosticará dengue grave como variable objetivo independiente**.

El alcance vigente es:

- pronosticar **riesgo de exceso de dengue en general**;
- utilizar información proveniente de **dengue clásico** y **dengue grave** como fuentes epidemiológicas de entrada;
- trabajar inicialmente con **Bucaramanga** y **Cali**;
- granularidad **mensual**;
- producir predicciones para **T+1** y **T+2**;
- salida principal: `EXCESO / NO_EXCESO` acompañada de probabilidad;
- el frontend no define el target, no calcula el canal endémico y no convierte probabilidades en clases: esos resultados deben provenir del pipeline/modelo/API.

### Regla importante para IA y desarrolladores

No asumir que `dengue_general = dengue_clasico + dengue_grave` salvo que el pipeline de datos lo formalice explícitamente. El contrato funcional exige recibir desde backend los valores epidemiológicos ya consolidados y metodológicamente válidos.

---

## 2. Convenciones de esta especificación

### Valores permitidos para `Estado actual`

- `EXISTE`: la funcionalidad está presente y es conceptualmente válida.
- `PARCIAL`: existe, pero requiere ajuste funcional, de datos o UX.
- `MOCK`: existe visualmente, pero usa datos simulados o incompletos.
- `PENDIENTE`: debe construirse.
- `CORREGIR`: existe, pero su comportamiento actual no debe mantenerse.
- `ELIMINAR`: debe retirarse porque genera información no soportada por el modelo.

### Valores permitidos para `Valor`

- `ALTO`: contribuye directamente a interpretar el riesgo, confiar en la predicción o tomar decisiones.
- `MEDIO`: aporta contexto, trazabilidad o usabilidad, pero no es central para decidir.

No se incluyen funcionalidades de valor bajo o elementos meramente decorativos.

---

## 3. Especificación funcional objetivo — 33 funcionalidades

| ID | Funcionalidad | Descripción y propósito | Estado actual | Valor |
|---|---|---|---|---|
| F01 | **Encabezado operacional** | Mostrar BIOMAC, objetivo `riesgo de exceso de dengue`, ciudades soportadas, granularidad mensual, horizontes T+1/T+2 y última actualización. Debe evitar ambigüedad sobre qué fenómeno y período está viendo el usuario. | PARCIAL | ALTO |
| F02 | **Selector de ciudad** | Permitir seleccionar Bucaramanga o Cali y actualizar de forma consistente todos los indicadores, gráficas, explicaciones y metadatos dependientes del municipio. | EXISTE | ALTO |
| F03 | **Fecha de corte epidemiológico** | Mostrar el último mes con datos observados realmente disponibles. Debe distinguirse de la fecha de ejecución del dashboard y de la fecha de inferencia. | PARCIAL | ALTO |
| F04 | **Calidad y frescura de datos** | Informar completitud, retrasos, datos parciales y advertencias relevantes de las fuentes epidemiológicas y climáticas usadas para la inferencia. Nunca ocultar una degradación importante de calidad. | PENDIENTE | ALTO |
| F05 | **Alerta principal T+2** | Responder de forma prioritaria si existe riesgo de `EXCESO` o `NO_EXCESO` en el segundo mes futuro para la ciudad seleccionada e indicar claramente el mes objetivo. | MOCK | ALTO |
| F06 | **Probabilidad T+2** | Mostrar la probabilidad producida por el modelo para el exceso en T+2. Debe provenir del backend y no ser calculada o modificada por el frontend. | MOCK | ALTO |
| F07 | **Incertidumbre del pronóstico** | Mostrar intervalo o rango de incertidumbre únicamente cuando exista un método estadístico válido que lo produzca. Si no existe, el campo debe omitirse o presentarse como no disponible; nunca simularlo. | MOCK | ALTO |
| F08 | **Evolución T+1 → T+2** | Permitir entender si el riesgo aumenta, disminuye o permanece estable entre los dos horizontes, mostrando probabilidad, clase y mes objetivo de cada predicción. | MOCK | ALTO |
| F09 | **Threshold real del modelo** | Mostrar o utilizar como referencia el umbral que convierte probabilidad en `EXCESO/NO_EXCESO`. Debe provenir del modelo/API y corresponder a la versión desplegada. | CORREGIR | ALTO |
| F10 | **Estado frente al canal endémico** | Mostrar situación epidemiológica actual: casos observados consolidados para el target vigente, P75 y relación respecto al P75. Los valores deben llegar calculados desde backend. | PARCIAL | ALTO |
| F11 | **Clasificación epidemiológica actual** | Traducir el canal endémico a una categoría comprensible, por ejemplo normal/endemia/alerta/exceso según la metodología oficial del proyecto. Describe el presente y no debe confundirse con la predicción futura. | PARCIAL | ALTO |
| F12 | **Comparativo Bucaramanga vs. Cali** | Mostrar en una vista compacta T+1, probabilidad T+1, T+2 y probabilidad T+2 para ambas ciudades, facilitando comparación y priorización territorial. | MOCK | ALTO |
| F13 | **Serie histórica + canal endémico** | Una única visualización con la serie observada de dengue usada por el proyecto, P25/P50/P75 y períodos históricos de exceso. Debe permitir entender cómo se llegó a la situación actual. | PARCIAL | ALTO |
| F14 | **Separación visual observado / futuro** | Marcar inequívocamente el último período observado y el comienzo de T+1/T+2. Ninguna predicción debe presentarse visualmente como observación real. | EXISTE | ALTO |
| F15 | **Eliminar pronóstico artificial de número de casos** | Retirar cualquier cálculo frontend que invente casos futuros a partir de probabilidades. Si el modelo es clasificador, el dashboard solo debe mostrar clase, probabilidad y otras salidas realmente producidas por backend. | ELIMINAR | ALTO |
| F16 | **Gráfica comparativa de probabilidad T+1/T+2** | Comparar visualmente las probabilidades de Bucaramanga y Cali para ambos horizontes e incluir el threshold real correspondiente. Debe facilitar identificar qué ciudad/horizonte está más cerca o por encima del umbral. | MOCK | ALTO |
| F17 | **Explicabilidad local de la predicción** | Mostrar los principales factores que explican una predicción concreta para una ciudad y horizonte. Si se denomina SHAP, los valores deben ser SHAP locales reales, incluyendo valor de feature y dirección del efecto. | MOCK | ALTO |
| F18 | **Impulsores epidemiológicos** | Dentro de la explicación local, mostrar rezagos, tendencias, medias móviles u otras variables derivadas de dengue clásico y dengue grave únicamente cuando el modelo demuestre que influyen en esa predicción. | MOCK | ALTO |
| F19 | **Impulsores climáticos** | Mostrar temperatura, precipitación, humedad u otras variables climáticas solo cuando estén disponibles, hayan sido usadas realmente por el modelo y contribuyan a la predicción. No crear una gráfica climática independiente sin propósito decisional. | MOCK | MEDIO |
| F20 | **Insights automáticos priorizados** | Generar máximo tres mensajes derivados de resultados reales, por ejemplo riesgo creciente, proximidad al P75 o principal impulsor. No repetir literalmente KPIs ni producir conclusiones no soportadas. | MOCK | ALTO |
| F21 | **Orientación de acción** | Traducir el nivel de riesgo en orientación no prescriptiva de apoyo a la decisión, por ejemplo mantener o reforzar vigilancia/preparación. Las reglas deben ser validadas por el equipo y, cuando aplique, por experto epidemiológico. | MOCK | ALTO |
| F22 | **Semántica consistente de alerta** | Utilizar categorías y señales visuales consistentes mediante texto + icono + color. El significado nunca debe depender exclusivamente del color y debe diferenciar estado actual de riesgo futuro. | PARCIAL | MEDIO |
| F23 | **Historial de pronósticos** | Conservar las predicciones generadas en cada corte mensual, incluyendo ciudad, mes de referencia, horizonte, probabilidad, clase, threshold y versión del modelo, para permitir auditoría posterior. | PENDIENTE | ALTO |
| F24 | **Pronosticado vs. ocurrido** | Comparar predicciones históricas con resultados posteriormente observados e identificar aciertos, falsas alarmas y excesos no detectados. Debe permitir evaluar utilidad operacional, no solo métricas de entrenamiento. | PENDIENTE | ALTO |
| F25 | **Desempeño del modelo** | Ofrecer una vista secundaria con métricas relevantes como Recall/Sensibilidad de EXCESO, Precision, F1, falsas alarmas y, si se define, detección de inicio. Debe incluir resultados específicos para Bucaramanga y Cali cuando estén disponibles. | PENDIENTE | MEDIO |
| F26 | **Trazabilidad del modelo** | Mostrar modelo/champion usado, versión, fecha de entrenamiento, fecha de inferencia, MLflow run o identificador equivalente y versión de datos. Permite explicar qué artefactos produjeron una alerta. | PENDIENTE | ALTO |
| F27 | **Fuente y procedencia de datos** | Identificar de forma compacta las fuentes utilizadas, incluyendo SIVIGILA para dengue clásico y dengue grave y las fuentes climáticas efectivamente incorporadas. Debe estar disponible como contexto, no dominar la pantalla principal. | PARCIAL | MEDIO |
| F28 | **Integración real API → modelo** | Sustituir mocks por inferencias reales servidas por FastAPI. Todos los resultados epidemiológicos y predictivos deben provenir del backend mediante un contrato versionado; los componentes visuales no deben conocer detalles del modelo. | PENDIENTE | ALTO |
| F29 | **Estados loading / error / empty / retry** | Manejar explícitamente carga, ausencia de datos, errores de API y reintentos. Ante un fallo no se deben mostrar mocks ni datos antiguos como si fueran una predicción vigente. | PARCIAL | ALTO |
| F30 | **Última inferencia exitosa** | Mostrar cuándo se generó exitosamente la última predicción y diferenciar esa fecha de la última observación epidemiológica. Permite detectar pipelines desactualizados aunque el dashboard esté disponible. | PENDIENTE | ALTO |
| F31 | **Exportar snapshot / reporte** | Permitir exportar un resumen PDF o CSV con ciudad, mes de referencia, T+1/T+2, probabilidades, canal endémico, explicación, calidad de datos y trazabilidad del modelo. | PENDIENTE | MEDIO |
| F32 | **Responsive y accesibilidad** | Garantizar uso correcto en portátil/tablet, contraste, etiquetas, tooltips comprensibles y señales que no dependan solo del color. | PARCIAL | MEDIO |
| F33 | **Selector de mes de referencia / modo histórico** | En pruebas, permitir seleccionar el mes considerado `Actual`. El backend debe usar únicamente información disponible hasta ese corte y producir T+1/T+2. Esto habilita backtesting visual. En producción, el último corte válido debe ser el valor por defecto, manteniendo la posibilidad de consultar cortes históricos. | PENDIENTE | ALTO |

---

## 4. Flujo funcional objetivo

```text
Usuario selecciona ciudad
        |
        +--> En pruebas: selecciona mes de referencia
        |    En producción: se propone el último corte válido
        v
Dashboard solicita inferencia
        v
FastAPI valida solicitud
        v
Backend recupera únicamente datos disponibles hasta el mes de referencia
        |
        +--> dengue clásico
        +--> dengue grave
        +--> clima disponible
        +--> features derivadas/versionadas
        v
Modelo(s) T+1 / T+2
        v
Backend produce resultados consolidados
        |
        +--> EXCESO / NO_EXCESO
        +--> probabilidad
        +--> threshold
        +--> canal endémico
        +--> calidad de datos
        +--> explicación local, si existe
        +--> trazabilidad
        v
Dashboard presenta información sin recalcular resultados epidemiológicos
```

---

## 5. Preguntas que la pantalla principal debe responder

La pantalla principal debe permitir responder, en este orden conceptual:

1. **¿Qué ciudad y corte temporal estoy analizando?**
2. **¿Cuál es el estado epidemiológico observado actualmente?**
3. **¿Existe riesgo de exceso en T+1 y T+2?**
4. **¿Qué probabilidad y threshold sustentan la alerta?**
5. **¿Por qué el modelo produjo esa predicción?**
6. **¿Qué debería revisar o preparar el usuario?**
7. **¿Qué tan confiables y frescos son los datos y el modelo usados?**

---

## 6. Elementos que NO deben agregarse por defecto

- Un mapa mientras el alcance operativo sea únicamente Bucaramanga y Cali; el comparativo directo aporta más valor en esta escala.
- Una gráfica climática independiente si el clima no explica una decisión concreta.
- Predicciones de número de casos si el modelo desplegado solo clasifica exceso/no exceso.
- KPIs redundantes que repitan la misma probabilidad o clase con distinto formato.
- Métricas técnicas de infraestructura en la pantalla epidemiológica principal.
- SHAP simulado o importancia global presentada como explicación local.
- Datos mock mezclados con datos reales sin una etiqueta inequívoca de modo demostración.

---

## 7. Dependencias críticas para pasar de mock a datos reales

Antes de sustituir completamente los mocks, el backend/modelado debe garantizar:

1. una definición única y versionada del target `exceso de dengue general`;
2. targets/modelos o estrategia de inferencia explícitamente evaluada para `T+1` y `T+2`;
3. features reproducibles construidas sin data leakage respecto al mes de referencia;
4. threshold versionado y coherente con el modelo desplegado;
5. métricas globales y específicas para Bucaramanga y Cali;
6. datos climáticos con cobertura suficiente antes de atribuirles efecto;
7. explicabilidad local real si el dashboard utiliza la etiqueta `SHAP`;
8. persistencia de inferencias si se habilitan F23 y F24;
9. metadata de modelo, datos e inferencia consumible por API;
10. contrato FastAPI compatible con esta especificación funcional.

---

## 8. Relación con `API-sign.md`

`API-sign.md` define el contrato técnico Dashboard ↔ FastAPI. Este `plan.md` define **qué debe ofrecer funcionalmente el dashboard**.

Cuando exista una diferencia entre ambos documentos por un cambio posterior de alcance, primero debe resolverse la decisión funcional y después actualizarse el contrato API para mantener consistencia.

**Nota de alcance:** el contrato API creado inicialmente utilizaba `dengue grave` como target. Debido a la decisión vigente de pronosticar `dengue en general` utilizando dengue clásico y dengue grave como fuentes de información, `API-sign.md` deberá alinearse con esta nueva definición antes de implementar la integración real.
