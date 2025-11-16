# RAXE CE Architecture

## Overview

RAXE CE follows Clean/Hexagonal Architecture principles with strict separation of concerns.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI / SDK Layer                         │
│              (Click commands, Public API)                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Application Layer                          │
│        (Use cases, orchestration, workflows)                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Domain Layer (PURE - NO I/O)                   │
│    • ThreatDetector (pure functions)                        │
│    • RuleEngine (stateless logic)                           │
│    • ScanResult (value objects)                             │
│    • NO database, NO network, NO filesystem                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                Infrastructure Layer                         │
│    • SQLite persistence                                     │
│    • HTTP client for cloud API                              │
│    • File I/O for configs                                   │
│    • Telemetry sender                                       │
└─────────────────────────────────────────────────────────────┘
```

## Domain Layer - CRITICAL RULES

The domain layer is **PURE** - it contains zero I/O operations:

✅ **Allowed:**
- Pure functions (input → output)
- Stateless transformations
- Business logic
- Validations
- Rule matching

❌ **Forbidden:**
- Database calls
- Network requests
- File system access
- Logging with side effects
- Any I/O operation

## Data Flow

### Threat Detection Flow

```
User Prompt
    ↓
SDK/CLI Layer
    ↓
Application Layer (scan_prompt use case)
    ↓
Domain Layer (pure detection logic)
    ↓
Application Layer (orchestration)
    ↓
Infrastructure Layer (save to queue)
    ↓
Background Worker (batch send to cloud)
```

## More Documentation

- [API Reference](api_reference.md) - Public API documentation
- [Development Guide](development.md) - Contributing guidelines
- [Integration Guide](integration_guide.md) - How to integrate RAXE

*Full architecture documentation will be expanded as implementation progresses.*
