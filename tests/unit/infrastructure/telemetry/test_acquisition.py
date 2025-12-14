"""
Unit tests for acquisition source detection module.

Tests the detect_acquisition_source function and its helper functions.
These tests use environment variable manipulation (infrastructure layer tests).

Coverage target: >95%
"""

import os
from unittest.mock import patch

import pytest

from raxe.infrastructure.telemetry.acquisition import (
    AcquisitionSource,
    detect_acquisition_source,
)


# =============================================================================
# Test Markers
# =============================================================================
pytestmark = [pytest.mark.unit, pytest.mark.infrastructure, pytest.mark.telemetry]


# =============================================================================
# Test Fixtures
# =============================================================================
@pytest.fixture
def clean_env():
    """Fixture that clears relevant environment variables before each test."""
    env_vars_to_clear = [
        "CI",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "CIRCLECI",
        "TRAVIS",
        "JENKINS_URL",
        "BUILDKITE",
        "AZURE_PIPELINES",
        "BITBUCKET_PIPELINES",
        "TEAMCITY_VERSION",
        "DRONE",
        "CODEBUILD_BUILD_ID",
        "RAXE_DOCKER",
        "RAXE_REFERRAL_CODE",
        "RAXE_ENTERPRISE_DEPLOY",
        "RAXE_ACQUISITION_SOURCE",
    ]
    original_env = {}
    for var in env_vars_to_clear:
        if var in os.environ:
            original_env[var] = os.environ.pop(var)

    yield

    # Restore original environment
    for var, value in original_env.items():
        os.environ[var] = value
    for var in env_vars_to_clear:
        if var not in original_env and var in os.environ:
            del os.environ[var]


# =============================================================================
# Explicit Acquisition Source Tests
# =============================================================================
class TestExplicitAcquisitionSource:
    """Test explicit RAXE_ACQUISITION_SOURCE environment variable."""

    def test_explicit_source_takes_priority(self, clean_env: None) -> None:
        """Explicit RAXE_ACQUISITION_SOURCE should override all other detection."""
        os.environ["RAXE_ACQUISITION_SOURCE"] = "homebrew"
        os.environ["CI"] = "true"  # CI should be overridden

        result = detect_acquisition_source(install_method="pip")

        assert result == "homebrew"

    @pytest.mark.parametrize(
        "source",
        [
            "pip_install",
            "github_release",
            "docker",
            "homebrew",
            "website_download",
            "referral",
            "enterprise_deploy",
            "ci_integration",
            "unknown",
        ],
    )
    def test_explicit_source_accepts_all_valid_values(
        self, clean_env: None, source: str
    ) -> None:
        """Should accept all valid acquisition source values."""
        os.environ["RAXE_ACQUISITION_SOURCE"] = source

        result = detect_acquisition_source()

        assert result == source

    def test_invalid_explicit_source_falls_through(self, clean_env: None) -> None:
        """Invalid explicit source should fall through to other detection methods."""
        os.environ["RAXE_ACQUISITION_SOURCE"] = "invalid_source"
        os.environ["CI"] = "true"

        result = detect_acquisition_source()

        # Should detect CI since explicit source is invalid
        assert result == "ci_integration"


# =============================================================================
# Enterprise Deployment Tests
# =============================================================================
class TestEnterpriseDeployment:
    """Test enterprise deployment detection."""

    def test_enterprise_deploy_detected(self, clean_env: None) -> None:
        """RAXE_ENTERPRISE_DEPLOY should return enterprise_deploy."""
        os.environ["RAXE_ENTERPRISE_DEPLOY"] = "true"

        result = detect_acquisition_source()

        assert result == "enterprise_deploy"

    def test_enterprise_deploy_takes_priority_over_ci(self, clean_env: None) -> None:
        """Enterprise deploy should override CI detection."""
        os.environ["RAXE_ENTERPRISE_DEPLOY"] = "1"
        os.environ["CI"] = "true"

        result = detect_acquisition_source()

        assert result == "enterprise_deploy"


# =============================================================================
# Referral Code Tests
# =============================================================================
class TestReferralCode:
    """Test referral code detection."""

    def test_referral_code_detected(self, clean_env: None) -> None:
        """RAXE_REFERRAL_CODE should return referral."""
        os.environ["RAXE_REFERRAL_CODE"] = "FRIEND123"

        result = detect_acquisition_source()

        assert result == "referral"

    def test_referral_takes_priority_over_ci(self, clean_env: None) -> None:
        """Referral should override CI detection."""
        os.environ["RAXE_REFERRAL_CODE"] = "ABC"
        os.environ["CI"] = "true"

        result = detect_acquisition_source()

        assert result == "referral"


# =============================================================================
# Docker Environment Tests
# =============================================================================
class TestDockerEnvironment:
    """Test Docker environment detection."""

    def test_docker_env_var_detected(self, clean_env: None) -> None:
        """RAXE_DOCKER should return docker."""
        os.environ["RAXE_DOCKER"] = "1"

        result = detect_acquisition_source()

        assert result == "docker"

    def test_docker_takes_priority_over_ci(self, clean_env: None) -> None:
        """Docker should override CI detection."""
        os.environ["RAXE_DOCKER"] = "true"
        os.environ["CI"] = "true"

        result = detect_acquisition_source()

        assert result == "docker"

    def test_dockerenv_file_detected(self, clean_env: None) -> None:
        """/.dockerenv file should trigger docker detection."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True

            result = detect_acquisition_source()

            assert result == "docker"

    def test_docker_cgroup_detected(self, clean_env: None) -> None:
        """Docker in cgroup should trigger docker detection."""
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", create=True) as mock_open:
                mock_open.return_value.__enter__.return_value.read.return_value = (
                    "1:name=systemd:/docker/abc123\n"
                )

                result = detect_acquisition_source()

                assert result == "docker"


# =============================================================================
# CI Environment Tests
# =============================================================================
class TestCIEnvironment:
    """Test CI environment detection."""

    @pytest.mark.parametrize(
        "ci_var",
        [
            "CI",
            "GITHUB_ACTIONS",
            "GITLAB_CI",
            "CIRCLECI",
            "TRAVIS",
            "JENKINS_URL",
            "BUILDKITE",
            "AZURE_PIPELINES",
            "BITBUCKET_PIPELINES",
            "TEAMCITY_VERSION",
            "DRONE",
            "CODEBUILD_BUILD_ID",
        ],
    )
    def test_ci_environments_detected(self, clean_env: None, ci_var: str) -> None:
        """Each CI environment variable should trigger ci_integration detection."""
        os.environ[ci_var] = "true"

        result = detect_acquisition_source()

        assert result == "ci_integration"

    def test_ci_takes_priority_over_install_method(self, clean_env: None) -> None:
        """CI should override install method inference."""
        os.environ["CI"] = "true"

        result = detect_acquisition_source(install_method="pip")

        assert result == "ci_integration"


# =============================================================================
# Install Method Inference Tests
# =============================================================================
class TestInstallMethodInference:
    """Test acquisition source inference from install method."""

    @pytest.mark.parametrize(
        "install_method,expected_source",
        [
            ("pip", "pip_install"),
            ("uv", "pip_install"),
            ("pipx", "pip_install"),
            ("poetry", "pip_install"),
            ("conda", "pip_install"),
            ("source", "github_release"),
        ],
    )
    def test_install_method_inference(
        self, clean_env: None, install_method: str, expected_source: AcquisitionSource
    ) -> None:
        """Install method should be mapped to appropriate acquisition source."""
        result = detect_acquisition_source(install_method=install_method)

        assert result == expected_source

    def test_unknown_install_method_returns_unknown(self, clean_env: None) -> None:
        """Unknown install method should return unknown."""
        result = detect_acquisition_source(install_method="unknown")

        assert result == "unknown"


# =============================================================================
# Default Behavior Tests
# =============================================================================
class TestDefaultBehavior:
    """Test default behavior when no detection matches."""

    def test_no_detection_returns_unknown(self, clean_env: None) -> None:
        """When nothing is detected, should return unknown."""
        # Mock Docker file checks to return False
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=FileNotFoundError):
                result = detect_acquisition_source()

                assert result == "unknown"

    def test_none_install_method_returns_unknown(self, clean_env: None) -> None:
        """None install_method should return unknown."""
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=FileNotFoundError):
                result = detect_acquisition_source(install_method=None)

                assert result == "unknown"


# =============================================================================
# Priority Order Tests
# =============================================================================
class TestPriorityOrder:
    """Test that detection priority order is correct."""

    def test_priority_order_explicit_over_all(self, clean_env: None) -> None:
        """Explicit source > Enterprise > Referral > Docker > CI > Install Method."""
        os.environ["RAXE_ACQUISITION_SOURCE"] = "website_download"
        os.environ["RAXE_ENTERPRISE_DEPLOY"] = "true"
        os.environ["RAXE_REFERRAL_CODE"] = "ABC"
        os.environ["RAXE_DOCKER"] = "true"
        os.environ["CI"] = "true"

        result = detect_acquisition_source(install_method="pip")

        assert result == "website_download"

    def test_priority_order_enterprise_over_referral(self, clean_env: None) -> None:
        """Enterprise > Referral when explicit not set."""
        os.environ["RAXE_ENTERPRISE_DEPLOY"] = "true"
        os.environ["RAXE_REFERRAL_CODE"] = "ABC"
        os.environ["CI"] = "true"

        result = detect_acquisition_source(install_method="pip")

        assert result == "enterprise_deploy"

    def test_priority_order_referral_over_docker(self, clean_env: None) -> None:
        """Referral > Docker when enterprise not set."""
        os.environ["RAXE_REFERRAL_CODE"] = "ABC"
        os.environ["RAXE_DOCKER"] = "true"
        os.environ["CI"] = "true"

        result = detect_acquisition_source(install_method="pip")

        assert result == "referral"

    def test_priority_order_docker_over_ci(self, clean_env: None) -> None:
        """Docker > CI when referral not set."""
        os.environ["RAXE_DOCKER"] = "true"
        os.environ["CI"] = "true"

        result = detect_acquisition_source(install_method="pip")

        assert result == "docker"

    def test_priority_order_ci_over_install_method(self, clean_env: None) -> None:
        """CI > Install Method when docker not set."""
        os.environ["CI"] = "true"

        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=FileNotFoundError):
                result = detect_acquisition_source(install_method="pip")

                assert result == "ci_integration"


# =============================================================================
# Edge Cases
# =============================================================================
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_env_var_not_detected(self, clean_env: None) -> None:
        """Empty environment variables should not trigger detection."""
        os.environ["CI"] = ""
        os.environ["RAXE_REFERRAL_CODE"] = ""
        os.environ["RAXE_ENTERPRISE_DEPLOY"] = ""

        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=FileNotFoundError):
                result = detect_acquisition_source(install_method="pip")

                assert result == "pip_install"

    def test_cgroup_permission_error_handled(self, clean_env: None) -> None:
        """Permission errors reading cgroup should be handled gracefully."""
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=PermissionError):
                result = detect_acquisition_source(install_method="pip")

                assert result == "pip_install"

    def test_cgroup_os_error_handled(self, clean_env: None) -> None:
        """OS errors reading cgroup should be handled gracefully."""
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=OSError):
                result = detect_acquisition_source(install_method="pip")

                assert result == "pip_install"
