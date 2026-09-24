from app.db import create_database_engine


def test_postgres_engine_uses_pool_settings() -> None:
    engine = create_database_engine("postgresql+psycopg://user:password@localhost:5432/test")

    try:
        assert engine.pool.size() == 10
        assert engine.pool._max_overflow == 20
        assert engine.pool._timeout == 30
        assert engine.pool._pre_ping is True
        assert engine.pool._recycle == 300
        assert engine.pool._use_lifo is True
    finally:
        engine.dispose()


def test_sqlite_engine_keeps_thread_check() -> None:
    engine = create_database_engine("sqlite:///:memory:")

    try:
        assert engine.url.get_backend_name() == "sqlite"
    finally:
        engine.dispose()
