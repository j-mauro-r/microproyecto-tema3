"""
Dashboard de alerta temprana de dengue grave — Grupo 11 MAIA PDS
Ejecutar: streamlit run dashboard/app.py
"""
import streamlit as st
import pandas as pd
import numpy as np
import requests
import json
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Alerta Dengue Grave",
    page_icon="🦟",
    layout="wide",
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("🦟 Dengue Grave — Alerta Temprana")
st.sidebar.caption("Grupo 11 · MAIA PDS · Uniandes 2026")
pagina = st.sidebar.radio("Navegacion", ["Prediccion individual", "Prediccion por lote", "Acerca del modelo"])

# ── Pagina 1: Prediccion individual ──────────────────────────────────────────
if pagina == "Prediccion individual":
    st.title("Prediccion de semana con dengue grave")
    st.markdown(
        "Ingresa los datos del municipio y la semana epidemiologica para obtener "
        "la probabilidad de que ocurra al menos un caso de dengue grave."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        cod_mun = st.number_input("Codigo municipio (COD_MUN_O)", min_value=1, value=11001, step=1)
        ano     = st.number_input("Ano", min_value=2007, max_value=2030, value=2024)
        semana  = st.number_input("Semana epidemiologica", min_value=1, max_value=53, value=1)

    with col2:
        st.subheader("Rezagos dengue grave")
        g1 = st.number_input("grave_lag_1 (semana -1)", min_value=0.0, value=0.0)
        g2 = st.number_input("grave_lag_2 (semana -2)", min_value=0.0, value=0.0)
        g4 = st.number_input("grave_lag_4 (semana -4)", min_value=0.0, value=0.0)
        g8 = st.number_input("grave_lag_8 (semana -8)", min_value=0.0, value=0.0)

    with col3:
        st.subheader("Rezagos dengue clasico")
        c1 = st.number_input("clasico_lag_1", min_value=0.0, value=0.0)
        c4 = st.number_input("clasico_lag_4", min_value=0.0, value=0.0)
        es_endemico   = st.selectbox("Municipio endemico", [1, 0])
        zona_canal    = st.number_input("Zona canal (0=normal, 1=alerta, 2=exceso)", min_value=0.0, max_value=2.0, value=0.0)

    sem_rad = semana * 2 * np.pi / 52
    payload = {
        "COD_MUN_O": int(cod_mun),
        "ANO": int(ano),
        "SEMANA": int(semana),
        "grave_lag_1": g1, "grave_lag_2": g2, "grave_lag_3": 0.0,
        "grave_lag_4": g4, "grave_lag_8": g8,
        "clasico_lag_1": c1, "clasico_lag_2": 0.0, "clasico_lag_3": 0.0,
        "clasico_lag_4": c4, "clasico_lag_8": 0.0,
        "grave_roll4": g1 + g2 + g4, "clasico_roll4": c1 + c4,
        "lst_media": None, "lst_lag_1": None, "lst_lag_2": None, "lst_lag_4": None,
        "semana_sin": float(np.sin(sem_rad)),
        "semana_cos": float(np.cos(sem_rad)),
        "anio_epidemia": int(ano - 2007),
        "es_endemico": es_endemico,
        "zona_canal_lag1": zona_canal,
        "p25": 0.0, "p75": 0.0,
        "sir_lag1": None,
    }

    if st.button("Predecir", type="primary"):
        try:
            resp = requests.post(f"{API_URL}/predict", json=payload, timeout=10)
            if resp.status_code == 200:
                res = resp.json()
                prob = res["prob_grave"]
                pred = res["prediccion"]

                st.divider()
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    color = "red" if pred == 1 else "green"
                    label = "ALERTA GRAVE" if pred == 1 else "Sin alerta"
                    st.markdown(f"### :{color}[{label}]")
                    st.metric("Probabilidad de dengue grave", f"{prob*100:.1f}%")
                    st.caption(f"Umbral de decision: {res['umbral']}")
                with col_r2:
                    st.progress(prob)
                    if pred == 1:
                        st.warning("Se recomienda activar vigilancia epidemiologica reforzada.")
                    else:
                        st.success("Nivel de riesgo bajo segun el modelo.")
            else:
                st.error(f"Error API ({resp.status_code}): {resp.text}")
        except requests.exceptions.ConnectionError:
            st.error(f"No se pudo conectar a la API en {API_URL}. Verifica que este corriendo.")

# ── Pagina 2: Prediccion por lote ─────────────────────────────────────────────
elif pagina == "Prediccion por lote":
    st.title("Prediccion por lote (CSV)")
    st.markdown(
        "Sube un archivo CSV con las columnas de features del modelo. "
        "Deben incluir al menos: `COD_MUN_O`, `ANO`, `SEMANA`, y las variables de rezago."
    )

    uploaded = st.file_uploader("Selecciona un CSV", type=["csv"])
    if uploaded:
        df_in = pd.read_csv(uploaded)
        st.write(f"Filas cargadas: {len(df_in):,}")
        st.dataframe(df_in.head())

        if st.button("Enviar a la API", type="primary"):
            if len(df_in) > 500:
                st.warning("Se enviaran solo las primeras 500 filas.")
                df_in = df_in.head(500)

            records = df_in.fillna(value=np.nan).where(df_in.notna(), None).to_dict(orient="records")
            try:
                resp = requests.post(f"{API_URL}/predict-batch", json=records, timeout=30)
                if resp.status_code == 200:
                    df_out = pd.DataFrame(resp.json())
                    st.success(f"{len(df_out)} predicciones recibidas.")
                    st.dataframe(df_out)

                    csv_out = df_out.to_csv(index=False).encode("utf-8")
                    st.download_button("Descargar resultados", csv_out, "predicciones.csv", "text/csv")
                else:
                    st.error(f"Error ({resp.status_code}): {resp.text}")
            except requests.exceptions.ConnectionError:
                st.error(f"No se pudo conectar a la API en {API_URL}.")

# ── Pagina 3: Acerca del modelo ───────────────────────────────────────────────
else:
    st.title("Acerca del modelo")
    st.markdown("""
### Sistema de alerta temprana de dengue grave — Grupo 11

**Problema:** Predecir si una semana epidemiologica en un municipio colombiano tendra al menos
un caso de dengue grave (COD_EVE 220), con una semana de anticipacion.

**Datos:**
- SIVIGILA: 48,823 casos de dengue grave (2007-2024), 621 municipios endemicos
- GEE/MODIS: temperatura superficial del suelo (LST) por municipio y semana

**Modelo:** XGBoost clasificador binario
- 26 features de rezago temporal, climaticas y epidemiologicas
- Manejo de desbalance con `scale_pos_weight` (~9:1)
- Experimentos versionados con MLflow en AWS EC2

**Particion temporal:**
| Conjunto | Periodo | Filas |
|---|---|---|
| Entrenamiento | 2007-2021 | ~190,000 |
| Validacion | 2022 | ~12,600 |
| Prueba | 2023-2024 | ~44,200 |

**Features principales:**
- `grave_lag_1/2/4/8`: casos graves en semanas previas
- `clasico_lag_1/4`: casos clasicos en semanas previas
- `zona_canal_lag1`: zona del canal endemico (Bortman 1999)
- `sir_lag1`: razon de incidencia estandarizada
- `lst_media/lag`: temperatura superficial MODIS

---
*MAIA Proyecto de Desarrollo de Soluciones — Uniandes 2026*
    """)
