# HU009 — Evidencia de implementación

**Estado:** `[LISTA PARA AUDITORÍA]`  
**Rama / PR:** `docs/hu009-metadata-explicabilidad-calidad` / `#31`  
**SHA de implementación:** `6e3eb02d` (el commit documental queda como tip del PR).

## Baseline

Ejecutado antes de modificar código el 2026-09-03:

- API: 194 passed, 1 warning Starlette/httpx, 2.17 s.
- `compileall`: PASS; `pip check`: No broken requirements found.
- Frontend: 5 archivos, 27 tests PASS; typecheck PASS.
- Lint: 0 errores, 9 warnings Fast Refresh heredados.
- Build: PASS; warnings `vite-tsconfig-paths` e `inlineDynamicImports`.

## Fuentes reales y disponibilidad

- Champion, predicciones y thresholds: `ChampionOutput` HU004/HU005, sin recálculo.
- Calidad: mismo `ValidatedMonthlyUpload`; las 39 features requeridas ya fueron
  verificadas numéricas, finitas y no nulas para ambos municipios y el corte.
- Completitud epidemiológica/climática: **null**, porque no existe denominador
  contractual por grupo. Se persiste un warning visible.
- Contexto: `p25`, `p75` y `zona_canal` proceden de la allowlist de 39 features del
  corte. `observed_cases`, `p50` y `ratio_to_p75`: **null**; ningún lag los sustituye.
- PR12 contiene el script y tuvo `shap_local_T1/T2.parquet` en su commit, pero esos
  artefactos no existen en la rama/ambiente vigente. Composición actual:
  `UnavailableExplanationProvider`, por lo que explanation es `available=false`.
- El provider parquet existe como opción explícita y solo devuelve SHAP local con
  feature contract, municipio, mes y horizonte exactos. No se ejecuta en GET.

## Implementación

- Contratos inmutables: quality, current status, decision rule, explanation y top features.
- Metadata Champion opcional preservada: MLflow run, hash de artefacto, versión de
  regla y método de explicación; permanece null cuando no existe.
- SQLite: tablas hijas `snapshot_quality`, `current_status`,
  `prediction_enrichments` y `champion_enrichments`, todas con FK a `runs`.
- API latest/history: extensión aditiva; snapshots legacy devuelven null/unavailable.
- Frontend: DTO → mapper → modelo; quality/warnings, contexto parcial, explicación
  por horizonte y “Historial de predicciones”. No hay cálculo analítico en React.
- Refresh continúa llamando únicamente `getLatest`; history es una query read-only separada.

## Pruebas agregadas

Backend `test_hu009_enrichment.py`: calidad/corte/completitud, contexto parcial sin
lags, ratio, provider unavailable, SHAP exacto T+1/T+2/ciudad/mes, artefacto
corrupto, orden por valor absoluto/signo, persistencia/API/history y legacy.

Frontend: mapping enriched/legacy/history, warning visible, contexto parcial,
SHAP local con contribuciones positiva/negativa e historial correctamente rotulado.

## Resultados finales

- `.venv/bin/python -m pytest api/tests -q`: **202 passed, 1 warning in 2.50s**.
- `.venv/bin/python -m compileall -q api/app api/tests`: PASS.
- `.venv/bin/python -m pip check`: `No broken requirements found.`
- `npm test`: **5 archivos, 30 tests PASS**, 891 ms.
- `npm run typecheck`: PASS.
- `npm run lint`: PASS, 0 errores y 9 warnings Fast Refresh heredados.
- `npm run build`: PASS; warnings de migración `vite-tsconfig-paths` y Nitro
  `inlineDynamicImports` ya existentes.

## Criterios CA01–CA34

| Criterios | Estado | Evidencia |
|---|---|---|
| CA01–CA04 | PASS | tests mapper/persistencia/API; metadata opcional nullable y output nativo |
| CA05–CA08 | PASS | builder quality y round-trip warning SQLite → API → mapper → UI |
| CA09–CA13 | PASS | current status parcial; observed/p50/ratio null; React solo renderiza |
| CA14–CA20 | PASS | providers y fixtures parquet exactas; imports/GET sin runtime ML/cloud |
| CA21–CA25 | PASS | FKs, run común, latest/history y lectura legacy aditiva |
| CA26–CA30 | PASS | tests UI available/partial/unavailable, warning, no causalidad y Refresh GET-only |
| CA31–CA34 | PASS | suites finales, inspección de seguridad y esta evidencia versionada |

## Autovalidaciones AV01–AV28

| AV | Estado | Evidencia |
|---|---|---|
| AV01 | PASS | baseline exacto registrado arriba |
| AV02 | PASS | `generate_shap.py`, generator, contrato JSON y árbol del commit PR12 inspeccionados |
| AV03 | PASS | metadata Champion persiste y se serializa sin reinterpretación |
| AV04 | PASS | tests HU006/HU007 mantienen thresholds 0.61/0.67 independientes |
| AV05 | PASS | tests HU008/HU009 mantienen expected cases/score sin porcentaje |
| AV06 | PASS | `test_quality_uses_validated_cut...` |
| AV07 | PASS | completitudes null y warning por falta de denominador |
| AV08 | PASS | round-trip warning y test UI `role=alert` |
| AV09 | PASS | current status exige source; observed cases permanece null |
| AV10 | PASS | p50 null en builder/UI |
| AV11 | PASS | `test_ratio_requires_observed_cases_and_positive_p75` |
| AV12 | PASS | provider unavailable retorna contrato vacío |
| AV13 | PASS | fixture SHAP por T+1/T+2 y Cali/Bucaramanga |
| AV14 | PASS | mismatch mes/ciudad/horizonte retorna unavailable |
| AV15 | PASS | top features ordenadas por abs y signo -0.8 preservado |
| AV16 | PASS | solo columnas `shap_`; no importancia global/PNG |
| AV17 | PASS | test read queries: GET no llama orchestrator/Champion; provider no está en query path |
| AV18 | PASS | history usa repositorio query-only y tests de lectura |
| AV19 | PASS | FKs y claves `(run_id, divipola, horizon)`; round-trip mismo run |
| AV20 | PASS | ausencia de tablas/filas se degrada a null/unavailable |
| AV21 | PASS | mapping legacy no fabrica defaults analíticos |
| AV22 | PASS | tests UI de quality/context/explanation available/unavailable/partial |
| AV23 | PASS | test hook conserva Refresh GET-only/POST cero |
| AV24 | PASS | `rg` frontend sin imports shap/xgboost/pandas/ML |
| AV25 | PASS | query/runtime inspeccionado sin DVC pull, S3 ni MLflow obligatorio |
| AV26 | PASS | suite API completa registrada en PR |
| AV27 | PASS | test/typecheck/lint/build registrados en PR |
| AV28 | PASS | `git diff --check`, estado Git y búsqueda de artefactos ejecutados |

## Gaps preservados

No hay observed cases actual, p50, ratio, completitud por grupo ni SHAP operativo.
No se versionaron parquets/modelos ni se agregaron cloud, auth, entrenamiento,
recomendaciones o causalidad. HU010 conserva E2E/deployment.
