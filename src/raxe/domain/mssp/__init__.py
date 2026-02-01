"""MSSP (Managed Security Service Provider) domain models.

This module provides domain models for the MSSP multi-tenant hierarchy:
    mssp_id -> customer_id -> app_id -> agent_id

Privacy Modes:
    - FULL: All telemetry data fields available
    - PRIVACY_SAFE: Only non-PII fields (default, safest option)
"""

from raxe.domain.mssp.models import (
    MSSP,
    AgentConfig,
    DataMode,
    MSSPCustomer,
    MSSPTier,
    WebhookConfig,
)

__all__ = [
    "MSSP",
    "AgentConfig",
    "DataMode",
    "MSSPCustomer",
    "MSSPTier",
    "WebhookConfig",
]
