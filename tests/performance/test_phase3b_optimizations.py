"""
Performance validation tests for Phase 3B optimizations.

These tests verify that database indexes, optimized queries, and pagination
meet performance requirements:
- Query time <100ms for analytics queries
- Memory usage <10MB for large datasets
- No N+1 query patterns
"""

import tempfile
import time
import tracemalloc
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from raxe.infrastructure.analytics.aggregator import DataAggregator
from raxe.infrastructure.analytics.engine import AnalyticsEngine
from raxe.infrastructure.database.models import Base, TelemetryEvent


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        yield db_path


@pytest.fixture
def engine_with_data(temp_db):
    """Create database with test data."""
    # Create database
    engine = create_engine(f"sqlite:///{temp_db}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    # Add test data
    session = SessionLocal()
    try:
        # Create 10,000 events for testing (simulating real load)
        test_customer_id = "test_user_123"
        base_time = datetime.now(timezone.utc) - timedelta(days=30)

        events = []
        for i in range(10000):
            event = TelemetryEvent(
                event_id=f"evt_{i}",
                customer_id=test_customer_id,
                api_key_id="api_key_1",
                text_hash=f"hash_{i}",
                text_length=100 + i % 100,
                detection_count=i % 5,  # 20% have detections
                highest_severity="high" if i % 5 > 0 else None,
                l1_inference_ms=2.0 + (i % 10) * 0.1,
                l2_inference_ms=5.0 if i % 10 == 0 else None,
                total_latency_ms=7.0 + (i % 20) * 0.5,
                policy_action="allow",
                sdk_version="1.0.0",
                environment="production",
                timestamp=base_time + timedelta(hours=i),
            )
            events.append(event)

        session.bulk_save_objects(events)
        session.commit()

        yield engine, test_customer_id

    finally:
        session.close()
        engine.dispose()


class TestDatabaseIndexes:
    """Test that database indexes are created correctly."""

    def test_indexes_exist(self, engine_with_data):
        """Verify all required indexes exist."""
        engine, _ = engine_with_data
        inspector = inspect(engine)
        indexes = inspector.get_indexes('telemetry_events')

        # Convert to set of index names
        index_names = {idx['name'] for idx in indexes}

        # Required indexes from Phase 3B
        required_indexes = {
            'idx_priority_processed',
            'idx_timestamp_processed',
            'idx_customer_timestamp',
            'ix_telemetry_customer_type',
            'ix_telemetry_type_created',
            'ix_telemetry_severity_timestamp',
            'ix_telemetry_detection_customer',
        }

        # Verify all required indexes exist
        for required in required_indexes:
            assert required in index_names, f"Missing index: {required}"

    def test_index_columns(self, engine_with_data):
        """Verify indexes are on correct columns."""
        engine, _ = engine_with_data
        inspector = inspect(engine)
        indexes = inspector.get_indexes('telemetry_events')

        # Find customer_timestamp index
        customer_timestamp_idx = next(
            (idx for idx in indexes if idx['name'] == 'idx_customer_timestamp'),
            None
        )
        assert customer_timestamp_idx is not None
        assert 'customer_id' in customer_timestamp_idx['column_names']
        assert 'timestamp' in customer_timestamp_idx['column_names']


class TestQueryPerformance:
    """Test that optimized queries meet performance requirements."""

    def test_get_user_stats_performance(self, engine_with_data, temp_db):
        """Test get_user_stats query time <100ms."""
        _engine_db, customer_id = engine_with_data

        # Create analytics engine
        analytics_engine = AnalyticsEngine(db_path=temp_db)

        # Measure query time
        start = time.perf_counter()
        stats = analytics_engine.get_user_stats(customer_id)
        elapsed = time.perf_counter() - start

        # Verify results
        assert stats.total_scans == 10000
        assert stats.installation_id == customer_id

        # Performance requirement: <100ms
        assert elapsed < 0.1, f"Query took {elapsed*1000:.2f}ms (requirement: <100ms)"

        analytics_engine.close()

    def test_get_user_stats_uses_aggregation(self, engine_with_data, temp_db):
        """Verify get_user_stats uses SQL aggregation, not loading all rows."""
        _engine_db, customer_id = engine_with_data

        analytics_engine = AnalyticsEngine(db_path=temp_db)

        # Track memory usage
        tracemalloc.start()
        start_memory = tracemalloc.get_traced_memory()[0]

        analytics_engine.get_user_stats(customer_id)

        _current_memory, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        memory_used_mb = (peak_memory - start_memory) / 1024 / 1024

        # Performance requirement: <10MB memory usage
        # If we loaded all 10K events, we'd use much more memory
        assert memory_used_mb < 10, f"Used {memory_used_mb:.2f}MB (requirement: <10MB)"

        analytics_engine.close()

    def test_daily_rollup_performance(self, engine_with_data, temp_db):
        """Test daily rollup query performance."""
        _engine_db, _ = engine_with_data

        aggregator = DataAggregator(db_path=temp_db)

        # Query 30 days of data
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        start = time.perf_counter()
        rollups = aggregator.get_daily_rollup(start_date, end_date)
        elapsed = time.perf_counter() - start

        # Verify results
        assert len(rollups) == 31  # 30 days + 1

        # Performance requirement: <100ms
        assert elapsed < 0.1, f"Query took {elapsed*1000:.2f}ms (requirement: <100ms)"

        aggregator.close()

    def test_detection_breakdown_single_query(self, engine_with_data, temp_db):
        """Verify detection breakdown uses single GROUP BY, not N queries."""
        _engine_db, _ = engine_with_data

        aggregator = DataAggregator(db_path=temp_db)

        # This should use ONE GROUP BY query, not 5 separate COUNT queries
        start = time.perf_counter()
        breakdowns = aggregator.get_detection_breakdown(days=30)
        elapsed = time.perf_counter() - start

        # Verify results
        assert len(breakdowns) > 0

        # Performance requirement: <50ms (single query should be fast)
        assert elapsed < 0.05, f"Query took {elapsed*1000:.2f}ms (requirement: <50ms)"

        aggregator.close()


class TestPagination:
    """Test pagination support."""

    def test_get_user_events_paginated(self, engine_with_data, temp_db):
        """Test paginated event retrieval."""
        _engine_db, customer_id = engine_with_data

        analytics_engine = AnalyticsEngine(db_path=temp_db)

        # Get first page
        page_1 = analytics_engine.get_user_events_paginated(
            customer_id,
            limit=100,
            offset=0
        )
        assert len(page_1) == 100

        # Get second page
        page_2 = analytics_engine.get_user_events_paginated(
            customer_id,
            limit=100,
            offset=100
        )
        assert len(page_2) == 100

        # Pages should be different
        assert page_1[0].event_id != page_2[0].event_id

        analytics_engine.close()

    def test_pagination_memory_usage(self, engine_with_data, temp_db):
        """Verify pagination limits memory usage."""
        _engine_db, customer_id = engine_with_data

        analytics_engine = AnalyticsEngine(db_path=temp_db)

        # Track memory for paginated query
        tracemalloc.start()
        start_memory = tracemalloc.get_traced_memory()[0]

        # Get only 100 events instead of all 10K
        analytics_engine.get_user_events_paginated(
            customer_id,
            limit=100,
            offset=0
        )

        _current_memory, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        memory_used_mb = (peak_memory - start_memory) / 1024 / 1024

        # Should use minimal memory (<<10MB)
        assert memory_used_mb < 1, f"Used {memory_used_mb:.2f}MB (should be <1MB for 100 events)"

        analytics_engine.close()


class TestBatchOperations:
    """Test batch query optimizations."""

    def test_scan_dates_batch_loading(self, engine_with_data, temp_db):
        """Test get_scan_dates_for_user performance."""
        _engine_db, customer_id = engine_with_data

        analytics_engine = AnalyticsEngine(db_path=temp_db)

        # This should use DISTINCT query, not load all events
        start = time.perf_counter()
        scan_dates = analytics_engine.get_scan_dates_for_user(customer_id)
        elapsed = time.perf_counter() - start

        # Verify results (should have unique dates from 10K events)
        assert len(scan_dates) > 0

        # Performance requirement: <50ms
        assert elapsed < 0.05, f"Query took {elapsed*1000:.2f}ms (requirement: <50ms)"

        analytics_engine.close()

    def test_retention_batch_calculation(self, engine_with_data, temp_db):
        """Test batch retention calculation avoids N+1."""
        _engine_db, customer_id = engine_with_data

        analytics_engine = AnalyticsEngine(db_path=temp_db)

        # Calculate retention for multiple users in one query
        user_ids = [customer_id, "user_2", "user_3"]
        cohort_date = date.today() - timedelta(days=7)

        start = time.perf_counter()
        results = analytics_engine.calculate_retention_batch(
            user_ids,
            cohort_date
        )
        elapsed = time.perf_counter() - start

        # Verify results
        assert customer_id in results

        # Performance requirement: <100ms for 3 users
        # (avoids 3 separate queries)
        assert elapsed < 0.1, f"Query took {elapsed*1000:.2f}ms (requirement: <100ms)"

        analytics_engine.close()


class TestPerformanceRegression:
    """Integration tests for overall performance."""

    def test_analytics_dashboard_load_time(self, engine_with_data, temp_db):
        """Simulate analytics dashboard loading all metrics."""
        _engine_db, customer_id = engine_with_data

        analytics_engine = AnalyticsEngine(db_path=temp_db)
        aggregator = DataAggregator(db_path=temp_db)

        # Simulate dashboard loading multiple metrics
        start = time.perf_counter()

        # Load all dashboard metrics
        analytics_engine.get_user_stats(customer_id)
        analytics_engine.get_global_stats()
        aggregator.get_daily_rollup(
            date.today() - timedelta(days=7),
            date.today()
        )
        aggregator.get_detection_breakdown(days=7)

        elapsed = time.perf_counter() - start

        # Performance requirement: Full dashboard load <500ms
        assert elapsed < 0.5, f"Dashboard load took {elapsed*1000:.2f}ms (requirement: <500ms)"

        analytics_engine.close()
        aggregator.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
