from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


database_url = make_url(settings.database_url)

engine_options: dict = {
    "pool_pre_ping": True,
}

if database_url.get_backend_name() == "sqlite":
    engine_options["connect_args"] = {"check_same_thread": False}

    if database_url.database not in (None, "", ":memory:"):
        from pathlib import Path

        Path(database_url.database).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

engine = create_engine(
    settings.database_url,
    **engine_options,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and always close it."""

    with SessionLocal() as session:
        yield session