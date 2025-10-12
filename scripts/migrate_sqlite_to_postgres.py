#!/usr/bin/env python3
"""
Скрипт миграции данных из SQLite в PostgreSQL

Использование:
    python scripts/migrate_sqlite_to_postgres.py

Требования:
    - SQLite база: assistant.db
    - PostgreSQL: запущен через docker-compose up -d postgres
    - .env: DATABASE_URL=postgresql://myassistent:password@localhost:5432/myassistent
"""

import os
import sys
from pathlib import Path

# Добавляем src в путь
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm
import logging

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Пути к базам
SQLITE_DB = PROJECT_ROOT / "assistant.db"
POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://myassistent:change_me_in_production@localhost:5432/myassistent"
)


def migrate_table(sqlite_conn, postgres_conn, table_name: str, batch_size: int = 1000):
    """
    Мигрирует данные из SQLite таблицы в PostgreSQL
    
    Args:
        sqlite_conn: SQLAlchemy connection к SQLite
        postgres_conn: SQLAlchemy connection к PostgreSQL
        table_name: имя таблицы
        batch_size: размер батча для вставки
    """
    logger.info(f"📦 Миграция таблицы: {table_name}")
    
    # Получаем количество строк
    count_query = text(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = sqlite_conn.execute(count_query).scalar()
    
    if total_rows == 0:
        logger.info(f"  ⚠️  Таблица {table_name} пуста, пропускаем")
        return
    
    logger.info(f"  📊 Всего строк: {total_rows:,}")
    
    # Получаем структуру таблицы
    columns_query = text(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in sqlite_conn.execute(columns_query).fetchall()]
    columns_str = ", ".join(columns)
    
    # Читаем данные батчами
    offset = 0
    migrated = 0
    
    with tqdm(total=total_rows, desc=f"  {table_name}", unit="rows") as pbar:
        while offset < total_rows:
            # Читаем батч из SQLite
            select_query = text(f"SELECT {columns_str} FROM {table_name} LIMIT :limit OFFSET :offset")
            rows = sqlite_conn.execute(
                select_query,
                {"limit": batch_size, "offset": offset}
            ).fetchall()
            
            if not rows:
                break
            
            # Вставляем в PostgreSQL (игнорируем дубликаты)
            placeholders = ", ".join([f":{col}" for col in columns])
            insert_query = text(f"""
                INSERT INTO {table_name} ({columns_str})
                VALUES ({placeholders})
                ON CONFLICT DO NOTHING
            """)
            
            for row in rows:
                try:
                    row_dict = dict(zip(columns, row))
                    postgres_conn.execute(insert_query, row_dict)
                    migrated += 1
                except Exception as e:
                    logger.warning(f"  ⚠️  Ошибка вставки строки: {e}")
                    continue
            
            postgres_conn.commit()
            offset += batch_size
            pbar.update(len(rows))
    
    logger.info(f"  [OK] Мигрировано: {migrated:,} строк")


def migrate_all():
    """Главная функция миграции"""
    
    # Проверка наличия SQLite базы
    if not SQLITE_DB.exists():
        logger.error(f"❌ SQLite база не найдена: {SQLITE_DB}")
        sys.exit(1)
    
    logger.info("🚀 Начинается миграция SQLite → PostgreSQL")
    logger.info(f"📂 SQLite: {SQLITE_DB}")
    logger.info(f"🐘 PostgreSQL: {POSTGRES_URL}")
    
    # Создаём подключения
    sqlite_engine = create_engine(f"sqlite:///{SQLITE_DB}")
    postgres_engine = create_engine(POSTGRES_URL)
    
    sqlite_conn = sqlite_engine.connect()
    postgres_conn = postgres_engine.connect()
    
    try:
        # Применяем Alembic миграции к PostgreSQL
        logger.info("📝 Применяем Alembic миграции к PostgreSQL...")
        os.system("alembic upgrade head")
        
        # Список таблиц для миграции (в правильном порядке из-за FK)
        tables = [
            "messages",
            "articles",
            "article_annotations",
            "prices",
            "model_runs",
            "signal_events",
            "signal_outcomes",
            "portfolio",
            "paper_positions",
            "paper_orders",
            "paper_trades",
            "equity_points",
        ]
        
        # Мигрируем каждую таблицу
        for table in tables:
            try:
                migrate_table(sqlite_conn, postgres_conn, table)
            except Exception as e:
                logger.error(f"❌ Ошибка миграции таблицы {table}: {e}")
                logger.info("⏩ Продолжаем со следующей таблицей...")
        
        # Обновляем sequences для автоинкремента (PostgreSQL)
        logger.info("🔄 Обновление sequences...")
        for table in tables:
            try:
                postgres_conn.execute(text(f"""
                    SELECT setval(
                        pg_get_serial_sequence('{table}', 'id'),
                        COALESCE((SELECT MAX(id) FROM {table}), 1)
                    )
                """))
                postgres_conn.commit()
            except Exception as e:
                logger.warning(f"  ⚠️  Таблица {table} без автоинкремента: {e}")
        
        logger.info("🎉 Миграция завершена успешно!")
        
        # Статистика
        logger.info("\n📊 Статистика миграции:")
        for table in tables:
            try:
                count = postgres_conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                logger.info(f"  {table:25} {count:>10,} строк")
            except Exception:
                pass
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
    finally:
        sqlite_conn.close()
        postgres_conn.close()
    
    logger.info("\n[SUCCESS] Готово! Теперь обновите .env:")
    logger.info(f"   DATABASE_URL={POSTGRES_URL}")


if __name__ == "__main__":
    # Подтверждение от пользователя
    print("[WARNING] ВНИМАНИЕ: Эта операция мигрирует данные из SQLite в PostgreSQL")
    print(f"   SQLite: {SQLITE_DB}")
    print(f"   PostgreSQL: {POSTGRES_URL}")
    print()
    
    response = input("Продолжить? (yes/no): ").strip().lower()
    if response != "yes":
        print("[CANCELLED] Миграция отменена")
        sys.exit(0)
    
    migrate_all()

