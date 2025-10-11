"""
MLflow Model Registry интеграция для управления моделями
Поддерживает стадии: None, Staging, Production, Archived
"""
import os
import logging
from typing import Optional, Dict, List

# Загрузка переменных окружения из .env
from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)

# Проверяем доступность MLflow
try:
    import mlflow
    from mlflow.tracking import MlflowClient
    MLFLOW_ENABLED = os.getenv("MLFLOW_TRACKING_URI") is not None
    if MLFLOW_ENABLED:
        mlflow.set_tracking_uri(os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000"))
        client = MlflowClient()
        logger.info(f"[mlflow_registry] Tracking enabled: {mlflow.get_tracking_uri()}")
    else:
        client = None
except ImportError:
    MLFLOW_ENABLED = False
    client = None
    logger.info("[mlflow_registry] MLflow not installed")


def get_model_by_stage(model_name: str = "xgboost_trading_model", stage: str = "Production") -> Optional[str]:
    """
    Получить URI модели из Model Registry по стадии
    
    Args:
        model_name: Имя зарегистрированной модели
        stage: Стадия (None, Staging, Production, Archived)
    
    Returns:
        URI модели или None если не найдена
    """
    if not MLFLOW_ENABLED or client is None:
        logger.warning("[mlflow_registry] MLflow not enabled")
        return None
    
    try:
        # Получаем последнюю версию модели на указанной стадии
        model_versions = client.get_latest_versions(model_name, stages=[stage])
        
        if not model_versions:
            logger.info(f"[mlflow_registry] No model found for stage '{stage}'")
            return None
        
        latest_version = model_versions[0]
        model_uri = f"models:/{model_name}/{stage}"
        
        logger.info(f"[mlflow_registry] Found model: {model_name} v{latest_version.version} (stage: {stage})")
        return model_uri
        
    except Exception as e:
        logger.warning(f"[mlflow_registry] Failed to get model: {e}")
        return None


def promote_model_to_stage(
    model_name: str = "xgboost_trading_model",
    version: int = None,
    stage: str = "Production",
    archive_existing: bool = True
) -> bool:
    """
    Перевести модель на указанную стадию
    
    Args:
        model_name: Имя модели
        version: Версия модели (если None, берётся последняя)
        stage: Целевая стадия (Staging, Production, Archived)
        archive_existing: Архивировать ли существующие модели на этой стадии
    
    Returns:
        True если успешно, False иначе
    """
    if not MLFLOW_ENABLED or client is None:
        logger.warning("[mlflow_registry] MLflow not enabled")
        return False
    
    try:
        # Если версия не указана, берём последнюю
        if version is None:
            versions = client.search_model_versions(f"name='{model_name}'")
            if not versions:
                logger.error(f"[mlflow_registry] Model '{model_name}' not found")
                return False
            version = max(int(v.version) for v in versions)
        
        # Архивируем существующие модели на этой стадии
        if archive_existing and stage in ["Staging", "Production"]:
            existing = client.get_latest_versions(model_name, stages=[stage])
            for model_version in existing:
                client.transition_model_version_stage(
                    name=model_name,
                    version=model_version.version,
                    stage="Archived"
                )
                logger.info(f"[mlflow_registry] Archived {model_name} v{model_version.version}")
        
        # Переводим модель на новую стадию
        client.transition_model_version_stage(
            name=model_name,
            version=version,
            stage=stage
        )
        
        logger.info(f"[mlflow_registry] Promoted {model_name} v{version} to {stage}")
        return True
        
    except Exception as e:
        logger.error(f"[mlflow_registry] Failed to promote model: {e}")
        return False


def list_registered_models() -> List[Dict]:
    """
    Получить список всех зарегистрированных моделей
    
    Returns:
        Список словарей с информацией о моделях
    """
    if not MLFLOW_ENABLED or client is None:
        logger.warning("[mlflow_registry] MLflow not enabled")
        return []
    
    try:
        models = []
        for rm in client.search_registered_models():
            # Получаем последние версии для каждой стадии
            latest_versions = {}
            for stage in ["None", "Staging", "Production", "Archived"]:
                versions = client.get_latest_versions(rm.name, stages=[stage])
                if versions:
                    v = versions[0]
                    latest_versions[stage] = {
                        "version": v.version,
                        "run_id": v.run_id,
                        "status": v.status,
                        "creation_timestamp": v.creation_timestamp
                    }
            
            models.append({
                "name": rm.name,
                "latest_versions": latest_versions,
                "description": rm.description or "",
                "creation_timestamp": rm.creation_timestamp,
                "last_updated_timestamp": rm.last_updated_timestamp,
            })
        
        return models
        
    except Exception as e:
        logger.error(f"[mlflow_registry] Failed to list models: {e}")
        return []


def get_model_info(model_name: str = "xgboost_trading_model") -> Optional[Dict]:
    """
    Получить детальную информацию о модели
    
    Args:
        model_name: Имя модели
    
    Returns:
        Словарь с информацией или None
    """
    if not MLFLOW_ENABLED or client is None:
        logger.warning("[mlflow_registry] MLflow not enabled")
        return None
    
    try:
        rm = client.get_registered_model(model_name)
        
        # Получаем все версии
        versions = client.search_model_versions(f"name='{model_name}'")
        
        versions_info = []
        for v in sorted(versions, key=lambda x: int(x.version), reverse=True):
            # Получаем метрики из run
            run = client.get_run(v.run_id)
            metrics = run.data.metrics
            
            versions_info.append({
                "version": v.version,
                "stage": v.current_stage,
                "run_id": v.run_id,
                "status": v.status,
                "creation_timestamp": v.creation_timestamp,
                "metrics": {
                    "accuracy": metrics.get("accuracy"),
                    "roc_auc": metrics.get("roc_auc"),
                    "sharpe_like": metrics.get("sharpe_like"),
                    "total_return": metrics.get("total_return"),
                }
            })
        
        return {
            "name": rm.name,
            "description": rm.description or "",
            "creation_timestamp": rm.creation_timestamp,
            "last_updated_timestamp": rm.last_updated_timestamp,
            "latest_versions": rm.latest_versions,
            "all_versions": versions_info,
        }
        
    except Exception as e:
        logger.error(f"[mlflow_registry] Failed to get model info: {e}")
        return None


def compare_model_versions(
    model_name: str = "xgboost_trading_model",
    version1: int = None,
    version2: int = None
) -> Optional[Dict]:
    """
    Сравнить две версии модели по метрикам
    
    Args:
        model_name: Имя модели
        version1: Первая версия (если None, берётся Production)
        version2: Вторая версия (если None, берётся Staging)
    
    Returns:
        Словарь с результатами сравнения
    """
    if not MLFLOW_ENABLED or client is None:
        logger.warning("[mlflow_registry] MLflow not enabled")
        return None
    
    try:
        # Получаем версии
        if version1 is None:
            prod_versions = client.get_latest_versions(model_name, stages=["Production"])
            if not prod_versions:
                logger.warning("[mlflow_registry] No Production model found")
                return None
            version1 = int(prod_versions[0].version)
        
        if version2 is None:
            stage_versions = client.get_latest_versions(model_name, stages=["Staging"])
            if not stage_versions:
                logger.warning("[mlflow_registry] No Staging model found")
                return None
            version2 = int(stage_versions[0].version)
        
        # Получаем run'ы
        v1 = client.get_model_version(model_name, version1)
        v2 = client.get_model_version(model_name, version2)
        
        run1 = client.get_run(v1.run_id)
        run2 = client.get_run(v2.run_id)
        
        # Сравниваем метрики
        metrics = ["accuracy", "roc_auc", "sharpe_like", "total_return"]
        comparison = {}
        
        for metric in metrics:
            val1 = run1.data.metrics.get(metric, 0)
            val2 = run2.data.metrics.get(metric, 0)
            
            diff = val2 - val1
            diff_pct = (diff / abs(val1) * 100) if val1 != 0 else 0
            
            comparison[metric] = {
                f"version_{version1}": val1,
                f"version_{version2}": val2,
                "difference": diff,
                "difference_pct": diff_pct,
                "better": "v2" if diff > 0 else "v1" if diff < 0 else "equal"
            }
        
        return {
            "model_name": model_name,
            "version1": version1,
            "version2": version2,
            "comparison": comparison,
        }
        
    except Exception as e:
        logger.error(f"[mlflow_registry] Failed to compare models: {e}")
        return None

