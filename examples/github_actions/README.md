# GitHub Actions Integration with RAXE

Automated security scanning in CI/CD pipeline.

## Features

- Scan all prompts in codebase
- Block PRs with security threats
- Automated PR comments
- Scan result artifacts

## Setup

1. Copy `raxe-scan.yml` to `.github/workflows/`
2. Copy `scan_prompts.py` to `.github/scripts/`
3. Push to trigger workflow

## Workflow

The action will:
1. Scan all Python files for prompt strings
2. Check each prompt for security threats
3. Upload scan results as artifact
4. Comment on PR if threats found
5. Fail workflow if threats detected

## Local Testing

```bash
python scan_prompts.py
```

## Configuration

Edit `raxe-scan.yml` to customize:
- Trigger events
- Python version
- Severity thresholds

## Learn More

- [GitHub Actions Docs](https://docs.github.com/actions)
- [RAXE Documentation](https://docs.raxe.ai)
