# HU004 — Evidencia canónica de implementación

**Fecha:** 2026-09-03
**Rama:** `docs/hu004-champion-adapter`
**Estado:** `[COMPLETADA — DESARROLLO]`
**AWS/deployment:** `[PENDIENTE — MAURICIO]`

## Resultado arquitectónico

HU005 y las HUs posteriores disponen de una sola operación:

```text
HU005 → ChampionOutputProvider.produce(context) → ChampionOutput
```

La estrategia se selecciona exclusivamente en composición/configuración:

```text
MVP:    MaterializedChampionProvider → MaterializedOutputAdapter → ChampionOutput
Futuro: ExecutableChampionProvider   → LazyChampionAdapter       → ChampionOutput
```

Ambos implementan `ChampionOutputProvider`. No existe fallback: si el provider
seleccionado falla, el error se propaga y no se invoca la otra estrategia.
`ChampionExecutionContext` es inmutable; cada provider exige su única entrada, rechaza
la de la otra estrategia y valida `reference_month` y el hash fuente cuando aplica.

## Archivos

Modificados en el cierre del blocker:

- `api/app/champion/__init__.py`
- `api/app/champion/provider.py`
- `api/tests/test_champion_provider.py`
- `dashboard_prototipos/docs/hu004_champion_adapter.md`
- `dashboard_prototipos/docs/hu004_evidencia_implementacion.md`
- `dashboard_prototipos/docs/arquitectura.md`
- `dashboard_prototipos/docs/implementacion.md`
- `dashboard_prototipos/docs/API-sign.md`

La implementación previa vigente incluye los adapters, modelos y pruebas ejecutables y
materializados bajo `api/app/champion/` y `api/tests/`.

## Evidencia de intercambiabilidad

- El mismo consumer de prueba recibe `ChampionOutputProvider` y llama únicamente
  `produce(context)` con cualquiera de los dos providers.
- Ambos caminos retornan exactamente `ChampionOutput` y satisfacen el Protocol.
- La fábrica acepta una sola estrategia y rechaza dependencias de la estrategia opuesta.
- Un adapter materializado que falla propaga su excepción; no llama al ejecutable.
- El provider ejecutable delega y mantiene una sola carga tras múltiples llamadas.
- El materializado conserva thresholds T+1 `0.61` y T+2 `0.67` del fixture.

## Criterios de aceptación canónicos CA01–CA22

| CA | Estado | Evidencia |
|---|---|---|
| CA01 | PASS | baseline y regresión completa verdes |
| CA02 | PASS | interfaz única `produce(context)` |
| CA03 | PASS | ambos providers satisfacen el mismo Protocol |
| CA04 | PASS | consumer HU005-style sin branching A/B |
| CA05 | PASS | ambos retornan `ChampionOutput` |
| CA06 | PASS | MVP selecciona materializado por composición |
| CA07 | PASS | ejecutable es alternativa futura, no requisito MVP |
| CA08 | PASS | provider ejecutable delega sin duplicar lógica |
| CA09 | PASS | load-once preservado |
| CA10 | PASS | errores estables existentes preservados |
| CA11 | PASS | provider materializado no ejecuta modelos |
| CA12 | PASS | cuatro combinaciones PR12 exactas |
| CA13 | PASS | orden del array no determina asociación |
| CA14 | PASS | probability y label se preservan |
| CA15 | PASS | thresholds T+1/T+2 independientes |
| CA16 | PASS | target_month validado |
| CA17 | PASS | metadata y feature contract preservados |
| CA18 | PASS | contexto ejecutable incorrecto falla controladamente |
| CA19 | PASS | contexto materializado incorrecto falla controladamente |
| CA20 | PASS | ausencia de fallback demostrada |
| CA21 | PASS | HU005 solo requiere provider/output comunes |
| CA22 | PASS | documentación consolidada y consistente |

## Autovalidaciones canónicas AV01–AV20

| AV | Estado | Resultado |
|---|---|---|
| AV01 | PASS | imports públicos sin frameworks ML |
| AV02 | PASS | contratos/contexto inmutables |
| AV03 | PASS | executable produce output común |
| AV04 | PASS | materialized produce output común |
| AV05 | PASS | consumer idéntico funciona con A/B |
| AV06 | PASS | tipo de salida no cambia |
| AV07 | PASS | validación feature contract preservada |
| AV08 | PASS | load-once preservado |
| AV09 | PASS | T+1-only no inventa T+2 |
| AV10 | PASS | cuatro claves materializadas exactas |
| AV11 | PASS | asociación independiente del orden |
| AV12 | PASS | thresholds por horizonte preservados |
| AV13 | PASS | contexto ejecutable incorrecto rechazado |
| AV14 | PASS | contexto materializado incorrecto rechazado |
| AV15 | PASS | selección explícita probada |
| AV16 | PASS | fallo no conmuta estrategia |
| AV17 | PASS | sin AWS/DVC/MLflow/modelo/red |
| AV18 | PASS | pruebas focales aprobadas |
| AV19 | PASS | suite/compileall/pip check aprobados |
| AV20 | PASS | sin HU005 real ni infraestructura |

## Comandos y resultados

```text
.venv/bin/python -m pytest api/tests/test_champion_adapter.py -q
→ 11 passed, 1 warning in 0.02s

.venv/bin/python -m pytest api/tests/test_materialized_champion_adapter.py -q
→ 34 passed, 1 warning in 0.17s

.venv/bin/python -m pytest api/tests/test_champion_provider.py -q
→ 10 passed, 1 warning in 0.14s

.venv/bin/python -m pytest api/tests -q
→ 126 passed, 1 warning in 0.75s

.venv/bin/python -m compileall -q api/app api/tests
→ exit 0, sin salida

.venv/bin/python -m pip check
→ No broken requirements found.
```

Las pruebas no requieren credenciales AWS, DVC, S3, MLflow, XGBoost, pickle ni red. La
advertencia conocida de `fastapi.testclient`/Starlette sobre `httpx` no pertenece a HU004.

## Tareas restantes de Mauricio

1. Configurar `MaterializedChampionProvider` en el deployment MVP.
2. Materializar de forma controlada el `ChampionResult` real de PR #12.
3. Provisionar/configurar EC2 y variables sin versionar secretos.
4. Ejecutar smoke test real y registrar metadata, horizontes y thresholds.
5. Levantar Uvicorn y validar readiness/health en infraestructura.

La disponibilidad productiva del provider ejecutable no bloquea el MVP. Su activación
futura debe limitarse a composición/configuración de HU004.
