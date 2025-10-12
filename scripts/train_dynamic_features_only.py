"""
Обучение модели ТОЛЬКО на динамичных фичах (Technical + News + Price)

Удаляем статичные: On-chain, Macro, Social (28 фичей)
Оставляем динамичные: Technical, News, Price (50 фичей)
"""
import json
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.features import build_dataset
from src.db import SessionLocal
from src.modeling import train_xgb_and_save

def main():
    print("\n" + "="*70)
    print("[TRAINING] ОБУЧЕНИЕ ТОЛЬКО НА ДИНАМИЧНЫХ ФИЧАХ")
    print("="*70 + "\n")
    
    # Параметры
    EXCHANGE = "bybit"
    SYMBOL = "BTC/USDT"
    TIMEFRAME = "1h"
    HORIZON_STEPS = 6
    
    print(f"[PARAMS]:")
    print(f"   Exchange: {EXCHANGE}")
    print(f"   Symbol: {SYMBOL}")
    print(f"   Timeframe: {TIMEFRAME}")
    print(f"   Strategy: Remove static features (OnChain, Macro, Social)\n")
    
    # Загрузка данных
    print("[LOADING] Загрузка датасета...")
    db = SessionLocal()
    
    try:
        df, all_features = build_dataset(db, EXCHANGE, SYMBOL, TIMEFRAME, HORIZON_STEPS)
        print(f"[OK] Датасет: {len(df)} строк x {len(all_features)} фичей (изначально)\n")
        
        # Фильтрация: удаляем статичные фичи
        print("[FILTERING] Удаление статичных фичей...")
        
        # Проверка уникальности каждой фичи
        static_features = []
        dynamic_features = []
        
        for feat in all_features:
            if feat in df.columns:
                unique_count = df[feat].nunique()
                if unique_count <= 1:
                    static_features.append(feat)
                    print(f"   [REMOVE] {feat}: unique={unique_count} (static)")
                else:
                    dynamic_features.append(feat)
        
        print(f"\n[STATS]:")
        print(f"   - Static features removed: {len(static_features)}")
        print(f"   - Dynamic features kept: {len(dynamic_features)}")
        print(f"   - Reduction: {len(all_features)} -> {len(dynamic_features)} features\n")
        
        # Сохраняем baseline
        baseline_path = Path("artifacts/metrics.json")
        if baseline_path.exists():
            import shutil
            shutil.copy(baseline_path, "artifacts/metrics_baseline.json")
            print(f"[BACKUP] Baseline сохранён\n")
        
        # Обучение модели с динамичными фичами
        print("[TRAINING] Обучение XGBoost с динамичными фичами...")
        print(f"   Features: {len(dynamic_features)}\n")
        
        metrics, model_path = train_xgb_and_save(
            df,
            dynamic_features,
            artifacts_dir="artifacts",
            mlflow_experiment="myassistent-trading",
            mlflow_run_name=f"{SYMBOL}_{TIMEFRAME}_dynamic_only"
        )
        
        print(f"\n[OK] Модель обучена и сохранена: {model_path}")
        print(f"\n[METRICS]:")
        print(f"   - ROC AUC: {metrics.get('roc_auc', 0):.4f}")
        print(f"   - Accuracy: {metrics['accuracy']:.4f}")
        print(f"   - Total Return: {metrics['total_return']:.4f} ({metrics['total_return']*100:.2f}%)")
        print(f"   - Sharpe: {metrics.get('sharpe_like', 0):.4f}")
        print(f"   - Features used: {len(dynamic_features)}")
        
        # Сравнение с baseline
        baseline_path = Path("artifacts/metrics_baseline.json")
        if baseline_path.exists():
            with open(baseline_path) as f:
                baseline = json.load(f)
            
            print(f"\n[COMPARISON] vs Baseline (with static features):")
            print(f"   - Baseline ROC AUC: {baseline.get('roc_auc', 0):.4f}")
            print(f"   - New ROC AUC: {metrics.get('roc_auc', 0):.4f}")
            
            improvement = ((metrics.get('roc_auc', 0) - baseline.get('roc_auc', 0)) / baseline.get('roc_auc', 1)) * 100
            print(f"   - Improvement: {improvement:+.2f}%")
            
            if improvement > 0:
                print(f"   - Verdict: [SUCCESS] Feature selection helped!")
            else:
                print(f"   - Verdict: [INFO] No improvement from feature selection")
        
        # Сохраняем список динамичных фичей
        with open("artifacts/config/dynamic_features.json", "w") as f:
            json.dump({
                "dynamic_features": dynamic_features,
                "static_features": static_features,
                "n_dynamic": len(dynamic_features),
                "n_static": len(static_features),
            }, f, indent=2)
        
        print("\n[SAVED] Список фичей: artifacts/config/dynamic_features.json")
        
        print("\n" + "="*70)
        print("[SUCCESS] ОБУЧЕНИЕ ЗАВЕРШЕНО!")
        print("="*70)
        print("\nРезультаты:")
        print(f"  - Удалено статичных фичей: {len(static_features)}")
        print(f"  - Использовано динамичных: {len(dynamic_features)}")
        print(f"  - ROC AUC: {metrics.get('roc_auc', 0):.4f}")
        print(f"  - Total Return: {metrics['total_return']*100:.2f}%\n")
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()

