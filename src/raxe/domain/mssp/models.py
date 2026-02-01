"""MSSP domain models.

TDD: Implementation following tests in tests/unit/domain/mssp/test_models.py.

MSSP Hierarchy:
    mssp_id -> customer_id -> app_id -> agent_id

Privacy Modes:
    - FULL: All telemetry data fields available
    - PRIVACY_SAFE: Only non-PII fields (default)

SIEM Integration:
    Per-customer SIEM configuration enables routing events to different
    SIEM platforms (Splunk, CrowdStrike, Sentinel) per customer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

if TYPE_CHECKING:
    pass


class DataMode(str, Enum):
    """Data privacy mode for telemetry.

    Controls which fields are included in telemetry data sent to MSSP.

    Attributes:
        FULL: All telemetry data fields available including hashes
        PRIVACY_SAFE: Only non-PII fields (no hashes, no matched text)
    """

    FULL = "full"
    PRIVACY_SAFE = "privacy_safe"


class MSSPTier(str, Enum):
    """MSSP subscription tier.

    Determines available features and customer limits.

    Attributes:
        STARTER: Basic tier with limited customers
        PROFESSIONAL: Mid-tier with more customers and features
        ENTERPRISE: Full-featured tier with unlimited capabilities
    """

    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


@dataclass(frozen=True)
class WebhookConfig:
    """Webhook configuration for alert delivery.

    Configures how security alerts are delivered to external systems.

    Attributes:
        url: HTTPS webhook endpoint URL (HTTP allowed only for localhost/127.0.0.1)
        secret: Shared secret for webhook signature verification
        retry_count: Number of delivery retries on failure (0-10, default 3)
        timeout_seconds: Request timeout in seconds (5-120, default 30)

    Raises:
        ValueError: If validation fails for any field
    """

    url: str
    secret: str
    retry_count: int = 3
    timeout_seconds: int = 30

    def __post_init__(self) -> None:
        """Validate webhook configuration."""
        # Validate URL is not empty
        if not self.url:
            raise ValueError("url cannot be empty")

        # Validate secret is not empty
        if not self.secret:
            raise ValueError("secret cannot be empty")

        # Parse and validate URL
        try:
            parsed = urlparse(self.url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid URL format")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError("Invalid URL format") from e

        # Validate HTTPS requirement (except localhost)
        is_localhost = parsed.netloc.startswith("localhost") or parsed.netloc.startswith(
            "127.0.0.1"
        )
        if parsed.scheme != "https" and not is_localhost:
            raise ValueError("HTTPS is required for webhook URLs")

        # Validate retry_count bounds (0-10)
        if not 0 <= self.retry_count <= 10:
            raise ValueError("retry_count must be between 0 and 10")

        # Validate timeout_seconds bounds (5-120)
        if not 5 <= self.timeout_seconds <= 120:
            raise ValueError("timeout_seconds must be between 5 and 120")


@dataclass(frozen=True)
class MSSP:
    """Managed Security Service Provider entity.

    Represents an MSSP organization that manages multiple customer accounts.

    Attributes:
        mssp_id: Unique identifier, must start with 'mssp_'
        name: Display name for the MSSP
        tier: Subscription tier (STARTER, PROFESSIONAL, ENTERPRISE)
        max_customers: Maximum number of customers allowed
        api_key_hash: Hashed API key for authentication
        webhook_config: Optional webhook for receiving alerts
        created_at: ISO 8601 creation timestamp
        updated_at: ISO 8601 last update timestamp

    Raises:
        ValueError: If validation fails for any field
    """

    mssp_id: str
    name: str
    tier: MSSPTier
    max_customers: int
    api_key_hash: str
    webhook_config: WebhookConfig | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        """Validate MSSP configuration."""
        # Validate mssp_id is not empty
        if not self.mssp_id:
            raise ValueError("mssp_id cannot be empty")

        # Validate mssp_id prefix
        if not self.mssp_id.startswith("mssp_"):
            raise ValueError("mssp_id must start with 'mssp_'")

        # Validate name is not empty
        if not self.name:
            raise ValueError("name cannot be empty")

        # Validate api_key_hash is not empty
        if not self.api_key_hash:
            raise ValueError("api_key_hash cannot be empty")

        # Validate max_customers is positive
        if self.max_customers <= 0:
            raise ValueError("max_customers must be a positive integer")


@dataclass(frozen=True)
class MSSPCustomer:
    """Customer within an MSSP's portfolio.

    Represents an organization managed by an MSSP.

    Attributes:
        customer_id: Unique identifier, must start with 'cust_'
        mssp_id: Parent MSSP identifier, must start with 'mssp_'
        name: Display name for the customer
        data_mode: Privacy mode for telemetry (default PRIVACY_SAFE)
        data_fields: List of allowed telemetry fields (default empty list)
        retention_days: Data retention period in days (1-365, default 30)
        heartbeat_threshold_seconds: Agent heartbeat timeout (60-3600, default 300)
        webhook_config: Optional customer-specific webhook override
        siem_config: Optional SIEM integration configuration for this customer
        created_at: ISO 8601 creation timestamp
        updated_at: ISO 8601 last update timestamp

    Raises:
        ValueError: If validation fails for any field

    Example:
        >>> from raxe.domain.siem.config import SIEMConfig, SIEMType
        >>> siem = SIEMConfig(
        ...     siem_type=SIEMType.SPLUNK,
        ...     endpoint_url="https://splunk:8088/services/collector/event",
        ...     auth_token="token",
        ... )
        >>> customer = MSSPCustomer(
        ...     customer_id="cust_123",
        ...     mssp_id="mssp_test",
        ...     name="Acme Corp",
        ...     siem_config=siem,
        ... )
    """

    customer_id: str
    mssp_id: str
    name: str
    data_mode: DataMode = DataMode.PRIVACY_SAFE
    data_fields: list[str] = field(default_factory=list)
    retention_days: int = 30
    heartbeat_threshold_seconds: int = 300
    webhook_config: WebhookConfig | None = None
    siem_config: Any = None  # Type: SIEMConfig | None (Any to avoid circular import)
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        """Validate customer configuration."""
        # Validate customer_id is not empty
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")

        # Validate customer_id prefix
        if not self.customer_id.startswith("cust_"):
            raise ValueError("customer_id must start with 'cust_'")

        # Validate mssp_id is not empty
        if not self.mssp_id:
            raise ValueError("mssp_id cannot be empty")

        # Validate mssp_id prefix
        if not self.mssp_id.startswith("mssp_"):
            raise ValueError("mssp_id must start with 'mssp_'")

        # Validate name is not empty
        if not self.name:
            raise ValueError("name cannot be empty")

        # Validate retention_days bounds (1-365)
        if not 1 <= self.retention_days <= 365:
            raise ValueError("retention_days must be between 1 and 365")

        # Validate heartbeat_threshold_seconds bounds (60-3600)
        if not 60 <= self.heartbeat_threshold_seconds <= 3600:
            raise ValueError("heartbeat_threshold_seconds must be between 60 and 3600")


@dataclass(frozen=True)
class AgentConfig:
    """Agent configuration within a customer's application.

    Represents a deployed AI agent being monitored.

    Attributes:
        agent_id: Unique identifier, must start with 'agent_'
        app_id: Application identifier, must start with 'app_'
        customer_id: Parent customer identifier, must start with 'cust_'
        name: Display name for the agent
        enabled: Whether the agent is active (default True)
        last_heartbeat: ISO 8601 timestamp of last heartbeat
        created_at: ISO 8601 creation timestamp
        updated_at: ISO 8601 last update timestamp

    Raises:
        ValueError: If validation fails for any field
    """

    agent_id: str
    app_id: str
    customer_id: str
    name: str
    enabled: bool = True
    last_heartbeat: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    def __post_init__(self) -> None:
        """Validate agent configuration."""
        # Validate agent_id is not empty
        if not self.agent_id:
            raise ValueError("agent_id cannot be empty")

        # Validate agent_id prefix
        if not self.agent_id.startswith("agent_"):
            raise ValueError("agent_id must start with 'agent_'")

        # Validate app_id is not empty
        if not self.app_id:
            raise ValueError("app_id cannot be empty")

        # Validate app_id prefix
        if not self.app_id.startswith("app_"):
            raise ValueError("app_id must start with 'app_'")

        # Validate customer_id is not empty
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")

        # Validate customer_id prefix
        if not self.customer_id.startswith("cust_"):
            raise ValueError("customer_id must start with 'cust_'")

        # Validate name is not empty
        if not self.name:
            raise ValueError("name cannot be empty")
