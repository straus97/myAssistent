"""
API endpoints для векторизованного бэктестинга.

Endpoints:
- POST /backtest/run - Запуск бэктеста
- GET /backtest/results/{run_id} - Получить результаты
- GET /backtest/list - Список всех бэктестов
- DELETE /backtest/results/{run_id} - Удалить результаты
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
import json
from pathlib import Path
import logging

from ..db import get_db
from ..dependencies import require_api_key
from ..backtest import run_vectorized_backtest, save_backtest_results

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/backtest", tags=["Backtest"])


# ============================
# Pydantic Models
# ============================

class BacktestRequest(BaseModel):
    """Запрос на запуск бэктеста."""
    exchange: str = Field(..., description="Биржа (binance, bybit)")
    symbol: str = Field(..., description="Торговая пара (BTC/USDT, ETH/USDT)")
    timeframe: str = Field(..., description="Таймфрейм (1h, 4h, 1d)")
    start_date: str = Field(..., description="Дата начала (YYYY-MM-DD)")
    end_date: str = Field(..., description="Дата окончания (YYYY-MM-DD)")
    model_path: Optional[str] = Field(None, description="Путь к модели (если None - используем последнюю)")
    signal_threshold: float = Field(0.5, ge=0.0, le=1.0, description="Порог для BUY сигнала")
    
    # Конфигурация бэктеста
    initial_capital: float = Field(1000.0, gt=0, description="Начальный капитал (USDT)")
    commission_bps: float = Field(8.0, ge=0, description="Комиссии в базисных пунктах")
    slippage_bps: float = Field(5.0, ge=0, description="Проскальзывание в базисных пунктах")
    latency_bars: int = Field(1, ge=0, description="Задержка исполнения (баров)")
    position_size: float = Field(1.0, ge=0.0, le=1.0, description="Размер позиции (доля капитала)")

    class Config:
        json_schema_extra = {
            "example": {
                "exchange": "binance",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "start_date": "2024-01-01",
                "end_date": "2025-01-01",
                "model_path": None,
                "signal_threshold": 0.6,
                "initial_capital": 1000.0,
                "commission_bps": 8.0,
                "slippage_bps": 5.0,
                "latency_bars": 1,
                "position_size": 1.0,
            }
        }


class BacktestResponse(BaseModel):
    """Результаты бэктеста."""
    success: bool
    error: Optional[str] = None
    run_id: Optional[str] = None
    metrics: Optional[Dict] = None
    equity_curve: Optional[List[Dict]] = None
    trades: Optional[List[Dict]] = None
    benchmark: Optional[Dict] = None
    config: Optional[Dict] = None


class BacktestListItem(BaseModel):
    """Элемент списка бэктестов."""
    run_id: str
    exchange: str
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    total_return: float
    sharpe_ratio: float
    max_drawdown: float


# ============================
# Endpoints
# ============================

@router.post("/run", response_model=BacktestResponse, dependencies=[Depends(require_api_key)])
def run_backtest_endpoint(
    request: BacktestRequest,
    db: Session = Depends(get_db),
):
    """
    Запускает векторизованный бэктест стратегии.

    **Функционал:**
    - Векторизованная симуляция через pandas (быстро)
    - Реалистичные комиссии и проскальзывание
    - Latency (задержка исполнения)
    - Метрики: Sharpe, Sortino, Calmar, Max DD, Win Rate
    - Сравнение с buy-and-hold

    **Критерии успеха:**
    - Sharpe > 1.5 (хорошая стратегия)
    - Max DD < 20% (контролируемый риск)
    - Win Rate > 55%
    - Outperforms buy-and-hold

    **Пример:**
    ```json
    {
      "exchange": "binance",
      "symbol": "BTC/USDT",
      "timeframe": "1h",
      "start_date": "2024-01-01",
      "end_date": "2025-01-01",
      "initial_capital": 1000
    }
    ```
    """
    logger.info(f"[backtest] Starting backtest: {request.exchange} {request.symbol} {request.timeframe}")

    # Формируем конфигурацию
    config = {
        "initial_capital": request.initial_capital,
        "commission_bps": request.commission_bps,
        "slippage_bps": request.slippage_bps,
        "latency_bars": request.latency_bars,
        "position_size": request.position_size,
    }

    # Запускаем бэктест
    try:
        results = run_vectorized_backtest(
            db=db,
            exchange=request.exchange,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            model_path=request.model_path,
            signal_threshold=request.signal_threshold,
            config=config,
        )
    except Exception as e:
        logger.error(f"[backtest] Failed to run backtest: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to run backtest: {str(e)}")

    if not results["success"]:
        logger.error(f"[backtest] Backtest failed: {results['error']}")
        raise HTTPException(status_code=400, detail=results["error"])

    # Сохраняем результаты
    try:
        filepath = save_backtest_results(results)
        run_id = Path(filepath).stem  # backtest_20250101_120000
    except Exception as e:
        logger.warning(f"[backtest] Failed to save results: {e}")
        run_id = "unsaved"

    logger.info(f"[backtest] Completed. Run ID: {run_id}, Sharpe: {results['metrics']['sharpe_ratio']:.2f}")

    return BacktestResponse(
        success=True,
        error=None,
        run_id=run_id,
        metrics=results["metrics"],
        equity_curve=results["equity_curve"],
        trades=results["trades"],
        benchmark=results["benchmark"],
        config=results["config"],
    )


@router.get("/results/{run_id}", response_model=BacktestResponse, dependencies=[Depends(require_api_key)])
def get_backtest_results(run_id: str):
    """
    Получает результаты сохранённого бэктеста.

    **Параметры:**
    - run_id: ID бэктеста (например, backtest_20250101_120000)

    **Пример:**
    ```
    GET /backtest/results/backtest_20250101_120000
    ```
    """
    filepath = Path("artifacts/backtest") / f"{run_id}.json"

    if not filepath.exists():
        logger.error(f"[backtest] Results not found: {run_id}")
        raise HTTPException(status_code=404, detail=f"Backtest results not found: {run_id}")

    try:
        with open(filepath, "r") as f:
            results = json.load(f)
    except Exception as e:
        logger.error(f"[backtest] Failed to load results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load results: {str(e)}")

    return BacktestResponse(
        success=True,
        error=None,
        run_id=run_id,
        metrics=results.get("metrics"),
        equity_curve=None,  # Не сохраняем equity curve в JSON (слишком большой)
        trades=results.get("trades"),
        benchmark=results.get("benchmark"),
        config=results.get("config"),
    )


@router.get("/list", dependencies=[Depends(require_api_key)])
def list_backtests(
    limit: int = Query(20, ge=1, le=100, description="Максимальное количество результатов"),
):
    """
    Возвращает список всех сохранённых бэктестов.

    **Параметры:**
    - limit: Максимальное количество результатов (по умолчанию 20)

    **Пример:**
    ```
    GET /backtest/list?limit=10
    ```
    """
    backtest_dir = Path("artifacts/backtest")
    
    if not backtest_dir.exists():
        return {"backtests": []}

    # Получаем все JSON файлы
    files = sorted(backtest_dir.glob("backtest_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[:limit]

    backtests = []
    for filepath in files:
        try:
            with open(filepath, "r") as f:
                results = json.load(f)
            
            metrics = results.get("metrics", {})
            config = results.get("config", {})
            
            backtests.append({
                "run_id": filepath.stem,
                "timestamp": filepath.stem.replace("backtest_", ""),
                "metrics": {
                    "total_return": metrics.get("total_return", 0.0),
                    "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                    "max_drawdown": metrics.get("max_drawdown", 0.0),
                    "win_rate": metrics.get("win_rate", 0.0),
                    "total_trades": metrics.get("total_trades", 0),
                },
                "config": config,
            })
        except Exception as e:
            logger.warning(f"[backtest] Failed to load {filepath}: {e}")
            continue

    return {"backtests": backtests, "total": len(backtests)}


@router.delete("/results/{run_id}", dependencies=[Depends(require_api_key)])
def delete_backtest_results(run_id: str):
    """
    Удаляет результаты бэктеста.

    **Параметры:**
    - run_id: ID бэктеста

    **Пример:**
    ```
    DELETE /backtest/results/backtest_20250101_120000
    ```
    """
    filepath = Path("artifacts/backtest") / f"{run_id}.json"

    if not filepath.exists():
        raise HTTPException(status_code=404, detail=f"Backtest results not found: {run_id}")

    try:
        filepath.unlink()
        logger.info(f"[backtest] Deleted results: {run_id}")
        return {"success": True, "message": f"Deleted backtest results: {run_id}"}
    except Exception as e:
        logger.error(f"[backtest] Failed to delete results: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete results: {str(e)}")


@router.get("/compare", dependencies=[Depends(require_api_key)])
def compare_backtests(
    run_ids: str = Query(..., description="Comma-separated list of run IDs (e.g., run1,run2,run3)"),
):
    """
    Сравнивает несколько бэктестов.

    **Параметры:**
    - run_ids: Список run_id через запятую

    **Пример:**
    ```
    GET /backtest/compare?run_ids=backtest_20250101_120000,backtest_20250102_120000
    ```

    **Возвращает:**
    - Таблицу сравнения метрик
    - Лучший бэктест по каждой метрике
    """
    run_id_list = [rid.strip() for rid in run_ids.split(",")]

    if len(run_id_list) < 2:
        raise HTTPException(status_code=400, detail="At least 2 run_ids required for comparison")

    if len(run_id_list) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 backtests for comparison")

    comparison = []
    for run_id in run_id_list:
        filepath = Path("artifacts/backtest") / f"{run_id}.json"

        if not filepath.exists():
            logger.warning(f"[backtest] Results not found: {run_id}")
            continue

        try:
            with open(filepath, "r") as f:
                results = json.load(f)
            
            metrics = results.get("metrics", {})
            config = results.get("config", {})
            
            comparison.append({
                "run_id": run_id,
                "total_return": metrics.get("total_return", 0.0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0.0),
                "sortino_ratio": metrics.get("sortino_ratio", 0.0),
                "calmar_ratio": metrics.get("calmar_ratio", 0.0),
                "max_drawdown": metrics.get("max_drawdown", 0.0),
                "win_rate": metrics.get("win_rate", 0.0),
                "total_trades": metrics.get("total_trades", 0),
                "exposure_time": metrics.get("exposure_time", 0.0),
                "benchmark_return": metrics.get("benchmark_return", 0.0),
                "outperformance": metrics.get("excess_return", 0.0),
                "config": config,
            })
        except Exception as e:
            logger.warning(f"[backtest] Failed to load {run_id}: {e}")
            continue

    if len(comparison) < 2:
        raise HTTPException(status_code=400, detail="Not enough valid backtests for comparison")

    # Определяем лучшие по каждой метрике
    best = {
        "total_return": max(comparison, key=lambda x: x["total_return"])["run_id"],
        "sharpe_ratio": max(comparison, key=lambda x: x["sharpe_ratio"])["run_id"],
        "sortino_ratio": max(comparison, key=lambda x: x["sortino_ratio"])["run_id"],
        "calmar_ratio": max(comparison, key=lambda x: x["calmar_ratio"])["run_id"],
        "max_drawdown": max(comparison, key=lambda x: x["max_drawdown"])["run_id"],  # Ближе к 0
        "win_rate": max(comparison, key=lambda x: x["win_rate"])["run_id"],
        "outperformance": max(comparison, key=lambda x: x["outperformance"])["run_id"],
    }

    return {
        "comparison": comparison,
        "best": best,
        "count": len(comparison),
    }

