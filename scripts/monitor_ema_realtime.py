"""
Real-time мониторинг EMA Crossover стратегии

ЦЕЛЬ: Проверять систему каждые 60 секунд и логировать все сигналы

ПРОВЕРКИ:
1. Система работает (API доступен)
2. Цены обновляются
3. Сигналы генерируются
4. Paper trading equity отслеживается
5. Нет критических ошибок

USAGE:
    python scripts/monitor_ema_realtime.py
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import time
import requests
import logging
from datetime import datetime
from typing import Dict, Any, List
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("artifacts/monitor_ema_realtime.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class EMAMonitor:
    """Real-time монитор для EMA Crossover стратегии"""
    
    def __init__(
        self,
        api_url: str = "http://localhost:8000",
        api_key: str = None,
        check_interval: int = 60,
        symbols: List[str] = None
    ):
        self.api_url = api_url
        self.api_key = api_key or self._load_api_key()
        self.check_interval = check_interval
        self.symbols = symbols or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
        
        self.headers = {"X-API-Key": self.api_key}
        self.last_equity = None
        self.last_signals = []
        self.iteration = 0
    
    def _load_api_key(self) -> str:
        """Загружает API key из .env"""
        env_file = Path(".env")
        if env_file.exists():
            with open(env_file, "r") as f:
                for line in f:
                    if line.startswith("API_KEY="):
                        return line.strip().split("=", 1)[1]
        
        # Fallback к дефолтному ключу
        return "4ac25807582dae9f9b91396d7ccd223ba796bfdb7077241a994bdeff874b4faf"
    
    def check_api_health(self) -> bool:
        """Проверяет доступность API"""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"API health check failed: {e}")
            return False
    
    def get_monitor_status(self) -> Dict[str, Any]:
        """Получает статус paper trading monitor"""
        try:
            response = requests.get(
                f"{self.api_url}/paper-monitor/status",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Monitor status returned {response.status_code}")
                return {}
        
        except Exception as e:
            logger.error(f"Failed to get monitor status: {e}")
            return {}
    
    def get_recent_signals(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Получает последние сигналы"""
        try:
            response = requests.get(
                f"{self.api_url}/signals/recent?limit={limit}",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Recent signals returned {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"Failed to get recent signals: {e}")
            return []
    
    def get_equity(self) -> Dict[str, Any]:
        """Получает текущий equity"""
        try:
            response = requests.get(
                f"{self.api_url}/trade/equity",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Equity returned {response.status_code}")
                return {}
        
        except Exception as e:
            logger.error(f"Failed to get equity: {e}")
            return {}
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Получает открытые позиции"""
        try:
            response = requests.get(
                f"{self.api_url}/trade/positions",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Positions returned {response.status_code}")
                return []
        
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []
    
    def check_for_new_signals(self, current_signals: List[Dict]) -> List[Dict]:
        """Проверяет наличие новых сигналов"""
        if not self.last_signals:
            self.last_signals = current_signals
            return current_signals
        
        # Сравниваем по timestamp
        last_timestamps = {s.get("created_at") for s in self.last_signals}
        new_signals = [s for s in current_signals if s.get("created_at") not in last_timestamps]
        
        self.last_signals = current_signals
        return new_signals
    
    def log_summary(
        self,
        monitor_status: Dict,
        equity: Dict,
        positions: List[Dict],
        new_signals: List[Dict]
    ) -> None:
        """Логирует сводку текущего состояния"""
        self.iteration += 1
        
        logger.info("\n" + "="*80)
        logger.info(f"📊 EMA MONITOR - Iteration #{self.iteration}")
        logger.info("="*80)
        
        # Monitor status
        if monitor_status:
            enabled = monitor_status.get("enabled", False)
            auto_execute = monitor_status.get("auto_execute", False)
            last_update = monitor_status.get("last_update", "Never")
            
            logger.info(f"\n🔄 MONITOR STATUS:")
            logger.info(f"  Enabled: {'✅ YES' if enabled else '❌ NO'}")
            logger.info(f"  Auto-execute: {'✅ ON' if auto_execute else '⚠️ OFF'}")
            logger.info(f"  Last update: {last_update}")
            
            stats = monitor_status.get("stats", {})
            logger.info(f"  Total updates: {stats.get('total_updates', 0)}")
            logger.info(f"  Total signals: {stats.get('total_signals', 0)}")
            logger.info(f"  Errors: {stats.get('errors', 0)}")
        
        # Equity
        if equity:
            current_equity = equity.get("equity", 0)
            total_pnl = equity.get("total_pnl", 0)
            pnl_pct = (total_pnl / 10000.0) * 100 if current_equity > 0 else 0
            
            logger.info(f"\n💰 EQUITY:")
            logger.info(f"  Current: ${current_equity:,.2f}")
            logger.info(f"  P&L: ${total_pnl:+,.2f} ({pnl_pct:+.2f}%)")
            
            # Изменение equity
            if self.last_equity is not None:
                equity_change = current_equity - self.last_equity
                equity_change_pct = (equity_change / self.last_equity) * 100 if self.last_equity > 0 else 0
                
                if equity_change > 0:
                    logger.info(f"  Change: +${equity_change:.2f} (+{equity_change_pct:.2f}%) ↗️")
                elif equity_change < 0:
                    logger.info(f"  Change: ${equity_change:.2f} ({equity_change_pct:.2f}%) ↘️")
                else:
                    logger.info(f"  Change: $0.00 (0.00%) →")
            
            self.last_equity = current_equity
        
        # Positions
        logger.info(f"\n📈 POSITIONS:")
        if positions:
            for pos in positions[:5]:  # Показываем первые 5
                symbol = pos.get("symbol", "???")
                entry_price = pos.get("entry_price", 0)
                current_price = pos.get("current_price", 0)
                pnl_pct = pos.get("pnl_pct", 0)
                duration = pos.get("duration_hours", 0)
                
                logger.info(
                    f"  {symbol}: Entry ${entry_price:.2f} → ${current_price:.2f} "
                    f"({pnl_pct:+.2f}%) [{duration:.1f}h]"
                )
            
            if len(positions) > 5:
                logger.info(f"  ... and {len(positions) - 5} more")
        else:
            logger.info(f"  No open positions")
        
        # New signals
        if new_signals:
            logger.info(f"\n🚨 NEW SIGNALS ({len(new_signals)}):")
            for sig in new_signals:
                symbol = sig.get("symbol", "???")
                signal_type = sig.get("signal", "???")
                price = sig.get("price", 0)
                prob = sig.get("prob_up", sig.get("probability", 0))
                created_at = sig.get("created_at", "???")
                
                logger.info(
                    f"  {symbol}: {signal_type} @ ${price:.2f} "
                    f"(prob: {prob:.1%}) at {created_at}"
                )
        else:
            logger.info(f"\n✅ No new signals")
        
        logger.info("\n" + "="*80 + "\n")
    
    def run(self) -> None:
        """Запускает мониторинг в бесконечном цикле"""
        logger.info("🚀 Starting EMA Real-time Monitor")
        logger.info(f"API URL: {self.api_url}")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Symbols: {', '.join(self.symbols)}")
        logger.info("\n" + "="*80 + "\n")
        
        while True:
            try:
                # 1. Проверяем API
                if not self.check_api_health():
                    logger.error("❌ API is not available!")
                    time.sleep(self.check_interval)
                    continue
                
                # 2. Получаем данные
                monitor_status = self.get_monitor_status()
                equity = self.get_equity()
                positions = self.get_positions()
                recent_signals = self.get_recent_signals(limit=10)
                
                # 3. Проверяем новые сигналы
                new_signals = self.check_for_new_signals(recent_signals)
                
                # 4. Логируем сводку
                self.log_summary(monitor_status, equity, positions, new_signals)
                
                # 5. Ждём следующей проверки
                time.sleep(self.check_interval)
            
            except KeyboardInterrupt:
                logger.info("\n\n⏹️  Monitor stopped by user")
                break
            
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}", exc_info=True)
                time.sleep(self.check_interval)


def main():
    """Основная функция"""
    
    # Параметры монитора
    API_URL = "http://localhost:8000"
    CHECK_INTERVAL = 60  # секунд
    SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    
    monitor = EMAMonitor(
        api_url=API_URL,
        check_interval=CHECK_INTERVAL,
        symbols=SYMBOLS
    )
    
    monitor.run()


if __name__ == "__main__":
    main()

