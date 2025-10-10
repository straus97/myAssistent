"""
Векторизованный бэктестинг стратегий.

Основные функции:
- run_vectorized_backtest() - быстрая симуляция через pandas
- calculate_metrics() - Sharpe, Sortino, Calmar, Max DD, Win Rate
- calculate_drawdown() - анализ просадок (величина, duration, recovery)
- compare_with_benchmark() - сравнение с buy-and-hold

Реалистичная симуляция:
- Комиссии (8 bps по умолчанию)
- Проскальзывание (5 bps)
- Latency (задержка исполнения 1-2 бара)
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import joblib
from sqlalchemy.orm import Session

from .db import Price
from .features import build_dataset

logger = logging.getLogger(__name__)


# ============================
# Конфигурация по умолчанию
# ============================

DEFAULT_CONFIG = {
    "initial_capital": 1000.0,  # Начальный капитал (USDT)
    "commission_bps": 8.0,  # Комиссии в базисных пунктах (0.08%)
    "slippage_bps": 5.0,  # Проскальзывание в базисных пунктах (0.05%)
    "latency_bars": 1,  # Задержка исполнения (количество баров)
    "position_size": 1.0,  # Размер позиции (доля от капитала, 0.0-1.0)
}


# ============================
# Основная функция бэктестинга
# ============================

def run_vectorized_backtest(
    db: Session,
    exchange: str,
    symbol: str,
    timeframe: str,
    start_date: str,
    end_date: str,
    model_path: str | None = None,
    signal_threshold: float = 0.5,
    config: Dict | None = None,
) -> Dict:
    """
    Запускает векторизованный бэктест стратегии.

    Args:
        db: SQLAlchemy сессия
        exchange: Биржа (binance, bybit)
        symbol: Торговая пара (BTC/USDT)
        timeframe: Таймфрейм (1h, 4h, 1d)
        start_date: Дата начала (YYYY-MM-DD)
        end_date: Дата окончания (YYYY-MM-DD)
        model_path: Путь к модели XGBoost (если None - используем последнюю)
        signal_threshold: Порог для BUY сигнала (вероятность > threshold)
        config: Конфигурация бэктеста (комиссии, проскальзывание и т.д.)

    Returns:
        Dict с результатами бэктеста:
        - equity_curve: DataFrame с историей капитала
        - metrics: Метрики стратегии (Sharpe, Sortino, etc.)
        - trades: Список сделок
        - benchmark: Сравнение с buy-and-hold
    """
    logger.info(f"[backtest] Starting backtest: {exchange} {symbol} {timeframe} ({start_date} → {end_date})")

    # Загрузка конфигурации
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    initial_capital = float(cfg["initial_capital"])
    commission_bps = float(cfg["commission_bps"])
    slippage_bps = float(cfg["slippage_bps"])
    latency_bars = int(cfg["latency_bars"])
    position_size = float(cfg["position_size"])

    # 1. Построение датасета с фичами
    logger.info("[backtest] Building dataset with features...")
    try:
        df, feature_cols = build_dataset(
            db=db,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )
    except Exception as e:
        logger.error(f"[backtest] Failed to build dataset: {e}")
        return {
            "success": False,
            "error": f"Failed to build dataset: {str(e)}",
            "equity_curve": None,
            "metrics": None,
            "trades": None,
            "benchmark": None,
        }

    if df.empty:
        return {
            "success": False,
            "error": "Empty dataset",
            "equity_curve": None,
            "metrics": None,
            "trades": None,
            "benchmark": None,
        }

    # Фильтрация по датам
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    # Логируем доступный диапазон данных
    logger.info(f"[backtest] Available data range: {df['timestamp'].min()} → {df['timestamp'].max()}")
    
    start = pd.to_datetime(start_date).tz_localize('UTC')
    end = pd.to_datetime(end_date).tz_localize('UTC')
    
    logger.info(f"[backtest] Requested date range: {start} → {end}")
    
    df = df[(df["timestamp"] >= start) & (df["timestamp"] <= end)].copy()
    
    logger.info(f"[backtest] After filtering: {len(df)} rows")

    if len(df) < 10:
        return {
            "success": False,
            "error": f"Insufficient data ({len(df)} rows). Available data: {df['timestamp'].min() if not df.empty else 'N/A'} → {df['timestamp'].max() if not df.empty else 'N/A'}. Requested: {start_date} → {end_date}",
            "equity_curve": None,
            "metrics": None,
            "trades": None,
            "benchmark": None,
        }

    logger.info(f"[backtest] Dataset: {len(df)} rows, {df['timestamp'].min()} → {df['timestamp'].max()}")

    # 2. Загрузка модели
    if model_path is None:
        # Ищем последнюю модель
        artifacts_dir = Path("artifacts/models")
        if not artifacts_dir.exists():
            artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        models = list(artifacts_dir.glob("model_*.pkl")) + list(artifacts_dir.glob("*.pkl"))
        if not models:
            return {
                "success": False,
                "error": "No model found in artifacts/models/. Please train a model first using POST /model/train",
                "equity_curve": None,
                "metrics": None,
                "trades": None,
                "benchmark": None,
            }
        model_path = str(sorted(models, key=lambda p: p.stat().st_mtime)[-1])

    logger.info(f"[backtest] Loading model: {model_path}")
    try:
        model_obj = joblib.load(model_path)
        # Модель сохраняется как dict с ключами: model, feature_cols, threshold, metrics
        if isinstance(model_obj, dict) and "model" in model_obj:
            model = model_obj["model"]
            logger.info(f"[backtest] Loaded model from dict (threshold: {model_obj.get('threshold', 'N/A')})")
        else:
            model = model_obj  # Старый формат - напрямую модель
    except Exception as e:
        logger.error(f"[backtest] Failed to load model: {e}")
        return {
            "success": False,
            "error": f"Failed to load model: {str(e)}",
            "equity_curve": None,
            "metrics": None,
            "trades": None,
            "benchmark": None,
        }

    # 3. Генерация сигналов
    feature_cols = [c for c in df.columns if c not in ["timestamp", "close", "future_ret", "y"]]
    X = df[feature_cols].fillna(0)

    try:
        proba = model.predict_proba(X)[:, 1]  # Вероятность класса 1 (buy)
    except Exception as e:
        logger.error(f"[backtest] Model prediction failed: {e}")
        return {
            "success": False,
            "error": f"Model prediction failed: {str(e)}",
            "equity_curve": None,
            "metrics": None,
            "trades": None,
            "benchmark": None,
        }

    df["signal_proba"] = proba
    df["signal"] = (proba >= signal_threshold).astype(int)

    # 4. Симуляция с задержкой (latency)
    df["signal_delayed"] = df["signal"].shift(latency_bars).fillna(0).astype(int)

    # 5. Векторизованный расчёт доходности с комиссиями и проскальзыванием
    commission_rate = commission_bps / 10000.0
    slippage_rate = slippage_bps / 10000.0

    # Реальная доходность с учётом комиссий и проскальзывания
    # При покупке: платим комиссию и проскальзывание
    # При продаже: платим комиссию
    df["ret"] = df["close"].pct_change()
    df["strategy_ret"] = df["signal_delayed"] * df["ret"]
    
    # Вычисляем точки входа/выхода
    df["position"] = df["signal_delayed"]
    df["position_change"] = df["position"].diff().fillna(0)
    
    # Комиссии при открытии позиции (вход)
    df["entry_cost"] = (df["position_change"] == 1).astype(int) * (commission_rate + slippage_rate)
    # Комиссии при закрытии позиции (выход)
    df["exit_cost"] = (df["position_change"] == -1).astype(int) * commission_rate
    
    # Итоговая доходность с учётом всех издержек
    df["strategy_ret_net"] = df["strategy_ret"] - df["entry_cost"] - df["exit_cost"]
    
    # Применяем position_size (если позиция неполная, остальное в кэше)
    df["strategy_ret_net"] = df["strategy_ret_net"] * position_size

    # 6. Расчёт equity curve
    df["equity"] = initial_capital * (1 + df["strategy_ret_net"]).cumprod()
    df["benchmark_equity"] = initial_capital * (1 + df["ret"]).cumprod()

    # 7. Расчёт метрик
    metrics = calculate_metrics(df)

    # 8. Список сделок
    trades = extract_trades(df)

    # 9. Сравнение с бенчмарком
    benchmark = compare_with_benchmark(df)

    # 10. Equity curve для визуализации
    equity_curve = df[["timestamp", "equity", "benchmark_equity"]].copy()
    equity_curve["timestamp"] = equity_curve["timestamp"].astype(str)

    logger.info(f"[backtest] Completed. Sharpe: {metrics['sharpe_ratio']:.2f}, Total Return: {metrics['total_return']:.2%}")

    return {
        "success": True,
        "error": None,
        "equity_curve": equity_curve.to_dict(orient="records"),
        "metrics": metrics,
        "trades": trades,
        "benchmark": benchmark,
        "config": cfg,
    }


# ============================
# Расчёт метрик
# ============================

def calculate_metrics(df: pd.DataFrame) -> Dict:
    """
    Вычисляет метрики стратегии.

    Метрики:
    - Total Return (общая доходность)
    - Sharpe Ratio (risk-adjusted returns)
    - Sortino Ratio (downside deviation)
    - Calmar Ratio (return / max drawdown)
    - Max Drawdown (величина, duration, recovery)
    - Win Rate, Avg Win, Avg Loss
    - Total Trades, Exposure Time
    """
    metrics = {}

    # Базовые метрики
    initial_equity = df["equity"].iloc[0]
    final_equity = df["equity"].iloc[-1]
    total_return = (final_equity / initial_equity) - 1.0
    metrics["total_return"] = float(total_return)

    # Returns
    returns = df["strategy_ret_net"].dropna()
    if len(returns) > 0:
        mean_ret = returns.mean()
        std_ret = returns.std()
        
        # Sharpe Ratio (annualized, assuming 365 days)
        # Для крипто используем 365 дней (24/7 торговля)
        n_periods = len(returns)
        if std_ret > 0:
            sharpe = (mean_ret / std_ret) * np.sqrt(365)
        else:
            sharpe = 0.0
        metrics["sharpe_ratio"] = float(sharpe)

        # Sortino Ratio (учитывает только негативную волатильность)
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_std = negative_returns.std()
            sortino = (mean_ret / downside_std) * np.sqrt(365) if downside_std > 0 else 0.0
        else:
            sortino = float('inf') if mean_ret > 0 else 0.0
        metrics["sortino_ratio"] = float(sortino) if not np.isinf(sortino) else 999.0

    else:
        metrics["sharpe_ratio"] = 0.0
        metrics["sortino_ratio"] = 0.0

    # Drawdown анализ
    dd_info = calculate_drawdown(df)
    metrics.update(dd_info)

    # Calmar Ratio (return / max drawdown)
    max_dd = abs(dd_info["max_drawdown"])
    if max_dd > 0:
        calmar = total_return / max_dd
    else:
        calmar = 0.0
    metrics["calmar_ratio"] = float(calmar)

    # Trade-level метрики
    trade_metrics = calculate_trade_metrics(df)
    metrics.update(trade_metrics)

    # Benchmark сравнение
    benchmark_return = (df["benchmark_equity"].iloc[-1] / df["benchmark_equity"].iloc[0]) - 1.0
    metrics["benchmark_return"] = float(benchmark_return)
    metrics["excess_return"] = float(total_return - benchmark_return)

    return metrics


def calculate_drawdown(df: pd.DataFrame) -> Dict:
    """
    Вычисляет максимальную просадку и связанные метрики.

    Returns:
        - max_drawdown: Максимальная просадка (отрицательное число)
        - max_drawdown_duration: Длительность максимальной просадки (в барах)
        - max_recovery_time: Время восстановления после просадки (в барах)
        - current_drawdown: Текущая просадка
    """
    equity = df["equity"]
    
    # Running maximum (пик капитала)
    running_max = equity.expanding().max()
    
    # Drawdown в каждый момент времени
    drawdown = (equity - running_max) / running_max
    
    max_dd = float(drawdown.min())
    max_dd_idx = drawdown.idxmin()
    
    # Длительность просадки (от пика до дна)
    peak_idx = equity[:max_dd_idx].idxmax()
    dd_duration = max_dd_idx - peak_idx
    
    # Время восстановления (от дна до восстановления пика)
    peak_value = equity[peak_idx]
    recovery_idx = None
    if max_dd_idx < len(equity) - 1:
        future_equity = equity[max_dd_idx:]
        recovery_mask = future_equity >= peak_value
        if recovery_mask.any():
            recovery_idx = recovery_mask.idxmax()
            recovery_time = recovery_idx - max_dd_idx
        else:
            recovery_time = None  # Ещё не восстановились
    else:
        recovery_time = None
    
    # Текущая просадка (от последнего пика)
    current_dd = float(drawdown.iloc[-1])
    
    return {
        "max_drawdown": max_dd,
        "max_drawdown_duration": int(dd_duration),
        "max_recovery_time": int(recovery_time) if recovery_time is not None else None,
        "current_drawdown": current_dd,
    }


def calculate_trade_metrics(df: pd.DataFrame) -> Dict:
    """
    Вычисляет метрики на уровне сделок.

    Returns:
        - total_trades: Общее количество сделок
        - win_rate: % прибыльных сделок
        - avg_win: Средняя прибыль в прибыльных сделках
        - avg_loss: Средний убыток в убыточных сделках
        - profit_factor: Отношение прибыли к убыткам
        - exposure_time: Доля времени в позиции (%)
    """
    # Определяем точки входа/выхода
    position = df["position"].fillna(0)
    position_change = position.diff().fillna(0)
    
    entries = (position_change == 1)
    exits = (position_change == -1)
    
    # Парсим сделки
    trades = []
    entry_idx = None
    for idx in df.index:
        if entries[idx]:
            entry_idx = idx
        elif exits[idx] and entry_idx is not None:
            # Закрытие сделки
            entry_price = df.loc[entry_idx, "close"]
            exit_price = df.loc[idx, "close"]
            pnl = (exit_price / entry_price) - 1.0
            trades.append(pnl)
            entry_idx = None
    
    # Если есть открытая сделка в конце
    if entry_idx is not None:
        entry_price = df.loc[entry_idx, "close"]
        exit_price = df.iloc[-1]["close"]
        pnl = (exit_price / entry_price) - 1.0
        trades.append(pnl)
    
    total_trades = len(trades)
    
    if total_trades > 0:
        trades_arr = np.array(trades)
        wins = trades_arr[trades_arr > 0]
        losses = trades_arr[trades_arr <= 0]
        
        win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
        avg_win = float(wins.mean()) if len(wins) > 0 else 0.0
        avg_loss = float(losses.mean()) if len(losses) > 0 else 0.0
        
        # Profit Factor
        total_win = wins.sum() if len(wins) > 0 else 0.0
        total_loss = abs(losses.sum()) if len(losses) > 0 else 0.0
        profit_factor = total_win / total_loss if total_loss > 0 else float('inf')
    else:
        win_rate = 0.0
        avg_win = 0.0
        avg_loss = 0.0
        profit_factor = 0.0
    
    # Exposure time (доля времени в позиции)
    exposure_time = (position > 0).sum() / len(position)
    
    return {
        "total_trades": total_trades,
        "win_rate": float(win_rate),
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": float(profit_factor) if not np.isinf(profit_factor) else 999.0,
        "exposure_time": float(exposure_time),
    }


def extract_trades(df: pd.DataFrame, max_trades: int = 100) -> List[Dict]:
    """
    Извлекает список сделок для детального анализа.

    Args:
        df: DataFrame с результатами бэктеста
        max_trades: Максимальное количество сделок для возврата

    Returns:
        List of trades: [{entry_time, exit_time, entry_price, exit_price, pnl, duration}]
    """
    position = df["position"].fillna(0)
    position_change = position.diff().fillna(0)
    
    entries = (position_change == 1)
    exits = (position_change == -1)
    
    trades = []
    entry_idx = None
    entry_time = None
    entry_price = None
    
    for idx in df.index:
        if entries[idx]:
            entry_idx = idx
            entry_time = df.loc[idx, "timestamp"]
            entry_price = df.loc[idx, "close"]
        elif exits[idx] and entry_idx is not None:
            exit_time = df.loc[idx, "timestamp"]
            exit_price = df.loc[idx, "close"]
            pnl = (exit_price / entry_price) - 1.0
            duration = idx - entry_idx
            
            trades.append({
                "entry_time": str(entry_time),
                "exit_time": str(exit_time),
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "pnl": float(pnl),
                "duration_bars": int(duration),
            })
            
            entry_idx = None
    
    # Открытая сделка в конце
    if entry_idx is not None:
        exit_time = df.iloc[-1]["timestamp"]
        exit_price = df.iloc[-1]["close"]
        pnl = (exit_price / entry_price) - 1.0
        duration = len(df) - 1 - entry_idx
        
        trades.append({
            "entry_time": str(entry_time),
            "exit_time": str(exit_time),
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "pnl": float(pnl),
            "duration_bars": int(duration),
            "status": "open",
        })
    
    # Ограничиваем количество сделок
    return trades[:max_trades]


# ============================
# Сравнение с бенчмарком
# ============================

def compare_with_benchmark(df: pd.DataFrame) -> Dict:
    """
    Сравнивает стратегию с бенчмарком (buy-and-hold).

    Returns:
        Dict с метриками бенчмарка и сравнением:
        - benchmark_return: Доходность buy-and-hold
        - benchmark_sharpe: Sharpe ratio бенчмарка
        - benchmark_max_dd: Максимальная просадка бенчмарка
        - outperformance: Превосходство стратегии над бенчмарком
    """
    # Бенчмарк (buy-and-hold)
    initial = df["benchmark_equity"].iloc[0]
    final = df["benchmark_equity"].iloc[-1]
    benchmark_return = (final / initial) - 1.0
    
    # Sharpe бенчмарка
    returns = df["ret"].dropna()
    if len(returns) > 0 and returns.std() > 0:
        benchmark_sharpe = (returns.mean() / returns.std()) * np.sqrt(365)
    else:
        benchmark_sharpe = 0.0
    
    # Max DD бенчмарка
    equity = df["benchmark_equity"]
    running_max = equity.expanding().max()
    drawdown = (equity - running_max) / running_max
    benchmark_max_dd = float(drawdown.min())
    
    # Сравнение
    strategy_return = (df["equity"].iloc[-1] / df["equity"].iloc[0]) - 1.0
    outperformance = strategy_return - benchmark_return
    
    return {
        "benchmark_return": float(benchmark_return),
        "benchmark_sharpe": float(benchmark_sharpe),
        "benchmark_max_dd": benchmark_max_dd,
        "outperformance": float(outperformance),
        "beats_benchmark": bool(outperformance > 0),
    }


# ============================
# Вспомогательные функции
# ============================

def save_backtest_results(results: Dict, output_dir: str = "artifacts/backtest") -> str:
    """
    Сохраняет результаты бэктеста в файл.

    Args:
        results: Результаты бэктеста
        output_dir: Директория для сохранения

    Returns:
        Путь к сохранённому файлу
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"backtest_{timestamp}.json"
    filepath = output_path / filename
    
    # Сохраняем в JSON (без equity_curve для экономии места)
    import json
    results_to_save = {k: v for k, v in results.items() if k != "equity_curve"}
    
    with open(filepath, "w") as f:
        json.dump(results_to_save, f, indent=2, default=str)
    
    logger.info(f"[backtest] Results saved to {filepath}")
    return str(filepath)

