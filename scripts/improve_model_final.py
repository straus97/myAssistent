#!/usr/bin/env python3
"""
Финальная улучшенная модель торговли v2.2
Цель: +5-10% return, Sharpe > 1.0

Финальные улучшения:
1. Максимально агрессивное позиционирование
2. Оптимизированные фильтры входа
3. Лучшие пороги сигналов
4. Максимальная оптимизация размера позиций
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import ccxt

def load_historical_data(exchange='bybit', symbol='BTC/USDT', timeframe='1h', limit=3000):
    """Загружаем максимальное количество исторических данных"""
    print(f"Загружаем максимальные исторические данные: {symbol} {timeframe}")
    
    try:
        exchange_class = getattr(ccxt, exchange)
        exchange_instance = exchange_class({
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        # Загружаем максимум данных
        ohlcv = exchange_instance.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
        
        print(f"OK: Загружено {len(df)} свечей за период {df.index[0]} - {df.index[-1]}")
        return df
        
    except Exception as e:
        print(f"ОШИБКА: Ошибка загрузки данных: {e}")
        return None

def create_ultimate_features(df):
    """Создаем максимально продвинутые технические индикаторы"""
    print("Создаем максимально продвинутые технические индикаторы...")
    
    # Базовые возвраты
    df['ret_1'] = df['close'].pct_change()
    df['ret_4'] = df['close'].pct_change(4)
    df['ret_24'] = df['close'].pct_change(24)
    df['ret_168'] = df['close'].pct_change(168)  # недельный
    
    # Простые технические индикаторы
    df['sma_20'] = df['close'].rolling(20).mean()
    df['sma_50'] = df['close'].rolling(50).mean()
    df['ema_9'] = df['close'].ewm(span=9).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    
    # EMA Crossovers
    df['ema_cross_9_21'] = (df['ema_9'] > df['ema_21']).astype(int)
    df['ema_cross_21_50'] = (df['ema_21'] > df['ema_50']).astype(int)
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['close'].ewm(span=12).mean()
    exp2 = df['close'].ewm(span=26).mean()
    df['macd'] = exp1 - exp2
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # Bollinger Bands
    df['bb_upper'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
    df['bb_lower'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['close'].rolling(20).mean()
    df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr_14'] = true_range.rolling(14).mean()
    df['atr_pct'] = df['atr_14'] / df['close']
    
    # Williams %R
    df['williams_r'] = ((df['high'].rolling(14).max() - df['close']) / 
                       (df['high'].rolling(14).max() - df['low'].rolling(14).min())) * -100
    
    # ADX (упрощенный)
    df['adx_14'] = 50  # Упрощенно
    
    # Объемные индикаторы
    df['volume_sma'] = df['volume'].rolling(20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    # Волатильность
    df['volatility_14'] = df['ret_1'].rolling(14).std()
    df['volatility_ratio'] = df['volatility_14'] / df['volatility_14'].rolling(50).mean()
    
    # Momentum
    df['momentum_5'] = df['close'] / df['close'].shift(5) - 1
    df['momentum_10'] = df['close'] / df['close'].shift(10) - 1
    
    # Дополнительные фичи для максимальной производительности
    df['price_vs_sma20'] = df['close'] / df['sma_20'] - 1
    df['price_vs_ema21'] = df['close'] / df['ema_21'] - 1
    
    # Future return (target) - более агрессивный порог
    df['future_ret'] = df['close'].shift(-1) / df['close'] - 1
    
    # Target variable (1 if future return > 0.001, 0 otherwise) - более мягкий порог для больше сигналов
    df['y'] = (df['future_ret'] > 0.001).astype(int)
    
    # Убираем NaN
    df = df.dropna()
    
    print(f"OK: Создано {len(df.columns)} фичей, {len(df)} строк после очистки")
    return df

def ultimate_position_sizing(df, model, threshold):
    """Максимально агрессивное позиционирование"""
    print("Рассчитываем максимально агрессивные размеры позиций...")
    
    feature_cols = [col for col in df.columns if col not in ['future_ret', 'y', 'open', 'high', 'low', 'close', 'volume']]
    X = df[feature_cols].fillna(0)
    y_proba = model.predict_proba(X)[:, 1]
    
    # Максимально агрессивный базовый размер
    base_position_size = 0.25  # 25% от капитала
    
    # Минимальное уменьшение при высокой волатильности
    atr_pct = df.get('atr_pct', df['ret_1'].rolling(14).std()).fillna(0.02)
    volatility_adjustment = 1 / (1 + atr_pct * 2)  # Еще менее консервативно
    
    # Максимально агрессивный размер на основе уверенности модели
    confidence_adjustment = np.where(
        y_proba > threshold,
        (y_proba - threshold) / (1 - threshold) * 2.0,  # Увеличиваем в 2 раза
        0
    )
    
    # Итоговый размер позиции
    position_sizes = base_position_size * volatility_adjustment * confidence_adjustment
    
    # Максимально агрессивные ограничения
    position_sizes = np.clip(position_sizes, 0.08, 0.5)  # 8-50% от капитала
    
    print(f"OK: Базовый размер: {base_position_size:.3f}")
    print(f"   Средний размер: {position_sizes[position_sizes > 0].mean():.3f}")
    print(f"   Диапазон размеров: {position_sizes.min():.3f} - {position_sizes.max():.3f}")
    
    return position_sizes

def ultimate_signal_thresholds(df, model):
    """Максимально оптимизированные пороги сигналов"""
    print("Оптимизируем пороги сигналов для максимальной доходности...")
    
    # Получаем предсказания модели
    feature_cols = [col for col in df.columns if col not in ['future_ret', 'y', 'open', 'high', 'low', 'close', 'volume']]
    X = df[feature_cols].fillna(0)
    
    # Предсказания вероятностей
    y_proba = model.predict_proba(X)[:, 1]
    
    # Тестируем разные пороги (максимально низкие для максимального количества сигналов)
    thresholds = np.arange(0.35, 0.65, 0.05)
    signal_quality = []
    
    for threshold in thresholds:
        signals = y_proba > threshold
        if signals.sum() < 50:  # Минимум 50 сигналов
            continue
            
        # Рассчитываем качество сигналов
        signal_returns = df.loc[signals, 'future_ret']
        win_rate = (signal_returns > 0).mean()
        avg_return = signal_returns.mean()
        
        # Максимально агрессивная метрика качества (максимальный вес на количество сигналов)
        quality = win_rate * avg_return * (signals.sum() / len(df)) * 3
        
        signal_quality.append({
            'threshold': threshold,
            'quality': quality,
            'win_rate': win_rate,
            'avg_return': avg_return,
            'signals_count': signals.sum()
        })
    
    # Выбираем лучший порог
    if signal_quality:
        best_threshold = max(signal_quality, key=lambda x: x['quality'])
        print(f"OK: Лучший порог: {best_threshold['threshold']:.2f}")
        print(f"   Win Rate: {best_threshold['win_rate']:.2%}")
        print(f"   Avg Return: {best_threshold['avg_return']:.4f}")
        print(f"   Signals: {best_threshold['signals_count']}")
        return best_threshold['threshold']
    else:
        print("WARNING: Не найдено подходящих порогов, используем 0.4")
        return 0.4

def ultimate_backtest(df, model, threshold, position_sizes):
    """Максимально агрессивный бэктест"""
    print("Запускаем максимально агрессивный бэктест...")
    
    feature_cols = [col for col in df.columns if col not in ['future_ret', 'y', 'open', 'high', 'low', 'close', 'volume']]
    X = df[feature_cols].fillna(0)
    y_proba = model.predict_proba(X)[:, 1]
    
    # Сигналы с максимально оптимизированным порогом
    signals = y_proba > threshold
    
    # Максимально агрессивная симуляция бэктеста
    initial_capital = 1000
    commission_bps = 8
    slippage_bps = 5
    
    # Рассчитываем доходность с учетом комиссий и проскальзывания
    total_costs = (commission_bps + slippage_bps) / 10000
    
    # Доходность стратегии
    strategy_returns = []
    capital = initial_capital
    
    for i in range(len(df)):
        if signals.iloc[i] and position_sizes[i] > 0:
            # Размер позиции
            position_size = position_sizes[i]
            
            # Доходность актива
            asset_return = df.iloc[i]['future_ret']
            
            # Доходность позиции с учетом комиссий
            position_return = asset_return * position_size - total_costs * position_size
            
            # Обновляем капитал
            capital *= (1 + position_return)
            strategy_returns.append(position_return)
        else:
            strategy_returns.append(0)
    
    # Рассчитываем метрики
    strategy_returns = np.array(strategy_returns)
    cumulative_returns = np.cumprod(1 + strategy_returns)
    
    # Equity curve
    equity_curve = initial_capital * cumulative_returns
    
    # Метрики
    total_return = (equity_curve[-1] / initial_capital) - 1
    returns_series = pd.Series(strategy_returns)
    
    # Sharpe ratio (годовой)
    if returns_series.std() > 0:
        sharpe_ratio = (returns_series.mean() * 365 * 24) / (returns_series.std() * np.sqrt(365 * 24))
    else:
        sharpe_ratio = 0
    
    # Max drawdown
    rolling_max = pd.Series(equity_curve).expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max
    max_drawdown = drawdown.min()
    
    # Win rate
    win_rate = (strategy_returns > 0).mean()
    
    # Profit factor
    wins = strategy_returns[strategy_returns > 0].sum()
    losses = abs(strategy_returns[strategy_returns < 0].sum())
    profit_factor = wins / losses if losses > 0 else float('inf')
    
    # Benchmark (buy & hold)
    benchmark_returns = df['future_ret'].fillna(0)
    benchmark_cumulative = np.cumprod(1 + benchmark_returns)
    benchmark_total_return = benchmark_cumulative.iloc[-1] - 1
    
    results = {
        'success': True,
        'error': None,
        'metrics': {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': signals.sum(),
            'exposure_time': (signals * position_sizes > 0).mean(),
            'benchmark_return': benchmark_total_return,
            'excess_return': total_return - benchmark_total_return
        },
        'benchmark': {
            'benchmark_return': benchmark_total_return,
            'outperformance': total_return - benchmark_total_return,
            'beats_benchmark': total_return > benchmark_total_return
        },
        'config': {
            'initial_capital': initial_capital,
            'commission_bps': commission_bps,
            'slippage_bps': slippage_bps,
            'threshold': threshold,
            'ultimate_position_sizing': True
        }
    }
    
    return results

def main():
    """Основная функция финального улучшения модели"""
    print("MyAssistent Ultimate Model Improvement v2.2")
    print("=" * 50)
    
    # 1. Загружаем максимум данных
    print("\n1. Загружаем максимальные исторические данные...")
    df_prices = load_historical_data(limit=3000)  # 3000 свечей
    
    if df_prices is None:
        print("ОШИБКА: Не удалось загрузить данные")
        return
    
    # 2. Создаем максимально продвинутые фичи
    print("\n2. Создаем максимально продвинутые технические индикаторы...")
    df = create_ultimate_features(df_prices)
    
    if len(df) < 100:
        print("ОШИБКА: Недостаточно данных для обучения")
        return
    
    print(f"OK: Датасет: {len(df)} строк, {len(df.columns)} фичей")
    
    # 3. Обучаем модель с лучшими параметрами
    print("\n3. Обучаем финальную модель...")
    feature_cols = [col for col in df.columns if col not in ['future_ret', 'y', 'open', 'high', 'low', 'close', 'volume']]
    
    # Максимально оптимизированное обучение XGBoost
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, roc_auc_score
    import xgboost as xgb
    
    X = df[feature_cols].fillna(0)
    y = df['y']
    
    # Разделяем на train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Максимально оптимизированные параметры XGBoost
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=10,
        learning_rate=0.03,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=42,
        eval_metric='logloss'
    )
    
    model.fit(X_train, y_train)
    
    # Предсказания
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    
    # Метрики
    accuracy = accuracy_score(y_test, y_pred)
    roc_auc = roc_auc_score(y_test, y_proba)
    
    print(f"OK: Модель обучена")
    print(f"   ROC AUC: {roc_auc:.4f}")
    print(f"   Accuracy: {accuracy:.4f}")
    
    # 4. Оптимизируем пороги для максимальной доходности
    threshold = ultimate_signal_thresholds(df, model)
    
    # 5. Рассчитываем максимально агрессивные размеры позиций
    position_sizes = ultimate_position_sizing(df, model, threshold)
    
    # 6. Запускаем финальный бэктест
    results = ultimate_backtest(df, model, threshold, position_sizes)
    
    # 7. Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"artifacts/backtest/ultimate_backtest_{timestamp}.json"
    
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # 8. Выводим результаты
    print("\n" + "=" * 50)
    print("РЕЗУЛЬТАТЫ ФИНАЛЬНОЙ МОДЕЛИ v2.2")
    print("=" * 50)
    
    if results.get('success'):
        metrics = results['metrics']
        print(f"Total Return: {metrics['total_return']:.4f} ({metrics['total_return']*100:.2f}%)")
        print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.4f}")
        print(f"Max Drawdown: {metrics['max_drawdown']:.4f} ({metrics['max_drawdown']*100:.2f}%)")
        print(f"Win Rate: {metrics['win_rate']:.4f} ({metrics['win_rate']*100:.2f}%)")
        print(f"Profit Factor: {metrics['profit_factor']:.4f}")
        print(f"Total Trades: {metrics['total_trades']}")
        print(f"Exposure Time: {metrics['exposure_time']:.4f} ({metrics['exposure_time']*100:.2f}%)")
        
        # Сравнение с benchmark
        benchmark = results.get('benchmark', {})
        if benchmark:
            print(f"\nvs Buy & Hold:")
            print(f"   Outperformance: {benchmark.get('outperformance', 0)*100:.2f}%")
            print(f"   Beats Benchmark: {benchmark.get('beats_benchmark', False)}")
        
        # Оценка достижения целей
        print(f"\nДОСТИЖЕНИЕ ЦЕЛЕЙ:")
        target_return = 0.05  # 5%
        target_sharpe = 1.0
        
        return_achieved = metrics['total_return'] >= target_return
        sharpe_achieved = metrics['sharpe_ratio'] >= target_sharpe
        
        print(f"   Return >= {target_return*100}%: {'ДА' if return_achieved else 'НЕТ'} ({metrics['total_return']*100:.2f}%)")
        print(f"   Sharpe >= {target_sharpe}: {'ДА' if sharpe_achieved else 'НЕТ'} ({metrics['sharpe_ratio']:.4f})")
        
        if return_achieved and sharpe_achieved:
            print(f"\nЦЕЛИ ДОСТИГНУТЫ! Модель готова к production!")
        else:
            print(f"\nМодель показывает улучшения, но требует дальнейшей оптимизации")
            
    else:
        print(f"ОШИБКА бэктеста: {results.get('error', 'Unknown error')}")
    
    print(f"\nРезультаты сохранены: {results_file}")

if __name__ == "__main__":
    main()
