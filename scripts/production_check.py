#!/usr/bin/env python3
"""
Production Readiness Check

Проверяет готовность системы к production deployment:
1. Все обязательные переменные окружения установлены
2. Сервисы доступны (Database, MLflow, etc.)
3. Модель обучена и работает
4. Risk management настроен
5. Мониторинг подключен
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


def check_env_variables() -> Tuple[bool, List[str]]:
    """Проверяет обязательные переменные окружения"""
    print("\n[1/6] Проверка переменных окружения...")
    
    required_vars = {
        "API_KEY": "Защита API endpoints",
        "DATABASE_URL": "Подключение к БД",
    }
    
    recommended_vars = {
        "SENTRY_DSN": "Error tracking в production",
        "HEALTHCHECK_URL": "Uptime monitoring",
        "TELEGRAM_BOT_TOKEN": "Уведомления",
        "MLFLOW_TRACKING_URI": "ML tracking",
    }
    
    issues = []
    
    # Проверка обязательных
    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value:
            issues.append(f"REQUIRED: {var} не установлен ({description})")
            print(f"  FAIL: {var} - {description}")
        else:
            print(f"  PASS: {var} - установлен")
    
    # Проверка рекомендованных
    for var, description in recommended_vars.items():
        value = os.getenv(var)
        if not value:
            print(f"  WARN: {var} не установлен ({description})")
        else:
            print(f"  PASS: {var} - установлен")
    
    return len([i for i in issues if "REQUIRED" in i]) == 0, issues


def check_database() -> Tuple[bool, List[str]]:
    """Проверяет подключение к БД"""
    print("\n[2/6] Проверка подключения к БД...")
    
    issues = []
    
    try:
        from src.db import SessionLocal
        from sqlalchemy import text
        
        with SessionLocal() as db:
            result = db.execute(text("SELECT 1")).scalar()
            
            if result == 1:
                print("  PASS: Подключение к БД работает")
                
                # Проверка таблиц
                from src.db import Price, SignalEvent
                prices_count = db.query(Price).count()
                signals_count = db.query(SignalEvent).count()
                
                print(f"  INFO: Prices: {prices_count} строк")
                print(f"  INFO: Signals: {signals_count} строк")
                
                if prices_count == 0:
                    issues.append("WARNING: Нет исторических цен в БД")
                    print("  WARN: Нет исторических цен")
                
                return True, issues
    
    except Exception as e:
        issues.append(f"ERROR: Не удалось подключиться к БД: {e}")
        print(f"  FAIL: {e}")
        return False, issues


def check_model() -> Tuple[bool, List[str]]:
    """Проверяет наличие обученной модели"""
    print("\n[3/6] Проверка ML модели...")
    
    issues = []
    
    try:
        from pathlib import Path
        import joblib
        
        # Ищем последнюю модель в artifacts/models/
        models_dir = Path("artifacts/models")
        if not models_dir.exists():
            issues.append("ERROR: Директория artifacts/models/ не существует")
            print("  FAIL: Нет директории моделей")
            return False, issues
        
        # Ищем файлы моделей
        model_files = list(models_dir.glob("model_*.pkl"))
        if not model_files:
            issues.append("WARNING: Нет обученных моделей в artifacts/models/ (запустите POST /model/train)")
            print("  WARN: Модели не найдены (обучите модель через POST /model/train)")
            return True, issues  # Не критично - можно обучить после запуска
        
        # Берем последнюю модель
        model_path = max(model_files, key=lambda p: p.stat().st_mtime)
        
        if not model_path:
            issues.append("ERROR: Нет активной модели для BTC/USDT 1h")
            print("  FAIL: Модель не найдена")
            return False, issues
        
        if not Path(model_path).exists():
            issues.append(f"ERROR: Модель не существует: {model_path}")
            print(f"  FAIL: Файл не найден: {model_path}")
            return False, issues
        
        # Попытка загрузить модель
        model = joblib.load(model_path)
        print(f"  PASS: Модель найдена и загружена")
        print(f"  INFO: Path: {model_path}")
        
        # Проверка метрик
        metrics_path = Path("artifacts/metrics.json")
        if metrics_path.exists():
            import json
            metrics = json.loads(metrics_path.read_text())
            
            roc_auc = metrics.get("roc_auc", 0)
            sharpe = metrics.get("sharpe_like", 0)
            
            print(f"  INFO: ROC AUC: {roc_auc:.4f}")
            print(f"  INFO: Sharpe-like: {sharpe:.4f}")
            
            if roc_auc < 0.52:
                issues.append(f"WARNING: ROC AUC низкий ({roc_auc:.4f} < 0.52)")
                print(f"  WARN: ROC AUC ниже рекомендуемого")
        
        return True, issues
    
    except Exception as e:
        issues.append(f"ERROR: Ошибка проверки модели: {e}")
        print(f"  FAIL: {e}")
        return False, issues


def check_risk_management() -> Tuple[bool, List[str]]:
    """Проверяет настройку risk management"""
    print("\n[4/6] Проверка Risk Management...")
    
    issues = []
    
    try:
        from src.risk_management import load_risk_config
        
        config = load_risk_config()
        
        if not config.get("enabled", True):
            issues.append("WARNING: Risk Management выключен!")
            print("  WARN: Risk Management выключен")
        else:
            print("  PASS: Risk Management включен")
        
        # Проверка Stop-Loss
        sl_config = config.get("stop_loss", {})
        if sl_config.get("enabled", True):
            sl_pct = sl_config.get("percentage", 0) * 100
            print(f"  PASS: Stop-Loss включен ({sl_pct:.1f}%)")
        else:
            issues.append("WARNING: Stop-Loss выключен")
            print("  WARN: Stop-Loss выключен")
        
        # Проверка Take-Profit
        tp_config = config.get("take_profit", {})
        if tp_config.get("enabled", True):
            tp_pct = tp_config.get("percentage", 0) * 100
            print(f"  PASS: Take-Profit включен ({tp_pct:.1f}%)")
        else:
            issues.append("WARNING: Take-Profit выключен")
            print("  WARN: Take-Profit выключен")
        
        # Проверка Max Exposure
        me_config = config.get("max_exposure", {})
        if me_config.get("enabled", True):
            me_pct = me_config.get("percentage", 0) * 100
            print(f"  PASS: Max Exposure включен ({me_pct:.1f}%)")
        else:
            issues.append("WARNING: Max Exposure выключен")
            print("  WARN: Max Exposure выключен")
        
        return len(issues) == 0, issues
    
    except Exception as e:
        issues.append(f"ERROR: Ошибка проверки risk management: {e}")
        print(f"  FAIL: {e}")
        return False, issues


def check_monitoring() -> Tuple[bool, List[str]]:
    """Проверяет настройку мониторинга"""
    print("\n[5/6] Проверка мониторинга...")
    
    issues = []
    
    # Sentry
    sentry_dsn = os.getenv("SENTRY_DSN")
    if sentry_dsn:
        print("  PASS: Sentry DSN настроен")
    else:
        issues.append("WARNING: SENTRY_DSN не установлен - нет error tracking")
        print("  WARN: Sentry не настроен")
    
    # Healthchecks.io
    healthcheck_url = os.getenv("HEALTHCHECK_URL")
    if healthcheck_url:
        print("  PASS: Healthcheck URL настроен")
    else:
        issues.append("WARNING: HEALTHCHECK_URL не установлен - нет uptime monitoring")
        print("  WARN: Healthchecks.io не настроен")
    
    # Prometheus
    enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
    if enable_metrics:
        print("  PASS: Prometheus metrics включены")
    else:
        print("  WARN: Prometheus metrics выключены")
    
    # MLflow
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI")
    if mlflow_uri:
        print(f"  PASS: MLflow URI настроен ({mlflow_uri})")
    else:
        print("  WARN: MLflow не настроен")
    
    return len([i for i in issues if "ERROR" in i]) == 0, issues


def check_paper_trading() -> Tuple[bool, List[str]]:
    """Проверяет настройку paper trading"""
    print("\n[6/6] Проверка Paper Trading...")
    
    issues = []
    
    try:
        from src.trade import paper_get_equity, paper_get_positions
        
        equity_data = paper_get_equity()
        positions = paper_get_positions()
        
        equity = equity_data.get("equity", 0)
        print(f"  INFO: Equity: ${equity:.2f}")
        print(f"  INFO: Открытых позиций: {len(positions)}")
        
        if equity <= 0:
            issues.append("WARNING: Equity = 0, установите начальный капитал")
            print("  WARN: Equity = 0")
        else:
            print("  PASS: Paper trading настроен")
        
        # Проверка Paper Monitor
        from src.paper_trading_monitor import get_monitor_status
        
        monitor = get_monitor_status()
        if monitor.get("enabled", False):
            print("  PASS: Paper Monitor включен")
        else:
            print("  INFO: Paper Monitor выключен (запустите через POST /paper-monitor/start)")
        
        return True, issues
    
    except Exception as e:
        issues.append(f"ERROR: Ошибка проверки paper trading: {e}")
        print(f"  FAIL: {e}")
        return False, issues


def main():
    """Основная функция"""
    print("=" * 60)
    print("[PRODUCTION] Production Readiness Check")
    print("=" * 60)
    
    all_checks = []
    all_issues = []
    
    # Запускаем все проверки
    checks = [
        ("Environment Variables", check_env_variables),
        ("Database", check_database),
        ("ML Model", check_model),
        ("Risk Management", check_risk_management),
        ("Monitoring", check_monitoring),
        ("Paper Trading", check_paper_trading),
    ]
    
    for name, check_func in checks:
        success, issues = check_func()
        all_checks.append((name, success))
        all_issues.extend(issues)
    
    # Итоговый отчёт
    print("\n" + "=" * 60)
    print("[SUMMARY] Итоговый отчёт")
    print("=" * 60)
    
    for name, success in all_checks:
        status = "PASS" if success else "FAIL"
        print(f"  {status}: {name}")
    
    # Выводим все проблемы
    if all_issues:
        print(f"\n[ISSUES] Найдено проблем: {len(all_issues)}")
        print("-" * 60)
        
        errors = [i for i in all_issues if "ERROR" in i]
        warnings = [i for i in all_issues if "WARNING" in i]
        
        if errors:
            print("\nКРИТИЧНЫЕ ОШИБКИ:")
            for issue in errors:
                print(f"  - {issue}")
        
        if warnings:
            print("\nПРЕДУПРЕЖДЕНИЯ:")
            for issue in warnings:
                print(f"  - {issue}")
    
    # Итоговая оценка
    print("\n" + "=" * 60)
    
    critical_failed = sum(1 for name, success in all_checks if not success)
    
    if critical_failed == 0 and not any("ERROR" in i for i in all_issues):
        print("[SUCCESS] Система готова к production deployment!")
        print("=" * 60)
        return 0
    else:
        print(f"[FAILED] Система НЕ готова к production!")
        print(f"Критичных проблем: {critical_failed}")
        print("Исправьте проблемы и запустите проверку снова.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

