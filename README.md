# SAT-Dengue Colombia 🦟

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi) ![XGBoost](https://img.shields.io/badge/XGBoost-2.0-orange) ![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker) ![DVC](https://img.shields.io/badge/DVC-3.x-945DD6?logo=dvc) ![MLflow](https://img.shields.io/badge/MLflow-2.x-0194E2?logo=mlflow)

Sistema de alerta temprana basado en inteligencia artificial para anticipar el exceso de casos de dengue a nivel municipal en Colombia con un horizonte de 4 a 8 semanas.

---

## Pregunta de negocio

> ¿Qué municipios presentan riesgo de experimentar un exceso de casos de dengue en las próximas 4 a 8 semanas, de manera que sea posible anticipar la ocurrencia de un brote y apoyar la toma oportuna de medidas preventivas?

---

## Contexto del problema

El dengue es una enfermedad endémica en Colombia con brotes recurrentes que afectan principalmente a los valles interandinos, la Costa Caribe y la Orinoquía. El país cuenta con el sistema de vigilancia epidemiológica SIVIGILA (Sistema Nacional de Vigilancia en Salud Pública), que registra semanalmente los casos notificados a nivel municipal desde 2007. La identificación tardía de un brote inminente reduce el margen disponible para desplegar acciones de control vectorial y preparar recursos hospitalarios, lo que convierte la anticipación en un problema de alto impacto para la salud pública.

## Solución propuesta

Se desarrolla un prototipo funcional de alerta temprana que integra:

1. **Modelo supervisado (XGBoost)** entrenado sobre variables epidemiológicas, climáticas y demográficas históricas para predecir el nivel de riesgo por municipio a 4–8 semanas.
2. **API de inferencia (FastAPI)** que expone las predicciones del modelo en tiempo real.
3. **Tablero interactivo** que consume la API y permite a las secretarías de salud identificar municipios en riesgo, visualizar el corredor endémico histórico y consultar indicadores de tendencia.
4. **Despliegue en contenedores Docker** para garantizar reproducibilidad y portabilidad.

---

## Fuentes de datos

| Fuente | Descripción | Período | Acceso |
|--------|-------------|---------|--------|
| SIVIGILA / INS | Casos confirmados de dengue por municipio, agregados mensualmente | 2007–2024 | Público — [datos.gov.co](https://www.datos.gov.co/dataset/Dengue/ke8u-qixu) |
| Google Earth Engine | Temperatura media y precipitación mensual por municipio | 2007–2024 | Requiere cuenta GEE con proyecto GCP |
| DANE | Población urbana y rural por municipio | 2005, 2018, proyecciones 2024 | Público — [dane.gov.co](https://www.dane.gov.co) |

---

## Metodología

### Definición de exceso de casos
Se define como **exceso de casos** cualquier semana epidemiológica en la que el número de casos de dengue en un municipio supere el **percentil 75 (P75)** de la distribución histórica de la misma semana, calculado sobre el período de referencia 2007–2019 (excluyendo años de epidemia mayor: 2010, 2013, 2016, 2019). Esta definición operacionaliza el **corredor endémico** estándar en la vigilancia epidemiológica latinoamericana (Bortman, 1999; INS Colombia, 2023).

### Alcance municipal
El análisis se restringe a **municipios endémicos**, definidos como aquellos con:
- Casos confirmados en **≥ 10 de los 18 años** del período 2007–2024, **y**
- **≥ 200 casos acumulados** en el mismo período.

Este criterio garantiza que el corredor endémico se construya sobre series históricas estadísticamente robustas y excluye municipios con transmisión esporádica o importada.

### Horizonte de pronóstico
**4 a 8 semanas** — umbral mínimo operativo para que las secretarías de salud municipales activen cadenas de respuesta institucional (control larvario, fumigación, gestión de recursos). Fuente metodológica: WHO/TDR (2012), Johansson et al. (2019 PNAS).

---

## Estructura del repositorio

```
microproyecto-tema3/
│
├── data/                   # Datos versionados con DVC (no en Git)
│   ├── raw/                # Datos descargados sin procesar
│   └── processed/          # Datos listos para modelado
│
├── notebooks/              # Análisis exploratorio y experimentación
│
├── src/                    # Código fuente del pipeline
│   ├── features/           # Construcción de variables y canal endémico
│   ├── models/             # Entrenamiento y evaluación de modelos
│   └── pipelines/          # Orquestación del pipeline completo
│
├── api/                    # API de inferencia con FastAPI
│   ├── main.py
│   └── requirements.txt
│
├── dashboard_prototipos/   # Mockup HTML del tablero (Entrega 1)
│
├── dashboard/              # Frontend generado con Lovable (Entregas 2–3)
│
├── docker/                 # Dockerfiles y docker-compose
│
├── .dvc/                   # Configuración de DVC
├── .dvcignore
│
├── mlruns/                 # Experimentos MLflow (ignorado en Git)
│
└── README.md
```

---

## Stack tecnológico

| Herramienta | Rol |
|-------------|-----|
| Python 3.11 | Lenguaje principal |
| XGBoost | Modelo de clasificación/regresión de riesgo |
| scikit-learn | Preprocesamiento, métricas, pipeline |
| pandas / numpy | Manipulación de datos |
| FastAPI + Uvicorn | API de inferencia REST |
| MLflow | Registro y comparación de experimentos |
| DVC | Versionamiento de datos y modelos |
| Docker / Compose | Contenedorización y despliegue |
| Lovable | Generación del frontend del tablero |
| Google Earth Engine | Extracción de variables climáticas |

---

## Equipo

| Nombre | Correo | Rol |
|--------|--------|-----|
| Stevan Ramírez Cajamarca | s.ramirezc2@uniandes.edu.co | Ingeniería de datos / DVC |
| Nicolás Steven Lara Villa | n.larav@uniandes.edu.co | Modelado / API |
| Jersson Mauricio Rodríguez Aponte | jm.rodrigueza1@uniandes.edu.co | Frontend / Infraestructura |
| Sergio Andrés Ballesteros Suárez | sa.ballesteros@uniandes.edu.co | EDA / Features |

**Experto de dominio:** Carlos Bravo Vega — ca.bravo955@uniandes.edu.co

**Curso:** Proyecto de Desarrollo de Soluciones — MAIA, Universidad de los Andes, 2026

---

## Cómo ejecutar

> ⚠️ Las instrucciones de ejecución se completarán una vez que los datos estén disponibles y el pipeline esté operativo (Entrega 2).

```bash
# Clonar el repositorio
git clone https://github.com/j-mauro-r/microproyecto-tema3.git
cd microproyecto-tema3

# Restaurar datos desde DVC remote
dvc pull

# Levantar la API (stub)
cd api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Ver documentación interactiva
# http://localhost:8000/docs
```

---

## Referencias clave

- Bortman, M. (1999). Elaboración de corredores o canales endémicos. *Rev Panam Salud Pública*, 5(1). https://doi.org/10.1590/S1020-49891999000100001
- INS Colombia. (2023). Protocolo de vigilancia — Dengue (v4). Ministerio de Salud y Protección Social.
- Johansson et al. (2019). An open challenge to advance probabilistic forecasting for dengue epidemics. *PNAS*, 116(48). https://doi.org/10.1073/pnas.1909865116
- WHO/TDR. (2012). Technical handbook for dengue surveillance. World Health Organization.

---

## Licencia

[MIT](LICENSE)
