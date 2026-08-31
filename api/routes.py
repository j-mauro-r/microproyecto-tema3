import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from api.schemas import PredictRequest, PredictResponse
from api.model_loader import load_model, FEATURE_COLS, DEFAULT_THRESHOLD

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        model = load_model()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    row = {col: getattr(req, col, None) for col in FEATURE_COLS}
    X = pd.DataFrame([row])[FEATURE_COLS]

    prob = float(model.predict_proba(X)[0, 1])
    pred = int(prob >= DEFAULT_THRESHOLD)

    return PredictResponse(
        divipola=req.divipola,
        ANO=req.ANO,
        MES=req.MES,
        prob_grave=round(prob, 4),
        prediccion=pred,
        umbral=DEFAULT_THRESHOLD,
    )


@router.post("/predict-batch")
def predict_batch(requests: list[PredictRequest]):
    if len(requests) > 500:
        raise HTTPException(status_code=400, detail="Maximo 500 filas por batch")

    try:
        model = load_model()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))

    rows = [{col: getattr(r, col, None) for col in FEATURE_COLS} for r in requests]
    X = pd.DataFrame(rows)[FEATURE_COLS]
    probs = model.predict_proba(X)[:, 1]

    return [
        {
            "divipola": req.divipola,
            "ANO": req.ANO,
            "MES": req.MES,
            "prob_grave": round(float(p), 4),
            "prediccion": int(p >= DEFAULT_THRESHOLD),
        }
        for req, p in zip(requests, probs)
    ]
