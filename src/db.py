from __future__ import annotations
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Text,
    UniqueConstraint,
    ForeignKey,
    Float,
    Index,
)
from sqlalchemy import text as _sql_text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from src.config import settings
from urllib.parse import urlparse

# уважаем .env / переменные окружения
DATABASE_URL = settings.DATABASE_URL
url = urlparse(DATABASE_URL)
is_sqlite = url.scheme.startswith("sqlite")

# Настройка connection pool в зависимости от БД
if is_sqlite:
    # SQLite: check_same_thread для многопоточности
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    # PostgreSQL: connection pooling
    pool_params = {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE,
        "pool_pre_ping": True,
        "echo_pool": settings.ENV == "dev",  # debug pooling в dev
    }
    
    # Если используем pgbouncer, отключаем pool_size (pgbouncer делает pooling сам)
    if settings.USE_PGBOUNCER:
        pool_params = {
            "poolclass": None,  # NullPool - без pooling на стороне SQLAlchemy
            "pool_pre_ping": True,
        }
    
    engine = create_engine(DATABASE_URL, **pool_params)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)


class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    summary = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    __table_args__ = (
        UniqueConstraint("url", name="uq_articles_url"),
        Index("ix_articles_published_id", "published_at", "id"),
    )


class ArticleAnnotation(Base):
    __tablename__ = "article_annotations"
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), unique=True, index=True, nullable=False)
    lang = Column(String, nullable=True)
    sentiment = Column(Float, nullable=True)
    tags = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)


class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    ts = Column(Integer, nullable=False, index=True)  # millis since epoch
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    __table_args__ = (
        UniqueConstraint("exchange", "symbol", "timeframe", "ts", name="uq_price_row"),
        Index("ix_prices_market", "exchange", "symbol", "timeframe"),
    )


class ModelRun(Base):
    __tablename__ = "model_runs"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    horizon_steps = Column(Integer, nullable=False)
    n_train = Column(Integer, nullable=False)
    n_test = Column(Integer, nullable=False)
    accuracy = Column(Float, nullable=True)
    roc_auc = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)
    total_return = Column(Float, nullable=True)
    sharpe_like = Column(Float, nullable=True)
    model_path = Column(String, nullable=False)
    features_json = Column(Text, nullable=False)
    __table_args__ = (
        Index("ix_modelrun_market", "exchange", "symbol", "timeframe"),
        Index("ix_modelrun_market_hz_id", "exchange", "symbol", "timeframe", "horizon_steps", "id"),
    )


class SignalEvent(Base):
    __tablename__ = "signal_events"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    horizon_steps = Column(Integer, nullable=False)
    bar_dt = Column(DateTime, nullable=False)
    close = Column(Float, nullable=False)
    prob_up = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    signal = Column(String, nullable=False)  # 'buy' | 'flat'
    model_path = Column(String, nullable=False)
    note = Column(Text, nullable=True)
    __table_args__ = (
        UniqueConstraint("exchange", "symbol", "timeframe", "bar_dt", name="uq_signal_bar"),
        Index("ix_signal_pairtf_dt", "exchange", "symbol", "timeframe", "bar_dt"),
        Index("ix_signal_created", "created_at"),
    )


# --- ИСХОДЫ СИГНАЛОВ (пост-оценка) ---
class SignalOutcome(Base):
    __tablename__ = "signal_outcomes"
    id = Column(Integer, primary_key=True, index=True)
    signal_event_id = Column(Integer, ForeignKey("signal_events.id"), unique=True, index=True, nullable=False)

    # копия ключевых параметров события (для удобства запросов/дашбордов)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    timeframe = Column(String, nullable=False)
    horizon_steps = Column(Integer, nullable=False)

    # когда исход «разрешился» (т.е. когда собрали h шагов вперёд)
    resolved_at = Column(DateTime, default=datetime.now)

    # метрики исхода
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=False)
    ret_h = Column(Float, nullable=False)  # доходность за horizon_steps (exit/entry - 1)
    max_drawdown = Column(Float, nullable=False)  # минимум по пути (close/entry - 1), <= 0

    __table_args__ = (
        Index("ix_outcome_pairtf", "exchange", "symbol", "timeframe"),
        Index("ix_outcome_resolved", "resolved_at"),
    )


# --- PAPER TRADING ---
class Portfolio(Base):
    __tablename__ = "portfolio"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    cash = Column(Float, nullable=False, default=0.0)


class PaperPosition(Base):
    __tablename__ = "paper_positions"
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    qty = Column(Float, nullable=False, default=0.0)
    avg_price = Column(Float, nullable=False, default=0.0)
    realized_pnl = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime, default=datetime.now)
    __table_args__ = (
        UniqueConstraint("exchange", "symbol", name="uq_paperpos_pair"),
        Index("ix_paperpos_pair", "exchange", "symbol"),
    )


class PaperOrder(Base):
    __tablename__ = "paper_orders"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    side = Column(String, nullable=False)  # 'buy' | 'sell'
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float, nullable=False, default=0.0)
    status = Column(String, nullable=False, default="filled")
    signal_event_id = Column(Integer, ForeignKey("signal_events.id"), nullable=True)
    note = Column(Text, nullable=True)
    __table_args__ = (Index("ix_paperorders_pair", "exchange", "symbol"),)


class PaperTrade(Base):
    __tablename__ = "paper_trades"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    order_id = Column(Integer, ForeignKey("paper_orders.id"), nullable=False)
    exchange = Column(String, nullable=False)
    symbol = Column(String, nullable=False)
    qty = Column(Float, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float, nullable=False, default=0.0)
    __table_args__ = (Index("ix_papertrades_pair", "exchange", "symbol"),)


class EquityPoint(Base):
    __tablename__ = "equity_points"
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.now)
    ts = Column(DateTime, nullable=False, index=True)
    equity = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    positions_value = Column(Float, nullable=False)


# Создаём таблицы, если их ещё нет
Base.metadata.create_all(bind=engine)


def ensure_runtime_indexes(engine):
    """Создаёт недостающие индексы (idempotent). Безопасно для SQLite/Postgres."""
    stmts = [
        # статьи
        "CREATE INDEX IF NOT EXISTS ix_articles_published_id ON articles (published_at, id)",
        # модельные запуски
        "CREATE INDEX IF NOT EXISTS ix_modelrun_market_hz_id ON model_runs (exchange, symbol, timeframe, horizon_steps, id)",
    ]
    with engine.begin() as con:
        for s in stmts:
            con.execute(_sql_text(s))
