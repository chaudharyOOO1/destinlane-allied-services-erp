import os
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool

from app.core.config import settings

engine_kwargs = {
    "pool_pre_ping": True,
}

# Vercel functions are short-lived. A persistent SQLAlchemy pool per function
# instance can exhaust a managed Postgres/Supabase connection limit quickly.
# Use one connection per request on Vercel and keep a small pool locally.
if os.getenv("VERCEL"):
    engine_kwargs["poolclass"] = NullPool
else:
    engine_kwargs.update({"pool_size": 5, "max_overflow": 5})

engine = create_engine(settings.sync_database_url, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
