#!/usr/bin/env python3
"""
Упрощенная улучшенная модель торговли v2.0
Цель: +5-10% return, Sharpe > 1.0

Улучшения:
1. Динамическое позиционирование (Kelly Criterion)
2. Более строгие фильтры входа
3. Улучшенные пороги сигналов
4. Адаптивные периоды удержания
"""

import os
import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import ccxt

def load_historical_data(exchange='bybit', symbol='BTC/USDT', timeframe='1h', limit=1000):
    """Загружаем исторические данные для обучения"""
    print(f"Загружаем исторические данные: {symbol} {timeframe}")
    
    try:
        exchange_class = getattr(ccxt, exchange)
        exchange_instance = exchange_class({
            'sandbox': False,
            'enableRateLimit': True,
        })
        
        # Загружаем данные
        ohlcv = exchange_instance.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.set_index('timestamp')
        
        print(f"OK: Загружено {len(df)} свечей за период {df.index[0]} - {df.index[-1]}")
        return df
        
    except Exception as e:
        print(f"ОШИБКА: Ошибка загрузки данных: {e}")
        return None

def create_features(df):
    """Создаем технические индикаторы"""
    print("Создаем технические индикаторы...")
    
    # Базовые возвраты
    df['ret_1'] = df['close'].pct_change()
    df['ret_4'] = df['close'].pct_change(4)
    df['ret_24'] = df['close'].pct_change(24)
    
    # Простые технические индикаторы
    df['sma_20'] = df['close'].rolling(20).mean()
    df['ema_9'] = df['close'].ewm(span=9).mean()
    df['ema_21'] = df['close'].ewm(span=21).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi_14'] = 100 - (100 / (1 + rs))
    
    # Bollinger Bands
    df['bb_upper'] = df['close'].rolling(20).mean() + (df['close'].rolling(20).std() * 2)
    df['bb_lower'] = df['close'].rolling(20).mean() - (df['close'].rolling(20).std() * 2)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['close'].rolling(20).mean()
    
    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    df['atr_14'] = true_range.rolling(14).mean()
    
    # Future return (target)
    df['future_ret'] = df['close'].shift(-1) / df['close'] - 1
    
    # Target variable (1 if future return > 0, 0 otherwise)
    df['y'] = (df['future_ret'] > 0).astype(int)
    
    # Убираем NaN
    df = df.dropna()
    
    print(f"OK: Создано {len(df.columns)} фичей, {len(df)} строк после очистки")
    return df

def kelly_criterion_position_sizing(returns, win_rate, avg_win, avg_loss):
    """Рассчитываем оптимальный размер позиции по Kelly Criterion"""
    if avg_loss == 0:
        return 0.1  # Консервативный размер
    
    # Kelly = (bp - q) / b
    # где b = avg_win / |avg_loss|, p = win_rate, q = 1 - win_rate
    b = avg_win / abs(avg_loss)
    p = win_rate
    q = 1 - win_rate
    
    kelly = (b * p - q) / b
    
    # Ограничиваем Kelly до разумных пределов (0.05 - 0.25)
    kelly = max(0.05, min(0.25, kelly))
    
    return kelly

def improved_signal_thresholds(df, model):
    """Улучшенные пороги сигналов на основе исторических данных"""
    print("Оптимизируем пороги сигналов...")
    
    # Получаем предсказания модели
    feature_cols = [col for col in df.columns if col not in ['future_ret', 'y', 'open', 'high', 'low', 'close', 'volume']]
    X = df[feature_cols].fillna(0)
    
    # Предсказания вероятностей
    y_proba = model.predict_proba(X)[:, 1]  # Вероятность класса 1 (BUY)
    
    # Тестируем разные пороги
    thresholds = np.arange(0.55, 0.85, 0.05)
    signal_quality = []
    
    for threshold in thresholds:
        signals = y_proba > threshold
        if signals.sum() < 10:  # Минимум 10 сигналов
            continue
            
        # Рассчитываем качество сигналов
        signal_returns = df.loc[signals, 'future_ret']
        win_rate = (signal_returns > 0).mean()
        avg_return = signal_returns.mean()
        
        # Комбинированная метрика
        quality = win_rate * avg_return * signals.sum() / len(df)
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
        print("WARNING: Не найдено подходящих порогов, используем 0.6")
        return 0.6

def adaptive_position_sizing(df, model, threshold):
    """Адаптивный размер позиций на основе волатильности и качества сигналов"""
    print("Рассчитываем адаптивные размеры позиций...")
    
    feature_cols = [col for col in df.columns if col not in ['future_ret', 'y', 'open', 'high', 'low', 'close', 'volume']]
    X = df[feature_cols].fillna(0)
    y_proba = model.predict_proba(X)[:, 1]
    
    # Базовый размер из Kelly Criterion
    returns = df['future_ret']
    win_rate = (returns > 0).mean()
    avg_win = returns[returns > 0].mean() if (returns > 0).sum() > 0 else 0
    avg_loss = returns[returns < 0].mean() if (returns < 0).sum() > 0 else 0
    
    base_position_size = kelly_criterion_position_sizing(returns, win_rate, avg_win, avg_loss)
    
    # Адаптивный размер на основе волатильности
    atr_pct = df.get('atr_14', df['ret_1'].rolling(14).std()).fillna(0.02) / df['close']
    
    # Чем выше волатильность, тем меньше позиция
    volatility_adjustment = 1 / (1 + atr_pct * 10)
    
    # Размер на основе уверенности модели
    confidence_adjustment = np.where(
        y_proba > threshold,
        (y_proba - threshold) / (1 - threshold),  # Нормализация
        0
    )
    
    # Итоговый размер позиции
    position_sizes = base_position_size * volatility_adjustment * confidence_adjustment
    
    # Ограничиваем размеры
    position_sizes = np.clip(position_sizes, 0.02, 0.3)  # 2-30% от капитала
    
    print(f"OK: Базовый размер (Kelly): {base_position_size:.3f}")
    print(f"   Средний адаптивный размер: {position_sizes[position_sizes > 0].mean():.3f}")
    print(f"   Диапазон размеров: {position_sizes.min():.3f} - {position_sizes.max():.3f}")
    
    return position_sizes

def improved_backtest(df, model, threshold, position_sizes):
    """Улучшенный бэктест с адаптивными размерами позиций"""
    print("Запускаем улучшенный бэктест...")
    
    feature_cols = [col for col in df.columns if col not in ['future_ret', 'y', 'open', 'high', 'low', 'close', 'volume']]
    X = df[feature_cols].fillna(0)
    y_proba = model.predict_proba(X)[:, 1]
    
    # Сигналы с улучшенным порогом
    signals = y_proba > threshold
    
    # Простая симуляция бэктеста
    initial_capital = 1000
    commission_bps = 8
    slippage_bps = 5
    
    # Рассчитываем доходность с учетом комиссий и проскальзывания
    total_costs = (commission_bps + slippage_bps) / 10000  # Переводим в доли
    
    # Доходность стратегии
    strategy_returns = []
    capital = initial_capital
    
    for i, (idx, row) in enumerate(df.iterrows()):
        if signals[i] and position_sizes[i] > 0:
            # Размер позиции
            position_size = position_sizes[i]
            
            # Доходность актива
            asset_return = row.get('future_ret', 0)
            
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
    benchmark_returns = df.get('future_ret', pd.Series(0, index=df.index)).fillna(0)
    benchmark_cumulative = np.cumprod(1 + benchmark_returns)
    benchmark_total_return = benchmark_cumulative[-1] - 1
    
    # Торговые сделки
    trades = []
    in_position = False
    entry_price = None
    entry_time = None
    
    for i, (idx, row) in enumerate(df.iterrows()):
        if signals[i] and position_sizes[i] > 0 and not in_position:
            # Вход в позицию
            in_position = True
            entry_price = row.get('close', 100000)
            entry_time = idx
            
        elif not signals[i] and in_position:
            # Выход из позиции
            exit_price = row.get('close', 100000)
            exit_time = idx
            
            # PnL
            pnl = (exit_price - entry_price) / entry_price - total_costs
            
            trades.append({
                'entry_time': entry_time,
                'exit_time': exit_time,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'duration_bars': (exit_time - entry_time).total_seconds() / 3600  # в часах
            })
            
            in_position = False
    
    results = {
        'success': True,
        'error': None,
        'metrics': {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'total_trades': len(trades),
            'exposure_time': (signals * position_sizes > 0).mean(),
            'benchmark_return': benchmark_total_return,
            'excess_return': total_return - benchmark_total_return
        },
        'trades': trades[:20],  # Ограничиваем количество сделок для JSON
        'benchmark': {
            'benchmark_return': benchmark_total_return,
            'benchmark_sharpe': 0,  # Упрощенно
            'benchmark_max_dd': 0,  # Упрощенно
            'outperformance': total_return - benchmark_total_return,
            'beats_benchmark': total_return > benchmark_total_return
        },
        'config': {
            'initial_capital': initial_capital,
            'commission_bps': commission_bps,
            'slippage_bps': slippage_bps,
            'threshold': threshold,
            'adaptive_position_sizing': True
        }
    }
    
    return results

def main():
    """Основная функция улучшения модели"""
    print("MyAssistent Model Improvement v2.0")
    print("=" * 50)
    
    # 1. Загружаем данные
    print("\n1. Загружаем исторические данные...")
    df_prices = load_historical_data(limit=1000)  # 1000 свечей для демо
    
    if df_prices is None:
        print("ОШИБКА: Не удалось загрузить данные")
        return
    
    # 2. Создаем фичи
    print("\n2. Создаем технические индикаторы...")
    df = create_features(df_prices)
    
    if len(df) < 100:
        print("ОШИБКА: Недостаточно данных для обучения")
        return
    
    print(f"OK: Датасет: {len(df)} строк, {len(df.columns)} фичей")
    
    # 3. Обучаем модель
    print("\n3. Обучаем улучшенную модель...")
    feature_cols = [col for col in df.columns if col not in ['future_ret', 'y', 'open', 'high', 'low', 'close', 'volume']]
    
    # Простое обучение XGBoost
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score, roc_auc_score
    import xgboost as xgb
    
    X = df[feature_cols].fillna(0)
    y = df['y']
    
    # Разделяем на train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Обучаем XGBoost
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=6,
        learning_rate=0.1,
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
    
    # 4. Оптимизируем пороги
    threshold = improved_signal_thresholds(df, model)
    
    # 5. Рассчитываем адаптивные размеры позиций
    position_sizes = adaptive_position_sizing(df, model, threshold)
    
    # 6. Запускаем улучшенный бэктест
    results = improved_backtest(df, model, threshold, position_sizes)
    
    # 7. Сохраняем результаты
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"artifacts/backtest/improved_backtest_{timestamp}.json"
    
    os.makedirs(os.path.dirname(results_file), exist_ok=True)
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    # 8. Выводим результаты
    print("\n" + "=" * 50)
    print("РЕЗУЛЬТАТЫ УЛУЧШЕННОЙ МОДЕЛИ v2.0")
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
