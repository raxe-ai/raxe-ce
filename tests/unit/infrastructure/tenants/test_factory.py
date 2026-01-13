"""Tests for tenant repository factory.

Tests cover:
- RepositoryFactory class
- Convenience functions (get_tenant_repo, get_policy_repo, get_app_repo)
- Base path resolution
- Cached repository creation
"""

from raxe.infrastructure.tenants.factory import (
    RepositoryFactory,
    get_app_repo,
    get_policy_repo,
    get_repository_factory,
    get_tenant_repo,
)


class TestRepositoryFactory:
    """Tests for RepositoryFactory class."""

    def test_init_with_default_base_path(self):
        """Factory without base_path uses default on access."""
        factory = RepositoryFactory()
        # base_path is lazily resolved
        assert factory._resolved_base_path is None
        # Access triggers resolution
        path = factory.base_path
        assert path is not None
        assert factory._resolved_base_path is not None

    def test_init_with_custom_base_path(self, tmp_path):
        """Factory with custom base_path uses it directly."""
        factory = RepositoryFactory(base_path=tmp_path)
        assert factory.base_path == tmp_path

    def test_base_path_respects_env_var(self, tmp_path, monkeypatch):
        """Factory respects RAXE_TENANTS_DIR environment variable."""
        monkeypatch.setenv("RAXE_TENANTS_DIR", str(tmp_path))
        factory = RepositoryFactory()
        assert factory.base_path == tmp_path

    def test_get_tenant_repo_returns_correct_type(self, tmp_path):
        """get_tenant_repo returns YamlTenantRepository."""
        from raxe.infrastructure.tenants.yaml_repository import YamlTenantRepository

        factory = RepositoryFactory(base_path=tmp_path)
        repo = factory.get_tenant_repo()
        assert isinstance(repo, YamlTenantRepository)

    def test_get_policy_repo_returns_correct_type(self, tmp_path):
        """get_policy_repo returns YamlPolicyRepository by default."""
        from raxe.infrastructure.tenants.yaml_repository import YamlPolicyRepository

        factory = RepositoryFactory(base_path=tmp_path)
        repo = factory.get_policy_repo()
        assert isinstance(repo, YamlPolicyRepository)

    def test_get_policy_repo_cached_returns_cached_type(self, tmp_path):
        """get_policy_repo(cached=True) returns CachedPolicyRepository."""
        from raxe.infrastructure.tenants.yaml_repository import CachedPolicyRepository

        factory = RepositoryFactory(base_path=tmp_path)
        repo = factory.get_policy_repo(cached=True)
        assert isinstance(repo, CachedPolicyRepository)

    def test_get_policy_repo_cached_with_custom_maxsize(self, tmp_path):
        """get_policy_repo cached respects cache_maxsize parameter."""
        factory = RepositoryFactory(base_path=tmp_path)
        repo = factory.get_policy_repo(cached=True, cache_maxsize=64)
        # Verify cache was created with correct size
        assert repo.cache.maxsize == 64

    def test_get_app_repo_returns_correct_type(self, tmp_path):
        """get_app_repo returns YamlAppRepository."""
        from raxe.infrastructure.tenants.yaml_repository import YamlAppRepository

        factory = RepositoryFactory(base_path=tmp_path)
        repo = factory.get_app_repo()
        assert isinstance(repo, YamlAppRepository)

    def test_get_all_repos_returns_tuple_of_three(self, tmp_path):
        """get_all_repos returns tuple of all three repositories."""
        from raxe.infrastructure.tenants.yaml_repository import (
            YamlAppRepository,
            YamlPolicyRepository,
            YamlTenantRepository,
        )

        factory = RepositoryFactory(base_path=tmp_path)
        tenant_repo, policy_repo, app_repo = factory.get_all_repos()

        assert isinstance(tenant_repo, YamlTenantRepository)
        assert isinstance(policy_repo, YamlPolicyRepository)
        assert isinstance(app_repo, YamlAppRepository)

    def test_repos_use_same_base_path(self, tmp_path):
        """All repos from same factory use same base_path."""
        factory = RepositoryFactory(base_path=tmp_path)
        tenant_repo, policy_repo, app_repo = factory.get_all_repos()

        assert tenant_repo.base_path == tmp_path
        assert policy_repo.base_path == tmp_path
        assert app_repo.base_path == tmp_path


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_repository_factory_creates_factory(self, tmp_path):
        """get_repository_factory returns RepositoryFactory."""
        factory = get_repository_factory(base_path=tmp_path)
        assert isinstance(factory, RepositoryFactory)
        assert factory.base_path == tmp_path

    def test_get_repository_factory_without_path_uses_default(self):
        """get_repository_factory without path uses default."""
        factory = get_repository_factory()
        # Should not raise, should use default path
        assert factory.base_path is not None

    def test_get_tenant_repo_returns_repository(self, tmp_path):
        """get_tenant_repo returns YamlTenantRepository."""
        from raxe.infrastructure.tenants.yaml_repository import YamlTenantRepository

        repo = get_tenant_repo(base_path=tmp_path)
        assert isinstance(repo, YamlTenantRepository)
        assert repo.base_path == tmp_path

    def test_get_policy_repo_returns_repository(self, tmp_path):
        """get_policy_repo returns YamlPolicyRepository."""
        from raxe.infrastructure.tenants.yaml_repository import YamlPolicyRepository

        repo = get_policy_repo(base_path=tmp_path)
        assert isinstance(repo, YamlPolicyRepository)
        assert repo.base_path == tmp_path

    def test_get_policy_repo_cached(self, tmp_path):
        """get_policy_repo with cached=True returns CachedPolicyRepository."""
        from raxe.infrastructure.tenants.yaml_repository import CachedPolicyRepository

        repo = get_policy_repo(base_path=tmp_path, cached=True)
        assert isinstance(repo, CachedPolicyRepository)

    def test_get_app_repo_returns_repository(self, tmp_path):
        """get_app_repo returns YamlAppRepository."""
        from raxe.infrastructure.tenants.yaml_repository import YamlAppRepository

        repo = get_app_repo(base_path=tmp_path)
        assert isinstance(repo, YamlAppRepository)
        assert repo.base_path == tmp_path


class TestFactoryIntegration:
    """Integration tests for factory with real operations."""

    def test_factory_repos_can_perform_operations(self, tmp_path):
        """Repos from factory can perform real CRUD operations."""
        from datetime import datetime, timezone

        from raxe.domain.tenants.models import Tenant

        factory = RepositoryFactory(base_path=tmp_path)
        tenant_repo = factory.get_tenant_repo()

        # Create tenant
        tenant = Tenant(
            tenant_id="test",
            name="Test Tenant",
            default_policy_id="balanced",
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        tenant_repo.save_tenant(tenant)

        # Retrieve tenant
        loaded = tenant_repo.get_tenant("test")
        assert loaded is not None
        assert loaded.name == "Test Tenant"

        # List tenants
        all_tenants = tenant_repo.list_tenants()
        assert len(all_tenants) == 1

        # Delete tenant
        tenant_repo.delete_tenant("test")
        assert tenant_repo.get_tenant("test") is None

    def test_convenience_functions_work_with_env_var(self, tmp_path, monkeypatch):
        """Convenience functions respect RAXE_TENANTS_DIR."""
        monkeypatch.setenv("RAXE_TENANTS_DIR", str(tmp_path))

        # All convenience functions should use the env var path
        tenant_repo = get_tenant_repo()
        policy_repo = get_policy_repo()
        app_repo = get_app_repo()

        assert tenant_repo.base_path == tmp_path
        assert policy_repo.base_path == tmp_path
        assert app_repo.base_path == tmp_path

    def test_multiple_factory_calls_are_independent(self, tmp_path):
        """Each factory call creates independent instance."""
        factory1 = get_repository_factory(base_path=tmp_path)
        factory2 = get_repository_factory(base_path=tmp_path)

        # Different instances
        assert factory1 is not factory2

        # But same configuration
        assert factory1.base_path == factory2.base_path
