# Pipeline de datos y modelado

Sistema de alerta temprana de dengue para Bucaramanga (68001) y Cali (76001).

---

## Flujo

```
Kaggle: saballesteros/maia4331-2614-grupo19
   dengue.csv               1.705.604 casos de dengue clasico, 2007-2025
   dengue_grave.csv            50.101 casos de dengue grave, 2007-2025
   google_earth_engine.csv  7.751.898 filas de clima diario por municipio
        |
        |  data/download_datasets.py
        v
   data/raw/                          ~2,6 GB, no se versiona en Git
        |
        |  src/data/build_panel.py
        v
   data/processed/panel_mensual.parquet          20 MB
   una fila por municipio y mes, 253.992 filas, 1.114 municipios, 2007-2025
        |
        |  src/features/build_features.py
        v
   data/processed/features_mensual.parquet       35 MB
   el mismo panel mas 40 variables predictoras y la etiqueta de brote
        |
        |  src/models/baseline.py   y los modelos que vengan
        v
   metricas comparables entre modelos
```

Cada capa lee la anterior. Ninguna vuelve a los crudos.

## Como se corre

```bash
pip install -r requirements.txt
python data/download_datasets.py          # necesita .env con las credenciales de Kaggle
python -m src.data.build_panel            # --sample 50000 para una prueba de 20 segundos
python -m src.features.build_features
python -m src.models.baseline

python -m tests.test_evaluation
python -m tests.test_features
```

## Estructura

| Ruta | Que hace |
|---|---|
| `src/data/build_panel.py` | Crudos a panel mensual completo |
| `src/features/build_features.py` | Panel a variables de modelado y etiqueta |
| `src/evaluation/splits.py` | Particion temporal y folds de validacion cruzada |
| `src/evaluation/metrics.py` | Metricas de alerta, iguales para todos los modelos |
| `src/models/baseline.py` | Los cuatro baselines de referencia |
| `tests/` | Verificacion de los modulos compartidos, sin dependencias adicionales |

---

## Decisiones tomadas

### El municipio se identifica con el DIVIPOLA de cinco digitos

`COD_MUN_O` es el consecutivo dentro del departamento, no una llave. El codigo `001` lo comparten 33 municipios, entre ellos **Cali (76001) y Bucaramanga (68001)**, que son justamente los dos del alcance. La llave es `COD_DPTO_O` de dos digitos mas `COD_MUN_O` de tres.

### La fecha es la de inicio de sintomas

Se usa `INI_SIN` con respaldo en `FEC_NOT`, siguiendo la indicacion del profesor: es cuando la persona enfermo y no depende del retraso del sistema de vigilancia.

Las fechas vienen como `16/09/2007 12:00:00 a. m.` en formato dia/mes/anio, y se parsean con `format="%d/%m/%Y"` explicito. Sin declarar el formato, pandas no logra inferirlo por el `" a. m."` del final, cae a `dateutil` y asume mes/dia: toda fecha con dia menor o igual a 12, alrededor del 39% de los registros, queda con el mes cambiado.

Efecto de usar `INI_SIN`: se descartan 237 casos con sintomas iniciados en 2006 y notificados en 2007. Hay 133 registros con `INI_SIN` vacio que entran por el respaldo.

### Se excluyen los registros que no corresponden a un municipio

`COD_DPTO_O = 01` significa EXTERIOR, y en ese caso `COD_MUN_O` guarda el codigo ISO del pais de origen:

| Codigo | Casos | Origen |
|---|---|---|
| `01862` | 2.211 | Venezuela |
| `01076` | 302 | Brasil |
| `01000` | 150 | Exterior, pais desconocido |
| `01604` | 91 | Peru |
| `01484` | 69 | Mexico |
| `01218` | 57 | Ecuador |

`COD_DPTO_O = 00` es PROCEDENCIA DESCONOCIDA, 889 casos. Se comprueba en las columnas `Departamento_ocurrencia` y `Municipio_ocurrencia`, que dicen `EXTERIOR | EXTERIOR_VENEZUELA` y `PROCEDENCIA DESCONOCIDA`.

Son casos importados, no transmision local. Si se dejan, aparecen como 67 municipios inexistentes y 14.472 filas sin clima. Filtrandolos, la cobertura del cruce climatico sube de 90,8% a 96,3%.

### El panel se arma completo

Todos los municipios por todos los meses de 2007 a 2025, con cero donde no hubo casos. Dos razones:

Los percentiles del canal endemico se calculan sobre todos los meses. Si solo existieran las filas con casos, el P25 y el P75 quedarian inflados y el canal alertaria menos de lo debido.

Los rezagos son meses calendario. Con filas faltantes, `shift(1)` devuelve la fila anterior que exista, que puede ser de hace cuatro meses.

### Cruce climatico por codigo

`google_earth_engine.csv` (ERA5-Land y CHIRPS) trae `mpio_cdpmp` con el DIVIPOLA completo, asi que el cruce va por codigo. El archivo anterior, de MODIS, traia codigos GAUL de la FAO y obligaba a cruzar por nombre de municipio, perdiendo alrededor del 20%. El pipeline detecta cual de los dos formatos recibe y avisa si es el viejo.

### El objetivo es dengue total

`SERIE_OBJETIVO = "casos_clasico"`. Se cambio desde dengue grave el 1 de septiembre, por decision de equipo, porque la serie de graves quedo inservible despues del cambio de clasificacion de la OMS de 2009 (ver Limitaciones).

### Encuadre: cada fila predice el futuro, no el presente

Cada fila es un municipio y un mes t. Las variables son todo lo que se conoce al cerrar ese mes, y la etiqueta es si habra brote en **t + HORIZONTE**.

```
fila      = (municipio, mes t)
variables = casos, clima, canal y estacionalidad hasta el mes t
objetivo  = brote en el mes t + HORIZONTE
```

Mover el horizonte es cambiar una constante o pasar `--horizonte 3`. El encuadre anterior tenia las variables rezagadas y la etiqueta en el mes de la fila, lo que obligaba a rezagar variable por variable para mover la anticipacion.

Dos consecuencias de este encuadre. El clima del mes en curso deja de ser trampa: si se predice t+1 parado en t, ese clima ya se conoce. Y `casos_clasico` del mes en curso pasa a ser variable legitima, no etiqueta.

### Etiqueta de brote

Un mes es brote si los casos de ese municipio y ese mes superan el **P75 historico del mismo mes**. Es la zona de epidemia del canal endemico.

| Columna | Que es |
|---|---|
| `brote` | el mes de la fila esta por encima del P75. Es **variable**, no etiqueta |
| `objetivo` | si habra brote en t + HORIZONTE. Es la **etiqueta** |
| `es_inicio` | el mes objetivo arranca el brote, o sea que el anterior no lo era |
| `p75_objetivo` | el umbral del mes que se predice |
| `zona_objetivo` | en que zona del umbral **del mes objetivo** caen los casos de hoy |

`es_inicio` no es predictora: depende del mes objetivo. Sirve para separar, al evaluar, la deteccion de inicios de la de continuaciones.

`zona_objetivo` existe porque el canal es estacional. Bucaramanga tiene P75 de 158 en diciembre y 378 en julio: estar en 300 casos es epidemia en uno y normal en el otro. La pregunta util no es "estoy por encima del umbral de este mes" sino "con lo que llevo hoy, cruzo el umbral del mes que viene". Sin esa distincion, el baseline del canal y el de persistencia son la misma regla.

P75 mensual con referencia 2007-2022:

```
Bucaramanga     219  244  320  366  315  340  378  283  309  268  232  158
Cali            838 1146 1580 1192  952  758  652  667  506  480  513  586
```

### Municipio endemico

Criterio de `Decisiones_Metodologicas`: al menos **diez anios con casos y doscientos casos acumulados**, sobre la serie de dengue clasico, dentro de la ventana de referencia. Da **523 municipios de 1.114**.

El documento estimaba entre 120 y 150; el EDA del equipo obtuvo 621 sobre una ventana mas larga y sin filtrar el exterior. El criterio escrito da 523, no el rango estimado.

La PR #8 usaba tres meses con casos y cincuenta acumulados sobre la serie de graves. Se cambio al criterio del documento para que el codigo y la memoria metodologica digan lo mismo.

### Particion temporal

```
entrenamiento : 2007 - 2022    con validacion cruzada de ventana expansiva
prueba        : 2023 - 2025    se evalua una sola vez, al final
```

La particion va sobre **`anio_objetivo`**, el mes que se predice, no sobre el mes de la fila. Con horizonte de un mes, la fila de diciembre de 2022 predice enero de 2023, que es prueba: particionar por el mes de la fila dejaria esa etiqueta del lado del entrenamiento.

No hay un anio fijo de validacion. Los hiperparametros se escogen con `folds_temporales`: cada fold entrena con todos los anios anteriores y valida sobre uno solo, avanzando de 2015 a 2022.

La razon es concreta: **2008, 2011, 2017, 2018, 2021 y 2022 no tienen ni un mes por encima del canal** en Bucaramanga ni en Cali. Un anio suelto de validacion puede quedarse sin positivos y dejar la seleccion de hiperparametros sin nada que medir. Los folds vacios igual sirven, porque miden falsas alarmas.

La prueba cubre tres anios a proposito: 2023 de subida (126.411 casos de clasico), 2024 de epidemia (309.627, el maximo de la serie) y 2025 de descenso (120.564). Con un solo anio epidemico, un modelo que alerta siempre saldria bien.

### Cada fold recalcula su propia referencia

El canal, el SIR, la endemicidad y la etiqueta dependen de la ventana de referencia, y se recalculan por fold con `aplicar_referencia(df, ref_fin=anio - 1)`.

Sin eso hay fuga: un P75 calculado hasta 2022 y usado para validar 2015 ya vio ocho anios de futuro, y como la etiqueta es `casos > p75`, la contaminacion alcanza tambien a la etiqueta. El archivo de variables trae esas columnas calculadas hasta 2022, que es correcto para la prueba (2023-2025) pero seria fuga dentro de la validacion cruzada.

Al recalcular por fold hay que pasar los meses del anio validado aunque no se evaluen, porque la etiqueta sale de correr el brote hacia adelante: sin ellos, la ultima fila de cada municipio se queda sin objetivo y el fold pierde observaciones en silencio.

`tests/test_features.py::test_nada_ve_el_futuro` es la red general. Corrompe **todas** las columnas numericas posteriores a un corte y exige que ninguna de las predictoras cambie en las filas anteriores, ni la etiqueta cuando el mes objetivo es anterior, mas la contraprueba de que despues del corte si cambian. No verifica columnas por nombre: verifica el invariante, asi que cubre sola cualquier variable que se agregue despues.

### Metricas

No se usa exactitud como criterio. En los folds los meses por encima del canal son el 14,1%, asi que un modelo que nunca alerta acierta el 86% sin detectar un solo brote.

Las que deciden son sensibilidad, precision, tasa de falsas alarmas y PR-AUC, mas dos desgloses: por municipio, y separando inicios de brote de continuaciones.

El PR-AUC esta implementado a mano para no depender de scikit-learn, que no esta en `requirements.txt`. Se valido contra `sklearn.metrics.average_precision_score` en 300 casos aleatorios con distintos tamanos, tasas de positivos y puntajes empatados: diferencia maxima 3,3e-16. Sensibilidad, precision, F1 y matriz de confusion se contrastaron igual en 200 casos mas.

### Baselines

| Baseline | Regla |
|---|---|
| `nunca_alerta` | no alerta nunca |
| `siempre_alerta` | alerta todos los meses |
| `persistencia` | alerta si el mes en curso ya esta en brote |
| `canal_endemico` | alerta si los casos de hoy ya superan el umbral del mes que se predice |

---

## Resultados de los baselines

Agregado de los ocho folds, 192 meses, 27 brotes (14,1%):

| | sensibilidad | precision | F1 | falsas alarmas | inicios |
|---|---|---|---|---|---|
| nunca_alerta | 0,000 | — | 0,000 | 0,000 | 0 de 3 |
| siempre_alerta | 1,000 | 0,141 | 0,247 | 1,000 | 3 de 3 |
| **persistencia** | 0,889 | 0,857 | **0,873** | 0,024 | **0 de 3** |
| **canal_endemico** | 0,926 | 0,806 | 0,862 | 0,036 | **2 de 3** |

Fold por fold:

```
 fold       ref  meses  brotes  inicios
 2015 2007-2014     24      13        1
 2016 2007-2015     24       9        1
 2017 2007-2016     24       0        0
 2018 2007-2017     24       0        0
 2019 2007-2018     24       2        1
 2020 2007-2019     24       3        0
 2021 2007-2020     24       0        0
 2022 2007-2021     24       0        0
```

---

## Limitacion principal: la etiqueta es un estado, no un evento

**Esta es la observacion mas importante del pipeline y condiciona lo que puede aportar cualquier modelo.**

De los 27 meses en brote de los folds, **3 son inicio de brote y 24 son continuacion**. Cali estuvo 12 meses seguidos por encima del P75 en 2015 y 9 en 2016. A escala mensual con umbral P75, "brote" no es un evento que ocurre: es un estado que dura casi un anio.

Eso hace que predecir el mes siguiente sea casi determinista, y explica por que los baselines lucen tan bien:

| | inicios detectados | continuaciones detectadas |
|---|---|---|
| persistencia | **0 de 3** | 24 de 24 |
| canal_endemico | 2 de 3 | 23 de 24 |

El F1 de 0,873 de la persistencia sale casi entero de acertar que un brote que ya empezo sigue. Operativamente eso no vale nada: cuando va el mes dos de un brote, la secretaria de salud ya lo sabe. **Todo el valor de un sistema de alerta temprana esta en esos 3 meses de inicio, y la persistencia no detecta ninguno por construccion.**

Por eso el baseline reporta las dos vistas. Un modelo que mejore el F1 agregado sin mejorar la deteccion de inicios no esta aportando nada.

Con 3 inicios en ocho anios de dos municipios no hay estadistica posible, solo conteo. Dos caminos, ninguno para esta entrega:

- **Subir el horizonte de prediccion.** Predecir el mes t con informacion hasta t-3 en vez de t-1. La persistencia se degrada y el modelo tiene donde aportar. Es un experimento comparable en MLflow.
- **Bajar a granularidad semanal.** Cuadruplicaria las observaciones y las transiciones, y con dengue total la serie da (Cali 57 a 680 casos por semana, Bucaramanga 5 a 219). Implica rehacer el panel.

---

## Por que se cambio de dengue grave a dengue total

El cambio de clasificacion de la OMS de 2009, adoptado en Colombia hacia 2010-2011, parte la serie de dengue grave en dos:

```
casos graves en Bucaramanga
2007  1.756      2011   18      2017   1
2008    562      2012   20      2018   4
2009    866      2013   46      2020   1
2010    811      2014   67      2021   3
```

Una caida de 45 veces entre dos anios consecutivos no es una mejora clinica. A nivel nacional la tasa de gravedad pasa de 19,7% en 2007 a 0,94% en 2017.

Con dengue grave, el P75 de Bucaramanga quedaba entre 5 y 17 casos al mes, umbral fijado por 2007-2010 e inalcanzable en el regimen actual. En la practica Bucaramanga no podia generar alertas y solo se medi­a Cali. Los folds quedaban con 7 positivos en 192 meses (3,6%) contra 24,2% del bloque de entrenamiento: se entrenaba sobre un regimen que termino hace quince anios.

Se midieron cinco configuraciones antes de decidir:

| Objetivo | Referencia | Train | Folds | Prueba | Folds vacios |
|---|---|---|---|---|---|
| grave | 2007-2022 | 24,2% | 3,6% | 22,2% | 5 de 8 |
| grave | 2011-2022 | 37,0% | 9,4% | 47,2% | 4 de 8 |
| grave | 2013-2022 | 39,6% | 12,0% | 51,4% | 3 de 8 |
| **clasico** | **2007-2022** | 25,0% | **14,1%** | 58,3% | 4 de 8 |
| clasico | 2011-2022 | 26,6% | 19,3% | 66,7% | 4 de 8 |

Recortar la referencia manteniendo dengue grave no era salida: con 2013-2022 el P75 de Bucaramanga en julio da cero, con lo que un solo caso en el mes cuenta como epidemia.

El cambio es una constante (`SERIE_OBJETIVO`), asi que volver atras o probar la otra serie cuesta una linea.

---

## Supuestos

Se cuentan todos los registros del archivo. **Las columnas `AJUSTE` y `TIP_CAS` no se usan para filtrar**, y ambas afectan el conteo: en SIVIGILA `AJUSTE` marca el estado del caso y algunos codigos corresponden a casos descartados, y `TIP_CAS` distingue confirmado por laboratorio de confirmado por clinica o por nexo epidemiologico. Es pregunta abierta para el experto.

El municipio es el de **ocurrencia** (`COD_MUN_O`), no el de residencia ni el de notificacion. Para decidir donde mandar control vectorial, ocurrencia es lo epidemiologicamente correcto.

Las variables climaticas son promedios mensuales de series diarias. El 3,7% de los municipios-mes queda sin clima porque el archivo climatico cubre 1.121 municipios y el panel tiene 1.114 codigos, con unos cuarenta que no coinciden.

La referencia del canal coincide con la ventana de entrenamiento. Si se cambia una hay que cambiar la otra: `REF_FIN` en `build_features.py` y `ANIO_FIN_TRAIN` en `splits.py`.

---

## Otras limitaciones

**La prueba tiene 58,3% de meses en brote**, y 2024 tiene los 24 meses. No es un error del canal, 2024 fue epidemico todo el anio, pero como conjunto de evaluacion es flojo: `siempre_alerta` saca 0,583 de precision sin hacer nada.

**Bucaramanga aporta un solo brote en los ocho folds**, los otros 26 son de Cali. El cambio a dengue total resolvio la escasez global, de 7 brotes a 27, pero no que Bucaramanga siga siendo casi invisible en la validacion cruzada. Su P75 lo fijan 2010, 2013 y 2014, y entre 2015 y 2022 no vuelve a esos niveles. En la prueba si aparece, con 23 de 36 meses.

**Los anios epidemicos no estan definidos de forma consistente.** El documento de decisiones lista 2010, 2013, 2016 y 2019; el EDA agrega 2023 y 2024. Ninguna de las dos listas incluye 2024, que es el anio con mas casos de toda la serie con 309.627, mas del doble que 2010. Y 2014, con 105.356, queda fuera mientras 2016, con 100.117, entra.

**Cuidado al leer el baseline de persistencia.** En el agregado su sensibilidad y su precision son siempre iguales, porque correr una serie binaria un mes conserva la cantidad de unos y hace que las alertas emitidas coincidan con los brotes reales. Es aritmetica, no desempenio.

---

## Pendientes

- MLflow en EC2 para registrar los experimentos.
- Realinear DVC para que versione `data/processed/` en vez de los crudos viejos, que ya no existen. Los tres `.dvc` de `data/raw/` quedaron sin actualizar.
- Un target de `make` para el panel y las variables.
- Llevar al experto: `AJUSTE`, `TIP_CAS`, y si el horizonte de prediccion de un mes es el adecuado dado que la etiqueta se comporta como un estado anual.
