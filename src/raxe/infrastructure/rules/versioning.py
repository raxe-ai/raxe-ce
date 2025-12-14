"""Schema versioning and compatibility checking.

Handles semantic versioning for rule schema and ensures compatibility
between different schema versions.
"""
from dataclasses import dataclass


class VersionError(Exception):
    """Exception raised when version compatibility check fails."""
    pass


@dataclass(frozen=True)
class Version:
    """Semantic version representation.

    Attributes:
        major: Major version number (breaking changes)
        minor: Minor version number (backward compatible features)
        patch: Patch version number (backward compatible fixes)
    """
    major: int
    minor: int
    patch: int

    def __post_init__(self) -> None:
        """Validate version numbers are non-negative."""
        if self.major < 0 or self.minor < 0 or self.patch < 0:
            raise ValueError(f"Version numbers must be non-negative: {self}")

    @classmethod
    def parse(cls, version_str: str) -> 'Version':
        """Parse semver string like '1.2.3'.

        Args:
            version_str: Version string in semver format

        Returns:
            Parsed Version object

        Raises:
            ValueError: If version string is invalid
        """
        parts = version_str.split('.')
        if len(parts) != 3:
            raise ValueError(
                f"Version must be in semver format (X.Y.Z), got '{version_str}'"
            )

        try:
            major = int(parts[0])
            minor = int(parts[1])
            patch = int(parts[2])
            return cls(major=major, minor=minor, patch=patch)
        except ValueError as e:
            raise ValueError(
                f"Version parts must be integers, got '{version_str}'"
            ) from e

    def __str__(self) -> str:
        """Return string representation in semver format.

        Returns:
            Version string in format 'major.minor.patch'
        """
        return f"{self.major}.{self.minor}.{self.patch}"

    def __lt__(self, other: 'Version') -> bool:
        """Compare versions for ordering.

        Args:
            other: Version to compare against

        Returns:
            True if this version is less than other
        """
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __le__(self, other: 'Version') -> bool:
        """Compare versions for ordering.

        Args:
            other: Version to compare against

        Returns:
            True if this version is less than or equal to other
        """
        return (self.major, self.minor, self.patch) <= (other.major, other.minor, other.patch)

    def __gt__(self, other: 'Version') -> bool:
        """Compare versions for ordering.

        Args:
            other: Version to compare against

        Returns:
            True if this version is greater than other
        """
        return (self.major, self.minor, self.patch) > (other.major, other.minor, other.patch)

    def __ge__(self, other: 'Version') -> bool:
        """Compare versions for ordering.

        Args:
            other: Version to compare against

        Returns:
            True if this version is greater than or equal to other
        """
        return (self.major, self.minor, self.patch) >= (other.major, other.minor, other.patch)

    def is_compatible_with(self, other: 'Version') -> bool:
        """Check if this version can load rules from other version.

        Compatibility rules:
        - Same major version: compatible (minor/patch differences OK)
        - Different major version: incompatible (breaking changes)

        Args:
            other: Version to check compatibility against

        Returns:
            True if versions are compatible, False otherwise
        """
        return self.major == other.major


class VersionChecker:
    """Check schema version compatibility for rules.

    Ensures that rule files are compatible with the current parser version.
    """

    # Current schema version supported by this implementation
    CURRENT_VERSION = Version(1, 1, 0)

    # Minimum supported version (can load rules from this version onwards)
    MINIMUM_VERSION = Version(1, 0, 0)

    def check_compatibility(self, rule_version: str) -> None:
        """Verify rule schema version is compatible.

        Args:
            rule_version: Version string from rule file

        Raises:
            VersionError: If rule version is incompatible with parser
        """
        try:
            rule_v = Version.parse(rule_version)
        except ValueError as e:
            raise VersionError(f"Invalid rule version format: {e}") from e

        # Check if rule version is too old
        if rule_v < self.MINIMUM_VERSION:
            raise VersionError(
                f"Rule schema v{rule_version} is too old. "
                f"Minimum supported version is v{self.MINIMUM_VERSION}"
            )

        # Check major version compatibility
        if not self.CURRENT_VERSION.is_compatible_with(rule_v):
            raise VersionError(
                f"Rule schema v{rule_version} is incompatible with "
                f"parser v{self.CURRENT_VERSION}. "
                f"Major version mismatch indicates breaking changes."
            )

        # Warn if rule is newer minor/patch version (still compatible)
        if rule_v > self.CURRENT_VERSION:
            # This is a warning condition, not an error
            # Could be logged, but we don't do logging in infrastructure
            pass

    def is_compatible(self, rule_version: str) -> bool:
        """Check if rule version is compatible without raising exception.

        Args:
            rule_version: Version string from rule file

        Returns:
            True if compatible, False otherwise
        """
        try:
            self.check_compatibility(rule_version)
            return True
        except VersionError:
            return False

    def get_migration_path(
        self,
        from_version: str,
        to_version: str | None = None
    ) -> list[tuple[Version, Version]]:
        """Get the migration path between two versions.

        Future use: Returns list of version transitions needed for migration.

        Args:
            from_version: Starting version
            to_version: Target version (defaults to CURRENT_VERSION)

        Returns:
            List of (from, to) version tuples representing migration steps

        Raises:
            VersionError: If migration path doesn't exist
        """
        from_v = Version.parse(from_version)
        to_v = Version.parse(to_version) if to_version else self.CURRENT_VERSION

        # For now, only same-major migrations are supported
        if not from_v.is_compatible_with(to_v):
            raise VersionError(
                f"Cannot migrate from v{from_v} to v{to_v}: "
                f"different major versions (breaking changes)"
            )

        # If versions are compatible, no migration needed
        # Future: Could return intermediate migration steps
        return [(from_v, to_v)] if from_v != to_v else []
