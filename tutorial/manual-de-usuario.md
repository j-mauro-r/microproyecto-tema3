# Manual de usuario del dashboard BIOMAC

## 1. Objetivo del dashboard

BIOMAC presenta alertas tempranas sobre la posibilidad de un exceso de casos de dengue en Bucaramanga y Cali para los dos meses siguientes al corte analizado.

El dashboard permite:

- consultar las predicciones de cada ciudad;
- comparar la probabilidad con el umbral de decisión del modelo;
- revisar información del canal endémico y de calidad de los datos;
- identificar el modelo y el proceso que generaron los resultados;
- cargar el archivo mensual que inicia una nueva actualización.

Las predicciones apoyan la preparación y el seguimiento. No sustituyen la valoración de las autoridades de salud ni demuestran que una variable sea la causa de un resultado.

## 2. Acceso al dashboard

Este manual supone que la instalación local ya terminó y que los servicios están funcionando.

1. Abra un navegador web.
2. Ingrese a [http://localhost:3000](http://localhost:3000).
3. Espere mientras aparece el mensaje **Cargando predicciones…**.

Si ya existe una actualización completada, se mostrará la vista principal. Si aún no hay predicciones, aparecerá la pantalla **Sin predicciones**, desde la cual puede cargar el primer periodo mensual.

[imagen-pantalla-sin-predicciones-con-botones-reintentar-y-actualizar-datos]

## 3. Descripción general de la interfaz

La vista principal contiene:

1. El encabezado **BIOMAC — Sistema de alerta temprana de dengue**.
2. El corte de los datos y el nombre y la versión del **Champion**.
3. Los botones **Actualizar vista** y **Actualizar datos**.
4. La fecha de generación y el identificador del **Run**.
5. El panel **Metadata y trazabilidad**.
6. Los botones **Bucaramanga** y **Cali**.
7. Las tarjetas de predicción **T+1** y **T+2**.
8. Los paneles **Canal endémico**, **Explicabilidad** y **Calidad de datos**.
9. El **Historial de predicciones**.

[imagen-vista-general-del-dashboard-con-las-secciones-principales]

## 4. Consultar las predicciones por ciudad

Al abrir el dashboard, **Bucaramanga** está seleccionada de forma predeterminada.

1. Seleccione **Bucaramanga** o **Cali**.
2. Revise las tarjetas **T+1** y **T+2** de la ciudad elegida.
3. Consulte los paneles inferiores. El **Canal endémico** cambia con la ciudad seleccionada.

El botón activo aparece resaltado. Cambiar de ciudad no procesa datos nuevos: solo muestra la información ya disponible para esa ciudad.

[imagen-selector-de-ciudad-bucaramanga-y-cali]

Si aparece **No hay predicciones persistidas para esta ciudad**, la última actualización no contiene resultados para la ciudad seleccionada.

## 5. Interpretar T+1, T+2 y el mes objetivo

- **T+1** es la predicción para el primer mes posterior al mes de referencia.
- **T+2** es la predicción para el segundo mes posterior al mes de referencia.
- El mes que acompaña a cada título es el **mes objetivo** de esa predicción.

Por ejemplo, para un corte de diciembre de 2025, T+1 corresponde a enero de 2026 y T+2 a febrero de 2026.

Cada horizonte tiene su propia probabilidad, su propio resultado y su propio threshold. Deben interpretarse por separado.

[imagen-predicciones-t1-y-t2-con-probabilidad-y-threshold]

## 6. Interpretar los resultados de una predicción

### EXCESO y NO_EXCESO

- **EXCESO** indica que la probabilidad calculada es igual o superior al threshold de ese horizonte.
- **NO_EXCESO** indica que la probabilidad es inferior al threshold.

Estas etiquetas son resultados del modelo para el mes objetivo; no representan por sí solas una confirmación de casos observados.

### Probabilidad

La **Probabilidad** expresa la estimación de exceso y se muestra como porcentaje. Un valor mayor representa una estimación más alta, pero la etiqueta final depende de su comparación con el threshold correspondiente.

### Threshold

El **Threshold** es el umbral usado para asignar **EXCESO** o **NO_EXCESO**. La interfaz lo muestra como un número decimal entre 0 y 1, mientras que la probabilidad se presenta como porcentaje.

Ejemplo de lectura: un threshold de `0.34` equivale a 34 %. Este ejemplo explica el formato y no anticipa el resultado que verá el usuario.

### Casos esperados y Risk score

Las tarjetas también incluyen **Casos esperados** y **Risk score**. El Champion vigente produce probabilidades, por lo que estos campos pueden aparecer como **No disponible**. No deben estimarse a partir de la probabilidad.

### Información no disponible

Si la API no entrega un valor, el dashboard muestra **No disponible** o **Información no disponible**. Esto no equivale a cero.

## 7. Champion, versión y Run

En la parte superior se muestra **Champion** seguido del nombre y la versión del modelo que generó la predicción vigente.

El panel **Metadata y trazabilidad** presenta:

- **Output**: tipo de resultado producido por el modelo; en el Champion local vigente es una probabilidad.
- **Feature contract**: versión del conjunto de datos que el modelo espera recibir.
- **Run**: identificador del procesamiento mensual que produjo la vista.

El mismo Run aparece junto a la fecha de actualización. Úselo para distinguir una ejecución de otra cuando reporte un problema o compare el historial.

[imagen-encabezado-y-panel-de-metadata-con-champion-version-y-run]

## 8. Actualizar la vista

Use **Actualizar vista** para volver a consultar la última predicción completada.

1. Seleccione **Actualizar vista**.
2. Mientras se realiza la consulta, el botón muestra **Actualizando…**.
3. Al terminar, revise el corte, la fecha y el Run mostrados.

Esta acción no carga archivos ni genera un procesamiento mensual.

Si la consulta falla y ya había una predicción visible, el dashboard conserva esa última predicción y muestra el aviso **No se pudo actualizar la vista. Se conserva la última predicción válida.** Puede seleccionar **Reintentar**.

[imagen-aviso-de-error-al-actualizar-con-ultima-prediccion-conservada]

## 9. Actualizar los datos mensuales

Use **Actualizar datos** para enviar un archivo mensual a validación y procesamiento.

El entorno local vigente incluye un flujo reproducible para diciembre de 2025:

- archivo: `tutorial/carga_mensual_2025-12.csv`;
- mes de referencia: diciembre de 2025 (`2025-12`).

El archivo debe conservar la estructura del CSV de ejemplo. La validación vigente exige:

- formato CSV y codificación UTF-8;
- un tamaño máximo de 10 MB con la configuración local predeterminada;
- exactamente una fila para Bucaramanga, con código `68001`, y una para Cali, con código `76001`;
- valores de año y mes iguales al mes de referencia seleccionado;
- todas las columnas requeridas del archivo de ejemplo;
- valores numéricos válidos, finitos y no vacíos en las 39 variables requeridas;
- ausencia de columnas objetivo o resultados futuros no permitidos.

No cambie nombres de columnas ni agregue municipios. Si prepara un archivo propio, use el archivo de ejemplo como plantilla.

### Cargar el archivo y seleccionar el mes

1. Seleccione **Actualizar datos**.
2. En la ventana **Actualizar periodo mensual**, ubique **Archivo mensual CSV**.
3. Seleccione `tutorial/carga_mensual_2025-12.csv`.
4. En **Mes de referencia**, elija diciembre de 2025.
5. Seleccione **Confirmar actualización**.

[imagen-modal-actualizar-periodo-mensual-con-archivo-y-mes-de-referencia]

El mes de referencia describe el periodo contenido en las filas del archivo. No es el mes T+1 ni el mes T+2.

### Confirmar el procesamiento

Después de seleccionar **Confirmar actualización**, el navegador pregunta:

> ¿Actualizar BIOMAC con [nombre del archivo] para [mes de referencia]?

- Acepte para iniciar el procesamiento.
- Cancele para volver a la ventana sin enviar el archivo.

Mientras se procesa, el botón muestra **Procesando…** y permanece deshabilitado.

Cuando termina correctamente, aparece **Actualización completada**, seguida del Run, el mes de referencia y el estado **COMPLETED**. La ventana permanece abierta y el dashboard vuelve a consultar la última predicción y el historial.

[imagen-confirmacion-de-actualizacion-completada-con-run-mes-y-estado]

## 10. Calidad de datos

El panel **Calidad de datos** muestra:

- **Estado**: resultado general de la validación registrada para la actualización.
- **Último mes observado**: periodo de los datos procesados.
- avisos adicionales: precisiones o limitaciones que deben considerarse al leer el resultado.

En el flujo local vigente, el estado puede mostrarse como `complete` cuando las 39 variables requeridas superan la validación. Aun así, puede aparecer un aviso indicando que la completitud separada de los grupos epidemiológico y climático no está calculada. Un aviso no debe ocultarse ni interpretarse como un dato adicional.

Si la actualización no contiene información de calidad, aparece **Información de calidad no disponible**.

[imagen-panel-calidad-de-datos-con-estado-mes-y-aviso]

## 11. Canal endémico

El panel **Canal endémico** corresponde a la ciudad seleccionada y puede mostrar:

- **Casos observados**: casos registrados para el periodo, si están disponibles.
- **P25**, **P50** y **P75**: valores de referencia del canal endémico recibidos por el dashboard.
- **Zona**: valor de zona entregado en el archivo mensual.

En el flujo vigente, P25, P75 y Zona proceden del CSV cargado. **Casos observados** y P50 pueden mostrarse como **No disponible**; no deben interpretarse como cero ni calcularse manualmente desde otros campos.

La interfaz muestra el valor de **Zona** tal como fue recibido y no incluye una leyenda que traduzca sus códigos. Por ello, el manual no asigna nombres epidemiológicos a esos valores.

Si no existe contexto para la ciudad, aparece **Información de contexto no disponible**.

[imagen-panel-canal-endemico-de-la-ciudad-seleccionada]

## 12. Explicabilidad

Debajo de cada predicción puede aparecer una explicación local con las variables que más contribuyeron al resultado. Una contribución positiva impulsa el resultado del modelo en sentido positivo y una negativa en sentido contrario; no demuestra causalidad.

El panel **Explicabilidad** recuerda esta limitación. En la configuración local vigente no se cargan artefactos de explicación, por lo que normalmente se muestra **Explicación local no disponible para esta predicción.**

[imagen-mensaje-de-explicacion-local-no-disponible-en-una-prediccion]

## 13. Historial de predicciones

El panel **Historial de predicciones** lista hasta 12 actualizaciones completadas. Cada línea muestra:

- el mes de referencia;
- el identificador del Run.

La lista sirve para comprobar qué procesamientos quedaron registrados. Los elementos no son botones y no permiten abrir ni restaurar una predicción anterior.

Si no hay registros disponibles, aparece **No hay historial de predicciones disponible**.

[imagen-historial-de-predicciones-con-mes-y-run]

## 14. Mensajes y errores frecuentes

### No fue posible conectar con BIOMAC API

El dashboard no pudo comunicarse con el servicio que entrega y procesa los datos. Seleccione **Reintentar**. Si el mensaje continúa, solicite apoyo a la persona responsable de la instalación local.

### Aún no hay predicciones disponibles

Todavía no existe una actualización mensual completada. Use **Actualizar datos** y siga el procedimiento de este manual.

### Selecciona un archivo CSV válido

No se eligió un archivo o su nombre no termina en `.csv`. Seleccione el archivo mensual correcto.

### Selecciona un mes válido

No se eligió el mes de referencia. Selecciónelo antes de confirmar.

### El archivo está vacío o no contiene registros

El CSV no contiene datos procesables. Use un archivo completo con encabezado y las dos filas requeridas.

### Faltan columnas requeridas / el archivo contiene columnas prohibidas

La estructura no coincide con el contrato vigente. Compare el encabezado con `tutorial/carga_mensual_2025-12.csv` y no agregue columnas de resultados futuros.

### Todas las filas deben coincidir exactamente con reference_month

El año o el mes de una fila no coincide con **Mes de referencia**. Corrija el archivo o la selección del mes.

### El archivo debe contener exactamente Bucaramanga y Cali

Falta una de las ciudades, hay una ciudad adicional o hay más de dos filas. Incluya una sola fila con `68001` y una sola fila con `76001`.

### Las features requeridas deben ser numéricas, finitas y no nulas

Una o más variables contienen texto, un valor vacío o un número no válido. Corrija las columnas indicadas por el mensaje y vuelva a intentarlo.

### El contexto no corresponde al provider Champion configurado

El periodo seleccionado no coincide con el artefacto Champion disponible en el entorno local actual. Use el archivo incluido para diciembre de 2025 con el mes `2025-12`.

### BIOMAC API no pudo completar la solicitud / Ocurrió un error interno inesperado

El procesamiento no terminó. La última predicción válida se conserva. Puede usar **Reintentar** en la ventana; si vuelve a fallar, conserve el Run visible y solicite apoyo a la persona responsable de la instalación.

## 15. Buenas prácticas de uso

- Confirme siempre la ciudad, el corte y el mes objetivo antes de interpretar una alerta.
- Lea T+1 y T+2 por separado; sus probabilidades y thresholds pueden ser distintos.
- Compare la probabilidad con el threshold del mismo horizonte.
- No interprete **No disponible** como cero.
- Use el CSV de ejemplo como plantilla y no modifique sus encabezados.
- Verifique que el mes elegido coincida con el año y el mes de todas las filas.
- Espere el mensaje **Actualización completada** antes de cerrar la ventana.
- Anote el Run cuando necesite comunicar o revisar un resultado.
- Considere los avisos de calidad y las limitaciones de explicabilidad.
- Use las predicciones como apoyo para la toma de decisiones, junto con el análisis epidemiológico correspondiente.
