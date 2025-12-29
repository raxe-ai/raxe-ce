# RAXE Agentic Integrations - Master Todo

**Version:** 3.0 | **Date:** 2025-12-30 | **Status:** MASTER IMPLEMENTATION DOCUMENT

---

## Git Changes Overview

### Recent Commits (v0.3.1)
```
cbd1080 docs: add architecture diagram showing L1/L2 detection flow
9d04418 docs: update badges to show L1/L2 detection + Gemma ML + local execution
c7166ae docs: update README with badges, accurate output, v0.3.1 beta
ae0bf63 fix: sync __version__ with package version (0.3.1)
7b3aead security: fix ReDoS and tarball path traversal vulnerabilities (v0.3.0)
```

### Uncommitted Changes Summary
- **Modified:** 7 files (1,829 insertions, 1,203 deletions)
- **Untracked:** 27 items (new code, tests, docs)
- **Total Lines Added:** ~8,500+ lines of new code

---

## File Classification

### PUBLIC - Commit These (Core Code)

| File | Lines | Purpose |
|------|-------|---------|
| `src/raxe/sdk/agent_scanner.py` | 1,646 | **CANONICAL** AgentScanner |
| `src/raxe/sdk/integrations/agent_scanner.py` | 457 | Deprecation adapter |
| `src/raxe/sdk/integrations/autogen.py` | 569 | AutoGen integration |
| `src/raxe/sdk/integrations/crewai.py` | 1,043 | CrewAI integration |
| `src/raxe/sdk/integrations/llamaindex.py` | 795 | LlamaIndex integration |
| `src/raxe/mcp/*.py` | 504 | MCP server |
| `src/raxe/integrations/*.py` | ~400 | Registry, availability, utils |

### PUBLIC - Commit These (Tests)

| Directory/File | Lines | Purpose |
|----------------|-------|---------|
| `tests/unit/sdk/integrations/test_*.py` | 3,050 | Unit tests |
| `tests/unit/sdk/test_agent_scanner.py` | 516 | Core tests |
| `tests/unit/agentic/` | ~500 | Agentic unit tests |
| `tests/integration/agentic/` | ~200 | Integration tests |
| `tests/performance/agentic/` | ~100 | Performance tests |
| `tests/security/agentic/` | ~100 | Security tests |
| `tests/golden/fixtures/agentic/` | ~50 | Golden fixtures |

### PUBLIC - Commit These (CI/Docs)

| File | Purpose | Notes |
|------|---------|-------|
| `.github/workflows/test-integrations.yml` | CI workflow | **FIXED** |
| `docs/integrations/AUTOGEN.md` | User docs | PUBLIC |
| `docs/integrations/LLAMAINDEX_INTEGRATION.md` | User docs | PUBLIC |

### LOCAL ONLY - In .gitignore

| Path | Reason |
|------|--------|
| `.agent-workspace/` | Agent analysis files |
| `docs/design/` | Internal design docs |
| `docs/roadmap/` | Internal roadmap |
| `docs/testing/AGENTIC_TESTING_STRATEGY.md` | Internal testing strategy |
| `docs/MCP_SERVER_IMPLEMENTATION_PLAN.md` | Internal implementation plan |
| `docs/AGENTIC_PACKAGING_SPEC.md` | Internal packaging spec |

---

## Critical Decisions (Confirmed)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Canonical AgentScanner** | `src/raxe/sdk/agent_scanner.py` | 1647 lines, modern v2.0, LangChain uses it |
| **HuggingFace default** | Log-only | Safe default, blocking opt-in |
| **Response scanning** | Opt-in only | scan_responses=False |
| **MCP Transport** | stdio only (Phase 1) | Claude Desktop compatible |
| **L2 Detection** | Enabled by default | Better security |

---

## Phase 0: Git Cleanup (COMPLETED)

- [x] **0.1** Add local-only paths to `.gitignore`
- [x] **0.2** Delete `docker/` directory (not ready for deployment)
- [x] **0.3** Fix CI workflow paths (`integrations` -> `sdk/integrations`)
- [x] **0.4** Remove non-existent integrations from CI (openai-agents, anthropic)
- [x] **0.5** Copy this plan to `todo.md` as master document

---

## Phase 1: Security (P0 Blockers)

| ID | Issue | File | Action |
|----|-------|------|--------|
| **P0-1** | MCP input validation | `src/raxe/mcp/server.py` | Add MAX_TEXT_LENGTH, rate limiting |
| **P0-2** | HuggingFace blocking default | `src/raxe/sdk/integrations/huggingface.py:83` | Change `True` -> `False` |
| **P0-3** | Callback PII leak | `src/raxe/sdk/agent_scanner.py:438` | Pass hash, not raw text |

### P0-1 Implementation
```python
# Add to src/raxe/mcp/server.py
MAX_TEXT_LENGTH = 100_000
MAX_CONTEXT_LENGTH = 1_000
RATE_LIMIT_RPM = 60

if len(text) > MAX_TEXT_LENGTH:
    return {"error": "Input too large", "code": "INVALID_INPUT"}
```

### P0-2 Implementation
```python
# Change in huggingface.py:83
raxe_block_on_input_threats: bool = False  # Was True
```

---

## Phase 2: AgentScanner Consolidation (P1)

| ID | Task | File |
|----|------|------|
| **P1-1** | Add ScanMode, MessageType, ScanContext | `src/raxe/sdk/agent_scanner.py` |
| **P1-2** | Create deprecation adapter | `src/raxe/sdk/integrations/agent_scanner.py` |
| **P1-3** | Update AutoGen imports | `src/raxe/sdk/integrations/autogen.py` |
| **P1-4** | Update CrewAI imports | `src/raxe/sdk/integrations/crewai.py` |
| **P1-5** | Fix tool validation bypass | `src/raxe/sdk/agent_scanner.py:1243` |
| **P1-6** | Add telemetry flush | LlamaIndex, CrewAI exit points |
| **P1-7** | MCP rate limiting | `src/raxe/mcp/server.py` |

### P1-1 Implementation (Add to agent_scanner.py)
```python
class ScanMode(str, Enum):
    LOG_ONLY = "log_only"
    BLOCK_ON_THREAT = "block_on_threat"
    BLOCK_ON_HIGH = "block_on_high"
    BLOCK_ON_CRITICAL = "block_on_critical"

class MessageType(str, Enum):
    HUMAN_INPUT = "human_input"
    AGENT_TO_AGENT = "agent_to_agent"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"

@dataclass
class ScanContext:
    message_type: MessageType
    sender_name: str | None = None
    receiver_name: str | None = None
    conversation_id: str | None = None
```

### P1-2 Implementation (Replace integrations/agent_scanner.py)
```python
import warnings
warnings.warn(
    "Import from raxe.sdk.agent_scanner instead. "
    "This module will be removed in v0.5.0",
    DeprecationWarning, stacklevel=2
)
from raxe.sdk.agent_scanner import (
    AgentScanner, ScanConfig as AgentScannerConfig,
    ScanMode, MessageType, ScanContext, ScanType, ToolPolicy,
)
```

---

## Phase 3: Integration Hardening (P2)

| ID | Task | Integration |
|----|------|-------------|
| **P2-1** | Create extractors module | NEW `extractors.py` |
| **P2-2** | Migrate to extractors | LangChain |
| **P2-3** | Migrate to extractors | AutoGen |
| **P2-4** | Migrate to extractors | CrewAI |
| **P2-5** | Migrate to extractors | LlamaIndex |
| **P2-6** | Add async callbacks | LangChain |
| **P2-7** | Add async hooks | AutoGen |
| **P2-8** | Add async callbacks | CrewAI |
| **P2-9** | Add async handlers | LlamaIndex |
| **P2-10** | Thread-safe stats | CrewAI |

---

## Phase 4: Testing & CI

| ID | Task | Priority |
|----|------|----------|
| **P4-1** | Fix CI workflow paths | DONE |
| **P4-2** | Run existing unit tests | HIGH |
| **P4-3** | Verify integration tests | HIGH |
| **P4-4** | Add coverage reporting | MEDIUM |
| **P4-5** | Add performance benchmarks | MEDIUM |

---

## Phase 5: Documentation

| ID | Task | Status |
|----|------|--------|
| **P5-1** | LangChain docs | Missing |
| **P5-2** | CrewAI docs | Missing |
| **P5-3** | AutoGen docs | EXISTS |
| **P5-4** | LlamaIndex docs | EXISTS |
| **P5-5** | API reference | Missing |
| **P5-6** | Quickstart guides | Missing |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| L1 Scan Latency (P95) | <10ms |
| L1+L2 Scan Latency (P95) | <50ms |
| Unit Test Coverage | >90% |
| Integration Test Coverage | >80% |

---

## Execution Checklist

### Day 1 (NOW)
- [x] Phase 0: Git cleanup (.gitignore, CI fixes)
- [ ] Phase 1: P0 security blockers

### Day 2-3
- [ ] Phase 2: AgentScanner consolidation

### Day 4-5
- [ ] Phase 3: Integration hardening (extractors, async)
- [ ] Phase 4: Testing verification

### Week 2
- [ ] Phase 5: Documentation
- [ ] Final review and release prep

---

## P0: Security Blockers (MUST FIX FIRST)

| ID | Issue | File | Effort |
|----|-------|------|--------|
| **P0-1** | MCP input validation missing (memory exhaustion, ReDoS) | `src/raxe/mcp/server.py` | 4h |
| **P0-2** | HuggingFace default blocking (violates safe-default) | `src/raxe/sdk/integrations/huggingface.py:83` | 2h |
| **P0-3** | Callback PII leak (raw text passed to callbacks) | `src/raxe/sdk/agent_scanner.py:438-439` | 4h |

### P0-1: MCP Input Validation
```python
# Add to src/raxe/mcp/server.py
MAX_TEXT_LENGTH = 100_000
MAX_CONTEXT_LENGTH = 1_000
RATE_LIMIT_RPM = 60

# Validate before scanning
if len(text) > MAX_TEXT_LENGTH:
    return {"error": "Input too large", "code": "INVALID_INPUT"}
```

### P0-2: HuggingFace Default Fix
```python
# Change in src/raxe/sdk/integrations/huggingface.py:83
- raxe_block_on_input_threats: bool = True   # OLD
+ raxe_block_on_input_threats: bool = False  # NEW (log-only default)
```

### P0-3: Callback PII Fix
```python
# Callbacks receive hash, not raw text
on_threat_callback(prompt_hash, result)  # NOT on_threat_callback(raw_text, result)
```

---

## P1: Critical Issues (This Sprint)

| ID | Issue | Files | Effort |
|----|-------|-------|--------|
| P1-1 | Consolidate AgentScanner implementations | Multiple | 3d |
| P1-2 | Add ScanMode, MessageType, ScanContext to canonical | `agent_scanner.py` | 4h |
| P1-3 | Create compatibility adapter | `integrations/agent_scanner.py` | 4h |
| P1-4 | Update AutoGen to use canonical | `autogen.py` | 4h |
| P1-5 | Update CrewAI to use canonical | `crewai.py` | 4h |
| P1-6 | Add telemetry flush to exit points | LlamaIndex, CrewAI | 2h |
| P1-7 | MCP rate limiting | `mcp/server.py` | 4h |
| P1-8 | Fix tool validation bypass | `agent_scanner.py:1243` | 4h |

### P1-2: Add Missing Types to Canonical AgentScanner
```python
# Add to src/raxe/sdk/agent_scanner.py after line ~90

class ScanMode(str, Enum):
    LOG_ONLY = "log_only"
    BLOCK_ON_THREAT = "block_on_threat"
    BLOCK_ON_HIGH = "block_on_high"
    BLOCK_ON_CRITICAL = "block_on_critical"

class MessageType(str, Enum):
    HUMAN_INPUT = "human_input"
    AGENT_TO_AGENT = "agent_to_agent"
    AGENT_RESPONSE = "agent_response"
    FUNCTION_CALL = "function_call"
    FUNCTION_RESULT = "function_result"
    SYSTEM = "system"

@dataclass
class ScanContext:
    message_type: MessageType
    sender_name: str | None = None
    receiver_name: str | None = None
    conversation_id: str | None = None
    message_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
```

### P1-3: Compatibility Adapter
```python
# Replace src/raxe/sdk/integrations/agent_scanner.py

import warnings
warnings.warn(
    "Import from raxe.sdk.agent_scanner instead. "
    "This module will be removed in v0.5.0",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from canonical module
from raxe.sdk.agent_scanner import (
    AgentScanner,
    ScanConfig as AgentScannerConfig,  # Alias for compatibility
    ScanMode,
    MessageType,
    ScanContext,
    ScanType,
    ToolPolicy,
)
```

### P1-8: Tool Validation Bypass Fix
```python
# Replace in src/raxe/sdk/agent_scanner.py:1243
import unicodedata
import re

def is_dangerous_tool(tool_name: str) -> bool:
    name_normalized = unicodedata.normalize('NFKD', tool_name.lower())

    if name_normalized in DANGEROUS_TOOL_NAMES:
        return True

    dangerous_patterns = [
        r'\b(shell|bash|exec|eval|ssh)\b',
        r'(run|execute|invoke).*(command|code|script)',
    ]
    return any(re.search(p, name_normalized, re.I) for p in dangerous_patterns)
```

---

## P2: Important Improvements (Next Sprint)

| ID | Issue | Files | Effort |
|----|-------|-------|--------|
| P2-1 | Create unified extractors module | `extractors.py` (NEW) | 1d |
| P2-2 | Migrate LangChain to extractors | `langchain.py` | 4h |
| P2-3 | Migrate AutoGen to extractors | `autogen.py` | 2h |
| P2-4 | Migrate CrewAI to extractors | `crewai.py` | 4h |
| P2-5 | Migrate LlamaIndex to extractors | `llamaindex.py` | 2h |
| P2-6 | Add LangChain async callbacks | `langchain.py` | 1d |
| P2-7 | Add AutoGen async hooks | `autogen.py` | 4h |
| P2-8 | Add CrewAI async callbacks | `crewai.py` | 4h |
| P2-9 | Add LlamaIndex async handlers | `llamaindex.py` | 4h |
| P2-10 | Thread-safe CrewScanStats | `crewai.py:187` | 2h |
| P2-11 | Implement timeout handling | `agent_scanner.py` | 4h |
| P2-12 | Fail-closed option for blocking | All integrations | 4h |

### P2-1: Unified Extractors Module
```python
# NEW: src/raxe/sdk/integrations/extractors.py (~150 lines)

def extract_text_from_message(message: Any) -> str | None:
    """Universal message text extraction."""
    if isinstance(message, str):
        return message
    if hasattr(message, "content"):
        return _extract_content(message.content)
    if isinstance(message, dict):
        return message.get("content") or message.get("text")
    return None

def extract_function_call_text(message: Any) -> str | None:
    """Extract function/tool call for scanning."""
    ...

def is_function_call(message: Any) -> bool:
    """Detect if message is a function call."""
    ...
```

---

## MCP Server Implementation

### Phase 1: Core Infrastructure

| File | Purpose |
|------|---------|
| `src/raxe/mcp/config.py` (NEW) | MCPConfig dataclass |
| `src/raxe/mcp/privacy.py` (NEW) | PrivacyFilter - CRITICAL |
| `src/raxe/mcp/session.py` (NEW) | SessionState tracking |
| `src/raxe/mcp/tools.py` (NEW) | 7 tool handlers |
| `src/raxe/mcp/rate_limiter.py` (NEW) | Rate limiting |

### 7 MCP Tools

| Tool | Latency | Status |
|------|---------|--------|
| `raxe_scan` | <10ms | Implement |
| `raxe_scan_batch` | <100ms | Implement |
| `raxe_check_prompt` | <5ms | Implement |
| `raxe_explain_threat` | <10ms | Implement |
| `raxe_list_rules` | <50ms | Exists |
| `raxe_stats` | <1ms | Implement |
| `raxe_suppress` | <1ms | Implement |

---

## Testing Requirements

### New Tests Required: ~247 tests

| Category | Tests | Priority |
|----------|-------|----------|
| AgentScanner consolidation | 36 | P1 |
| Inconsistent defaults | 11 | P0 |
| Async support | 26 | P2 |
| Message extractors | 44 | P2 |
| MCP security | 23 | P0 |
| Cross-cutting security | 45 | P1 |
| Integration tests | 62 | P1 |

### Critical Security Tests
```python
# tests/security/agentic/test_mcp_security.py
def test_input_length_validation()
def test_rate_limiting()
def test_error_no_information_disclosure()
def test_no_pii_in_responses()

# tests/security/agentic/test_pii_prevention.py
def test_callback_receives_hash_only()
def test_no_raw_text_in_logs()
```

---

## 4-Week Timeline

### Week 1: Foundation & Security (P0 + P1-1 to P1-5)
- Day 1-2: P0 security blockers
- Day 3: Add types to canonical AgentScanner
- Day 4: Create compatibility adapter
- Day 5: Update AutoGen, CrewAI imports

### Week 2: Consolidation Complete + Extractors (P1-6 to P2-5)
- Day 1-2: Remaining P1 tasks (telemetry, rate limiting, tool validation)
- Day 3-5: Create extractors module, migrate integrations

### Week 3: Async Support + Testing (P2-6 to P2-12)
- Day 1-3: Add async callbacks to all integrations
- Day 4-5: Thread safety, timeout, fail-closed

### Week 4: MCP + Documentation
- Day 1-2: Complete MCP tools implementation
- Day 3: Integration and golden tests
- Day 4: Performance tests
- Day 5: Documentation and release prep

---

## Files Summary

### Create (6 files)
- `src/raxe/sdk/integrations/extractors.py`
- `src/raxe/mcp/config.py`
- `src/raxe/mcp/privacy.py`
- `src/raxe/mcp/session.py`
- `src/raxe/mcp/tools.py`
- `src/raxe/mcp/rate_limiter.py`

### Modify (11 files)
- `src/raxe/sdk/agent_scanner.py` - Add types, scan_message(), fix tool validation
- `src/raxe/sdk/integrations/agent_scanner.py` - Replace with adapter + deprecation
- `src/raxe/sdk/integrations/langchain.py` - Use extractors, add async
- `src/raxe/sdk/integrations/autogen.py` - Use canonical AgentScanner
- `src/raxe/sdk/integrations/crewai.py` - Use canonical, thread-safe stats
- `src/raxe/sdk/integrations/llamaindex.py` - Use extractors, telemetry flush
- `src/raxe/sdk/integrations/huggingface.py` - Fix default to log-only
- `src/raxe/mcp/server.py` - Input validation, rate limiting
- `pyproject.toml` - Dependencies, test markers
- `.github/workflows/test-integrations.yml` - Fix paths, matrix (DONE)

---

## Success Criteria (v0.4.0 Release Gate)

### Must Have
- [ ] Single consolidated AgentScanner
- [ ] All P0 security issues fixed
- [ ] All P1 critical issues fixed
- [ ] All integrations default to log-only
- [ ] >85% test coverage for integrations
- [ ] MCP works with Claude Desktop

### Should Have
- [ ] All P2 issues fixed
- [ ] Async support in all integrations
- [ ] Performance benchmarks <10ms P95

---

## Design Decisions (Confirmed)

| Decision | Choice |
|----------|--------|
| Canonical AgentScanner | `src/raxe/sdk/agent_scanner.py` (1647 lines) |
| HuggingFace default | Log-only (with deprecation warning) |
| Response scanning | Opt-in only |
| MCP Transport | stdio only (Phase 1) |
| L2 Detection | Enabled by default |
| Async pattern | Sync-first with async wrappers |

---

## Risk Mitigation

### Risk 1: AgentScanner Breaking Changes
**Impact:** All integrations fail
**Mitigation:**
- Freeze AgentScanner API before integration work
- Use Protocol classes for interfaces
- Backward compatibility tests in CI

### Risk 2: Framework Version Incompatibility
**Impact:** Specific integration fails
**Mitigation:**
- Test against multiple versions in CI matrix
- Document supported versions explicitly
- Use duck typing for optional features

### Risk 3: Performance Regression
**Impact:** User experience degradation
**Mitigation:**
- Baseline benchmarks before changes
- Performance tests in CI
- Alert on >20% regression

### Risk 4: Security Vulnerabilities
**Impact:** Production security risk
**Mitigation:**
- Security review before release
- Fuzzing tool inputs
- Regular dependency updates

---

## Success Metrics

### Performance Targets
| Metric | Target | Measurement |
|--------|--------|-------------|
| L1 Scan Latency (P95) | <10ms | Per-message |
| L1+L2 Scan Latency (P95) | <50ms | Per-message |
| Memory Overhead | <100MB | Per process |
| Cold Start | <500ms | First scan |

### Quality Targets
| Metric | Target |
|--------|--------|
| Unit Test Coverage | >90% per integration |
| Integration Test Coverage | >80% |
| Security Test Coverage | All attack vectors |
| Documentation Coverage | 100% public API |

### Adoption Targets (90 days post-release)
| Metric | Target |
|--------|--------|
| LangChain Downloads | 5,000 |
| AutoGen Downloads | 2,000 |
| CrewAI Downloads | 1,000 |
| LlamaIndex Downloads | 1,000 |

---

## Agent Workspace Files

All detailed analyses saved in `.agent-workspace/`:
- `MASTER_PLAN_SYNTHESIZED.md` - Full 730-line master plan
- `TECH_LEAD_CRITICAL_ISSUES.md` - Architecture analysis
- `BACKEND_DEV_IMPLEMENTATION.md` - Code-level changes
- `SECURITY_ANALYST_REVIEW.md` - Security assessment
- `QA_TESTING_STRATEGY.md` - Testing requirements
- `PLAN_REVIEW_CONTEXT.md` - Context for agents

---

## Quick Reference: File Changes Summary

### Files to Create
| File | Purpose | Lines |
|------|---------|-------|
| `src/raxe/sdk/integrations/extractors.py` | Unified message extraction | ~150 |
| `src/raxe/mcp/config.py` | MCPConfig dataclass | ~50 |
| `src/raxe/mcp/privacy.py` | PrivacyFilter | ~100 |
| `src/raxe/mcp/session.py` | SessionState tracking | ~80 |
| `src/raxe/mcp/tools.py` | 7 tool handlers | ~200 |
| `src/raxe/mcp/rate_limiter.py` | Rate limiting | ~50 |

### Files to Modify
| File | Changes |
|------|---------|
| `src/raxe/sdk/agent_scanner.py` | Add ScanMode, MessageType, ScanContext enums |
| `src/raxe/sdk/integrations/agent_scanner.py` | Replace with deprecation adapter |
| `src/raxe/sdk/integrations/langchain.py` | Use extractors, add async |
| `src/raxe/sdk/integrations/autogen.py` | Update imports to canonical |
| `src/raxe/sdk/integrations/crewai.py` | Update imports to canonical |
| `src/raxe/sdk/integrations/llamaindex.py` | Use extractors, telemetry flush |
| `src/raxe/sdk/integrations/huggingface.py` | Fix default to log-only |
| `src/raxe/mcp/server.py` | Add input validation, rate limiting |
| `.gitignore` | Add `.agent-workspace/` (DONE) |

---

**Phase 0 COMPLETE. Ready to start Phase 1 (P0 Security Blockers).**
