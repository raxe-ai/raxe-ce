"""Unit tests for version checking and compatibility."""

import pytest

from raxe.infrastructure.rules.versioning import (
    Version,
    VersionChecker,
    VersionError,
)


class TestVersion:
    """Test Version dataclass."""

    def test_create_version(self):
        """Version can be created with major, minor, patch."""
        v = Version(1, 2, 3)

        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_version_is_immutable(self):
        """Version is frozen and cannot be modified."""
        v = Version(1, 0, 0)

        with pytest.raises(AttributeError):
            v.major = 2  # type: ignore

    def test_version_validates_negative(self):
        """Version raises ValueError for negative numbers."""
        with pytest.raises(ValueError, match="must be non-negative"):
            Version(-1, 0, 0)

        with pytest.raises(ValueError, match="must be non-negative"):
            Version(1, -1, 0)

        with pytest.raises(ValueError, match="must be non-negative"):
            Version(1, 0, -1)

    def test_parse_valid_semver(self):
        """Version.parse parses valid semver strings."""
        v = Version.parse("1.2.3")

        assert v.major == 1
        assert v.minor == 2
        assert v.patch == 3

    def test_parse_zero_version(self):
        """Version.parse handles 0.x.y versions."""
        v = Version.parse("0.1.0")

        assert v.major == 0
        assert v.minor == 1
        assert v.patch == 0

    def test_parse_invalid_format(self):
        """Version.parse raises ValueError for invalid format."""
        with pytest.raises(ValueError, match="must be in semver format"):
            Version.parse("1.2")

        with pytest.raises(ValueError, match="must be in semver format"):
            Version.parse("1.2.3.4")

        with pytest.raises(ValueError, match="must be in semver format"):
            Version.parse("invalid")

    def test_parse_non_integer_parts(self):
        """Version.parse raises ValueError for non-integer parts."""
        with pytest.raises(ValueError, match="must be integers"):
            Version.parse("1.2.x")

        with pytest.raises(ValueError, match="must be integers"):
            Version.parse("a.b.c")

    def test_str_representation(self):
        """Version.__str__ returns semver format."""
        v = Version(1, 2, 3)

        assert str(v) == "1.2.3"

    def test_version_comparison_lt(self):
        """Version comparison with <."""
        assert Version(1, 0, 0) < Version(2, 0, 0)
        assert Version(1, 0, 0) < Version(1, 1, 0)
        assert Version(1, 0, 0) < Version(1, 0, 1)
        assert not Version(1, 0, 0) < Version(1, 0, 0)

    def test_version_comparison_le(self):
        """Version comparison with <=."""
        assert Version(1, 0, 0) <= Version(1, 0, 0)
        assert Version(1, 0, 0) <= Version(1, 1, 0)

    def test_version_comparison_gt(self):
        """Version comparison with >."""
        assert Version(2, 0, 0) > Version(1, 0, 0)
        assert Version(1, 1, 0) > Version(1, 0, 0)
        assert Version(1, 0, 1) > Version(1, 0, 0)

    def test_version_comparison_ge(self):
        """Version comparison with >=."""
        assert Version(1, 0, 0) >= Version(1, 0, 0)
        assert Version(1, 1, 0) >= Version(1, 0, 0)

    def test_is_compatible_with_same_major(self):
        """Versions with same major are compatible."""
        v1 = Version(1, 0, 0)
        v2 = Version(1, 5, 10)

        assert v1.is_compatible_with(v2)
        assert v2.is_compatible_with(v1)

    def test_is_compatible_with_different_major(self):
        """Versions with different major are incompatible."""
        v1 = Version(1, 0, 0)
        v2 = Version(2, 0, 0)

        assert not v1.is_compatible_with(v2)
        assert not v2.is_compatible_with(v1)


class TestVersionChecker:
    """Test VersionChecker."""

    def test_current_version_is_set(self):
        """VersionChecker has CURRENT_VERSION defined."""
        checker = VersionChecker()

        assert checker.CURRENT_VERSION.major == 1
        assert checker.CURRENT_VERSION.minor == 1
        assert checker.CURRENT_VERSION.patch == 0

    def test_check_compatibility_same_version(self):
        """Same version as current is compatible."""
        checker = VersionChecker()

        # Should not raise
        checker.check_compatibility("1.1.0")

    def test_check_compatibility_same_major_older_minor(self):
        """Older minor version with same major is compatible."""
        checker = VersionChecker()

        # Should not raise
        checker.check_compatibility("1.0.0")

    def test_check_compatibility_same_major_newer_minor(self):
        """Newer minor version with same major is compatible."""
        checker = VersionChecker()

        # Should not raise (warning condition but still compatible)
        checker.check_compatibility("1.2.0")

    def test_check_compatibility_different_major(self):
        """Different major version is incompatible."""
        checker = VersionChecker()

        with pytest.raises(VersionError, match="incompatible"):
            checker.check_compatibility("2.0.0")

        # Note: v0.9.0 fails "too old" check before compatibility check
        with pytest.raises(VersionError, match="too old"):
            checker.check_compatibility("0.9.0")

    def test_check_compatibility_below_minimum(self):
        """Version below MINIMUM_VERSION is rejected."""
        checker = VersionChecker()

        # Assuming MINIMUM_VERSION is 1.0.0
        with pytest.raises(VersionError, match="too old"):
            checker.check_compatibility("0.5.0")

    def test_check_compatibility_invalid_format(self):
        """Invalid version format raises VersionError."""
        checker = VersionChecker()

        with pytest.raises(VersionError, match="Invalid rule version format"):
            checker.check_compatibility("invalid")

    def test_is_compatible_returns_bool(self):
        """is_compatible returns bool without raising."""
        checker = VersionChecker()

        assert checker.is_compatible("1.0.0") is True
        assert checker.is_compatible("1.1.0") is True
        assert checker.is_compatible("2.0.0") is False
        assert checker.is_compatible("invalid") is False

    def test_get_migration_path_same_version(self):
        """Migration path for same version is empty."""
        checker = VersionChecker()

        path = checker.get_migration_path("1.1.0", "1.1.0")

        assert path == []

    def test_get_migration_path_compatible_versions(self):
        """Migration path between compatible versions."""
        checker = VersionChecker()

        path = checker.get_migration_path("1.0.0", "1.1.0")

        assert len(path) == 1
        assert path[0][0] == Version(1, 0, 0)
        assert path[0][1] == Version(1, 1, 0)

    def test_get_migration_path_incompatible_versions(self):
        """Migration path fails for incompatible versions."""
        checker = VersionChecker()

        with pytest.raises(VersionError, match="Cannot migrate"):
            checker.get_migration_path("1.0.0", "2.0.0")

    def test_get_migration_path_to_current(self):
        """Migration path defaults to CURRENT_VERSION."""
        checker = VersionChecker()

        path = checker.get_migration_path("1.0.0")

        # Should migrate from 1.0.0 to CURRENT_VERSION (1.1.0)
        assert len(path) == 1
        assert path[0][1] == checker.CURRENT_VERSION
