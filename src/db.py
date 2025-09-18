# src/db.py
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, UniqueConstraint, ForeignKey, Float
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./assistant.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, index=True)
    text = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

# НОВОЕ: хранилище новостей
class Article(Base):
    __tablename__ = "articles"
    id = Column(Integer, primary_key=True, index=True)
    source = Column(String, nullable=False)        # домен источника
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    summary = Column(Text, nullable=True)          # краткое описание из RSS
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint('url', name='uq_articles_url'),  # не добавлять дубликаты по URL
    )

# НОВОЕ: Аннотации к статьям (1:1)
class ArticleAnnotation(Base):
    __tablename__ = "article_annotations"
    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"), unique=True, index=True, nullable=False)
    lang = Column(String, nullable=True)          # напр., 'en', 'ru', ...
    sentiment = Column(Float, nullable=True)      # compound, диапазон [-1..1]
    tags = Column(Text, nullable=True)            # строки через запятую, например "btc,etf,regulation"
    created_at = Column(DateTime, default=datetime.now)

class Price(Base):
    __tablename__ = "prices"
    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String, nullable=False)     # напр. 'binance'
    symbol = Column(String, nullable=False)       # напр. 'BTC/USDT'
    timeframe = Column(String, nullable=False)    # напр. '1h'
    ts = Column(Integer, nullable=False, index=True)  # миллисекунды Unix Time
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)

    __table_args__ = (
        UniqueConstraint('exchange','symbol','timeframe','ts', name='uq_price_row'),
    )


# Создаём таблицы, если их ещё нет
Base.metadata.create_all(bind=engine)
