"""Infrastructure layer for MSSP/Partner ecosystem management.

This module provides storage implementations for MSSP entities:
- YamlMSSPRepository: YAML-based MSSP storage
- YamlCustomerRepository: YAML-based customer storage

Factory functions (preferred API):
- get_mssp_repo: Get an MSSP repository
- get_customer_repo: Get a customer repository

Utilities:
- get_mssp_base_path: Get the base path for MSSP storage
"""

import os
from pathlib import Path

from raxe.infrastructure.mssp.yaml_repository import (
    YamlCustomerRepository,
    YamlMSSPRepository,
)

__all__ = [
    "YamlCustomerRepository",
    "YamlMSSPRepository",
    "get_customer_repo",
    "get_mssp_base_path",
    "get_mssp_repo",
]


def get_mssp_base_path() -> Path:
    """Get the base path for MSSP storage.

    Can be overridden with RAXE_MSSP_DIR environment variable.

    Returns:
        Path to MSSP storage directory (default: ~/.raxe/mssp/)
    """
    env_path = os.getenv("RAXE_MSSP_DIR")
    if env_path:
        return Path(env_path)
    return Path.home() / ".raxe" / "mssp"


def get_mssp_repo(base_path: Path | None = None) -> "YamlMSSPRepository":
    """Get an MSSP repository.

    Args:
        base_path: Optional custom base path for storage

    Returns:
        YamlMSSPRepository instance
    """
    path = base_path or get_mssp_base_path()
    return YamlMSSPRepository(path)


def get_customer_repo(mssp_id: str, base_path: Path | None = None) -> "YamlCustomerRepository":
    """Get a customer repository for a specific MSSP.

    Args:
        mssp_id: MSSP identifier
        base_path: Optional custom base path for storage

    Returns:
        YamlCustomerRepository instance
    """
    path = base_path or get_mssp_base_path()
    return YamlCustomerRepository(path, mssp_id)
