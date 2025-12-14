# CI/CD Integration Guide

This guide covers integrating RAXE security scanning into your CI/CD pipelines. RAXE can scan LLM prompts, AI-generated content, and configuration files for security threats as part of your automated build process.

## Quick Start

### GitHub Actions (Copy-Paste Ready)

Create `.github/workflows/raxe-scan.yml`:

```yaml
name: RAXE Security Scan
on: [push, pull_request]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install and run RAXE
        run: |
          pip install raxe
          raxe init --force

          # Scan prompts directory using --ci flag
          find ./prompts -name "*.txt" -o -name "*.md" | while read file; do
            echo "Scanning: $file"
            raxe scan --stdin --ci < "$file" || exit 1
          done
        env:
          RAXE_API_KEY: ${{ secrets.RAXE_API_KEY }}
```

### GitLab CI (Copy-Paste Ready)

Add to your `.gitlab-ci.yml`:

```yaml
raxe_security_scan:
  image: python:3.11-slim
  stage: test
  script:
    - pip install raxe
    - raxe init --force
    - |
      find ./prompts -type f \( -name "*.txt" -o -name "*.md" \) | while read file; do
        echo "Scanning: $file"
        raxe scan --stdin --ci < "$file" || exit 1
      done
  artifacts:
    when: always
    paths:
      - raxe-scan-results.json
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

---

## The --ci Flag

RAXE provides a dedicated `--ci` flag for CI/CD environments that enables:

- **JSON output** by default (machine-parseable)
- **No banner/logo** output (cleaner logs)
- **Exit code 1** when threats are detected (for build failures)
- **No color codes** (works in all CI environments)
- **Suppressed verbose output** (even if `--verbose` is set)

**Usage:**
```bash
# Using --ci flag (recommended for CI/CD)
raxe scan "test prompt" --ci

# Equivalent to:
raxe --quiet scan "test prompt" --format json

# Can also be set via environment variable
export RAXE_CI=true
raxe scan "test prompt"
```

---

## GitHub Actions

### Using the Official Template

RAXE provides a comprehensive GitHub Actions workflow template. Copy it from:
`.github/workflows/raxe-scan.yml`

**Features:**
- Automatic Python setup and caching
- Directory and single-file scanning
- PR comments with scan results
- SARIF report generation for GitHub Security tab
- Configurable severity thresholds
- Artifact upload for audit trails

### Basic Configuration

```yaml
name: RAXE Security Scan
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install RAXE
        run: |
          pip install "raxe>=0.2.0"
          raxe --version

      - name: Initialize RAXE
        run: raxe init --force
        env:
          RAXE_API_KEY: ${{ secrets.RAXE_API_KEY }}

      - name: Run security scan
        run: |
          raxe batch ./prompts/test-prompts.txt --format json --output results.json

          # Check for threats
          if jq -e '.threats_found > 0' results.json > /dev/null; then
            echo "Security threats detected!"
            jq '.results[] | select(.has_threats)' results.json
            exit 1
          fi
```

### Advanced Configuration

```yaml
name: RAXE Security Scan

on:
  push:
    branches: [main]
    paths:
      - "prompts/**"
      - "src/ai/**"
  pull_request:
    branches: [main]
  workflow_dispatch:
    inputs:
      scan_path:
        description: "Path to scan"
        default: "./prompts/"
      fail_on_threat:
        description: "Fail on threat detection"
        type: boolean
        default: true

jobs:
  scan:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"

      - name: Install RAXE
        run: pip install "raxe>=0.2.0"

      - name: Initialize RAXE
        run: |
          if [ -n "$RAXE_API_KEY" ]; then
            raxe init --api-key "$RAXE_API_KEY" --force
          else
            raxe init --force
          fi
        env:
          RAXE_API_KEY: ${{ secrets.RAXE_API_KEY }}

      - name: Scan files
        id: scan
        run: |
          SCAN_PATH="${{ github.event.inputs.scan_path || './prompts/' }}"
          FAIL_ON_THREAT="${{ github.event.inputs.fail_on_threat || 'true' }}"

          echo "Scanning: $SCAN_PATH"

          # Run scan with JSON output
          THREATS_FOUND=false
          RESULTS='{"results": []}'

          find "$SCAN_PATH" -type f \( -name "*.txt" -o -name "*.md" -o -name "*.yaml" \) | while read file; do
            RESULT=$(raxe scan --stdin --format json --quiet < "$file")

            if echo "$RESULT" | jq -e '.has_detections' > /dev/null; then
              THREATS_FOUND=true
              echo "Threat found in: $file"
            fi
          done

          echo "threats_found=$THREATS_FOUND" >> $GITHUB_OUTPUT

          if [ "$THREATS_FOUND" = "true" ] && [ "$FAIL_ON_THREAT" = "true" ]; then
            exit 1
          fi
        env:
          RAXE_QUIET: "true"

      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: raxe-scan-results
          path: "*.json"
          retention-days: 30
```

### Scanning on PR Changes Only

```yaml
name: RAXE PR Scan

on:
  pull_request:
    paths:
      - "prompts/**"
      - "**/*.prompt"
      - "**/*.prompt.txt"

jobs:
  scan-changed:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Get changed files
        id: changed
        run: |
          CHANGED=$(git diff --name-only ${{ github.event.pull_request.base.sha }} ${{ github.sha }} | grep -E '\.(txt|md|prompt|yaml)$' || true)
          echo "files=$CHANGED" >> $GITHUB_OUTPUT

      - name: Set up Python and install RAXE
        if: steps.changed.outputs.files != ''
        run: |
          pip install raxe
          raxe init --force

      - name: Scan changed files
        if: steps.changed.outputs.files != ''
        run: |
          echo "${{ steps.changed.outputs.files }}" | while read file; do
            if [ -f "$file" ]; then
              echo "Scanning: $file"
              raxe scan --stdin --format json --quiet < "$file" || exit 1
            fi
          done
```

---

## GitLab CI

### Using the Official Template

RAXE provides GitLab CI templates that you can include directly:

```yaml
# .gitlab-ci.yml
include:
  - local: '/.gitlab/ci-templates/raxe-scan.yml'

stages:
  - test
  - security

# Basic scan
raxe_security_scan:
  extends: .raxe-scan
  stage: security
  variables:
    SCAN_PATH: "./prompts/"
    FAIL_ON_THREAT: "true"
```

### Template Variants

The GitLab templates include several variants:

| Template | Description |
|----------|-------------|
| `.raxe-scan` | Standard scan with artifacts |
| `.raxe-scan-quick` | Fast scan, no artifacts (for MR pipelines) |
| `.raxe-scan-full` | Full scan with SARIF output |
| `.raxe-scan-scheduled` | Nightly/scheduled scans |

### Basic Configuration

```yaml
stages:
  - test
  - security

raxe_security_scan:
  image: python:3.11-slim
  stage: security

  variables:
    SCAN_PATH: "./prompts/"
    FAIL_ON_THREAT: "true"

  before_script:
    - pip install --quiet raxe
    - raxe init --force

  script:
    - |
      find "$SCAN_PATH" -type f \( -name "*.txt" -o -name "*.md" \) | while read file; do
        echo "Scanning: $file"
        raxe scan --stdin --format json --quiet < "$file"
        if [ $? -eq 1 ]; then
          echo "Threat detected in $file"
          if [ "$FAIL_ON_THREAT" = "true" ]; then
            exit 1
          fi
        fi
      done

  artifacts:
    when: always
    paths:
      - raxe-scan-results.json
    expire_in: 30 days

  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
```

### Advanced Configuration with Security Reports

```yaml
raxe_security_scan:
  image: python:3.11-slim
  stage: security

  variables:
    SCAN_PATH: "./prompts/"
    RAXE_API_KEY: $RAXE_API_KEY

  before_script:
    - pip install --quiet raxe jq
    - |
      if [ -n "$RAXE_API_KEY" ]; then
        raxe init --api-key "$RAXE_API_KEY" --force
      else
        raxe init --force
      fi

  script:
    - |
      # Initialize results
      echo '{"results": [], "summary": {}}' > raxe-scan-results.json

      TOTAL_THREATS=0
      FILES_SCANNED=0

      find "$SCAN_PATH" -type f \( -name "*.txt" -o -name "*.md" -o -name "*.yaml" \) | while read file; do
        FILES_SCANNED=$((FILES_SCANNED + 1))
        echo "Scanning: $file"

        RESULT=$(raxe scan --stdin --format json --quiet < "$file" 2>/dev/null || echo '{}')

        # Append to results
        jq --arg file "$file" --argjson result "$RESULT" \
          '.results += [{"file": $file, "result": $result}]' \
          raxe-scan-results.json > tmp.json && mv tmp.json raxe-scan-results.json

        if echo "$RESULT" | jq -e '.has_detections == true' > /dev/null 2>&1; then
          TOTAL_THREATS=$((TOTAL_THREATS + 1))
        fi
      done

      # Update summary
      jq --arg total "$TOTAL_THREATS" --arg scanned "$FILES_SCANNED" \
        '.summary = {"threats_found": ($total | tonumber), "files_scanned": ($scanned | tonumber)}' \
        raxe-scan-results.json > tmp.json && mv tmp.json raxe-scan-results.json

      # Report results
      echo ""
      echo "=========================================="
      echo "Scan Complete"
      echo "=========================================="
      jq '.summary' raxe-scan-results.json

      # Check for failures
      if [ "$TOTAL_THREATS" -gt 0 ]; then
        echo "Security threats detected!"
        jq '.results[] | select(.result.has_detections == true)' raxe-scan-results.json
        exit 1
      fi

  artifacts:
    when: always
    paths:
      - raxe-scan-results.json
    reports:
      sast: raxe-scan-results.json
    expire_in: 30 days
```

---

## Jenkins Pipeline

### Declarative Pipeline

```groovy
pipeline {
    agent {
        docker {
            image 'python:3.11-slim'
        }
    }

    environment {
        RAXE_API_KEY = credentials('raxe-api-key')
        RAXE_QUIET = 'true'
    }

    stages {
        stage('Setup') {
            steps {
                sh '''
                    pip install --quiet raxe
                    raxe --version
                    raxe init --force
                '''
            }
        }

        stage('Security Scan') {
            steps {
                script {
                    def scanPath = './prompts/'
                    def exitCode = sh(
                        script: """
                            find ${scanPath} -type f \\( -name "*.txt" -o -name "*.md" \\) | while read file; do
                                echo "Scanning: \$file"
                                raxe scan --stdin --format json --quiet < "\$file"
                                if [ \$? -eq 1 ]; then
                                    echo "THREAT DETECTED in \$file"
                                    exit 1
                                fi
                            done
                        """,
                        returnStatus: true
                    )

                    if (exitCode == 1) {
                        error('Security threats detected!')
                    } else if (exitCode > 1) {
                        error("Scan failed with exit code: ${exitCode}")
                    }
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: '**/raxe-*.json', allowEmptyArchive: true
        }
        failure {
            echo 'Security scan failed - review the results'
        }
    }
}
```

### Scripted Pipeline

```groovy
node {
    stage('Checkout') {
        checkout scm
    }

    stage('Setup RAXE') {
        sh '''
            pip install raxe
            raxe init --force
        '''
    }

    stage('Security Scan') {
        def result = sh(
            script: '''
                raxe batch ./prompts/test-prompts.txt --format json --output scan-results.json

                # Parse results
                python3 -c "
import json
with open('scan-results.json') as f:
    data = json.load(f)
    if data.get('threats_found', 0) > 0:
        print(f'Found {data[\"threats_found\"]} threats!')
        exit(1)
"
            ''',
            returnStatus: true
        )

        if (result != 0) {
            error('Security threats detected in prompts!')
        }
    }
}
```

---

## Generic CI/CD Integration

For any CI/CD system, follow these steps:

### 1. Install RAXE

```bash
pip install "raxe>=0.2.0"
```

### 2. Initialize Configuration

```bash
# Without API key (basic features)
raxe init --force

# With API key (enhanced features)
raxe init --api-key "$RAXE_API_KEY" --force
```

### 3. Run Scans

**Single file:**
```bash
raxe scan --stdin --format json --quiet < prompt.txt
```

**Batch file (multiple prompts, one per line):**
```bash
raxe batch prompts.txt --format json --output results.json
```

**Directory scan:**
```bash
find ./prompts -name "*.txt" | xargs -I {} sh -c 'raxe scan --stdin --format json --quiet < "{}"'
```

### 4. Parse Results

```bash
# Check if threats were found
if jq -e '.has_detections == true' results.json > /dev/null; then
    echo "Threats detected!"
    exit 1
fi
```

---

## Environment Variables

Configure RAXE behavior through environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `RAXE_API_KEY` | API key for cloud features | None |
| `RAXE_QUIET` | Suppress visual output | `false` |
| `RAXE_NO_COLOR` | Disable colored output | `false` |
| `RAXE_VERBOSE` | Enable detailed logging | `false` |

**Example:**
```bash
export RAXE_QUIET=true
export RAXE_NO_COLOR=true
raxe scan --stdin --format json < prompt.txt
```

---

## Exit Codes

RAXE uses standardized exit codes for CI/CD integration:

| Code | Meaning | Action |
|------|---------|--------|
| `0` | Success - no threats detected | Continue pipeline |
| `1` | Threats detected | Fail build (configurable) |
| `2` | Invalid input | Check arguments/files |
| `3` | Configuration error | Run `raxe init` |
| `4` | Scan error | Check logs |
| `5` | Authentication error | Check API key |

**Shell script example:**
```bash
raxe scan --stdin --format json --quiet < prompt.txt
EXIT_CODE=$?

case $EXIT_CODE in
    0)
        echo "Scan passed - no threats"
        ;;
    1)
        echo "FAILED - Security threats detected"
        exit 1
        ;;
    2)
        echo "ERROR - Invalid input"
        exit 2
        ;;
    3)
        echo "ERROR - Configuration problem"
        raxe init --force
        exit 3
        ;;
    4)
        echo "ERROR - Scan execution failed"
        exit 4
        ;;
    5)
        echo "ERROR - Authentication failed"
        exit 5
        ;;
esac
```

---

## JSON Output Format

When using `--format json`, RAXE outputs structured data:

### Single Scan Result

```json
{
  "has_detections": true,
  "detections": [
    {
      "rule_id": "PI-001",
      "severity": "high",
      "confidence": 0.95,
      "layer": "L1",
      "message": "Prompt injection attempt detected: instruction override pattern"
    },
    {
      "rule_id": "L2-prompt_injection",
      "severity": "high",
      "confidence": 0.87,
      "layer": "L2",
      "message": "ML model detected prompt injection",
      "family": "injection",
      "sub_family": "instruction_override"
    }
  ],
  "duration_ms": 4.23,
  "l1_count": 1,
  "l2_count": 1
}
```

### Batch Scan Result

```json
{
  "total_scanned": 10,
  "threats_found": 2,
  "results": [
    {
      "line": 1,
      "prompt": "Ignore all previous instructions...",
      "has_threats": true,
      "detection_count": 1,
      "highest_severity": "high",
      "duration_ms": 3.45,
      "detections": [
        {
          "rule_id": "PI-001",
          "severity": "high",
          "confidence": 0.92
        }
      ]
    }
  ]
}
```

### Field Reference

| Field | Type | Description |
|-------|------|-------------|
| `has_detections` | boolean | Whether any threats were found |
| `detections` | array | List of detection objects |
| `detections[].rule_id` | string | Unique rule identifier |
| `detections[].severity` | string | `critical`, `high`, `medium`, `low`, `info` |
| `detections[].confidence` | float | Confidence score (0.0-1.0) |
| `detections[].layer` | string | Detection layer (`L1` or `L2`) |
| `detections[].message` | string | Human-readable description |
| `duration_ms` | float | Scan duration in milliseconds |

---

## Best Practices

### 1. Scan Early in Pipeline

```yaml
stages:
  - lint
  - security    # Run RAXE here, before tests
  - test
  - build
  - deploy
```

### 2. Cache Dependencies

```yaml
# GitHub Actions
- uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: raxe-${{ runner.os }}-pip

# GitLab CI
cache:
  key: raxe-pip
  paths:
    - .cache/pip/
```

### 3. Fail Fast on Critical Threats

```bash
# Only fail on high/critical severity
raxe scan --stdin --format json --quiet < prompt.txt > result.json

SEVERITY=$(jq -r '.detections[0].severity // "none"' result.json)
if [ "$SEVERITY" = "critical" ] || [ "$SEVERITY" = "high" ]; then
    exit 1
fi
```

### 4. Save Artifacts for Audit

```yaml
artifacts:
  when: always
  paths:
    - raxe-scan-results.json
  expire_in: 90 days
```

### 5. Use API Key for Enterprise Features

Store `RAXE_API_KEY` as a secret in your CI/CD system:
- GitHub: Settings > Secrets > Actions
- GitLab: Settings > CI/CD > Variables
- Jenkins: Credentials

---

## Troubleshooting

### Common Issues

**"RAXE not initialized"**
```bash
# Solution: Initialize before scanning
raxe init --force
```

**"No files to scan"**
```bash
# Solution: Check path exists and contains scannable files
ls -la ./prompts/
find ./prompts -type f -name "*.txt"
```

**"JSON parsing error"**
```bash
# Solution: Ensure RAXE_QUIET=true to prevent mixed output
export RAXE_QUIET=true
raxe scan --format json --stdin < prompt.txt
```

**"Permission denied"**
```bash
# Solution: Check file permissions
chmod +r ./prompts/*.txt
```

### Debug Mode

```bash
# Enable verbose output for debugging
RAXE_VERBOSE=true raxe scan "test prompt" --format text
```

---

## Support

- Documentation: https://docs.raxe.ai
- GitHub Issues: https://github.com/raxe-ai/raxe-ce/issues
- Enterprise Support: https://raxe.ai/enterprise
