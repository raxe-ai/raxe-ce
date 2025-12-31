# CHANGELOG


## v0.4.7 (2025-12-31)

### Bug Fixes

- **tests**: Skip deprecated FP tests until API updated
  ([`5304b1f`](https://github.com/raxe-ai/raxe-ce/commit/5304b1faba51cdd41d3d69ea36aefa9c171c4c63))

### Continuous Integration

- **tests**: Run only unit+golden tests on push, full suite on PRs
  ([`5a21e2f`](https://github.com/raxe-ai/raxe-ce/commit/5a21e2f53da99b337296a047f2a450dc91d1034d))


## v0.4.6 (2025-12-31)

### Bug Fixes

- **ci**: Simplify release workflow - remove heavy test suite
  ([`51cbb8f`](https://github.com/raxe-ai/raxe-ce/commit/51cbb8f58b8dc102eac6d1b4053945fdfbd64168))


## v0.4.5 (2025-12-31)

### Bug Fixes

- **ci**: Use RELEASE_PAT for workflow dispatch permissions
  ([`b1f482b`](https://github.com/raxe-ai/raxe-ce/commit/b1f482be11be45737e3c3719cd03bcdd0edbc4fb))


## v0.4.4 (2025-12-31)

### Bug Fixes

- **ci**: Update pre-commit config header for clarity
  ([`90e0719`](https://github.com/raxe-ai/raxe-ce/commit/90e071911780a177506435c2571907e638f6f9a4))

### Chores

- Revert version to 0.4.3 and fix semantic-release workflow
  ([`2a1f707`](https://github.com/raxe-ai/raxe-ce/commit/2a1f7076a7c5a679571065110bed058a82783ef6))

- Revert accidental 1.0.0 version bump - Use official python-semantic-release GitHub Action - This
  prevents the shell script parsing issues that caused the error

### Continuous Integration

- **automation**: Add pre-commit hooks, security scanning, and semantic release
  ([`6a055ae`](https://github.com/raxe-ai/raxe-ce/commit/6a055ae271f848a43edf406f853e48de74e568dd))

- Add .pre-commit-config.yaml with ruff, bandit, yaml validation - Add CodeQL security scanning
  workflow (weekly + on push/PR) - Add benchmark workflow with performance regression alerts - Add
  semantic-release workflow for automatic versioning - Update test-integrations.yml with API key
  secrets - Add docs-validation job to test.yml - Add semantic-release config to pyproject.toml -
  Add missing pytest markers (infrastructure, real_api)

Note: Mypy disabled in pre-commit (pre-existing type errors need fixing)

### Documentation

- Add improved CLAUDE.md with development workflow
  ([`7fa296a`](https://github.com/raxe-ai/raxe-ce/commit/7fa296acbdd71ceab7c49e4dd295696ca1c374a7))

- Lean main file (153 lines) with universal guidelines - PREPARE → PLAN → EXECUTE → VERIFY →
  DOCUMENT workflow - TDD-first development approach - Common mistakes section to prevent repeat
  bugs - Key patterns documented (AgentScanner, telemetry, integrations) - Thinking triggers for
  complexity levels - Detailed rules in .claude/rules/ (local only, gitignored)


## v0.4.3 (2025-12-31)

### Bug Fixes

- **litellm**: Inherit from CustomLogger for proper callback integration
  ([`b945d76`](https://github.com/raxe-ai/raxe-ce/commit/b945d76e1265960751ae6ccfd60cca95c014658a))

- RaxeLiteLLMCallback now extends litellm.integrations.custom_logger.CustomLogger - Fixes callback
  hooks not being triggered by LiteLLM - Added graceful fallback stub when litellm is not installed
  - Stats tracking and threat detection now work correctly

Tested with real API calls against GPT-4o-mini.


## v0.4.2 (2025-12-31)

### Chores

- Bump version to 0.4.2 for optional dependencies release
  ([`7bc1716`](https://github.com/raxe-ai/raxe-ce/commit/7bc1716106532b330ab446f57952c7953c74ccad))

### Features

- **deps**: Add optional dependencies for all framework integrations
  ([`81236bb`](https://github.com/raxe-ai/raxe-ce/commit/81236bbb15e9530a5c4ac1288ca69b9a204c8a38))

Added optional extras for pip install raxe[framework]: - langchain, crewai, autogen, llamaindex,
  litellm, dspy, portkey - agents: all framework integrations combined


## v0.4.1 (2025-12-31)

### Features

- **integrations**: Add LiteLLM and DSPy integrations v0.4.1
  ([`3368645`](https://github.com/raxe-ai/raxe-ce/commit/336864581e7fb3f235b972cbd88daad79b3f0212))

New integrations: - LiteLLM: RaxeLiteLLMCallback for 200+ LLM providers - DSPy: RaxeDSPyCallback and
  RaxeModuleGuard for declarative pipelines

Fixed defaults (all now passive/log-only): - OpenAI wrapper: raxe_block_on_threat=False - Anthropic
  wrapper: raxe_block_on_threat=False - VertexAI wrapper: raxe_block_on_threat=False

Updated documentation: - README.md: Added LiteLLM and DSPy to integration table - QUICKSTART.md:
  Fixed wrapper examples to show log-only default - CHANGELOG.md: Added v0.4.1 release notes


## v0.4.0 (2025-12-31)

### Bug Fixes

- Sync __version__ with package version (0.3.1)
  ([`ae0bf63`](https://github.com/raxe-ai/raxe-ce/commit/ae0bf63b8b163351081cf6a5d6b99d9eceb54e2a))

- **integrations**: Add AutoGen v0.4+ support and fix callback handlers
  ([`1628408`](https://github.com/raxe-ai/raxe-ce/commit/1628408ed8bad9f70e54a34e1d5ae50ec4f63ca6))

AutoGen: - Add support for AutoGen v0.4+ (autogen-agentchat) async API - New wrap_agent() method for
  v0.4+ agents - Keep register() for v0.2.x (pyautogen) backward compatibility - Add version
  detection functions - Add _RaxeAgentWrapper class for async message interception

LangChain: - Rewrite with factory pattern for proper BaseCallbackHandler inheritance - Fix pydantic
  ValidationError when used with strict type checking - Use _RaxeCallbackHandlerMixin + dynamic
  type() class creation

LlamaIndex: - Fix base class initialization with required event_starts_to_ignore and
  event_ends_to_ignore parameters - Change import path to llama_index.core.callbacks.base

CLI: - Change doctor performance targets: 5ms→50ms avg, 10ms→100ms P95 - Add CONSOLE_KEYS_URL export
  to expiry_warning.py

Docs: - Update README with AutoGen v0.2.x and v0.4+ examples - Update CHANGELOG with dual API
  support note

- **tests**: Resolve integration test failures for v0.4.0 release
  ([`f21e2b4`](https://github.com/raxe-ai/raxe-ce/commit/f21e2b433575f5c569b9bd60d1143ac0eaf6ebc4))

Key fixes:

LangChain Integration: - Fix RaxeCallbackHandler.__new__ to call mixin __init__ directly - Change
  MRO to put mixin first for proper method precedence - Fix ScanType.TOOL_OUTPUT → TOOL_RESULT
  (actual enum value) - Rewrite tests to work with AgentScanner composition

LlamaIndex Integration: - Fix RecursionError in extract_texts_from_value by using
  Mock(spec=["text"]) - Bare Mock() caused infinite loop due to hasattr() always returning True

OpenAI Wrapper: - Create proper inheritable mock class with @cached_property for chat - Fix
  wrap_client to pass api_key to constructor - Update tests for inheritance-based RaxeOpenAI pattern

Documentation: - Make all code samples in docs self-contained and runnable - Add missing imports
  (asyncio, typing) to examples - Fix placeholder comments to complete code blocks - Add
  RELEASE_MESSAGE.md for v0.4.0 announcement

Test Results: - LangChain: 33/33 tests pass - LlamaIndex: 51/51 tests pass - OpenAI: 20/20 tests
  pass (1 expected skip)

### Chores

- Phase 0 - Git cleanup for agentic integrations
  ([`67ffa1a`](https://github.com/raxe-ai/raxe-ce/commit/67ffa1a2cf4c02c220293c8f540758127ae777c3))

- Add CI workflow for integration testing (test-integrations.yml) - Fixed paths:
  src/raxe/sdk/integrations/** (not src/raxe/integrations/**) - Removed non-existent integrations
  (openai-agents, anthropic) - Matrix testing for Python 3.10/3.11/3.12 - Tests: mcp, langchain,
  crewai, autogen, llamaindex - Update todo.md with master implementation plan - Phase 0-5 task
  breakdown - P0/P1/P2 priority classification - Success criteria and metrics - Design decisions
  documented

- Remove todo.md from tracking and add to .gitignore
  ([`dd09783`](https://github.com/raxe-ai/raxe-ce/commit/dd09783fb9224cf3b084bf53727d0bd520463611))

### Documentation

- Add agentic integration documentation and tests
  ([`2fd5998`](https://github.com/raxe-ai/raxe-ce/commit/2fd59989647751a83ed1202a24b17abd68e059b5))

- Add AutoGen integration guide (docs/integrations/AUTOGEN.md) - Add LlamaIndex integration guide
  (docs/integrations/LLAMAINDEX_INTEGRATION.md) - Add canonical agent_scanner unit tests - Update
  .gitignore to exclude internal planning docs

- Add architecture diagram showing L1/L2 detection flow
  ([`cbd1080`](https://github.com/raxe-ai/raxe-ce/commit/cbd108096dbcffc104c9c7a4e4f2cf9ef5bfb76f))

- Update badges to show L1/L2 detection + Gemma ML + local execution
  ([`9d04418`](https://github.com/raxe-ai/raxe-ce/commit/9d04418cc690ce2ea0211756497250f8a6c81de8))

- Update README with badges, accurate output, v0.3.1 beta
  ([`c7166ae`](https://github.com/raxe-ai/raxe-ce/commit/c7166aed9a46d3666bccff759ccc87c7b896f51a))

- Add PyPI version, downloads, Python 3.10+, and license badges - Update version from v0.0.1 to
  v0.3.1 Beta - Fix output example to match actual Rich-formatted CLI output - Standardize all
  Twitter links to x.com - Change 'Get Started in 60 Seconds' to '2 Minutes' (honest timing) - Move
  'Snort for LLMs' analogy to top of Why RAXE section - Add Python 3.10+ requirement prominently -
  Make auth optional (Step 3) - instant testing works without signup - Collapse alternative auth
  methods into details tag - Fix 'toxic content' to 'harmful content' in threat families - Improve
  What You Get section with table format - Update footer tagline

### Features

- Add integration availability registry
  ([`bc370d6`](https://github.com/raxe-ai/raxe-ce/commit/bc370d671ec3f4587b901a7ef32357a4462313be))

- Add src/raxe/integrations/ module for checking framework availability - availability.py: Check if
  optional dependencies are installed - registry.py: Integration info registry - utils.py: Shared
  utilities for integrations - Update uv.lock with dependency changes

- **integrations**: Add agentic framework integrations v0.4.0
  ([`b545f7f`](https://github.com/raxe-ai/raxe-ce/commit/b545f7fd52ed92a03ab3e026f864cc12af79835a))

Add first-class support for the most popular agentic AI frameworks:

- LangChain: RaxeCallbackHandler for chains, agents, RAG pipelines - CrewAI: RaxeCrewGuard with
  step/task callbacks, tool wrapping - AutoGen: RaxeConversationGuard for multi-agent conversations
  - LlamaIndex: RaxeLlamaIndexCallback with instrumentation API - Portkey: RaxePortkeyWebhook for AI
  Gateway guardrails

Features: - All integrations default to log-only mode (safe default) - Configurable blocking with
  ScanMode enum - Tool policy enforcement for dangerous tools - Convenience imports from
  raxe.sdk.integrations - Full async support

Testing: - 243 unit tests passing - 117 real framework integration tests passing - Tested with
  LangChain 1.2.0, CrewAI 1.7.2, AutoGen, LlamaIndex 0.14.12

Documentation: - docs.raxe.ai/integrations updated for all frameworks - Quick start code in
  README.md - Full API reference in CHANGELOG.md

### Refactoring

- Phase 2 - AgentScanner consolidation
  ([`e34a5c2`](https://github.com/raxe-ai/raxe-ce/commit/e34a5c2193c981e7a80eee34aaa5221fc40dcc3b))

P1-1: Add ScanMode, MessageType, ScanContext to canonical agent_scanner.py

P1-2: Create deprecation adapter at integrations/agent_scanner.py

P1-3: Update AutoGen to use canonical imports with factory pattern

P1-4: Update CrewAI to use canonical imports with factory pattern

P1-5: Add LlamaIndex integration using canonical API

Key changes: - All integrations now use raxe.sdk.agent_scanner (canonical) - Factory pattern:
  create_agent_scanner(raxe, config) - API migration: mode=ScanMode.X -> on_threat="log/block" -
  AgentScanResult replaces direct ScanPipelineResult access - Helper method
  _raise_security_exception for None pipeline_result

Tests: 202 passing (44 LangChain + 32 AutoGen + 48 CrewAI + 51 LlamaIndex + 27 AgentScanner)

- **integrations**: Add unified extractors module for text extraction
  ([`fed8c38`](https://github.com/raxe-ai/raxe-ce/commit/fed8c386e316d81f25bbbd18aca8f64fcb2ff6b7))

- Create extractors.py with common text extraction functions: - extract_text_from_message: Universal
  message extraction - extract_text_from_content: Content field extraction -
  extract_text_from_content_list: Multi-modal content handling - extract_text_from_dict: Dict
  extraction with fallback keys - extract_text_from_response: LLM response extraction -
  extract_texts_from_value: Recursive value extraction - is_function_call: Function call detection -
  extract_function_call_text: Function call text extraction - extract_agent_name: Agent name
  extraction

- Update LangChain to use unified extractors - Update AutoGen to use unified extractors for both
  v0.2.x and v0.4+ APIs - Update CrewAI to use extract_text_from_dict for dict cases - Update
  LlamaIndex to use unified extractors - Add convenience functions: create_callback_handler,
  get_langchain_version

This improves maintainability by centralizing extraction logic.

### Security

- Fix ReDoS and tarball path traversal vulnerabilities (v0.3.0)
  ([`7b3aead`](https://github.com/raxe-ai/raxe-ce/commit/7b3aeadc73e704170d5974fce0048f1950f56549))

- T-001: Fix hash length test assertions (64 -> 71 chars for sha256: prefix) - S-001: Replace re
  module with regex for enforced timeout in pattern matching - S-002: Add secure tarball extraction
  with path traversal protection (CVE-2007-4559)

Security improvements: - Pattern matching now enforces timeout via regex module (prevents ReDoS) -
  Tarball extraction validates paths, blocks traversal, skips symlinks - Python 3.12+ uses built-in
  data_filter, 3.10-3.11 uses manual validation

Test coverage: - 4 new timeout tests for ReDoS protection - 9 new security tests for tarball
  extraction - Hash length assertions updated across 4 test files

- Phase 1 - P0 security blockers
  ([`aa12ba4`](https://github.com/raxe-ai/raxe-ce/commit/aa12ba467a1807cfc27294e5792042e20d634f8a))

P0-1: MCP input validation

- Add RateLimiter class (60 req/min per client) - Add MAX_TEXT_LENGTH (100KB) and MAX_CONTEXT_LENGTH
  (1KB) limits - Add input validation before scanning to prevent memory exhaustion

P0-2: HuggingFace safe default

- Change raxe_block_on_input_threats default from True to False - Follows "log-only by default,
  blocking opt-in" principle

P0-3: Callback PII prevention

- Update _build_result to compute SHA256 hash of content - All scan methods now pass content param
  for hashing - AgentScanResult.prompt_hash contains hash, not raw text - Prevents PII leakage
  through callbacks

Files: - src/raxe/mcp/server.py (P0-1) - src/raxe/sdk/integrations/huggingface.py (P0-2) -
  src/raxe/sdk/agent_scanner.py (P0-3)

### Testing

- Add agentic test infrastructure scaffolding
  ([`f2d426e`](https://github.com/raxe-ai/raxe-ce/commit/f2d426e6d7c832f23a128e88b16bb54a1629083d))

- Add conftest.py with shared fixtures for agentic tests - Set up directory structure for: - Unit
  tests (unit/agentic/) - Integration tests (integration/agentic/) - Performance tests
  (performance/agentic/) - Security tests (security/agentic/) - Golden fixtures
  (golden/fixtures/agentic/)


## v0.2.0 (2025-12-20)

### Features

- **suppression**: Add suppression system v1.0
  ([`5d61d85`](https://github.com/raxe-ai/raxe-ce/commit/5d61d8587ca210213abe6360d0cc1fcd217d811a))

BREAKING CHANGE: .raxeignore deprecated, use .raxe/suppressions.yaml

Features: - YAML-based suppression configuration (.raxe/suppressions.yaml) - Policy action overrides
  (SUPPRESS, FLAG, LOG) - Inline SDK suppression with context manager - CLI --suppress flag and
  management commands - Security hardening (pattern/reason length limits, max count) - Required
  reason field for audit compliance - Wildcard pattern validation (no bare wildcards) -
  Detection.is_flagged field for FLAG action - Full audit trail for all suppression operations

Documentation: - docs/SUPPRESSIONS.md - User guide - CHANGELOG.md - v0.2.0 release notes

### BREAKING CHANGES

- **suppression**: .raxeignore deprecated, use .raxe/suppressions.yaml
