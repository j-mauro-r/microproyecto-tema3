"""
EDA de los datos GEE LST consolidados.
Genera figuras en data/figures/ y estadísticas en consola.
"""

import os, pandas as pd, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

CSV   = r"C:\Users\nilara\Downloads\dengue_project\data\processed\gee_lst_municipios.csv"
FIGS  = r"C:\Users\nilara\Downloads\dengue_project\data\figures"
os.makedirs(FIGS, exist_ok=True)

plt.rcParams.update({'figure.dpi': 120, 'axes.spines.top': False,
                     'axes.spines.right': False})

print("Cargando CSV...")
df = pd.read_csv(CSV, parse_dates=['fecha'], low_memory=False)
df['año']  = df['source_file']
df['mes']  = df['fecha'].dt.month
df['dia_año'] = df['fecha'].dt.dayofyear

print(f"Filas: {len(df):,}  |  Columnas: {list(df.columns)}")
print(f"Rango fechas: {df['fecha'].min().date()} → {df['fecha'].max().date()}")
print(f"Municipios únicos: {df['ADM2_CODE'].nunique():,}")
print(f"Nulos LST: {df['lst_celsius'].isna().mean()*100:.1f}%")

# ── Fig 1: Nulos por año ───────────────────────────────────────────────────
nulos_ano = df.groupby('año')['lst_celsius'].apply(lambda x: x.isna().mean()*100)
fig, ax = plt.subplots(figsize=(13, 4))
ax.bar(nulos_ano.index, nulos_ano.values, color='#5C8DBE', width=0.7)
ax.axhline(nulos_ano.mean(), linestyle='--', color='gray',
           label=f'Promedio {nulos_ano.mean():.1f}%')
ax.set_ylim(0, 100)
ax.set_xlabel('Año')
ax.set_ylabel('% observaciones nulas')
ax.set_title('Porcentaje de datos faltantes por año — LST MODIS (nubosidad)')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(FIGS, '06_gee_nulos_por_ano.png'))
plt.close()
print("Guardado: 06_gee_nulos_por_ano.png")

# ── Fig 2: Temperatura media mensual (todos los municipios) ───────────────
df_notnull = df.dropna(subset=['lst_celsius'])
temp_mes = df_notnull.groupby(['año', 'mes'])['lst_celsius'].mean().reset_index()
temp_mes_global = df_notnull.groupby('mes')['lst_celsius'].mean()

fig, ax = plt.subplots(figsize=(13, 5))
for year in sorted(df['año'].unique()):
    sub = temp_mes[temp_mes['año'] == year]
    ax.plot(sub['mes'], sub['lst_celsius'], alpha=0.3, color='#5C8DBE', linewidth=1)
ax.plot(temp_mes_global.index, temp_mes_global.values,
        color='#BE1D2B', linewidth=2.5, label='Promedio 2007–2024')
ax.set_xticks(range(1, 13))
ax.set_xticklabels(['Ene','Feb','Mar','Abr','May','Jun',
                    'Jul','Ago','Sep','Oct','Nov','Dic'])
ax.set_xlabel('Mes')
ax.set_ylabel('LST promedio (°C)')
ax.set_title('Temperatura superficial mensual — Colombia 2007–2024\n(líneas azules = años individuales, roja = promedio)')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(FIGS, '07_gee_temp_mensual.png'))
plt.close()
print("Guardado: 07_gee_temp_mensual.png")

# ── Fig 3: Serie temporal anual media ─────────────────────────────────────
temp_ano = df_notnull.groupby('año')['lst_celsius'].mean()
fig, ax = plt.subplots(figsize=(13, 4))
ax.plot(temp_ano.index, temp_ano.values, marker='o', color='#1654A2', linewidth=2)
ax.set_xlabel('Año')
ax.set_ylabel('LST promedio (°C)')
ax.set_title('Temperatura superficial promedio anual — Colombia 2007–2024')
ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f°C'))
plt.tight_layout()
plt.savefig(os.path.join(FIGS, '08_gee_temp_por_ano.png'))
plt.close()
print("Guardado: 08_gee_temp_por_ano.png")

# ── Fig 4: Distribución de LST ────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(10, 4))
ax.hist(df_notnull['lst_celsius'], bins=80, color='#5C8DBE', edgecolor='white', linewidth=0.3)
ax.axvline(df_notnull['lst_celsius'].mean(), color='#BE1D2B', linewidth=2,
           label=f"Media {df_notnull['lst_celsius'].mean():.1f}°C")
ax.set_xlabel('LST (°C)')
ax.set_ylabel('Frecuencia')
ax.set_title('Distribución de temperatura superficial — todos los municipios 2007–2024')
ax.legend()
plt.tight_layout()
plt.savefig(os.path.join(FIGS, '09_gee_distribucion_lst.png'))
plt.close()
print("Guardado: 09_gee_distribucion_lst.png")

# ── Fig 5: Top 10 departamentos por temperatura media ─────────────────────
temp_dpto = (df_notnull.groupby('ADM1_NAME')['lst_celsius']
             .mean().sort_values(ascending=False).head(10))
fig, ax = plt.subplots(figsize=(10, 5))
temp_dpto.sort_values().plot.barh(ax=ax, color='#1654A2')
ax.set_xlabel('LST promedio (°C)')
ax.set_title('Top 10 departamentos con mayor temperatura superficial promedio')
ax.xaxis.set_major_formatter(mticker.FormatStrFormatter('%.1f°C'))
plt.tight_layout()
plt.savefig(os.path.join(FIGS, '10_gee_temp_por_dpto.png'))
plt.close()
print("Guardado: 10_gee_temp_por_dpto.png")

# ── Estadísticas de resumen ───────────────────────────────────────────────
print("\n=== ESTADÍSTICAS CLAVE ===")
print(f"Total filas:          {len(df):,}")
print(f"Filas con datos:      {len(df_notnull):,} ({len(df_notnull)/len(df)*100:.1f}%)")
print(f"Municipios:           {df['ADM2_CODE'].nunique():,}")
print(f"Departamentos:        {df['ADM1_NAME'].nunique():,}")
print(f"LST media (°C):       {df_notnull['lst_celsius'].mean():.2f}")
print(f"LST std  (°C):        {df_notnull['lst_celsius'].std():.2f}")
print(f"LST min  (°C):        {df_notnull['lst_celsius'].min():.2f}")
print(f"LST max  (°C):        {df_notnull['lst_celsius'].max():.2f}")
print(f"Nulos promedio/año:   {nulos_ano.mean():.1f}%")
print(f"Nulos max (año):      {nulos_ano.idxmax()} ({nulos_ano.max():.1f}%)")
print(f"Nulos min (año):      {nulos_ano.idxmin()} ({nulos_ano.min():.1f}%)")
