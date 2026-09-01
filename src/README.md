# Pipeline de datos y modelado

Sistema de alerta temprana de dengue para Bucaramanga (68001) y Cali (76001).

---

## Flujo

```
Kaggle: saballesteros/maia4331-2614-grupo19
   dengue.csv              1.705.604 casos de dengue clasico, 2007-2025
   dengue_grave.csv           50.101 casos de dengue grave, 2007-2025
   google_earth_engine.csv  7.751.898 filas de clima diario por municipio
        |
        |  data/download_datasets.py
        v
   data/raw/                          ~2,6 GB, no se versiona en Git
        |
        |  src/data/build_panel.py
        v
   data/processed/panel_mensual.parquet          20 MB
   una fila por municipio y mes, 253.992 filas, 1.114 municipios
        |
        |  src/features/build_features.py
        v
   data/processed/features_mensual.parquet       35 MB
   el mismo panel mas 35 variables predictoras y la etiqueta de brote
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
| `tests/` | Verificacion de los modulos compartidos |

---

## Decisiones tomadas

### El municipio se identifica con el DIVIPOLA de cinco digitos

`COD_MUN_O` es el consecutivo dentro del departamento, no una llave. El codigo `001` lo comparten 33 municipios, entre ellos **Cali (76001) y Bucaramanga (68001)**, que son justamente los dos del alcance. La llave es `COD_DPTO_O` de dos digitos mas `COD_MUN_O` de tres.

### La fecha es la de inicio de sintomas

Se usa `INI_SIN` con respaldo en `FEC_NOT`, siguiendo la indicacion del profesor: es cuando la persona enfermo y no depende del retraso del sistema de vigilancia.

Las fechas vienen como `16/09/2007 12:00:00 a. m.` en formato dia/mes/anio, y se parsean con `format="%d/%m/%Y"` explicito. Sin declarar el formato, pandas no logra inferirlo por el `" a. m."`, cae a `dateutil` y asume mes/dia: toda fecha con dia menor o igual a 12, alrededor del 39% de los registros, queda con el mes cambiado.

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

### Etiqueta de brote

Un mes es brote si los casos de ese municipio y ese mes superan el **P75 historico del mismo mes**, calculado sobre 2007-2022. Es la zona de epidemia del canal endemico.

La serie sobre la que se calcula esta en la constante `SERIE_OBJETIVO` de `build_features.py`. Hoy es `casos_grave`, siguiendo la propuesta del equipo.

### Municipio endemico

Criterio de `Decisiones_Metodologicas`: al menos **diez anios con casos y doscientos casos acumulados**, sobre la serie de dengue clasico, dentro de la ventana de referencia.

La PR #8 usaba tres meses con casos y cincuenta acumulados sobre la serie de graves. Se cambio al criterio del documento para que el codigo y la memoria metodologica digan lo mismo.

### Particion temporal

```
entrenamiento : 2007 - 2022    con validacion cruzada de ventana expansiva
prueba        : 2023 - 2025    se evalua una sola vez, al final
```

No hay un anio fijo de validacion. Los hiperparametros se escogen con `folds_temporales`: cada fold entrena con todos los anios anteriores y valida sobre uno solo, avanzando de 2015 a 2022.

La razon es concreta. **2018, 2021 y 2022 no tienen ni un mes por encima del canal en Bucaramanga ni en Cali**, ni con la serie de graves ni con la de clasicos, ni con referencia 2007-2021 ni con 2011-2021. Se comprobo con las cuatro combinaciones. Un anio suelto de validacion puede quedarse sin positivos y dejar la seleccion de hiperparametros sin nada que medir.

La prueba cubre tres anios a proposito: 2023 de subida (126.411 casos de clasico), 2024 de epidemia (309.627, el maximo de la serie) y 2025 de descenso (120.564). Con un solo anio epidemico, un modelo que alerta siempre saldria bien; con 2025 adentro, paga en falsas alarmas.

### Metricas

No se usa exactitud como criterio. El 93,5% de los meses no tienen casos graves, asi que un modelo que nunca alerta acierta el 93,5%. Se calcula y se reporta unicamente para dejarlo en evidencia.

Las que deciden son sensibilidad, precision, tasa de falsas alarmas y PR-AUC, mas el desglose por municipio.

El PR-AUC esta implementado a mano para no depender de scikit-learn, que no esta en `requirements.txt`. Se valido contra `sklearn.metrics.average_precision_score` en 300 casos aleatorios con distintos tamanos, tasas de positivos y puntajes empatados: diferencia maxima 3,3e-16. Sensibilidad, precision, F1 y matriz de confusion se contrastaron igual en 200 casos mas.

### Baselines

| Baseline | Regla |
|---|---|
| `nunca_alerta` | no alerta nunca |
| `siempre_alerta` | alerta todos los meses |
| `persistencia` | alerta si el mes anterior fue brote |
| `canal_endemico` | alerta si el mes anterior quedo por encima del P75 |

`canal_endemico` es el rival real: es lo que hoy hace una secretaria de salud mirando su grafica, sin modelo. Cualquier modelo tiene que ganarle en sensibilidad sin disparar las falsas alarmas.

---

## Supuestos

Se cuentan todos los registros del archivo. **Las columnas `AJUSTE` y `TIP_CAS` no se estan usando para filtrar**, y ambas afectan el conteo: en SIVIGILA `AJUSTE` marca el estado del caso y algunos codigos corresponden a casos descartados, y `TIP_CAS` distingue confirmado por laboratorio de confirmado por clinica o por nexo epidemiologico. Es pregunta abierta para el experto.

El municipio es el de **ocurrencia** (`COD_MUN_O`), no el de residencia ni el de notificacion. Para decidir donde mandar control vectorial, ocurrencia es lo epidemiologicamente correcto.

Las variables climaticas son promedios mensuales de series diarias. El 3,7% de los municipios-mes queda sin clima porque el archivo climatico cubre 1.121 municipios y el panel tiene 1.114 codigos, con unos cuarenta que no coinciden.

La referencia del canal endemico coincide con la ventana de entrenamiento. Si se cambia una, hay que cambiar la otra: `REF_FIN` en `build_features.py` y `ANIO_FIN_TRAIN` en `splits.py`.

---

## Limitacion principal: el objetivo y el alcance

Esta es la limitacion que condiciona todo lo demas y probablemente obligue a
cambiar el alcance de la entrega.

### El cambio de clasificacion de la OMS de 2009 parte la serie en dos

La tasa de gravedad nacional cae de 19,7% en 2007 a 0,94% en 2017. En
Bucaramanga el quiebre es de 45 veces entre dos anios consecutivos:

```
casos graves en Bucaramanga
2007  1.756      2011   18      2017   1
2008    562      2012   20      2018   4
2009    866      2013   46      2020   1
2010    811      2014   67      2021   3
```

Una caida asi no es una mejora clinica. Es la definicion de caso, que Colombia
adopto hacia 2010-2011. Despues de 2011 Bucaramanga registra entre 1 y 14
casos graves **al anio**.

### Consecuencia sobre el canal

El P75 de Bucaramanga, calculado sobre 2007-2022, queda entre 5 y 17 casos al
mes. Ese umbral lo fijan 2007-2010 y es inalcanzable en el regimen actual. En
la practica **Bucaramanga casi no puede generar una alerta**, y lo que se
termina midiendo es Cali.

Eso produce una separacion grande entre el bloque de entrenamiento y los anios
que de verdad sirven para escoger hiperparametros:

```
entrenamiento 2007-2022    93 brotes / 384 meses   24,2%
folds 2015-2022             7 brotes / 192 meses    3,6%
prueba 2023-2025           16 brotes /  72 meses   22,2%
```

Los 93 brotes del entrenamiento estan casi todos entre 2007 y 2014. Cinco de
los ocho folds no tienen ni un positivo.

### Las alternativas, medidas

| Objetivo | Referencia | Train | Folds | Prueba | Folds vacios |
|---|---|---|---|---|---|
| grave | 2007-2022 (configuracion actual) | 24,2% | 3,6% | 22,2% | 5 de 8 |
| grave | 2011-2022 | 37,0% | 9,4% | 47,2% | 4 de 8 |
| grave | 2013-2022 | 39,6% | 12,0% | 51,4% | 3 de 8 |
| clasico | 2007-2022 | 25,0% | 16,7% | 58,3% | 4 de 8 |
| clasico | 2011-2022 | 26,6% | 19,3% | 66,7% | 4 de 8 |

La columna que importa es la distancia entre train y folds, porque mide cuanto
se parece el pasado sobre el que se entrena al presente sobre el que se
predice.

Recortar la referencia a 2013-2022 manteniendo dengue grave no sirve: el P75 de
Bucaramanga en julio da cero, con lo que un solo caso en el mes cuenta como
epidemia. Eso deja de ser un canal endemico.

### Que se decidio

Se mantiene **dengue grave con referencia 2007-2022**, que es lo que dice la
propuesta del equipo, y se documenta la limitacion en lugar de cambiar el
alcance sin consultarlo. El cambio es una sola constante (`SERIE_OBJETIVO` en
`build_features.py`, `REF_INICIO` y `REF_FIN` para la ventana).

Hay dos salidas posibles y las dos son decision de equipo con el experto:
cambiar el objetivo a dengue total, o cambiar los municipios del alcance por
otros donde la serie de dengue grave siga siendo densa despues de 2011.

## Otras limitaciones

**Los anios epidemicos no estan definidos de forma consistente.** El documento
de decisiones lista 2010, 2013, 2016 y 2019; el EDA agrega 2023 y 2024. Ninguna
de las dos listas incluye 2024 como lo que es: el anio con mas casos de toda la
serie, 309.627 de clasico, mas del doble que 2010. Y 2014, con 105.356 casos,
queda fuera mientras 2016, con 100.117, entra.

**Los anios 2017, 2018, 2021 y 2022 no tienen brotes** en Bucaramanga ni en
Cali, con ninguna configuracion de objetivo ni de referencia. No es un error:
fueron anios tranquilos. Esos folds igual aportan, porque miden falsas alarmas.

**El numero de municipios endemicos del documento no se habia verificado.** El
texto estima entre 120 y 150. Aplicando el criterio escrito sobre los datos
reales dan 523 dentro de 2007-2022, y el EDA del equipo obtuvo 621 sobre una
ventana mas larga y sin filtrar el exterior.

**Cuidado al leer el baseline de persistencia.** Su sensibilidad y su precision
son siempre iguales, porque correr una serie binaria un mes conserva la
cantidad de unos y hace que las alertas emitidas coincidan con los brotes
reales. Es aritmetica, no desempenio.

## Pendientes

- Realinear DVC para que versione `data/processed/` en vez de los crudos viejos, que ya no existen. Los tres `.dvc` de `data/raw/` quedaron sin actualizar.
- Un target de `make` para el panel y las variables.
- MLflow para registrar los experimentos.
- Llevar al experto: `AJUSTE`, `TIP_CAS`, el tratamiento del quiebre de 2011 y si el objetivo debe ser dengue grave o dengue total.
