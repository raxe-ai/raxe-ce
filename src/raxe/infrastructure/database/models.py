"""SQLAlchemy models generated from JSON schemas.

This module provides SQLAlchemy ORM models that correspond to our JSON schemas,
enabling database persistence with schema validation.
"""

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class TelemetryEvent(Base):
    """Telemetry event model for scan_performed events.

    Corresponds to telemetry/scan_performed.json schema.
    """

    __tablename__ = "telemetry_events"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Event metadata
    event_type = Column(String(50), nullable=False, default="scan_performed")
    event_id = Column(String(36), nullable=False, unique=True, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Customer info (hashed)
    customer_id = Column(String(64), nullable=False, index=True)
    api_key_id = Column(String(64), nullable=False, index=True)
    project_id = Column(String(36), nullable=True)

    # Detection data (privacy-preserving)
    text_hash = Column(String(64), nullable=False)  # SHA256 hash only
    text_length = Column(Integer, nullable=False)
    detection_count = Column(Integer, nullable=False, default=0)
    highest_severity = Column(
        Enum("critical", "high", "medium", "low", "info", name="severity_enum"),
        nullable=True
    )

    # Performance metrics
    l1_inference_ms = Column(Float, nullable=False)
    l2_inference_ms = Column(Float, nullable=True)  # Optional if L2 not used
    total_latency_ms = Column(Float, nullable=False)
    queue_depth = Column(Integer, nullable=True)

    # Policy outcome
    policy_action = Column(
        Enum("allow", "block", "flag", name="policy_action_enum"),
        nullable=False,
        default="allow"
    )
    severity_override = Column(
        Enum("critical", "high", "medium", "low", "info", name="severity_override_enum"),
        nullable=True
    )

    # Environment info
    sdk_version = Column(String(20), nullable=False)
    environment = Column(
        Enum("production", "staging", "development", "testing", name="environment_enum"),
        nullable=False,
        default="production"
    )

    # Circuit breaker status
    circuit_breaker_status = Column(
        Enum("closed", "open", "half_open", name="circuit_status_enum"),
        nullable=True
    )

    # A/B test cohort
    ab_test_cohort = Column(String(50), nullable=True)

    # Priority for queue processing
    priority = Column(
        Enum("critical", "high", "medium", "low", name="priority_enum"),
        nullable=False,
        default="low",
        index=True
    )

    # Processing status
    processed = Column(Boolean, nullable=False, default=False, index=True)
    batch_id = Column(String(36), nullable=True, index=True)
    error_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)

    # Additional metadata (flexible JSON field)
    # Note: renamed from 'metadata' to 'event_metadata' to avoid SQLAlchemy reserved name
    event_metadata = Column(JSON, nullable=True)

    # Indexes for efficient querying
    __table_args__ = (
        # Existing indexes
        Index("idx_priority_processed", "priority", "processed"),
        Index("idx_timestamp_processed", "timestamp", "processed"),
        Index("idx_customer_timestamp", "customer_id", "timestamp"),

        # Performance optimization indexes (Phase 3B)
        # For customer queries by event type
        Index("ix_telemetry_customer_type", "customer_id", "event_type"),

        # For event type filtering with time ordering
        Index("ix_telemetry_type_created", "event_type", "timestamp"),

        # For severity-based queries
        Index("ix_telemetry_severity_timestamp", "highest_severity", "timestamp"),

        # For detection count queries
        Index("ix_telemetry_detection_customer", "detection_count", "customer_id"),

        # Constraints
        CheckConstraint("text_length >= 0", name="check_text_length_positive"),
        CheckConstraint("detection_count >= 0", name="check_detection_count_positive"),
        CheckConstraint("l1_inference_ms >= 0", name="check_l1_inference_positive"),
        CheckConstraint("total_latency_ms >= 0", name="check_total_latency_positive"),
        CheckConstraint("error_count >= 0", name="check_error_count_positive"),
    )

    def __repr__(self):
        """String representation."""
        return (
            f"<TelemetryEvent(id={self.id}, event_id={self.event_id}, "
            f"customer={self.customer_id[:8]}..., severity={self.highest_severity})>"
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "customer_id": self.customer_id,
            "api_key_id": self.api_key_id,
            "project_id": self.project_id,
            "text_hash": self.text_hash,
            "text_length": self.text_length,
            "detection_count": self.detection_count,
            "highest_severity": self.highest_severity,
            "l1_inference_ms": self.l1_inference_ms,
            "l2_inference_ms": self.l2_inference_ms,
            "total_latency_ms": self.total_latency_ms,
            "queue_depth": self.queue_depth,
            "policy_action": self.policy_action,
            "severity_override": self.severity_override,
            "sdk_version": self.sdk_version,
            "environment": self.environment,
            "circuit_breaker_status": self.circuit_breaker_status,
            "ab_test_cohort": self.ab_test_cohort,
            "metadata": self.event_metadata,  # Map back to 'metadata' for API compatibility
        }


class RuleCache(Base):
    """Cache for loaded rules with versioning.

    Corresponds to rules/rule_models.json schema.
    """

    __tablename__ = "rule_cache"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Rule identification
    rule_id = Column(String(100), nullable=False)
    version = Column(String(20), nullable=False)
    versioned_id = Column(String(120), nullable=False, unique=True, index=True)

    # Rule metadata
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    family = Column(String(50), nullable=False, index=True)
    severity = Column(
        Enum("critical", "high", "medium", "low", "info", name="rule_severity_enum"),
        nullable=False,
        index=True
    )
    confidence = Column(Float, nullable=False)

    # Rule content (stored as JSON)
    patterns = Column(JSON, nullable=False)  # List of pattern dicts
    examples = Column(JSON, nullable=True)   # Match/no-match examples
    metrics = Column(JSON, nullable=True)    # Performance metrics

    # Caching metadata
    loaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_used = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    use_count = Column(Integer, nullable=False, default=0)
    rule_hash = Column(String(64), nullable=False)  # SHA256 of rule content

    # Pack information
    pack_id = Column(String(50), nullable=True, index=True)
    pack_version = Column(String(20), nullable=True)

    __table_args__ = (
        Index("idx_family_severity", "family", "severity"),
        Index("idx_pack_rules", "pack_id", "rule_id"),
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="check_confidence_range"),
    )

    def __repr__(self):
        """String representation."""
        return f"<RuleCache(id={self.versioned_id}, severity={self.severity})>"


class MLModelCache(Base):
    """Cache for ML model metadata and predictions.

    Corresponds to ml/l2_prediction.json schema.
    """

    __tablename__ = "ml_model_cache"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Model identification
    model_name = Column(String(100), nullable=False)
    model_version = Column(String(20), nullable=False, index=True)
    model_hash = Column(String(64), nullable=False)

    # Model metadata
    loaded_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_prediction = Column(DateTime(timezone=True), nullable=True)
    prediction_count = Column(Integer, nullable=False, default=0)
    avg_inference_ms = Column(Float, nullable=True)

    # Model configuration
    device = Column(
        Enum("cpu", "cuda", "mps", "tpu", name="device_enum"),
        nullable=False,
        default="cpu"
    )
    batch_size = Column(Integer, nullable=False, default=1)
    optimization = Column(JSON, nullable=True)  # Quantization, pruning settings

    # Model performance
    accuracy = Column(Float, nullable=True)
    precision = Column(Float, nullable=True)
    recall = Column(Float, nullable=True)
    f1_score = Column(Float, nullable=True)

    __table_args__ = (
        Index("idx_model_version", "model_name", "model_version"),
        CheckConstraint("batch_size > 0", name="check_batch_size_positive"),
        CheckConstraint(
            "avg_inference_ms IS NULL OR avg_inference_ms >= 0",
            name="check_inference_ms_positive"
        ),
    )

    def __repr__(self):
        """String representation."""
        return f"<MLModelCache(name={self.model_name}, version={self.model_version})>"


class APIUsageMetrics(Base):
    """Track API usage for billing.

    Corresponds to billing/usage_metrics.json schema.
    """

    __tablename__ = "api_usage_metrics"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Time window
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)

    # Customer identification
    customer_id = Column(String(64), nullable=False, index=True)
    api_key_id = Column(String(64), nullable=False, index=True)

    # Usage counts
    scan_count = Column(Integer, nullable=False, default=0)
    threat_count = Column(Integer, nullable=False, default=0)
    tokens_scanned = Column(Integer, nullable=False, default=0)

    # Performance metrics
    avg_latency_ms = Column(Float, nullable=True)
    p95_latency_ms = Column(Float, nullable=True)
    error_count = Column(Integer, nullable=False, default=0)

    # Billing tier
    tier = Column(
        Enum("free", "pro", "enterprise", name="billing_tier_enum"),
        nullable=False,
        default="free"
    )

    __table_args__ = (
        Index("idx_customer_period", "customer_id", "period_start", "period_end"),
        CheckConstraint("period_end > period_start", name="check_period_valid"),
        CheckConstraint("scan_count >= 0", name="check_scan_count_positive"),
        CheckConstraint("tokens_scanned >= 0", name="check_tokens_positive"),
    )

    def __repr__(self):
        """String representation."""
        return (
            f"<APIUsageMetrics(customer={self.customer_id[:8]}..., "
            f"period={self.period_start} to {self.period_end})>"
        )