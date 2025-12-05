"""Database connection management with proper pooling.

This module provides connection pooling for SQLite databases,
ensuring thread-safety and efficient resource usage.
"""
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


class DatabaseManager:
    """Manages database connections with proper pooling.

    For SQLite databases, uses StaticPool for thread-safety.
    For other databases, would use QueuePool.
    """

    def __init__(
        self,
        database_url: str | None = None,
        db_path: Path | None = None,
        echo: bool = False,
    ):
        """Initialize database manager.

        Args:
            database_url: SQLAlchemy database URL (overrides db_path)
            db_path: Path to SQLite database file
            echo: Whether to echo SQL statements (for debugging)
        """
        if database_url is None:
            if db_path is None:
                db_path = Path.home() / ".raxe" / "raxe.db"
            database_url = f"sqlite:///{db_path}"

        self.database_url = database_url
        self._engine: Engine | None = None
        self._session_factory: sessionmaker | None = None
        self.echo = echo

    @property
    def engine(self) -> Engine:
        """Get or create database engine.

        Returns:
            SQLAlchemy engine instance
        """
        if self._engine is None:
            # SQLite-specific configuration
            if self.database_url.startswith("sqlite"):
                # Use StaticPool for SQLite to maintain a single connection
                # This prevents threading issues while still being efficient
                self._engine = create_engine(
                    self.database_url,
                    poolclass=StaticPool,
                    connect_args={"check_same_thread": False},
                    echo=self.echo,
                )
            else:
                # For other databases (PostgreSQL, MySQL), use default QueuePool
                from sqlalchemy.pool import QueuePool

                self._engine = create_engine(
                    self.database_url,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=30,
                    pool_recycle=3600,
                    pool_pre_ping=True,
                    echo=self.echo,
                )

        return self._engine

    @property
    def session_factory(self) -> sessionmaker:
        """Get or create session factory.

        Returns:
            SQLAlchemy sessionmaker instance
        """
        if self._session_factory is None:
            self._session_factory = sessionmaker(
                bind=self.engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )

        return self._session_factory

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy Session instance

        Example:
            >>> manager = DatabaseManager()
            >>> session = manager.get_session()
            >>> try:
            ...     # Use session
            ...     session.commit()
            ... finally:
            ...     session.close()
        """
        return self.session_factory()

    @contextmanager
    def session_scope(self):
        """Provide a transactional scope for database operations.

        Yields:
            Session: Database session

        Example:
            >>> manager = DatabaseManager()
            >>> with manager.session_scope() as session:
            ...     # Use session, auto-commits on success
            ...     session.add(obj)
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def close(self) -> None:
        """Close all database connections and dispose of the engine."""
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global instance for convenience
_db_manager: DatabaseManager | None = None


def get_db_manager(db_path: Path | None = None) -> DatabaseManager:
    """Get or create the global database manager.

    Args:
        db_path: Optional database path (only used on first call)

    Returns:
        DatabaseManager instance

    Example:
        >>> manager = get_db_manager()
        >>> session = manager.get_session()
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(db_path=db_path)
    return _db_manager


def get_session() -> Session:
    """Get a database session from the global manager.

    Returns:
        SQLAlchemy Session instance

    Example:
        >>> session = get_session()
        >>> try:
        ...     # Use session
        ...     session.commit()
        ... finally:
        ...     session.close()
    """
    return get_db_manager().get_session()


def reset_db_manager() -> None:
    """Reset the global database manager.

    Useful for testing or when switching databases.
    """
    global _db_manager
    if _db_manager is not None:
        _db_manager.close()
        _db_manager = None
