"""
Basic smoke tests to validate repository structure.

These tests ensure the package is importable and basic structure is correct.
Will be expanded as features are implemented.
"""

import sys
from pathlib import Path


def test_package_importable():
    """Test that the raxe package can be imported."""
    import raxe

    assert raxe is not None
    assert hasattr(raxe, "__version__")


def test_package_version():
    """Test that package version is defined."""
    import raxe

    assert raxe.__version__ == "1.0.0"


def test_package_structure():
    """Test that all expected subpackages exist."""
    import raxe.application
    import raxe.cli
    import raxe.domain
    import raxe.infrastructure
    import raxe.sdk
    import raxe.utils

    # Verify they're importable
    assert raxe.domain is not None
    assert raxe.application is not None
    assert raxe.infrastructure is not None
    assert raxe.cli is not None
    assert raxe.sdk is not None
    assert raxe.utils is not None


def test_infrastructure_subpackages():
    """Test that infrastructure subpackages exist."""
    import raxe.infrastructure.cloud
    import raxe.infrastructure.config
    import raxe.infrastructure.database

    assert raxe.infrastructure.database is not None
    assert raxe.infrastructure.cloud is not None
    assert raxe.infrastructure.config is not None


def test_sdk_wrappers():
    """Test that SDK wrappers package exists."""
    import raxe.sdk.wrappers

    assert raxe.sdk.wrappers is not None


def test_python_version():
    """Test that Python version is 3.10+."""
    assert sys.version_info >= (3, 10), "Python 3.10+ required"


def test_project_root_exists():
    """Test that key files exist in project root."""
    project_root = Path(__file__).parent.parent

    required_files = [
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "CODE_OF_CONDUCT.md",
    ]

    for file in required_files:
        file_path = project_root / file
        assert file_path.exists(), f"{file} not found"


def test_source_structure():
    """Test that source directory structure is correct."""
    project_root = Path(__file__).parent.parent
    src_dir = project_root / "src" / "raxe"

    required_dirs = [
        "domain",
        "application",
        "infrastructure",
        "cli",
        "sdk",
        "utils",
    ]

    for dir_name in required_dirs:
        dir_path = src_dir / dir_name
        assert dir_path.exists(), f"{dir_name}/ not found"
        assert (dir_path / "__init__.py").exists(), f"{dir_name}/__init__.py not found"


def test_test_structure():
    """Test that test directory structure is correct."""
    project_root = Path(__file__).parent.parent
    tests_dir = project_root / "tests"

    required_dirs = [
        "unit",
        "integration",
        "performance",
        "golden",
    ]

    for dir_name in required_dirs:
        dir_path = tests_dir / dir_name
        assert dir_path.exists(), f"tests/{dir_name}/ not found"
