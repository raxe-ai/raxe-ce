# CLAUDE.md - AI Assistant Guide for raxe-ce

## Project Overview

**Project Name:** raxe-ce (raxe Community Edition)
**Organization:** raxe.ai
**License:** MIT
**Primary Language:** Python
**Status:** Initial development phase

This is a Python-based project by raxe.ai. The repository is currently in its initial setup phase.

## Repository Structure

### Current Structure
```
raxe-ce/
├── .git/                 # Git version control
├── .gitignore           # Python-specific gitignore
├── LICENSE              # MIT License
├── README.md            # Project readme
└── CLAUDE.md            # This file - AI assistant guide
```

### Expected Future Structure
As the project develops, expect to see:
```
raxe-ce/
├── src/                 # Main source code
│   └── raxe_ce/        # Python package
├── tests/              # Test suite
├── docs/               # Documentation
├── scripts/            # Utility scripts
├── examples/           # Usage examples
├── .github/            # GitHub workflows
├── pyproject.toml      # Project metadata and dependencies
├── requirements.txt    # Python dependencies (if not using pyproject.toml)
├── setup.py           # Package setup (legacy or for compatibility)
├── README.md          # Project documentation
├── LICENSE            # MIT License
└── CLAUDE.md          # This guide
```

## Development Environment Setup

### Prerequisites
- Python 3.8+ (check project requirements as they develop)
- pip or alternative package manager (poetry, pdm, uv, pipenv)
- Git
- Virtual environment tool (venv, virtualenv, conda)

### Initial Setup
```bash
# Clone the repository
git clone https://github.com/raxe-ai/raxe-ce.git
cd raxe-ce

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies (once they exist)
pip install -r requirements.txt
# OR if using pyproject.toml:
pip install -e .
# OR if using poetry:
poetry install
```

## Python Development Conventions

### Code Style
The .gitignore suggests support for multiple tools. Follow these guidelines:

1. **Code Formatting:**
   - Use Black or Ruff for code formatting
   - Line length: 88 characters (Black default) or 120 (common alternative)
   - Follow PEP 8 style guidelines

2. **Type Checking:**
   - Use type hints for function signatures
   - Consider using mypy, pytype, or pyre for static type checking

3. **Import Organization:**
   - Standard library imports first
   - Third-party imports second
   - Local application imports third
   - Use absolute imports over relative imports when possible

4. **Naming Conventions:**
   - `snake_case` for functions, variables, and module names
   - `PascalCase` for class names
   - `UPPER_CASE` for constants
   - Private methods/variables prefix with `_`

### Code Quality Tools
The project .gitignore indicates support for:
- **Ruff:** Modern, fast Python linter and formatter
- **mypy:** Static type checker
- **pytest:** Testing framework (indicated by .pytest_cache)
- **coverage:** Code coverage measurement

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=raxe_ce --cov-report=html

# Run specific test file
pytest tests/test_specific.py

# Run with verbose output
pytest -v
```

### Test Organization
- Place tests in `tests/` directory
- Mirror source structure in tests
- Name test files with `test_` prefix
- Name test functions with `test_` prefix
- Use fixtures for common test setup

## Git Workflow

### Branch Strategy
- `main` or `master`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: New features
- `bugfix/*`: Bug fixes
- `hotfix/*`: Urgent production fixes
- `claude/*`: AI assistant working branches

### Commit Conventions
Follow conventional commits format:
```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

Example:
```
feat(api): add user authentication endpoint

Implements JWT-based authentication with refresh tokens.
Includes middleware for protected routes.

Closes #123
```

### Git Commands Reference
```bash
# Create and switch to new branch
git checkout -b feature/your-feature-name

# Stage changes
git add .

# Commit with message
git commit -m "feat: your feature description"

# Push to remote
git push -u origin feature/your-feature-name

# Pull latest changes
git pull origin main

# Rebase on main
git fetch origin
git rebase origin/main
```

## Dependency Management

The .gitignore supports multiple Python dependency managers:

### pip (Traditional)
```bash
# Install from requirements.txt
pip install -r requirements.txt

# Generate requirements.txt
pip freeze > requirements.txt
```

### Poetry (Modern, Recommended for Libraries)
```bash
# Initialize
poetry init

# Add dependency
poetry add package-name

# Install dependencies
poetry install

# Update dependencies
poetry update
```

### PDM (Modern, PEP 582)
```bash
# Initialize
pdm init

# Add dependency
pdm add package-name

# Install dependencies
pdm install
```

### UV (Ultra-fast Package Installer)
```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt
```

## Common Development Tasks

### Setting Up Pre-commit Hooks
```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

### Building and Packaging
```bash
# Build package
python -m build

# Install locally in development mode
pip install -e .
```

### Documentation
```bash
# If using Sphinx
cd docs
make html

# If using MkDocs
mkdocs serve
```

## AI Assistant Guidelines

### When Working on This Project

1. **Always Check Current State:**
   - Read relevant files before making changes
   - Check for existing tests before adding features
   - Review recent commits to understand context

2. **Follow Python Best Practices:**
   - Write type hints for new functions
   - Add docstrings (Google, NumPy, or Sphinx style)
   - Maintain test coverage for new code
   - Keep functions focused and modular

3. **Documentation:**
   - Update README.md when adding major features
   - Add inline comments for complex logic
   - Update this CLAUDE.md as the project evolves
   - Document all public APIs

4. **Testing Requirements:**
   - Write tests for new features
   - Ensure tests pass before committing
   - Maintain or improve code coverage
   - Include both unit and integration tests

5. **Code Review Checklist:**
   - [ ] Code follows project style guidelines
   - [ ] Type hints are present
   - [ ] Docstrings are added
   - [ ] Tests are written and passing
   - [ ] No security vulnerabilities introduced
   - [ ] Error handling is appropriate
   - [ ] No unnecessary dependencies added
   - [ ] Documentation is updated

6. **Security Considerations:**
   - Never commit sensitive data (.env files, credentials)
   - Validate all user inputs
   - Use parameterized queries for database operations
   - Follow OWASP guidelines for web security
   - Keep dependencies updated for security patches

7. **Performance:**
   - Profile code for bottlenecks before optimizing
   - Use appropriate data structures
   - Consider memory usage for large datasets
   - Add caching where appropriate

### Project-Specific Patterns

As the project develops, document common patterns here:

#### Architecture Patterns
(To be filled in as architecture emerges)

#### Error Handling
```python
# Prefer specific exceptions
class RaxeException(Exception):
    """Base exception for raxe-ce"""
    pass

class ValidationError(RaxeException):
    """Raised when validation fails"""
    pass
```

#### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Detailed information for debugging")
logger.info("General informational messages")
logger.warning("Warning messages")
logger.error("Error messages")
logger.critical("Critical issues")
```

## Environment Variables

Document environment variables as they are added:

```bash
# Example .env file structure (DO NOT COMMIT)
# RAXE_API_KEY=your_api_key
# RAXE_DATABASE_URL=postgresql://localhost/raxe
# RAXE_DEBUG=true
```

## Framework-Specific Guidelines

### If Using Django
- Follow Django's project structure
- Use Django ORM for database operations
- Implement migrations for schema changes
- Use Django's built-in authentication
- Keep settings modular (settings/base.py, settings/dev.py, etc.)

### If Using Flask
- Use application factory pattern
- Organize code with blueprints
- Use Flask-SQLAlchemy for ORM
- Implement proper error handlers
- Use environment-based configuration

### If Using FastAPI
- Use Pydantic models for validation
- Implement proper dependency injection
- Document APIs with OpenAPI
- Use async/await where appropriate
- Implement proper exception handlers

## Database Migrations

### Alembic (SQLAlchemy)
```bash
# Create migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

### Django
```bash
# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create empty migration
python manage.py makemigrations --empty app_name
```

## Continuous Integration

When CI/CD is set up, typical workflow:
```yaml
# .github/workflows/test.yml example
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=raxe_ce
      - run: ruff check .
```

## Troubleshooting

### Common Issues

**Import Errors:**
```bash
# Ensure package is installed in development mode
pip install -e .

# Check PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

**Test Failures:**
```bash
# Clear pytest cache
pytest --cache-clear

# Run tests with verbose output
pytest -vv
```

**Dependency Conflicts:**
```bash
# Create fresh virtual environment
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Resources

### Python Documentation
- [Python Official Docs](https://docs.python.org/3/)
- [PEP 8 Style Guide](https://peps.python.org/pep-0008/)
- [Type Hints (PEP 484)](https://peps.python.org/pep-0484/)

### Testing
- [pytest Documentation](https://docs.pytest.org/)
- [unittest Documentation](https://docs.python.org/3/library/unittest.html)

### Tools
- [Ruff](https://docs.astral.sh/ruff/)
- [Black](https://black.readthedocs.io/)
- [mypy](https://mypy.readthedocs.io/)
- [Poetry](https://python-poetry.org/)

## Changelog

### 2025-11-14
- Initial CLAUDE.md created
- Repository initialized with Python .gitignore
- MIT License added

---

**Last Updated:** 2025-11-14
**Document Version:** 1.0.0
**Maintainer:** AI assistants working on raxe-ce

**Note:** This document should be updated as the project evolves. When adding new features, patterns, or conventions, update this guide to help future contributors (human and AI) understand the project.
