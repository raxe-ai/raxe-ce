"""Partner API SDK for MSSP ecosystem management.

This module provides a programmatic interface for MSSPs to manage
customers, configure data policies, and monitor agents.

Example:
    >>> from raxe.sdk.partner import PartnerClient
    >>> client = PartnerClient(mssp_id="mssp_yourcompany")
    >>> customer = client.create_customer(
    ...     customer_id="cust_acme",
    ...     name="Acme Corporation",
    ...     data_mode="full",
    ... )
    >>> print(customer.customer_id)
    cust_acme
"""

from raxe.sdk.partner.client import (
    PartnerClient,
    PartnerClientConfig,
    create_partner_client,
)

__all__ = [
    "PartnerClient",
    "PartnerClientConfig",
    "create_partner_client",
]
