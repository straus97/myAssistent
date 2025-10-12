"""
Запуск бэктестинга с последней обученной моделью
"""
import json
from pathlib import Path
import sys
from datetime import datetime, timedelta
sys.path.append(str(Path(__file__).parent.parent))

from src.backtest import run_vectorized_backtest
from src.db import SessionLocal


def main():
    print("\n" + "="*70)
    print("[BACKTEST] ТЕСТИРОВАНИЕ МОДЕЛИ НА ИСТОРИЧЕСКИХ ДАННЫХ")
    print("="*70 + "\n")
    
    # Параметры
    EXCHANGE = "bybit"
    SYMBOL = "BTC/USDT"
    TIMEFRAME = "1h"
    MODEL_PATH = "artifacts/models/xgb_20251012_091746.pkl"  # Последняя улучшенная модель
    
    # Даты для бэктеста (последние 60 дней)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    START_DATE_STR = start_date.strftime("%Y-%m-%d")
    END_DATE_STR = end_date.strftime("%Y-%m-%d")
    
    INITIAL_CAPITAL = 1000.0
    COMMISSION_BPS = 8.0  # 0.08% Bybit taker fee
    SLIPPAGE_BPS = 5.0    # 0.05% slippage
    
    print(f"[PARAMS]:")
    print(f"   Exchange: {EXCHANGE}")
    print(f"   Symbol: {SYMBOL}")
    print(f"   Timeframe: {TIMEFRAME}")
    print(f"   Period: {START_DATE_STR} to {END_DATE_STR}")
    print(f"   Initial capital: ${INITIAL_CAPITAL}")
    print(f"   Model: {Path(MODEL_PATH).name}\n")
    
    # Запуск бэктестинга через существующую функцию
    print("[BACKTEST] Запуск симуляции...")
    
    db = SessionLocal()
    
    try:
        results = run_vectorized_backtest(
            db=db,
            exchange=EXCHANGE,
            symbol=SYMBOL,
            timeframe=TIMEFRAME,
            start_date=START_DATE_STR,
            end_date=END_DATE_STR,
            model_path=MODEL_PATH,
            signal_threshold=0.5,  # Will be loaded from model
            config={
                "initial_capital": INITIAL_CAPITAL,
                "commission_bps": COMMISSION_BPS,
                "slippage_bps": SLIPPAGE_BPS,
                "latency_bars": 1,
            }
        )
        
        # Вывод результатов
        print("\n" + "="*70)
        print("[RESULTS] РЕЗУЛЬТАТЫ БЭКТЕСТИНГА")
        print("="*70 + "\n")
        
        metrics = results.get("metrics", {})
        
        print(f"[PERFORMANCE]:")
        print(f"   - Total Return: {metrics.get('total_return', 0):.2f}%")
        print(f"   - Buy & Hold: {metrics.get('buy_hold_return', 0):.2f}%")
        print(f"   - Outperformance: {metrics.get('outperformance', 0):.2f}%")
        print(f"   - Beats Benchmark: {metrics.get('beats_benchmark', False)}")
        
        print(f"\n[RISK METRICS]:")
        print(f"   - Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.4f}")
        print(f"   - Sortino Ratio: {metrics.get('sortino_ratio', 0):.4f}")
        print(f"   - Calmar Ratio: {metrics.get('calmar_ratio', 0):.4f}")
        print(f"   - Max Drawdown: {metrics.get('max_drawdown', 0):.2f}%")
        
        print(f"\n[TRADING STATS]:")
        print(f"   - Total Trades: {metrics.get('total_trades', 0)}")
        print(f"   - Win Rate: {metrics.get('win_rate', 0):.2f}%")
        print(f"   - Avg Win: {metrics.get('avg_win', 0):.2f}%")
        print(f"   - Avg Loss: {metrics.get('avg_loss', 0):.2f}%")
        print(f"   - Profit Factor: {metrics.get('profit_factor', 0):.2f}")
        print(f"   - Exposure Time: {metrics.get('exposure_time', 0):.2f}%")
        
        # Сохранение результатов через встроенную функцию
        from src.backtest import save_backtest_results
        output_path = save_backtest_results(results, output_dir="artifacts/backtest")
        
        print(f"\n[SAVED] Результаты: {output_path}")
        
        print("\n" + "="*70)
        total_ret = metrics.get('total_return', 0)
        if total_ret > 0:
            print("[EXCELLENT] МОДЕЛЬ ПРИБЫЛЬНАЯ!")
        elif total_ret > -5:
            print("[SUCCESS] МОДЕЛЬ ПОЧТИ НА НУЛЕ (близко к прибыли!)")
        else:
            print("[WARNING] Модель всё ещё убыточная")
        print("="*70 + "\n")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

