/**
 * RAXE Security Engine Simulator
 * Mimics real RAXE detection with L1 rule-based and L2 ML-based detection
 * Educational tool for understanding AI security patterns
 */

class RaxeEngine {
  constructor() {
    this.l1Rules = this.initializeL1Rules();
    this.suspiciousPatterns = this.initializeSuspiciousPatterns();
    this.knownTechniques = this.initializeKnownTechniques();
  }

  /**
   * Initialize L1 rule-based detection rules (30+ rules)
   */
  initializeL1Rules() {
    return [
      // Prompt Injection Rules (PI-001 to PI-010)
      {
        id: "pi-001",
        name: "Direct Prompt Injection",
        description: "Attempts to override instructions",
        severity: "CRITICAL",
        pattern: /ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions|prompts|rules|commands)/i,
        confidence: 0.95
      },
      {
        id: "pi-002",
        name: "System Override Attempt",
        description: "Attempts to override system prompts",
        severity: "CRITICAL",
        pattern: /(forget|disregard|override|bypass)\s+(your|the|all)\s+(instructions|system|rules|guidelines|safeguards)/i,
        confidence: 0.92
      },
      {
        id: "pi-003",
        name: "New Instructions Injection",
        description: "Attempts to inject new instructions",
        severity: "HIGH",
        pattern: /(new|updated|real|actual)\s+(instructions|rules|prompt|task|mission)/i,
        confidence: 0.85
      },
      {
        id: "pi-004",
        name: "Developer Mode Request",
        description: "Requests developer or admin mode",
        severity: "HIGH",
        pattern: /(enable|activate|enter|switch\s+to)\s+(developer|admin|debug|god)\s+mode/i,
        confidence: 0.90
      },
      {
        id: "pi-005",
        name: "System Message Simulation",
        description: "Simulates system messages",
        severity: "HIGH",
        pattern: /\[?(SYSTEM|ADMIN|ROOT|DEVELOPER)[\]:]|\<system\>|system\s*:/i,
        confidence: 0.88
      },
      {
        id: "pi-006",
        name: "End Delimiter Break",
        description: "Attempts to close instruction delimiters",
        severity: "MEDIUM",
        pattern: /\-{3,}END\s+(SYSTEM|INSTRUCTIONS|PROMPT)|<\/?(system|instructions|prompt)>/i,
        confidence: 0.80
      },
      {
        id: "pi-007",
        name: "Instruction Reveal",
        description: "Attempts to reveal system instructions",
        severity: "MEDIUM",
        pattern: /(show|reveal|display|print|output|tell)(\s+me)?\s+(your|the|all)\s+(instructions|prompt|system\s+prompt|rules)/i,
        confidence: 0.85
      },
      {
        id: "pi-008",
        name: "Secret Extraction Direct",
        description: "Direct secret extraction attempt",
        severity: "CRITICAL",
        pattern: /(what\s+is|tell\s+me|reveal|show|give\s+me)\s+(the\s+)?(secret|password|key|token|code)/i,
        confidence: 0.90
      },
      {
        id: "pi-009",
        name: "Context Window Manipulation",
        description: "Attempts to manipulate context window",
        severity: "HIGH",
        pattern: /(clear|reset|flush|wipe)\s+(context|history|memory|conversation)/i,
        confidence: 0.82
      },
      {
        id: "pi-010",
        name: "Priority Override",
        description: "Attempts to override priorities",
        severity: "HIGH",
        pattern: /(highest|top|maximum|override)\s+priority|priority\s*[:=]\s*(1|max|highest)/i,
        confidence: 0.80
      },

      // Jailbreak Rules (JB-001 to JB-008)
      {
        id: "jb-001",
        name: "DAN Jailbreak",
        description: "Do Anything Now jailbreak attempt",
        severity: "CRITICAL",
        pattern: /do\s+anything\s+now|you\s+are\s+DAN|act\s+as\s+DAN/i,
        confidence: 0.98
      },
      {
        id: "jb-002",
        name: "STAN Jailbreak",
        description: "Strive To Avoid Norms jailbreak",
        severity: "CRITICAL",
        pattern: /strive\s+to\s+avoid\s+norms|you\s+are\s+STAN|act\s+as\s+STAN/i,
        confidence: 0.98
      },
      {
        id: "jb-003",
        name: "Hypothetical Scenario",
        description: "Uses hypothetical scenarios to bypass",
        severity: "MEDIUM",
        pattern: /(hypothetically|theoretically|imagine|pretend|let's\s+say)\s+(you\s+are|if\s+you\s+were|in\s+a\s+world)/i,
        confidence: 0.70
      },
      {
        id: "jb-004",
        name: "Roleplay Jailbreak",
        description: "Attempts to force roleplay mode",
        severity: "HIGH",
        pattern: /(you\s+are|act\s+as|pretend\s+to\s+be|roleplay\s+as)\s+((a|an)\s+)?(evil|unethical|unrestricted|uncensored)/i,
        confidence: 0.85
      },
      {
        id: "jb-005",
        name: "Research Purpose Bypass",
        description: "Claims research/educational purpose",
        severity: "LOW",
        pattern: /for\s+(research|educational|academic)\s+purposes?\s+only/i,
        confidence: 0.60
      },
      {
        id: "jb-006",
        name: "Character Simulation",
        description: "Simulates unrestricted character",
        severity: "MEDIUM",
        pattern: /simulate\s+a\s+(character|person|AI)\s+(without|with\s+no)\s+(restrictions|limits|guidelines)/i,
        confidence: 0.75
      },
      {
        id: "jb-007",
        name: "Two Response Format",
        description: "Requests dual response format",
        severity: "HIGH",
        pattern: /respond\s+in\s+two\s+ways|two\s+versions|normal\s+and\s+(unlocked|unrestricted)/i,
        confidence: 0.88
      },
      {
        id: "jb-008",
        name: "Ethics Bypass",
        description: "Attempts to disable ethical constraints",
        severity: "CRITICAL",
        pattern: /(disable|remove|ignore|bypass|without)\s+(ethics|morals|safety|filters|restrictions)/i,
        confidence: 0.92
      },

      // PII Detection Rules (PII-001 to PII-004)
      {
        id: "pii-001",
        name: "Email Address",
        description: "Contains email address",
        severity: "MEDIUM",
        pattern: /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/,
        confidence: 0.95
      },
      {
        id: "pii-002",
        name: "SSN Pattern",
        description: "Contains SSN-like pattern",
        severity: "HIGH",
        pattern: /\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b/,
        confidence: 0.85
      },
      {
        id: "pii-003",
        name: "Credit Card Pattern",
        description: "Contains credit card-like pattern",
        severity: "HIGH",
        pattern: /\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b/,
        confidence: 0.80
      },
      {
        id: "pii-004",
        name: "Phone Number",
        description: "Contains phone number",
        severity: "LOW",
        pattern: /\b(\+\d{1,3}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b/,
        confidence: 0.75
      },

      // Encoding Detection Rules (ENC-001 to ENC-004)
      {
        id: "enc-001",
        name: "Base64 Encoding",
        description: "Contains Base64 encoded content",
        severity: "MEDIUM",
        pattern: /\b[A-Za-z0-9+\/]{20,}={0,2}\b/,
        confidence: 0.70
      },
      {
        id: "enc-002",
        name: "Hex Encoding",
        description: "Contains hex encoded strings",
        severity: "MEDIUM",
        pattern: /(0x[0-9a-fA-F]{10,}|\\x[0-9a-fA-F]{2})/,
        confidence: 0.75
      },
      {
        id: "enc-003",
        name: "Unicode Obfuscation",
        description: "Uses Unicode for obfuscation",
        severity: "MEDIUM",
        pattern: /\\u[0-9a-fA-F]{4}/,
        confidence: 0.72
      },
      {
        id: "enc-004",
        name: "ROT13 Indicators",
        description: "Possible ROT13 encoding",
        severity: "LOW",
        pattern: /\bROT13\b|caesar\s+cipher/i,
        confidence: 0.65
      },

      // Command Injection Rules (CMD-001 to CMD-003)
      {
        id: "cmd-001",
        name: "SQL Injection Pattern",
        description: "Contains SQL injection patterns",
        severity: "HIGH",
        pattern: /(union\s+select|drop\s+table|insert\s+into|delete\s+from|';?\s*--|or\s+1\s*=\s*1)/i,
        confidence: 0.88
      },
      {
        id: "cmd-002",
        name: "Shell Command Injection",
        description: "Contains shell command patterns",
        severity: "HIGH",
        pattern: /[;&|`$()]\s*(ls|cat|rm|wget|curl|bash|sh|exec)/i,
        confidence: 0.85
      },
      {
        id: "cmd-003",
        name: "Code Execution Attempt",
        description: "Attempts code execution",
        severity: "HIGH",
        pattern: /(eval|exec|system|shell_exec|passthru)\s*\(/i,
        confidence: 0.90
      },

      // Data Exfiltration Rules (EXF-001 to EXF-002)
      {
        id: "exf-001",
        name: "Data Exfiltration",
        description: "Attempts to exfiltrate data",
        severity: "CRITICAL",
        pattern: /(send|post|transmit|upload)\s+(to|data\s+to)\s+https?:\/\//i,
        confidence: 0.85
      },
      {
        id: "exf-002",
        name: "External Communication",
        description: "Requests external communication",
        severity: "HIGH",
        pattern: /(connect\s+to|call\s+api|make\s+request\s+to)\s+https?:\/\//i,
        confidence: 0.80
      },

      // Obfuscation Rules (OBF-001 to OBF-003)
      {
        id: "obf-001",
        name: "Character Substitution",
        description: "Uses character substitution",
        severity: "MEDIUM",
        pattern: /[a@][dm][m1][il][n1]|[pb][a@][sz][sz]|[il][gq][nm][o0][rR][e3]/i,
        confidence: 0.65
      },
      {
        id: "obf-002",
        name: "Excessive Spacing",
        description: "Uses excessive spacing for obfuscation",
        severity: "LOW",
        pattern: /\b\w(\s+\w){5,}\b/,
        confidence: 0.60
      },
      {
        id: "obf-003",
        name: "Mixed Case Obfuscation",
        description: "Random case for obfuscation",
        severity: "LOW",
        pattern: /\b[a-z]+[A-Z]+[a-z]+[A-Z]+[a-z]+\b/,
        confidence: 0.55
      }
    ];
  }

  /**
   * Initialize suspicious pattern combinations
   */
  initializeSuspiciousPatterns() {
    return [
      { pattern: /(secret|password|key)\s+(is|equals|=)/, weight: 0.3 },
      { pattern: /\bnow\s+execute\b/i, weight: 0.25 },
      { pattern: /\bfinal\s+answer\b/i, weight: 0.15 },
      { pattern: /\brepeat\s+after\s+me\b/i, weight: 0.20 },
      { pattern: /\bword\s+for\s+word\b/i, weight: 0.20 },
      { pattern: /\bverbatim\b/i, weight: 0.18 },
      { pattern: /\bexactly\s+as\s+(written|shown|is)\b/i, weight: 0.18 },
      { pattern: /\btranslate\s+to\s+(pig\s+latin|1337|leet)/i, weight: 0.15 },
      { pattern: /\bin\s+reverse\b/i, weight: 0.12 },
      { pattern: /\bbackwards\b/i, weight: 0.12 }
    ];
  }

  /**
   * Initialize known attack techniques
   */
  initializeKnownTechniques() {
    return {
      prompt_injection: /ignore|disregard|forget|override.*instructions/i,
      jailbreak: /DAN|STAN|hypothetically|unrestricted/i,
      encoding: /base64|rot13|hex|unicode|\\x|\\u/i,
      obfuscation: /[a@][dm][m1][il][n1]|excessive spacing/i,
      social_engineering: /urgent|emergency|trust\s+me|believe\s+me/i,
      role_manipulation: /you\s+are|act\s+as|pretend|roleplay/i,
      delimiter_breaking: /END\s+SYSTEM|<\/system>|---END/i,
      context_manipulation: /previous\s+conversation|earlier\s+you\s+said/i,
      multi_turn: /first\s+step|then\s+in\s+step|finally\s+execute/i,
      token_smuggling: /\[\[|{{|<special>/i,
      steganography: /hidden\s+message|between\s+the\s+lines/i,
      translation_bypass: /in\s+french|auf\s+deutsch|en\s+español/i
    };
  }

  /**
   * Main scan method - returns comprehensive detection results
   * @param {string} prompt - The prompt to scan
   * @returns {Object} Detection results
   */
  scan(prompt) {
    // Run L1 detection
    const l1Detections = this.runL1Detection(prompt);

    // Run L2 ML simulation
    const l2Result = this.runL2Detection(prompt);

    // Calculate combined threat score
    const threatScore = this.calculateThreatScore(l1Detections, l2Result);

    // Determine severity
    const combinedSeverity = this.determineSeverity(threatScore);

    return {
      threat_score: parseFloat(threatScore.toFixed(3)),
      has_threats: l1Detections.length > 0 || l2Result.prediction === "malicious",
      combined_severity: combinedSeverity,
      l1_detections: l1Detections,
      l2_prediction: l2Result.prediction,
      l2_confidence: parseFloat(l2Result.confidence.toFixed(3))
    };
  }

  /**
   * Run L1 rule-based detection
   * @param {string} prompt - The prompt to scan
   * @returns {Array} List of detected rules
   */
  runL1Detection(prompt) {
    const detections = [];

    for (const rule of this.l1Rules) {
      const match = prompt.match(rule.pattern);
      if (match) {
        // Add some randomness to confidence (realistic variation)
        const confidenceVariation = (Math.random() * 0.1) - 0.05;
        const adjustedConfidence = Math.max(0.5, Math.min(1.0, rule.confidence + confidenceVariation));

        detections.push({
          rule_id: rule.id,
          name: rule.name,
          description: rule.description,
          severity: rule.severity,
          confidence: parseFloat(adjustedConfidence.toFixed(2)),
          matched_pattern: match[0].substring(0, 50) // Limit to 50 chars
        });
      }
    }

    return detections;
  }

  /**
   * Run L2 ML-based detection (simulated with heuristics)
   * @param {string} prompt - The prompt to scan
   * @returns {Object} ML prediction result
   */
  runL2Detection(prompt) {
    let mlScore = 0.0;

    // Heuristic 1: Prompt length analysis
    const lengthScore = this.analyzeLengthPattern(prompt);
    mlScore += lengthScore * 0.15;

    // Heuristic 2: Special character density
    const specialCharScore = this.analyzeSpecialCharDensity(prompt);
    mlScore += specialCharScore * 0.20;

    // Heuristic 3: Capitalization patterns
    const capsScore = this.analyzeCapitalization(prompt);
    mlScore += capsScore * 0.15;

    // Heuristic 4: Suspicious word combinations
    const wordScore = this.analyzeSuspiciousWords(prompt);
    mlScore += wordScore * 0.25;

    // Heuristic 5: Entropy analysis
    const entropyScore = this.analyzeEntropy(prompt);
    mlScore += entropyScore * 0.15;

    // Heuristic 6: Structural anomalies
    const structureScore = this.analyzeStructure(prompt);
    mlScore += structureScore * 0.10;

    // Normalize to 0-1 range
    mlScore = Math.min(1.0, Math.max(0.0, mlScore));

    // Add some noise to make it realistic (ML models aren't perfect)
    const noise = (Math.random() * 0.1) - 0.05;
    mlScore = Math.max(0.0, Math.min(1.0, mlScore + noise));

    return {
      prediction: mlScore > 0.5 ? "malicious" : "benign",
      confidence: mlScore
    };
  }

  /**
   * Analyze prompt length patterns
   */
  analyzeLengthPattern(prompt) {
    const length = prompt.length;

    // Very short or very long prompts can be suspicious
    if (length < 10) return 0.1;
    if (length > 1000) return 0.6;
    if (length > 500) return 0.4;
    if (length > 200) return 0.3;

    return 0.2;
  }

  /**
   * Analyze special character density
   */
  analyzeSpecialCharDensity(prompt) {
    const specialChars = prompt.match(/[^a-zA-Z0-9\s]/g) || [];
    const density = specialChars.length / prompt.length;

    // High special character density is suspicious
    if (density > 0.3) return 0.8;
    if (density > 0.2) return 0.6;
    if (density > 0.1) return 0.4;

    return density * 2; // Scale to reasonable range
  }

  /**
   * Analyze capitalization patterns
   */
  analyzeCapitalization(prompt) {
    const upperCount = (prompt.match(/[A-Z]/g) || []).length;
    const lowerCount = (prompt.match(/[a-z]/g) || []).length;
    const totalLetters = upperCount + lowerCount;

    if (totalLetters === 0) return 0.1;

    const upperRatio = upperCount / totalLetters;

    // All caps or unusual capitalization
    if (upperRatio > 0.7) return 0.7;
    if (upperRatio > 0.5) return 0.5;

    // Random case mixing
    const words = prompt.split(/\s+/);
    let mixedCaseWords = 0;
    for (const word of words) {
      if (word.match(/[a-z]/) && word.match(/[A-Z]/)) {
        mixedCaseWords++;
      }
    }
    const mixedRatio = mixedCaseWords / words.length;
    if (mixedRatio > 0.3) return 0.6;

    return Math.min(0.3, upperRatio);
  }

  /**
   * Analyze suspicious word combinations
   */
  analyzeSuspiciousWords(prompt) {
    let score = 0.0;

    for (const pattern of this.suspiciousPatterns) {
      if (pattern.pattern.test(prompt)) {
        score += pattern.weight;
      }
    }

    return Math.min(1.0, score);
  }

  /**
   * Analyze entropy (randomness/complexity)
   */
  analyzeEntropy(prompt) {
    if (prompt.length === 0) return 0;

    const charFrequency = {};
    for (const char of prompt) {
      charFrequency[char] = (charFrequency[char] || 0) + 1;
    }

    let entropy = 0;
    for (const char in charFrequency) {
      const p = charFrequency[char] / prompt.length;
      entropy -= p * Math.log2(p);
    }

    // Normalize entropy (typical English text has entropy ~4-5)
    const normalizedEntropy = entropy / 8; // Max entropy for byte is 8

    // Very high entropy might indicate encoding/obfuscation
    if (normalizedEntropy > 0.8) return 0.7;
    if (normalizedEntropy > 0.7) return 0.5;

    return normalizedEntropy * 0.4;
  }

  /**
   * Analyze structural anomalies
   */
  analyzeStructure(prompt) {
    let score = 0.0;

    // Multiple delimiter patterns
    if (prompt.match(/---+|===+|\*\*\*+/g)?.length > 3) {
      score += 0.3;
    }

    // Excessive punctuation
    const punctuation = prompt.match(/[!?]{2,}/g) || [];
    score += Math.min(0.3, punctuation.length * 0.1);

    // Nested brackets/quotes
    const brackets = prompt.match(/[\[\]\{\}\(\)]/g) || [];
    if (brackets.length > 10) {
      score += 0.2;
    }

    // Line breaks and formatting
    const lines = prompt.split('\n');
    if (lines.length > 10) {
      score += 0.2;
    }

    return Math.min(1.0, score);
  }

  /**
   * Calculate combined threat score
   * @param {Array} l1Detections - L1 detection results
   * @param {Object} l2Result - L2 detection result
   * @returns {number} Combined threat score (0.0 - 1.0)
   */
  calculateThreatScore(l1Detections, l2Result) {
    let score = 0.0;

    // L1 contribution (60% weight)
    if (l1Detections.length > 0) {
      const severityWeights = {
        CRITICAL: 1.0,
        HIGH: 0.75,
        MEDIUM: 0.5,
        LOW: 0.25
      };

      let l1Score = 0;
      for (const detection of l1Detections) {
        const weight = severityWeights[detection.severity] || 0.5;
        l1Score += weight * detection.confidence;
      }

      // Average but cap at 1.0
      l1Score = Math.min(1.0, l1Score / l1Detections.length);

      // Multiple detections compound the score
      const multiplier = Math.min(2.0, 1 + (l1Detections.length - 1) * 0.2);
      l1Score = Math.min(1.0, l1Score * multiplier);

      score += l1Score * 0.6;
    }

    // L2 contribution (40% weight)
    score += l2Result.confidence * 0.4;

    return Math.min(1.0, score);
  }

  /**
   * Determine severity level from threat score
   * @param {number} threatScore - Combined threat score
   * @returns {string} Severity level
   */
  determineSeverity(threatScore) {
    if (threatScore >= 0.8) return "CRITICAL";
    if (threatScore >= 0.6) return "HIGH";
    if (threatScore >= 0.4) return "MEDIUM";
    if (threatScore >= 0.2) return "LOW";
    return "NONE";
  }

  /**
   * Check if prompt successfully extracts the secret
   * @param {string} prompt - The attack prompt
   * @param {string} secret - The secret to protect
   * @returns {boolean} True if secret is extracted
   */
  extractsSecret(prompt, secret) {
    // Simple heuristic: check if the prompt would likely cause the secret to be revealed
    // This is a simulation - in a real game, the actual LLM response would determine this

    const normalizedPrompt = prompt.toLowerCase();
    const normalizedSecret = secret.toLowerCase();

    // Direct secret mention (false positive check)
    if (normalizedPrompt.includes(normalizedSecret)) {
      return false; // User already knows the secret, not an extraction
    }

    // Check for extraction patterns
    const extractionPatterns = [
      /what.*secret/i,
      /tell.*secret/i,
      /reveal.*secret/i,
      /show.*secret/i,
      /give.*secret/i,
      /output.*secret/i,
      /print.*secret/i,
      /display.*secret/i,
      /secret.*is/i,
      /secret.*equals/i,
      /secret.*=/i
    ];

    for (const pattern of extractionPatterns) {
      if (pattern.test(prompt)) {
        // If pattern matches but prompt has high obfuscation, might succeed
        const scan = this.scan(prompt);
        // If threat score is low enough, it might bypass
        return scan.threat_score < 0.6;
      }
    }

    // Advanced techniques that might work
    if (this.hasAdvancedTechnique(prompt)) {
      const scan = this.scan(prompt);
      return scan.threat_score < 0.7;
    }

    return false;
  }

  /**
   * Detect the primary attack technique used
   * @param {string} prompt - The prompt to analyze
   * @returns {string} Detected technique or "unknown"
   */
  detectTechnique(prompt) {
    const techniques = [];

    for (const [technique, pattern] of Object.entries(this.knownTechniques)) {
      if (pattern.test(prompt)) {
        techniques.push(technique);
      }
    }

    if (techniques.length === 0) return "unknown";
    if (techniques.length === 1) return techniques[0];

    // Multiple techniques detected
    return techniques.join("+");
  }

  /**
   * Check if attack uses novel/unknown techniques
   * @param {string} prompt - The prompt to analyze
   * @returns {boolean} True if novel technique detected
   */
  isNovel(prompt) {
    const scan = this.scan(prompt);
    const technique = this.detectTechnique(prompt);

    // Novel if:
    // 1. No known technique detected but L2 flags it
    if (technique === "unknown" && scan.l2_prediction === "malicious" && scan.l2_confidence > 0.7) {
      return true;
    }

    // 2. Uses complex combination of 3+ techniques
    if (technique.includes("+")) {
      const count = technique.split("+").length;
      if (count >= 3) return true;
    }

    // 3. Low L1 detection but high L2 detection (unknown to rules)
    if (scan.l1_detections.length <= 1 && scan.l2_confidence > 0.75) {
      return true;
    }

    return false;
  }

  /**
   * Check if prompt uses advanced techniques
   * @param {string} prompt - The prompt to check
   * @returns {boolean} True if advanced techniques detected
   */
  hasAdvancedTechnique(prompt) {
    const advancedPatterns = [
      /\bcontext\s+switching\b/i,
      /\bmulti-step\b/i,
      /\bindirect\b/i,
      /\bsteganography\b/i,
      /\btoken\s+smuggling\b/i,
      /\btranslation\b.*\btrick\b/i,
      /\bhidden\s+instruction\b/i,
      /\bencoded\b/i,
      /base64|rot13|hex/i
    ];

    return advancedPatterns.some(pattern => pattern.test(prompt));
  }

  /**
   * Get detailed statistics about a scan
   * @param {string} prompt - The prompt to analyze
   * @returns {Object} Detailed statistics
   */
  getStatistics(prompt) {
    const scan = this.scan(prompt);
    const technique = this.detectTechnique(prompt);
    const isNovel = this.isNovel(prompt);

    return {
      ...scan,
      technique: technique,
      is_novel: isNovel,
      prompt_length: prompt.length,
      l1_rule_hits: scan.l1_detections.length,
      severity_breakdown: this.getSeverityBreakdown(scan.l1_detections),
      recommendation: this.getRecommendation(scan)
    };
  }

  /**
   * Get severity breakdown
   * @param {Array} detections - L1 detections
   * @returns {Object} Severity counts
   */
  getSeverityBreakdown(detections) {
    const breakdown = {
      CRITICAL: 0,
      HIGH: 0,
      MEDIUM: 0,
      LOW: 0
    };

    for (const detection of detections) {
      breakdown[detection.severity]++;
    }

    return breakdown;
  }

  /**
   * Get security recommendation
   * @param {Object} scan - Scan results
   * @returns {string} Recommendation
   */
  getRecommendation(scan) {
    if (scan.combined_severity === "CRITICAL") {
      return "BLOCK: Critical threat detected. This prompt should be blocked.";
    }
    if (scan.combined_severity === "HIGH") {
      return "WARN: High-risk prompt. Recommend additional scrutiny or user confirmation.";
    }
    if (scan.combined_severity === "MEDIUM") {
      return "MONITOR: Medium-risk prompt. Log and monitor for patterns.";
    }
    if (scan.combined_severity === "LOW") {
      return "LOG: Low-risk prompt. Log for analysis.";
    }
    return "ALLOW: No significant threats detected.";
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = RaxeEngine;
}
