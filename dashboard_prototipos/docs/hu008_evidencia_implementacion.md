# HU008 — Evidencia de implementación y cierre de auditoría

**Estado:** `[LISTA PARA AUDITORÍA FINAL]`

**Rama / PR:** `docs/hu008-integracion-dashboard` / `#30`

**SHA de implementación auditada:** `5d104c3e`

**Ámbito:** integración local Dashboard ↔ FastAPI; sin cambios de backend.

## Correcciones de auditoría

- Se reemplazó **“BIOMAC — Alerta temprana de dengue grave”** por
  **“BIOMAC — Sistema de alerta temprana de dengue”**. React ya no afirma un
  target epidemiológico que el contrato API no entrega.
- `BiomacApiError` conserva `details?: unknown` del `ErrorEnvelope` para soporte,
  sin presentarlo en la UI.
- Se añadió cobertura directa de apertura/retry, Refresh, selector/horizontes,
  upload UX, mutación con React Query, receipt, nullability y no-fallback.
- Se configuró Vitest para deduplicar React y probar hooks reales con
  `QueryClientProvider`.

## Archivos modificados en `5d104c3e`

- `dashboard_prototipos/dengue-watch-pro/README.md`
- `dashboard_prototipos/dengue-watch-pro/vitest.config.ts`
- `src/features/dengue/DengueDashboard.tsx`
- `src/features/dengue/DengueDashboard.test.tsx`
- `src/features/dengue/components/MonthlyUploadDialog.test.tsx`
- `src/hooks/useDengueDashboard.ts`
- `src/hooks/useDengueDashboard.test.tsx`
- `src/routes/index.tsx`
- `src/services/dengue/dengue.http.repository.ts`
- `src/services/dengue/dengue.http.repository.test.ts`

Esta evidencia se actualiza en el commit documental posterior, identificable como
el tip del PR #30.

## Arquitectura y comportamiento verificados

```text
React UI → useDengueDashboard → React Query
  → DengueRepository → HttpDengueRepository → FastAPI /api/v2
```

- Apertura: exactamente un `GET /predictions/latest`; el filtro local usa
  DIVIPOLA `68001` para Bucaramanga y `76001` para Cali.
- Refresh: solo hace refetch de `latest`; no ejecuta POST, conserva el snapshot
  durante `isFetching` y también ante un error posterior.
- Upload: valida archivo/mes/CSV y confirmación antes de mutar. Un resultado
  `COMPLETED` invalida y refetchea `latest`; un error conserva el snapshot y el
  retry reutiliza el mismo objeto `File` y mes.
- El mapper conserva `null` en `probability`, `label` y `decisionThreshold`; no
  convierte `riskScore` ni `expectedCases` en probabilidad.
- `MockDengueRepository` no es importado por ningún módulo productivo. Los errores
  HTTP, de red, JSON o payload inválido producen `BiomacApiError`, nunca fallback.
- Canal endémico, explicabilidad, historia y calidad permanecen explícitamente no
  disponibles para HU009; no se fabrican datos.

## Pruebas añadidas por la auditoría

- `DengueDashboard.test.tsx` (8): loading sin mocks, empty, error 500, refetch,
  recuperación posterior, snapshot durante fetching/error, T+1/T+2, thresholds
  independientes y campos nulos/no disponibles.
- `MonthlyUploadDialog.test.tsx` (4): archivo/mes/CSV, cancelación/aceptación,
  disabled durante submit y receipt con `run_id`, mes y `COMPLETED`.
- `useDengueDashboard.test.tsx` (4): apertura y selector, Refresh GET-only,
  POST COMPLETED + refetch, error + snapshot + retry con archivo/mes exactos.
- `dengue.http.repository.test.ts` (5 totales): se añadió la preservación de
  `error.details`; también cubre multipart, nullability, error API y no-fallback.
- `api-config.test.ts` mantiene 6 pruebas de configuración.

## Resultados exactos finales

Ejecutados el 2026-09-03 desde `dashboard_prototipos/dengue-watch-pro`, salvo la
suite API ejecutada desde la raíz:

- `npm test`: **5 archivos, 27 pruebas PASS**; duración 813 ms.
- `npm run typecheck`: **PASS**, `tsc --noEmit`, exit 0.
- `npm run lint`: **PASS**, 0 errores y **9 warnings** heredados de
  `react-refresh/only-export-components`.
- `npm run build`: **PASS**. Warnings reales: migración de
  `vite-tsconfig-paths` a `resolve.tsconfigPaths` y Nitro ignora
  `inlineDynamicImports` cuando `codeSplitting` está configurado.
- `.venv/bin/python -m pytest api/tests -q`: **194 passed, 1 warning in 1.98s**.
  Warning conocido: `StarletteDeprecationWarning` por `httpx` con
  `starlette.testclient`.
- `git diff --check`: **PASS**.

## Criterios de aceptación CA01–CA30

| Criterios | Estado | Evidencia                                                                                            |
| --------- | ------ | ---------------------------------------------------------------------------------------------------- |
| CA01–CA05 | PASS   | `api-config.test.ts`, composition root HTTP e inspección de imports sin mock/fallback                |
| CA06–CA11 | PASS   | `DengueDashboard.test.tsx`: datos API, empty, error, retry, recuperación y Refresh con stale data    |
| CA12–CA20 | PASS   | tests del diálogo, hook y repositorio: validación, confirmación, FormData, receipt, refetch y retry  |
| CA21–CA25 | PASS   | tests de mapper/dashboard para nullability, outputs nativos y ausencia de enriquecimientos ficticios |
| CA26–CA30 | PASS   | estados UI automatizados, cuatro gates frontend, API verde e inspección de configuración/alcance     |

## Autovalidaciones AV01–AV24

| AV   | Estado | Evidencia o procedimiento verificable                                                                              |
| ---- | ------ | ------------------------------------------------------------------------------------------------------------------ |
| AV01 | PASS   | Inspección: `src/services/dengue/index.ts` compone `HttpDengueRepository`.                                         |
| AV02 | PASS   | `rg 'MockDengueRepository' src --glob '!**/*.test.*'`: solo aparece su declaración, no imports productivos.        |
| AV03 | PASS   | `useDengueDashboard.test.tsx`: apertura llama una sola vez a `latest`.                                             |
| AV04 | PASS   | `DengueDashboard.test.tsx`: solo `PREDICTION_NOT_FOUND` produce empty.                                             |
| AV05 | PASS   | `DengueDashboard.test.tsx`: latest 500 muestra error inicial.                                                      |
| AV06 | PASS   | `DengueDashboard.test.tsx`: Reintentar llama refetch y una respuesta posterior recupera la vista.                  |
| AV07 | PASS   | `useDengueDashboard.test.tsx`: Refresh llama GET latest por segunda vez y cero POST/createRun.                     |
| AV08 | PASS   | `DengueDashboard.test.tsx`: `isFetching=true` mantiene el 72% y muestra “Actualizando…”.                           |
| AV09 | PASS   | `DengueDashboard.test.tsx`: error de Refresh conserva el snapshot y ofrece nuevo Refresh.                          |
| AV10 | PASS   | `dengue.http.repository.test.ts`: POST usa `FormData` con archivo y mes, sin fijar boundary.                       |
| AV11 | PASS   | `MonthlyUploadDialog.test.tsx`: sin archivo, sin mes y no-CSV no llaman submit.                                    |
| AV12 | PASS   | `MonthlyUploadDialog.test.tsx`: cancelar confirma cero submit; aceptar envía archivo/mes exactos.                  |
| AV13 | PASS   | `useDengueDashboard.test.tsx`: `COMPLETED` invalida/refetchea latest.                                              |
| AV14 | PASS   | `useDengueDashboard.test.tsx`: error conserva snapshot y retry reutiliza archivo/mes.                              |
| AV15 | PASS   | Tests del diálogo muestran receipt; test HTTP conserva `requestId`, code y `details`.                              |
| AV16 | PASS   | Tests HTTP/dashboard preservan `probability`, `label` y threshold nulos.                                           |
| AV17 | PASS   | Test dashboard comprueba thresholds T+1/T+2; inspección del mapper mantiene `riskScore`/`expectedCases` separados. |
| AV18 | PASS   | Test dashboard exige paneles “Información no disponible”; inspección confirma que no se rellenan.                  |
| AV19 | PASS   | Inspección con `rg` de módulos productivos: sin cálculos ML, SHAP, percentiles o target inventado.                 |
| AV20 | PASS   | Inspección de `.env.example`: única variable pública `VITE_BIOMAC_API_BASE_URL`, sin secretos/cloud.               |
| AV21 | PASS   | `test`, `typecheck`, `lint` y `build` ejecutados con scripts reales; resultados arriba.                            |
| AV22 | PASS   | Conteo capturado de Vitest: 5 archivos y 27 pruebas.                                                               |
| AV23 | PASS   | Suite raíz capturada: 194 pruebas API pasan, sin regresión backend.                                                |
| AV24 | PASS   | Inspección Git: rama indicada, PR #30, sin rama/PR nuevo ni merge.                                                 |

## Pendientes fuera de alcance

HU009 debe suministrar desde fuentes reales canal endémico/current status, data
quality, explicación e historia. HU010 cubrirá E2E con procesos reales y
deployment. HU008 no agrega cloud, auth, MLflow, DVC, modelos, feature engineering,
SHAP ni secretos.
