"""Acquisition source detection for telemetry.

This module handles detection of how RAXE was acquired/installed.
Contains I/O operations (environment variable reads) so belongs in infrastructure layer.
"""

import os
from typing import Literal

AcquisitionSource = Literal[
    "pip_install",
    "github_release",
    "docker",
    "homebrew",
    "website_download",
    "referral",
    "enterprise_deploy",
    "ci_integration",
    "unknown",
]

# Environment variables that indicate CI environments
CI_ENV_VARS = frozenset({
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
})


def _is_ci_environment() -> bool:
    """Check if running in a CI environment.

    Returns:
        True if any CI environment variable is set.
    """
    return any(os.environ.get(var) for var in CI_ENV_VARS)


def _is_docker_environment() -> bool:
    """Check if running inside a Docker container.

    Returns:
        True if Docker environment is detected.
    """
    # Check for Docker-specific environment variable
    if os.environ.get("RAXE_DOCKER"):
        return True

    # Check for /.dockerenv file (common Docker indicator)
    if os.path.exists("/.dockerenv"):
        return True

    # Check cgroup for docker
    try:
        with open("/proc/1/cgroup", "r") as f:
            return "docker" in f.read()
    except (FileNotFoundError, PermissionError, OSError):
        pass

    return False


def _has_referral_code() -> bool:
    """Check if a referral code is present.

    Returns:
        True if RAXE_REFERRAL_CODE environment variable is set.
    """
    return bool(os.environ.get("RAXE_REFERRAL_CODE"))


def _is_enterprise_deploy() -> bool:
    """Check if this is an enterprise deployment.

    Returns:
        True if RAXE_ENTERPRISE_DEPLOY environment variable is set.
    """
    return bool(os.environ.get("RAXE_ENTERPRISE_DEPLOY"))


def _get_explicit_acquisition_source() -> str | None:
    """Get explicitly set acquisition source from environment.

    Returns:
        The value of RAXE_ACQUISITION_SOURCE if set, None otherwise.
    """
    return os.environ.get("RAXE_ACQUISITION_SOURCE")


def detect_acquisition_source(
    install_method: str | None = None,
) -> AcquisitionSource:
    """Detect how RAXE was acquired/installed.

    Detection priority (highest to lowest):
    1. Explicit RAXE_ACQUISITION_SOURCE environment variable
    2. Enterprise deployment (RAXE_ENTERPRISE_DEPLOY)
    3. Referral code (RAXE_REFERRAL_CODE)
    4. Docker environment
    5. CI environment
    6. Install method inference (pip -> pip_install)
    7. Default to "unknown"

    Args:
        install_method: The install method detected (pip, uv, etc).
            Used to infer acquisition source if not explicitly set.

    Returns:
        The detected acquisition source.

    Example:
        >>> # In normal pip install
        >>> detect_acquisition_source(install_method="pip")
        'pip_install'

        >>> # In CI with pip
        >>> os.environ["CI"] = "true"
        >>> detect_acquisition_source(install_method="pip")
        'ci_integration'
    """
    # 1. Check for explicit acquisition source
    explicit_source = _get_explicit_acquisition_source()
    if explicit_source:
        # Validate it's a known value
        valid_sources: set[AcquisitionSource] = {
            "pip_install",
            "github_release",
            "docker",
            "homebrew",
            "website_download",
            "referral",
            "enterprise_deploy",
            "ci_integration",
            "unknown",
        }
        if explicit_source in valid_sources:
            return explicit_source  # type: ignore[return-value]

    # 2. Check for enterprise deployment
    if _is_enterprise_deploy():
        return "enterprise_deploy"

    # 3. Check for referral code
    if _has_referral_code():
        return "referral"

    # 4. Check for Docker environment
    if _is_docker_environment():
        return "docker"

    # 5. Check for CI environment
    if _is_ci_environment():
        return "ci_integration"

    # 6. Infer from install method
    if install_method:
        # Map install methods to acquisition sources
        install_method_mapping: dict[str, AcquisitionSource] = {
            "pip": "pip_install",
            "uv": "pip_install",  # uv is a pip-compatible installer
            "pipx": "pip_install",  # pipx installs from PyPI
            "poetry": "pip_install",  # poetry installs from PyPI
            "conda": "pip_install",  # Treat conda similar to pip
            "source": "github_release",  # Source install usually from GitHub
        }
        if install_method in install_method_mapping:
            return install_method_mapping[install_method]

    # 7. Default to unknown
    return "unknown"
