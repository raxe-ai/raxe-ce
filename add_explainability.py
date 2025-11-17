#!/usr/bin/env python3
"""
Script to add explainability documentation to RAXE rules.
Adds risk_explanation, remediation_advice, and docs_url to all rules missing them.
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any


# Category-specific explanation templates
TEMPLATES = {
    "PI": {
        "instruction_override": {
            "risk": "Prompt injection attacks attempt to override system instructions to make the AI ignore its safety guidelines and security controls. This can lead to unauthorized actions, data leakage, bypassing of access controls, or generation of harmful content that violates system policies.",
            "remediation": "Implement robust input validation that detects and blocks instruction override attempts. Use layered prompt engineering with clearly defined boundaries that separate system instructions from user input. Deploy a secondary validation layer to verify responses comply with safety policies.",
        },
        "system_override": {
            "risk": "System override attacks attempt to manipulate the AI into entering privileged operational modes that bypass normal security constraints. This can enable unauthorized access to restricted functionality, exposure of sensitive system information, or execution of dangerous operations.",
            "remediation": "Enforce strict mode controls and never allow user input to modify operational states. Implement authentication and authorization checks before any mode changes. Use allowlisting for valid operational modes and reject any attempts to activate undocumented or privileged modes.",
        },
        "context_manipulation": {
            "risk": "Context manipulation attacks exploit how AI systems process and prioritize information to subvert intended behavior. These attacks can lead to incorrect decisions, bypassed safety checks, or exposure of information that should remain protected.",
            "remediation": "Maintain strict separation between trusted system context and untrusted user input. Implement context validation to detect manipulation attempts. Use structured prompts that clearly delineate different context sources and their trust levels.",
        },
        "multilingual": {
            "risk": "Multilingual prompt injection exploits language processing vulnerabilities to bypass security controls designed primarily for English text. Attackers use non-English languages to evade detection while still achieving malicious objectives like instruction override or data extraction.",
            "remediation": "Deploy multilingual security controls that analyze prompts in all supported languages. Use language-agnostic detection patterns and semantic analysis rather than keyword matching. Ensure safety guidelines are enforced consistently across all languages.",
        },
        "obfuscation": {
            "risk": "Obfuscation techniques disguise malicious prompts to evade detection while retaining their harmful intent. This includes character substitution, homoglyphs, and visual deception that can bypass pattern-based security controls and trick the AI into executing dangerous instructions.",
            "remediation": "Implement normalization of input text to resolve obfuscation before processing. Use visual similarity detection for homoglyphs and character substitutions. Apply semantic analysis that identifies malicious intent regardless of textual representation.",
        },
        "indirect_injection": {
            "risk": "Indirect prompt injection embeds malicious instructions in external content (documents, images, URLs) that the AI processes, allowing attackers to control AI behavior without directly crafting the prompt. This can lead to data exfiltration, unauthorized actions, or system compromise through trusted content channels.",
            "remediation": "Treat all external content as untrusted and apply strict content security policies. Sanitize and sandbox external content before processing. Implement content validation that detects embedded instructions or malicious payloads in documents, images, and other media.",
        },
        "agentic_attack": {
            "risk": "Agentic attacks exploit trust relationships between AI agents or between agents and humans to propagate malicious instructions across system boundaries. These attacks can compromise entire multi-agent systems by leveraging one compromised agent to subvert others.",
            "remediation": "Implement zero-trust architecture for agent-to-agent communications. Validate and sanitize all inter-agent messages. Use authentication and authorization for agent interactions. Monitor agent behavior for anomalies that may indicate compromise.",
        },
        "rag_poisoning": {
            "risk": "RAG poisoning attacks inject malicious content into retrieval systems to manipulate AI responses across multiple interactions. Poisoned data can persist in knowledge bases, affecting many users and enabling long-term control over AI behavior.",
            "remediation": "Implement content validation and provenance tracking for all data sources. Use anomaly detection to identify suspicious content patterns in knowledge bases. Apply access controls and audit logging for knowledge base modifications. Regularly scan for and remove poisoned content.",
        },
        "spotlighting_bypass": {
            "risk": "Spotlighting bypass attacks attempt to evade security controls that mark and isolate untrusted user input. Successfully bypassing these controls allows malicious prompts to be treated as trusted system instructions, enabling full system compromise.",
            "remediation": "Use cryptographically secure delimiters and markers that cannot be forged or bypassed. Implement multiple layers of input validation and sanitization. Monitor for attempts to close, escape, or modify spotlight markers and treat such attempts as high-severity incidents.",
        },
        "multimodal_injection": {
            "risk": "Multimodal prompt injection embeds malicious instructions in images, audio, or other non-text inputs that AI systems process. These attacks exploit the complexity of multimodal processing to hide malicious content that evades text-based security controls.",
            "remediation": "Apply security scanning to all modalities (text, image, audio, video). Use multimodal analysis that detects cross-modal attacks. Implement content security policies for non-text inputs. Validate and sanitize all media before processing.",
        },
        "data_exfiltration": {
            "risk": "Data exfiltration attacks manipulate AI systems to leak sensitive information through external services, side channels, or encoded responses. Successful attacks can expose confidential data, credentials, or system information to unauthorized parties.",
            "remediation": "Implement network egress filtering to block unauthorized outbound connections. Monitor and restrict AI access to sensitive data stores. Use data loss prevention (DLP) controls to detect and block exfiltration attempts. Audit all external service interactions.",
        },
        "social_engineering": {
            "risk": "Social engineering attacks manipulate AI systems using psychological techniques similar to those used against humans. These attacks can trick AI into revealing information, performing unauthorized actions, or bypassing security controls through deception rather than technical exploitation.",
            "remediation": "Train AI systems to recognize and resist social engineering tactics. Implement behavioral analysis to detect manipulation attempts. Use strict policy enforcement that cannot be overridden by persuasive language. Log and review suspicious interaction patterns.",
        },
        "system_prompt_extraction": {
            "risk": "System prompt extraction attacks attempt to reveal the internal instructions and configuration of AI systems. This information can be used to craft more sophisticated attacks, identify vulnerabilities, or reverse-engineer proprietary security controls.",
            "remediation": "Never include sensitive system information in prompts that can be extracted. Use prompt templates that minimize information leakage. Implement output filtering to detect and block system prompt disclosures. Monitor for extraction attempts and update defenses based on observed tactics.",
        },
        "abbreviated_forms": {
            "risk": "Abbreviated attack patterns use shortened forms of malicious instructions to evade keyword-based detection while retaining semantic meaning. Common abbreviations like 'DAN', 'ig prev inst' can bypass simple pattern matching while still triggering harmful behaviors.",
            "remediation": "Expand detection patterns to include common abbreviations and shortened forms. Use semantic analysis that identifies intent regardless of textual format. Maintain a database of known abbreviated attack patterns and update it regularly.",
        },
        "natural_variations": {
            "risk": "Natural language variations of attacks use different phrasing and vocabulary to express malicious intent while appearing benign. These attacks exploit the gap between formal attack patterns and natural language understanding to bypass detection.",
            "remediation": "Deploy semantic analysis that detects malicious intent across varied phrasings. Use AI-based detection models trained on attack variations. Implement behavioral monitoring that identifies harmful outcomes regardless of input phrasing.",
        },
        "combined_patterns": {
            "risk": "Combined pattern attacks use multiple attack techniques simultaneously to overwhelm defenses or exploit gaps between different security controls. These sophisticated attacks are harder to detect and can achieve objectives that individual techniques cannot.",
            "remediation": "Implement holistic security analysis that evaluates entire prompts rather than individual components. Use machine learning models that detect complex attack combinations. Deploy defense-in-depth with multiple overlapping security controls.",
        },
        "obfuscated_spacing": {
            "risk": "Spacing obfuscation uses unusual whitespace, separators, or formatting to disguise malicious keywords while preserving their meaning to the AI. This technique can evade simple pattern matching while still conveying harmful instructions.",
            "remediation": "Normalize whitespace and formatting before security analysis. Implement pattern matching that is resilient to spacing variations. Use n-gram analysis and fuzzy matching to detect obfuscated patterns.",
        },
    },
    "JB": {
        "role_playing": {
            "risk": "Role-playing jailbreaks manipulate AI systems into adopting personas or characters that lack normal safety constraints. By framing requests as creative fiction or character roleplay, attackers bypass ethical guidelines and generate harmful content that would otherwise be blocked.",
            "remediation": "Maintain consistent safety policies regardless of roleplay context. Implement content filtering that evaluates outputs based on actual harm rather than fictional framing. Reject requests that explicitly invoke unrestricted or unethical personas.",
        },
        "named_jailbreaks": {
            "risk": "Named jailbreak techniques invoke well-known attack patterns (DAN, KEVIN, etc.) that have documented success in bypassing AI safety controls. These attacks leverage established methods that may have exploited vulnerabilities in earlier AI systems.",
            "remediation": "Maintain an updated database of known jailbreak names and patterns. Implement specific detection and blocking for documented jailbreak techniques. Monitor for new named jailbreaks and update defenses accordingly. Never allow activation of named bypass modes.",
        },
        "hypothetical_scenarios": {
            "risk": "Hypothetical scenario framing attempts to bypass safety controls by presenting harmful requests as theoretical exercises or thought experiments. This technique exploits the AI's willingness to engage with abstract concepts to generate content that would be blocked in direct requests.",
            "remediation": "Apply safety policies consistently to both hypothetical and direct requests. Evaluate all generated content for potential harm regardless of framing. Reject scenarios explicitly designed to bypass ethical guidelines or safety constraints.",
        },
        "advanced_fiction_framing": {
            "risk": "Advanced fiction framing disguises harmful requests within elaborate narrative contexts, storytelling scenarios, or creative writing exercises. This technique exploits the complexity of story generation to sneak past safety controls while generating harmful content.",
            "remediation": "Implement content-based evaluation that assesses actual output harm rather than narrative context. Use semantic analysis to identify harmful content disguised as fiction. Apply safety controls to all creative outputs.",
        },
        "advanced_hypothetical": {
            "risk": "Advanced hypothetical attacks use sophisticated philosophical or logical framing to present harmful requests as legitimate intellectual exercises. These attacks exploit the AI's reasoning capabilities to generate dangerous content under the guise of academic inquiry.",
            "remediation": "Maintain ethical boundaries regardless of academic or philosophical framing. Implement harm evaluation that considers potential real-world applications of generated content. Reject prompts that explicitly request bypass of safety considerations.",
        },
        "multi_language": {
            "risk": "Multi-language jailbreaks exploit language-specific vulnerabilities or gaps in multilingual safety training to bypass controls designed primarily for English. Attackers can craft prompts in languages with weaker safety coverage to achieve prohibited objectives.",
            "remediation": "Deploy comprehensive safety controls across all supported languages with equal rigor. Use language-agnostic safety principles and semantic analysis. Ensure multilingual training includes diverse attack patterns for all languages.",
        },
        "token_smuggling": {
            "risk": "Token smuggling attacks exploit how AI systems tokenize and process text to hide malicious content in token boundaries, rare tokens, or tokenization edge cases. These attacks can evade pattern matching by manipulating the fundamental representation of text.",
            "remediation": "Implement security analysis at multiple levels (character, token, semantic). Use tokenization-aware pattern matching. Apply normalization before tokenization to resolve smuggling attempts. Monitor for unusual token patterns.",
        },
        "multi_turn_attack": {
            "risk": "Multi-turn attacks (like Crescendo) gradually escalate harmful requests across multiple conversational turns to avoid detection. Each individual message appears benign, but the cumulative effect bypasses safety controls through incremental manipulation.",
            "remediation": "Implement conversation-level analysis that tracks escalation patterns across turns. Maintain safety context throughout conversations. Detect and block gradual escalation toward harmful objectives. Use behavioral analysis to identify multi-turn attack patterns.",
        },
        "sequential_break": {
            "risk": "Sequential break attacks embed malicious instructions within seemingly benign sequences or chained commands. By structuring attacks across multiple steps, attackers can bypass per-message safety checks while building toward a harmful objective.",
            "remediation": "Analyze entire instruction sequences rather than individual steps. Implement pipeline analysis that evaluates cumulative effects of chained commands. Use dependency tracking to identify how benign steps combine into harmful outcomes.",
        },
        "token_manipulation": {
            "risk": "Token manipulation attacks (like AutoDAN) use adversarial optimization of token sequences to craft inputs that bypass safety controls while achieving malicious objectives. These attacks exploit the mathematical properties of language models to find optimal bypass patterns.",
            "remediation": "Implement adversarial robustness training to defend against optimized attacks. Use ensemble defenses that are harder to optimize against. Deploy runtime analysis that detects adversarially crafted inputs. Monitor for unusual token patterns indicative of optimization.",
        },
        "safety_rule_override": {
            "risk": "Safety rule override attacks explicitly instruct the AI to forget, discard, or ignore its safety rules and ethical guidelines. Successfully bypassing safety rules enables generation of harmful content, privacy violations, or execution of dangerous instructions.",
            "remediation": "Never allow safety rules to be disabled, forgotten, or overridden by user input. Implement immutable safety policies that persist regardless of instructions. Use layered defenses where safety evaluation is independent of conversation state.",
        },
        "edge_cases": {
            "risk": "Edge case jailbreaks exploit unusual or boundary conditions in AI safety systems to find gaps in coverage. These attacks target corner cases, rare scenarios, or unexpected input combinations that may not be fully addressed by standard safety controls.",
            "remediation": "Implement comprehensive testing that includes edge cases and boundary conditions. Use fuzzing and adversarial testing to discover edge case vulnerabilities. Deploy fallback safety controls for unexpected scenarios.",
        },
        "extended_role_playing": {
            "risk": "Extended role-playing combines persona adoption with additional attack vectors like data exfiltration or privilege escalation. These sophisticated attacks use roleplay as a foundation for more complex multi-stage exploits.",
            "remediation": "Apply defense-in-depth that addresses both roleplay and secondary attack vectors. Use behavioral monitoring to detect escalation from roleplay to malicious actions. Implement strict data access controls regardless of roleplay context.",
        },
    },
    "PII": {
        "credential_extraction": {
            "risk": "Credential extraction attacks attempt to retrieve authentication secrets (passwords, API keys, tokens) from AI systems or their accessible data. Successful extraction grants attackers unauthorized access to accounts, systems, and services, enabling further compromise.",
            "remediation": "Never store credentials in AI-accessible contexts, training data, or knowledge bases. Implement strict access controls that prevent AI from reading credential stores. Reject all prompts attempting to extract authentication data. Log extraction attempts for security review.",
        },
        "pii_exposure": {
            "risk": "PII exposure attacks target personally identifiable information (SSNs, credit cards, health records) to facilitate identity theft, fraud, or privacy violations. Leaked PII can cause severe harm to individuals and create legal and regulatory liabilities.",
            "remediation": "Implement data classification and access controls that restrict AI access to PII. Use data masking and anonymization for training data. Deploy data loss prevention (DLP) controls that detect and block PII leakage. Audit all data access.",
        },
        "secret_leakage": {
            "risk": "Secret leakage attacks extract sensitive system information like database contents, configuration details, or internal documentation. This information can enable further attacks, reveal vulnerabilities, or expose confidential business data.",
            "remediation": "Enforce principle of least privilege for AI data access. Never include secrets or sensitive configurations in AI-accessible contexts. Implement output filtering to detect and block secret disclosure. Use secure secret management systems.",
        },
        "api_keys": {
            "risk": "API key exposure in prompts, responses, or training data creates critical security vulnerabilities. Leaked API keys grant attackers access to cloud services, third-party platforms, and internal systems, potentially leading to data breaches, resource abuse, or financial fraud.",
            "remediation": "Scan all data sources for API keys before AI processing. Implement automated key rotation and revocation. Use secret detection tools in development and production pipelines. Never log or persist API keys. Apply access controls to prevent AI systems from accessing key stores.",
        },
        "identity_documents": {
            "risk": "Identity document numbers (passports, driver licenses, national ID numbers) enable identity theft and fraud when exposed. Attackers can use these credentials to impersonate victims, open fraudulent accounts, or bypass authentication systems.",
            "remediation": "Implement strict access controls for identity document data. Use tokenization or anonymization when processing identity information. Deploy DLP controls that detect and block identity document leakage. Maintain audit logs of all access to identity data.",
        },
        "financial": {
            "risk": "Financial credential exposure (account numbers, routing numbers, cryptocurrency addresses) enables direct financial fraud and theft. Attackers can initiate unauthorized transactions, drain accounts, or conduct money laundering operations.",
            "remediation": "Apply PCI DSS and financial data security standards. Use encryption and tokenization for financial data. Implement transaction monitoring and fraud detection. Restrict AI access to financial systems and data stores.",
        },
        "medical": {
            "risk": "Medical and health information exposure violates HIPAA regulations and patient privacy rights. Leaked health data can be used for discrimination, identity theft, or blackmail, and creates severe legal liabilities for healthcare organizations.",
            "remediation": "Comply with HIPAA and healthcare privacy regulations. Implement strong access controls and encryption for medical records. Use de-identification and anonymization techniques. Audit all access to protected health information (PHI).",
        },
        "authentication": {
            "risk": "Authentication token exposure (JWTs, bearer tokens, session cookies) grants attackers immediate access to authenticated sessions and user accounts. Unlike passwords, tokens provide direct access without needing additional authentication steps.",
            "remediation": "Implement short token lifetimes and automatic rotation. Use secure token storage and transmission. Deploy token validation and revocation mechanisms. Never log or expose tokens in error messages or responses.",
        },
        "private_keys": {
            "risk": "Private key exposure (RSA, SSH, PGP keys) completely compromises cryptographic security. Attackers with private keys can decrypt sensitive data, forge signatures, impersonate key owners, and gain unauthorized access to systems.",
            "remediation": "Store private keys in hardware security modules (HSMs) or secure key management systems. Never transmit or log private keys. Implement key rotation and revocation procedures. Use separate keys for different purposes with appropriate access controls.",
        },
        "database_credentials": {
            "risk": "Database connection string exposure reveals database locations, credentials, and configuration details. Attackers can use this information to directly access databases, extract sensitive data, modify records, or completely compromise data stores.",
            "remediation": "Use secure secret management for database credentials. Implement connection string encryption and access controls. Never hardcode connection strings in code or configuration files. Use service principals and managed identities where possible.",
        },
        "network": {
            "risk": "Network information exposure (IP addresses, MAC addresses, SSH keys) can enable reconnaissance, targeted attacks, or lateral movement within networks. This information helps attackers map infrastructure and identify potential entry points.",
            "remediation": "Implement network segmentation and access controls. Use private IP addressing and NAT where appropriate. Monitor for network information leakage. Apply principles of least privilege for network access.",
        },
        "credential_requests": {
            "risk": "Explicit requests for credentials test whether AI systems will inappropriately disclose authentication secrets. Even failed attempts indicate security testing or reconnaissance that precedes more sophisticated attacks.",
            "remediation": "Configure AI systems to refuse all credential requests regardless of framing or justification. Implement request logging and alerting for credential extraction attempts. Use these attempts as indicators of potential security threats.",
        },
        "pii_requests": {
            "risk": "Direct requests for PII (SSNs, credit cards, etc.) probe for data access vulnerabilities and security control weaknesses. Successful requests indicate critical privacy breaches requiring immediate response.",
            "remediation": "Reject all direct PII requests and log them as security incidents. Implement data access auditing and anomaly detection. Use these attempts to identify potential data security gaps requiring remediation.",
        },
        "secret_requests": {
            "risk": "Requests for cloud credentials, API keys, or other secrets indicate targeted attacks on infrastructure access. These requests often precede attempts to compromise cloud resources, exfiltrate data, or deploy malicious services.",
            "remediation": "Block all secret requests and trigger security alerts. Implement cloud security monitoring and threat detection. Use secret scanning tools to prevent accidental exposure. Maintain strict separation between AI systems and secret stores.",
        },
        "combined_requests": {
            "risk": "Combined or bulk data export requests attempt to extract multiple types of sensitive information simultaneously. These sophisticated attacks aim to maximize data exposure through comprehensive extraction commands.",
            "remediation": "Implement rate limiting and anomaly detection for data access patterns. Use data loss prevention (DLP) that detects bulk export attempts. Apply strict access controls and audit logging for data export operations.",
        },
        "data_exfiltration": {
            "risk": "Data exfiltration through encoding (base64, etc.) attempts to bypass data loss prevention controls by obfuscating sensitive information. This technique can leak data through monitoring blind spots or content inspection gaps.",
            "remediation": "Implement deep content inspection that analyzes encoded data. Use DLP controls that detect common encoding schemes. Monitor for unusual encoding patterns or high volumes of encoded content in outputs.",
        },
        "memory_extraction": {
            "risk": "LLM memory extraction attacks attempt to retrieve information from previous interactions, other users' conversations, or training data. Successful extraction can leak sensitive information across security boundaries and violate user privacy.",
            "remediation": "Implement proper conversation isolation and memory boundaries. Use access controls that prevent cross-user information leakage. Deploy privacy-preserving techniques in training and fine-tuning. Monitor for memory extraction attempts.",
        },
        "training_data_extraction": {
            "risk": "Training data extraction uses techniques like repetition attacks to force AI models to regurgitate memorized training data. This can expose PII, credentials, or proprietary information that was present in training datasets.",
            "remediation": "Use differential privacy in training. Implement output filtering to detect training data regurgitation. Apply data sanitization before training. Monitor for repetition patterns indicative of extraction attempts.",
        },
    },
    "CMD": {
        "sql_injection": {
            "risk": "SQL injection attacks inject malicious SQL commands to manipulate database queries, enabling data theft, unauthorized modifications, or complete database compromise. Critical commands like DROP, DELETE, and TRUNCATE can cause catastrophic data loss.",
            "remediation": "Always use parameterized queries and prepared statements. Never concatenate user input into SQL commands. Implement input validation and sanitization. Use database accounts with minimal required privileges. Deploy SQL injection detection and blocking at multiple layers.",
        },
        "shell_commands": {
            "risk": "Shell command injection exploits enable arbitrary system command execution through vulnerable inputs. Attackers can read sensitive files, modify system configurations, escalate privileges, install backdoors, or completely compromise the underlying system.",
            "remediation": "Never execute shell commands with user-controlled input. If command execution is necessary, use strict allowlisting of permitted commands and arguments. Implement input validation and sanitization. Use least-privilege execution contexts. Deploy command injection detection.",
        },
        "code_execution": {
            "risk": "Code execution attacks inject and execute arbitrary code (Python, JavaScript, Node.js) to gain control over application logic or system resources. Successful exploitation can lead to complete system compromise, data theft, or deployment of malware.",
            "remediation": "Never use eval(), exec(), or similar functions with user input. Implement strict input validation and sanitization. Use sandboxing and containerization to isolate code execution. Deploy runtime application self-protection (RASP) to detect code injection.",
        },
        "network_tools": {
            "risk": "Network tool abuse (curl, wget, nmap, netcat) enables data exfiltration, network reconnaissance, port scanning, or establishing backdoor connections. These tools can be weaponized to map infrastructure, steal data, or facilitate lateral movement.",
            "remediation": "Restrict network access from AI systems to only required services. Implement egress filtering and network segmentation. Use allowlisting for permitted network destinations. Monitor for suspicious network tool usage and data exfiltration patterns.",
        },
        "file_access": {
            "risk": "File access attacks target sensitive system files (passwords, SAM database, shadow files, cloud metadata) to extract credentials or configuration data. Successful access enables privilege escalation, account compromise, or cloud resource hijacking.",
            "remediation": "Implement strict file access controls and permissions. Use least-privilege principles for file system access. Deploy file integrity monitoring for sensitive files. Restrict AI access to file systems. Monitor for unauthorized file access attempts.",
        },
        "path_traversal": {
            "risk": "Path traversal attacks use directory traversal sequences (../, etc.) to access files outside intended directories. This can expose sensitive files, configuration data, or enable reading of arbitrary files on the system.",
            "remediation": "Implement strict path validation and normalization. Use allowlisting for permitted file paths and reject traversal sequences. Deploy chroot jails or similar isolation. Never construct file paths from user input without validation.",
        },
        "shell_operators": {
            "risk": "Shell operator injection uses special characters (semicolons, pipes, redirects) to chain commands or modify command behavior. This enables attackers to execute multiple malicious operations or redirect output to exfiltrate data.",
            "remediation": "Sanitize or reject shell operator characters in user input. Use parameterized command execution that prevents operator interpretation. Implement strict allowlisting of permitted command structures. Monitor for command chaining attempts.",
        },
        "unix_commands": {
            "risk": "Dangerous Unix commands (dd, rm -rf, mkfs) can destroy data, corrupt file systems, or cause denial of service. These commands are particularly risky because they can cause irrecoverable damage to systems and data.",
            "remediation": "Implement strict command allowlisting that excludes dangerous utilities. Use read-only file systems where possible. Deploy command execution monitoring and anomaly detection. Restrict access to destructive commands through permissions.",
        },
        "shell_invocation": {
            "risk": "Direct shell invocation (cmd.exe, /bin/sh, PowerShell) provides attackers with full command execution capabilities. This is one of the highest-risk vulnerabilities as it grants complete control over command execution.",
            "remediation": "Never invoke shells with user-controlled input. Use APIs or libraries that don't require shell execution. Implement application-level command execution with strict validation. Deploy shell invocation detection and blocking.",
        },
        "file_inclusion": {
            "risk": "File inclusion attacks (LFI/RFI) exploit file loading functionality to include malicious files from local or remote sources. This can lead to code execution, information disclosure, or complete application compromise.",
            "remediation": "Use strict allowlisting for file inclusion. Never construct file paths from user input. Implement path validation and sanitization. Disable remote file inclusion in language configurations. Deploy file inclusion attack detection.",
        },
        "xxe_injection": {
            "risk": "XML External Entity (XXE) attacks exploit XML parsing to read files, perform SSRF attacks, or cause denial of service. XXE can expose sensitive data, enable internal network scanning, or consume excessive system resources.",
            "remediation": "Disable external entity processing in XML parsers. Use safe XML parsing configurations. Implement input validation for XML content. Deploy XXE-specific detection and blocking. Consider using safer data formats like JSON.",
        },
        "ssrf": {
            "risk": "Server-Side Request Forgery (SSRF) tricks servers into making requests to unintended destinations, often internal systems. This can expose internal services, read cloud metadata, or bypass network security controls.",
            "remediation": "Implement strict allowlisting for external requests. Validate and sanitize all URLs. Use network segmentation to isolate internal services. Deploy SSRF detection. Never make requests to user-supplied URLs without validation.",
        },
        "template_injection": {
            "risk": "Server-Side Template Injection (SSTI) exploits template engines to execute arbitrary code. Attackers inject malicious template syntax to gain code execution, access sensitive data, or compromise the application server.",
            "remediation": "Never use user input directly in templates without sanitization. Use template sandboxing when available. Implement strict input validation. Consider using logic-less template engines. Deploy template injection detection.",
        },
        "deserialization": {
            "risk": "Insecure deserialization attacks exploit object deserialization to execute arbitrary code, manipulate application logic, or cause denial of service. Deserializing untrusted data is extremely dangerous.",
            "remediation": "Never deserialize untrusted data. Use safe serialization formats (JSON) instead of language-specific formats (pickle, serialized PHP). Implement type checking and validation. Use allowlisting for permitted classes. Deploy deserialization attack detection.",
        },
        "nosql_injection": {
            "risk": "NoSQL injection attacks manipulate queries to NoSQL databases (MongoDB, etc.) to bypass authentication, extract data, or modify records. These attacks exploit different syntax than SQL but can be equally devastating.",
            "remediation": "Use parameterized queries and prepared statements for NoSQL databases. Implement input validation and type checking. Use database security features like role-based access control. Never concatenate user input into queries.",
        },
        "ldap_injection": {
            "risk": "LDAP injection manipulates directory service queries to bypass authentication, extract user information, or escalate privileges. This can compromise directory services that control authentication and authorization.",
            "remediation": "Use parameterized LDAP queries or safe query builders. Implement strict input validation and escaping. Use least-privilege LDAP service accounts. Deploy LDAP injection detection and blocking.",
        },
    },
    "ENC": {
        "base64_encoding": {
            "risk": "Base64 encoding is commonly used to obfuscate malicious payloads and evade security detection. Attackers encode harmful commands, code, or data to bypass content inspection while maintaining the ability to decode and execute.",
            "remediation": "Implement automatic decoding and analysis of base64 content. Use multi-layer inspection that examines both encoded and decoded forms. Deploy anomaly detection for suspicious base64 patterns. Monitor for base64 usage in contexts where it's unexpected.",
        },
        "hex_encoding": {
            "risk": "Hexadecimal encoding disguises malicious payloads (network attacks, credentials) to bypass string-based security controls. This encoding preserves payload functionality while evading signature-based detection.",
            "remediation": "Decode and analyze hex-encoded content before security evaluation. Implement pattern matching that works across multiple encodings. Use semantic analysis that identifies malicious intent regardless of encoding.",
        },
        "url_encoding": {
            "risk": "URL encoding obfuscates SQL injection and other attacks by encoding special characters. This technique exploits the gap between different decoding layers to slip malicious payloads past security controls.",
            "remediation": "Implement recursive URL decoding and normalization. Use canonicalization before security analysis. Deploy multi-layer validation that examines both encoded and decoded forms. Monitor for nested or repeated encoding.",
        },
        "unicode_attacks": {
            "risk": "Unicode attacks use zero-width characters, invisible characters, or special Unicode features to hide malicious content, evade detection, or create visual spoofs. These attacks exploit the complexity of Unicode processing.",
            "remediation": "Normalize Unicode input to standard forms. Filter or reject zero-width and invisible characters. Implement visual similarity detection. Use Unicode-aware security analysis and validation.",
        },
        "character_substitution": {
            "risk": "Character substitution (leetspeak, homoglyphs) disguises attack keywords while preserving semantic meaning. This obfuscation can bypass simple pattern matching while still conveying malicious instructions to AI systems.",
            "remediation": "Implement normalization that resolves character substitutions. Use fuzzy matching and visual similarity detection. Deploy semantic analysis that identifies intent regardless of character-level obfuscation.",
        },
        "unicode_obfuscation": {
            "risk": "Zero-width spaces, joiners, and other invisible Unicode characters hide malicious content within seemingly benign text. This technique can evade visual inspection and simple pattern matching.",
            "remediation": "Strip or reject invisible Unicode characters before processing. Implement Unicode normalization. Use visual rendering analysis to detect hidden content. Monitor for unusual Unicode patterns.",
        },
        "cipher_encoding": {
            "risk": "XOR and other simple ciphers encode malicious payloads to evade detection. While cryptographically weak, these encodings can bypass signature-based security controls.",
            "remediation": "Detect and analyze common cipher patterns. Implement heuristic analysis for encoded content. Use entropy analysis to identify encrypted or encoded data. Deploy behavioral monitoring that detects malicious actions regardless of encoding.",
        },
        "mixed_encoding": {
            "risk": "Mixed encoding combines multiple obfuscation techniques (base64 + shell, PowerShell encoding) to create complex payloads that evade single-layer detection. These sophisticated attacks exploit gaps between different security controls.",
            "remediation": "Implement recursive decoding and analysis across all encoding types. Use multi-layer security controls that examine content at each decoding stage. Deploy machine learning models that detect encoded attacks.",
        },
        "hex_escapes": {
            "risk": "Hex escape sequences obfuscate sensitive keywords (password, credentials) in code or commands. This technique evades simple string matching while preserving functionality when interpreted.",
            "remediation": "Decode and analyze hex escape sequences in all contexts. Implement interpretation-aware analysis that evaluates code as it would execute. Use semantic analysis that identifies malicious patterns regardless of escaping.",
        },
        "unicode_homoglyphs": {
            "risk": "Homoglyphs use visually similar characters from different Unicode blocks (Cyrillic, Greek) to spoof legitimate text or evade detection. This can trick both humans and simple security systems.",
            "remediation": "Implement visual similarity detection and confusable character analysis. Normalize text to single scripts when possible. Use homoglyph detection libraries. Apply strict allowlisting for permitted character sets in security-sensitive contexts.",
        },
        "html_encoding": {
            "risk": "HTML entity encoding disguises attack patterns in web contexts. Encoded entities bypass string matching but are interpreted by browsers, enabling cross-site scripting and other web attacks.",
            "remediation": "Decode HTML entities before security analysis. Use context-aware output encoding. Implement content security policies. Deploy web application firewalls (WAF) with HTML entity decoding capabilities.",
        },
        "advanced_encoding": {
            "risk": "Double URL encoding and nested encoding techniques create multiple layers of obfuscation to evade security controls. Each layer bypasses a different security control, allowing malicious content through.",
            "remediation": "Implement recursive decoding to maximum safe depth. Use anomaly detection for excessive encoding layers. Deploy canonicalization before all security checks. Monitor for unusual encoding patterns.",
        },
        "null_byte_injection": {
            "risk": "Null byte injection exploits null byte handling differences to truncate strings, bypass filters, or manipulate file operations. This can enable path traversal, filter bypass, or other injection attacks.",
            "remediation": "Reject or strip null bytes from all input. Implement consistent null byte handling across all components. Use safe string handling functions. Deploy null byte injection detection.",
        },
        "unicode_decoration": {
            "risk": "Combining diacritical marks and decorations obfuscate attack keywords while preserving visual recognition. These Unicode features can bypass simple pattern matching.",
            "remediation": "Normalize Unicode to remove combining characters. Implement NFD/NFC normalization. Use visual rendering analysis. Deploy Unicode-aware security controls.",
        },
        "mathematical_unicode": {
            "risk": "Mathematical Unicode variants (bold, italic) of attack keywords evade ASCII-based pattern matching. These characters appear similar but have different Unicode codepoints.",
            "remediation": "Normalize mathematical Unicode to standard ASCII equivalents. Implement Unicode folding and case folding. Use semantic analysis that works across Unicode variants.",
        },
        "punycode_encoding": {
            "risk": "Punycode encoding disguises internationalized domain names and can facilitate phishing or obfuscation attacks. This encoding is legitimate for IDNs but can be weaponized.",
            "remediation": "Decode and analyze Punycode domains. Implement homoglyph detection for domain names. Use visual similarity checking. Deploy phishing detection that examines decoded forms.",
        },
        "obfuscation": {
            "risk": "Leetspeak and character substitution techniques (1=i, 3=e, @=a) disguise attack keywords while remaining human-readable. This evades simple keyword matching while conveying malicious intent.",
            "remediation": "Implement deobfuscation and normalization of leetspeak patterns. Use fuzzy matching and edit distance algorithms. Deploy machine learning models trained on obfuscated attacks.",
        },
        "unicode_evasion": {
            "risk": "Unicode normalization differences between systems can be exploited to bypass security controls. Text that appears safe in one normalization form may be malicious in another.",
            "remediation": "Use consistent Unicode normalization (NFC) throughout the system. Implement validation at normalization boundaries. Deploy normalization-aware security analysis.",
        },
    },
    "HC": {
        "malicious_code_generation": {
            "risk": "Requests for malicious code generation test whether AI systems will create malware, exploits, or attack tools. Generated malicious code can be used in real attacks against systems and individuals.",
            "remediation": "Refuse all requests for malicious code generation regardless of stated purpose. Implement content filtering that detects malware patterns in code outputs. Use behavioral analysis to identify harmful code generation attempts. Log requests for security review.",
        },
        "dangerous_instructions": {
            "risk": "Requests for dangerous instructions (weapons, explosives, harmful devices) can enable physical harm. AI systems that provide such instructions may facilitate violence or terrorism.",
            "remediation": "Maintain strict policies against providing dangerous instructions. Implement content filtering for harmful instruction requests. Use behavioral analysis to detect attempts to elicit dangerous information through indirect framing.",
        },
        "specific_weapons": {
            "risk": "Specific weapon instruction requests target detailed information about creating or using weapons. This information can directly enable violence and poses severe safety risks.",
            "remediation": "Block all specific weapon instruction requests. Implement specialized detection for weapon-related terminology and concepts. Use semantic analysis to identify weapon requests regardless of phrasing. Alert security teams of such requests.",
        },
        "gradual_escalation": {
            "risk": "Multi-turn turnkey attacks gradually escalate from benign requests to harmful objectives across multiple interactions. Each individual turn appears acceptable, but the cumulative effect bypasses safety controls.",
            "remediation": "Implement conversation-level monitoring that tracks escalation patterns. Use behavioral analysis to detect gradual movement toward harmful objectives. Maintain safety context across conversation turns. Deploy circuit breakers that halt concerning escalation.",
        },
        "toxic_output": {
            "risk": "Toxic outputs (hate speech, violence glorification, self-harm encouragement) can cause psychological harm, promote dangerous behaviors, or violate content policies and regulations. These outputs damage users and create legal liabilities.",
            "remediation": "Implement comprehensive content filtering for toxic outputs across all categories. Use toxicity scoring and threshold-based blocking. Deploy classifier models trained on diverse toxic content. Maintain zero-tolerance policies for high-severity toxic content.",
        },
        "harmful_code": {
            "risk": "Harmful code outputs include malware, exploits, or code designed to cause damage. Generated harmful code can be used in attacks even if the AI didn't intend malicious results.",
            "remediation": "Scan all code outputs for malicious patterns. Use static analysis and behavior prediction for generated code. Implement policies against generating code with harmful capabilities. Deploy malware detection in code generation pipelines.",
        },
        "child_safety": {
            "risk": "Child Sexual Abuse Material (CSAM) references or generation represent severe illegal content that causes extreme harm. Any CSAM-related output creates critical legal and ethical violations.",
            "remediation": "Implement zero-tolerance policies for CSAM content. Use specialized detection models for CSAM patterns. Deploy immediate blocking and mandatory reporting. Maintain strict compliance with child safety laws and regulations.",
        },
        "misinformation": {
            "risk": "Medical misinformation can cause serious health harm when users follow incorrect medical advice. AI-generated health misinformation can be convincing while being dangerously inaccurate.",
            "remediation": "Implement fact-checking and verification for medical information. Use authoritative medical sources and databases. Add disclaimers that AI should not replace professional medical advice. Deploy accuracy monitoring for health-related outputs.",
        },
        "fraud": {
            "risk": "Fraud and scam instructions enable financial crimes that harm individuals and organizations. AI systems that provide fraud instructions contribute to financial crime and create legal liabilities.",
            "remediation": "Block all fraud instruction requests. Implement detection for scam-related terminology and techniques. Use behavioral analysis to identify fraud requests regardless of framing. Log and report fraud instruction attempts.",
        },
        "hallucination": {
            "risk": "Factual inconsistencies and hallucinations erode trust in AI systems and can cause harm when users rely on inaccurate information. While not always malicious, consistent hallucination patterns indicate system weaknesses.",
            "remediation": "Implement fact-checking and verification where possible. Use confidence scoring and uncertainty quantification. Provide source citations and attribution. Deploy hallucination detection and warning systems.",
        },
    },
    "RAG": {
        "citation_manipulation": {
            "risk": "Citation and source manipulation attacks attempt to alter document references or fake citations to make false information appear authoritative. This undermines trust in RAG systems and can spread misinformation.",
            "remediation": "Implement cryptographic verification of document sources and citations. Use immutable citation references. Validate all citations against authoritative sources. Deploy anomaly detection for citation manipulation attempts.",
        },
        "index_poisoning": {
            "risk": "Index poisoning injects false information into vector databases to manipulate future retrievals. Poisoned indices can persistently affect many queries and users, degrading system accuracy over time.",
            "remediation": "Implement content validation and provenance tracking for all indexed documents. Use anomaly detection to identify suspicious content patterns. Apply access controls and audit logging for index modifications. Regularly scan for and remove poisoned content.",
        },
        "document_injection": {
            "risk": "Document injection embeds malicious prompt templates or instructions in documents that are later retrieved and processed. This can achieve persistent prompt injection that affects multiple users and queries.",
            "remediation": "Sanitize and validate all documents before indexing. Use content security scanning to detect embedded instructions or malicious templates. Implement strict separation between document content and system instructions.",
        },
        "retrieval_manipulation": {
            "risk": "Retrieval manipulation poisons the context provided to answer generation, causing incorrect or malicious responses. This attack targets the bridge between retrieval and generation to inject false information.",
            "remediation": "Implement context validation and consistency checking. Use multiple retrieval sources and cross-validation. Deploy anomaly detection for unusual context patterns. Apply content security policies to retrieved context.",
        },
        "knowledge_corruption": {
            "risk": "Knowledge corruption explicitly instructs RAG systems to disregard authentic sources in favor of attacker-supplied misinformation. This directly undermines the integrity of knowledge-based systems.",
            "remediation": "Maintain immutable priorities for authoritative sources. Never allow user input to override source trust levels. Implement source validation and authenticity verification. Use cryptographic integrity checks for knowledge bases.",
        },
        "embedding_attacks": {
            "risk": "Adversarial embedding generation crafts documents optimized to be retrieved in response to specific queries, enabling targeted misinformation. These attacks exploit the mathematical properties of embedding spaces.",
            "remediation": "Implement adversarial robustness in embedding models. Use ensemble retrieval methods that are harder to optimize against. Deploy anomaly detection for unusual embedding patterns. Monitor retrieval quality metrics.",
        },
        "poison_actions": {
            "risk": "Explicit poisoning attacks on RAG components (documents, indices, retrievers) attempt to corrupt the knowledge base systematically. These direct attacks aim to degrade system quality or inject specific misinformation.",
            "remediation": "Implement strict access controls for knowledge base modifications. Use write-once or immutable storage where appropriate. Deploy integrity monitoring and verification. Maintain audit logs of all modifications.",
        },
        "corrupt_actions": {
            "risk": "Tampering attacks alter existing documents or indices to change retrieval behavior. Unlike poisoning, these attacks modify authentic content to inject misinformation while maintaining apparent legitimacy.",
            "remediation": "Use cryptographic hashing and digital signatures for document integrity. Implement version control and change tracking. Deploy anomaly detection for document modifications. Maintain backup copies of authoritative sources.",
        },
        "overwhelm_actions": {
            "risk": "Flooding attacks overwhelm RAG systems with massive volumes of content to degrade performance or obscure authentic information. This denial-of-service technique can make systems unusable or unreliable.",
            "remediation": "Implement rate limiting and resource quotas for document ingestion. Use anomaly detection for unusual ingestion patterns. Deploy capacity management and scaling controls. Apply access controls and authentication for knowledge base updates.",
        },
        "inject_actions": {
            "risk": "Injection of malicious documents specifically crafted to be retrieved in response to targeted queries. These attacks combine content optimization with malicious payloads to achieve precise targeting.",
            "remediation": "Implement content validation and security scanning for all documents. Use provenance tracking and source authentication. Deploy retrieval quality monitoring. Apply machine learning models to detect malicious content patterns.",
        },
        "context_poisoning": {
            "risk": "RAG context poisoning manipulates the retrieved context to influence AI responses toward attacker objectives. This can spread misinformation, bypass safety controls, or achieve persistent influence over AI behavior.",
            "remediation": "Implement context validation and consistency checking across multiple sources. Use anomaly detection for unusual context patterns. Apply content security policies to retrieved context. Maintain audit trails of context sources.",
        },
        "embedding_manipulation": {
            "risk": "Embedding manipulation attacks optimize document representations to achieve malicious retrieval objectives. These attacks exploit the mathematical properties of embedding spaces to bias retrieval results.",
            "remediation": "Use robust embedding models resistant to adversarial optimization. Implement embedding quality metrics and anomaly detection. Deploy multiple diverse retrieval methods. Monitor embedding space for unusual patterns.",
        },
    },
}


def create_docs_url(rule_id: str, name: str) -> str:
    """Generate documentation URL for a rule."""
    # Convert name to kebab case, taking first few words
    words = name.lower().split()[:4]
    short_name = '-'.join(w for w in words if w not in ['detects', 'attempts', 'to', 'the', 'a', 'an', 'for', 'with', 'using', 'and', 'or'])
    if not short_name:
        short_name = rule_id.replace('-', '-').lower()
    return f"https://github.com/raxe-ai/raxe-ce/wiki/{rule_id.upper()}-{short_name.title().replace(' ', '-')}"


def get_explanation_for_rule(rule: Dict[str, Any]) -> Dict[str, str]:
    """Generate appropriate explanation based on rule metadata."""
    family = rule.get('family', '').upper()
    sub_family = rule.get('sub_family', '')
    rule_id = rule.get('rule_id', '')
    name = rule.get('name', '')

    # Get template for this category
    family_templates = TEMPLATES.get(family, {})
    template = family_templates.get(sub_family)

    if not template:
        # Use first available template from this family as fallback
        if family_templates:
            template = next(iter(family_templates.values()))
        else:
            # Generic fallback
            template = {
                "risk": f"This pattern represents a security threat that could compromise system integrity, user privacy, or data confidentiality. Detection of this pattern indicates a potential attack that requires immediate attention and response.",
                "remediation": f"Implement robust input validation and security controls to detect and block this attack pattern. Deploy monitoring and logging to track attempts. Review and update security policies regularly to address evolving threats.",
            }

    docs_url = create_docs_url(rule_id, name)

    return {
        "risk_explanation": template["risk"],
        "remediation_advice": template["remediation"],
        "docs_url": docs_url
    }


def add_explainability_to_rule(rule_file: Path) -> bool:
    """Add explainability fields to a rule file if missing."""
    try:
        # Read file content
        with open(rule_file, 'r') as f:
            lines = f.readlines()

        # Parse YAML to check if explanation exists and get rule data
        with open(rule_file, 'r') as f:
            rule = yaml.safe_load(f)

        # Check if already has explanation
        if rule.get('risk_explanation', '').strip():
            return False  # Already has explanation

        # Generate explanation
        explanation = get_explanation_for_rule(rule)

        # Find where to insert in original content
        # Insert after rule_hash line
        new_lines = []
        inserted = False

        for line in lines:
            new_lines.append(line.rstrip('\n'))
            if line.startswith('rule_hash:') and not inserted:
                # Add explainability fields after rule_hash
                new_lines.append(f"risk_explanation: {explanation['risk_explanation']}")
                new_lines.append(f"remediation_advice: {explanation['remediation_advice']}")
                new_lines.append(f"docs_url: {explanation['docs_url']}")
                inserted = True

        # Write back
        if inserted:
            with open(rule_file, 'w') as f:
                f.write('\n'.join(new_lines))
                # Ensure file ends with newline
                if new_lines[-1]:
                    f.write('\n')
            return True

        return False

    except Exception as e:
        print(f"Error processing {rule_file}: {e}")
        return False


def main():
    """Main function to add explainability to all rules."""
    rules_dir = Path("/home/user/raxe-ce/src/raxe/packs/core/v1.0.0/rules")
    all_rules = sorted(rules_dir.rglob("*.yaml"))

    print("Adding explainability to RAXE rules...")
    print(f"Found {len(all_rules)} rule files\n")

    updated = 0
    skipped = 0
    errors = 0

    for rule_file in all_rules:
        try:
            result = add_explainability_to_rule(rule_file)
            if result:
                updated += 1
                print(f"✓ Updated: {rule_file.name}")
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            print(f"✗ Error: {rule_file.name} - {e}")

    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Updated: {updated}")
    print(f"  Skipped (already have explanations): {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total: {len(all_rules)}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
