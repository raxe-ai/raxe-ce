# CLAUDE.md

**RAXE Community Edition** - AI security platform for LLM threat detection.

```
Language: Python 3.10+ | Architecture: Clean/Hexagonal | License: Proprietary
Core: 460+ YAML rules (L1) + ML classifier (L2) | Privacy: Local-first, never transmit prompts
```

## Development Workflow (REQUIRED)

**Every task follows: PREPARE → PLAN → EXECUTE → VERIFY → DOCUMENT**

### 1. PREPARE (Understand Before Acting)
- Read relevant files BEFORE proposing changes
- Use `ultrathink` for complex architectural decisions
- Check existing patterns in similar files
- Identify test files that need updating

### 2. PLAN (Think Before Coding)
- For non-trivial changes, use `think hard` to evaluate approaches
- Break complex tasks into atomic, testable steps
- Identify edge cases and failure modes upfront
- Write test cases BEFORE implementation (TDD)

### 3. EXECUTE (Code with Discipline)
- One logical change per commit
- Follow existing patterns in the codebase
- Type hints required on all functions
- No I/O in domain layer (`src/raxe/domain/`)

### 4. VERIFY (Test Before Committing)
```bash
pytest tests/unit -v --tb=short        # Fast feedback
ruff check src/ --fix && ruff format src/  # Lint/format
mypy src/raxe                          # Type check
pytest tests/golden                    # Regression check
```

### 5. DOCUMENT (Update Alongside Code)
- Update docstrings for changed functions
- Update `docs/` if behavior changes
- Update `raxe-ce-docs/` for user-facing changes

## Critical Rules (ZERO TOLERANCE)

### Privacy - NEVER Transmit
```python
# FORBIDDEN in telemetry/logs - will cause security incident
"prompt", "matched_text", "response", "user_id", "ip_address", "system_prompt"
```
**Verify:** `pytest tests/*/test_telemetry*.py -v`

### Architecture - Domain Purity
```
CLI/SDK → Application → Domain (PURE - NO I/O) → Infrastructure
```
Domain layer (`src/raxe/domain/`) must have NO: file I/O, network, database, logging.

## Key Patterns

### AgentScanner (All Integrations Use This)
```
Location: src/raxe/sdk/agent_scanner.py
Pattern: Composition, not inheritance
Default: log-only (on_threat="log") - SAFE DEFAULT
Factory: create_agent_scanner(raxe, config, integration_type="...")
```

### Integration Structure
```
src/raxe/sdk/integrations/{framework}.py
├── {Framework}Config - extends/uses AgentScannerConfig
├── Raxe{Framework}Callback/Guard - composes AgentScanner
├── create_{framework}_handler() - factory function (PREFERRED)
└── Text extraction via extractors.py
```

### Telemetry (CANONICAL)
```
Builder: src/raxe/domain/telemetry/scan_telemetry_builder.py
Schema: docs/SCAN_TELEMETRY_SCHEMA.md
Flush: ensure_telemetry_flushed() at all exit points
```

## Commands

```bash
# Development
pytest tests/unit -v                   # Unit tests
pytest tests/integration               # Integration tests
raxe scan "test prompt"                # Manual test
raxe doctor                            # Health check

# Before commit
pre-commit run --all-files
pytest --cov=raxe --cov-fail-under=80

# After detection rule changes
python scripts/generate_golden_files.py
```

## File Reference

| Purpose | Location |
|---------|----------|
| Core scanner | `src/raxe/sdk/agent_scanner.py` |
| SDK client | `src/raxe/sdk/client.py` |
| Integrations | `src/raxe/sdk/integrations/` |
| Text extractors | `src/raxe/sdk/integrations/extractors.py` |
| Detection rules | `src/raxe/packs/core/v1.0.0/rules/` |
| Telemetry schema | `docs/SCAN_TELEMETRY_SCHEMA.md` |
| Public docs | `../raxe-ce-docs/` |

## Common Mistakes

1. **Blocking by default** - Always use `block_on_threats=False` (log-only) as default
2. **Direct integration imports** - Use factory functions: `create_langchain_handler()`
3. **Hardcoded message formats** - Use `extractors.py` for text extraction
4. **Missing telemetry flush** - Call `ensure_telemetry_flushed()` at exit points
5. **I/O in domain** - Keep `src/raxe/domain/` pure (no file/network/db ops)
6. **Skipping golden tests** - Always run `pytest tests/golden` after detection changes

## Git Conventions

```bash
# Format: <type>(<scope>): <subject>
feat(sdk): add DSPy integration
fix(cli): handle missing config file
test(integrations): add LiteLLM callback tests

# Types: feat, fix, perf, refactor, test, docs, chore, security
```

**DO NOT** include `Co-Authored-By` or `Generated with Claude Code` in commits.

## Triggers

- `think` - Standard extended thinking
- `think hard` - Complex problem analysis
- `think harder` - Deep architectural review
- `ultrathink` - Maximum analysis for critical decisions

## Related Documentation

- Architecture: [docs/architecture.md](docs/architecture.md)
- Integration Guide: [docs/integration_guide.md](docs/integration_guide.md)
- Testing: [docs/testing/](docs/testing/)
- Rules: [docs/CUSTOM_RULES.md](docs/CUSTOM_RULES.md)

---

@.claude/rules/
