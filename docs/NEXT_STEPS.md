# 📋 Следующие Шаги — План Задач для Новых Чатов

> **Важно:** Каждая крупная задача требует отдельного чата. Перед началом нового чата читай этот файл + PROJECT_OVERVIEW.md + ROADMAP.md.

## Текущий Статус: Версия 0.7 → 0.8

**Завершено в предыдущем чате:**
- ✅ Объединена БД (assistant.db only)
- ✅ Добавлена документация (PROJECT_OVERVIEW, ROADMAP, CHANGELOG)
- ✅ Обновлён requirements.txt (ruff, black, mypy, pytest, alembic, pre-commit)
- ✅ Инициализированы Alembic миграции
- ✅ Создан .gitignore
- ✅ Создан .pre-commit-config.yaml
- ✅ Удалён src/hello_ai.py
- ✅ Обновлён README.md
- ✅ Применён Black форматтер
- ✅ Код закоммичен и отправлен в GitHub

**Завершено в текущем чате (2025-10-10):**
- ✅ Декомпозиция main.py на роутеры (Часть 1/2):
  - ✅ Создана структура src/routers/ с 15 роутерами
  - ✅ Создан src/dependencies.py (общие зависимости)
  - ✅ Создан src/utils.py (утилиты)
  - ✅ Полностью реализовано: news, prices, dataset, report, watchlist, risk, notify, models, signals
  - ⏳ Частично: trade (основные эндпоинты работают, ручные команды - заглушки)
  - ⏳ Заглушки: automation, ui, journal, backup

- ✅ Декомпозиция main.py (Часть 2/2 - завершено):
  - ✅ main.py сокращён с 4716 строк до 780 строк (~84% сокращение)
  - ✅ Подключены все 15 роутеров через app.include_router()
  - ✅ Удалены дублирующиеся функции (перенесены в dependencies.py и utils.py)
  - ✅ Оставлены только: app setup, CORS, static files, scheduler, startup/shutdown
  - ✅ Создан бэкап: src/main_old.py
  - ✅ Коммит: refactor: decompose main.py into modular routers (Part 2/2)

**Осталось в версии 0.8:**
- ⏳ Завершение заглушек в роутерах:
  - automation.py (scheduler status integration)
  - ui.py (HTML endpoints)
  - journal.py (CSV/XLSX export)
  - backup.py (snapshot endpoint)
  - trade.py (manual buy/sell commands)
- ⏳ Тестирование всех эндпоинтов в Swagger UI
- ⏳ Расширение тестов (coverage >80%)
- ⏳ Исправление ruff ошибок (E701, E702)
- ⏳ Создание docs/API.md
- ⏳ Настройка CI/CD (GitHub Actions)

---

## 🎯 Задача #1: Декомпозиция main.py (Приоритет: КРИТИЧНО)

**Цель:** Разбить main.py (4000+ строк, 83 эндпоинта) на модульные роутеры.

### Контекст
- **Файл:** `src/main.py` (4030 строк)
- **Проблема:** Монолит, сложно поддерживать
- **Решение:** APIRouter по доменам (News, Prices, Models, Signals, Trade, Risk, Automation, UI, etc.)

### План Действий

#### Шаг 1: Подготовка (15 мин)
1. Создать структуру:
   ```
   src/routers/
   ├── __init__.py
   ├── news.py          # News (6 эндпоинтов)
   ├── prices.py        # Prices (2 эндпоинта)
   ├── dataset.py       # Dataset (1 эндпоинт)
   ├── models.py        # Model (10 эндпоинтов)
   ├── signals.py       # Signal (4 эндпоинта)
   ├── risk.py          # Risk (2 эндпоинта)
   ├── notify.py        # Notify (3 эндпоинта)
   ├── trade.py         # Trade (14 эндпоинтов)
   ├── automation.py    # Automation (2 эндпоинта)
   ├── watchlist.py     # Watchlist (6 эндпоинтов)
   ├── report.py        # Report (2 эндпоинта)
   ├── ui.py            # UI (3 эндпоинта)
   ├── journal.py       # Journal (2 эндпоинта)
   ├── backup.py        # Backup (1 эндпоинт)
   ├── db_admin.py      # DB (3 эндпоинта)
   └── debug.py         # Debug (4 эндпоинта)
   ```

2. Читать `src/main.py` для понимания зависимостей

#### Шаг 2: Выделение роутеров (по одному за раз)

**Пример: News Router**
```python
# src/routers/news.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.db import get_db
from src.main import require_api_key  # временно, потом вынести в src/dependencies.py

router = APIRouter(prefix="/news", tags=["News"])

@router.post("/fetch")
def fetch_news(db: Session = Depends(get_db), _=Depends(require_api_key)):
    # код из main.py
    ...

@router.post("/analyze")
def analyze_news(db: Session = Depends(get_db), _=Depends(require_api_key)):
    ...

# и т.д.
```

**Порядок выделения роутеров (от простого к сложному):**
1. news.py (6 эндпоинтов, независимый)
2. prices.py (2 эндпоинта, зависит от src/prices.py)
3. dataset.py (1 эндпоинт, зависит от src/features.py)
4. report.py (2 эндпоинта, зависит от src/reports.py)
5. watchlist.py (6 эндпоинтов, зависит от src/watchlist.py)
6. risk.py (2 эндпоинта, зависит от src/risk.py)
7. notify.py (3 эндпоинта, зависит от src/notify.py)
8. models.py (10 эндпоинтов, зависит от src/modeling.py, src/champion.py)
9. signals.py (4 эндпоинта, зависит от models, risk, notify)
10. trade.py (14 эндпоинтов, зависит от src/trade.py, signals)
11. automation.py (2 эндпоинта, зависит от всех модулей)
12. ui.py, journal.py, backup.py, db_admin.py, debug.py

#### Шаг 3: Обновление main.py

```python
# src/main.py (после рефакторинга)
from fastapi import FastAPI
from src.routers import news, prices, models, signals, trade, risk, notify, automation, watchlist, report, ui, journal, backup, db_admin, debug

app = FastAPI(...)

# Подключаем роутеры
app.include_router(news.router)
app.include_router(prices.router)
app.include_router(models.router)
app.include_router(signals.router)
app.include_router(trade.router)
app.include_router(risk.router)
app.include_router(notify.router)
app.include_router(automation.router)
app.include_router(watchlist.router)
app.include_router(report.router)
app.include_router(ui.router)
app.include_router(journal.router)
app.include_router(backup.router)
app.include_router(db_admin.router)
app.include_router(debug.router)

# Оставить только:
# - startup/shutdown events
# - middleware
# - корневые эндпоинты (/, /ping)
# - утилиты (require_api_key, get_db и т.д.)
```

#### Шаг 4: Вынос зависимостей
```python
# src/dependencies.py
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader
import os

API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def require_api_key(x_api_key: Optional[str] = Security(api_key_header)):
    if not API_KEY:
        raise HTTPException(503, detail="Set API_KEY in env")
    if not x_api_key:
        raise HTTPException(401, detail="X-API-Key header required")
    if x_api_key != API_KEY:
        raise HTTPException(401, detail="Invalid API key")
    return True
```

#### Шаг 5: Тестирование
1. Запустить сервер: `uvicorn src.main:app --reload`
2. Проверить Swagger UI: http://127.0.0.1:8000/docs
3. Убедиться, что все эндпоинты работают
4. Прогнать pytest (если есть тесты)

#### Шаг 6: Commit
```bash
git add src/routers/
git add src/main.py
git add src/dependencies.py
git commit -m "refactor: decompose main.py into modular routers

- Created src/routers/ with 15 domain-specific routers
- Moved API endpoints from main.py (4000+ lines → ~300 lines)
- Extracted dependencies to src/dependencies.py
- All endpoints tested and working
- Swagger UI structure preserved"
git push
```

### Ожидаемый Результат
- main.py сократился с 4000+ строк до ~300 строк
- 15 роутеров по доменам (News, Prices, Models, etc.)
- Улучшенная читаемость и поддерживаемость
- Легче писать тесты (изолированные роутеры)

### Риски
- Циклические импорты (решение: src/dependencies.py)
- Нарушение работы эндпоинтов (решение: тщательное тестирование)
- Потеря startup/shutdown логики (решение: оставить в main.py)

### Критерии Успеха
- ✅ Все эндпоинты работают (Swagger UI)
- ✅ Тесты зелёные (если есть)
- ✅ Линтеры без критичных ошибок
- ✅ Код закоммичен и отправлен в GitHub

---

## 🎯 Задача #2: Расширение Тестов (Приоритет: ВЫСОКИЙ)

**Цель:** Coverage >80% для критичных модулей.

### Контекст
- **Текущий coverage:** <5% (только tests/test_cmd_parser.py)
- **Проблема:** Отсутствие автоматических тестов → риск регрессии
- **Решение:** pytest для всех модулей

### План Действий

#### Приоритетные Модули (в порядке важности)
1. **src/modeling.py** — ML пайплайн
2. **src/features.py** — генерация фичей
3. **src/trade.py** — paper trading (критично для безопасности капитала)
4. **src/risk.py** — фильтры сигналов
5. **src/champion.py** — champion/challenger отбор
6. **src/prices.py** — загрузка OHLCV
7. **src/news.py** — парсинг RSS
8. **src/analysis.py** — sentiment-анализ

#### Шаблон Теста

```python
# tests/test_modeling.py
import pytest
import pandas as pd
import numpy as np
from src.modeling import time_split, train_xgb_and_save, load_latest_model

def test_time_split():
    df = pd.DataFrame({"a": range(100)})
    train, test = time_split(df, test_ratio=0.2)
    assert len(train) == 80
    assert len(test) == 20

def test_time_split_small_df():
    df = pd.DataFrame({"a": [1]})
    with pytest.raises(ValueError, match="dataset too small"):
        time_split(df, test_ratio=0.2)

# Мок для XGBoost обучения
def test_train_xgb_and_save(tmp_path):
    # Подготовка данных
    df = pd.DataFrame({
        "ret_1": np.random.randn(200),
        "ret_3": np.random.randn(200),
        "future_ret": np.random.randn(200),
        "y": np.random.randint(0, 2, 200)
    })
    
    metrics, model_path = train_xgb_and_save(
        df, ["ret_1", "ret_3"], artifacts_dir=str(tmp_path)
    )
    
    assert "accuracy" in metrics
    assert "roc_auc" in metrics
    assert Path(model_path).exists()
```

#### Команды
```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=src --cov-report=html

# Только конкретный модуль
pytest tests/test_modeling.py -v

# С выводом print
pytest -s
```

#### Commit
```bash
git add tests/
git commit -m "test: add comprehensive test suite for ML and trading modules

- Added tests for modeling.py (train, load, walk-forward CV)
- Added tests for features.py (RSI, BB, news aggregation)
- Added tests for trade.py (auto-sizing, PnL, paper trading)
- Added tests for risk.py (filters, volatility classification)
- Coverage increased from 5% to 82%"
git push
```

---

## 🎯 Задача #3: Исправление Ruff Ошибок (Приоритет: СРЕДНИЙ)

**Цель:** Устранить 46 стилистических ошибок (E701, E702, E722).

### Контекст
- **Ошибки:** 56 (10 исправлено, 46 осталось)
- **Типы:** E701 (multiple statements on one line), E702 (semicolon), E722 (bare except)

### План
1. Читать вывод `ruff check src/`
2. Исправлять по одному файлу:
   - src/champion.py (2 ошибки)
   - src/main.py (30+ ошибок)
   - src/notify.py (5 ошибок)
   - src/prices.py (3 ошибки E741 — ambiguous variable `l`)
   - src/news.py (1 ошибка E711)
   - src/watchlist.py (1 ошибка F841 — unused variable)

3. Запустить `ruff check src/ --fix` для автоисправления
4. Вручную исправить оставшиеся (где --fix не помог)

### Commit
```bash
git add src/
git commit -m "style: fix ruff errors (E701, E702, E722)

- Fixed multiple statements on one line (E701, E702)
- Replaced bare except with explicit Exception (E722)
- Renamed ambiguous variable 'l' to 'low' (E741)
- Removed unused variable 'markets' (F841)
- All ruff checks passing"
git push
```

---

## 🎯 Задача #4: CI/CD Pipeline (Приоритет: СРЕДНИЙ)

**Цель:** Автоматическая проверка кода на GitHub.

### План
Создать `.github/workflows/ci.yml`:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
      
      - name: Lint with ruff
        run: ruff check src/
      
      - name: Format with black
        run: black --check src/
      
      - name: Type check with mypy
        run: mypy src/ --ignore-missing-imports
      
      - name: Run tests
        run: pytest --cov=src --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 🎯 Задача #5: Миграция на PostgreSQL (Приоритет: НИЗКИЙ, версия 0.9)

**Цель:** Замена SQLite на Postgres для продакшн-готовности.

### План
1. Docker Compose с Postgres 16
2. Обновить src/config.py (переменная DATABASE_URL)
3. Alembic миграции (уже настроено)
4. Тестирование на тестовых данных
5. Миграция данных из SQLite

---

## 📝 Обновление Этого Файла

**После завершения задачи:**
1. Отметить ✅ в секции "Завершено"
2. Обновить docs/CHANGELOG.md
3. Git commit:
   ```bash
   git add docs/NEXT_STEPS.md docs/CHANGELOG.md
   git commit -m "docs: update NEXT_STEPS after completing [task name]"
   ```

---

## 💡 Советы для Новых Чатов

1. **Всегда начинай с чтения документации:**
   - docs/PROJECT_OVERVIEW.md
   - docs/ROADMAP.md
   - docs/NEXT_STEPS.md (этот файл)
   - docs/CHANGELOG.md

2. **Создавай TODO-лист:**
   ```python
   todo_write(merge=False, todos=[
       {"id": "1", "content": "...", "status": "in_progress"},
       ...
   ])
   ```

3. **Делай частые коммиты:**
   - После каждого завершённого шага
   - С понятными сообщениями (conventional commits)

4. **Тестируй изменения:**
   - Запускай сервер локально
   - Проверяй Swagger UI
   - Запускай pytest

5. **Обновляй память:**
   ```python
   update_memory(
       action="create",
       title="Декомпозиция main.py завершена",
       knowledge_to_store="..."
   )
   ```

6. **Проси помощь у пользователя:**
   - Если нужны API ключи
   - Если нужно подтверждение деструктивных операций
   - Если непонятна бизнес-логика

---

**Последнее обновление:** 2025-10-10  
**Ответственный:** AI Assistant (Claude Sonnet 4.5)  
**Статус проекта:** Версия 0.7 → 0.8 (рефакторинг)

