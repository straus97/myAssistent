## Шаг 2 — Проверка и настройка Git
- Установлен Git for Windows.
- Проверена версия: git --version → 2.xx.x
- Настроены user.name, user.email, init.defaultBranch=main, credential.helper=manager.
- Создан проект C:\AI\my-assistant.
- Добавлены файлы: .gitignore, README.md, JOURNAL.md, src/hello_ai.py.
- Сделан первый коммит.

## Шаг 3.1 — История коммитов
- Научился смотреть историю через `git log`.
- Нашёл список коммитов в PyCharm (Git → Show History).
- Посмотрел историю на GitHub (вкладка Commits).

## Шаг 4 — Первый API на FastAPI
- Установлены пакеты: fastapi, uvicorn.
- Создан файл src/main.py с эндпоинтами /hello и /time.
- Запущен сервер через uvicorn, проверены ответы в браузере.
- Открыта документация API по адресу /docs.

## Шаг 6 — Новости (RSS → SQLite → API)
- Установлены пакеты: feedparser, python-dateutil.
- В БД добавлена таблица `articles` с уникальным URL.
- Создан модуль `src/news.py` (функция fetch_and_store).
- В `src/main.py` добавлены маршруты:
  - POST /news/fetch — загрузка новостей из RSS.
  - GET /news/latest — последние новости.
  - GET /news/search?q= — поиск по заголовкам/аннотациям.
- Проверено через /docs: новости подтягиваются и отображаются.

## Шаг 7 — Аналитика новостей (язык, тональность, теги)
- Установлены: vaderSentiment, langdetect.
- Добавлена таблица article_annotations (1:1 к articles).
- Создан модуль src/analysis.py: detect_lang, sentiment_score, extract_tags, analyze_new_articles.
- В API добавлены маршруты:
  - POST /news/analyze — анализ N последних неаннотированных статей.
  - GET /news/annotated — просмотр последних аннотированных.
  - GET /news/by_tag?tag=... — выборка статей по тегу.
- Проверено через /docs: анализ выполняется, теги и тональность видны.

