"""Tests for MSSP domain models.

TDD: These tests are written BEFORE implementation.
Tests will fail until the models are implemented in src/raxe/domain/mssp/models.py

MSSP Hierarchy:
    mssp_id -> customer_id -> app_id -> agent_id

Privacy Modes:
    - FULL: All telemetry data fields available
    - PRIVACY_SAFE: Only non-PII fields (no hashes, no matched text)
"""

from dataclasses import FrozenInstanceError

import pytest

# Note: These imports will fail until implementation exists
# This is expected in TDD - tests are written first
from raxe.domain.mssp.models import (
    MSSP,
    AgentConfig,
    DataMode,
    MSSPCustomer,
    MSSPTier,
    WebhookConfig,
)


class TestDataMode:
    """Tests for DataMode enum."""

    def test_data_mode_values(self) -> None:
        """DataMode enum has correct string values."""
        assert DataMode.FULL.value == "full"
        assert DataMode.PRIVACY_SAFE.value == "privacy_safe"

    def test_data_mode_from_string(self) -> None:
        """DataMode can be created from string value."""
        assert DataMode("full") == DataMode.FULL
        assert DataMode("privacy_safe") == DataMode.PRIVACY_SAFE

    def test_data_mode_invalid_raises(self) -> None:
        """Invalid mode string raises ValueError."""
        with pytest.raises(ValueError):
            DataMode("invalid_mode")

    def test_data_mode_is_string_enum(self) -> None:
        """DataMode values are strings for serialization."""
        assert isinstance(DataMode.FULL.value, str)
        assert isinstance(DataMode.PRIVACY_SAFE.value, str)


class TestMSSPTier:
    """Tests for MSSPTier enum."""

    def test_mssp_tier_values(self) -> None:
        """MSSPTier enum has correct string values."""
        assert MSSPTier.STARTER.value == "starter"
        assert MSSPTier.PROFESSIONAL.value == "professional"
        assert MSSPTier.ENTERPRISE.value == "enterprise"

    def test_mssp_tier_from_string(self) -> None:
        """MSSPTier can be created from string value."""
        assert MSSPTier("starter") == MSSPTier.STARTER
        assert MSSPTier("professional") == MSSPTier.PROFESSIONAL
        assert MSSPTier("enterprise") == MSSPTier.ENTERPRISE

    def test_mssp_tier_invalid_raises(self) -> None:
        """Invalid tier string raises ValueError."""
        with pytest.raises(ValueError):
            MSSPTier("invalid_tier")

    def test_mssp_tier_ordering(self) -> None:
        """MSSPTier values represent ascending feature levels."""
        # Verify all tiers exist
        tiers = [MSSPTier.STARTER, MSSPTier.PROFESSIONAL, MSSPTier.ENTERPRISE]
        assert len(tiers) == 3

    def test_mssp_tier_default_max_customers(self) -> None:
        """Each tier has a default max_customers value."""
        assert MSSPTier.STARTER.default_max_customers == 10
        assert MSSPTier.PROFESSIONAL.default_max_customers == 50
        assert MSSPTier.ENTERPRISE.default_max_customers == 0  # unlimited


class TestWebhookConfig:
    """Tests for WebhookConfig dataclass."""

    def test_webhook_config_creation(self) -> None:
        """WebhookConfig can be created with required fields."""
        config = WebhookConfig(
            url="https://example.com/webhook",
            secret="whsec_test_secret",
        )
        assert config.url == "https://example.com/webhook"
        assert config.secret == "whsec_test_secret"

    def test_webhook_config_defaults(self) -> None:
        """WebhookConfig has correct default values."""
        config = WebhookConfig(
            url="https://example.com/webhook",
            secret="test_secret",
        )
        assert config.retry_count == 3
        assert config.timeout_seconds == 30

    def test_webhook_config_custom_values(self) -> None:
        """WebhookConfig accepts custom retry and timeout values."""
        config = WebhookConfig(
            url="https://example.com/webhook",
            secret="test_secret",
            retry_count=5,
            timeout_seconds=60,
        )
        assert config.retry_count == 5
        assert config.timeout_seconds == 60

    def test_webhook_config_validation_https_required(self) -> None:
        """Non-HTTPS URLs raise ValueError (except localhost)."""
        with pytest.raises(ValueError, match="HTTPS.*required"):
            WebhookConfig(
                url="http://example.com/webhook",
                secret="test_secret",
            )

    def test_webhook_config_allows_localhost_http(self) -> None:
        """HTTP is allowed for localhost development."""
        config = WebhookConfig(
            url="http://localhost:8080/webhook",
            secret="test_secret",
        )
        assert config.url == "http://localhost:8080/webhook"

    def test_webhook_config_allows_127_0_0_1_http(self) -> None:
        """HTTP is allowed for 127.0.0.1 development."""
        config = WebhookConfig(
            url="http://127.0.0.1:8080/webhook",
            secret="test_secret",
        )
        assert config.url == "http://127.0.0.1:8080/webhook"

    def test_webhook_config_validation_empty_url(self) -> None:
        """Empty URL raises ValueError."""
        with pytest.raises(ValueError, match="url cannot be empty"):
            WebhookConfig(
                url="",
                secret="test_secret",
            )

    def test_webhook_config_validation_empty_secret(self) -> None:
        """Empty secret raises ValueError."""
        with pytest.raises(ValueError, match="secret cannot be empty"):
            WebhookConfig(
                url="https://example.com/webhook",
                secret="",
            )

    def test_webhook_config_validation_retry_count_negative(self) -> None:
        """Negative retry_count raises ValueError."""
        with pytest.raises(ValueError, match="retry_count.*0.*10"):
            WebhookConfig(
                url="https://example.com/webhook",
                secret="test_secret",
                retry_count=-1,
            )

    def test_webhook_config_validation_retry_count_too_high(self) -> None:
        """retry_count > 10 raises ValueError."""
        with pytest.raises(ValueError, match="retry_count.*0.*10"):
            WebhookConfig(
                url="https://example.com/webhook",
                secret="test_secret",
                retry_count=11,
            )

    def test_webhook_config_validation_retry_count_bounds(self) -> None:
        """Valid retry_count values (0, 5, 10) are accepted."""
        for count in [0, 5, 10]:
            config = WebhookConfig(
                url="https://example.com/webhook",
                secret="test_secret",
                retry_count=count,
            )
            assert config.retry_count == count

    def test_webhook_config_validation_timeout_too_low(self) -> None:
        """timeout_seconds < 5 raises ValueError."""
        with pytest.raises(ValueError, match="timeout_seconds.*5.*120"):
            WebhookConfig(
                url="https://example.com/webhook",
                secret="test_secret",
                timeout_seconds=4,
            )

    def test_webhook_config_validation_timeout_too_high(self) -> None:
        """timeout_seconds > 120 raises ValueError."""
        with pytest.raises(ValueError, match="timeout_seconds.*5.*120"):
            WebhookConfig(
                url="https://example.com/webhook",
                secret="test_secret",
                timeout_seconds=121,
            )

    def test_webhook_config_validation_timeout_bounds(self) -> None:
        """Valid timeout values (5, 60, 120) are accepted."""
        for timeout in [5, 60, 120]:
            config = WebhookConfig(
                url="https://example.com/webhook",
                secret="test_secret",
                timeout_seconds=timeout,
            )
            assert config.timeout_seconds == timeout

    def test_webhook_config_immutable(self) -> None:
        """WebhookConfig is immutable (frozen)."""
        config = WebhookConfig(
            url="https://example.com/webhook",
            secret="test_secret",
        )
        with pytest.raises(FrozenInstanceError):
            config.url = "https://other.com/webhook"  # type: ignore[misc]

    def test_webhook_config_validation_invalid_url_format(self) -> None:
        """Invalid URL format raises ValueError."""
        with pytest.raises(ValueError, match="Invalid URL"):
            WebhookConfig(
                url="not-a-valid-url",
                secret="test_secret",
            )


class TestMSSP:
    """Tests for MSSP dataclass."""

    def test_mssp_creation(self) -> None:
        """MSSP can be created with required fields."""
        mssp = MSSP(
            mssp_id="mssp_acme",
            name="Acme Security",
            tier=MSSPTier.PROFESSIONAL,
            max_customers=100,
            api_key_hash="sha256:abc123",
        )
        assert mssp.mssp_id == "mssp_acme"
        assert mssp.name == "Acme Security"
        assert mssp.tier == MSSPTier.PROFESSIONAL
        assert mssp.max_customers == 100
        assert mssp.api_key_hash == "sha256:abc123"

    def test_mssp_defaults(self) -> None:
        """MSSP has correct default values."""
        mssp = MSSP(
            mssp_id="mssp_test",
            name="Test MSSP",
            tier=MSSPTier.STARTER,
            max_customers=10,
            api_key_hash="sha256:test",
        )
        assert mssp.webhook_config is None
        assert mssp.created_at is None
        assert mssp.updated_at is None

    def test_mssp_with_webhook(self, sample_webhook_config: WebhookConfig) -> None:
        """MSSP can have optional webhook configuration."""
        mssp = MSSP(
            mssp_id="mssp_with_webhook",
            name="MSSP With Webhook",
            tier=MSSPTier.ENTERPRISE,
            max_customers=500,
            api_key_hash="sha256:webhook_test",
            webhook_config=sample_webhook_config,
        )
        assert mssp.webhook_config is not None
        assert mssp.webhook_config.url == "https://alerts.example.com/webhook"

    def test_mssp_validation_empty_id(self) -> None:
        """Empty mssp_id raises ValueError."""
        with pytest.raises(ValueError, match="mssp_id cannot be empty"):
            MSSP(
                mssp_id="",
                name="Test",
                tier=MSSPTier.STARTER,
                max_customers=10,
                api_key_hash="sha256:test",
            )

    def test_mssp_validation_empty_name(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            MSSP(
                mssp_id="mssp_test",
                name="",
                tier=MSSPTier.STARTER,
                max_customers=10,
                api_key_hash="sha256:test",
            )

    def test_mssp_validation_empty_api_key_hash(self) -> None:
        """Empty api_key_hash raises ValueError."""
        with pytest.raises(ValueError, match="api_key_hash cannot be empty"):
            MSSP(
                mssp_id="mssp_test",
                name="Test",
                tier=MSSPTier.STARTER,
                max_customers=10,
                api_key_hash="",
            )

    def test_mssp_validation_id_prefix(self) -> None:
        """mssp_id must start with 'mssp_' prefix."""
        with pytest.raises(ValueError, match="mssp_id must start with 'mssp_'"):
            MSSP(
                mssp_id="invalid_id",
                name="Test",
                tier=MSSPTier.STARTER,
                max_customers=10,
                api_key_hash="sha256:test",
            )

    def test_mssp_validation_max_customers_zero_is_unlimited(self) -> None:
        """max_customers=0 means unlimited."""
        mssp = MSSP(
            mssp_id="mssp_test",
            name="Test",
            tier=MSSPTier.ENTERPRISE,
            max_customers=0,
            api_key_hash="sha256:test",
        )
        assert mssp.max_customers == 0

    def test_mssp_validation_max_customers_negative(self) -> None:
        """max_customers cannot be negative."""
        with pytest.raises(ValueError, match="max_customers must be.*non-negative"):
            MSSP(
                mssp_id="mssp_test",
                name="Test",
                tier=MSSPTier.STARTER,
                max_customers=-5,
                api_key_hash="sha256:test",
            )

    def test_mssp_immutable(self) -> None:
        """MSSP is immutable (frozen)."""
        mssp = MSSP(
            mssp_id="mssp_test",
            name="Test",
            tier=MSSPTier.STARTER,
            max_customers=10,
            api_key_hash="sha256:test",
        )
        with pytest.raises(FrozenInstanceError):
            mssp.name = "Changed"  # type: ignore[misc]

    def test_mssp_tier_enum_value(self) -> None:
        """MSSP tier is proper MSSPTier enum."""
        mssp = MSSP(
            mssp_id="mssp_test",
            name="Test",
            tier=MSSPTier.ENTERPRISE,
            max_customers=1000,
            api_key_hash="sha256:test",
        )
        assert isinstance(mssp.tier, MSSPTier)
        assert mssp.tier == MSSPTier.ENTERPRISE


class TestMSSPCustomer:
    """Tests for MSSPCustomer dataclass."""

    def test_customer_creation(self) -> None:
        """MSSPCustomer can be created with required fields."""
        customer = MSSPCustomer(
            customer_id="cust_001",
            mssp_id="mssp_acme",
            name="Customer One",
        )
        assert customer.customer_id == "cust_001"
        assert customer.mssp_id == "mssp_acme"
        assert customer.name == "Customer One"

    def test_customer_defaults(self) -> None:
        """MSSPCustomer has correct default values."""
        customer = MSSPCustomer(
            customer_id="cust_test",
            mssp_id="mssp_test",
            name="Test Customer",
        )
        assert customer.data_mode == DataMode.PRIVACY_SAFE
        assert customer.data_fields == []
        assert customer.retention_days == 30
        assert customer.heartbeat_threshold_seconds == 300
        assert customer.webhook_config is None
        assert customer.created_at is None
        assert customer.updated_at is None

    def test_customer_full_data_mode(self) -> None:
        """MSSPCustomer can be created with full data mode."""
        customer = MSSPCustomer(
            customer_id="cust_full",
            mssp_id="mssp_test",
            name="Full Data Customer",
            data_mode=DataMode.FULL,
            data_fields=["prompt_hash", "severity", "rule_id"],
        )
        assert customer.data_mode == DataMode.FULL
        assert "prompt_hash" in customer.data_fields

    def test_customer_privacy_safe_mode(self) -> None:
        """MSSPCustomer can be created with privacy-safe data mode."""
        customer = MSSPCustomer(
            customer_id="cust_safe",
            mssp_id="mssp_test",
            name="Privacy Customer",
            data_mode=DataMode.PRIVACY_SAFE,
            data_fields=["severity", "rule_id"],
        )
        assert customer.data_mode == DataMode.PRIVACY_SAFE

    def test_customer_validation_empty_id(self) -> None:
        """Empty customer_id raises ValueError."""
        with pytest.raises(ValueError, match="customer_id cannot be empty"):
            MSSPCustomer(
                customer_id="",
                mssp_id="mssp_test",
                name="Test",
            )

    def test_customer_validation_empty_mssp_id(self) -> None:
        """Empty mssp_id raises ValueError."""
        with pytest.raises(ValueError, match="mssp_id cannot be empty"):
            MSSPCustomer(
                customer_id="cust_test",
                mssp_id="",
                name="Test",
            )

    def test_customer_validation_empty_name(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            MSSPCustomer(
                customer_id="cust_test",
                mssp_id="mssp_test",
                name="",
            )

    def test_customer_validation_id_prefix(self) -> None:
        """customer_id must start with 'cust_' prefix."""
        with pytest.raises(ValueError, match="customer_id must start with 'cust_'"):
            MSSPCustomer(
                customer_id="invalid_id",
                mssp_id="mssp_test",
                name="Test",
            )

    def test_customer_validation_mssp_id_prefix(self) -> None:
        """mssp_id must start with 'mssp_' prefix."""
        with pytest.raises(ValueError, match="mssp_id must start with 'mssp_'"):
            MSSPCustomer(
                customer_id="cust_test",
                mssp_id="invalid_mssp",
                name="Test",
            )

    def test_customer_validation_retention_days_too_low(self) -> None:
        """retention_days < 1 raises ValueError."""
        with pytest.raises(ValueError, match="retention_days must be.*1.*365"):
            MSSPCustomer(
                customer_id="cust_test",
                mssp_id="mssp_test",
                name="Test",
                retention_days=0,
            )

    def test_customer_validation_retention_days_too_high(self) -> None:
        """retention_days > 365 raises ValueError."""
        with pytest.raises(ValueError, match="retention_days must be.*1.*365"):
            MSSPCustomer(
                customer_id="cust_test",
                mssp_id="mssp_test",
                name="Test",
                retention_days=366,
            )

    def test_customer_validation_retention_days_bounds(self) -> None:
        """Valid retention_days values (1, 90, 365) are accepted."""
        for days in [1, 90, 365]:
            customer = MSSPCustomer(
                customer_id="cust_test",
                mssp_id="mssp_test",
                name="Test",
                retention_days=days,
            )
            assert customer.retention_days == days

    def test_customer_validation_heartbeat_threshold_too_low(self) -> None:
        """heartbeat_threshold_seconds < 60 raises ValueError."""
        with pytest.raises(ValueError, match="heartbeat_threshold_seconds must be.*60.*3600"):
            MSSPCustomer(
                customer_id="cust_test",
                mssp_id="mssp_test",
                name="Test",
                heartbeat_threshold_seconds=59,
            )

    def test_customer_validation_heartbeat_threshold_too_high(self) -> None:
        """heartbeat_threshold_seconds > 3600 raises ValueError."""
        with pytest.raises(ValueError, match="heartbeat_threshold_seconds must be.*60.*3600"):
            MSSPCustomer(
                customer_id="cust_test",
                mssp_id="mssp_test",
                name="Test",
                heartbeat_threshold_seconds=3601,
            )

    def test_customer_validation_heartbeat_threshold_bounds(self) -> None:
        """Valid heartbeat_threshold values (60, 300, 3600) are accepted."""
        for threshold in [60, 300, 3600]:
            customer = MSSPCustomer(
                customer_id="cust_test",
                mssp_id="mssp_test",
                name="Test",
                heartbeat_threshold_seconds=threshold,
            )
            assert customer.heartbeat_threshold_seconds == threshold

    def test_customer_with_webhook(self, sample_webhook_config: WebhookConfig) -> None:
        """MSSPCustomer can have customer-level webhook override."""
        customer = MSSPCustomer(
            customer_id="cust_webhook",
            mssp_id="mssp_test",
            name="Webhook Customer",
            webhook_config=sample_webhook_config,
        )
        assert customer.webhook_config is not None
        assert customer.webhook_config.url == "https://alerts.example.com/webhook"

    def test_customer_immutable(self) -> None:
        """MSSPCustomer is immutable (frozen)."""
        customer = MSSPCustomer(
            customer_id="cust_test",
            mssp_id="mssp_test",
            name="Test",
        )
        with pytest.raises(FrozenInstanceError):
            customer.name = "Changed"  # type: ignore[misc]

    def test_customer_data_mode_enum_value(self) -> None:
        """MSSPCustomer data_mode is proper DataMode enum."""
        customer = MSSPCustomer(
            customer_id="cust_test",
            mssp_id="mssp_test",
            name="Test",
            data_mode=DataMode.FULL,
        )
        assert isinstance(customer.data_mode, DataMode)
        assert customer.data_mode == DataMode.FULL


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_agent_config_creation(self) -> None:
        """AgentConfig can be created with required fields."""
        agent = AgentConfig(
            agent_id="agent_001",
            app_id="app_support",
            customer_id="cust_001",
            name="Support Bot Agent",
        )
        assert agent.agent_id == "agent_001"
        assert agent.app_id == "app_support"
        assert agent.customer_id == "cust_001"
        assert agent.name == "Support Bot Agent"

    def test_agent_config_defaults(self) -> None:
        """AgentConfig has correct default values."""
        agent = AgentConfig(
            agent_id="agent_test",
            app_id="app_test",
            customer_id="cust_test",
            name="Test Agent",
        )
        assert agent.enabled is True
        assert agent.last_heartbeat is None
        assert agent.created_at is None
        assert agent.updated_at is None

    def test_agent_config_disabled(self) -> None:
        """AgentConfig can be created with enabled=False."""
        agent = AgentConfig(
            agent_id="agent_disabled",
            app_id="app_test",
            customer_id="cust_test",
            name="Disabled Agent",
            enabled=False,
        )
        assert agent.enabled is False

    def test_agent_config_validation_empty_id(self) -> None:
        """Empty agent_id raises ValueError."""
        with pytest.raises(ValueError, match="agent_id cannot be empty"):
            AgentConfig(
                agent_id="",
                app_id="app_test",
                customer_id="cust_test",
                name="Test",
            )

    def test_agent_config_validation_empty_app_id(self) -> None:
        """Empty app_id raises ValueError."""
        with pytest.raises(ValueError, match="app_id cannot be empty"):
            AgentConfig(
                agent_id="agent_test",
                app_id="",
                customer_id="cust_test",
                name="Test",
            )

    def test_agent_config_validation_empty_customer_id(self) -> None:
        """Empty customer_id raises ValueError."""
        with pytest.raises(ValueError, match="customer_id cannot be empty"):
            AgentConfig(
                agent_id="agent_test",
                app_id="app_test",
                customer_id="",
                name="Test",
            )

    def test_agent_config_validation_empty_name(self) -> None:
        """Empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            AgentConfig(
                agent_id="agent_test",
                app_id="app_test",
                customer_id="cust_test",
                name="",
            )

    def test_agent_config_validation_id_prefix(self) -> None:
        """agent_id must start with 'agent_' prefix."""
        with pytest.raises(ValueError, match="agent_id must start with 'agent_'"):
            AgentConfig(
                agent_id="invalid_id",
                app_id="app_test",
                customer_id="cust_test",
                name="Test",
            )

    def test_agent_config_validation_app_id_prefix(self) -> None:
        """app_id must start with 'app_' prefix."""
        with pytest.raises(ValueError, match="app_id must start with 'app_'"):
            AgentConfig(
                agent_id="agent_test",
                app_id="invalid_app",
                customer_id="cust_test",
                name="Test",
            )

    def test_agent_config_validation_customer_id_prefix(self) -> None:
        """customer_id must start with 'cust_' prefix."""
        with pytest.raises(ValueError, match="customer_id must start with 'cust_'"):
            AgentConfig(
                agent_id="agent_test",
                app_id="app_test",
                customer_id="invalid_cust",
                name="Test",
            )

    def test_agent_config_with_heartbeat(self) -> None:
        """AgentConfig can have last_heartbeat timestamp."""
        agent = AgentConfig(
            agent_id="agent_heartbeat",
            app_id="app_test",
            customer_id="cust_test",
            name="Heartbeat Agent",
            last_heartbeat="2025-01-29T10:00:00Z",
        )
        assert agent.last_heartbeat == "2025-01-29T10:00:00Z"

    def test_agent_config_immutable(self) -> None:
        """AgentConfig is immutable (frozen)."""
        agent = AgentConfig(
            agent_id="agent_test",
            app_id="app_test",
            customer_id="cust_test",
            name="Test",
        )
        with pytest.raises(FrozenInstanceError):
            agent.name = "Changed"  # type: ignore[misc]


class TestHierarchyRelationships:
    """Tests for MSSP hierarchy relationships.

    Hierarchy: mssp_id -> customer_id -> app_id -> agent_id
    """

    def test_customer_belongs_to_mssp(
        self, sample_mssp: MSSP, sample_customer_full_mode: MSSPCustomer
    ) -> None:
        """MSSPCustomer references its parent MSSP via mssp_id."""
        assert sample_customer_full_mode.mssp_id == sample_mssp.mssp_id

    def test_agent_belongs_to_customer(
        self, sample_customer_full_mode: MSSPCustomer, sample_agent_config: AgentConfig
    ) -> None:
        """AgentConfig references its parent MSSPCustomer via customer_id."""
        assert sample_agent_config.customer_id == sample_customer_full_mode.customer_id

    def test_hierarchy_chain_integrity(
        self,
        sample_mssp: MSSP,
        sample_customer_full_mode: MSSPCustomer,
        sample_agent_config: AgentConfig,
    ) -> None:
        """Full hierarchy chain from MSSP to Agent is traceable."""
        # MSSP -> Customer
        assert sample_customer_full_mode.mssp_id == sample_mssp.mssp_id
        # Customer -> Agent
        assert sample_agent_config.customer_id == sample_customer_full_mode.customer_id
        # All IDs follow prefix conventions
        assert sample_mssp.mssp_id.startswith("mssp_")
        assert sample_customer_full_mode.customer_id.startswith("cust_")
        assert sample_agent_config.app_id.startswith("app_")
        assert sample_agent_config.agent_id.startswith("agent_")


class TestDataModeConfiguration:
    """Tests for data mode and privacy configuration."""

    def test_full_mode_allows_all_fields(self, sample_customer_full_mode: MSSPCustomer) -> None:
        """Full data mode allows all telemetry fields."""
        assert sample_customer_full_mode.data_mode == DataMode.FULL
        # Full mode allows hash fields
        assert "prompt_hash" in sample_customer_full_mode.data_fields

    def test_privacy_safe_mode_restricts_fields(
        self, sample_customer_privacy_safe: MSSPCustomer
    ) -> None:
        """Privacy-safe mode restricts to non-PII fields only."""
        assert sample_customer_privacy_safe.data_mode == DataMode.PRIVACY_SAFE
        # Privacy-safe should not include hash fields
        assert "prompt_hash" not in sample_customer_privacy_safe.data_fields

    def test_default_mode_is_privacy_safe(self, sample_customer_default: MSSPCustomer) -> None:
        """Default data mode is privacy-safe for safety."""
        assert sample_customer_default.data_mode == DataMode.PRIVACY_SAFE

    def test_data_fields_list_is_immutable(self, sample_customer_full_mode: MSSPCustomer) -> None:
        """Data fields list should be treated as immutable."""
        # Note: tuple would be truly immutable, list is mutable but frozen dataclass
        # prevents reassignment. This test documents expected behavior.
        original_fields = sample_customer_full_mode.data_fields
        assert isinstance(original_fields, list)


class TestWebhookInheritance:
    """Tests for webhook configuration inheritance."""

    def test_mssp_webhook_config(self, sample_mssp_enterprise: MSSP) -> None:
        """MSSP can have a webhook configuration."""
        assert sample_mssp_enterprise.webhook_config is not None
        assert sample_mssp_enterprise.webhook_config.url == "https://soc.bigcorp.com/alerts"

    def test_customer_can_override_webhook(self, sample_webhook_config: WebhookConfig) -> None:
        """Customer can override MSSP webhook with their own."""
        customer = MSSPCustomer(
            customer_id="cust_override",
            mssp_id="mssp_enterprise",
            name="Override Customer",
            webhook_config=sample_webhook_config,
        )
        # Customer has their own webhook
        assert customer.webhook_config is not None
        assert customer.webhook_config.url == "https://alerts.example.com/webhook"

    def test_customer_without_webhook_inherits_none(
        self, sample_customer_default: MSSPCustomer
    ) -> None:
        """Customer without webhook_config has None (inherits from MSSP at runtime)."""
        assert sample_customer_default.webhook_config is None
