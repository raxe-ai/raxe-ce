# Security Policy

## Reporting Security Vulnerabilities

**We take security seriously.** If you discover a security vulnerability in RAXE CE, please help us responsibly disclose it.

### ⚠️ DO NOT

- **Do NOT** open a public GitHub issue
- **Do NOT** discuss the vulnerability publicly
- **Do NOT** exploit the vulnerability

### ✅ DO

**Report vulnerabilities privately to:** security@raxe.ai

Please include:

1. **Description** - What is the vulnerability?
2. **Impact** - What could an attacker do?
3. **Reproduction** - Step-by-step instructions
4. **Environment** - OS, Python version, RAXE version
5. **Suggested fix** - If you have ideas

### Our Commitment

We will:

- **Acknowledge** your report within 48 hours
- **Investigate** and validate the issue
- **Fix** confirmed vulnerabilities in priority order
- **Credit** you in release notes (if desired)
- **Keep you updated** throughout the process

### Response Times

| Severity | Initial Response | Fix Target |
|----------|-----------------|------------|
| Critical | 24 hours | 7 days |
| High | 48 hours | 14 days |
| Medium | 1 week | 30 days |
| Low | 2 weeks | 90 days |

## Severity Levels

### Critical

- Remote code execution
- Authentication bypass
- Data leakage of PII/secrets
- SQL injection
- Privilege escalation

### High

- Denial of service (DoS)
- XSS or injection vulnerabilities
- Insecure defaults
- Cryptographic failures

### Medium

- Information disclosure (non-PII)
- Missing security headers
- Weak encryption
- CSRF vulnerabilities

### Low

- Security misconfiguration
- Verbose error messages
- Missing rate limiting

## Supported Versions

We provide security updates for:

| Version | Supported |
|---------|-----------|
| 0.1.x   | ✅ Yes    |
| < 0.1   | ❌ No     |

Once v1.0 is released, we will support the latest major version + one prior version.

## Security Best Practices

### For Users

**When using RAXE CE:**

1. **Keep updated** - Update to the latest version regularly
2. **Protect API keys** - Never commit API keys to version control
3. **Review telemetry** - Understand what data is sent (see README)
4. **Use HTTPS** - Always use encrypted connections
5. **Validate inputs** - Don't trust user input blindly

**Environment variables:**
```bash
# Store sensitive values in .env (NOT in code)
RAXE_API_KEY=your_secret_key_here
```

**Never commit:**
- API keys
- Passwords
- Certificates
- Private keys

### For Contributors

**When contributing code:**

1. **No secrets in code** - Use environment variables
2. **Parameterized queries** - Prevent SQL injection
3. **Input validation** - Validate all user input
4. **Dependency scanning** - Run `bandit` before committing
5. **Minimal permissions** - Request only needed permissions

**Pre-commit checks:**
```bash
# Security scan
bandit -r src/raxe

# Dependency check
pip-audit

# Secret detection
detect-secrets scan
```

## Security Features in RAXE CE

### Privacy-First Design

- **Local scanning** - Detection happens on your machine
- **PII hashing** - Prompts are hashed before transmission
- **Configurable telemetry** - You control what's sent
- **No prompt storage** - We never store raw prompts

### Secure Defaults

- **Fail open** - If RAXE fails, your app continues (configurable)
- **Rate limiting** - Prevents abuse
- **Circuit breaker** - Graceful degradation under load
- **Encrypted transmission** - All cloud communication uses TLS

### Data Protection

**What we hash:**
```python
# SHA-256 hash of prompts (one-way, irreversible)
prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()
```

**What we send:**
- Hashed prompts (SHA-256)
- Rule IDs that matched
- Severity scores
- Timestamps
- Environment metadata (OS, Python version)

**What we NEVER send:**
- Raw prompts
- User PII
- API keys
- Source code
- Private data

## Vulnerability Disclosure Timeline

1. **Day 0** - Vulnerability reported
2. **Day 1-2** - Acknowledgment sent
3. **Day 3-7** - Investigation and validation
4. **Day 7-14** - Fix developed and tested
5. **Day 14-21** - Coordinated disclosure with reporter
6. **Day 21+** - Public disclosure and CVE assignment

## Hall of Fame

We recognize security researchers who responsibly disclose vulnerabilities:

*No vulnerabilities reported yet. Be the first!*

## Security Contacts

- **Email:** security@raxe.ai
- **PGP Key:** Available at https://raxe.ai/pgp
- **Bug Bounty:** Coming soon

## CVE Information

We assign CVEs for all security vulnerabilities. Check:
- [GitHub Security Advisories](https://github.com/raxe-ai/raxe-ce/security/advisories)
- [NIST NVD](https://nvd.nist.gov/)

## Security Audit History

| Date | Auditor | Scope | Report |
|------|---------|-------|--------|
| TBD | TBD | Full | Coming |

We are planning a comprehensive third-party security audit before v1.0 release.

## Compliance

RAXE CE is designed to support:

- **GDPR** - Privacy by design, data minimization
- **SOC 2** - Security controls and audit logging
- **ISO 27001** - Information security management
- **OWASP Top 10** - Secure coding practices

## Additional Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

---

**Thank you for helping keep RAXE CE and our users safe!** 🛡️
