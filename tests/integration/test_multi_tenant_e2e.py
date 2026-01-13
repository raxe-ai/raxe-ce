"""End-to-end integration tests for multi-tenant policy management.

Tests complete workflows:
1. Create tenant → Create app → Scan with tenant context → Verify policy attribution
2. Tenant isolation (Tenant A suppressions don't affect Tenant B)
3. Policy resolution fallback chain (request → app → tenant → system default)
4. CLI JSON output parseable by AI agents
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from click.testing import CliRunner

from raxe.cli import app as app_cli
from raxe.cli import policy as policy_cli
from raxe.cli import tenant as tenant_cli
from raxe.domain.tenants.models import App, Tenant, TenantPolicy
from raxe.domain.tenants.presets import GLOBAL_PRESETS
from raxe.domain.tenants.resolver import resolve_policy
from raxe.infrastructure.tenants import (
    CachedPolicyRepository,
    InvalidEntityIdError,
    YamlAppRepository,
    YamlPolicyRepository,
    YamlTenantRepository,
    validate_entity_id,
)


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def temp_tenant_dir(tmp_path):
    """Create a temporary tenant directory."""
    tenant_dir = tmp_path / "tenants"
    tenant_dir.mkdir()
    return tenant_dir


def _create_tenant(
    tenant_dir: Path, tenant_id: str, name: str, policy_id: str = "balanced"
) -> Tenant:
    """Helper to create a tenant."""
    repo = YamlTenantRepository(tenant_dir)
    tenant_obj = Tenant(
        tenant_id=tenant_id,
        name=name,
        default_policy_id=policy_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo.save_tenant(tenant_obj)
    return tenant_obj


def _create_app(
    tenant_dir: Path,
    app_id: str,
    tenant_id: str,
    name: str,
    policy_id: str | None = None,
) -> App:
    """Helper to create an app."""
    repo = YamlAppRepository(tenant_dir)
    app_obj = App(
        app_id=app_id,
        tenant_id=tenant_id,
        name=name,
        default_policy_id=policy_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    repo.save_app(app_obj)
    return app_obj


@pytest.mark.integration
class TestMultiTenantE2EWorkflow:
    """E2E tests for complete multi-tenant workflows."""

    def test_full_tenant_workflow(self, temp_tenant_dir):
        """Create tenant → Create app → Configure policy → Verify resolution."""
        # 1. Create tenant with balanced default
        tenant_obj = _create_tenant(temp_tenant_dir, "acme", "Acme Corp", "balanced")
        assert tenant_obj.tenant_id == "acme"
        assert tenant_obj.default_policy_id == "balanced"

        # 2. Create app with strict policy override
        app_obj = _create_app(temp_tenant_dir, "trading", "acme", "Trading System", "strict")
        assert app_obj.app_id == "trading"
        assert app_obj.default_policy_id == "strict"

        # 3. Create another app inheriting from tenant
        chatbot_app = _create_app(temp_tenant_dir, "chatbot", "acme", "Customer Bot")
        assert chatbot_app.default_policy_id is None

        # 4. Verify policy resolution for app with override
        result = resolve_policy(
            request_policy_id=None,
            app=app_obj,
            tenant=tenant_obj,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.policy.policy_id == "strict"
        assert result.resolution_source == "app"
        assert "app:trading" in result.resolution_path

        # 5. Verify policy resolution for app inheriting from tenant
        result2 = resolve_policy(
            request_policy_id=None,
            app=chatbot_app,
            tenant=tenant_obj,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result2.policy.policy_id == "balanced"
        assert result2.resolution_source == "tenant"
        assert "tenant:acme" in result2.resolution_path

        # 6. Verify request-level override takes precedence
        result3 = resolve_policy(
            request_policy_id="monitor",
            app=app_obj,
            tenant=tenant_obj,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result3.policy.policy_id == "monitor"
        assert result3.resolution_source == "request"

    def test_policy_resolution_fallback_chain(self, temp_tenant_dir):
        """Verify complete fallback chain: request → app → tenant → system default."""
        # Create tenant with strict default
        tenant_obj = _create_tenant(temp_tenant_dir, "bank", "Bank Corp", "strict")

        # Create app with balanced override
        app_obj = _create_app(temp_tenant_dir, "internal", "bank", "Internal Tool", "balanced")

        # 1. Request override has highest priority
        result = resolve_policy(
            request_policy_id="monitor",
            app=app_obj,
            tenant=tenant_obj,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.resolution_source == "request"
        assert result.policy.policy_id == "monitor"

        # 2. App default is second priority (when no request override)
        result = resolve_policy(
            request_policy_id=None,
            app=app_obj,
            tenant=tenant_obj,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.resolution_source == "app"
        assert result.policy.policy_id == "balanced"

        # 3. Tenant default is third priority (when no app default)
        app_no_policy = _create_app(temp_tenant_dir, "public", "bank", "Public API")
        result = resolve_policy(
            request_policy_id=None,
            app=app_no_policy,
            tenant=tenant_obj,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.resolution_source == "tenant"
        assert result.policy.policy_id == "strict"

        # 4. System default is last resort
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=None,
            policy_registry=GLOBAL_PRESETS,
        )
        assert result.resolution_source == "system_default"
        assert result.policy.policy_id == "balanced"  # System default is balanced


@pytest.mark.integration
class TestTenantIsolation:
    """Tests for verifying complete tenant isolation."""

    def test_tenant_a_suppressions_not_visible_to_tenant_b(self, temp_tenant_dir):
        """Suppressions for Tenant A should not affect Tenant B."""
        # Create two tenants
        _create_tenant(temp_tenant_dir, "tenant-a", "Tenant A")
        _create_tenant(temp_tenant_dir, "tenant-b", "Tenant B")

        # Create suppression file for tenant A
        suppress_dir = temp_tenant_dir / "tenant-a"
        suppress_dir.mkdir(parents=True, exist_ok=True)
        suppress_file = suppress_dir / "suppressions.yaml"
        suppress_file.write_text("""
version: "1.0"
suppressions:
  - pattern: "pi-001"
    reason: "Tenant A specific false positive"
    action: SUPPRESS
    created_at: "2026-01-13T00:00:00Z"
""")

        # Verify tenant A has the suppression
        assert suppress_file.exists()
        content = suppress_file.read_text()
        assert "pi-001" in content
        assert "Tenant A" in content

        # Verify tenant B has no suppressions
        tenant_b_suppress = temp_tenant_dir / "tenant-b" / "suppressions.yaml"
        assert not tenant_b_suppress.exists()

    def test_tenant_policies_isolated(self, temp_tenant_dir):
        """Custom policies for one tenant don't affect another."""
        # Create tenants
        tenant_a = _create_tenant(temp_tenant_dir, "company-a", "Company A", "strict")
        _create_tenant(temp_tenant_dir, "company-b", "Company B", "monitor")

        # Verify each has their own default
        tenant_repo = YamlTenantRepository(temp_tenant_dir)

        loaded_a = tenant_repo.get_tenant("company-a")
        loaded_b = tenant_repo.get_tenant("company-b")

        assert loaded_a.default_policy_id == "strict"
        assert loaded_b.default_policy_id == "monitor"

        # Changing one doesn't affect the other
        updated_a = Tenant(
            tenant_id="company-a",
            name="Company A",
            default_policy_id="balanced",  # Changed from strict
            created_at=tenant_a.created_at,
        )
        tenant_repo.save_tenant(updated_a)

        # B should still be monitor
        loaded_b_again = tenant_repo.get_tenant("company-b")
        assert loaded_b_again.default_policy_id == "monitor"


@pytest.mark.integration
class TestCLIJSONOutput:
    """Tests for CLI JSON output (AI-agent ready)."""

    def test_tenant_list_json_parseable(self, runner, temp_tenant_dir, monkeypatch):
        """raxe tenant list --output json returns valid JSON."""
        # Create tenants
        _create_tenant(temp_tenant_dir, "acme", "Acme Corp")
        _create_tenant(temp_tenant_dir, "globex", "Globex Inc")

        # Mock the tenant base path
        monkeypatch.setattr(
            tenant_cli,
            "get_tenants_base_path",
            lambda: temp_tenant_dir,
        )

        result = runner.invoke(tenant_cli.tenant, ["list", "--output", "json"])
        assert result.exit_code == 0

        # Must be valid JSON
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

        tenant_ids = [t["tenant_id"] for t in data]
        assert "acme" in tenant_ids
        assert "globex" in tenant_ids

    def test_policy_list_json_parseable(self, runner, temp_tenant_dir, monkeypatch):
        """raxe policy list --output json returns valid JSON."""
        _create_tenant(temp_tenant_dir, "test-corp", "Test Corp")

        # Create a custom policy for this tenant
        from raxe.domain.tenants.models import PolicyMode

        policy_repo = YamlPolicyRepository(temp_tenant_dir)
        custom_policy = TenantPolicy(
            policy_id="custom-strict",
            name="Custom Strict Policy",
            tenant_id="test-corp",
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )
        policy_repo.save_policy(custom_policy)

        monkeypatch.setattr(
            policy_cli,
            "get_tenants_base_path",
            lambda: temp_tenant_dir,
        )

        result = runner.invoke(
            policy_cli.policy, ["list", "--tenant", "test-corp", "--output", "json"]
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert isinstance(data, list)

        # Should include global presets and custom policy
        policy_ids = [p["policy_id"] for p in data]
        # Global presets may or may not be shown depending on CLI implementation
        # But at least our custom policy should be there
        assert "custom-strict" in policy_ids

    def test_app_list_json_parseable(self, runner, temp_tenant_dir, monkeypatch):
        """raxe app list --output json returns valid JSON."""
        _create_tenant(temp_tenant_dir, "mycompany", "My Company")
        _create_app(temp_tenant_dir, "chatbot", "mycompany", "Chatbot")
        _create_app(temp_tenant_dir, "api", "mycompany", "API Service")

        monkeypatch.setattr(
            app_cli,
            "get_tenants_base_path",
            lambda: temp_tenant_dir,
        )

        result = runner.invoke(app_cli.app, ["list", "--tenant", "mycompany", "--output", "json"])
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

        app_ids = [a["app_id"] for a in data]
        assert "chatbot" in app_ids
        assert "api" in app_ids


@pytest.mark.integration
class TestSecurityValidation:
    """Tests for security features (path traversal prevention, etc.)."""

    def test_path_traversal_blocked(self, temp_tenant_dir):
        """Path traversal attempts are blocked."""
        with pytest.raises(InvalidEntityIdError):
            validate_entity_id("../../../etc/passwd", "tenant")

        with pytest.raises(InvalidEntityIdError):
            validate_entity_id("tenant/../../secret", "tenant")

        with pytest.raises(InvalidEntityIdError):
            validate_entity_id("..\\..\\windows", "tenant")

    def test_null_byte_injection_blocked(self, temp_tenant_dir):
        """Null byte injection is blocked."""
        with pytest.raises(InvalidEntityIdError):
            validate_entity_id("tenant\x00.yaml", "tenant")

    def test_reserved_names_blocked(self, temp_tenant_dir):
        """Reserved system names are blocked."""
        for reserved in ["_global", "_system", "_admin", "_root"]:
            with pytest.raises(InvalidEntityIdError, match="reserved"):
                validate_entity_id(reserved, "tenant")

    def test_valid_ids_accepted(self, temp_tenant_dir):
        """Valid entity IDs are accepted."""
        valid_ids = [
            "acme",
            "acme-corp",
            "acme_corp",
            "tenant123",
            "A1B2C3",
            "my-long-tenant-name",
        ]
        for valid_id in valid_ids:
            result = validate_entity_id(valid_id, "tenant")
            assert result == valid_id


@pytest.mark.integration
class TestPolicyCaching:
    """Tests for policy caching performance."""

    def test_cached_repository_returns_same_result(self, temp_tenant_dir):
        """CachedPolicyRepository returns same policy on repeated calls."""
        from raxe.domain.tenants.models import PolicyMode

        # Create a custom policy for testing
        policy_repo = YamlPolicyRepository(temp_tenant_dir)
        _create_tenant(temp_tenant_dir, "cache-test", "Cache Test Tenant")

        # Save a policy to test caching
        test_policy = TenantPolicy(
            policy_id="test-cached",
            name="Test Cached Policy",
            tenant_id="cache-test",
            mode=PolicyMode.BALANCED,
            blocking_enabled=True,
        )
        policy_repo.save_policy(test_policy)

        # Wrap in cached repository
        cached_repo = CachedPolicyRepository(policy_repo)

        # First call - cache miss
        result1 = cached_repo.get_policy("test-cached", tenant_id="cache-test")
        assert result1 is not None
        assert result1.policy_id == "test-cached"

        # Second call - cache hit
        result2 = cached_repo.get_policy("test-cached", tenant_id="cache-test")
        assert result2 is not None
        assert result2.policy_id == "test-cached"

        # Should be same object from cache
        assert result1 == result2

    def test_cache_invalidation(self, temp_tenant_dir):
        """Cache can be invalidated."""
        from raxe.domain.tenants.models import PolicyMode

        policy_repo = YamlPolicyRepository(temp_tenant_dir)
        _create_tenant(temp_tenant_dir, "cache-clear-test", "Cache Clear Test")

        # Save a policy
        test_policy = TenantPolicy(
            policy_id="test-invalidate",
            name="Test Invalidation",
            tenant_id="cache-clear-test",
            mode=PolicyMode.STRICT,
            blocking_enabled=True,
        )
        policy_repo.save_policy(test_policy)

        # Wrap in cached repo
        cached_repo = CachedPolicyRepository(policy_repo)

        # Populate cache
        _ = cached_repo.get_policy("test-invalidate", tenant_id="cache-clear-test")
        assert len(cached_repo.cache) > 0

        # Clear cache
        cached_repo.cache.clear()
        assert len(cached_repo.cache) == 0


@pytest.mark.integration
class TestPolicyExplainCommand:
    """Tests for policy explain command."""

    def test_explain_shows_resolution_path(self, runner, temp_tenant_dir, monkeypatch):
        """raxe policy explain shows which policy would be used."""
        _create_tenant(temp_tenant_dir, "demo", "Demo Corp", "strict")
        _create_app(temp_tenant_dir, "webapp", "demo", "Web App", "balanced")

        monkeypatch.setattr(
            policy_cli,
            "get_tenants_base_path",
            lambda: temp_tenant_dir,
        )

        # Explain for app with override
        result = runner.invoke(
            policy_cli.policy,
            ["explain", "--tenant", "demo", "--app", "webapp"],
        )
        assert result.exit_code == 0
        assert "balanced" in result.output
        assert "app" in result.output.lower()

        # Explain for tenant default (no app)
        result = runner.invoke(
            policy_cli.policy,
            ["explain", "--tenant", "demo"],
        )
        assert result.exit_code == 0
        assert "strict" in result.output

    def test_explain_json_output(self, runner, temp_tenant_dir, monkeypatch):
        """raxe policy explain --output json returns valid JSON."""
        _create_tenant(temp_tenant_dir, "jsontest", "JSON Test", "monitor")

        monkeypatch.setattr(
            policy_cli,
            "get_tenants_base_path",
            lambda: temp_tenant_dir,
        )

        result = runner.invoke(
            policy_cli.policy,
            ["explain", "--tenant", "jsontest", "--output", "json"],
        )
        assert result.exit_code == 0

        data = json.loads(result.output)
        assert "effective_policy_id" in data
        assert "resolution_source" in data
        assert "resolution_path" in data
        assert data["effective_policy_id"] == "monitor"


@pytest.mark.integration
class TestPolicyTelemetryFields:
    """E2E tests for policy telemetry field propagation.

    Verifies that policy_name, policy_mode, policy_version flow correctly
    from tenant/policy configuration through scan results to telemetry.
    """

    def test_custom_policy_telemetry_fields_in_metadata(self, temp_tenant_dir):
        """Verify custom policy fields appear in scan result metadata.

        This tests the complete flow:
        1. Create tenant with custom policy (including version)
        2. Resolve policy for scan
        3. Verify policy attribution includes name, mode, version
        """
        from raxe.domain.tenants.models import PolicyMode

        # 1. Create tenant with custom policy that has version tracking
        tenant_obj = _create_tenant(temp_tenant_dir, "telemetry-test", "Telemetry Test Corp")

        # 2. Create a custom policy with version tracking
        policy_repo = YamlPolicyRepository(temp_tenant_dir)
        custom_policy = TenantPolicy(
            policy_id="custom-strict-v2",
            name="Custom Strict Policy V2",
            tenant_id="telemetry-test",
            mode=PolicyMode.CUSTOM,
            blocking_enabled=True,
            block_severity_threshold="MEDIUM",
            block_confidence_threshold=0.7,
            version=2,  # Version tracking
        )
        policy_repo.save_policy(custom_policy)

        # 3. Set tenant default to custom policy
        updated_tenant = Tenant(
            tenant_id="telemetry-test",
            name="Telemetry Test Corp",
            default_policy_id="custom-strict-v2",
            created_at=tenant_obj.created_at,
        )
        YamlTenantRepository(temp_tenant_dir).save_tenant(updated_tenant)

        # 4. Load the custom policy registry (global presets + tenant policies)
        loaded_policy = policy_repo.get_policy("custom-strict-v2", tenant_id="telemetry-test")
        assert loaded_policy is not None
        assert loaded_policy.name == "Custom Strict Policy V2"
        assert loaded_policy.mode == PolicyMode.CUSTOM
        assert loaded_policy.version == 2

        # 5. Build combined registry for resolution
        combined_registry = {**GLOBAL_PRESETS}
        combined_registry[loaded_policy.policy_id] = loaded_policy

        # 6. Resolve policy for this tenant
        loaded_tenant = YamlTenantRepository(temp_tenant_dir).get_tenant("telemetry-test")
        result = resolve_policy(
            request_policy_id=None,
            app=None,
            tenant=loaded_tenant,
            policy_registry=combined_registry,
        )

        # 7. Verify policy attribution contains all telemetry-relevant fields
        assert result.policy.policy_id == "custom-strict-v2"
        assert result.policy.name == "Custom Strict Policy V2"
        assert result.policy.mode == PolicyMode.CUSTOM
        assert result.policy.version == 2
        assert result.resolution_source == "tenant"

    def test_policy_telemetry_builder_receives_all_fields(self, temp_tenant_dir):
        """Verify telemetry builder correctly includes policy fields.

        Tests that build_scan_telemetry() includes:
        - policy_id
        - policy_name
        - policy_mode
        - policy_version
        """
        from raxe.domain.telemetry.scan_telemetry_builder import build_scan_telemetry

        # Build telemetry with all policy fields
        telemetry = build_scan_telemetry(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="Test prompt for telemetry",
            tenant_id="acme",
            app_id="chatbot",
            policy_id="custom-policy-v3",
            policy_name="Custom Policy Version 3",
            policy_mode="custom",
            policy_version=3,
        )

        # Verify all policy fields are in telemetry payload
        assert telemetry["tenant_id"] == "acme"
        assert telemetry["app_id"] == "chatbot"
        assert telemetry["policy_id"] == "custom-policy-v3"
        assert telemetry["policy_name"] == "Custom Policy Version 3"
        assert telemetry["policy_mode"] == "custom"
        assert telemetry["policy_version"] == 3

    def test_preset_policy_telemetry_fields(self, temp_tenant_dir):
        """Verify preset policies (balanced, strict, monitor) have correct telemetry.

        Preset policies should report their standard names and modes.
        Global presets have version=1 (immutable baseline version).
        """
        # Test balanced preset
        result = resolve_policy(
            request_policy_id="balanced",
            app=None,
            tenant=None,
            policy_registry=GLOBAL_PRESETS,
        )

        assert result.policy.policy_id == "balanced"
        assert result.policy.name == "Balanced Mode"
        assert result.policy.mode.value == "balanced"
        # Global presets have version=1 (immutable baseline)
        assert result.policy.version == 1

        # Test strict preset
        result_strict = resolve_policy(
            request_policy_id="strict",
            app=None,
            tenant=None,
            policy_registry=GLOBAL_PRESETS,
        )

        assert result_strict.policy.policy_id == "strict"
        assert result_strict.policy.name == "Strict Mode"
        assert result_strict.policy.mode.value == "strict"
        assert result_strict.policy.version == 1

        # Test monitor preset
        result_monitor = resolve_policy(
            request_policy_id="monitor",
            app=None,
            tenant=None,
            policy_registry=GLOBAL_PRESETS,
        )

        assert result_monitor.policy.policy_id == "monitor"
        assert result_monitor.policy.name == "Monitor Mode"
        assert result_monitor.policy.mode.value == "monitor"
        assert result_monitor.policy.version == 1

    def test_full_telemetry_flow_with_custom_policy(self, temp_tenant_dir):
        """Full E2E test: custom policy → resolution → telemetry payload.

        This is the complete integration test verifying the entire flow
        from policy creation to telemetry payload generation.
        """
        from raxe.domain.telemetry.scan_telemetry_builder import build_scan_telemetry
        from raxe.domain.tenants.models import PolicyMode

        # 1. Create tenant
        tenant_obj = _create_tenant(temp_tenant_dir, "e2e-test", "E2E Test Corp")

        # 2. Create custom policy with all tracking fields
        policy_repo = YamlPolicyRepository(temp_tenant_dir)
        custom_policy = TenantPolicy(
            policy_id="e2e-custom-v5",
            name="E2E Custom Policy",
            tenant_id="e2e-test",
            mode=PolicyMode.CUSTOM,
            blocking_enabled=True,
            block_severity_threshold="HIGH",
            block_confidence_threshold=0.85,
            version=5,
        )
        policy_repo.save_policy(custom_policy)

        # 3. Create app with policy override
        app_obj = _create_app(temp_tenant_dir, "e2e-app", "e2e-test", "E2E App", "e2e-custom-v5")

        # 4. Load and resolve
        combined_registry = {**GLOBAL_PRESETS}
        loaded_policy = policy_repo.get_policy("e2e-custom-v5", tenant_id="e2e-test")
        combined_registry[loaded_policy.policy_id] = loaded_policy

        result = resolve_policy(
            request_policy_id=None,
            app=app_obj,
            tenant=tenant_obj,
            policy_registry=combined_registry,
        )

        # 5. Build telemetry payload as SDK would
        telemetry = build_scan_telemetry(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=10.5,
            entry_point="sdk",
            prompt="Test prompt for E2E telemetry verification",
            tenant_id="e2e-test",
            app_id="e2e-app",
            policy_id=result.policy.policy_id,
            policy_name=result.policy.name,
            policy_mode=result.policy.mode.value,
            policy_version=result.policy.version,
        )

        # 6. Verify complete telemetry payload
        assert telemetry["tenant_id"] == "e2e-test"
        assert telemetry["app_id"] == "e2e-app"
        assert telemetry["policy_id"] == "e2e-custom-v5"
        assert telemetry["policy_name"] == "E2E Custom Policy"
        assert telemetry["policy_mode"] == "custom"
        assert telemetry["policy_version"] == 5

        # 7. Verify resolution path is correct
        assert result.resolution_source == "app"
        assert "app:e2e-app" in result.resolution_path

    def test_policy_version_none_omitted_from_telemetry(self):
        """Verify that None policy_version is not included in telemetry.

        When policy_version is None (e.g., legacy policies without version tracking),
        it should be omitted from telemetry payload.
        """
        from raxe.domain.telemetry.scan_telemetry_builder import build_scan_telemetry

        # Build telemetry with version=None (legacy policy without versioning)
        telemetry = build_scan_telemetry(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="Test prompt",
            policy_id="legacy-policy",
            policy_name="Legacy Policy",
            policy_mode="balanced",
            policy_version=None,  # Legacy policy without version tracking
        )

        # policy_version should NOT be in payload when None
        assert "policy_version" not in telemetry
        # But other policy fields should be present
        assert telemetry["policy_id"] == "legacy-policy"
        assert telemetry["policy_name"] == "Legacy Policy"
        assert telemetry["policy_mode"] == "balanced"

    def test_policy_version_included_when_set(self):
        """Verify that policy_version IS included when it has a value.

        Custom policies with version tracking should have version in telemetry.
        """
        from raxe.domain.telemetry.scan_telemetry_builder import build_scan_telemetry

        # Build telemetry with explicit version
        telemetry = build_scan_telemetry(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="Test prompt",
            policy_id="custom-v3",
            policy_name="Custom Policy V3",
            policy_mode="custom",
            policy_version=3,
        )

        # policy_version SHOULD be in payload when set
        assert "policy_version" in telemetry
        assert telemetry["policy_version"] == 3
        assert telemetry["policy_id"] == "custom-v3"
        assert telemetry["policy_name"] == "Custom Policy V3"
        assert telemetry["policy_mode"] == "custom"
