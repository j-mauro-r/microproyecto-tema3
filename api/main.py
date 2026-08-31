from fastapi import FastAPI
from api.routes import router

app = FastAPI(
    title="DengueGrave API",
    description="Predicción de semanas con dengue grave por municipio — Grupo 11 MAIA PDS",
    version="0.1.0",
)

app.include_router(router)
