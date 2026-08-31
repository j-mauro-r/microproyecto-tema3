from pydantic import BaseModel, Field
from typing import Optional


class PredictRequest(BaseModel):
    divipola: str = Field(..., description="Codigo DIVIPOLA de 5 digitos del municipio")
    ANO: int = Field(..., ge=2007, le=2030)
    MES: int = Field(..., ge=1, le=12)
    grave_lag_1: float = Field(0.0, description="Casos graves mes anterior")
    grave_lag_2: float = 0.0
    grave_lag_3: float = 0.0
    grave_lag_4: float = 0.0
    grave_lag_6: float = 0.0
    clasico_lag_1: float = 0.0
    clasico_lag_2: float = 0.0
    clasico_lag_3: float = 0.0
    clasico_lag_4: float = 0.0
    clasico_lag_6: float = 0.0
    grave_roll3: float = 0.0
    clasico_roll3: float = 0.0
    temp_mean_c: Optional[float] = None
    temp_lag_1: Optional[float] = None
    temp_lag_2: Optional[float] = None
    temp_lag_3: Optional[float] = None
    rain_mm_day: Optional[float] = None
    rain_lag_1: Optional[float] = None
    rain_lag_2: Optional[float] = None
    rain_lag_3: Optional[float] = None
    mes_sin: float = 0.0
    mes_cos: float = 1.0
    anio_epidemia: int = 0
    es_endemico: int = 1
    zona_canal_lag1: float = 0.0
    p25: float = 0.0
    p75: float = 0.0
    sir_lag1: Optional[float] = None


class PredictResponse(BaseModel):
    divipola: str
    ANO: int
    MES: int
    prob_grave: float = Field(..., description="Probabilidad de mes con dengue grave (0-1)")
    prediccion: int = Field(..., description="1 = alerta grave, 0 = sin alerta")
    umbral: float = Field(..., description="Umbral de decision utilizado")
