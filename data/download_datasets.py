# Descarga los datasets consolidados desde Kaggle y los guarda en data/raw
#
# Antes de ejecutar este script:
# 1. Copia example.env a .env (en la raiz del proyecto)
# 2. En https://www.kaggle.com/settings -> API -> Create New Token LEGACY,
#    descarga tu token y completa KAGGLE_USERNAME y KAGGLE_KEY en el .env
# 3. Instala las dependencias: pip install -r requirements.txt

import shutil
from pathlib import Path

from dotenv import load_dotenv
import kagglehub

load_dotenv()

ruta_raw = Path(__file__).parent / "raw"

# Download latest version
path = Path(kagglehub.dataset_download("saballesteros/maia4331-2614-grupo19"))

for archivo in path.glob("*.csv"):
    shutil.copy2(archivo, ruta_raw / archivo.name)

print("Archivos guardados en:", ruta_raw)
