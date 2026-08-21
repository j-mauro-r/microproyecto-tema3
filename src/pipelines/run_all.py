"""
Script maestro: extrae xlsx, combina y genera EDA.
Ejecutar desde cualquier ubicación — usa rutas absolutas.
"""

import os, sys, glob, re, time, zipfile, shutil
import pandas as pd
import matplotlib
matplotlib.use("Agg")   # sin interfaz gráfica — guarda como PNG
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

# ── Rutas ──────────────────────────────────────────────────────────────────────
BASE      = r"C:\Users\nilara\Downloads\dengue_project"
RAW_210   = os.path.join(BASE, "data", "raw")
RAW_220   = os.path.join(BASE, "data", "raw", "grave")
PROC      = os.path.join(BASE, "data", "processed")
FIGS      = os.path.join(BASE, "data", "figures")
ZIP_210   = r"C:\Users\nilara\Downloads\Dengue.zip"
ZIP_220   = r"C:\Users\nilara\Downloads\Dengue Grave.zip"

CSV_210     = os.path.join(PROC, "sivigila_dengue_consolidado.csv")
CSV_220     = os.path.join(PROC, "sivigila_dengue_grave_consolidado.csv")
CSV_COMPLETO = os.path.join(PROC, "sivigila_dengue_completo.csv")
CSV_ENDEMICOS = os.path.join(PROC, "municipios_endemicos.csv")
CSV_SEMANAL   = os.path.join(PROC, "dengue_semanal_municipio_completo.csv")

for d in [RAW_210, RAW_220, PROC, FIGS]:
    os.makedirs(d, exist_ok=True)

EPIDEMIC_YEARS = [2010, 2013, 2016, 2019, 2023, 2024]
MIN_YEARS, MIN_CASES = 10, 200

plt.rcParams.update({'figure.dpi': 120, 'axes.spines.top': False,
                     'axes.spines.right': False})


# ══ PASO 1: Extraer xlsx ══════════════════════════════════════════════════════
def extract_xlsx(zip_path, dest_dir, suffix, exclude_years=None):
    print(f"\n[1] Extrayendo {os.path.basename(zip_path)} → {dest_dir}")
    with zipfile.ZipFile(zip_path) as z:
        entries = [n for n in z.namelist() if n.lower().endswith(".xlsx")]
        for entry in entries:
            year_m = re.search(r'\d{4}', os.path.basename(entry))
            if not year_m:
                continue
            year = int(year_m.group())
            if exclude_years and year in exclude_years:
                print(f"  Omitiendo {year}")
                continue
            dest = os.path.join(dest_dir, os.path.basename(entry))
            if os.path.exists(dest):
                print(f"  Ya existe: {os.path.basename(dest)}")
                continue
            with z.open(entry) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"  Extraído: {os.path.basename(dest)}")


# ══ PASO 2: Combinar xlsx en CSV ═════════════════════════════════════════════
def combine_xlsx(src_dir, pattern, output_csv, label):
    print(f"\n[2] Combinando {label} → {os.path.basename(output_csv)}")
    files = sorted(glob.glob(os.path.join(src_dir, pattern)))
    if not files:
        print(f"  ERROR: No se encontraron archivos con patrón {pattern} en {src_dir}")
        return None

    total, first, resumen, t0 = 0, True, [], time.time()
    for path in files:
        fname = os.path.basename(path)
        year = int(re.search(r'\d{4}', fname).group())
        mb = os.path.getsize(path) / 1_048_576
        print(f"  {fname} ({mb:.0f} MB)...", end="", flush=True)
        t1 = time.time()
        df = pd.read_excel(path, engine="openpyxl", dtype=str)
        df.insert(0, "source_file", year)
        rows = len(df)
        total += rows
        resumen.append({"año": year, "filas": rows})
        df.to_csv(output_csv, mode="w" if first else "a",
                  header=first, index=False, encoding="utf-8")
        first = False
        print(f" {rows:,} filas ({time.time()-t1:.0f}s)")

    print(f"  Total: {total:,} filas | {(time.time()-t0)/60:.1f} min")
    return pd.DataFrame(resumen)


# ══ PASO 3: Combinar ambos CSV ════════════════════════════════════════════════
def combine_both():
    print(f"\n[3] Uniendo clásico + grave → {os.path.basename(CSV_COMPLETO)}")
    df_c = pd.read_csv(CSV_210, dtype=str, low_memory=False)
    df_c.insert(1, "tipo_dengue", "clasico")
    df_g = pd.read_csv(CSV_220, dtype=str, low_memory=False)
    df_g.insert(1, "tipo_dengue", "grave")

    dupes = set(df_c["CONSECUTIVE"].dropna()) & set(df_g["CONSECUTIVE"].dropna())
    print(f"  Duplicados por CONSECUTIVE: {len(dupes):,}")

    df = pd.concat([df_c, df_g], ignore_index=True)
    if dupes:
        df["_orden"] = df["tipo_dengue"].map({"grave": 0, "clasico": 1})
        df = (df.sort_values("_orden")
                .drop_duplicates(subset="CONSECUTIVE", keep="first")
                .drop(columns="_orden")
                .reset_index(drop=True))

    df.to_csv(CSV_COMPLETO, index=False, encoding="utf-8")
    print(f"  Total: {len(df):,} filas guardadas")
    return df


# ══ PASO 4: EDA clásico ═══════════════════════════════════════════════════════
def eda_clasico():
    print("\n[4] EDA dengue clásico")
    df = pd.read_csv(CSV_210, dtype=str, low_memory=False)
    df['ANO'] = pd.to_numeric(df['ANO'], errors='coerce')
    df['SEMANA'] = pd.to_numeric(df['SEMANA'], errors='coerce')

    # Casos por año
    por_ano = df.groupby('ANO').size()
    fig, ax = plt.subplots(figsize=(13, 4))
    colors = ['#BE1D2B' if y in EPIDEMIC_YEARS else '#5C8DBE' for y in por_ano.index]
    ax.bar(por_ano.index, por_ano.values, color=colors, width=0.7)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f'{int(x):,}'))
    ax.set_title('Casos dengue clásico por año (2007–2024)')
    ax.set_xlabel('Año')
    ax.set_ylabel('Casos')
    plt.tight_layout()
    plt.savefig(os.path.join(FIGS, "01_clasico_por_ano.png"))
    plt.close()
    print("  Guardado: 01_clasico_por_ano.png")

    # Corredor endémico nacional
    df_ref = df[~df['ANO'].isin(EPIDEMIC_YEARS)]
    semanal = df_ref.groupby(['ANO', 'SEMANA']).size().reset_index(name='casos')
    corredor = semanal.groupby('SEMANA')['casos'].agg(
        p25=lambda x: x.quantile(0.25),
        mediana='median',
        p75=lambda x: x.quantile(0.75)
    ).reset_index()

    fig, ax = plt.subplots(figsize=(13, 5))
    ax.fill_between(corredor['SEMANA'], corredor['p25'], corredor['p75'],
                    alpha=0.25, color='#1A7F37', label='P25–P75')
    ax.plot(corredor['SEMANA'], corredor['mediana'], color='#1A7F37', lw=2, label='Mediana')
    ax.plot(corredor['SEMANA'], corredor['p75'], color='#C27800', lw=1.5,
            linestyle='--', label='P75 (umbral epidémico)')
    ax.set_title('Corredor endémico nacional — período de referencia')
    ax.set_xlabel('Semana epidemiológica')
    ax.set_ylabel('Casos')
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(FIGS, "02_corredor_endemico_nacional.png"))
    plt.close()
    print("  Guardado: 02_corredor_endemico_nacional.png")

    # Municipios endémicos
    anos_con_casos = (df.groupby(['Municipio_ocurrencia', 'COD_MUN_O', 'ANO'])
                       .size().gt(0).groupby(level=[0,1]).sum().rename('anos_con_casos'))
    casos_acum = df.groupby(['Municipio_ocurrencia','COD_MUN_O']).size().rename('casos_acumulados')
    endemicos = pd.concat([anos_con_casos, casos_acum], axis=1).reset_index()
    endemicos = endemicos[(endemicos['anos_con_casos'] >= MIN_YEARS) &
                          (endemicos['casos_acumulados'] >= MIN_CASES)].sort_values('casos_acumulados', ascending=False)
    endemicos.to_csv(CSV_ENDEMICOS, index=False, encoding='utf-8')
    print(f"  Municipios endémicos: {len(endemicos):,}  → {os.path.basename(CSV_ENDEMICOS)}")
    return endemicos


# ══ PASO 5: EDA grave ════════════════════════════════════════════════════════
def eda_grave():
    print("\n[5] EDA dengue grave")
    df = pd.read_csv(CSV_220, dtype=str, low_memory=False)
    df['ANO'] = pd.to_numeric(df['ANO'], errors='coerce')

    por_ano = df.groupby('ANO').size()
    fig, ax = plt.subplots(figsize=(13, 4))
    colors = ['#BE1D2B' if y in EPIDEMIC_YEARS else '#9B3A4A' for y in por_ano.index]
    ax.bar(por_ano.index, por_ano.values, color=colors, width=0.7)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x,_: f'{int(x):,}'))
    ax.set_title('Casos dengue grave por año (2007–2024)')
    ax.set_xlabel('Año')
    ax.set_ylabel('Casos')
    plt.tight_layout()
    plt.savefig(os.path.join(FIGS, "03_grave_por_ano.png"))
    plt.close()
    print("  Guardado: 03_grave_por_ano.png")

    # Tasa de gravedad
    df_c = pd.read_csv(CSV_210, usecols=['ANO'], dtype=str)
    df_c['ANO'] = pd.to_numeric(df_c['ANO'], errors='coerce')
    clasico_ano = df_c.groupby('ANO').size().rename('clasico')
    grave_ano   = df.groupby('ANO').size().rename('grave')
    tasa = pd.concat([clasico_ano, grave_ano], axis=1).dropna()
    tasa['tasa_%'] = (tasa['grave'] / tasa['clasico'] * 100).round(2)

    fig, ax = plt.subplots(figsize=(13, 4))
    ax.plot(tasa.index, tasa['tasa_%'], marker='o', color='#BE1D2B', lw=2)
    ax.axhline(tasa['tasa_%'].mean(), linestyle='--', color='gray',
               label=f"Media {tasa['tasa_%'].mean():.1f}%")
    ax.set_title('Tasa de gravedad por año (grave / clásico)')
    ax.set_xlabel('Año')
    ax.set_ylabel('%')
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(FIGS, "04_tasa_gravedad.png"))
    plt.close()
    print("  Guardado: 04_tasa_gravedad.png")
    return tasa


# ══ PASO 6: EDA combinado ════════════════════════════════════════════════════
def eda_completo():
    print("\n[6] EDA dataset completo")
    df = pd.read_csv(CSV_COMPLETO, dtype=str, low_memory=False)
    df['ANO'] = pd.to_numeric(df['ANO'], errors='coerce')
    df['SEMANA'] = pd.to_numeric(df['SEMANA'], errors='coerce')

    # Clásico vs grave por año
    por_ano_tipo = df.groupby(['ANO','tipo_dengue']).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(13, 5))
    width = 0.4
    x = np.arange(len(por_ano_tipo))
    ax.bar(x - width/2, por_ano_tipo.get('clasico', 0), width, label='Clásico', color='#5C8DBE')
    ax.bar(x + width/2, por_ano_tipo.get('grave',   0), width, label='Grave',   color='#BE1D2B')
    ax.set_xticks(x)
    ax.set_xticklabels(por_ano_tipo.index, rotation=45, ha='right')
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v,_: f'{int(v):,}'))
    ax.set_title('Casos clásico vs grave por año (2007–2024)')
    ax.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(FIGS, "05_clasico_vs_grave.png"))
    plt.close()
    print("  Guardado: 05_clasico_vs_grave.png")

    # Tabla semanal por municipio
    tabla_semanal = (df.groupby(['COD_MUN_O','Municipio_ocurrencia',
                                 'Departamento_ocurrencia','ANO','SEMANA','tipo_dengue'])
                      .size().unstack(fill_value=0).reset_index())
    tabla_semanal.columns.name = None
    tabla_semanal.to_csv(CSV_SEMANAL, index=False, encoding='utf-8')
    print(f"  Tabla semanal: {len(tabla_semanal):,} filas → {os.path.basename(CSV_SEMANAL)}")


# ══ MAIN ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    t_total = time.time()

    extract_xlsx(ZIP_210, RAW_210, "_210")
    extract_xlsx(ZIP_220, RAW_220, "_220", exclude_years=[2025])

    r1 = combine_xlsx(RAW_210, "Datos_*_210.xlsx", CSV_210, "dengue clásico (210)")
    r2 = combine_xlsx(RAW_220, "Datos_*_220.xlsx", CSV_220, "dengue grave (220)")

    df_completo = combine_both()

    endemicos = eda_clasico()
    tasa      = eda_grave()
    eda_completo()

    print(f"\n{'='*55}")
    print(f"COMPLETADO en {(time.time()-t_total)/60:.1f} min")
    print(f"\nCSVs generados:")
    for csv in [CSV_210, CSV_220, CSV_COMPLETO, CSV_ENDEMICOS, CSV_SEMANAL]:
        if os.path.exists(csv):
            mb = os.path.getsize(csv) / 1_048_576
            print(f"  {os.path.basename(csv):50s} {mb:.0f} MB")
    print(f"\nFiguras guardadas en: {FIGS}")
    for f in sorted(os.listdir(FIGS)):
        print(f"  {f}")
