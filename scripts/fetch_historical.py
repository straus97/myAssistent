"""
Загрузка максимального количества исторических данных
"""
import ccxt
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.db import SessionLocal, Price
from sqlalchemy import and_
import time

def main():
    print("="*70)
    print("[HISTORICAL FETCHER] ЗАГРУЗКА МАКСИМУМА ДАННЫХ")
    print("="*70 + "\n")
    
    exchange_name = "bybit"
    symbol = "BTC/USDT"
    timeframe = "1h"
    
    # Инициализация биржи
    exchange = ccxt.bybit({'enableRateLimit': True})
    
    # Вычисляем дату 3 месяца назад
    since = int((datetime.now() - timedelta(days=90)).timestamp() * 1000)
    
    print(f"[PARAMS]:")
    print(f"   Exchange: {exchange_name}")
    print(f"   Symbol: {symbol}")
    print(f"   Timeframe: {timeframe}")
    print(f"   Since: {datetime.fromtimestamp(since/1000)}")
    print(f"   Expected: ~2160 candles (90 days x 24h)\n")
    
    db = SessionLocal()
    all_ohlcv = []
    
    try:
        # Загрузка порциями (Bybit limit = 1000 за раз)
        current_since = since
        iteration = 0
        max_iterations = 5  # Максимум 5 запросов
        
        while iteration < max_iterations:
            print(f"[FETCH] Iteration {iteration + 1}, since: {datetime.fromtimestamp(current_since/1000)}")
            
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=current_since, limit=1000)
            
            if not ohlcv:
                print("[INFO] No more data available")
                break
            
            print(f"[OK] Fetched {len(ohlcv)} candles")
            all_ohlcv.extend(ohlcv)
            
            # Обновляем since на timestamp последней свечи + 1 hour
            last_ts = ohlcv[-1][0]
            current_since = last_ts + 3600 * 1000
            
            # Если достигли текущего времени - выходим
            if current_since > int(datetime.now().timestamp() * 1000):
                break
            
            iteration += 1
            time.sleep(1)  # Rate limiting
        
        print(f"\n[TOTAL] Загружено {len(all_ohlcv)} свечей всего\n")
        
        # Сохранение в БД
        print("[SAVING] Сохранение в БД...")
        saved_count = 0
        updated_count = 0
        
        for candle in all_ohlcv:
            timestamp_ms, open_price, high, low, close, volume = candle
            
            # Проверка существования
            existing = db.query(Price).filter(and_(
                Price.exchange == exchange_name,
                Price.symbol == symbol,
                Price.timeframe == timeframe,
                Price.ts == timestamp_ms
            )).first()
            
            if existing:
                # Обновление
                existing.open = open_price
                existing.high = high
                existing.low = low
                existing.close = close
                existing.volume = volume
                updated_count += 1
            else:
                # Создание нового
                price = Price(
                    exchange=exchange_name,
                    symbol=symbol,
                    timeframe=timeframe,
                    ts=timestamp_ms,
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume
                )
                db.add(price)
                saved_count += 1
        
        db.commit()
        
        # Итоговая статистика
        total_count = db.query(Price).filter(and_(
            Price.exchange == exchange_name,
            Price.symbol == symbol,
            Price.timeframe == timeframe
        )).count()
        
        print(f"\n[STATS]:")
        print(f"   - Saved: {saved_count} new candles")
        print(f"   - Updated: {updated_count} existing candles")
        print(f"   - Total in DB: {total_count} candles")
        
        # Диапазон данных
        oldest = db.query(Price.ts).filter(and_(
            Price.exchange == exchange_name,
            Price.symbol == symbol,
            Price.timeframe == timeframe
        )).order_by(Price.ts.asc()).first()
        
        newest = db.query(Price.ts).filter(and_(
            Price.exchange == exchange_name,
            Price.symbol == symbol,
            Price.timeframe == timeframe
        )).order_by(Price.ts.desc()).first()
        
        if oldest and newest:
            oldest_dt = datetime.utcfromtimestamp(oldest[0]/1000)
            newest_dt = datetime.utcfromtimestamp(newest[0]/1000)
            days = (newest_dt - oldest_dt).days
            
            print(f"\n[RANGE]:")
            print(f"   - Oldest: {oldest_dt}")
            print(f"   - Newest: {newest_dt}")
            print(f"   - Coverage: {days} days")
        
        print(f"\n[SUCCESS] Датасет расширен до {total_count} строк!")
        
        db.close()
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        db.close()

if __name__ == "__main__":
    main()

