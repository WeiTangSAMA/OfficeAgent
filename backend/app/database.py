from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

class Base(DeclarativeBase): pass

engine = create_engine(f"sqlite:///{settings.app_data_dir / 'app.db'}", connect_args={"check_same_thread": False}, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)

@event.listens_for(engine, "connect")
def pragmas(dbapi_connection, _):
    dbapi_connection.execute("PRAGMA foreign_keys=ON")
    dbapi_connection.execute("PRAGMA journal_mode=WAL")

def session_scope():
    db = SessionLocal()
    try: yield db
    finally: db.close()
