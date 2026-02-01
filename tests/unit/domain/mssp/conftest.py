"""Fixtures for MSSP domain model tests.

TDD: These fixtures support tests written BEFORE implementation.
"""

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


@pytest.fixture
def sample_webhook_config() -> WebhookConfig:
    """Create a sample webhook configuration for testing."""
    return WebhookConfig(
        url="https://alerts.example.com/webhook",
        secret="whsec_test_secret_12345",
        retry_count=3,
        timeout_seconds=30,
    )


@pytest.fixture
def sample_webhook_config_localhost() -> WebhookConfig:
    """Create a localhost webhook for development testing."""
    return WebhookConfig(
        url="http://localhost:8080/webhook",
        secret="dev_secret",
        retry_count=1,
        timeout_seconds=10,
    )


@pytest.fixture
def sample_mssp() -> MSSP:
    """Create a sample MSSP for testing."""
    return MSSP(
        mssp_id="mssp_acme",
        name="Acme Security Services",
        tier=MSSPTier.PROFESSIONAL,
        max_customers=100,
        api_key_hash="sha256:abc123",
    )


@pytest.fixture
def sample_mssp_enterprise() -> MSSP:
    """Create an enterprise-tier MSSP for testing."""
    return MSSP(
        mssp_id="mssp_bigcorp",
        name="BigCorp Enterprise Security",
        tier=MSSPTier.ENTERPRISE,
        max_customers=1000,
        api_key_hash="sha256:def456",
        webhook_config=WebhookConfig(
            url="https://soc.bigcorp.com/alerts",
            secret="enterprise_secret",
        ),
    )


@pytest.fixture
def sample_mssp_starter() -> MSSP:
    """Create a starter-tier MSSP for testing."""
    return MSSP(
        mssp_id="mssp_startup",
        name="Startup Security",
        tier=MSSPTier.STARTER,
        max_customers=10,
        api_key_hash="sha256:ghi789",
    )


@pytest.fixture
def sample_customer_full_mode() -> MSSPCustomer:
    """Create a customer with full data mode for testing."""
    return MSSPCustomer(
        customer_id="cust_001",
        mssp_id="mssp_acme",
        name="Customer One",
        data_mode=DataMode.FULL,
        data_fields=["prompt_hash", "response_hash", "severity", "rule_id", "timestamp"],
        retention_days=90,
    )


@pytest.fixture
def sample_customer_privacy_safe() -> MSSPCustomer:
    """Create a customer with privacy-safe data mode for testing."""
    return MSSPCustomer(
        customer_id="cust_002",
        mssp_id="mssp_acme",
        name="Privacy Customer",
        data_mode=DataMode.PRIVACY_SAFE,
        data_fields=["severity", "rule_id", "timestamp"],
        retention_days=30,
    )


@pytest.fixture
def sample_customer_default() -> MSSPCustomer:
    """Create a customer with default settings for testing."""
    return MSSPCustomer(
        customer_id="cust_003",
        mssp_id="mssp_acme",
        name="Default Customer",
    )


@pytest.fixture
def sample_agent_config() -> AgentConfig:
    """Create a sample agent configuration for testing."""
    return AgentConfig(
        agent_id="agent_chatbot_001",
        app_id="app_support",
        customer_id="cust_001",
        name="Support Chatbot Agent",
        enabled=True,
    )


@pytest.fixture
def sample_agent_config_disabled() -> AgentConfig:
    """Create a disabled agent configuration for testing."""
    return AgentConfig(
        agent_id="agent_disabled_001",
        app_id="app_internal",
        customer_id="cust_001",
        name="Disabled Agent",
        enabled=False,
    )
