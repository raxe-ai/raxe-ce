#!/usr/bin/env python3
"""
Version Bump Utility for RAXE

Usage:
    python scripts/bump_version.py major  # 1.0.0 -> 2.0.0
    python scripts/bump_version.py minor  # 1.0.0 -> 1.1.0
    python scripts/bump_version.py patch  # 1.0.0 -> 1.0.1
    python scripts/bump_version.py 1.2.3  # Set specific version
"""

import re
import sys
from pathlib import Path


def get_current_version(pyproject_path: Path) -> str:
    """Extract current version from pyproject.toml"""
    content = pyproject_path.read_text()
    match = re.search(r'version\s*=\s*"([^"]+)"', content)
    if not match:
        raise ValueError("Could not find version in pyproject.toml")
    return match.group(1)


def parse_version(version: str) -> tuple[int, int, int]:
    """Parse version string into major, minor, patch"""
    parts = version.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version}")
    return int(parts[0]), int(parts[1]), int(parts[2])


def bump_version(current: str, bump_type: str) -> str:
    """Bump version based on type"""
    major, minor, patch = parse_version(current)

    if bump_type == "major":
        return f"{major + 1}.0.0"
    elif bump_type == "minor":
        return f"{major}.{minor + 1}.0"
    elif bump_type == "patch":
        return f"{major}.{minor}.{patch + 1}"
    else:
        # Assume it's a specific version
        parse_version(bump_type)  # Validate format
        return bump_type


def update_pyproject(pyproject_path: Path, new_version: str) -> None:
    """Update version in pyproject.toml"""
    content = pyproject_path.read_text()
    updated = re.sub(
        r'version\s*=\s*"[^"]+"',
        f'version = "{new_version}"',
        content
    )
    pyproject_path.write_text(updated)


def update_init(init_path: Path, new_version: str) -> None:
    """Update version in __init__.py"""
    if not init_path.exists():
        return

    content = init_path.read_text()

    # Check if __version__ exists
    if "__version__" in content:
        updated = re.sub(
            r'__version__\s*=\s*["\'][^"\']+["\']',
            f'__version__ = "{new_version}"',
            content
        )
    else:
        # Add __version__ if it doesn't exist
        updated = f'__version__ = "{new_version}"\n\n{content}'

    init_path.write_text(updated)


def update_changelog(changelog_path: Path, new_version: str) -> None:
    """Add entry to CHANGELOG.md"""
    if not changelog_path.exists():
        content = "# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n"
        changelog_path.write_text(content)

    content = changelog_path.read_text()

    # Add new version entry
    from datetime import date
    today = date.today().isoformat()

    new_entry = f"""## [{new_version}] - {today}

### Added
-

### Changed
-

### Fixed
-

"""

    # Insert after the header
    lines = content.split("\n")
    header_end = 0
    for i, line in enumerate(lines):
        if line.startswith("## "):
            header_end = i
            break

    if header_end > 0:
        lines.insert(header_end, new_entry)
    else:
        lines.append(new_entry)

    changelog_path.write_text("\n".join(lines))


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    bump_type = sys.argv[1]
    repo_root = Path(__file__).parent.parent

    pyproject_path = repo_root / "pyproject.toml"
    init_path = repo_root / "src" / "raxe" / "__init__.py"
    changelog_path = repo_root / "CHANGELOG.md"

    try:
        current_version = get_current_version(pyproject_path)
        new_version = bump_version(current_version, bump_type)

        print(f"Current version: {current_version}")
        print(f"New version: {new_version}")
        print()

        # Confirm
        response = input("Proceed with version bump? [y/N]: ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)

        # Update files
        print("Updating pyproject.toml...")
        update_pyproject(pyproject_path, new_version)

        print("Updating __init__.py...")
        update_init(init_path, new_version)

        print("Updating CHANGELOG.md...")
        update_changelog(changelog_path, new_version)

        print()
        print(f"Version bumped to {new_version}")
        print()
        print("Next steps:")
        print(f"1. Review changes: git diff")
        print(f"2. Update CHANGELOG.md with actual changes")
        print(f"3. Commit changes: git commit -am 'chore: bump version to {new_version}'")
        print(f"4. Create tag: git tag v{new_version}")
        print(f"5. Push: git push && git push --tags")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
