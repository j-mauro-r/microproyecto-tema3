# Dengue Alert Dashboard

Construye en Lovable el FRONTEND del prototipo BIOMAC — Sistema de Alerta Temprana de Dengue Grave.

OBJETIVO

Crear un dashboard que permita responder:

“¿Existe riesgo de que se presente un exceso de casos de dengue grave en Bucaramanga y Cali dentro de los próximos dos meses, de manera que se puedan tomar oportunamente medidas preventivas y de preparación del sistema de salud?”

ALCANCE

- Trabajar únicamente con Bucaramanga y Cali.

- Granularidad mensual.

- Horizonte predictivo: T+1 y T+2 meses.

- Salida del modelo: clasificación binaria:

  0 = NO EXCESO

  1 = EXCESO

- Mostrar además la probabilidad asociada.

- Por ahora usar datos mock desacoplados. No implementar backend.

DASHBOARD

1. Selector de ciudad:

   - Bucaramanga

   - Cali

2. KPIs principales:

   - Alerta T+2: EXCESO / NO EXCESO.

   - Probabilidad de exceso T+2.

   - Estado actual frente al canal endémico P75.

3. Comparativo compacto:

   Mostrar para ambas ciudades:

   - resultado T+1

   - probabilidad T+1

   - resultado T+2

   - probabilidad T+2

4. Serie histórica + canal endémico:

   - casos mensuales observados

   - P25

   - P50

   - P75

   - meses históricos con exceso

   - diferenciar claramente histórico y horizonte futuro.

5. Pronóstico:

   Gráfica comparativa de probabilidad de exceso T+1 y T+2 para Bucaramanga y Cali.

6. Interpretabilidad:

   Gráfica SHAP/importancia de variables:

   - rezagos de casos

   - promedio móvil

   - precipitación

   - temperatura

   - estacionalidad.

7. Insights:

   Mostrar máximo 3 hallazgos interpretables derivados de los datos.

DISEÑO

Mantener estética oscura, científica y profesional tipo health analytics.

Eliminar mapa nacional, ranking nacional, KPIs de otros municipios y cualquier elemento redundante.

ARQUITECTURA

Aplicar SOLID, DRY y Atomic Design.

Separar:

components/

features/

pages/

hooks/

services/

types/

mocks/

Ningún componente visual debe contener datos hardcodeados.

Crear interfaces TypeScript y una capa repository/service mock preparada para reemplazarse posteriormente por la API del modelo.

La interfaz debe permitir comprender en pocos segundos:

1. ¿Hay alerta?

2. ¿Con qué probabilidad?

3. ¿Para cuál horizonte?

4. ¿Qué evidencia epidemiológica la soporta?

5. ¿Qué variables impulsan la predicción?

No implementar funcionalidades que no aporten directamente a estas preguntas.

This project was built with [Lovable](https://lovable.dev).

**Live app**: https://dengue-watch-pro.lovable.app

## Build with Lovable

Continue developing this project in the [Lovable editor](https://lovable.dev/projects/818bc040-f3b5-4f74-9621-92768cfd24db).

- **Ship faster**: describe what you want to build and Lovable handles the code.
- **Stay in sync**: every change made in Lovable is committed straight to this repository.
- **Full ownership**: this code is yours. Push to `main` on GitHub and your changes sync back into Lovable, ready for your next prompt.

## Development

Prefer working locally? You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
git clone <this-repository-url>
cd <repository-name>
npm i
npm run dev
```
