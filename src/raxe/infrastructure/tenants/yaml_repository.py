"""YAML-based repositories for tenant, policy, and app storage.

Storage structure:
    ~/.raxe/tenants/
    ├── {tenant_id}/
    │   ├── tenant.yaml      # Tenant configuration
    │   ├── policies/
    │   │   └── {policy_id}.yaml
    │   └── apps/
    │       └── {app_id}.yaml
    └── _global/
        └── policies/
            └── {policy_id}.yaml  # Global policies (tenant_id=None)
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from raxe.domain.tenants.models import (
    App,
    PolicyMode,
    Tenant,
    TenantPolicy,
)
from raxe.infrastructure.tenants.cache import PolicyCache

logger = logging.getLogger(__name__)

# Schema version for YAML files
SCHEMA_VERSION = "1.0"

# Directory name for global (non-tenant) policies
GLOBAL_TENANT_DIR = "_global"

# Reserved directory names that cannot be used as entity IDs
RESERVED_NAMES = frozenset({"_global", "_system", "_admin", "_root"})

# Valid entity ID pattern: alphanumeric with hyphens and underscores
# Must start with alphanumeric, no path traversal characters
VALID_ID_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")


class InvalidEntityIdError(ValueError):
    """Raised when an entity ID is invalid or potentially malicious."""

    pass


def validate_entity_id(entity_id: str, entity_type: str) -> str:
    """Validate an entity ID to prevent path traversal attacks.

    Args:
        entity_id: The ID to validate (tenant_id, policy_id, app_id)
        entity_type: Type of entity for error messages ("tenant", "policy", "app")

    Returns:
        The validated entity_id (unchanged if valid)

    Raises:
        InvalidEntityIdError: If the ID is invalid or potentially malicious
    """
    # Check for None or empty
    if not entity_id or not entity_id.strip():
        raise InvalidEntityIdError(f"Invalid {entity_type} ID: ID cannot be empty")

    # Strip whitespace
    entity_id = entity_id.strip()

    # Check for null bytes
    if "\x00" in entity_id:
        raise InvalidEntityIdError(
            f"Invalid {entity_type} ID '{entity_id}': null bytes not allowed"
        )

    # Check for path traversal patterns
    if ".." in entity_id or "/" in entity_id or "\\" in entity_id:
        raise InvalidEntityIdError(
            f"Invalid {entity_type} ID '{entity_id}': path traversal characters not allowed"
        )

    # Check for hidden directories (starting with .)
    if entity_id.startswith("."):
        raise InvalidEntityIdError(f"Invalid {entity_type} ID '{entity_id}': cannot start with '.'")

    # Check for reserved names
    if entity_id.lower() in RESERVED_NAMES:
        raise InvalidEntityIdError(
            f"Invalid {entity_type} ID '{entity_id}': '{entity_id}' is a reserved name"
        )

    # Check against valid pattern
    if not VALID_ID_PATTERN.match(entity_id):
        raise InvalidEntityIdError(
            f"Invalid {entity_type} ID '{entity_id}': "
            f"IDs must be alphanumeric with hyphens/underscores only (e.g., 'my-{entity_type}')"
        )

    return entity_id


class YamlTenantRepository:
    """YAML-based repository for Tenant persistence.

    Stores tenants in:
        {base_path}/{tenant_id}/tenant.yaml
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize repository.

        Args:
            base_path: Base directory for tenant storage
        """
        self.base_path = Path(base_path)

    def _tenant_path(self, tenant_id: str) -> Path:
        """Get path to tenant.yaml for a tenant."""
        # Validate to prevent path traversal
        validate_entity_id(tenant_id, "tenant")
        return self.base_path / tenant_id / "tenant.yaml"

    def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID.

        Args:
            tenant_id: Tenant identifier (validated for security)

        Returns:
            Tenant object or None if not found

        Raises:
            InvalidEntityIdError: If tenant_id contains path traversal characters
        """
        path = self._tenant_path(tenant_id)
        if not path.exists():
            return None

        try:
            import yaml
        except ImportError:
            logger.warning("yaml_not_available", extra={"message": "PyYAML not installed"})
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.warning("yaml_read_error", extra={"path": str(path), "error": str(e)})
            return None

        if not data or "tenant" not in data:
            return None

        return self._parse_tenant(data["tenant"])

    def _parse_tenant(self, data: dict[str, Any]) -> Tenant | None:
        """Parse tenant data from YAML."""
        try:
            return Tenant(
                tenant_id=data["tenant_id"],
                name=data["name"],
                default_policy_id=data["default_policy_id"],
                partner_id=data.get("partner_id"),
                tier=data.get("tier", "free"),
                created_at=data.get("created_at"),
            )
        except (KeyError, ValueError) as e:
            logger.warning("tenant_parse_error", extra={"error": str(e)})
            return None

    def save_tenant(self, tenant: Tenant) -> None:
        """Save a tenant to storage.

        Args:
            tenant: Tenant object to save

        Raises:
            InvalidEntityIdError: If tenant_id contains path traversal characters
        """
        # Validate tenant_id before any file operations
        validate_entity_id(tenant.tenant_id, "tenant")

        try:
            import yaml
        except ImportError:
            logger.error("yaml_not_available", extra={"message": "PyYAML not installed"})
            return

        path = self._tenant_path(tenant.tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        tenant_data: dict[str, Any] = {
            "tenant_id": tenant.tenant_id,
            "name": tenant.name,
            "default_policy_id": tenant.default_policy_id,
            "tier": tenant.tier,
            "created_at": tenant.created_at or datetime.now(timezone.utc).isoformat(),
        }

        if tenant.partner_id:
            tenant_data["partner_id"] = tenant.partner_id

        data: dict[str, Any] = {
            "version": SCHEMA_VERSION,
            "tenant": tenant_data,
        }

        with open(path, "w", encoding="utf-8") as f:
            f.write("# RAXE Tenant Configuration\n")
            f.write(f"# Tenant ID: {tenant.tenant_id}\n\n")
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info("tenant_saved", extra={"tenant_id": tenant.tenant_id, "path": str(path)})

    def delete_tenant(self, tenant_id: str) -> bool:
        """Delete a tenant from storage.

        Args:
            tenant_id: Tenant identifier to delete

        Returns:
            True if deleted, False if not found

        Raises:
            InvalidEntityIdError: If tenant_id contains path traversal characters
        """
        import shutil

        # Validate to prevent path traversal
        validate_entity_id(tenant_id, "tenant")
        tenant_dir = self.base_path / tenant_id
        if not tenant_dir.exists():
            return False

        shutil.rmtree(tenant_dir)
        logger.info("tenant_deleted", extra={"tenant_id": tenant_id})
        return True

    def list_tenants(self) -> list[Tenant]:
        """List all tenants."""
        if not self.base_path.exists():
            return []

        tenants: list[Tenant] = []
        for tenant_dir in self.base_path.iterdir():
            if tenant_dir.is_dir() and tenant_dir.name != GLOBAL_TENANT_DIR:
                tenant = self.get_tenant(tenant_dir.name)
                if tenant:
                    tenants.append(tenant)

        return tenants

    def tenant_exists(self, tenant_id: str) -> bool:
        """Check if a tenant exists."""
        return self._tenant_path(tenant_id).exists()


class YamlPolicyRepository:
    """YAML-based repository for TenantPolicy persistence.

    Stores policies in:
        {base_path}/{tenant_id}/policies/{policy_id}.yaml
        {base_path}/_global/policies/{policy_id}.yaml  (for tenant_id=None)
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize repository.

        Args:
            base_path: Base directory for tenant storage
        """
        self.base_path = Path(base_path)

    def _policy_path(self, policy_id: str, tenant_id: str | None) -> Path:
        """Get path to policy YAML file.

        Args:
            policy_id: Policy identifier (validated)
            tenant_id: Tenant identifier or None for global (validated)

        Returns:
            Path to the policy YAML file

        Raises:
            InvalidEntityIdError: If any ID contains path traversal characters
        """
        # Validate IDs to prevent path traversal
        validate_entity_id(policy_id, "policy")
        if tenant_id is not None:
            validate_entity_id(tenant_id, "tenant")

        tenant_dir = tenant_id if tenant_id else GLOBAL_TENANT_DIR
        return self.base_path / tenant_dir / "policies" / f"{policy_id}.yaml"

    def get_policy(self, policy_id: str, tenant_id: str | None = None) -> TenantPolicy | None:
        """Get a policy by ID.

        Args:
            policy_id: Policy identifier
            tenant_id: Tenant identifier or None for global policies

        Returns:
            TenantPolicy object or None if not found

        Raises:
            InvalidEntityIdError: If any ID contains path traversal characters
        """
        path = self._policy_path(policy_id, tenant_id)
        if not path.exists():
            return None

        try:
            import yaml
        except ImportError:
            logger.warning("yaml_not_available", extra={"message": "PyYAML not installed"})
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.warning("yaml_read_error", extra={"path": str(path), "error": str(e)})
            return None

        if not data or "policy" not in data:
            return None

        return self._parse_policy(data["policy"])

    def _parse_policy(self, data: dict[str, Any]) -> TenantPolicy | None:
        """Parse policy data from YAML."""
        try:
            mode = PolicyMode(data["mode"])
            return TenantPolicy(
                policy_id=data["policy_id"],
                name=data["name"],
                tenant_id=data.get("tenant_id"),  # Can be None
                mode=mode,
                blocking_enabled=data.get("blocking_enabled", True),
                block_severity_threshold=data.get("block_severity_threshold", "HIGH"),
                block_confidence_threshold=data.get("block_confidence_threshold", 0.85),
                l2_enabled=data.get("l2_enabled", True),
                l2_threat_threshold=data.get("l2_threat_threshold", 0.35),
                telemetry_detail=data.get("telemetry_detail", "standard"),
                version=data.get("version", 1),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
            )
        except (KeyError, ValueError) as e:
            logger.warning("policy_parse_error", extra={"error": str(e)})
            return None

    def save_policy(self, policy: TenantPolicy) -> None:
        """Save a policy to storage."""
        try:
            import yaml
        except ImportError:
            logger.error("yaml_not_available", extra={"message": "PyYAML not installed"})
            return

        path = self._policy_path(policy.policy_id, policy.tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now(timezone.utc).isoformat()
        data: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "policy": {
                "policy_id": policy.policy_id,
                "name": policy.name,
                "mode": policy.mode.value,
                "blocking_enabled": policy.blocking_enabled,
                "block_severity_threshold": policy.block_severity_threshold,
                "block_confidence_threshold": policy.block_confidence_threshold,
                "l2_enabled": policy.l2_enabled,
                "l2_threat_threshold": policy.l2_threat_threshold,
                "telemetry_detail": policy.telemetry_detail,
                "version": policy.version,
                "created_at": policy.created_at or now,
                "updated_at": now,
            },
        }

        if policy.tenant_id is not None:
            data["policy"]["tenant_id"] = policy.tenant_id

        with open(path, "w", encoding="utf-8") as f:
            f.write("# RAXE Policy Configuration\n")
            f.write(f"# Policy ID: {policy.policy_id}\n\n")
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info(
            "policy_saved",
            extra={"policy_id": policy.policy_id, "tenant_id": policy.tenant_id, "path": str(path)},
        )

    def delete_policy(self, policy_id: str, tenant_id: str | None = None) -> bool:
        """Delete a policy from storage."""
        path = self._policy_path(policy_id, tenant_id)
        if not path.exists():
            return False

        path.unlink()
        logger.info("policy_deleted", extra={"policy_id": policy_id, "tenant_id": tenant_id})
        return True

    def list_policies(self, tenant_id: str | None = None) -> list[TenantPolicy]:
        """List policies for a tenant (or all if tenant_id is None)."""
        policies: list[TenantPolicy] = []

        if tenant_id is not None:
            # List policies for specific tenant
            policies_dir = self.base_path / tenant_id / "policies"
            if policies_dir.exists():
                for policy_file in policies_dir.glob("*.yaml"):
                    policy = self.get_policy(policy_file.stem, tenant_id)
                    if policy:
                        policies.append(policy)
        else:
            # List all policies across all tenants
            if self.base_path.exists():
                for tenant_dir in self.base_path.iterdir():
                    if tenant_dir.is_dir():
                        tid = None if tenant_dir.name == GLOBAL_TENANT_DIR else tenant_dir.name
                        policies_dir = tenant_dir / "policies"
                        if policies_dir.exists():
                            for policy_file in policies_dir.glob("*.yaml"):
                                policy = self.get_policy(policy_file.stem, tid)
                                if policy:
                                    policies.append(policy)

        return policies

    def get_all_policies_as_registry(self) -> dict[str, TenantPolicy]:
        """Get all policies as lookup dictionary."""
        all_policies = self.list_policies(tenant_id=None)
        return {p.policy_id: p for p in all_policies}


class YamlAppRepository:
    """YAML-based repository for App persistence.

    Stores apps in:
        {base_path}/{tenant_id}/apps/{app_id}.yaml
    """

    def __init__(self, base_path: Path) -> None:
        """Initialize repository.

        Args:
            base_path: Base directory for tenant storage
        """
        self.base_path = Path(base_path)

    def _app_path(self, app_id: str, tenant_id: str) -> Path:
        """Get path to app YAML file.

        Args:
            app_id: App identifier (validated)
            tenant_id: Tenant identifier (validated)

        Returns:
            Path to the app YAML file

        Raises:
            InvalidEntityIdError: If any ID contains path traversal characters
        """
        # Validate IDs to prevent path traversal
        validate_entity_id(app_id, "app")
        validate_entity_id(tenant_id, "tenant")
        return self.base_path / tenant_id / "apps" / f"{app_id}.yaml"

    def get_app(self, app_id: str, tenant_id: str) -> App | None:
        """Get an app by ID.

        Args:
            app_id: App identifier
            tenant_id: Tenant identifier

        Returns:
            App object or None if not found

        Raises:
            InvalidEntityIdError: If any ID contains path traversal characters
        """
        path = self._app_path(app_id, tenant_id)
        if not path.exists():
            return None

        try:
            import yaml
        except ImportError:
            logger.warning("yaml_not_available", extra={"message": "PyYAML not installed"})
            return None

        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except (yaml.YAMLError, OSError) as e:
            logger.warning("yaml_read_error", extra={"path": str(path), "error": str(e)})
            return None

        if not data or "app" not in data:
            return None

        return self._parse_app(data["app"])

    def _parse_app(self, data: dict[str, Any]) -> App | None:
        """Parse app data from YAML."""
        try:
            return App(
                app_id=data["app_id"],
                tenant_id=data["tenant_id"],
                name=data["name"],
                default_policy_id=data.get("default_policy_id"),
                created_at=data.get("created_at"),
            )
        except (KeyError, ValueError) as e:
            logger.warning("app_parse_error", extra={"error": str(e)})
            return None

    def save_app(self, app: App) -> None:
        """Save an app to storage."""
        try:
            import yaml
        except ImportError:
            logger.error("yaml_not_available", extra={"message": "PyYAML not installed"})
            return

        path = self._app_path(app.app_id, app.tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, Any] = {
            "version": SCHEMA_VERSION,
            "app": {
                "app_id": app.app_id,
                "tenant_id": app.tenant_id,
                "name": app.name,
                "created_at": app.created_at or datetime.now(timezone.utc).isoformat(),
            },
        }

        if app.default_policy_id is not None:
            data["app"]["default_policy_id"] = app.default_policy_id

        with open(path, "w", encoding="utf-8") as f:
            f.write("# RAXE App Configuration\n")
            f.write(f"# App ID: {app.app_id}\n\n")
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

        logger.info(
            "app_saved",
            extra={"app_id": app.app_id, "tenant_id": app.tenant_id, "path": str(path)},
        )

    def delete_app(self, app_id: str, tenant_id: str) -> bool:
        """Delete an app from storage."""
        path = self._app_path(app_id, tenant_id)
        if not path.exists():
            return False

        path.unlink()
        logger.info("app_deleted", extra={"app_id": app_id, "tenant_id": tenant_id})
        return True

    def list_apps(self, tenant_id: str) -> list[App]:
        """List all apps for a tenant."""
        apps_dir = self.base_path / tenant_id / "apps"
        if not apps_dir.exists():
            return []

        apps: list[App] = []
        for app_file in apps_dir.glob("*.yaml"):
            app = self.get_app(app_file.stem, tenant_id)
            if app:
                apps.append(app)

        return apps


class CachedPolicyRepository:
    """Caching wrapper for YamlPolicyRepository.

    Provides O(1) policy lookups with LRU cache eviction.
    Reduces file I/O for repeated policy lookups.

    Thread Safety:
        This implementation is NOT thread-safe. For multi-threaded
        use, wrap operations with appropriate locking.
    """

    def __init__(
        self,
        base_repo: YamlPolicyRepository,
        cache_maxsize: int = 128,
    ) -> None:
        """Initialize cached repository.

        Args:
            base_repo: Underlying YAML repository for storage
            cache_maxsize: Maximum number of policies to cache (default 128)
        """
        self._base_repo = base_repo
        self.cache = PolicyCache(maxsize=cache_maxsize)

    def _cache_key(self, policy_id: str, tenant_id: str | None) -> str:
        """Generate cache key for a policy.

        Args:
            policy_id: Policy identifier
            tenant_id: Tenant identifier or None for global

        Returns:
            Cache key string
        """
        return f"{policy_id}:{tenant_id}"

    def get_policy(self, policy_id: str, tenant_id: str | None = None) -> TenantPolicy | None:
        """Get a policy, using cache if available.

        Args:
            policy_id: Policy identifier
            tenant_id: Tenant identifier or None for global policies

        Returns:
            TenantPolicy object or None if not found
        """
        cache_key = self._cache_key(policy_id, tenant_id)

        # Try cache first
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # Cache miss - load from base repo
        policy = self._base_repo.get_policy(policy_id, tenant_id)
        if policy is not None:
            self.cache.set(cache_key, policy)

        return policy

    def save_policy(self, policy: TenantPolicy) -> None:
        """Save a policy and invalidate cache entry.

        Args:
            policy: TenantPolicy to save
        """
        # Save to base repo
        self._base_repo.save_policy(policy)

        # Invalidate cache entry (will be re-cached on next get)
        cache_key = self._cache_key(policy.policy_id, policy.tenant_id)
        self.cache.delete(cache_key)

    def delete_policy(self, policy_id: str, tenant_id: str | None = None) -> bool:
        """Delete a policy and invalidate cache entry.

        Args:
            policy_id: Policy identifier
            tenant_id: Tenant identifier or None for global

        Returns:
            True if deleted, False if not found
        """
        # Delete from base repo
        result = self._base_repo.delete_policy(policy_id, tenant_id)

        # Invalidate cache entry
        cache_key = self._cache_key(policy_id, tenant_id)
        self.cache.delete(cache_key)

        return result

    def list_policies(self, tenant_id: str | None = None) -> list[TenantPolicy]:
        """List policies (delegates to base repo).

        Args:
            tenant_id: Tenant identifier or None for all

        Returns:
            List of policies
        """
        return self._base_repo.list_policies(tenant_id)

    def cache_stats(self) -> dict[str, float]:
        """Get cache statistics.

        Returns:
            Dictionary with hits, misses, hit_rate, size, maxsize
        """
        return self.cache.stats()

    def clear_cache(self) -> None:
        """Clear all cached policies."""
        self.cache.clear()
