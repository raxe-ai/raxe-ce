"""Tests for database connection management."""

from sqlalchemy import text

from raxe.infrastructure.database.connection import (
    DatabaseManager,
    get_db_manager,
    get_session,
    reset_db_manager,
)


class TestDatabaseManager:
    """Test database connection manager."""

    def test_init_with_db_path(self, tmp_path):
        """Test initialization with database path."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        assert manager.database_url == f"sqlite:///{db_path}"
        assert manager._engine is None  # Lazy initialization

    def test_init_with_database_url(self):
        """Test initialization with database URL."""
        url = "sqlite:///test.db"
        manager = DatabaseManager(database_url=url)

        assert manager.database_url == url

    def test_engine_lazy_initialization(self, tmp_path):
        """Test engine is created lazily."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        # Engine should not exist yet
        assert manager._engine is None

        # Accessing engine property creates it
        engine = manager.engine
        assert engine is not None
        assert manager._engine is engine  # Cached

        # Second access returns same instance
        engine2 = manager.engine
        assert engine2 is engine

    def test_sqlite_uses_static_pool(self, tmp_path):
        """Test SQLite databases use StaticPool."""
        from sqlalchemy.pool import StaticPool

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        engine = manager.engine
        assert isinstance(engine.pool, StaticPool)

    def test_session_factory_creation(self, tmp_path):
        """Test session factory is created."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        # Session factory should not exist yet
        assert manager._session_factory is None

        # Accessing property creates it
        factory = manager.session_factory
        assert factory is not None
        assert manager._session_factory is factory

        # Second access returns same instance
        factory2 = manager.session_factory
        assert factory2 is factory

    def test_get_session(self, tmp_path):
        """Test getting database sessions."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        # Get two sessions
        session1 = manager.get_session()
        session2 = manager.get_session()

        # Should be different session objects
        assert session1 is not session2

        # Clean up
        session1.close()
        session2.close()

    def test_session_scope_commits_on_success(self, tmp_path):
        """Test session scope commits on success."""
        from datetime import datetime, timezone

        from raxe.infrastructure.database.models import Base, TelemetryEvent

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        # Create tables
        Base.metadata.create_all(manager.engine)

        # Use session scope
        with manager.session_scope() as session:
            event = TelemetryEvent(
                event_type="test",
                event_id="test-123",
                timestamp=datetime.now(timezone.utc),
                customer_id="test-customer",
                api_key_id="test-key",
                text_hash="abc123",
                text_length=10,
                detection_count=0,
                l1_inference_ms=5.0,
                total_latency_ms=5.0,
                sdk_version="1.0.0",
                environment="testing",
            )
            session.add(event)
            # Commit happens automatically

        # Verify data was committed
        with manager.session_scope() as session:
            count = session.query(TelemetryEvent).count()
            assert count == 1

    def test_session_scope_rolls_back_on_error(self, tmp_path):
        """Test session scope rolls back on error."""
        from datetime import datetime, timezone

        from raxe.infrastructure.database.models import Base, TelemetryEvent

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        # Create tables
        Base.metadata.create_all(manager.engine)

        # Use session scope with error
        try:
            with manager.session_scope() as session:
                event = TelemetryEvent(
                    event_type="test",
                    event_id="test-456",
                    timestamp=datetime.now(timezone.utc),
                    customer_id="test-customer",
                    api_key_id="test-key",
                    text_hash="def456",
                    text_length=10,
                    detection_count=0,
                    l1_inference_ms=5.0,
                    total_latency_ms=5.0,
                    sdk_version="1.0.0",
                    environment="testing",
                )
                session.add(event)
                # Raise error before commit
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify data was NOT committed
        with manager.session_scope() as session:
            count = session.query(TelemetryEvent).count()
            assert count == 0

    def test_close_disposes_engine(self, tmp_path):
        """Test close disposes of engine."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        # Create engine
        engine = manager.engine
        assert engine is not None

        # Close manager
        manager.close()

        # Engine should be cleared
        assert manager._engine is None
        assert manager._session_factory is None

    def test_context_manager(self, tmp_path):
        """Test using manager as context manager."""
        db_path = tmp_path / "test.db"

        with DatabaseManager(db_path=db_path) as manager:
            session = manager.get_session()
            assert session is not None
            session.close()

        # Engine should be disposed after context exit
        assert manager._engine is None


class TestGlobalDatabaseManager:
    """Test global database manager functions."""

    def test_get_db_manager_singleton(self, tmp_path):
        """Test global manager is singleton."""
        # Reset first
        reset_db_manager()

        # Get manager
        manager1 = get_db_manager(db_path=tmp_path / "test.db")
        manager2 = get_db_manager()

        # Should be same instance
        assert manager1 is manager2

    def test_get_session_from_global(self, tmp_path):
        """Test getting session from global manager."""
        reset_db_manager()

        # Set up global manager with specific path
        get_db_manager(db_path=tmp_path / "test.db")

        # Get session
        session = get_session()
        assert session is not None
        session.close()

    def test_reset_db_manager(self, tmp_path):
        """Test resetting global manager."""
        reset_db_manager()

        # Create first manager
        manager1 = get_db_manager(db_path=tmp_path / "test1.db")

        # Reset
        reset_db_manager()

        # Create second manager
        manager2 = get_db_manager(db_path=tmp_path / "test2.db")

        # Should be different instances
        assert manager1 is not manager2


class TestDatabasePerformance:
    """Test database connection performance."""

    def test_connection_reuse(self, tmp_path):
        """Test connections are reused efficiently."""
        from raxe.infrastructure.database.models import Base

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        # Create tables
        Base.metadata.create_all(manager.engine)

        # Execute multiple queries
        sessions = []
        for _ in range(10):
            session = manager.get_session()
            sessions.append(session)

        # Clean up
        for session in sessions:
            session.close()

        # Engine should still be alive
        assert manager._engine is not None

    def test_concurrent_sessions(self, tmp_path):
        """Test multiple concurrent sessions work correctly."""
        import threading

        from raxe.infrastructure.database.models import Base

        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path=db_path)

        # Create tables
        Base.metadata.create_all(manager.engine)

        results = []

        def worker():
            """Worker function for threading test."""
            try:
                with manager.session_scope() as session:
                    # Execute simple query
                    result = session.execute(text("SELECT 1")).scalar()
                    results.append(result)
            except Exception as e:
                results.append(e)

        # Run multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # All should succeed
        assert len(results) == 5
        assert all(r == 1 for r in results)
