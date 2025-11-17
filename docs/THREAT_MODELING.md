# RAXE Threat Model

## Document Information

**Version**: 1.0
**Last Updated**: 2025-11-17
**Status**: Active
**Owner**: RAXE Security Team

## Executive Summary

This document provides a comprehensive threat model for RAXE (AI Security Engine), analyzing potential security threats, attack vectors, and mitigations for the system. The threat model follows the STRIDE methodology and covers all components from user input to detection output.

## System Overview

### Purpose

RAXE is a privacy-first, local threat detection system for LLM applications that:
- Scans prompts and responses for security threats
- Operates entirely on user infrastructure
- Provides real-time detection (<10ms)
- Maintains user privacy through local processing

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        User Application                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                       RAXE SDK/CLI                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Client     │  │  Decorator   │  │  Wrappers    │      │
│  │   (sync/    │  │  @protect    │  │  (OpenAI,    │      │
│  │    async)    │  │              │  │  Anthropic)  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│                            ▼                                 │
│                  ┌────────────────────┐                      │
│                  │  Scan Pipeline     │                      │
│                  │  (Application)     │                      │
│                  └─────────┬──────────┘                      │
│                            │                                 │
│         ┌──────────────────┼──────────────────┐             │
│         ▼                  ▼                  ▼             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  L1 Engine   │  │  L2 Engine   │  │   Cache      │      │
│  │  (Rules)     │  │  (ML Model)  │  │   System     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            ▼                                 │
│                  ┌────────────────────┐                      │
│                  │   Infrastructure   │                      │
│                  │   - Database       │                      │
│                  │   - Config         │                      │
│                  │   - Telemetry      │                      │
│                  └────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ (Optional)
                  ┌────────────────────┐
                  │  Cloud Telemetry   │
                  │  (Anonymized)      │
                  └────────────────────┘
```

### Trust Boundaries

1. **User Application ↔ RAXE SDK**: User code calls RAXE library
2. **RAXE SDK ↔ Local Filesystem**: Config and database read/write
3. **RAXE SDK ↔ Cloud Services**: Optional telemetry transmission

## Assets

### Critical Assets

| Asset | Value | Confidentiality | Integrity | Availability |
|-------|-------|-----------------|-----------|--------------|
| User prompts/responses | **CRITICAL** | High | High | Medium |
| API keys (LLM providers) | **CRITICAL** | High | High | Low |
| Detection rules | HIGH | Low | High | Medium |
| ML models | HIGH | Low | High | Medium |
| Configuration | MEDIUM | Medium | High | Medium |
| Scan history | MEDIUM | High | Medium | Medium |
| Telemetry data | LOW | Medium | Low | Low |

### Data Flow

```
User Input → [BOUNDARY: User App → RAXE] → SDK Client →
Pipeline → L1/L2 Engines → Result → [BOUNDARY: RAXE → User App] →
User Application

(Optional) Scan Metadata → [BOUNDARY: Local → Cloud] →
Telemetry Service (anonymized hashes only)
```

## STRIDE Threat Analysis

### 1. Spoofing

#### T1.1: Malicious Rule Injection
**Threat**: Attacker injects malicious detection rules to bypass security
**Attack Vector**: Replacing rule files in `~/.raxe/custom_rules/` or `src/raxe/packs/`
**Impact**: HIGH - Could disable detection or cause false positives
**Mitigation**:
- ✅ Schema validation on all rule files
- ✅ YAML safety (no arbitrary code execution)
- ⚠️  File integrity checks (NOT implemented)
- ⚠️  Digital signatures on official rule packs (NOT implemented)

**Recommendation**: Add rule pack signing and verification

#### T1.2: Config File Tampering
**Threat**: Attacker modifies `~/.raxe/config.yaml` to disable detection
**Attack Vector**: Direct file modification with user permissions
**Impact**: MEDIUM - Could disable telemetry, reduce detection coverage
**Mitigation**:
- ✅ Schema validation on config load
- ✅ Fail-safe defaults (detection stays enabled)
- ⚠️  File permission checks (NOT implemented)

**Recommendation**: Add config file integrity monitoring

### 2. Tampering

#### T2.1: Database Manipulation
**Threat**: Attacker modifies SQLite database to hide scan history
**Attack Vector**: Direct access to `~/.raxe/raxe.db`
**Impact**: MEDIUM - Loss of audit trail, hidden threats
**Mitigation**:
- ✅ Parameterized queries (no SQL injection)
- ✅ Schema validation
- ❌ No encryption at rest
- ❌ No database integrity checks

**Recommendation**:
- Implement database encryption (sqlcipher)
- Add integrity verification (checksums)

#### T2.2: ML Model Poisoning
**Threat**: Attacker replaces L2 ML model with poisoned version
**Attack Vector**: Replace model file before download/after download
**Impact**: HIGH - Systematic detection bypass
**Mitigation**:
- ⚠️  Model file validation (basic)
- ❌ No model signing
- ❌ No model integrity verification

**Recommendation**: Implement model signing and hash verification

#### T2.3: ReDoS via Malicious Rules
**Threat**: Attacker submits rules with catastrophic backtracking patterns
**Attack Vector**: Community rule submission
**Impact**: HIGH - Denial of service, unbounded CPU usage
**Mitigation**:
- ✅ Timeout enforcement on all regex (5 seconds)
- ✅ ReDoS pattern detection in validation
- ✅ CI/CD validation pipeline
- ✅ Manual review for community submissions

**Status**: Well-mitigated

### 3. Repudiation

#### T3.1: Scan History Deletion
**Threat**: User or attacker deletes scan logs to hide security incidents
**Attack Vector**: Direct database access or `raxe export --delete`
**Impact**: MEDIUM - Loss of audit trail
**Mitigation**:
- ⚠️  Local-only logs (user controls deletion)
- ⚠️  Optional cloud backup via telemetry
- ❌ No immutable audit log

**Recommendation**: Add optional append-only audit mode

#### T3.2: Telemetry Manipulation
**Threat**: User modifies telemetry data before transmission
**Attack Vector**: Man-in-the-middle on local processes
**Impact**: LOW - Anonymized data only, limited value
**Mitigation**:
- ✅ SHA-256 hashing of sensitive data
- ✅ TLS for transmission
- ✅ User can disable telemetry

**Status**: Acceptable risk

### 4. Information Disclosure

#### T4.1: Prompt Leakage via Logs
**Threat**: User prompts logged to disk in plaintext
**Attack Vector**: Log file access, debug mode
**Impact**: CRITICAL - PII exposure, confidential data leak
**Mitigation**:
- ✅ Structured logging with PII filtering
- ✅ Only hashes stored in database
- ✅ No prompts in logs (unless debug enabled)
- ⚠️  Debug mode can expose prompts

**Recommendation**: Add `--redact-prompts` flag for debug mode

#### T4.2: API Key Exposure
**Threat**: LLM provider API keys leaked via logs or errors
**Attack Vector**: Error messages, verbose logging
**Impact**: CRITICAL - Unauthorized API access, financial loss
**Mitigation**:
- ✅ API keys never logged
- ✅ Exception messages sanitized
- ✅ Environment variable usage recommended
- ✅ Pre-commit hooks prevent key commits

**Status**: Well-mitigated

#### T4.3: Side-Channel via Performance
**Threat**: Timing attacks reveal information about prompts
**Attack Vector**: Measuring scan latency variations
**Impact**: LOW - Limited information leakage
**Mitigation**:
- ✅ Consistent performance across threat types
- ✅ Caching reduces timing variance

**Status**: Acceptable risk

#### T4.4: Telemetry Correlation
**Threat**: Telemetry data correlated to deanonymize users
**Attack Vector**: Statistical analysis of usage patterns
**Impact**: MEDIUM - Privacy compromise
**Mitigation**:
- ✅ SHA-256 hashing (one-way)
- ✅ No IP addresses transmitted (anonymized)
- ✅ No user identifiers
- ⚠️  Temporal patterns could reveal identity

**Recommendation**: Add noise/jitter to telemetry timestamps

### 5. Denial of Service

#### T5.1: Resource Exhaustion via Large Inputs
**Threat**: Attacker sends extremely large prompts to exhaust memory
**Attack Vector**: Malicious or accidental large text inputs
**Impact**: MEDIUM - Process crash, service unavailability
**Mitigation**:
- ⚠️  No input size limit (MISSING)
- ✅ Timeout on regex matching
- ✅ Circuit breaker for L2 model

**Recommendation**: Add max input size limit (e.g., 100KB)

#### T5.2: ReDoS Attack
**Threat**: Crafted inputs trigger catastrophic backtracking
**Attack Vector**: Specific input patterns + vulnerable regex
**Impact**: HIGH - CPU exhaustion, service unavailability
**Mitigation**:
- ✅ 5-second timeout on all patterns
- ✅ ReDoS detection in CI/CD
- ✅ Pattern safety validation

**Status**: Well-mitigated

#### T5.3: Database Filling Attack
**Threat**: Attacker generates unlimited scans to fill disk
**Attack Vector**: Automated scanning without cleanup
**Impact**: MEDIUM - Disk space exhaustion
**Mitigation**:
- ❌ No automatic log rotation
- ❌ No storage quotas
- ❌ No configurable retention policy

**Recommendation**:
- Add automatic log rotation
- Implement configurable retention (7/30/90 days)
- Add storage quota warnings

### 6. Elevation of Privilege

#### T6.1: Arbitrary Code Execution via Rules
**Threat**: Malicious rule executes arbitrary code
**Attack Vector**: YAML deserialization, regex eval
**Impact**: CRITICAL - Full system compromise
**Mitigation**:
- ✅ Safe YAML loader (no `!!python/object`)
- ✅ Rules are pure data (no code execution)
- ✅ Regex compilation only (no eval)

**Status**: Well-mitigated

#### T6.2: Privilege Escalation via Config
**Threat**: Config file grants unintended permissions
**Attack Vector**: Malicious config settings
**Impact**: LOW - Limited privilege model
**Mitigation**:
- ✅ No privileged operations
- ✅ Runs with user permissions only
- ✅ No sudo/root required

**Status**: Not applicable (no privilege model)

## Attack Scenarios

### Scenario 1: Malicious Rule Submission

**Attacker Goal**: Bypass detection for specific attack patterns

**Attack Steps**:
1. Submit community rule via GitHub PR
2. Rule has high confidence but matches benign patterns
3. Rule gets merged and distributed

**Impact**: Users miss real threats, false sense of security

**Mitigations**:
- ✅ Manual review of all rule PRs
- ✅ CI/CD validation (min 5 test cases per rule)
- ✅ Community voting on rules (planned)
- ⚠️  Limited automated testing of effectiveness

**Residual Risk**: MEDIUM - Sophisticated false negatives could slip through

### Scenario 2: Local Database Compromise

**Attacker Goal**: Hide evidence of attacks

**Attack Steps**:
1. Gain local user access (malware, insider)
2. Delete rows from `~/.raxe/raxe.db`
3. Remove evidence of malicious prompts

**Impact**: Loss of audit trail, hidden incidents

**Mitigations**:
- ⚠️  Optional cloud telemetry backup
- ⚠️  File permissions (user-only)
- ❌ No database encryption
- ❌ No integrity verification

**Residual Risk**: HIGH - No defense against privileged local attacker

**Recommendation**: Implement database encryption and integrity checks

### Scenario 3: Model Poisoning Attack

**Attacker Goal**: Degrade L2 detection accuracy

**Attack Steps**:
1. Compromise model download (MITM on HTTP)
2. Replace legitimate model with poisoned version
3. L2 layer systematically misses threats

**Impact**: Reduced detection accuracy, false negatives

**Mitigations**:
- ✅ HTTPS for model downloads
- ⚠️  Basic model file validation
- ❌ No cryptographic verification
- ❌ No model signing

**Residual Risk**: MEDIUM - MITM on HTTPS (rare but possible)

**Recommendation**: Implement model signing with public key pinning

### Scenario 4: Dependency Confusion Attack

**Attacker Goal**: Inject malicious code via supply chain

**Attack Steps**:
1. Publish malicious package "raxe" to PyPI
2. Users mistakenly install malicious package
3. Malicious code exfiltrates prompts

**Impact**: CRITICAL - Full compromise of user data

**Mitigations**:
- ✅ Official package on PyPI with verified author
- ✅ Dependency pinning in requirements
- ⚠️  Dependabot for security updates
- ❌ No SBOM (Software Bill of Materials)

**Residual Risk**: LOW - Established PyPI presence

**Recommendation**: Publish SBOM, consider package signing

## Security Controls

### Implemented Controls

| Control | Type | Effectiveness | Coverage |
|---------|------|---------------|----------|
| Input validation (schema) | Preventive | High | 100% |
| Parameterized queries | Preventive | High | 100% |
| Regex timeout | Preventive | High | 100% |
| ReDoS detection | Detective | High | CI/CD only |
| PII filtering in logs | Preventive | High | 80% |
| API key scrubbing | Preventive | High | 100% |
| TLS for telemetry | Preventive | High | 100% |
| Pre-commit hooks | Preventive | Medium | Dev only |

### Missing Controls (Recommendations)

| Control | Priority | Effort | Impact |
|---------|----------|--------|--------|
| Database encryption at rest | **HIGH** | Medium | HIGH |
| Input size limits | **HIGH** | Low | MEDIUM |
| Config file integrity checks | **HIGH** | Medium | MEDIUM |
| Model signing/verification | MEDIUM | High | HIGH |
| Rule pack signing | MEDIUM | High | MEDIUM |
| Automatic log rotation | MEDIUM | Low | MEDIUM |
| Storage quotas | LOW | Low | LOW |
| Telemetry timestamp jitter | LOW | Low | LOW |

## Data Retention

### Current State

**Problem**: No formal data retention policy

**Risks**:
- Unlimited database growth
- Disk space exhaustion
- Privacy concerns (indefinite storage)
- Compliance issues (GDPR right to deletion)

### Recommended Retention Policy

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| Scan history (hashes) | 30 days | Audit trail |
| Analytics/stats | 90 days | Trend analysis |
| Telemetry (cloud) | 1 year | Long-term patterns |
| Logs (debug) | 7 days | Troubleshooting |
| Cache | Session/TTL | Performance |

**Implementation**: Add `retention_days` config option

## Compliance Considerations

### GDPR (General Data Protection Regulation)

| Requirement | Status | Notes |
|-------------|--------|-------|
| Data minimization | ✅ | Only hashes stored |
| Privacy by design | ✅ | Local-first architecture |
| Right to deletion | ⚠️ | Manual only |
| Data portability | ✅ | Export command |
| Consent | ✅ | Opt-in telemetry |
| Security measures | ⚠️ | No encryption at rest |

**Recommendation**: Add `raxe privacy purge` command for GDPR compliance

### SOC 2 (Service Organization Control 2)

| Control | Status | Notes |
|---------|--------|-------|
| Audit logging | ⚠️ | Local only, deletable |
| Access controls | ❌ | No RBAC |
| Encryption at rest | ❌ | Not implemented |
| Encryption in transit | ✅ | TLS for cloud |
| Change management | ✅ | Git-based |
| Monitoring | ⚠️ | Limited |

**Recommendation**: Not SOC 2 compliant without additional controls

## Residual Risks

### Accepted Risks

1. **Local Attacker Access**: If attacker has local user access, they can modify database/config
   - **Rationale**: Out of scope for local-first tool
   - **Mitigation**: Document security best practices

2. **Sophisticated False Negatives**: Novel attacks may bypass rule-based detection
   - **Rationale**: Inherent limitation of signature-based detection
   - **Mitigation**: L2 ML layer, community rule updates

3. **Timing Side-Channels**: Scan duration may reveal information
   - **Rationale**: Low impact, difficult to exploit
   - **Mitigation**: Consistent performance across threat types

### Risks Requiring Mitigation

1. **Database Encryption** (HIGH)
2. **Input Size Limits** (HIGH)
3. **Config Integrity** (HIGH)
4. **Model Verification** (MEDIUM)
5. **Log Rotation** (MEDIUM)

## Security Roadmap

### Phase 1: Critical (Q1 2025)
- [ ] Database encryption at rest (sqlcipher)
- [ ] Input size limits (100KB default)
- [ ] Config file integrity checks (checksums)
- [ ] Data retention policy implementation

### Phase 2: Important (Q2 2025)
- [ ] Model signing and verification
- [ ] Rule pack signing
- [ ] Automatic log rotation
- [ ] SBOM generation

### Phase 3: Enhancement (Q3 2025)
- [ ] Append-only audit mode
- [ ] RBAC for team features
- [ ] Enhanced telemetry anonymization
- [ ] Security audit by third party

## Incident Response

### Security Vulnerability Disclosure

**Process**:
1. Report sent to security@raxe.ai
2. Acknowledged within 48 hours
3. Severity assessment (CRITICAL/HIGH/MEDIUM/LOW)
4. Fix developed and tested
5. Coordinated disclosure with reporter
6. CVE assignment if applicable
7. Public disclosure

**Response SLAs**:
- Critical: 24h response, 7-day fix
- High: 48h response, 14-day fix
- Medium: 1 week response, 30-day fix
- Low: 2 week response, 90-day fix

## References

- [STRIDE Threat Modeling](https://docs.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats)
- [OWASP Threat Modeling](https://owasp.org/www-community/Threat_Modeling)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
- [RAXE Security Policy](SECURITY.md)

---

**Document Review Schedule**: Quarterly (Jan, Apr, Jul, Oct)
**Next Review**: 2025-02-17
**Approver**: RAXE Security Team
