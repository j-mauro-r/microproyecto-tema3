"""
Combina los CSV anuales de GEE LST (2007-2024) en un único CSV.
Convierte la columna 'mean' a grados Celsius (mean * 0.02 - 273.15).
Lee directamente desde el zip sin extraer.
"""

import zipfile, io, os, re, time
import pandas as pd

ZIP        = r"C:\Users\nilara\Downloads\google_earth.zip"
OUTPUT_CSV = r"C:\Users\nilara\Downloads\dengue_project\data\processed\gee_lst_municipios.csv"
EXCLUDE_YEARS = [2025]

os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

total, first = 0, True
resumen = []
t0 = time.time()

with zipfile.ZipFile(ZIP) as z:
    entries = sorted([n for n in z.namelist() if n.lower().endswith('.csv')])
    print(f"Archivos encontrados: {len(entries)}")

    for entry in entries:
        year_m = re.search(r'\d{4}', os.path.basename(entry))
        if not year_m:
            continue
        year = int(year_m.group())
        if year in EXCLUDE_YEARS:
            print(f"  {year}: omitido")
            continue

        print(f"  {year}...", end="", flush=True)
        t1 = time.time()

        with z.open(entry) as f:
            df = pd.read_csv(f)

        df.insert(0, "source_file", year)
        # Convertir LST a Celsius
        df['lst_celsius'] = df['mean'] * 0.02 - 273.15
        df = df.drop(columns=['mean'])

        rows = len(df)
        total += rows
        resumen.append({'año': year, 'filas': rows,
                        'nulos_%': round(df['lst_celsius'].isna().mean()*100, 1)})

        df.to_csv(OUTPUT_CSV, mode='w' if first else 'a',
                  header=first, index=False, encoding='utf-8')
        first = False

        print(f" {rows:,} filas  nulos: {df['lst_celsius'].isna().mean()*100:.1f}%  ({time.time()-t1:.0f}s)")

print(f"\nTotal: {total:,} filas | {(time.time()-t0)/60:.1f} min")
print(f"CSV: {OUTPUT_CSV}  ({os.path.getsize(OUTPUT_CSV)/1_048_576:.0f} MB)")

df_res = pd.DataFrame(resumen)
print("\nResumen:")
print(df_res.to_string(index=False))
