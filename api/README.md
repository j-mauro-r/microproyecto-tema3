# DengueGrave API

FastAPI para servir predicciones del modelo XGBoost de dengue grave.

## Endpoints

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/health` | Verifica que la API esta activa |
| POST | `/predict` | Prediccion para un municipio y semana |
| POST | `/predict-batch` | Prediccion para hasta 500 filas (CSV) |

## Ejecucion local

```bash
# desde la raiz del repo
pip install -r requirements.txt
python -m api.run_api
# API disponible en http://localhost:8000
# Docs en http://localhost:8000/docs
```

## Variables de entorno

```env
MLFLOW_TRACKING_URI=http://127.0.0.1:5000   # URI del servidor MLflow
MLFLOW_RUN_ID=<run_id>                       # ID del run con el modelo entrenado
MODEL_THRESHOLD=0.35                         # Umbral optimo (actualizar tras training)
MODEL_LOCAL_PATH=model/xgb_model.pkl         # Fallback si MLflow no esta disponible
```

## Ejemplo de peticion

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "COD_MUN_O": 11001,
    "ANO": 2024,
    "SEMANA": 10,
    "grave_lag_1": 2.0,
    "clasico_lag_1": 15.0,
    "zona_canal_lag1": 1.0,
    "es_endemico": 1
  }'
```

## Docker

```bash
docker build -t dengue-api .
docker run -p 8000:8000 \
  -e MLFLOW_RUN_ID=<run_id> \
  -e MLFLOW_TRACKING_URI=http://<EC2_IP>:5000 \
  dengue-api
```
