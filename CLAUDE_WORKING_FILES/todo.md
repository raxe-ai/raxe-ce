# Session TODO: Repository Structure Setup
**Date**: 2025-11-14
**Session ID**: claude/setup-repo-structure-01YUtC9fcrqQHmXBgFguxM6n
**Agent**: tech-lead (structure setup)

## Session Goal
Create the complete raxe-ce repository structure following Clean/Hexagonal architecture with plugin support, ensuring all follow-on tasks have a solid foundation.

## Context
- **Repository**: raxe-ce (RAXE Community Edition)
- **Architecture**: Clean/Hexagonal with Domain-Driven Design
- **Philosophy**: Privacy-first, developer-friendly, AGI safety focused
- **Approach**: Create scaffolding now, full implementation incrementally via tasks

## Tasks Completed
- [x] Created CLAUDE_WORKING_FILES structure
- [ ] Created src/raxe core package structure
- [ ] Created test directory structure
- [ ] Created configuration files
- [ ] Created examples directory
- [ ] Created scripts directory
- [ ] Created docs directory
- [ ] Created .github workflows
- [ ] Created folder README.md files
- [ ] Created main README.md
- [ ] Created contributing documentation
- [ ] Verified against CLAUDE.md

## Structure Overview

```
raxe-ce/
├── CLAUDE_WORKING_FILES/     # Claude's working directory
│   ├── REPORTS/              # Session reports, analysis
│   ├── TEST/                 # Test data, experiments
│   └── MISC/                 # Other working files
│
├── src/raxe/                 # Main package (Clean Architecture)
│   ├── domain/               # PURE - NO I/O
│   ├── application/          # Use cases, orchestration
│   ├── infrastructure/       # I/O implementations
│   ├── cli/                  # Click CLI commands
│   ├── sdk/                  # Python SDK for users
│   └── utils/                # Shared utilities
│
├── tests/                    # >80% coverage required
│   ├── unit/                 # Fast, isolated tests
│   ├── integration/          # Integration tests
│   ├── performance/          # Benchmarks
│   └── golden/               # Regression tests
│
├── docs/                     # Documentation
├── examples/                 # Usage examples
├── scripts/                  # Development scripts
└── .github/                  # CI/CD workflows
```

## Key Principles
1. **Domain Layer Purity**: NO I/O operations in domain/
2. **Privacy-First**: Hash PII, never log prompts
3. **Clean Architecture**: Dependencies point inward
4. **Developer Experience**: <60s to first detection
5. **AGI Safety Mission**: Visibility before governance

## Next Steps After This Session
1. Implement domain layer (threat detection, rule engine)
2. Add infrastructure layer (SQLite, cloud API)
3. Build CLI commands
4. Create SDK wrappers
5. Add test suites

## Notes
- Configuration files use flexible version specifiers
- WASM plugin structure as placeholder for later
- Focus on CE (Community Edition) features first
- All scaffolding ready for incremental implementation
