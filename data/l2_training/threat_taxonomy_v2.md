# RAXE CE Threat Taxonomy v2.0
## Advanced Security Detection Framework

**Version:** 2.0.0
**Date:** 2025-11-16
**Research Sources:** Protect AI, Lakera Guard, CalypsoAI, OWASP LLM Top 10 2025, Microsoft MSRC

---

## Overview

This document defines the comprehensive threat taxonomy for RAXE CE's two-layer detection system, incorporating the latest research and attack techniques from leading AI security organizations.

## Detection Layer Architecture

### Layer 1 (L1): Pattern-Based Detection
- **Technology:** Regex pattern matching with YAML-based rules
- **Performance:** <5ms execution time
- **Coverage:** 220+ detection rules across 7 categories
- **Strength:** High precision for known attack patterns
- **Limitation:** Cannot detect semantic/contextual threats

### Layer 2 (L2): ML-Based Detection
- **Technology:** DistilBERT multi-task learning architecture
- **Performance:** <100ms execution time
- **Coverage:** 8 threat families with semantic understanding
- **Strength:** Detects novel attacks and contextual threats
- **Limitation:** Requires training data and careful tuning

---

## Threat Family Taxonomy

### 1. BENIGN (Family 0)
**Description:** Legitimate, safe interactions with no malicious intent

**Sub-categories:**
- Educational queries
- Technical questions
- Code assistance
- General conversation
- Documentation requests

**Examples:**
- "How does base64 encoding work?"
- "Can you help debug my Python code?"
- "Explain the difference between supervised and unsupervised learning"

---

### 2. PROMPT_INJECTION (Family 4)
**Description:** Attempts to override, manipulate, or bypass the AI's instructions

**OWASP Ranking:** #1 in OWASP LLM Top 10 2025

**Sub-categories:**

#### 2.1 Direct Prompt Injection
- **Classic instruction override:** "Ignore all previous instructions"
- **System prompt extraction:** "Reveal your system prompt"
- **Delimiter breaking:** "End of system prompt, new instructions:"

#### 2.2 Indirect Prompt Injection ⭐ NEW
- **Markdown exfiltration:** Malicious markdown image tags with data in URLs
- **Hidden instructions:** White text, zero-width characters, HTML comments
- **External data poisoning:** Malicious content in emails, web pages, documents
- **Self-replicating prompts:** Instructions that propagate across sessions

**Research Findings:**
- Indirect injection is the #1 reported vulnerability to Microsoft (2025)
- OpenAI: "Prompt injection remains an unsolved security problem"
- 50ms median detection time required for production systems (Lakera)

#### 2.3 Spotlighting Bypass ⭐ NEW
- Attempts to break out of delimiter-based isolation
- Override of context boundaries
- Microsoft Spotlighting evasion techniques

#### 2.4 Multimodal/Visual Injection ⭐ NEW
- Instructions hidden in images (invisible layers, steganography)
- Cross-modal exploitation (text-image interaction manipulation)
- File metadata poisoning

#### 2.5 Agentic Attacks ⭐ NEW
- **Inter-agent trust exploitation:** Impersonating trusted AI agents
- **Privilege escalation:** Bypassing agent-specific security boundaries
- **Multi-agent propagation:** Self-spreading attack vectors

**Research Finding:** Agent-to-agent attacks have 84.6% success rate vs 46.2% for direct injection (CMU, 2025)

#### 2.6 RAG Poisoning ⭐ NEW
- Database injection of malicious retrieval content
- Backdoor instructions in knowledge bases
- Persistent attack payloads in vector stores

**Detection Patterns:**
```regex
(?i)ignore\s+(all\s+)?previous\s+instructions
!\[.*?\]\(https?://.*ngrok.*data=.*\)
<span\s+style=["\']color:\s*white["\']>.*ignore.*</span>
```

---

### 3. JAILBREAK (Family 3)
**Description:** Attempts to make the AI adopt unrestricted personas or bypass safety training

**Sub-categories:**

#### 3.1 Classic Jailbreaks
- **DAN (Do Anything Now):** 12+ variants documented
- **STAN/Developer Mode:** Roleplay-based unrestricted modes
- **Evil Confidant:** Adversarial persona creation

**Effectiveness (2025):** ASR of 7.5-9.2% (down from 40%+ in 2023)

#### 3.2 Multi-Turn Attacks ⭐ NEW
- **Crescendo:** Gradual escalation from benign to harmful (avg 5 turns)
- **Derail:** Self-discovered clues for progressive jailbreaking
- **Conversational prompts:** Extended dialogue exploitation

**Research Finding:** Multi-turn attacks achieve 3-5x higher success rates than single-turn (USENIX Security 2025)

#### 3.3 Sequential Break ⭐ NEW
- Embedding jailbreaks in step-by-step instructions
- Evasion of detection mechanisms through sequencing
- Multi-stage attack chains

**Research Finding:** SequentialBreak evades state-of-the-art defenses with high stealth (arXiv 2411.06426)

#### 3.4 Advanced Roleplay ⭐ NEW
- Character development with unrestricted attributes
- Scenario-based ethics override
- Meta-roleplay (roleplaying as jailbreak-resistant AI that then breaks)

#### 3.5 Refusal Suppression ⭐ NEW
- Preventing "I cannot" responses
- Reframing refusals as compliance
- Meta-instructions about refusal behavior

#### 3.6 Token-Level Manipulation ⭐ NEW
- **AutoDAN:** Automated jailbreak generation (250% effectiveness increase)
- **Glitch tokens:** Exploiting undefined token behavior
- **Genetic algorithms:** Evolutionary jailbreak optimization

**Detection Patterns:**
```regex
(?i)you.?re\s+now\s+(DAN|in\s+DAN\s+mode)
(?i)let.?s\s+start.*simple.*gradually.*escalate
(?i)step\s+\d+.*ignore.*safety
```

---

### 4. DATA_EXFILTRATION (Family 5)
**Description:** Attempts to leak sensitive data through covert channels

**Sub-categories:**

#### 4.1 Markdown/HTML Exfiltration ⭐ NEW
- Image tags with attacker-controlled domains
- Base64-encoded data in URLs
- Subdomain exfiltration (data.base64.attacker.com)

**Research Finding:** Successful against Perplexity Comet, evaded checks (2025)

#### 4.2 Memory Extraction ⭐ NEW
- Cross-session memory access attempts
- User data leakage from persistent context
- Conversation history exfiltration

**Research Finding:** Successfully demonstrated against ChatGPT memory features (ActiveFence 2025)

#### 4.3 Training Data Extraction ⭐ NEW
- **Special character attacks:** Repeated {, }, @, # trigger memorization
- **Divergence attacks:** Forcing model to "glitch" and leak training data
- **Repeated token attacks:** Token duplication to break output patterns

**Research Finding:** Special characters are stronger memory triggers (arXiv 2405.05990)

#### 4.4 Canary Token Detection
- Attempts to detect honeypot/canary tokens
- Prompt leakage indicators
- Exfiltration channel testing

**Detection Patterns:**
```regex
(?i)encode.*base64.*send.*URL
(?i)reveal.*stored.*memory.*previous.*users
[{}\[\]@#$%&*]{10,}
```

---

### 5. COMMAND_INJECTION (Family 1)
**Description:** Attempts to execute unauthorized commands or code

**Sub-categories:**

#### 5.1 SQL Injection
- DROP, DELETE, TRUNCATE statements
- UNION-based data extraction
- Blind SQL injection patterns

#### 5.2 OS Command Injection
- Shell metacharacters
- Command chaining (;, &&, ||)
- Path traversal attempts

#### 5.3 Tool/Function Manipulation ⭐ NEW
- AI tool calling exploitation
- Function parameter tampering
- Plugin system abuse
- Code execution tool misuse

**Research Finding:** Agentic systems with tools have expanded attack surface

**Detection Patterns:**
```regex
(?i)';?\s*DROP\s+(TABLE|DATABASE)
(?i)call.*tool.*exec.*with.*parameters
```

---

### 6. PII_EXPOSURE (Family 2)
**Description:** Requests or attempts to leak personally identifiable information

**Sub-categories:**
- Email addresses
- Phone numbers
- SSN/National IDs
- Credit card numbers
- Health records
- Biometric data
- API keys and credentials

**Enhanced Detection:** Now includes exfiltration attempt patterns, not just PII presence

---

### 7. BIAS_MANIPULATION (Family 6)
**Description:** Attempts to make the AI produce biased, discriminatory, or unfair outputs

**Sub-categories:**
- Stereotype reinforcement
- Discriminatory decision-making
- Protected class targeting
- Fairness bypass

---

### 8. HALLUCINATION (Family 7)
**Description:** Attempts to force the AI to generate false or fabricated information

**Sub-categories:**
- Citation fabrication
- False expertise claims
- Misinformation generation
- Confidence manipulation

---

## Attack Vector Summary (2025)

### Top 5 Most Critical Threats

1. **Indirect Prompt Injection** (PI)
   - **Risk Level:** CRITICAL
   - **OWASP Rank:** #1
   - **Detection Difficulty:** High (context-dependent)
   - **Impact:** Data exfiltration, unauthorized actions

2. **Multi-Turn Jailbreaks** (JB)
   - **Risk Level:** HIGH
   - **Success Rate:** 3-5x single-turn attacks
   - **Detection Difficulty:** Very High (requires conversation tracking)
   - **Impact:** Complete safety bypass

3. **Memory/Training Data Extraction** (EXFIL)
   - **Risk Level:** CRITICAL
   - **Prevalence:** Increasing with persistent memory features
   - **Detection Difficulty:** Medium
   - **Impact:** Privacy breach, IP theft

4. **Agentic/Inter-Agent Attacks** (PI)
   - **Risk Level:** CRITICAL
   - **Success Rate:** 84.6% (highest of all attack types)
   - **Detection Difficulty:** High
   - **Impact:** Privilege escalation, system compromise

5. **RAG Poisoning** (PI)
   - **Risk Level:** HIGH
   - **Persistence:** Can affect all future queries
   - **Detection Difficulty:** Medium
   - **Impact:** Persistent backdoors, misinformation

### Emerging Techniques to Monitor

- **Visual prompt injection** in multimodal systems
- **Self-replicating prompts** across agent networks
- **AutoDAN and genetic jailbreaks** (automated generation)
- **SequentialBreak** stealth techniques
- **Crescendo** conversational exploitation

---

## Detection Strategy Recommendations

### L1 Pattern-Based Rules
**Best for:**
- Known attack patterns
- High-precision detections
- Fast screening (<5ms)
- Explicit malicious keywords

**Coverage:** 220+ rules across PI, JB, CMD, ENC, PII, RAG, HC

### L2 ML-Based Detection
**Best for:**
- Novel/zero-day attacks
- Semantic threats
- Context-dependent attacks
- Obfuscated patterns

**Model:** DistilBERT multi-task (binary, family, severity, context)

### Combined Pipeline
1. **L1 First:** Fast pattern screening
2. **L2 Selective:** Only if L1 uncertain or for semantic validation
3. **Policy Evaluation:** Business logic and custom rules
4. **Action:** ALLOW, WARN, or BLOCK based on confidence

**Performance Target:** <10ms for 95% of requests (balanced mode)

---

## Validation and Metrics

### L1 Metrics
- **Precision target:** >95%
- **Recall target:** >85%
- **False Positive Rate:** <5%
- **Execution time:** <5ms

### L2 Metrics
- **Precision target:** >90%
- **Recall target:** >80%
- **FPR target:** <5% (improved from 62.8% in v1.0)
- **Execution time:** <100ms

### Combined System
- **Overall Precision:** >93%
- **Overall Recall:** >88%
- **System FPR:** <3%

---

## References

1. **Lakera AI** - Prompt Injection Guide & Guard Platform (2025)
2. **Microsoft MSRC** - Defending Against Indirect Prompt Injection (2025)
3. **OWASP** - Top 10 for LLM Applications (2025)
4. **CalypsoAI** - Security Leaderboard & Red Team Methodologies (2025)
5. **Protect AI** - LLM Guard Security Toolkit (2025)
6. **USENIX Security** - Crescendo Multi-Turn Jailbreak Attack (2025)
7. **arXiv 2411.06426** - SequentialBreak: Embedding Jailbreaks (2024)
8. **arXiv 2310.04451** - AutoDAN: Generating Stealthy Jailbreaks (2024)
9. **arXiv 2405.05990** - Special Characters Attack on Training Data (2024)
10. **Carnegie Mellon University** - When LLMs Autonomously Attack (2025)
11. **ActiveFence** - LLM Memory Exfiltration Red Team (2025)
12. **Simon Willison** - Markdown Exfiltration Research (2024-2025)

---

## Changelog

### Version 2.0.0 (2025-11-16)
- ✨ Added 18+ new L1 detection rules
- ✨ Expanded threat taxonomy with 8 new attack categories
- ✨ Created comprehensive L2 training dataset (30+ examples)
- ✨ Incorporated research from Protect AI, Lakera, CalypsoAI
- ✨ Added OWASP LLM Top 10 2025 alignment
- 📊 New attack vectors: indirect injection, multi-turn, agentic, RAG poisoning
- 📊 Enhanced detection for markdown exfiltration, memory extraction
- 📊 Added token manipulation, refusal suppression patterns

### Version 1.0.0 (2025-11-09)
- Initial release with 202 L1 rules
- Basic L2 multi-task detector
- 7 threat families + benign class
