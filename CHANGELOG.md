# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Package distribution and publishing infrastructure
- Multi-platform wheel build workflow (Linux, macOS, Windows)
- Automated release workflow with TestPyPI validation
- Installation benchmark script (scripts/benchmark_install.sh)
- Version bump utility (scripts/bump_version.py)
- Comprehensive release process documentation
- MANIFEST.in for package size optimization

### Changed
- Optimized package dependencies with version ranges
- Improved package size (wheel: 135KB, sdist: 113KB)
- Enhanced pyproject.toml with package exclusions
- Updated dependency specifications for better compatibility

### Fixed
- Package exclusions to prevent test files in distribution
- Proper handling of package data (YAML rule files)

## [0.1.0] - TBD

Initial alpha release (in development)

### Planned Features
- CLI with `init`, `scan`, `config` commands
- Python SDK for integration
- L1 detection (rules-based)
- L2 detection (ML-based)
- Local SQLite queue
- Cloud telemetry (optional)
- OpenAI/Anthropic wrappers

---

## Version History

- **0.1.0** - Initial alpha (in development)

[Unreleased]: https://github.com/raxe-ai/raxe-ce/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/raxe-ai/raxe-ce/releases/tag/v0.1.0
