# BIOMAC — Prueba funcional del dashboard antes del merge de PR #33

**Estado:** plan manual de validación pre-merge  
**Rama objetivo:** `test/api-functional-e2e-local` (PR #33)  
**Dashboard:** `dashboard_prototipos/dengue-watch-pro`  
**Backend:** FastAPI `/api/v2`  
**Objetivo:** validar por separado la integración visual del dashboard con resultados conocidos y el ciclo técnico completo de inferencia, sin agregar funcionalidades nuevas al dashboard.

---

## 1. Decisión de alcance

Para Entrega 2 se mantiene el dashboard con las funcionalidades actuales. **No se implementará carga de archivos desde la UI ni se agregará una funcionalidad de ejecución manual del modelo en Lovable.**

La prueba se divide formalmente en dos partes:

```text
P1 — Integración visual
ChampionResult conocido
→ API
→ SQLite
→ GET latest/history
→ Dashboard
```

```text
P2 — E2E técnico
Input mensual preconfigurado
→ API / proceso técnico de prueba
→ Champion
→ ChampionResult
→ persistencia API
→ Dashboard GET latest
```

Esta separación evita acoplar el frontend al modelo y evita que abrir/refrescar la página dispare inferencia.

---

## 2. Comportamiento vigente del dashboard

El dashboard opera así:

```text
Browser
→ DengueDashboard
→ useDengueDashboard
→ React Query
→ HttpDengueRepository
→ FastAPI /api/v2
```

Reglas relevantes:

- la ruta principal es `/`;
- `VITE_BIOMAC_API_BASE_URL` debe incluir `/api/v2`;
- al abrir la pantalla se consulta `GET /predictions/latest`;
- también se consulta `GET /predictions/history?limit=12`;
- `Actualizar vista` solo vuelve a consultar `latest`;
- el dashboard no debe calcular `probability`, `threshold` ni `label`;
- Bucaramanga y Cali muestran T+1 y T+2;
- la UI debe reflejar exactamente los valores persistidos por el API;
- no existe fallback productivo a mocks.

**Nota:** aunque el código actual pueda conservar elementos de carga mensual, esta prueba no depende de ellos ni exige incorporarlos al producto final.

---

## 3. Evidencia inicial obligatoria

### E00 — Dashboard local antes de interacción efectiva con API

**Dónde:** Browser local.

1. Ejecutar el dashboard local.
2. Mantener FastAPI apagado.
3. Abrir la pantalla.
4. Confirmar que no aparecen datos mock como si fueran reales.

**Evidencia:** captura completa `E00-dashboard-api-off.png`.

**Resultado esperado:** estado explícito de API no disponible.

### E01 — API activa y SQLite vacío

**Dónde:** Terminal API + Browser.

1. Levantar FastAPI con una base SQLite nueva.
2. No cargar ningún resultado todavía.
3. Recargar el dashboard.

**Evidencia:** `E01-dashboard-empty.png`.

**Resultado esperado:** estado sin predicciones persistidas.

Estas dos capturas constituyen la línea base visual “antes”.

---

# PARTE 1 — Integración visual: resultado conocido → API → dashboard

## 4. Objetivo P1

Demostrar que el dashboard representa correctamente un `ChampionResult` conocido cuando el resultado ya fue producido por el modelo.

P1 **no prueba inferencia**. Prueba:

```text
ChampionResult
→ API
→ SQLite
→ latest/history
→ Dashboard
```

La carga técnica del resultado se realiza desde terminal/API; no desde la UI.

---

## 5. Escenarios visuales mínimos

Para clasificar una ciudad se usará T+2:

```text
T+2 = EXCESO     → ciudad con alerta
T+2 = NO_EXCESO  → ciudad normal
```

| Escenario | Cali T+2 | Bucaramanga T+2 |
|---|---|---|
| P1-S01 | `EXCESO` | `NO_EXCESO` |
| P1-S02 | `NO_EXCESO` | `EXCESO` |
| P1-S03 | `NO_EXCESO` | `NO_EXCESO` |

Siempre se deben registrar también T+1, probability, threshold, target month, model version, run_id y reference_month.

El Champion real actualmente validado para `2025-12` corresponde a P1-S02:

```text
Bucaramanga T+1 = 0.7347 / 0.34 / EXCESO
Bucaramanga T+2 = 0.6724 / 0.27 / EXCESO
Cali T+1         = 0.0132 / 0.34 / NO_EXCESO
Cali T+2         = 0.0150 / 0.27 / NO_EXCESO
```

---

## 6. Integridad de P1

Se deben priorizar resultados reales del Champion.

No modificar manualmente para forzar un escenario:

- `probability`;
- `threshold`;
- `label`;
- `feature_contract_version`;
- `feature_contract_sha256`.

Si no existe un periodo real para alguno de los tres patrones, puede utilizarse un fixture controlado **solo para validar UI/contrato**, marcándolo claramente como tal. No debe presentarse como inferencia real.

---

## 7. Ejecución P1

### P1.1 Preparar entorno

**Dónde:** Terminal, raíz del repositorio.

```bash
git switch test/api-functional-e2e-local
git status
mkdir -p runtime/dashboard-test/evidence
mkdir -p runtime/dashboard-test/scenarios
rm -f runtime/dashboard-test/biomac-dashboard-test.db
```

### P1.2 Configurar frontend

**Dónde:** `dashboard_prototipos/dengue-watch-pro/`.

`.env.local`:

```text
VITE_BIOMAC_API_BASE_URL=http://127.0.0.1:8001/api/v2
```

Ejecutar:

```bash
pnpm dev --host 127.0.0.1
```

### P1.3 Ejecutar cada escenario

Para cada P1-S01/P1-S02/P1-S03:

1. seleccionar/generar el `ChampionResult` correspondiente;
2. iniciar la composición local del API apuntando a ese JSON;
3. persistir el escenario mediante el mecanismo técnico disponible en la API/prueba funcional;
4. comprobar HTTP `201 COMPLETED` o persistencia equivalente aprobada;
5. abrir/refrescar el dashboard;
6. verificar Bucaramanga;
7. verificar Cali;
8. verificar historial y trazabilidad.

**No realizar inferencia del modelo durante P1.**

### Evidencia por escenario

Guardar como mínimo:

```text
P1-S01-api.png
P1-S01-bucaramanga.png
P1-S01-cali.png
P1-S02-api.png
P1-S02-bucaramanga.png
P1-S02-cali.png
P1-S03-api.png
P1-S03-bucaramanga.png
P1-S03-cali.png
P1-history-final.png
```

Cada captura visual debe permitir observar, cuando aplique:

- ciudad;
- T+1/T+2;
- label;
- probability;
- threshold;
- reference month;
- Champion/model version;
- run_id.

---

# PARTE 2 — E2E técnico: input → modelo → API → dashboard

## 8. Objetivo P2

Demostrar una vez el ciclo técnico completo sin incorporar nuevas funcionalidades al dashboard:

```text
Input mensual preconfigurado
→ trigger técnico desde terminal/script/API
→ Champion ejecuta inferencia
→ ChampionResult
→ API valida contrato
→ SQLite
→ GET latest
→ Dashboard
```

El dashboard continúa siendo únicamente consumidor del API.

---

## 9. Restricciones arquitectónicas P2

Está prohibido para esta prueba:

```text
abrir dashboard
→ ejecutar automáticamente modelo
```

También se evita:

- hardcodear features de inferencia en Lovable;
- invocar directamente XGBoost desde React;
- hacer que Refresh ejecute inferencia;
- enviar archivos desde la UI como requisito del Entregable 2;
- acoplar componentes visuales a scripts/modelos.

El trigger técnico debe quedar fuera del frontend.

---

## 10. Ejecución P2

### P2.1 Preparar un input real

**Dónde:** Terminal / entorno del modelo.

Seleccionar un `reference_month` válido y construir el input mensual requerido por el Champion con Bucaramanga y Cali y las 39 features contractuales.

Registrar:

```text
reference_month
feature_contract_version
feature_contract_sha256
fuente del input
```

### P2.2 Ejecutar la inferencia

**Dónde:** Terminal/script técnico del repositorio.

Ejecutar el Champion con ese input y generar un `ChampionResult` real.

Registrar como evidencia:

```text
model_name
model_version
reference_month
4 predicciones
probability
threshold
label
target_month
feature contract
```

**Evidencia:** `P2-inferencia.png` o log equivalente.

### P2.3 Pasar resultado al API

**Dónde:** Terminal/API local.

El API debe consumir el resultado mediante la frontera definida en HU004, validar el feature contract y persistir el nuevo snapshot.

Esperado:

```text
COMPLETED
4 predictions
latest actualizado
```

**Evidencia:** `P2-api-completed.png`.

### P2.4 Visualizar en dashboard

**Dónde:** Browser.

1. abrir/refrescar el dashboard;
2. seleccionar Bucaramanga;
3. validar T+1/T+2 contra el ChampionResult;
4. seleccionar Cali;
5. validar T+1/T+2;
6. comprobar corte, model version, run_id e historial.

**Evidencias:**

```text
P2-dashboard-bucaramanga.png
P2-dashboard-cali.png
P2-history.png
```

### P2.5 Read-only final

Pulsar **Actualizar vista**.

Esperado:

```text
GET latest
→ mismo snapshot
→ ningún nuevo run
→ ninguna nueva inferencia
```

Registrar conteo de runs antes/después o log HTTP.

**Evidencia:** `P2-refresh-read-only.png`.

---

## 11. Matriz de evidencia

| ID | Parte | Evidencia | Demuestra |
|---|---|---|---|
| E00 | Baseline | dashboard API apagada | no fallback mock |
| E01 | Baseline | API activa, DB vacía | conexión real sin datos |
| P1-S01 | Visual | Cali alerta / Bucaramanga normal | render patrón 1 |
| P1-S02 | Visual | Bucaramanga alerta / Cali normal | render patrón 2 |
| P1-S03 | Visual | ambas normales | render patrón 3 |
| P1-H | Visual | historial | persistencia de escenarios |
| P2-I | E2E | inferencia | modelo ejecutado con input real |
| P2-A | E2E | API COMPLETED | resultado aceptado/persistido |
| P2-D | E2E | dashboard | resultado técnico visible |
| P2-R | E2E | Refresh | lectura sin inferencia |

---

## 12. Criterios de aceptación

La prueba se considera **CERRADA** únicamente si:

### Parte 1

- [ ] E00 demuestra que el dashboard no presenta mocks cuando API no está disponible.
- [ ] E01 demuestra conexión real con API y ausencia inicial de snapshots.
- [ ] P1-S01 muestra Cali `EXCESO` T+2 y Bucaramanga `NO_EXCESO` T+2.
- [ ] P1-S02 muestra Cali `NO_EXCESO` T+2 y Bucaramanga `EXCESO` T+2.
- [ ] P1-S03 muestra ambas ciudades `NO_EXCESO` T+2.
- [ ] T+1/T+2, probability y threshold coinciden con la fuente del escenario.
- [ ] el dashboard no recalcula labels.
- [ ] latest corresponde al run más reciente.
- [ ] history conserva los escenarios completados.
- [ ] no se requiere carga de archivos desde la UI.

### Parte 2

- [ ] se usa un input mensual real/preconfigurado compatible con el Champion.
- [ ] la inferencia se dispara fuera del frontend.
- [ ] el Champion produce 4 predicciones reales.
- [ ] feature contract input ↔ Champion coincide exactamente.
- [ ] el API acepta/persiste el resultado sin alterar probability/threshold/label.
- [ ] `latest` devuelve el nuevo run.
- [ ] Bucaramanga y Cali muestran los valores exactos del ChampionResult.
- [ ] Refresh no crea un nuevo run.
- [ ] Refresh no dispara inferencia.
- [ ] no se agregaron funcionalidades nuevas al dashboard para hacer pasar la prueba.

### Cierre global

```text
P1 INTEGRACIÓN VISUAL: APROBADO / NO APROBADO
P2 E2E TÉCNICO:       APROBADO / NO APROBADO
PRUEBA DASHBOARD:     CERRADA / NO CERRADA
```

---

## 13. Decisión final de arquitectura

El dashboard permanece como capa de presentación y consumo:

```text
Dashboard
→ GET latest/history
→ API
```

La inferencia pertenece al backend/proceso técnico:

```text
Input mensual
→ Champion
→ ChampionResult
→ API/persistencia
```

La prueba no debe introducir una dependencia permanente frontend → modelo únicamente para demostrar el flujo de Entrega 2.