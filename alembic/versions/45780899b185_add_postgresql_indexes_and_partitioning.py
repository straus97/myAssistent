"""add_postgresql_indexes_and_partitioning

Revision ID: 45780899b185
Revises: 1c717f354547
Create Date: 2025-10-10 21:09:57.211469

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45780899b185'
down_revision: Union[str, Sequence[str], None] = '1c717f354547'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Добавляет PostgreSQL-специфичные оптимизации:
    - Индексы для ускорения запросов
    - Партиционирование таблицы prices по времени (по месяцам)
    - GIN индексы для полнотекстового поиска
    """
    
    # Проверяем, что используется PostgreSQL
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        print("Skipping PostgreSQL-specific migration (not PostgreSQL)")
        return
    
    # === 1. Дополнительные индексы для быстрых запросов ===
    
    # Articles: полнотекстовый поиск по title и summary
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_articles_title_trgm 
        ON articles USING gin(title gin_trgm_ops)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_articles_summary_trgm 
        ON articles USING gin(summary gin_trgm_ops)
    """)
    
    # Articles: индекс по source + published_at для фильтрации
    op.create_index(
        "ix_articles_source_published",
        "articles",
        ["source", "published_at"],
        unique=False,
        if_not_exists=True,
    )
    
    # Prices: составной индекс для временных запросов
    op.create_index(
        "ix_prices_symbol_ts",
        "prices",
        ["symbol", "ts"],
        unique=False,
        if_not_exists=True,
    )
    
    op.create_index(
        "ix_prices_exchange_symbol_ts",
        "prices",
        ["exchange", "symbol", "ts"],
        unique=False,
        if_not_exists=True,
    )
    
    # SignalEvent: индекс для быстрого поиска по времени
    op.create_index(
        "ix_signal_events_created_at",
        "signal_events",
        ["created_at"],
        unique=False,
        if_not_exists=True,
    )
    
    # SignalOutcome: индекс для статистики
    op.create_index(
        "ix_signal_outcomes_closed_at",
        "signal_outcomes",
        ["closed_at"],
        unique=False,
        if_not_exists=True,
    )
    
    # ModelRun: индекс для поиска свежих моделей
    op.create_index(
        "ix_model_runs_symbol_created",
        "model_runs",
        ["symbol", "created_at"],
        unique=False,
        if_not_exists=True,
    )
    
    # === 2. Партиционирование таблицы prices (опционально) ===
    # Примечание: партиционирование требует пересоздания таблицы
    # Раскомментируй, если нужно включить партиционирование
    
    # op.execute("""
    #     -- Переименовываем текущую таблицу
    #     ALTER TABLE prices RENAME TO prices_old;
    #     
    #     -- Создаём партиционированную таблицу
    #     CREATE TABLE prices (
    #         id SERIAL,
    #         exchange VARCHAR NOT NULL,
    #         symbol VARCHAR NOT NULL,
    #         timeframe VARCHAR NOT NULL,
    #         ts BIGINT NOT NULL,
    #         open DOUBLE PRECISION NOT NULL,
    #         high DOUBLE PRECISION NOT NULL,
    #         low DOUBLE PRECISION NOT NULL,
    #         close DOUBLE PRECISION NOT NULL,
    #         volume DOUBLE PRECISION NOT NULL,
    #         CONSTRAINT uq_price_row UNIQUE (exchange, symbol, timeframe, ts)
    #     ) PARTITION BY RANGE (ts);
    #     
    #     -- Создаём партиции на год вперёд (по месяцам)
    #     -- Пример для 2025 года (адаптируй под свои даты)
    #     CREATE TABLE prices_2025_01 PARTITION OF prices 
    #         FOR VALUES FROM (1704067200000) TO (1706745600000);
    #     CREATE TABLE prices_2025_02 PARTITION OF prices 
    #         FOR VALUES FROM (1706745600000) TO (1709251200000);
    #     -- ... и т.д. для остальных месяцев
    #     
    #     -- Копируем данные из старой таблицы
    #     INSERT INTO prices SELECT * FROM prices_old;
    #     
    #     -- Удаляем старую таблицу
    #     DROP TABLE prices_old;
    #     
    #     -- Создаём индексы на партициях
    #     CREATE INDEX ix_prices_market ON prices (exchange, symbol, timeframe);
    #     CREATE INDEX ix_prices_ts ON prices (ts);
    # """)
    
    # === 3. Оптимизации производительности ===
    
    # VACUUM ANALYZE для обновления статистики
    op.execute("VACUUM ANALYZE articles")
    op.execute("VACUUM ANALYZE prices")
    op.execute("VACUUM ANALYZE signal_events")
    op.execute("VACUUM ANALYZE model_runs")
    
    print("✅ PostgreSQL indexes and optimizations applied")


def downgrade() -> None:
    """
    Откатывает изменения (удаляет добавленные индексы)
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    
    # Удаляем созданные индексы
    op.drop_index("ix_articles_title_trgm", table_name="articles", if_exists=True)
    op.drop_index("ix_articles_summary_trgm", table_name="articles", if_exists=True)
    op.drop_index("ix_articles_source_published", table_name="articles", if_exists=True)
    op.drop_index("ix_prices_symbol_ts", table_name="prices", if_exists=True)
    op.drop_index("ix_prices_exchange_symbol_ts", table_name="prices", if_exists=True)
    op.drop_index("ix_signal_events_created_at", table_name="signal_events", if_exists=True)
    op.drop_index("ix_signal_outcomes_closed_at", table_name="signal_outcomes", if_exists=True)
    op.drop_index("ix_model_runs_symbol_created", table_name="model_runs", if_exists=True)
    
    print("✅ PostgreSQL indexes removed")
