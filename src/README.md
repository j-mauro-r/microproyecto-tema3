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
        |  src/models/baseline.py    reglas de referencia
        |  src/models/train.py       regresion de Poisson
        v
   MLflow en EC2, experimento sat-dengue
   baselines y modelos con los mismos folds y las mismas metricas
```

Cada capa lee la anterior. Ninguna vuelve a los crudos.

## Como se corre

```bash
pip install -r requirements.txt
python data/download_datasets.py          # necesita .env con las credenciales de Kaggle
python -m src.data.build_panel            # --sample 50000 para una prueba de 20 segundos
python -m src.features.build_features
python -m src.models.baseline
python -m src.models.train --tracking-uri http://IP_DEL_SERVIDOR:5000 --incluir-baselines

python -m tests.test_evaluation
python -m tests.test_features
```

Para mover el horizonte hay que rehacer las variables y volver a entrenar, porque la etiqueta cambia:

```bash
python -m src.features.build_features --horizonte 3
python -m src.models.train --tracking-uri http://IP_DEL_SERVIDOR:5000 --incluir-baselines
python -m src.models.train --tracking-uri http://IP_DEL_SERVIDOR:5000 --umbrales 1 1.2 1.5 1.8 2.2
```

## Estructura

| Ruta | Que hace |
|---|---|
| `src/data/build_panel.py` | Crudos a panel mensual completo |
| `src/features/build_features.py` | Panel a variables de modelado y etiqueta |
| `src/evaluation/splits.py` | Particion temporal y folds de validacion cruzada |
| `src/evaluation/metrics.py` | Metricas de alerta, iguales para todos los modelos |
| `src/models/baseline.py` | Los cuatro baselines de referencia |
| `src/models/train.py` | Regresion de Poisson y registro de corridas en MLflow |
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

### El objetivo es dengue clasico

`SERIE_OBJETIVO = "casos_clasico"`. Se cambio desde dengue grave el 1 de septiembre, por decision de equipo, porque la serie de graves quedo inservible despues del cambio de clasificacion de la OMS de 2009 (ver Limitaciones).

**Las dos series no se suman.** `casos_clasico` sale unicamente de `dengue.csv` (evento 210) y `casos_grave` unicamente de `dengue_grave.csv` (evento 220). Son dos columnas independientes del panel: la primera es el objetivo, la segunda queda como variable predictora. En SIVIGILA son dos eventos de notificacion distintos, no una particion de un mismo total, asi que sumarlos no seria correcto.

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

El PR-AUC esta implementado a mano. Cuando se escribio, scikit-learn no era dependencia del proyecto; hoy si lo es, porque el Poisson lo necesita, pero la implementacion propia se conserva a proposito: `src/evaluation/` no depende de ninguna libreria de modelado, asi que las metricas no cambian si manana se cambia de libreria. Se valido contra `sklearn.metrics.average_precision_score` en 300 casos aleatorios con distintos tamanos, tasas de positivos y puntajes empatados: diferencia maxima 3,3e-16. Sensibilidad, precision, F1 y matriz de confusion se contrastaron igual en 200 casos mas.

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

## Infraestructura de experimentos

Servidor de MLflow 2.22.0 en una instancia EC2 `t3.small` con Amazon Linux 2023, levantada en el Learner Lab de AWS Academy. Backend SQLite en `/opt/mlflow/mlflow.db`, artefactos en `/opt/mlflow/artifacts` servidos por el propio servidor con `--serve-artifacts`, y un servicio de systemd con `Restart=always` para que sobreviva a un reinicio de la instancia.

El cliente es `mlflow-skinny`, no `mlflow` completo. El paquete completo fija `pandas<3` y forzaria a bajar la version de pandas del proyecto; la version skinny trae el cliente de seguimiento sin el resto del ecosistema y funciona con pandas 3.

Dos advertencias sobre el Learner Lab. La instancia **se detiene, no se termina**, al cerrar la sesion del laboratorio, y **la IP publica cambia en cada reinicio**, asi que `--tracking-uri` hay que actualizarlo. Por eso el README no la deja escrita.

Cada corrida registra los mismos parametros y las mismas metricas, vengan de un baseline o de un modelo. Es lo que hace que la comparacion en MLflow sea legitima: sin eso, el PR-AUC solo existiria para los modelos y pareceria una ventaja suya cuando en realidad es que a los baselines no se les habia dado un orden.

Artefactos por corrida: `folds.csv` con el desglose fold por fold, `coeficientes.csv` con el peso de cada variable, y `variables.json` con la lista exacta de predictoras usadas.

---

## Resultados del modelado

Regresion de Poisson sobre las 40 predictoras, con imputacion por mediana y estandarizacion. El modelo predice **conteo de casos**, y la alerta sale de comparar ese conteo contra `k` veces el P75 del mes objetivo. Separar las dos cosas permite mover el punto de corte sin reentrenar.

Agregado de los ocho folds, 192 meses, 27 brotes, 3 de ellos inicio. Poisson con `alpha = 0,1`, corte en `k = 1`:

| horizonte | | alertas | sensibilidad | precision | F1 | PR-AUC | inicios |
|---|---|---|---|---|---|---|---|
| **t+1** | persistencia | 28 | 0,889 | 0,857 | 0,873 | 0,943 | 0 de 3 |
| | canal_endemico | 31 | 0,926 | 0,806 | 0,862 | 0,943 | **2 de 3** |
| | poisson | 27 | 0,889 | 0,889 | **0,889** | **0,957** | 1 de 3 |
| **t+2** | persistencia | 28 | 0,815 | 0,786 | 0,800 | 0,804 | 0 de 3 |
| | canal_endemico | 34 | 0,852 | 0,676 | 0,754 | 0,804 | **2 de 3** |
| | poisson | 32 | 0,889 | 0,750 | **0,814** | **0,831** | **2 de 3** |
| **t+3** | persistencia | 28 | 0,778 | 0,750 | **0,764** | 0,643 | **2 de 3** |
| | canal_endemico | 31 | 0,593 | 0,516 | 0,552 | 0,643 | **2 de 3** |
| | poisson | 37 | 0,815 | 0,595 | 0,688 | **0,762** | 1 de 3 |

### Ningun modelo supera al canal endemico en deteccion de inicios

```
              t+1    t+2    t+3
persistencia  0/3    0/3    2/3
canal         2/3    2/3    2/3
poisson       1/3    2/3    1/3
```

El canal endemico detecta dos de los tres inicios en los tres horizontes, y el Poisson no lo supera en ninguno. Es el resultado central del ejercicio: **la regla que una secretaria de salud ya aplica mirando su grafica, sin modelo de por medio, no ha sido superada en la unica metrica que le importa a un sistema de alerta temprana.**

El F1 dice otra cosa, y por eso no se usa solo. A t+1 el Poisson gana el F1 (0,889 contra 0,873) detectando **menos** inicios que el canal. Ese F1 sale de acertar continuaciones, que operativamente no valen nada.

La persistencia a t+3 merece una nota: pasa de 0 a 2 inicios. No es que mejore, es que a un mes vista la regla es imposible por construccion (alerta si el mes en curso ya esta en brote, y un inicio es justo cuando no lo estaba) y a tres meses esa imposibilidad desaparece. Con 3 inicios en total, acertar 2 puede ser coincidencia.

### El horizonte degrada todo, pero no por igual

De t+1 a t+3 el canal endemico pierde 31 puntos de F1 (0,862 a 0,552) y la persistencia pierde 11 (0,873 a 0,764). El Poisson pierde 20 pero conserva la sensibilidad casi intacta (0,889 a 0,815): se degrada emitiendo mas alertas, no perdiendo brotes. A t+3 emite 37 alertas para 27 brotes reales.

La ventaja del Poisson en PR-AUC crece con el horizonte: +0,014 a t+1, +0,027 a t+2, +0,119 a t+3. O sea que el modelo **si ordena mejor** los meses por riesgo, y cada vez mas a medida que el problema se vuelve dificil. Lo que no logra es convertir ese orden en un punto de corte mejor.

### El punto de corte no rescata al modelo

Barrido de `k` a t+3, mismo modelo, solo cambia donde se corta:

| k | alertas | sensibilidad | precision | F1 | inicios |
|---|---|---|---|---|---|
| 1,0 | 37 | 0,815 | 0,595 | **0,688** | 1 de 3 |
| 1,2 | 27 | 0,630 | 0,630 | 0,630 | 1 de 3 |
| 1,5 | 16 | 0,519 | 0,875 | 0,651 | 1 de 3 |
| 1,8 | 12 | 0,370 | 0,833 | 0,513 | 0 de 3 |
| 2,2 | 9 | 0,259 | 0,778 | 0,389 | 0 de 3 |

Ninguna eleccion de `k` llega a 0,764. Y subir el corte pierde inicios: a partir de 1,8 no queda ninguno. La ventaja del modelo en PR-AUC vive en la cola de alta precision y baja cobertura, que es la mitad equivocada de la curva para una alerta temprana.

### Que variables pesan, y el clima

Coeficientes de `poisson_alpha0.1_h1`, sobre variables estandarizadas, asi que son comparables entre si. Estan registrados como `coeficientes.csv` en cada corrida.

```
zona_canal            0,834      soil_water_l1_mean   -0,290
sir                   0,485      temp_mean_c          -0,234
dewpoint_mean_c       0,451      ...
brote                -0,422      rain_mm_day_lag_3    -0,055
p25                   0,370      rain_mm_day_lag_2    -0,045
casos_clasico_roll3   0,362      rain_mm_day_lag_1    -0,013
casos_clasico_lag_3  -0,327      rain_mm_day          -0,013
casos_clasico_lag_1  -0,326      es_endemico           0,000
```

Las tres primeras posiciones son la posicion en el canal, el SIR y **el punto de rocio**, que es una medida de humedad absoluta. O sea que el clima si entra, y no de forma marginal: el punto de rocio pesa mas que cualquiera de los rezagos de casos.

**Lo que no aporta es la lluvia.** Los cuatro terminos de precipitacion quedan por debajo de 0,06, un orden de magnitud debajo de la humedad y la temperatura. Es consistente con la literatura de dengue, donde la transmision responde mas a temperatura y humedad, que gobiernan el ciclo del vector, que al agua caida. Con criaderos domesticos, tanques y albercas, el agua no depende tanto de que llueva.

`es_endemico` da exactamente cero porque con dos municipios los dos son endemicos y la columna es constante. Vale la pena mantenerla igual: si el alcance se amplia, deja de serlo.

Advertencia al leer los signos. Varios rezagos de casos salen negativos mientras el rolling sale positivo. Con predictoras muy correlacionadas entre si, el signo de un coeficiente individual no se interpreta: el modelo reparte un mismo efecto entre columnas que dicen casi lo mismo. La magnitud agregada por familia de variables si informa, el signo de una sola no.

### La regularizacion no es la palanca

`alpha` en 0,01, 0,1, 1 y 10 mueve el F1 entre 0,868 y 0,889 a t+1, y entre 0,667 y 0,688 a t+3. Las diferencias caben dentro de un brote de 27. El problema no es sobreajuste.

### Conclusion

Con 3 inicios en ocho anios de dos municipios, un modelo no tiene de donde aprender a anticipar un inicio: cualquier diferencia en esa columna es de uno o dos casos. La limitacion es del diseno del problema, no del modelo, y ninguna busqueda de hiperparametros la va a resolver. Los caminos reales son bajar a granularidad semanal o ampliar el alcance a mas municipios, no probar mas modelos sobre estas 192 observaciones.

---

## Limitacion principal: la etiqueta es un estado, no un evento

**Esta es la observacion mas importante del pipeline y condiciona lo que puede aportar cualquier modelo.**

De los 27 meses en brote de los folds, **3 son inicio de brote y 24 son continuacion**. Cali estuvo 12 meses seguidos por encima del P75 en 2015 y 9 en 2016. A escala mensual con umbral P75, "brote" no es un evento que ocurre: es un estado que dura casi un anio.

Eso hace que predecir el mes siguiente sea casi determinista, y explica por que los baselines lucen tan bien. A horizonte de un mes:

| | inicios detectados | continuaciones detectadas |
|---|---|---|
| persistencia | **0 de 3** | 24 de 24 |
| canal_endemico | 2 de 3 | 23 de 24 |

El F1 de 0,873 de la persistencia sale casi entero de acertar que un brote que ya empezo sigue. Operativamente eso no vale nada: cuando va el mes dos de un brote, la secretaria de salud ya lo sabe. **Todo el valor de un sistema de alerta temprana esta en esos 3 meses de inicio, y la persistencia no detecta ninguno por construccion.**

Por eso el baseline reporta las dos vistas. Un modelo que mejore el F1 agregado sin mejorar la deteccion de inicios no esta aportando nada.

Con 3 inicios en ocho anios de dos municipios no hay estadistica posible, solo conteo.

**Subir el horizonte ya se probo** y esta medido arriba. La hipotesis era que a t+3 la persistencia se degrada y el modelo tiene donde aportar. Se degrada, si, pero el Poisson no ocupa ese espacio: gana en PR-AUC y pierde en F1 y en inicios. La hipotesis era razonable y salio que no.

Quedan dos caminos, ninguno para esta entrega:

- **Bajar a granularidad semanal.** Cuadruplicaria las observaciones y las transiciones, y con dengue clasico la serie da (Cali 57 a 680 casos por semana, Bucaramanga 5 a 219). Implica rehacer el panel.
- **Ampliar el alcance a mas municipios.** El panel ya trae los 1.114 y `--todos-los-municipios` esta implementado. Los 523 endemicos darian tres ordenes de magnitud mas de inicios. El alcance de dos municipios es una restriccion del enunciado, no del pipeline.

---

## Por que se cambio de dengue grave a dengue clasico

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

**Bucaramanga aporta un solo brote en los ocho folds**, los otros 26 son de Cali. El cambio a dengue clasico resolvio la escasez global, de 7 brotes a 27, pero no que Bucaramanga siga siendo casi invisible en la validacion cruzada. Su P75 lo fijan 2010, 2013 y 2014, y entre 2015 y 2022 no vuelve a esos niveles. En la prueba si aparece, con 23 de 36 meses.

**Los anios epidemicos no estan definidos de forma consistente.** El documento de decisiones lista 2010, 2013, 2016 y 2019; el EDA agrega 2023 y 2024. Ninguna de las dos listas incluye 2024, que es el anio con mas casos de toda la serie con 309.627, mas del doble que 2010. Y 2014, con 105.356, queda fuera mientras 2016, con 100.117, entra.

**Cuidado al leer el baseline de persistencia.** Su sensibilidad y su precision salen casi iguales en los tres horizontes, y no es desempenio sino aritmetica: correr una serie binaria conserva la cantidad de unos, asi que emite 28 alertas contra 27 brotes reales sin importar el horizonte. La precision queda atada a la sensibilidad por construccion y no aporta informacion aparte.

**El PR-AUC de persistencia y canal_endemico es identico** (0,943 / 0,804 / 0,643 segun el horizonte). Es correcto y esta puesto a proposito: comparten el mismo puntaje continuo, la razon entre los casos de hoy y el umbral del mes objetivo, y solo se diferencian en donde cortan. El PR-AUC mide el orden, no el corte.

---

## Pendientes

- Realinear DVC para que versione `data/processed/` en vez de los crudos viejos, que ya no existen. Los tres `.dvc` de `data/raw/` quedaron sin actualizar.
- Un target de `make` para el panel y las variables.
- Llevar al experto: `AJUSTE`, `TIP_CAS`, y si el horizonte de prediccion de un mes es el adecuado dado que la etiqueta se comporta como un estado anual.
