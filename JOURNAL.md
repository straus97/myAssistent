## Шаг 1 — Среда и каркас проекта
- Windows 10/11, Python 3.11 (x64).
- Создан проект: C:\AI\myAssistent.
- Виртуальное окружение: python -m venv .venv → активировано.
- Установлен базовый набор пакетов: fastapi, uvicorn[standard], pydantic, sqlalchemy, pandas, numpy.

## Шаг 2 — Git
- Установлен Git for Windows.
- Настроены: user.name, user.email, init.defaultBranch=main, credential.helper=manager.
- Добавлены файлы: .gitignore, README.md, JOURNAL.md.
- Сделан первый коммит.

## Шаг 3 — История коммитов
- Просмотр истории: git log, PyCharm → Git → Show History, GitHub → Commits.

## Шаг 4 — Первый API на FastAPI
- Создан src/main.py с базовыми эндпоинтами: /hello, /time.
- Сервер: uvicorn src.main:app --reload → проверка ответов.
- Документация: http://127.0.0.1:8000/docs.

## Шаг 5 — Offline-доки и отладка роутов
- Добавлены флаги окружения: OFFLINE_DOCS=1, ENABLE_DOCS=1.
- Подключён fastapi_offline (если нет — прозрачный откат к обычным докам).
- В main.py добавлены:
- - /ping — быстрый healthcheck.
- - /_debug/info — список роутов, cwd, первые элементы sys.path.
- Логи при старте печатают, откуда импортированы src/risk.py и src/notify.py.

## Шаг 6 — Новости (RSS → SQLite → API)
- Пакеты: feedparser, python-dateutil.
- - Таблица articles (уникальность по URL).
- src/news.py: fetch_and_store.
- Роуты:
- - POST /news/fetch — загрузка RSS.
- - GET /news/latest — последние записи.
- - GET /news/search?q= — поиск по title/summary.

## Шаг 7 — Аналитика новостей (язык/тональность/теги)
- Пакеты: vaderSentiment, langdetect.
- Таблица article_annotations (1:1).
- src/analysis.py: detect_lang, sentiment_score, extract_tags, analyze_new_articles.
- Роуты:
- - POST /news/analyze
- - GET /news/annotated
- - GET /news/by_tag?tag=...

## Шаг 8 — Цены → Фичи → Первая модель
- Пакеты: ccxt, scikit-learn, joblib.
- Таблица prices (+ индексы).
- Модули:
- - src/prices.py — OHLCV → SQLite.
- - src/features.py — сборка датасета (ретёрны, волатильность, агрегаты новостей).
- - src/modeling.py — обучение + простой бэктест.
- Роуты:
- - POST /prices/fetch, GET /prices/latest
- - POST /dataset/build
- - POST /model/train

## Шаг 9 — Планировщик (APScheduler)
- Пакет: apscheduler.
- Фоновые задачи: сбор новостей/аналитики/цен, ночная тренировка, ежедневный отчёт, генерация сигналов.
- Роут: GET /automation/status (проверка заданий).
- Важное: один воркер Uvicorn (без --workers), чтобы планировщик не плодился.

## Шаг 10 — Диагностика и кеш доков
- Если в /docs не видны новые роуты — «жёсткое обновление» (Ctrl+F5).
- Проверка через /_debug/info — список текущих маршрутов.
- Логи старта содержат пути модулей [boot] risk module: и [boot] notify module:.

## Шаг 11 — Дневной HTML-отчёт
- src/reports.py — агрегации новостей и цен, HTML-сводка.
- Роуты:
- - POST /report/daily — сгенерировать сейчас,
- - GET /report/latest — отдать последний.
- Планировщик: сборка отчёта ежедневно в 00:50 UTC.
- Артефакты: artifacts/reports/.

## Шаг 12 — Локальный дашборд (опция)
- Пакеты: streamlit, requests.
- streamlit_app.py — кнопки управления, графики, таблички.
- Запуск: streamlit run streamlit_app.py.

## Шаг 13 — XGBoost и журнал обучений
- Пакет: xgboost.
- Таблица model_runs (версии/метрики/путь к модели).
- src/modeling.py: XGBClassifier, автопорог по тесту, сохранение .pkl с таймстампом.
- Роут: GET /model/runs — недавние обучения.

## Шаг 14 — Сигналы и лог событий
- Таблица signal_events (уникальность: exchange+symbol+timeframe+bar_dt).
- load_latest_model() — получить актуальную модель/порог.
- Роуты:
- - POST /signal/latest — прогноз на последнем баре, запись в БД,
- - GET /signals/recent — последние события.
- Планировщик make_signals каждые 15 минут по PAIRS.

## Шаг 15 — Риск-политика (фильтры)
- src/risk.py + artifacts/config/risk_policy.json.
- Роуты: GET/POST /risk/policy.
- Применяем фильтры к сигналам (vol_norm, ret_std_24, cooldown и т. п.).
- В SignalEvent.note сохраняем причины/метрики.

## Шаг 16 — Уведомления (Telegram)
- Пакет: requests.
- src/notify.py: конфиг чтение/запись, отправка, форматирование сообщений, дефолтные правила.
- Роуты:
- - GET /notify/config — токен замаскирован,
- - POST /notify/config — enabled/token/chat_id/rules,
- - POST /notify/test.
- BUY всегда (если включено), FLAT — по правилу flat_min_prob, с учётом источника (source).

## Шаг 17 — Дедупликация и правила уведомлений
- Введён ключ rules.source (both/endpoint/scheduler) → контроль источника уведомлений.
- Унифицирован вызов maybe_send_signal_notification(...) из эндпоинта и планировщика.
- Профили конфигурации сохраняются в artifacts/config/notify_config.json.

## Шаг 18 — Бумажная торговля (карманный брокер)
- src/trade.py: лёгкое состояние в artifacts/paper_state.json.
- Кэш, позиции, журнал ордеров.
- Покупка «на 10% кэша», средняя цена, простое PnL (без комиссий).
- Роуты (финальная, удобная схема):
- - GET /trade/positions — позиции с mark-to-market по последней цене,
- - GET /trade/equity — кэш + позиции + equity (m2m),
- - POST /trade/paper/close — закрыть пару по последней цене.
- Автоторговля: в планировщике при final_signal == "buy" вызываем paper_open_buy_auto(...).

## Шаг 19 — Ручные запуска и «разовый сигнал»
- Роут: POST /automation/run — теперь универсальный:
- Режим job: {"job": "make_signals"} / fetch_news / analyze_news / fetch_prices / train_models / build_report.
- Режим action: {"action":"signal_once","exchange":"bybit","symbol":"BTC/USDT","timeframe":"15m","horizon_steps":12} — считает сигнал сейчас, применит фильтры, отправит уведомление и выполнит BUY в paper-брокере при допуске.

## Шаг 20 — Именование роутов и теги в Swagger
- Все эндпоинты промаркированы тегами: News, Prices, Dataset, Model, Signal, Risk, Notify, Trade, Report, Automation, Memory.
- Убраны неоднозначные /trade/portfolio и /trade/paper/order — вместо них ровно то, что ожидаем:
- - GET /trade/positions
- - GET /trade/equity
- - POST /trade/paper/close

## Шаг 21 — Динамический Watchlist и автопоиск ликвидных пар
- Создан `src/watchlist.py`: хранение в artifacts/config/watchlist.json, CRUD эндпоинты.
- Добавлен авто-дискавер через ccxt: отбор SPOT пар по USDT-котировке и объёму, исключение левередж-токенов.
- Эндпоинты:
  - GET /watchlist — текущее содержимое.
  - POST /watchlist, /watchlist/add, /watchlist/remove — управление списком.
  - POST /watchlist/discover — автодобавление топ-ликвидных пар.
- Планировщик:
  - job_discover_watchlist ежедневно — обновляет watchlist.
  - job_fetch_prices / job_make_signals — берут пары из watchlist (pairs_for_jobs).
- One-off:
  - POST /automation/run {"action":"scan_watchlist"} — скан всех пар без автотрейда (с TG-уведомлениями).

## Шаг 22 — Реестр активных моделей по парам (per-pair)
- Новый модуль `src/model_registry.py`:
  - active_models.json — ручной выбор модели для (exchange, symbol, timeframe, horizon_steps).
  - Автовыбор: приоритет ручной → последний успешный ModelRun для пары → общий fallback.
  - Функция `load_model_for(db, ex, sym, tf, hz)` внедрена в /signal/latest, job_make_signals и action=signal_once.
- Новые эндпоинты:
  - GET /model/active?exchange=&symbol=&timeframe=&horizon_steps= — показывает активную (manual) и последнюю из прогонов.
  - POST /model/active — закрепить конкретный model_path для пары/ТФ/горизонта.
  - GET /model/runs — добавлены фильтры по exchange/symbol/timeframe/horizon_steps.
- Результат: сигналы и уведомления идут по корректной модели для каждой пары, без «перепрыгивания» на чужие прогоны.

## Шаг 23 — SLA для моделей и автотренировка «только где нужно»
- Новый модуль `src/model_policy.py` и конфиг `artifacts/config/model_policy.json`:
  - max_age_days (по умолчанию 7 дней),
  - retrain_if_auc_below (по умолчанию 0.55),
  - min_train_rows (по умолчанию 200).
- В `main.py` добавлены:
  - Хелперы _last_run_for/_age_days/_model_needs_retrain.
  - GET /model/policy, POST /model/policy — чтение/изменение SLA.
  - GET /model/health — статус свежести моделей по watchlist.
  - POST /model/train_missing — тренируем только там, где нужно (нет модели, устарела, низкий AUC).
  - Ветвь /automation/run {"action":"train_missing"}.
- Обновлён job_train_models: пары из watchlist, соблюдение SLA, TG-уведомление по результату.
- Результат: экономим время, не «перетираем» свежие модели, поддерживаем актуальность автоматически.
