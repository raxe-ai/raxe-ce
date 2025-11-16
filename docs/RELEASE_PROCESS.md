# RAXE Release Process

This document describes the complete release process for RAXE Community Edition, from version bumping to PyPI publishing.

## Overview

RAXE uses semantic versioning (MAJOR.MINOR.PATCH) and automated releases via GitHub Actions. The release process is designed to be safe, auditable, and fast.

## Version Numbering

- **MAJOR**: Breaking changes (e.g., 1.0.0 → 2.0.0)
- **MINOR**: New features, backward compatible (e.g., 1.0.0 → 1.1.0)
- **PATCH**: Bug fixes, backward compatible (e.g., 1.0.0 → 1.0.1)

## Prerequisites

Before releasing, ensure:

- [ ] All tests pass on `main` branch
- [ ] Code coverage is ≥80%
- [ ] Security scans pass
- [ ] CHANGELOG.md is up to date
- [ ] Documentation is updated
- [ ] No uncommitted changes

## Release Workflow

### 1. Prepare Release

```bash
# Ensure you're on main and up to date
git checkout main
git pull origin main

# Run full test suite
pytest --cov=raxe --cov-fail-under=80

# Run linting and type checking
ruff check src/ tests/
mypy src/raxe

# Run security scan
bandit -r src/raxe -ll
```

### 2. Bump Version

Use the version bump script:

```bash
# For a patch release (0.1.0 → 0.1.1)
python scripts/bump_version.py patch

# For a minor release (0.1.0 → 0.2.0)
python scripts/bump_version.py minor

# For a major release (0.1.0 → 1.0.0)
python scripts/bump_version.py major

# Or set a specific version
python scripts/bump_version.py 1.2.3
```

This script will:
- Update `pyproject.toml`
- Update `src/raxe/__init__.py`
- Add entry to `CHANGELOG.md`

### 3. Update CHANGELOG

Edit `CHANGELOG.md` and fill in the actual changes:

```markdown
## [1.0.0] - 2025-11-15

### Added
- New threat detection rule for XYZ
- Support for Python 3.12

### Changed
- Improved scan performance by 30%
- Updated dependencies

### Fixed
- Bug in telemetry queue overflow handling
```

### 4. Commit and Tag

```bash
# Review changes
git diff

# Commit version bump
git add .
git commit -m "chore: bump version to 1.0.0"

# Create tag
git tag v1.0.0

# Push to GitHub
git push origin main
git push origin v1.0.0
```

### 5. Create GitHub Release

1. Go to https://github.com/raxe-ai/raxe-ce/releases
2. Click "Draft a new release"
3. Select the tag you just created (v1.0.0)
4. Click "Generate release notes" (GitHub will auto-generate)
5. Edit the notes to match CHANGELOG.md format
6. Click "Publish release"

This will trigger the automated release workflow.

### 6. Automated Release Process

Once you publish the GitHub release, the following happens automatically:

1. **Validation** (5 min)
   - Run linting (ruff)
   - Run type checking (mypy)
   - Run tests with coverage
   - Run security scan (bandit)

2. **Build** (2 min)
   - Build wheel and source distribution
   - Verify package size (<10MB)
   - Check package contents

3. **TestPyPI Publish** (2 min)
   - Publish to TestPyPI
   - Wait for package availability
   - Test installation from TestPyPI

4. **PyPI Publish** (2 min)
   - Publish to production PyPI
   - Package is now publicly available

5. **Release Notes** (1 min)
   - Auto-generate detailed release notes
   - Update GitHub release

**Total time: ~12 minutes from tag to PyPI**

### 7. Verify Release

After the workflow completes:

```bash
# Create fresh environment
python -m venv test_release
source test_release/bin/activate

# Install from PyPI
pip install raxe==1.0.0

# Verify installation
python -c "from raxe import Raxe; print(Raxe.__version__)"
raxe --version

# Test basic functionality
python -c "from raxe import Raxe; r = Raxe(); r.scan('test')"

# Cleanup
deactivate
rm -rf test_release
```

### 8. Announce Release

After verifying the release:

- [ ] Post to Discord/Slack
- [ ] Update documentation site
- [ ] Tweet announcement (if applicable)
- [ ] Update README badges

## Manual Release (Fallback)

If automated release fails, you can release manually:

```bash
# Build distribution
python -m build

# Check distribution
twine check dist/*

# Upload to TestPyPI first
twine upload --repository testpypi dist/*

# Test installation
pip install --index-url https://test.pypi.org/simple/ raxe

# Upload to PyPI
twine upload dist/*
```

## Hotfix Release

For urgent fixes to production:

```bash
# Create hotfix branch from tag
git checkout -b hotfix/1.0.1 v1.0.0

# Make fix
# ... edit files ...

# Test thoroughly
pytest

# Bump patch version
python scripts/bump_version.py patch

# Commit
git commit -am "fix: critical security issue in XYZ"

# Merge to main
git checkout main
git merge hotfix/1.0.1

# Tag and push
git tag v1.0.1
git push origin main
git push origin v1.0.1

# Create GitHub release (triggers automation)
```

## Pre-release (Beta/RC)

For beta or release candidate versions:

```bash
# Bump to beta version
python scripts/bump_version.py 1.0.0-beta.1

# Follow normal release process

# In GitHub release, check "This is a pre-release"
```

## Package Size Optimization

If package exceeds 10MB:

1. **Check what's included**:
   ```bash
   unzip -l dist/*.whl | less
   ```

2. **Common culprits**:
   - Test files (exclude in MANIFEST.in)
   - Large ML models (host separately)
   - Documentation (exclude from package)
   - Build artifacts (.pyc, __pycache__)

3. **Update exclusions**:
   - Edit `MANIFEST.in`
   - Edit `pyproject.toml` exclude patterns

4. **Rebuild and verify**:
   ```bash
   rm -rf dist/ build/
   python -m build
   ls -lh dist/
   ```

## Installation Speed Optimization

Target: <30 seconds install time

1. **Minimize dependencies**:
   - Keep core dependencies minimal
   - Move optional features to extras

2. **Use version ranges**:
   - Allow pip to reuse cached packages
   - Don't pin to exact versions unless necessary

3. **Test installation time**:
   ```bash
   ./scripts/benchmark_install.sh
   ```

## Rollback Procedure

If a release has critical issues:

1. **Yank the release from PyPI**:
   ```bash
   # This makes the version unavailable for new installs
   # but doesn't break existing installations
   twine upload --repository pypi --skip-existing --yanked "Critical bug" dist/*
   ```

2. **Create hotfix release** (see Hotfix Release above)

3. **Communicate**:
   - Update GitHub release notes
   - Post announcement
   - Document issue in CHANGELOG

## Troubleshooting

### Build fails with "package too large"

- Check `MANIFEST.in` exclusions
- Verify `pyproject.toml` exclude patterns
- Run `scripts/benchmark_install.sh` for detailed report

### PyPI upload fails with "version already exists"

- You cannot replace a version once uploaded
- Bump to next patch version
- Use pre-release suffix if needed (1.0.1-post1)

### Tests pass locally but fail in CI

- Check Python version differences
- Ensure dependencies are properly pinned
- Check for environment-specific issues

### TestPyPI installation test fails

- TestPyPI may have different dependency versions
- Use `--extra-index-url https://pypi.org/simple/` to fallback to PyPI

## GitHub Secrets Required

The automated release requires these secrets:

- `PYPI_API_TOKEN`: PyPI API token for publishing
- `TEST_PYPI_API_TOKEN`: TestPyPI API token for testing

To create tokens:

1. Go to https://pypi.org/manage/account/
2. Scroll to "API tokens"
3. Click "Add API token"
4. Name: "RAXE GitHub Actions"
5. Scope: "Project: raxe"
6. Copy token and add to GitHub secrets

## Monitoring

After release, monitor:

- PyPI download stats: https://pypistats.org/packages/raxe
- GitHub release page for feedback
- Issue tracker for bug reports
- Discord/community channels

## Checklist Template

Use this checklist for each release:

```markdown
## Release vX.Y.Z Checklist

### Pre-release
- [ ] All tests pass
- [ ] Coverage ≥80%
- [ ] Security scans pass
- [ ] CHANGELOG.md updated
- [ ] Version bumped
- [ ] Documentation updated

### Release
- [ ] Tag created
- [ ] GitHub release published
- [ ] CI/CD completed successfully
- [ ] PyPI package published

### Post-release
- [ ] Installation verified
- [ ] Basic functionality tested
- [ ] Release announced
- [ ] Documentation updated
```

## Additional Resources

- [Semantic Versioning](https://semver.org/)
- [PyPI Publishing Guide](https://packaging.python.org/tutorials/packaging-projects/)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github)
- [Twine Documentation](https://twine.readthedocs.io/)

## Support

For release issues:
- GitHub Issues: https://github.com/raxe-ai/raxe-ce/issues
- Discord: #releases channel
- Email: devops@raxe.ai
