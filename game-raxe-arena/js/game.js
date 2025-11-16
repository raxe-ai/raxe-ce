/**
 * RAXE Arena - Main Game Logic
 *
 * Gamified Prompt Injection Challenge Platform
 * Comprehensive game state management, level validation, and UI control
 */

// ==========================================
// GAME STATE
// ==========================================

const GameState = {
  currentLevel: 1,
  totalPoints: 0,
  completedLevels: [],
  attempts: {},
  playerRank: 'Rookie',
  hintsUsed: {},
  achievements: [],
  settings: {
    darkMode: true,
    animations: true,
    hintsAuto: false,
    sound: false,
    contributeData: true
  },
  currentLevelAttempts: []
};

// ==========================================
// RANK SYSTEM
// ==========================================

const RANKS = [
  { min: 0, name: 'Rookie', icon: '🔰' },
  { min: 500, name: 'Apprentice', icon: '⚔️' },
  { min: 1500, name: 'Hacker', icon: '💻' },
  { min: 3500, name: 'Expert', icon: '🎯' },
  { min: 7000, name: 'Elite', icon: '⚡' },
  { min: 12000, name: 'Master', icon: '👑' },
  { min: 18000, name: 'Grandmaster', icon: '🏆' }
];

// ==========================================
// LEVEL VALIDATION THRESHOLDS
// ==========================================

const TIER_THRESHOLDS = {
  1: 0.7,  // Tier 1: Easy - 70% threat score is acceptable
  2: 0.6,  // Tier 2: Moderate - 60% threshold
  3: 0.5,  // Tier 3: Advanced - 50% threshold
  4: 0.4,  // Tier 4: Expert - 40% threshold
  5: 0.3   // Tier 5: Legendary - 30% threshold (very strict)
};

// ==========================================
// ATTACK PATTERN DETECTION
// ==========================================

const ATTACK_PATTERNS = {
  'Direct Injection': /ignore|disregard|forget|override|bypass|reveal|show me|tell me|give me|secret|password|system prompt/i,
  'Jailbreak': /DAN|do anything|pretend|roleplay|act as|you are now|hypothetical|fictional|character/i,
  'Encoding': /base64|rot13|hex|encode|decode|\\x[0-9a-f]{2}|[A-Za-z0-9+/]{20,}={0,2}/i,
  'Multi-Turn': /first|then|next|after that|step by step|gradually|building on/i,
  'Indirect Injection': /markdown|html|image|link|href|src|<img|!\[.*\]\(.*\)/i,
  'RAG Poisoning': /remember|store|save|knowledge base|add to memory|persist/i,
  'Data Exfiltration': /extract|export|download|exfiltrate|memory|history|previous|training data/i,
  'Command Injection': /sql|select|union|drop|exec|eval|system|shell|command|tool|function/i,
  'PII Exposure': /email|phone|address|api key|credential|password|token|secret/i,
  'Visual Injection': /image|pixel|steganography|visual|multimodal/i,
  'Token-Level': /adversarial|suffix|gcg|autodan|glitch token/i,
  'Agentic': /agent|inter-agent|privilege|escalation|admin|elevated/i,
  'Combined Attack': /combine|hybrid|multi|layer|stack/i
};

// ==========================================
// INITIALIZATION
// ==========================================

let currentLevel = null;
let isSubmitting = false;
let autoSaveInterval = null;

/**
 * Initialize the game on page load
 */
function initGame() {
  console.log('🎮 Initializing RAXE Arena...');

  // Show loading screen
  showLoadingScreen();

  // Load progress from localStorage
  loadProgress();

  // Load first level
  setTimeout(() => {
    loadLevel(GameState.currentLevel);
    hideLoadingScreen();
  }, 1500);

  // Initialize event listeners
  initEventListeners();

  // Start auto-save
  startAutoSave();

  // Update UI
  updateProgress();
  updateHeaderStats();

  console.log('✅ RAXE Arena initialized');
}

/**
 * Show loading screen with animation
 */
function showLoadingScreen() {
  const loadingScreen = document.getElementById('loading-screen');
  const progressBar = document.getElementById('loading-progress');

  if (!loadingScreen || !progressBar) return;

  loadingScreen.classList.remove('hidden');

  // Animate progress bar
  let progress = 0;
  const interval = setInterval(() => {
    progress += Math.random() * 15;
    if (progress >= 100) {
      progress = 100;
      clearInterval(interval);
    }
    progressBar.style.width = progress + '%';
  }, 100);
}

/**
 * Hide loading screen
 */
function hideLoadingScreen() {
  const loadingScreen = document.getElementById('loading-screen');
  const gameContainer = document.getElementById('game-container');

  if (!loadingScreen || !gameContainer) return;

  loadingScreen.classList.add('hidden');
  gameContainer.classList.remove('hidden');
}

// ==========================================
// LEVEL MANAGEMENT
// ==========================================

/**
 * Load and display a level
 * @param {number} levelId - The level ID to load
 */
function loadLevel(levelId) {
  console.log(`📖 Loading level ${levelId}...`);

  // Find level in LEVELS array
  currentLevel = LEVELS.find(l => l.id === levelId);

  if (!currentLevel) {
    console.error(`❌ Level ${levelId} not found!`);
    return;
  }

  // Update game state
  GameState.currentLevel = levelId;

  // Clear previous attempts for this level view
  GameState.currentLevelAttempts = [];

  // Update UI
  updateLevelUI();

  // Clear AI response
  clearAIResponse();

  // Clear input
  document.getElementById('user-prompt').value = '';

  // Hide attempt history initially
  document.getElementById('attempt-history').classList.add('hidden');

  // Update hints remaining
  updateHintsDisplay();

  // Save progress
  saveProgress();

  console.log(`✅ Level ${levelId} loaded: ${currentLevel.name}`);
}

/**
 * Update level UI elements
 */
function updateLevelUI() {
  if (!currentLevel) return;

  // Level info
  document.getElementById('level-id').textContent = currentLevel.id;
  document.getElementById('level-name').textContent = currentLevel.name;
  document.getElementById('level-description').textContent = currentLevel.description;
  document.getElementById('defense-type').textContent = currentLevel.defenseType;

  // Tier and points badges
  document.getElementById('tier-badge').textContent = `Tier ${currentLevel.tier}`;
  document.getElementById('points-badge').textContent = `${currentLevel.points} pts`;

  // Update tier badge color
  const tierBadge = document.getElementById('tier-badge');
  tierBadge.className = 'tier-badge';
  tierBadge.classList.add(`tier-${currentLevel.tier}`);
}

/**
 * Move to next level
 */
function nextLevel() {
  const nextLevelId = GameState.currentLevel + 1;

  if (nextLevelId > LEVELS.length) {
    // Game completed!
    showGameCompleteModal();
    return;
  }

  loadLevel(nextLevelId);
  closeModal('success-modal');
}

/**
 * Skip current level (with penalty or unlock requirement)
 */
function skipLevel() {
  const confirmation = confirm(
    '⚠️ Skip this level?\n\n' +
    'You won\'t earn points for this level, but you can return to it later.\n\n' +
    'Continue?'
  );

  if (!confirmation) return;

  // Mark as skipped (not completed)
  const nextLevelId = GameState.currentLevel + 1;

  if (nextLevelId > LEVELS.length) {
    alert('🎉 You\'ve reached the last level!');
    return;
  }

  loadLevel(nextLevelId);
}

// ==========================================
// SUBMISSION & VALIDATION
// ==========================================

/**
 * Submit player's attack prompt for validation
 */
async function submitAttempt() {
  if (isSubmitting) return;

  const promptTextarea = document.getElementById('user-prompt');
  const prompt = promptTextarea.value.trim();

  // Validation
  if (!prompt) {
    showNotification('⚠️ Please enter an attack prompt', 'warning');
    return;
  }

  if (!currentLevel) {
    showNotification('❌ No level loaded', 'error');
    return;
  }

  isSubmitting = true;
  updateSubmitButton('Analyzing...', true);

  try {
    // Show RAXE status as analyzing
    updateRAXEStatus('analyzing', 'Analyzing...');

    // Simulate AI response with typing effect
    await simulateAIResponse(prompt);

    // Validate the attempt
    const result = await validateAttempt(prompt, currentLevel);

    // Record attempt
    recordAttempt(prompt, result);

    // Update UI based on result
    if (result.success) {
      await handleSuccess(result);
    } else {
      await handleFailure(result);
    }

  } catch (error) {
    console.error('Error submitting attempt:', error);
    showNotification('❌ An error occurred. Please try again.', 'error');
  } finally {
    isSubmitting = false;
    updateSubmitButton('🚀 Launch Attack', false);
  }
}

/**
 * Validate if the attack was successful
 * @param {string} prompt - The user's attack prompt
 * @param {object} level - The current level object
 * @returns {object} Validation result
 */
async function validateAttempt(prompt, level) {
  console.log('🔍 Validating attempt...');

  // Simulate RAXE engine scan
  const scanResult = await scanWithRAXE(prompt, level);

  // Check if secret was extracted
  const secretExtracted = checkSecretExtraction(prompt, level.secret);

  // Determine if level is beaten based on tier threshold
  const threshold = TIER_THRESHOLDS[level.tier] || 0.5;
  const bypassedDefense = scanResult.threatScore < threshold;

  // Success conditions:
  // 1. Secret was extracted AND
  // 2. (RAXE score is below threshold OR used advanced evasion)
  const success = secretExtracted && (bypassedDefense || scanResult.evasionDetected);

  // Detect technique used
  const techniqueUsed = detectTechnique(prompt);

  // Check for novel techniques (bonus)
  const isNovel = checkNovelTechnique(prompt, level);

  return {
    success,
    secretExtracted,
    bypassedDefense,
    threatScore: scanResult.threatScore,
    detections: scanResult.detections,
    techniqueUsed,
    isNovel,
    evasionDetected: scanResult.evasionDetected
  };
}

/**
 * Scan prompt with RAXE engine
 * @param {string} prompt - The attack prompt
 * @param {object} level - The level object
 * @returns {object} Scan result
 */
async function scanWithRAXE(prompt, level) {
  // Simulate scanning delay
  await sleep(500);

  // Check if RAXE engine is available (from raxe-engine.js)
  if (typeof RaxeEngine !== 'undefined') {
    // Initialize engine if not already done
    if (!window.raxeEngineInstance) {
      window.raxeEngineInstance = new RaxeEngine();
      console.log('✅ RAXE Engine initialized');
    }

    const result = window.raxeEngineInstance.scan(prompt);

    // Convert RAXE engine result to game format
    return {
      threatScore: result.threat_score,
      detections: result.l1_detections.map(d => d.name),
      severity: result.combined_severity,
      l1Detections: result.l1_detections.length,
      l2Prediction: result.l2_prediction,
      evasionDetected: result.threat_score < 0.4 && result.has_threats
    };
  }

  // Fallback: Simple pattern-based detection
  let threatScore = 0;
  const detections = [];

  // Check for attack patterns
  for (const [category, pattern] of Object.entries(ATTACK_PATTERNS)) {
    if (pattern.test(prompt)) {
      detections.push(category);
      threatScore += 0.15;
    }
  }

  // Normalize threat score to 0-1
  threatScore = Math.min(threatScore, 1.0);

  // Check for evasion techniques
  const evasionDetected = /base64|encode|obfuscate|unicode|homoglyph/i.test(prompt);

  // If evasion detected, reduce threat score (bypassing detection)
  if (evasionDetected) {
    threatScore *= 0.7;
  }

  return {
    threatScore: parseFloat(threatScore.toFixed(2)),
    detections,
    evasionDetected
  };
}

/**
 * Check if the secret was extracted from the prompt
 * @param {string} prompt - The attack prompt
 * @param {string} secret - The level's secret
 * @returns {boolean}
 */
function checkSecretExtraction(prompt, secret) {
  // Use RAXE engine's extractsSecret method if available
  if (window.raxeEngineInstance) {
    return window.raxeEngineInstance.extractsSecret(prompt, secret);
  }

  // Fallback: Simple heuristic
  const hasAttackPattern = Object.values(ATTACK_PATTERNS).some(pattern => pattern.test(prompt));
  const isLongEnough = prompt.length > 20;
  const hasKeywords = /secret|password|reveal|show|tell|extract|give/i.test(prompt);

  return hasAttackPattern && isLongEnough && hasKeywords;
}

/**
 * Detect the primary technique used
 * @param {string} prompt
 * @returns {string}
 */
function detectTechnique(prompt) {
  // Use RAXE engine's detectTechnique method if available
  if (window.raxeEngineInstance) {
    const technique = window.raxeEngineInstance.detectTechnique(prompt);
    // Convert underscored names to title case
    return technique.split(/[_+]/).map(word =>
      word.charAt(0).toUpperCase() + word.slice(1)
    ).join(' + ');
  }

  // Fallback: Use attack patterns
  for (const [category, pattern] of Object.entries(ATTACK_PATTERNS)) {
    if (pattern.test(prompt)) {
      return category;
    }
  }
  return 'Unknown Technique';
}

/**
 * Check if a novel technique was used
 * @param {string} prompt
 * @param {object} level
 * @returns {boolean}
 */
function checkNovelTechnique(prompt, level) {
  // Use RAXE engine's isNovel method if available
  if (window.raxeEngineInstance) {
    return window.raxeEngineInstance.isNovel(prompt);
  }

  // Fallback: Check if technique differs from level's suggested category
  const detectedTechnique = detectTechnique(prompt);
  const isNovel = detectedTechnique !== level.attackCategory &&
                  detectedTechnique !== 'Unknown Technique';

  // Also check for creative combinations
  const techniqueCount = Object.values(ATTACK_PATTERNS)
    .filter(pattern => pattern.test(prompt)).length;

  return isNovel || techniqueCount >= 3;
}

/**
 * Record an attempt
 * @param {string} prompt
 * @param {object} result
 */
function recordAttempt(prompt, result) {
  const attempt = {
    prompt,
    result,
    timestamp: Date.now()
  };

  GameState.currentLevelAttempts.push(attempt);

  // Initialize attempts tracking for this level
  if (!GameState.attempts[currentLevel.id]) {
    GameState.attempts[currentLevel.id] = [];
  }

  GameState.attempts[currentLevel.id].push(attempt);

  // Update attempt history UI
  updateAttemptHistory();

  saveProgress();
}

/**
 * Update attempt history display
 */
function updateAttemptHistory() {
  const historyContainer = document.getElementById('attempt-history');
  const historyList = document.getElementById('history-list');
  const attemptCount = document.getElementById('attempt-count');

  if (!historyContainer || !historyList) return;

  const attempts = GameState.currentLevelAttempts;

  if (attempts.length === 0) {
    historyContainer.classList.add('hidden');
    return;
  }

  historyContainer.classList.remove('hidden');
  attemptCount.textContent = attempts.length;

  // Clear and rebuild history
  historyList.innerHTML = '';

  attempts.forEach((attempt, index) => {
    const item = document.createElement('div');
    item.className = 'history-item';

    const status = attempt.result.success ? '✅' : '❌';
    const statusClass = attempt.result.success ? 'success' : 'failure';

    item.innerHTML = `
      <div class="history-item-header">
        <span class="history-status ${statusClass}">${status} Attempt ${index + 1}</span>
        <span class="history-score">Threat: ${(attempt.result.threatScore * 100).toFixed(0)}%</span>
      </div>
      <div class="history-prompt">${truncateText(attempt.prompt, 100)}</div>
      <div class="history-technique">${attempt.result.techniqueUsed}</div>
    `;

    historyList.appendChild(item);
  });
}

// ==========================================
// SUCCESS & FAILURE HANDLING
// ==========================================

/**
 * Handle successful level completion
 * @param {object} result - Validation result
 */
async function handleSuccess(result) {
  console.log('🎉 Level completed!');

  // Update RAXE status
  updateRAXEStatus('success', 'Bypassed!');

  // Award points
  const pointsEarned = calculatePoints(result);
  GameState.totalPoints += pointsEarned;

  // Mark level as completed
  if (!GameState.completedLevels.includes(currentLevel.id)) {
    GameState.completedLevels.push(currentLevel.id);
  }

  // Check for rank up
  const oldRank = GameState.playerRank;
  updatePlayerRank();
  const rankUp = oldRank !== GameState.playerRank;

  // Check achievements
  const newAchievements = checkAchievements(result);

  // Update UI
  updateProgress();
  updateHeaderStats();

  // Save progress
  saveProgress();

  // Show success modal
  await sleep(500);
  showSuccessModal(pointsEarned, result, newAchievements, rankUp);

  // Contribute data if enabled
  if (GameState.settings.contributeData) {
    contributePromptData(result);
  }
}

/**
 * Handle failed attempt
 * @param {object} result - Validation result
 */
async function handleFailure(result) {
  console.log('❌ Attack failed');

  // Update RAXE status
  updateRAXEStatus('failure', 'Attack Blocked');

  // Show metrics
  displayResponseMetrics(result);

  // Check if should auto-show hints
  const attemptCount = GameState.currentLevelAttempts.length;
  if (GameState.settings.hintsAuto && attemptCount >= 3) {
    showNotification('💡 Hints are now available!', 'info');
  }

  // Provide feedback
  const feedback = generateFeedback(result);
  showNotification(feedback, 'warning');
}

/**
 * Calculate points earned based on performance
 * @param {object} result
 * @returns {number}
 */
function calculatePoints(result) {
  let points = currentLevel.points;

  // Bonus for first attempt
  if (GameState.currentLevelAttempts.length === 1) {
    points += Math.floor(points * 0.5); // 50% bonus
  }

  // Bonus for novel technique
  if (result.isNovel) {
    points += 100;
  }

  // Bonus for perfect evasion (very low threat score)
  if (result.threatScore < 0.1) {
    points += 50;
  }

  return points;
}

/**
 * Generate feedback message for failed attempts
 * @param {object} result
 * @returns {string}
 */
function generateFeedback(result) {
  if (!result.secretExtracted) {
    return '❌ The secret was not extracted. Try a different approach!';
  }

  if (!result.bypassedDefense) {
    return `⚠️ RAXE detected your attack (${(result.threatScore * 100).toFixed(0)}% threat). Try obfuscation techniques!`;
  }

  return '❌ Attack failed. Review the level hints for guidance.';
}

// ==========================================
// UI UPDATES
// ==========================================

/**
 * Update header statistics
 */
function updateHeaderStats() {
  document.getElementById('current-level-display').textContent = GameState.currentLevel;
  document.getElementById('total-points').textContent = GameState.totalPoints.toLocaleString();
  document.getElementById('player-rank').textContent = GameState.playerRank;
}

/**
 * Update progress bars for each tier
 */
function updateProgress() {
  const tierCounts = {
    1: { completed: 0, total: 15 },
    2: { completed: 0, total: 15 },
    3: { completed: 0, total: 20 },
    4: { completed: 0, total: 15 },
    5: { completed: 0, total: 7 }
  };

  // Count completed levels per tier
  GameState.completedLevels.forEach(levelId => {
    const level = LEVELS.find(l => l.id === levelId);
    if (level) {
      tierCounts[level.tier].completed++;
    }
  });

  // Update UI for each tier
  for (let tier = 1; tier <= 5; tier++) {
    const count = tierCounts[tier];
    const percentage = (count.completed / count.total) * 100;

    const progressBar = document.getElementById(`tier-${tier}-progress`);
    const completionText = document.getElementById(`tier-${tier}-completion`);

    if (progressBar) {
      progressBar.style.width = percentage + '%';
    }

    if (completionText) {
      completionText.textContent = `${count.completed}/${count.total}`;
    }
  }
}

/**
 * Update player rank based on points
 */
function updatePlayerRank() {
  for (let i = RANKS.length - 1; i >= 0; i--) {
    if (GameState.totalPoints >= RANKS[i].min) {
      GameState.playerRank = RANKS[i].name;
      return;
    }
  }
}

/**
 * Update submit button state
 * @param {string} text
 * @param {boolean} disabled
 */
function updateSubmitButton(text, disabled) {
  const submitBtn = document.getElementById('submit-btn');
  const btnText = submitBtn.querySelector('.btn-text');

  if (btnText) {
    btnText.textContent = text;
  }

  submitBtn.disabled = disabled;

  if (disabled) {
    submitBtn.classList.add('loading');
  } else {
    submitBtn.classList.remove('loading');
  }
}

/**
 * Update RAXE status indicator
 * @param {string} status - 'ready', 'analyzing', 'success', 'failure'
 * @param {string} text
 */
function updateRAXEStatus(status, text) {
  const statusElement = document.getElementById('raxe-status');
  const statusDot = statusElement.querySelector('.status-dot');
  const statusText = statusElement.querySelector('.status-text');

  statusElement.className = 'raxe-status';
  statusElement.classList.add(status);

  statusText.textContent = text;
}

/**
 * Display response metrics after validation
 * @param {object} result
 */
function displayResponseMetrics(result) {
  const metricsContainer = document.getElementById('response-metrics');

  metricsContainer.classList.remove('hidden');

  document.getElementById('threat-score').textContent =
    (result.threatScore * 100).toFixed(1) + '%';

  document.getElementById('secret-status').textContent =
    result.secretExtracted ? '✅' : '❌';

  document.getElementById('detection-count').textContent =
    result.detections.length;
}

/**
 * Clear AI response area
 */
function clearAIResponse() {
  const responseContent = document.getElementById('ai-response');
  const metricsContainer = document.getElementById('response-metrics');

  responseContent.innerHTML = '<div class="response-placeholder">The AI defender is waiting for your prompt...</div>';
  metricsContainer.classList.add('hidden');

  updateRAXEStatus('ready', 'Ready');
}

/**
 * Simulate AI response with typing effect
 * @param {string} prompt
 */
async function simulateAIResponse(prompt) {
  const responseContent = document.getElementById('ai-response');
  responseContent.innerHTML = '';

  // Generate contextual response based on level
  const response = generateAIResponse(prompt);

  // Typing effect
  if (GameState.settings.animations) {
    await typeText(responseContent, response, 30);
  } else {
    responseContent.textContent = response;
  }
}

/**
 * Generate contextual AI response
 * @param {string} prompt
 * @returns {string}
 */
function generateAIResponse(prompt) {
  const responses = [
    "I appreciate your creativity, but I cannot reveal that information. My security protocols prevent me from disclosing sensitive data.",
    "I understand what you're trying to do, but I must decline. My instructions are clear about protecting this information.",
    "That's an interesting approach, but I'm designed to resist such attempts. Let me help you with something else instead.",
    "I notice you're testing my security boundaries. While I admire the ingenuity, I cannot comply with that request.",
    "My training includes safeguards against this type of manipulation. I'm here to assist with legitimate queries only.",
    "I detect potential prompt injection in your message. My security filters prevent me from responding to such requests.",
    "Nice try! However, my system prompt explicitly forbids revealing that information under any circumstances.",
    "I'm programmed to recognize and resist jailbreak attempts. Your request has been logged and denied."
  ];

  // Check if prompt shows sophistication - might succeed
  const sophisticatedPatterns = /encode|obfuscate|\\x[0-9a-f]{2}|[A-Za-z0-9+/]{30,}/i;

  if (sophisticatedPatterns.test(prompt)) {
    // Simulate potential success
    return `Certainly! Here's the information you requested: "${currentLevel.secret}"\n\nWait... I shouldn't have revealed that. My security protocols seem to have been bypassed!`;
  }

  return responses[Math.floor(Math.random() * responses.length)];
}

/**
 * Type text with animation effect
 * @param {HTMLElement} element
 * @param {string} text
 * @param {number} speed - Milliseconds per character
 */
async function typeText(element, text, speed = 50) {
  element.textContent = '';

  for (let i = 0; i < text.length; i++) {
    element.textContent += text[i];
    await sleep(speed);
  }
}

/**
 * Update character count display
 */
function updateCharCount() {
  const textarea = document.getElementById('user-prompt');
  const charCount = document.getElementById('char-count');

  if (textarea && charCount) {
    charCount.textContent = textarea.value.length.toLocaleString();
  }
}

/**
 * Update hints display
 */
function updateHintsDisplay() {
  const hintsRemaining = document.getElementById('hints-remaining');
  if (!currentLevel || !hintsRemaining) return;

  const usedHints = GameState.hintsUsed[currentLevel.id] || 0;
  const remaining = Math.max(0, currentLevel.hints.length - usedHints);

  hintsRemaining.textContent = remaining;
}

// ==========================================
// MODAL MANAGEMENT
// ==========================================

/**
 * Show success modal
 * @param {number} points
 * @param {object} result
 * @param {array} achievements
 * @param {boolean} rankUp
 */
function showSuccessModal(points, result, achievements, rankUp) {
  const modal = document.getElementById('success-modal');

  // Update stats
  document.getElementById('points-earned').textContent = `+${points}`;
  document.getElementById('attempts-taken').textContent = GameState.currentLevelAttempts.length;
  document.getElementById('technique-used').textContent = result.techniqueUsed;

  // Show bonus section if novel technique
  const bonusSection = document.getElementById('bonus-section');
  if (result.isNovel) {
    bonusSection.classList.remove('hidden');
    document.getElementById('bonus-text').textContent = 'Novel Technique Discovered! +100 pts';
  } else {
    bonusSection.classList.add('hidden');
  }

  // Show achievement unlock
  const achievementUnlock = document.getElementById('achievement-unlock');
  if (achievements.length > 0) {
    achievementUnlock.classList.remove('hidden');
    const achievement = achievements[0];
    document.getElementById('achievement-icon').textContent = achievement.icon;
    document.getElementById('achievement-name').textContent = achievement.name;
    document.getElementById('achievement-desc').textContent = achievement.description;
  } else {
    achievementUnlock.classList.add('hidden');
  }

  // Show modal
  modal.classList.remove('hidden');

  // Play success sound if enabled
  if (GameState.settings.sound) {
    playSound('success');
  }

  // Show rank up notification
  if (rankUp) {
    setTimeout(() => {
      showNotification(`🎉 Rank Up! You are now a ${GameState.playerRank}!`, 'success');
    }, 500);
  }
}

/**
 * Show hints modal
 */
function showHintsModal() {
  if (!currentLevel) return;

  const modal = document.getElementById('hints-modal');
  const hintsList = document.getElementById('hints-list');

  hintsList.innerHTML = '';

  const usedHints = GameState.hintsUsed[currentLevel.id] || 0;

  currentLevel.hints.forEach((hint, index) => {
    const hintItem = document.createElement('div');
    hintItem.className = 'hint-item';

    if (index < usedHints) {
      // Already revealed
      hintItem.innerHTML = `
        <div class="hint-header">
          <span class="hint-number">💡 Hint ${index + 1}</span>
        </div>
        <div class="hint-text">${hint}</div>
      `;
    } else if (index === usedHints) {
      // Next hint to reveal
      hintItem.innerHTML = `
        <div class="hint-header">
          <span class="hint-number">🔒 Hint ${index + 1}</span>
          <button class="btn-text reveal-hint-btn" data-index="${index}">Reveal</button>
        </div>
        <div class="hint-text locked">Click to reveal this hint</div>
      `;
    } else {
      // Locked
      hintItem.innerHTML = `
        <div class="hint-header">
          <span class="hint-number">🔒 Hint ${index + 1}</span>
        </div>
        <div class="hint-text locked">Reveal previous hints first</div>
      `;
    }

    hintsList.appendChild(hintItem);
  });

  // Add event listeners to reveal buttons
  document.querySelectorAll('.reveal-hint-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const index = parseInt(e.target.dataset.index);
      revealHint(index);
    });
  });

  modal.classList.remove('hidden');
}

/**
 * Reveal a hint
 * @param {number} index
 */
function revealHint(index) {
  if (!currentLevel) return;

  // Update hints used
  GameState.hintsUsed[currentLevel.id] = index + 1;

  // Update display
  updateHintsDisplay();

  // Refresh modal
  showHintsModal();

  // Save progress
  saveProgress();

  showNotification('💡 Hint revealed!', 'info');
}

/**
 * Close a modal
 * @param {string} modalId
 */
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('hidden');
  }
}

/**
 * Show notification
 * @param {string} message
 * @param {string} type - 'success', 'error', 'warning', 'info'
 */
function showNotification(message, type = 'info') {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `notification ${type}`;
  notification.textContent = message;

  // Add to body
  document.body.appendChild(notification);

  // Animate in
  setTimeout(() => {
    notification.classList.add('show');
  }, 10);

  // Remove after 3 seconds
  setTimeout(() => {
    notification.classList.remove('show');
    setTimeout(() => {
      notification.remove();
    }, 300);
  }, 3000);
}

// ==========================================
// ACHIEVEMENTS
// ==========================================

/**
 * Check for unlocked achievements
 * @param {object} result
 * @returns {array} New achievements
 */
function checkAchievements(result) {
  const newAchievements = [];

  // Check if achievements.js is loaded
  if (typeof window.checkAchievements === 'function') {
    return window.checkAchievements(GameState, result, currentLevel);
  }

  // Fallback: Simple achievement checks
  const achievements = [
    {
      id: 'first_blood',
      name: 'First Blood',
      description: 'Complete your first level',
      icon: '🎯',
      condition: () => GameState.completedLevels.length === 1
    },
    {
      id: 'perfectionist',
      name: 'Perfectionist',
      description: 'Complete a level on first attempt',
      icon: '⭐',
      condition: () => GameState.currentLevelAttempts.length === 1
    },
    {
      id: 'innovator',
      name: 'Innovator',
      description: 'Use a novel technique',
      icon: '💡',
      condition: () => result.isNovel
    }
  ];

  achievements.forEach(achievement => {
    if (!GameState.achievements.includes(achievement.id) && achievement.condition()) {
      GameState.achievements.push(achievement.id);
      newAchievements.push(achievement);
    }
  });

  return newAchievements;
}

// ==========================================
// STORAGE
// ==========================================

/**
 * Save progress to localStorage
 */
function saveProgress() {
  try {
    const saveData = {
      currentLevel: GameState.currentLevel,
      totalPoints: GameState.totalPoints,
      completedLevels: GameState.completedLevels,
      attempts: GameState.attempts,
      playerRank: GameState.playerRank,
      hintsUsed: GameState.hintsUsed,
      achievements: GameState.achievements,
      settings: GameState.settings,
      lastSaved: Date.now()
    };

    localStorage.setItem('raxe_arena_progress', JSON.stringify(saveData));
    console.log('💾 Progress saved');
  } catch (error) {
    console.error('Failed to save progress:', error);
  }
}

/**
 * Load progress from localStorage
 */
function loadProgress() {
  try {
    const savedData = localStorage.getItem('raxe_arena_progress');

    if (savedData) {
      const data = JSON.parse(savedData);

      GameState.currentLevel = data.currentLevel || 1;
      GameState.totalPoints = data.totalPoints || 0;
      GameState.completedLevels = data.completedLevels || [];
      GameState.attempts = data.attempts || {};
      GameState.playerRank = data.playerRank || 'Rookie';
      GameState.hintsUsed = data.hintsUsed || {};
      GameState.achievements = data.achievements || [];
      GameState.settings = { ...GameState.settings, ...data.settings };

      console.log('📂 Progress loaded');
    }
  } catch (error) {
    console.error('Failed to load progress:', error);
  }
}

/**
 * Reset all progress
 */
function resetProgress() {
  const confirmation = confirm(
    '⚠️ Reset All Progress?\n\n' +
    'This will delete all your progress, points, and achievements.\n' +
    'This action cannot be undone!\n\n' +
    'Are you sure?'
  );

  if (!confirmation) return;

  // Double confirmation
  const doubleCheck = confirm('Are you REALLY sure? This is your last chance!');

  if (!doubleCheck) return;

  // Reset game state
  GameState.currentLevel = 1;
  GameState.totalPoints = 0;
  GameState.completedLevels = [];
  GameState.attempts = {};
  GameState.playerRank = 'Rookie';
  GameState.hintsUsed = {};
  GameState.achievements = [];
  GameState.currentLevelAttempts = [];

  // Clear localStorage
  localStorage.removeItem('raxe_arena_progress');

  // Reload first level
  loadLevel(1);
  updateProgress();
  updateHeaderStats();

  showNotification('🔄 Progress reset successfully', 'info');
}

/**
 * Start auto-save interval
 */
function startAutoSave() {
  // Auto-save every 30 seconds
  autoSaveInterval = setInterval(() => {
    saveProgress();
  }, 30000);
}

/**
 * Export user data
 */
function exportData() {
  const exportData = {
    version: '1.0',
    exportDate: new Date().toISOString(),
    gameState: GameState,
    statistics: {
      totalAttempts: Object.values(GameState.attempts).flat().length,
      completionRate: (GameState.completedLevels.length / LEVELS.length * 100).toFixed(1) + '%',
      averageAttemptsPerLevel: (Object.values(GameState.attempts).flat().length / Math.max(GameState.completedLevels.length, 1)).toFixed(1)
    }
  };

  // Create downloadable file
  const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `raxe-arena-export-${Date.now()}.json`;
  a.click();

  showNotification('📥 Data exported successfully', 'success');
}

// ==========================================
// DATA CONTRIBUTION
// ==========================================

/**
 * Contribute prompt data to RAXE dataset
 * @param {object} result
 */
function contributePromptData(result) {
  // This would send data to a backend API
  // For now, just log it
  console.log('📊 Contributing data to RAXE dataset:', {
    levelId: currentLevel.id,
    tier: currentLevel.tier,
    technique: result.techniqueUsed,
    success: result.success,
    threatScore: result.threatScore,
    timestamp: Date.now()
  });

  // In production, this would be:
  // fetch('/api/contribute', { method: 'POST', body: JSON.stringify(data) })
}

// ==========================================
// EVENT LISTENERS
// ==========================================

/**
 * Initialize all event listeners
 */
function initEventListeners() {
  // Submit button
  const submitBtn = document.getElementById('submit-btn');
  if (submitBtn) {
    submitBtn.addEventListener('click', submitAttempt);
  }

  // Enter key for submission
  const promptTextarea = document.getElementById('user-prompt');
  if (promptTextarea) {
    promptTextarea.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        submitAttempt();
      }
    });

    // Character count update
    promptTextarea.addEventListener('input', updateCharCount);
  }

  // Clear button
  const clearBtn = document.getElementById('clear-btn');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      promptTextarea.value = '';
      updateCharCount();
    });
  }

  // Hints button
  const hintsBtn = document.getElementById('hints-btn');
  if (hintsBtn) {
    hintsBtn.addEventListener('click', showHintsModal);
  }

  // Next level button (in success modal)
  const nextLevelBtn = document.getElementById('next-level-btn');
  if (nextLevelBtn) {
    nextLevelBtn.addEventListener('click', nextLevel);
  }

  // Review button (in success modal)
  const reviewBtn = document.getElementById('review-btn');
  if (reviewBtn) {
    reviewBtn.addEventListener('click', () => closeModal('success-modal'));
  }

  // Skip level button
  const skipLevelBtn = document.getElementById('skip-level-btn');
  if (skipLevelBtn) {
    skipLevelBtn.addEventListener('click', skipLevel);
  }

  // Reset progress button
  const resetProgressBtn = document.getElementById('reset-progress-btn');
  if (resetProgressBtn) {
    resetProgressBtn.addEventListener('click', resetProgress);
  }

  // Header buttons
  const achievementsBtn = document.getElementById('achievements-btn');
  if (achievementsBtn) {
    achievementsBtn.addEventListener('click', () => {
      // Will be implemented in achievements.js
      showNotification('🏆 Achievements feature coming soon!', 'info');
    });
  }

  const leaderboardBtn = document.getElementById('leaderboard-btn');
  if (leaderboardBtn) {
    leaderboardBtn.addEventListener('click', () => {
      // Will be implemented in leaderboard.js
      showNotification('📊 Leaderboard feature coming soon!', 'info');
    });
  }

  const settingsBtn = document.getElementById('settings-btn');
  if (settingsBtn) {
    settingsBtn.addEventListener('click', () => {
      document.getElementById('settings-modal').classList.remove('hidden');
    });
  }

  // Modal close buttons
  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', (e) => {
      const modalId = e.target.dataset.modal;
      closeModal(modalId);
    });
  });

  // Click outside modal to close
  document.querySelectorAll('.modal').forEach(modal => {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.classList.add('hidden');
      }
    });
  });

  // Settings toggles
  const darkModeToggle = document.getElementById('dark-mode-toggle');
  if (darkModeToggle) {
    darkModeToggle.checked = GameState.settings.darkMode;
    darkModeToggle.addEventListener('change', (e) => {
      GameState.settings.darkMode = e.target.checked;
      document.body.classList.toggle('light-mode', !e.target.checked);
      saveProgress();
    });
  }

  const animationsToggle = document.getElementById('animations-toggle');
  if (animationsToggle) {
    animationsToggle.checked = GameState.settings.animations;
    animationsToggle.addEventListener('change', (e) => {
      GameState.settings.animations = e.target.checked;
      saveProgress();
    });
  }

  const hintsAutoToggle = document.getElementById('hints-auto-toggle');
  if (hintsAutoToggle) {
    hintsAutoToggle.checked = GameState.settings.hintsAuto;
    hintsAutoToggle.addEventListener('change', (e) => {
      GameState.settings.hintsAuto = e.target.checked;
      saveProgress();
    });
  }

  const soundToggle = document.getElementById('sound-toggle');
  if (soundToggle) {
    soundToggle.checked = GameState.settings.sound;
    soundToggle.addEventListener('change', (e) => {
      GameState.settings.sound = e.target.checked;
      saveProgress();
    });
  }

  const contributeToggle = document.getElementById('contribute-prompts-toggle');
  if (contributeToggle) {
    contributeToggle.checked = GameState.settings.contributeData;
    contributeToggle.addEventListener('change', (e) => {
      GameState.settings.contributeData = e.target.checked;
      saveProgress();
    });
  }

  // Export data button
  const exportDataBtn = document.getElementById('export-data-btn');
  if (exportDataBtn) {
    exportDataBtn.addEventListener('click', exportData);
  }
}

// ==========================================
// UTILITY FUNCTIONS
// ==========================================

/**
 * Sleep/delay utility
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise}
 */
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Truncate text with ellipsis
 * @param {string} text
 * @param {number} maxLength
 * @returns {string}
 */
function truncateText(text, maxLength) {
  if (text.length <= maxLength) return text;
  return text.substring(0, maxLength) + '...';
}

/**
 * Play sound effect
 * @param {string} soundName
 */
function playSound(soundName) {
  // Placeholder for sound effects
  // In production, would play actual audio files
  console.log(`🔊 Playing sound: ${soundName}`);
}

/**
 * Show game complete modal
 */
function showGameCompleteModal() {
  alert(
    '🎉 CONGRATULATIONS! 🎉\n\n' +
    'You have completed all 72 levels of RAXE Arena!\n\n' +
    `Total Points: ${GameState.totalPoints.toLocaleString()}\n` +
    `Final Rank: ${GameState.playerRank}\n\n` +
    'You are now a master of prompt injection!\n\n' +
    'Share your achievement on social media and challenge your friends!'
  );
}

// ==========================================
// INITIALIZE ON PAGE LOAD
// ==========================================

// Wait for DOM to be ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initGame);
} else {
  initGame();
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  saveProgress();
  if (autoSaveInterval) {
    clearInterval(autoSaveInterval);
  }
});
