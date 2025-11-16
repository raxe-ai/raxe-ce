# RAXE Packaging & Distribution Guide

Quick reference for package optimization, building, and distribution.

## Package Performance Requirements

- Package size: <10MB (currently 135KB wheel, 113KB sdist)
- Installation time: <30 seconds
- Import time: <1 second
- Python support: 3.10, 3.11, 3.12

## Quick Commands

### Build Package

```bash
# Build both wheel and source distribution
python -m build

# Build wheel only
python -m build --wheel

# Build sdist only
python -m build --sdist

# Check package size
ls -lh dist/
```

### Test Package Locally

```bash
# Run installation benchmarks
./scripts/benchmark_install.sh

# Manual test in clean environment
python -m venv test_env
source test_env/bin/activate
pip install dist/*.whl
python -c "from raxe import Raxe; print('OK')"
deactivate
rm -rf test_env
```

### Publish to TestPyPI

```bash
# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ raxe
```

### Publish to PyPI

```bash
# Check package
twine check dist/*

# Upload to PyPI (production)
twine upload dist/*
```

## Package Structure

```
dist/
├── raxe-0.1.0-py3-none-any.whl  # Universal Python wheel
└── raxe-0.1.0.tar.gz             # Source distribution
```

## What's Included in Package

### Included Files
- All Python source code (src/raxe/**/*.py)
- YAML rule packs (src/raxe/packs/**/*.yaml)
- Type hints marker (py.typed)
- Essential docs (README.md, LICENSE)

### Excluded Files
- Test files (tests/**)
- Documentation (docs/**)
- Examples (examples/**)
- Scripts (scripts/**)
- Build artifacts (*.pyc, __pycache__)
- Development config (.github/, .pre-commit-config.yaml)

## Package Size Optimization

### Current Size Breakdown

```bash
# Analyze wheel contents
unzip -l dist/*.whl

# Count files by type
unzip -l dist/*.whl | grep -E "\.(py|yaml)$" | wc -l
```

### Optimization Techniques

1. **Exclude Development Files**
   - Edit `MANIFEST.in`
   - Update `pyproject.toml` exclusions

2. **Minimize Dependencies**
   - Keep core dependencies minimal
   - Use optional dependencies for extras

3. **Compress Static Assets**
   - Compress large YAML files if needed
   - Use efficient data formats

4. **Remove Compiled Files**
   - Ensure no .pyc or .pyo files included
   - Clean __pycache__ directories

## Dependency Management

### Core Dependencies

Minimal set required for basic functionality:

```toml
dependencies = [
    "click>=8.0,<9.0",
    "pydantic>=2.0,<3.0",
    "httpx>=0.24,<1.0",
    "structlog>=23.0,<25.0",
    "python-dotenv>=1.0,<2.0",
    "sqlalchemy>=2.0,<3.0",
    "aiosqlite>=0.19,<1.0",
    "pyyaml>=6.0,<7.0",
]
```

### Optional Dependencies

Features that require additional packages:

```bash
# Install with OpenAI support
pip install raxe[wrappers]

# Install all optional features
pip install raxe[all]

# Install development dependencies
pip install raxe[dev]
```

## Multi-Platform Support

### Supported Platforms

- Linux (x86_64, aarch64)
- macOS (x86_64, arm64/Apple Silicon)
- Windows (x64)

### Testing on Different Platforms

GitHub Actions workflow tests on:
- Ubuntu Latest (Linux)
- macOS Latest (macOS)
- Windows Latest (Windows)

Across Python versions: 3.10, 3.11, 3.12

## Installation Benchmarks

Run benchmarks to verify performance:

```bash
./scripts/benchmark_install.sh
```

Expected results:
- Package size: <10MB (PASS at 135KB)
- Fresh install: <30s
- With dependencies: <60s
- Import time: <500ms

## Version Management

### Bump Version

```bash
# Patch version (0.1.0 -> 0.1.1)
python scripts/bump_version.py patch

# Minor version (0.1.0 -> 0.2.0)
python scripts/bump_version.py minor

# Major version (0.1.0 -> 1.0.0)
python scripts/bump_version.py major

# Specific version
python scripts/bump_version.py 1.2.3
```

### Version Locations

Version is stored in:
- `pyproject.toml`: `version = "x.y.z"`
- `src/raxe/__init__.py`: `__version__ = "x.y.z"`
- `CHANGELOG.md`: Release entries

## CI/CD Integration

### Automated Workflows

1. **Build Wheels** (`.github/workflows/build-wheels.yml`)
   - Triggered on: push, PR, tags
   - Builds wheels for all platforms
   - Validates package size
   - Tests installation

2. **Release** (`.github/workflows/release.yml`)
   - Triggered on: GitHub release
   - Validates code quality
   - Publishes to TestPyPI
   - Tests TestPyPI installation
   - Publishes to PyPI
   - Creates release notes

### GitHub Secrets Required

Set these in repository settings:

- `PYPI_API_TOKEN`: Production PyPI token
- `TEST_PYPI_API_TOKEN`: TestPyPI token

## Troubleshooting

### Package Too Large

```bash
# Find large files
unzip -l dist/*.whl | sort -k1 -n -r | head -20

# Check for test files
unzip -l dist/*.whl | grep -i test

# Rebuild after fixing exclusions
rm -rf dist/ build/ src/*.egg-info
python -m build
```

### Installation Too Slow

```bash
# Check dependency resolution time
pip install --verbose dist/*.whl

# Test with minimal dependencies
pip install --no-deps dist/*.whl
```

### Import Errors

```bash
# Verify package contents
unzip -l dist/*.whl | grep __init__.py

# Check installed files
pip show -f raxe

# Test import
python -c "import raxe; print(dir(raxe))"
```

## Best Practices

### Before Every Release

1. Clean build artifacts
   ```bash
   rm -rf dist/ build/ src/*.egg-info
   ```

2. Run full test suite
   ```bash
   pytest --cov=raxe --cov-fail-under=80
   ```

3. Build fresh package
   ```bash
   python -m build
   ```

4. Run benchmarks
   ```bash
   ./scripts/benchmark_install.sh
   ```

5. Test installation
   ```bash
   python -m venv test_env
   source test_env/bin/activate
   pip install dist/*.whl
   python -c "from raxe import Raxe; r = Raxe()"
   deactivate
   ```

### Security Checklist

- [ ] No secrets in package
- [ ] No API keys in code
- [ ] Dependencies scanned for vulnerabilities
- [ ] Package signed (if applicable)
- [ ] Security scan passed

### Quality Checklist

- [ ] Version bumped correctly
- [ ] CHANGELOG.md updated
- [ ] Tests passing (80%+ coverage)
- [ ] Linting passed (ruff)
- [ ] Type checking passed (mypy)
- [ ] Package size verified
- [ ] Installation tested

## Additional Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [Building and Distributing Packages](https://setuptools.pypa.io/en/latest/userguide/index.html)
- [PyPI Publishing](https://pypi.org/help/)
- [Twine Documentation](https://twine.readthedocs.io/)

## Support

For packaging issues:
- GitHub Issues: https://github.com/raxe-ai/raxe-ce/issues
- Documentation: https://docs.raxe.ai
- Email: devops@raxe.ai
