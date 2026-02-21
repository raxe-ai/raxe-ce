"""Usage metering service for MSSP billing.

Tracks agent counts and scan volumes for billing and reporting.
"""

from __future__ import annotations

from dataclasses import dataclass

from raxe.application.mssp_service import MSSPService, create_mssp_service
from raxe.infrastructure.agent.registry import AgentRegistry, get_agent_registry


@dataclass
class CustomerUsage:
    """Usage for a single customer."""

    customer_id: str
    customer_name: str
    active_agents: int
    total_scans: int
    total_threats: int


@dataclass
class UsageSummary:
    """Usage summary for an MSSP."""

    mssp_id: str
    total_customers: int
    active_agents: int
    customer_usage: list[CustomerUsage]


class UsageMeteringService:
    """Service for tracking MSSP usage and billing metrics."""

    def __init__(
        self,
        mssp_service: MSSPService | None = None,
        agent_registry: AgentRegistry | None = None,
    ) -> None:
        """Initialize usage metering service.

        Args:
            mssp_service: Optional MSSP service instance
            agent_registry: Optional agent registry instance
        """
        self._mssp_service = mssp_service or create_mssp_service()
        self._agent_registry = agent_registry or get_agent_registry()

    def get_usage_summary(self, mssp_id: str) -> UsageSummary:
        """Get usage summary for an MSSP.

        Args:
            mssp_id: MSSP identifier

        Returns:
            UsageSummary with customer breakdown

        Raises:
            MSSPNotFoundError: If MSSP not found
        """
        customers = self._mssp_service.list_customers(mssp_id)

        customer_usage: list[CustomerUsage] = []
        total_active = 0

        for customer in customers:
            agents = self._agent_registry.list_agents(
                mssp_id=mssp_id,
                customer_id=customer.customer_id,
            )
            active = self._agent_registry.count_active_agents(
                mssp_id=mssp_id,
                customer_id=customer.customer_id,
            )
            total_scans = sum(a.scans_total for a in agents)
            total_threats = sum(a.threats_total for a in agents)
            total_active += active

            customer_usage.append(
                CustomerUsage(
                    customer_id=customer.customer_id,
                    customer_name=customer.name,
                    active_agents=active,
                    total_scans=total_scans,
                    total_threats=total_threats,
                )
            )

        return UsageSummary(
            mssp_id=mssp_id,
            total_customers=len(customers),
            active_agents=total_active,
            customer_usage=customer_usage,
        )
