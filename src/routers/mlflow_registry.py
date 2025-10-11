"""
API endpoints для MLflow Model Registry
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from src.mlflow_registry import (
    get_model_by_stage,
    promote_model_to_stage,
    list_registered_models,
    get_model_info,
    compare_model_versions,
    MLFLOW_ENABLED
)

router = APIRouter(prefix="/mlflow", tags=["MLflow Registry"])


class PromoteModelRequest(BaseModel):
    model_name: str = "xgboost_trading_model"
    version: Optional[int] = None
    stage: str = "Production"
    archive_existing: bool = True


@router.get("/status")
def mlflow_status():
    """Проверить статус MLflow интеграции"""
    return {
        "enabled": MLFLOW_ENABLED,
        "tracking_uri": "http://localhost:5000" if MLFLOW_ENABLED else None,
        "message": "MLflow enabled" if MLFLOW_ENABLED else "MLflow not configured (set MLFLOW_TRACKING_URI in .env)"
    }


@router.get("/models")
def get_models():
    """Получить список всех зарегистрированных моделей"""
    if not MLFLOW_ENABLED:
        raise HTTPException(status_code=503, detail="MLflow not enabled")
    
    models = list_registered_models()
    return {
        "status": "ok",
        "models": models,
        "count": len(models)
    }


@router.get("/models/{model_name}")
def get_model_details(model_name: str):
    """Получить детальную информацию о модели"""
    if not MLFLOW_ENABLED:
        raise HTTPException(status_code=503, detail="MLflow not enabled")
    
    info = get_model_info(model_name)
    if info is None:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found")
    
    return {"status": "ok", "model": info}


@router.get("/models/{model_name}/stage/{stage}")
def get_model_by_stage_api(model_name: str, stage: str):
    """Получить модель из указанной стадии"""
    if not MLFLOW_ENABLED:
        raise HTTPException(status_code=503, detail="MLflow not enabled")
    
    if stage not in ["None", "Staging", "Production", "Archived"]:
        raise HTTPException(status_code=400, detail="Invalid stage. Use: None, Staging, Production, Archived")
    
    model_uri = get_model_by_stage(model_name, stage)
    if model_uri is None:
        return {
            "status": "not_found",
            "message": f"No model found for {model_name} in stage '{stage}'"
        }
    
    return {
        "status": "ok",
        "model_name": model_name,
        "stage": stage,
        "model_uri": model_uri
    }


@router.post("/models/promote")
def promote_model(req: PromoteModelRequest):
    """
    Перевести модель на указанную стадию (Staging, Production, Archived)
    
    Пример:
    ```json
    {
      "model_name": "xgboost_trading_model",
      "version": 5,
      "stage": "Production",
      "archive_existing": true
    }
    ```
    """
    if not MLFLOW_ENABLED:
        raise HTTPException(status_code=503, detail="MLflow not enabled")
    
    if req.stage not in ["Staging", "Production", "Archived"]:
        raise HTTPException(status_code=400, detail="Invalid stage. Use: Staging, Production, Archived")
    
    success = promote_model_to_stage(
        model_name=req.model_name,
        version=req.version,
        stage=req.stage,
        archive_existing=req.archive_existing
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="Failed to promote model")
    
    return {
        "status": "ok",
        "message": f"Model {req.model_name} promoted to {req.stage}",
        "model_name": req.model_name,
        "version": req.version,
        "stage": req.stage
    }


@router.get("/models/{model_name}/compare")
def compare_models(
    model_name: str,
    version1: Optional[int] = None,
    version2: Optional[int] = None
):
    """
    Сравнить две версии модели по метрикам
    
    Если версии не указаны:
    - version1 = Production
    - version2 = Staging
    """
    if not MLFLOW_ENABLED:
        raise HTTPException(status_code=503, detail="MLflow not enabled")
    
    comparison = compare_model_versions(model_name, version1, version2)
    if comparison is None:
        raise HTTPException(status_code=404, detail="Failed to compare models (versions not found?)")
    
    return {"status": "ok", "comparison": comparison}

