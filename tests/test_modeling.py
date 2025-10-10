"""
Тесты для src/modeling.py (ML пайплайн).
"""
import pytest
import tempfile
import shutil
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
from src.modeling import (
    time_split,
    _evaluate_with_threshold,
    _select_threshold_grid,
    train_xgb_and_save,
    load_latest_model,
    load_model_from_path,
    walk_forward_cv,
)


# --- Fixtures ---


@pytest.fixture
def sample_df():
    """Создаёт тестовый датасет с фичами и целевой переменной."""
    np.random.seed(42)
    n = 500
    df = pd.DataFrame(
        {
            "ret_1": np.random.randn(n) * 0.01,
            "ret_3": np.random.randn(n) * 0.02,
            "rsi_14": np.random.uniform(30, 70, n),
            "future_ret": np.random.randn(n) * 0.03,
        }
    )
    df["y"] = (df["future_ret"] > 0).astype(int)
    df.index = pd.date_range("2023-01-01", periods=n, freq="1h")
    return df


@pytest.fixture
def temp_artifacts_dir():
    """Создаёт временную директорию для артефактов."""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


# --- Тесты time_split ---


def test_time_split_normal():
    """Проверяет корректное разбиение датасета на train/test."""
    df = pd.DataFrame({"a": range(100)})
    train, test = time_split(df, test_ratio=0.2)
    assert len(train) == 80
    assert len(test) == 20
    assert train.index.max() < test.index.min()  # train раньше test


def test_time_split_custom_ratio():
    """Проверяет time_split с разными test_ratio."""
    df = pd.DataFrame({"a": range(200)})
    train, test = time_split(df, test_ratio=0.3)
    assert len(train) == 140
    assert len(test) == 60


def test_time_split_small_df():
    """Проверяет, что малые датасеты вызывают ValueError."""
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="dataset too small"):
        time_split(df, test_ratio=0.2)


def test_time_split_edge_case():
    """Граничный случай: n=2."""
    df = pd.DataFrame({"a": [1, 2]})
    train, test = time_split(df, test_ratio=0.5)
    assert len(train) == 1
    assert len(test) == 1


# --- Тесты _evaluate_with_threshold ---


def test_evaluate_with_threshold():
    """Проверяет вычисление метрик для заданного порога."""
    np.random.seed(42)
    y_true = np.array([0, 0, 1, 1, 1, 0, 1, 0, 1, 1])
    proba = np.array([0.2, 0.3, 0.7, 0.8, 0.6, 0.1, 0.9, 0.4, 0.85, 0.75])
    future_ret = np.array([0.01, -0.02, 0.03, 0.02, 0.01, -0.01, 0.04, -0.02, 0.03, 0.02])

    metrics = _evaluate_with_threshold(y_true, proba, future_ret, thr=0.5)

    assert "accuracy" in metrics
    assert "roc_auc" in metrics
    assert "total_return" in metrics
    assert "sharpe_like" in metrics
    assert 0.0 <= metrics["accuracy"] <= 1.0
    assert metrics["roc_auc"] is None or 0.0 <= metrics["roc_auc"] <= 1.0


def test_evaluate_with_threshold_all_zeros():
    """Случай, когда все предсказания ниже порога."""
    y_true = np.array([1, 1, 1, 1])
    proba = np.array([0.2, 0.3, 0.1, 0.4])
    future_ret = np.array([0.01, 0.02, 0.03, 0.04])

    metrics = _evaluate_with_threshold(y_true, proba, future_ret, thr=0.9)
    # все pred=0, стратегия не торгует
    assert metrics["total_return"] == 0.0


# --- Тесты _select_threshold_grid ---


def test_select_threshold_grid():
    """Проверяет подбор оптимального порога по сетке."""
    np.random.seed(42)
    y_true = np.random.randint(0, 2, 100)
    proba = np.random.uniform(0.3, 0.8, 100)
    future_ret = np.random.randn(100) * 0.02

    grid = np.array([0.45, 0.50, 0.55, 0.60])
    best_thr, best_metrics = _select_threshold_grid(y_true, proba, future_ret, grid=grid)

    assert best_thr in grid
    assert "accuracy" in best_metrics
    assert "total_return" in best_metrics


def test_select_threshold_grid_default():
    """Проверяет работу с дефолтной сеткой."""
    np.random.seed(42)
    y_true = np.random.randint(0, 2, 50)
    proba = np.random.uniform(0.4, 0.7, 50)
    future_ret = np.random.randn(50) * 0.01

    best_thr, best_metrics = _select_threshold_grid(y_true, proba, future_ret, grid=None)
    assert 0.50 <= best_thr <= 0.70


# --- Тесты train_xgb_and_save ---


def test_train_xgb_and_save(sample_df, temp_artifacts_dir):
    """Проверяет обучение XGBoost и сохранение модели."""
    feature_cols = ["ret_1", "ret_3", "rsi_14"]

    metrics, model_path = train_xgb_and_save(
        sample_df, feature_cols, artifacts_dir=temp_artifacts_dir, test_ratio=0.2
    )

    # Проверяем метрики
    assert "accuracy" in metrics
    assert "roc_auc" in metrics
    assert "n_train" in metrics
    assert "n_test" in metrics
    assert "threshold" in metrics
    assert metrics["n_train"] + metrics["n_test"] <= len(sample_df)

    # Проверяем, что модель сохранена
    assert Path(model_path).exists()
    assert model_path.endswith(".pkl")

    # Проверяем артефакты
    metrics_file = Path(temp_artifacts_dir) / "metrics.json"
    features_file = Path(temp_artifacts_dir) / "features.json"
    assert metrics_file.exists()
    assert features_file.exists()


def test_train_xgb_and_save_empty_df(temp_artifacts_dir):
    """Проверяет обработку пустого датасета."""
    df_empty = pd.DataFrame()
    with pytest.raises(ValueError, match="empty dataframe"):
        train_xgb_and_save(df_empty, ["ret_1"], artifacts_dir=temp_artifacts_dir)


def test_train_xgb_and_save_no_features(sample_df, temp_artifacts_dir):
    """Проверяет обработку пустого списка фичей."""
    with pytest.raises(ValueError, match="feature_cols is empty"):
        train_xgb_and_save(sample_df, [], artifacts_dir=temp_artifacts_dir)


def test_train_xgb_and_save_missing_columns(sample_df, temp_artifacts_dir):
    """Проверяет обработку несуществующих колонок."""
    feature_cols = ["ret_1", "nonexistent_col", "rsi_14"]

    # Не должно падать, должно продолжить с доступными колонками
    metrics, model_path = train_xgb_and_save(
        sample_df, feature_cols, artifacts_dir=temp_artifacts_dir, test_ratio=0.2
    )

    assert Path(model_path).exists()
    # Загружаем модель и проверяем, что используются только существующие фичи
    obj = joblib.load(model_path)
    assert "nonexistent_col" not in obj["feature_cols"]


# --- Тесты load_latest_model ---


def test_load_latest_model(sample_df, temp_artifacts_dir):
    """Проверяет загрузку последней модели."""
    feature_cols = ["ret_1", "ret_3", "rsi_14"]

    # Обучаем и сохраняем модель
    metrics, model_path = train_xgb_and_save(
        sample_df, feature_cols, artifacts_dir=temp_artifacts_dir
    )

    # Загружаем
    model, loaded_features, threshold, loaded_path = load_latest_model(artifacts_dir=temp_artifacts_dir)

    assert model is not None
    assert len(loaded_features) > 0
    assert 0.0 <= threshold <= 1.0
    assert Path(loaded_path).exists()


def test_load_latest_model_no_models(temp_artifacts_dir):
    """Проверяет ошибку, если моделей нет."""
    with pytest.raises(FileNotFoundError, match="Модель не найдена"):
        load_latest_model(artifacts_dir=temp_artifacts_dir)


def test_load_model_from_path(sample_df, temp_artifacts_dir):
    """Проверяет загрузку модели по конкретному пути."""
    feature_cols = ["ret_1", "ret_3"]

    _, model_path = train_xgb_and_save(sample_df, feature_cols, artifacts_dir=temp_artifacts_dir)

    model, features, threshold, path = load_model_from_path(model_path)

    assert model is not None
    assert len(features) > 0
    assert Path(path).exists()


def test_load_model_from_path_not_exists(temp_artifacts_dir):
    """Проверяет ошибку при загрузке несуществующего файла."""
    fake_path = Path(temp_artifacts_dir) / "nonexistent.pkl"
    with pytest.raises(FileNotFoundError, match="model file not found"):
        load_model_from_path(str(fake_path))


# --- Тесты walk_forward_cv ---


def test_walk_forward_cv(sample_df):
    """Проверяет walk-forward cross-validation."""
    feature_cols = ["ret_1", "ret_3", "rsi_14"]

    result = walk_forward_cv(
        sample_df,
        feature_cols,
        window_train=100,
        window_test=30,
        step=50,
        inner_valid_ratio=0.2,
        threshold_grid=np.array([0.50, 0.55, 0.60]),
    )

    assert "folds" in result
    assert "summary" in result
    assert "curve" in result
    assert result["summary"]["n_folds"] > 0

    # Проверяем структуру фолдов
    for fold in result["folds"]:
        assert "start" in fold
        assert "end" in fold
        assert "n_train" in fold
        assert "n_test" in fold
        assert "threshold" in fold
        assert "accuracy" in fold

    # Проверяем equity curve
    assert len(result["curve"]["equity"]) > 0
    assert len(result["curve"]["timestamps"]) > 0


def test_walk_forward_cv_empty_df():
    """Проверяет обработку пустого датасета."""
    df_empty = pd.DataFrame()
    result = walk_forward_cv(df_empty, ["ret_1"])

    assert result["summary"]["n_folds"] == 0
    assert result["folds"] == []


def test_walk_forward_cv_insufficient_data():
    """Проверяет обработку недостаточного количества данных."""
    df_small = pd.DataFrame(
        {"ret_1": [0.01, 0.02], "y": [0, 1], "future_ret": [0.01, -0.01]}
    )
    result = walk_forward_cv(df_small, ["ret_1"], window_train=10, window_test=5, step=5)

    # Недостаточно данных для хотя бы одного фолда
    assert result["summary"]["n_folds"] == 0


def test_walk_forward_cv_no_usable_features(sample_df):
    """Проверяет ошибку при отсутствии используемых фичей."""
    with pytest.raises(ValueError, match="no usable feature columns"):
        walk_forward_cv(sample_df, ["nonexistent_col"], window_train=100, window_test=30)


def test_walk_forward_cv_equity_curve_truncation(sample_df):
    """Проверяет усечение equity curve до max_pts."""
    feature_cols = ["ret_1", "ret_3", "rsi_14"]

    result = walk_forward_cv(
        sample_df,
        feature_cols,
        window_train=80,
        window_test=20,
        step=10,  # много фолдов
    )

    # Кривая должна быть усечена до ~400 точек
    assert len(result["curve"]["equity"]) <= 400


# --- Интеграционный тест ---


def test_full_pipeline(sample_df, temp_artifacts_dir):
    """Интеграционный тест: train -> save -> load -> predict."""
    feature_cols = ["ret_1", "ret_3", "rsi_14"]

    # 1. Обучаем и сохраняем
    metrics, model_path = train_xgb_and_save(
        sample_df, feature_cols, artifacts_dir=temp_artifacts_dir, test_ratio=0.2
    )

    # 2. Загружаем
    model, loaded_features, threshold, _ = load_latest_model(artifacts_dir=temp_artifacts_dir)

    # 3. Предсказываем
    X_test = sample_df[loaded_features].dropna().iloc[:10].values
    proba = model.predict_proba(X_test)[:, 1]

    assert len(proba) == 10
    assert all(0.0 <= p <= 1.0 for p in proba)

    # 4. Применяем threshold
    predictions = (proba > threshold).astype(int)
    assert all(p in [0, 1] for p in predictions)

