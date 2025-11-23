# Development Scripts

Utility scripts for RAXE CE development, testing, and maintenance.

## Available Scripts

### Performance & Benchmarking

#### `benchmark.py`
Run performance benchmarks to validate SLO compliance.

```bash
# Run all benchmarks
python scripts/benchmark.py

# Run specific benchmark
python scripts/benchmark.py --latency
python scripts/benchmark.py --throughput
python scripts/benchmark.py --memory

# Get help
python scripts/benchmark.py --help
```

**Benchmarks:**
- **Latency**: P95 scan latency < 10ms
- **Throughput**: > 1000 scans/sec
- **Memory**: < 100MB for 10K queued events

#### `benchmark_install.sh`
Test package installation time and size across different methods.

```bash
# Run installation benchmarks
./scripts/benchmark_install.sh
```

**Validates:**
- Package size < 10MB
- Installation time < 30 seconds
- Import time acceptable
- No test files in wheel

### Version Management

#### `bump_version.py`
Bump project version following semantic versioning.

```bash
# Bump patch version (1.0.0 -> 1.0.1)
python scripts/bump_version.py patch

# Bump minor version (1.0.0 -> 1.1.0)
python scripts/bump_version.py minor

# Bump major version (1.0.0 -> 2.0.0)
python scripts/bump_version.py major

# Set specific version
python scripts/bump_version.py 1.2.3
```

**Updates:**
- `pyproject.toml` version
- `src/raxe/__init__.py` `__version__`
- `CHANGELOG.md` entry

### Architecture & Quality

#### `check_architecture_violations.py`
Validate Clean Architecture compliance.

```bash
# Check for violations
python scripts/check_architecture_violations.py
```

**Checks:**
- CLI layer doesn't access private attributes
- Domain layer has no I/O imports
- Clean Architecture boundaries respected

### Testing

#### `generate_golden_files.py`
Generate test fixtures from rule examples.

```bash
# Generate golden files from rule examples
python scripts/generate_golden_files.py

# Custom output directory
python scripts/generate_golden_files.py --output-dir tests/golden/custom

# Dry run (preview only)
python scripts/generate_golden_files.py --dry-run

# Get help
python scripts/generate_golden_files.py --help
```

Creates:
- Input files (`*_input.txt`) containing test prompts
- Expected output files (`*_expected.json`) with detection results

#### `validate_schemas.py`
Validate RAXE data structures against JSON schemas.

```bash
# Validate all schemas and fixtures
python scripts/validate_schemas.py --all

# Validate specific rule file
python scripts/validate_schemas.py --rule path/to/rule.yaml

# Validate event JSON
python scripts/validate_schemas.py --event path/to/event.json

# Validate all test fixtures
python scripts/validate_schemas.py --fixtures

# Validate all schema files
python scripts/validate_schemas.py --schemas

# Get help
python scripts/validate_schemas.py --help
```

### Maintenance

#### `cleanup_cache.sh`
Clean build artifacts and cache directories.

```bash
# Clean all caches
./scripts/cleanup_cache.sh
```

**Removes:**
- `__pycache__/` directories
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `*.pyc`, `*.pyo` files
- `.coverage` files
- `htmlcov/` directory
- `dist/` and `build/` directories

#### `cleanup_for_public.sh`
Prepare repository for public release.

```bash
# Run cleanup (creates backup first!)
./scripts/cleanup_for_public.sh
```

**⚠️ WARNING**: This script deletes internal files. Always:
1. Commit all current work
2. Create backup branch: `git checkout -b pre-public-release-backup`
3. Tag current state: `git tag backup-before-cleanup`

**Removes:**
- Internal development directories
- Virtual environments
- Cache directories
- Internal documentation
- Build artifacts

## Development Workflow

### Quick Start
```bash
# Install development dependencies
pip install -e ".[dev]"

# Run architecture checks
python scripts/check_architecture_violations.py

# Run benchmarks
python scripts/benchmark.py

# Generate test fixtures
python scripts/generate_golden_files.py

# Validate schemas
python scripts/validate_schemas.py --all
```

### Before Committing
```bash
# Clean caches
./scripts/cleanup_cache.sh

# Check architecture
python scripts/check_architecture_violations.py

# Validate schemas
python scripts/validate_schemas.py --all
```

### Release Process
```bash
# 1. Bump version
python scripts/bump_version.py minor

# 2. Update CHANGELOG.md with actual changes

# 3. Run benchmarks
python scripts/benchmark.py

# 4. Test installation
./scripts/benchmark_install.sh

# 5. Commit and tag
git commit -am "chore: bump version to X.Y.Z"
git tag vX.Y.Z
git push && git push --tags
```

## Requirements

Most scripts require:
- Python 3.10+
- RAXE installed (`pip install -e .`)

Additional dependencies for specific scripts:
- `psutil` for memory benchmarks
- `pytest` for test generation
- `pyyaml` for rule validation

## Internal Scripts

Internal development scripts (not for public distribution) are located in `internal_scripts/`. These include:
- Dataset analysis tools
- Training data processors
- One-off maintenance scripts
- Internal rule management tools

## Contributing

When adding new scripts:
1. Add proper `--help` documentation with `argparse`
2. Include usage examples in docstring
3. Update this README
4. Add executable permissions for shell scripts: `chmod +x scripts/your_script.sh`
5. Follow existing naming conventions

## Support

For issues or questions:
- **Documentation**: [GitHub README](https://github.com/raxe-ai/raxe-ce)
- **Issues**: [github.com/raxe-ai/raxe-ce/issues](https://github.com/raxe-ai/raxe-ce/issues)
