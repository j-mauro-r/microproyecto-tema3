# Guion del video — SAT-Dengue · Entrega 3

**Duración objetivo:** ≤ 10 minutos  
**Narración:** cada sección asignada a un integrante  

---

## [0:00 – 0:30] Apertura *(Nicolás)*

> "Somos el Grupo 11 de MAIA — Sergio Ballesteros, Stevan Ramírez, Mauricio Rodríguez y Nicolás Lara. Este video presenta SAT-Dengue, un sistema de alerta temprana de brotes de dengue en Colombia. En los próximos diez minutos vamos a mostrar el problema que resolvemos, los modelos que evaluamos, el sistema funcionando en producción local y los resultados que obtuvimos."

---

## [0:30 – 1:45] Problema y arquitectura *(Mauricio)*

> "Las Secretarías de Salud de Cali y Bucaramanga detectan brotes de dengue de forma reactiva, cuando los casos ya superaron el canal endémico. SAT-Dengue clasifica mensualmente el riesgo de exceso para T+1 y T+2, es decir, el mes siguiente y el subsiguiente al corte de datos disponible."

**Mostrar en pantalla:** diagrama de arquitectura del sistema.

> "El pipeline tiene cuatro componentes: un panel municipio-mes con datos de SIVIGILA y ERA5/CHIRPS, una API REST en FastAPI, un tablero React, y un ciclo de reentrenamiento gestionado por MLflow. Todo corre en contenedores Docker."

---

## [1:45 – 3:30] Despliegue local con Docker *(Sergio)*

**Compartir pantalla:** terminal (Ubuntu/WSL2 o Linux), raíz del repositorio.

> "Vamos a levantar el sistema desde cero. Estamos en la raíz del repositorio clonado."

```bash
make up
```

> "El comando verifica si Docker está instalado, lo instala si falta, construye las dos imágenes y levanta los servicios. La API queda en `localhost:8001` y el dashboard en `localhost:3000`."

```bash
docker compose ps
curl http://localhost:8001/api/v2/health
```

> "El health endpoint confirma que la API está activa. Ahora abrimos el dashboard."

**Abrir** `http://localhost:3000` en el browser.

---

## [3:30 – 5:30] Demo del dashboard — carga mensual y predicciones *(Nicolás)*

> "El sistema arranca sin datos. Vamos a cargar el archivo de diciembre de 2025, que viene incluido en el repositorio como ejemplo reproducible."

1. Clic en **Actualizar datos**.
2. Seleccionar `tutorial/carga_mensual_2025-12.csv`.
3. Seleccionar mes de referencia: **diciembre 2025**.
4. **Confirmar actualización** → mostrar "COMPLETED" + Run ID.

> "El procesamiento tomó unos segundos. Ahora vemos las predicciones para Bucaramanga: T+1 y T+2 con su probabilidad calibrada, el umbral de decisión y la etiqueta EXCESO o NO_EXCESO."

**Cambiar a Cali.** Mostrar canal endémico (P25, P75, zona). Mostrar panel de trazabilidad (Champion, versión, Run ID).

> "El dashboard solo lee lo que devuelve la API, no inventa valores. Todo lo que aparece aquí tiene trazabilidad directa al run de MLflow que lo produjo."

---

## [5:30 – 7:30] Modelos y evaluación *(Stevan)*

**Mostrar:** MLflow o tabla comparativa del reporte.

> "Entrenamos y comparamos seis modelos: XGBoost, LightGBM, GAM, regresión de Poisson y dos baselines epidemiológicos: persistencia y canal endémico de Bortman."

> "La métrica que decide no es F1 global sino la sensibilidad en inicios de brote, que es lo que le importa a una Secretaría de Salud. En T+1, XGBoost y LightGBM alcanzan F1 de 0,965 frente a 0,951 del canal endémico, pero los tres modelos detectan los mismos 2 de 3 inicios. Este es el hallazgo central: la ventaja en F1 viene de acertar continuaciones, no inicios."

> "Con dos municipios y tres transiciones en ocho años no hay estadística suficiente para demostrar superioridad sobre el canal. Eso motiva ampliar el alcance a los 523 municipios endémicos del país en la siguiente entrega."

> "El Champion seleccionado es XGBoost con calibración Platt, porque es el único modelo validado de extremo a extremo contra el contrato de 39 features. LightGBM queda como candidato alternativo para T+2."

---

## [7:30 – 9:15] Repositorio y entregables *(Mauricio)*

**Mostrar:** repositorio en GitHub (`j-mauro-r/microproyecto-tema3`).

> "El repositorio incluye: el código de la API con tests unitarios e integración, el código del dashboard, los dos Dockerfiles y el Compose, el panel versionado con DVC, los experimentos registrados en MLflow, y los manuales de instalación y usuario."

**Mostrar brevemente:** `docker/api.Dockerfile`, `docker-compose.yml`, `tutorial/`.

> "Cualquier persona puede reproducir el sistema completo con `git clone` y `make up`, sin instalar Python, Node ni configurar credenciales de nube."

---

## [9:15 – 10:00] Conclusiones *(Sergio)*

> "SAT-Dengue demuestra un prototipo funcional, desplegable y trazable. El resultado de evaluación es honesto: no podemos afirmar que el modelo supera al canal endémico en la métrica que más importa, y lo reportamos así. La siguiente fase extiende el sistema a 523 municipios, donde el número de inicios crece en tres órdenes de magnitud y la comparación se vuelve estadísticamente válida. Gracias."

---

## Notas de edición

- Si la compilación de Docker en `make up` es lenta, hacer un corte y mostrar el resultado ya construido. El tiempo objetivo baja a ~8 minutos con ese corte.
- La captura del dashboard debe mostrar simultáneamente predicción, canal endémico y trazabilidad (sección 3.4 del reporte).
- Publicar en padlet con acceso abierto antes de la entrega.
