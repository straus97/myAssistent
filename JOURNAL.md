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

