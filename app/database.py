from typing import Generator
from sqlmodel import SQLModel, Session, create_engine
from app.config import settings

# SQLite connection with connect_args for multithreading in FastAPI
db_url = settings.DATABASE_URL or f"sqlite:///{str(settings.DATABASE_PATH).replace('\\', '/')}"
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}

engine = create_engine(
    db_url,
    echo=False,
    connect_args=connect_args
)


def create_db_and_tables() -> None:
    """Initialize SQLite database and create all tables."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    with Session(engine) as session:
        yield session
