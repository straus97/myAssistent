"""
Скрипт для обучения модели и анализа feature importance
Запуск: python scripts/train_and_analyze.py
"""
import os
import sys
from pathlib import Path
import json
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Для сохранения графиков без GUI
import matplotlib.pyplot as plt

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_db, init_db
from src.features import build_dataset
from src.modeling import train_xgb_and_save, load_latest_model
import joblib


def analyze_feature_importance(model_path: str, feature_cols: list, top_n: int = 20):
    """Анализ важности фич и категоризация"""
    print(f"\n{'='*70}")
    print(f"📊 FEATURE IMPORTANCE АНАЛИЗ")
    print(f"{'='*70}\n")
    
    # Загружаем модель
    obj = joblib.load(model_path)
    model = obj.get("model") if isinstance(obj, dict) else obj
    
    if not hasattr(model, "feature_importances_"):
        print("❌ Модель не поддерживает feature_importances_")
        return
    
    # Получаем важность фич
    importance = model.feature_importances_
    feature_importance = pd.DataFrame({
        'feature': feature_cols,
        'importance': importance
    }).sort_values('importance', ascending=False)
    
    # Категоризация фич
    def categorize_feature(feat):
        if feat.startswith('ret_') or feat == 'vol_norm':
            return 'Price'
        elif feat.startswith('rsi') or feat.startswith('bb_') or feat.startswith('macd') or \
             feat.startswith('atr') or feat.startswith('adx') or feat.startswith('stoch') or \
             feat.startswith('williams') or feat.startswith('cci') or feat.startswith('ema'):
            return 'Technical'
        elif feat.startswith('news_') or feat.startswith('sent_') or feat.startswith('tag_'):
            return 'News'
        elif feat.startswith('onchain_'):
            return 'OnChain'
        elif feat.startswith('macro_'):
            return 'Macro'
        elif feat.startswith('social_'):
            return 'Social'
        else:
            return 'Other'
    
    feature_importance['category'] = feature_importance['feature'].apply(categorize_feature)
    
    # Топ-20 фич
    print(f"🏆 ТОП-{top_n} ВАЖНЫХ ФИЧ:\n")
    print(feature_importance.head(top_n).to_string(index=False))
    
    # Статистика по категориям
    print(f"\n\n📈 ВАЖНОСТЬ ПО КАТЕГОРИЯМ:\n")
    category_stats = feature_importance.groupby('category').agg({
        'importance': ['sum', 'mean', 'count']
    }).round(4)
    category_stats.columns = ['Total_Importance', 'Avg_Importance', 'Count']
    category_stats = category_stats.sort_values('Total_Importance', ascending=False)
    print(category_stats)
    
    # Сохраняем результаты
    output_dir = Path("artifacts/analysis")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # JSON отчёт
    report = {
        "top_features": feature_importance.head(top_n).to_dict('records'),
        "category_stats": category_stats.reset_index().to_dict('records'),
        "total_features": len(feature_cols),
        "timestamp": pd.Timestamp.now().isoformat()
    }
    
    with open(output_dir / "feature_importance.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # График важности топ-20
    plt.figure(figsize=(12, 8))
    top_features = feature_importance.head(top_n)
    colors = top_features['category'].map({
        'Price': '#FF6B6B',
        'Technical': '#4ECDC4',
        'News': '#45B7D1',
        'OnChain': '#FFA07A',
        'Macro': '#98D8C8',
        'Social': '#F7DC6F'
    })
    
    plt.barh(range(top_n), top_features['importance'], color=colors)
    plt.yticks(range(top_n), top_features['feature'])
    plt.xlabel('Importance', fontsize=12)
    plt.title(f'Top {top_n} Feature Importance', fontsize=14, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(output_dir / "feature_importance_top20.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    # График по категориям
    plt.figure(figsize=(10, 6))
    category_stats.plot(kind='bar', y='Total_Importance', legend=False, color='#4ECDC4')
    plt.xlabel('Category', fontsize=12)
    plt.ylabel('Total Importance', fontsize=12)
    plt.title('Feature Importance by Category', fontsize=14, fontweight='bold')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "feature_importance_by_category.png", dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"\n✅ Результаты сохранены:")
    print(f"   - {output_dir / 'feature_importance.json'}")
    print(f"   - {output_dir / 'feature_importance_top20.png'}")
    print(f"   - {output_dir / 'feature_importance_by_category.png'}\n")
    
    return feature_importance


def compare_with_baseline(new_metrics: dict, baseline_path: str = "artifacts/metrics.json"):
    """Сравнение новой модели с baseline"""
    print(f"\n{'='*70}")
    print(f"📊 СРАВНЕНИЕ С BASELINE")
    print(f"{'='*70}\n")
    
    try:
        with open(baseline_path, "r") as f:
            baseline = json.load(f)
        
        print(f"{'Метрика':<20} {'Baseline':<15} {'New Model':<15} {'Изменение':<15}")
        print("-" * 70)
        
        metrics_to_compare = ['accuracy', 'roc_auc', 'sharpe_like', 'total_return']
        improvements = {}
        
        for metric in metrics_to_compare:
            base_val = baseline.get(metric)
            new_val = new_metrics.get(metric)
            
            if base_val is not None and new_val is not None:
                if base_val != 0:
                    change_pct = ((new_val - base_val) / abs(base_val)) * 100
                else:
                    change_pct = 0
                
                change_str = f"{change_pct:+.1f}%"
                if change_pct > 0:
                    change_str = f"✅ {change_str}"
                elif change_pct < 0:
                    change_str = f"❌ {change_str}"
                else:
                    change_str = "→ 0.0%"
                
                improvements[metric] = change_pct
                
                print(f"{metric:<20} {base_val:<15.4f} {new_val:<15.4f} {change_str:<15}")
            else:
                print(f"{metric:<20} {'N/A':<15} {'N/A':<15} {'N/A':<15}")
        
        # Итоговая оценка
        print("\n" + "="*70)
        avg_improvement = sum(improvements.values()) / len(improvements) if improvements else 0
        
        if avg_improvement > 5:
            verdict = "🎉 ОТЛИЧНОЕ УЛУЧШЕНИЕ!"
        elif avg_improvement > 0:
            verdict = "✅ Улучшение"
        elif avg_improvement > -5:
            verdict = "⚠️ Небольшое ухудшение"
        else:
            verdict = "❌ Значительное ухудшение"
        
        print(f"Средняя разница: {avg_improvement:+.1f}%")
        print(f"Вердикт: {verdict}")
        print("="*70 + "\n")
        
        return improvements
        
    except FileNotFoundError:
        print("❌ Baseline метрики не найдены. Текущая модель станет baseline.\n")
        return None


def main():
    print("\n" + "="*70)
    print("🚀 ОБУЧЕНИЕ МОДЕЛИ И FEATURE IMPORTANCE АНАЛИЗ")
    print("="*70 + "\n")
    
    # Параметры обучения
    EXCHANGE = "bybit"
    SYMBOL = "BTC/USDT"
    TIMEFRAME = "1h"
    HORIZON_STEPS = 6
    
    print(f"📌 Параметры:")
    print(f"   Exchange: {EXCHANGE}")
    print(f"   Symbol: {SYMBOL}")
    print(f"   Timeframe: {TIMEFRAME}")
    print(f"   Horizon: {HORIZON_STEPS} steps\n")
    
    # Инициализация БД
    print("🔄 Подключение к БД...")
    init_db()
    db = next(get_db())
    
    try:
        # Построение датасета
        print("🔄 Построение датасета с расширенными фичами...")
        df, feature_cols = build_dataset(db, EXCHANGE, SYMBOL, TIMEFRAME, HORIZON_STEPS)
        print(f"✅ Датасет построен: {len(df)} строк × {len(feature_cols)} фич\n")
        
        if len(df) < 200:
            print("❌ Недостаточно данных для обучения (< 200 строк)")
            return
        
        # Сохраняем старые метрики как baseline (если есть)
        baseline_path = Path("artifacts/metrics.json")
        if baseline_path.exists():
            baseline_backup = Path("artifacts/metrics_baseline.json")
            import shutil
            shutil.copy(baseline_path, baseline_backup)
            print(f"💾 Baseline сохранён: {baseline_backup}\n")
        
        # Обучение модели
        print("🔄 Обучение XGBoost модели...")
        print("   (это может занять 2-5 минут на больших данных)\n")
        
        metrics, model_path = train_xgb_and_save(
            df, 
            feature_cols, 
            artifacts_dir="artifacts",
            mlflow_experiment="myassistent-trading",
            mlflow_run_name=f"{SYMBOL}_{TIMEFRAME}_training"
        )
        
        print(f"\n✅ Модель обучена и сохранена: {model_path}")
        print(f"\n📊 МЕТРИКИ МОДЕЛИ:")
        print(f"   - Accuracy: {metrics['accuracy']:.4f}")
        print(f"   - ROC AUC: {metrics.get('roc_auc', 0):.4f}")
        print(f"   - Threshold: {metrics['threshold']:.4f}")
        print(f"   - Total Return: {metrics['total_return']:.4f} ({metrics['total_return']*100:.2f}%)")
        print(f"   - Sharpe-like: {metrics.get('sharpe_like', 0):.4f}")
        print(f"   - Train size: {metrics['n_train']} rows")
        print(f"   - Test size: {metrics['n_test']} rows\n")
        
        # Feature Importance Анализ
        analyze_feature_importance(model_path, feature_cols, top_n=20)
        
        # Сравнение с baseline
        if Path("artifacts/metrics_baseline.json").exists():
            compare_with_baseline(metrics, "artifacts/metrics_baseline.json")
        else:
            print("ℹ️ Baseline метрики отсутствуют. Текущая модель - первая.\n")
        
        print("="*70)
        print("✅ ВСЁ ГОТОВО!")
        print("="*70)
        print("\nСледующие шаги:")
        print("1. Проверьте MLflow UI: http://localhost:5000")
        print("2. Запустите бэктест: POST /backtest/run")
        print("3. Посмотрите графики в artifacts/analysis/\n")
        
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

