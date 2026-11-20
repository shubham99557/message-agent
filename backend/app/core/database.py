import logging
from sqlalchemy import create_engine, inspect, text, event
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL

connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforces SQLite WAL mode, foreign key enforcement, and a 5000ms busy timeout."""
    if db_url.startswith("sqlite"):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()
        except Exception as exc:
            logger.debug(f"SQLite PRAGMA setup skipped: {exc}")


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def sync_missing_columns(target_engine=None):
    """
    Ensures existing database tables have all columns defined on SQLAlchemy models.
    Prevents OperationalError when models gain columns across releases.
    """
    eng = target_engine or engine
    Base.metadata.create_all(bind=eng)
    inspector = inspect(eng)
    dialect_name = eng.dialect.name

    with eng.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            if not inspector.has_table(table_name):
                continue
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                col_type = col.type.compile(dialect=eng.dialect)
                default_clause = ""
                if col.default is not None and col.default.is_scalar:
                    val = col.default.arg
                    if isinstance(val, bool):
                        default_clause = f" DEFAULT {1 if val else 0}" if dialect_name == "sqlite" else f" DEFAULT {'TRUE' if val else 'FALSE'}"
                    elif isinstance(val, (int, float)):
                        default_clause = f" DEFAULT {val}"
                    elif isinstance(val, str):
                        safe_val = val.replace("'", "''")
                        default_clause = f" DEFAULT '{safe_val}'"
                alter_sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{col.name}" {col_type}{default_clause}'
                try:
                    conn.execute(text(alter_sql))
                    logger.info(f"Schema sync: added column {table_name}.{col.name} ({col_type})")
                except Exception as exc:
                    logger.warning(f"Schema sync skipped {table_name}.{col.name}: {exc}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
