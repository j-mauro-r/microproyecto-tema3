# HU008 — Evidencia de implementación

**Estado:** `[COMPLETADA — DESARROLLO]`

**Rama:** `docs/hu008-integracion-dashboard`

**SHA base auditado:** `56125013` (el commit de implementación se identifica en el historial)

**Ámbito:** integración local Dashboard ↔ FastAPI

## Baseline

- No existía script de tests ni de typecheck.
- `npm run lint`: fallaba con 12 errores Prettier y 9 warnings Fast Refresh heredados.
- `npm run build`: PASS; warning de migración `vite-tsconfig-paths` y warning Nitro
  `inlineDynamicImports`.

## Arquitectura y configuración

```text
React UI → useDengueDashboard → React Query
  → DengueRepository → HttpDengueRepository → FastAPI /api/v2
```

`.env.example` documenta la única variable pública:

```text
VITE_BIOMAC_API_BASE_URL=http://127.0.0.1:8001/api/v2
```

El lector elimina slash final y exige URL HTTP(S) cuyo path sea exactamente
`/api/v2`. La ausencia o invalidez produce `BiomacConfigurationError` controlado
dentro de la query. Ningún componente contiene hosts ni duplica el base path.

`HttpDengueRepository` es la composición default. `MockDengueRepository` requiere
un snapshot explícito y solo queda como fake de tests; nunca es importado por el
composition root ni se usa como fallback.

## Contratos y parsing

Los DTO TypeScript reflejan los envelopes HU006/HU007 en `snake_case`; el mapper
produce modelos UI sin alterar nullability. Se validan `prediction_snapshot`,
`run_id`, `predictions`, DIVIPOLA y horizonte. JSON/payload inválido, error API y
fallo de red generan `BiomacApiError` saneado con status/code/requestId cuando
existen.

## Apertura, Refresh y upload

- apertura: query key `["biomac","predictions","latest"]` ejecuta un GET;
- empty: solo `404 PREDICTION_NOT_FOUND` presenta “Aún no hay predicciones”;
- error inicial: mensaje controlado y Reintentar;
- Refresh: `refetch latest`, mantiene datos durante fetching y muestra aviso si falla;
- upload: dialog accesible solicita `.csv` y mes, valida UX y pide confirmación;
- multipart: browser crea `FormData`; solo se fija `Accept`, nunca boundary;
- éxito: muestra run_id/mes/COMPLETED e invalida `latest`;
- error: conserva el snapshot y permite reintentar con archivo/mes seleccionados.

La UI solo formatea una `probability` real como porcentaje. `expected_cases` y
`risk_score` conservan su etiqueta/valor. Canal, explicabilidad, historia y calidad
se muestran como no disponibles; se retiraron componentes que calculaban o
presentaban mock P25/P50/P75, SHAP, recomendaciones y proyecciones sintéticas.

## Pruebas y calidad

Se incorporaron Vitest y scripts `test`/`typecheck`. Las pruebas cubren URL,
configuración inválida, latest, nullability, thresholds, error envelope, red,
JSON/payload inválido, valores no soportados, no-fallback y multipart real.

Resultado final:

- `npm test`: 3 archivos, 15 pruebas PASS;
- `npm run typecheck`: PASS;
- `npm run lint`: PASS con 9 warnings Fast Refresh heredados y 0 errores;
- `npm run build`: PASS con los dos warnings de tooling ya descritos;
- `.venv/bin/python -m pytest api/tests -q`: 194 pruebas PASS, un warning conocido.

## Criterios y autovalidaciones

| Grupo | Resultado | Evidencia |
|---|---|---|
| CA01–CA05 | PASS | configuración única, HTTP default, sin fallback, latest inicial |
| CA06–CA11 | PASS | datos reales, empty/error/retry, Refresh read-only con stale data |
| CA12–CA20 | PASS | dialog, validación, confirmación, FormData, receipt, refetch y retry |
| CA21–CA25 | PASS | nullability/semántica nativa, cero cálculos/enriquecimientos ficticios |
| CA26–CA30 | PASS | estados, gates verdes, sin secretos/cloud y evidencia |
| AV01–AV06 | PASS | composición/config y estados iniciales/retry |
| AV07–AV15 | PASS | Refresh GET-only, upload/confirmación/refetch/error envelope |
| AV16–AV20 | PASS | nullable, outputs nativos, sin mock/ML, `.env.example` público |
| AV21–AV24 | PASS | test/typecheck/lint/build/API y git auditados |

## Pendientes HU009/HU010

HU009 debe suministrar desde fuentes reales canal endémico/current status, data
quality, explicación e historia. HU010 cubrirá E2E con procesos reales y
deployment. HU008 no agrega AWS, EC2, S3, RDS, Docker, auth, MLflow, DVC, modelos,
feature engineering, SHAP ni secretos.
