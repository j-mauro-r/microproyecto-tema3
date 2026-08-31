# Cómo correr el proyecto — Entrega 2

## 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

## 2. Descargar datos

```bash
make download   # usa kagglehub; requiere KAGGLE_USERNAME y KAGGLE_KEY en .env
```

O manualmente desde Kaggle: `saballesteros/maia4331-2614-grupo19`

## 3. Ejecutar los notebooks en orden

```
01 → 08   EDA y preparación de datos (ya ejecutados)
09        Feature engineering → genera data/processed/dengue_features_modelado.csv
10        Modelo XGBoost + MLflow → genera model/xgb_model.pkl y figuras 12-14
```

## 4. Correr la API

```bash
# Asegúrate de que model/xgb_model.pkl existe (generado por notebook 10)
python -m api.run_api
# Docs en http://localhost:8000/docs
```

## 5. Correr el dashboard

```bash
# En otra terminal
streamlit run dashboard/app.py
# Dashboard en http://localhost:8501
```

## 6. Docker (opcional)

```bash
cd docker
docker-compose up --build
# API: http://localhost:8000/docs
# Dashboard: http://localhost:8501
```

## 7. MLflow en EC2

Ver `docs/setup_ec2_mlflow.md` para instrucciones de configuración de la instancia.
Una vez configurada, cambiar en `notebooks/10_Modelo_XGBoost.ipynb`:

```python
MLFLOW_TRACKING_URI = "http://<IP_EC2>:5000"
```

y re-ejecutar el notebook.
