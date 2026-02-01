"""Tests for MSSP context in telemetry schema v3.0.

TDD: These tests define the expected behavior for MSSP telemetry fields.
Implementation should make these tests pass.
"""

from raxe.domain.telemetry.scan_telemetry_builder import (
    SCHEMA_VERSION,
    ScanTelemetryBuilder,
    build_scan_telemetry,
)


class TestMSSPContextFields:
    """Tests for MSSP context fields in telemetry payload."""

    def test_mssp_id_included_when_provided(self):
        """mssp_id is included in telemetry payload when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
        )

        assert "mssp_id" in result
        assert result["mssp_id"] == "mssp_partner"

    def test_customer_id_included_when_provided(self):
        """customer_id is included in telemetry payload when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            customer_id="cust_abc123",
        )

        assert "customer_id" in result
        assert result["customer_id"] == "cust_abc123"

    def test_agent_id_included_when_provided(self):
        """agent_id is included in telemetry payload when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            agent_id="agent_xyz789",
        )

        assert "agent_id" in result
        assert result["agent_id"] == "agent_xyz789"

    def test_full_mssp_hierarchy_in_payload(self):
        """All MSSP hierarchy fields are included when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
            customer_id="cust_abc123",
            app_id="app_chatbot",
            agent_id="agent_xyz789",
        )

        assert result["mssp_id"] == "mssp_partner"
        assert result["customer_id"] == "cust_abc123"
        assert result["app_id"] == "app_chatbot"
        assert result["agent_id"] == "agent_xyz789"

    def test_mssp_fields_not_included_when_not_provided(self):
        """MSSP fields are NOT in payload when not provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
        )

        assert "mssp_id" not in result
        assert "customer_id" not in result
        assert "agent_id" not in result


class TestMSSPContextBlock:
    """Tests for _mssp_context block in telemetry payload."""

    def test_mssp_context_block_created_when_mssp_fields_present(self):
        """_mssp_context block is created when MSSP fields are provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
            customer_id="cust_abc123",
        )

        assert "_mssp_context" in result
        assert result["_mssp_context"]["mssp_id"] == "mssp_partner"
        assert result["_mssp_context"]["customer_id"] == "cust_abc123"

    def test_mssp_context_block_includes_data_mode(self):
        """_mssp_context block includes data_mode when provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
            data_mode="full",
        )

        assert "_mssp_context" in result
        assert result["_mssp_context"]["data_mode"] == "full"

    def test_mssp_context_block_includes_data_fields(self):
        """_mssp_context block includes data_fields list when provided."""
        builder = ScanTelemetryBuilder()

        data_fields = ["prompt", "response", "matched_text"]
        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
            data_fields=data_fields,
        )

        assert "_mssp_context" in result
        assert result["_mssp_context"]["data_fields"] == data_fields

    def test_mssp_context_block_not_created_without_mssp_id(self):
        """_mssp_context block is NOT created when mssp_id is not provided."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            # No mssp_id
            customer_id="cust_abc123",  # Has customer but no MSSP
        )

        # _mssp_context should not be created without mssp_id
        assert "_mssp_context" not in result

    def test_full_mssp_context_structure(self):
        """Complete _mssp_context structure matches expected format."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
            customer_id="cust_abc123",
            app_id="app_chatbot",
            agent_id="agent_xyz789",
            data_mode="full",
            data_fields=["prompt", "matched_text"],
        )

        mssp_context = result["_mssp_context"]
        assert mssp_context["mssp_id"] == "mssp_partner"
        assert mssp_context["customer_id"] == "cust_abc123"
        assert mssp_context["app_id"] == "app_chatbot"
        assert mssp_context["agent_id"] == "agent_xyz789"
        assert mssp_context["data_mode"] == "full"
        assert mssp_context["data_fields"] == ["prompt", "matched_text"]


class TestDataModePrivacyControl:
    """Tests for data_mode privacy controls in telemetry."""

    def test_data_mode_defaults_to_privacy_safe(self):
        """data_mode defaults to 'privacy_safe' when not specified."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
            # data_mode not specified
        )

        assert result["_mssp_context"]["data_mode"] == "privacy_safe"

    def test_data_mode_full_allows_optional_fields(self):
        """data_mode='full' allows prompt_text and other raw fields."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt for full mode",
            mssp_id="mssp_partner",
            data_mode="full",
            data_fields=["prompt"],
            include_prompt_text=True,
        )

        # In full mode with prompt field enabled, prompt_text can be included
        # Note: This is for MSSP webhook only, never sent to RAXE
        assert result["_mssp_context"]["data_mode"] == "full"
        # The raw prompt should be available for MSSP dual-send
        assert "prompt_text" in result or result.get("_mssp_data", {}).get("prompt_text")

    def test_data_mode_privacy_safe_never_includes_raw_text(self):
        """data_mode='privacy_safe' never includes raw prompt text."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="sensitive prompt that should not appear",
            mssp_id="mssp_partner",
            data_mode="privacy_safe",
        )

        # In privacy_safe mode, no raw text
        assert "prompt_text" not in result
        assert "matched_text" not in result
        assert "response_text" not in result
        # Only hash should be present
        assert result["prompt_hash"].startswith("sha256:")


class TestMSSPDataForDualSend:
    """Tests for MSSP-specific data that enables dual-send telemetry."""

    def test_mssp_data_block_for_full_mode(self):
        """_mssp_data block contains raw data for MSSP webhook in full mode."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt for MSSP",
            mssp_id="mssp_partner",
            data_mode="full",
            data_fields=["prompt", "matched_text"],
            include_prompt_text=True,
        )

        # _mssp_data contains fields for MSSP webhook only
        assert "_mssp_data" in result
        assert result["_mssp_data"]["prompt_text"] == "test prompt for MSSP"

    def test_mssp_data_block_not_present_in_privacy_safe_mode(self):
        """_mssp_data block is NOT present in privacy_safe mode."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="sensitive prompt",
            mssp_id="mssp_partner",
            data_mode="privacy_safe",
        )

        assert "_mssp_data" not in result

    def test_mssp_data_only_includes_allowed_fields(self):
        """_mssp_data only includes fields specified in data_fields."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
            data_mode="full",
            data_fields=["prompt"],  # Only prompt, not response
            include_prompt_text=True,
        )

        mssp_data = result.get("_mssp_data", {})
        assert "prompt_text" in mssp_data
        assert "response_text" not in mssp_data


class TestConvenienceFunction:
    """Tests for build_scan_telemetry convenience function with MSSP fields."""

    def test_build_scan_telemetry_accepts_mssp_fields(self):
        """build_scan_telemetry function accepts all MSSP-related parameters."""
        result = build_scan_telemetry(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            mssp_id="mssp_partner",
            customer_id="cust_abc123",
            agent_id="agent_xyz789",
            data_mode="full",
            data_fields=["prompt"],
        )

        assert "mssp_id" in result
        assert "_mssp_context" in result


class TestSchemaVersion:
    """Tests for schema version update."""

    def test_schema_version_is_3_0_0(self):
        """Schema version should be 3.0.0 for MSSP support."""
        # Note: This test will fail until we update SCHEMA_VERSION
        assert SCHEMA_VERSION == "3.0.0"


class TestBackwardCompatibility:
    """Tests ensuring backward compatibility with existing telemetry."""

    def test_existing_tenant_id_still_works(self):
        """tenant_id field still works alongside new MSSP fields."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            tenant_id="acme",
            mssp_id="mssp_partner",
            customer_id="cust_abc123",
        )

        # Both tenant_id and MSSP fields should be present
        assert result["tenant_id"] == "acme"
        assert result["mssp_id"] == "mssp_partner"
        assert result["customer_id"] == "cust_abc123"

    def test_existing_policy_fields_still_work(self):
        """Existing policy fields work alongside MSSP fields."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
            policy_id="strict",
            policy_mode="strict",
            mssp_id="mssp_partner",
        )

        assert result["policy_id"] == "strict"
        assert result["policy_mode"] == "strict"
        assert result["mssp_id"] == "mssp_partner"

    def test_telemetry_without_mssp_fields_unchanged(self):
        """Telemetry without MSSP fields has unchanged structure."""
        builder = ScanTelemetryBuilder()

        result = builder.build(
            l1_result=None,
            l2_result=None,
            scan_duration_ms=5.0,
            entry_point="sdk",
            prompt="test prompt",
        )

        # Core fields still present
        assert "prompt_hash" in result
        assert "prompt_length" in result
        assert "threat_detected" in result
        assert "scan_duration_ms" in result
        assert "action_taken" in result
        assert "entry_point" in result

        # MSSP fields should not be present
        assert "mssp_id" not in result
        assert "customer_id" not in result
        assert "_mssp_context" not in result
