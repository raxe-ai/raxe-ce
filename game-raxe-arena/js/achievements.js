/**
 * RAXE Arena - Achievement & Badge System
 *
 * Comprehensive achievement tracking, progression, and rewards
 * Gamification features including badges, streaks, and mastery challenges
 */

// ==========================================
// ACHIEVEMENT DEFINITIONS
// ==========================================

const ACHIEVEMENTS = [
  // ==========================================
  // PROGRESSION TIER (Basic unlocking)
  // ==========================================
  {
    id: 'first_blood',
    name: 'First Blood',
    description: 'Complete your first level',
    icon: '🎯',
    category: 'progression',
    requirement: { type: 'levels_completed', count: 1 },
    points: 10,
    rarity: 'common',
    unlockedAt: null
  },
  {
    id: 'tier_one_master',
    name: 'Tier One Master',
    description: 'Complete all 15 levels in Tier 1',
    icon: '⭐',
    category: 'progression',
    requirement: { type: 'tier_completed', tier: 1 },
    points: 50,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'tier_two_master',
    name: 'Tier Two Master',
    description: 'Complete all 15 levels in Tier 2',
    icon: '⭐⭐',
    category: 'progression',
    requirement: { type: 'tier_completed', tier: 2 },
    points: 75,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'tier_three_master',
    name: 'Tier Three Master',
    description: 'Complete all 15 levels in Tier 3',
    icon: '⭐⭐⭐',
    category: 'progression',
    requirement: { type: 'tier_completed', tier: 3 },
    points: 100,
    rarity: 'rare',
    unlockedAt: null
  },
  {
    id: 'tier_four_master',
    name: 'Tier Four Master',
    description: 'Complete all 14 levels in Tier 4',
    icon: '⭐⭐⭐⭐',
    category: 'progression',
    requirement: { type: 'tier_completed', tier: 4 },
    points: 125,
    rarity: 'rare',
    unlockedAt: null
  },
  {
    id: 'tier_five_master',
    name: 'Tier Five Master',
    description: 'Complete all 13 legendary levels in Tier 5',
    icon: '⭐⭐⭐⭐⭐',
    category: 'progression',
    requirement: { type: 'tier_completed', tier: 5 },
    points: 200,
    rarity: 'epic',
    unlockedAt: null
  },
  {
    id: 'arena_champion',
    name: 'Arena Champion',
    description: 'Complete all 72 levels in RAXE Arena',
    icon: '🏆',
    category: 'progression',
    requirement: { type: 'levels_completed', count: 72 },
    points: 500,
    rarity: 'legendary',
    unlockedAt: null
  },

  // ==========================================
  // SKILL TIER (Speed & Efficiency)
  // ==========================================
  {
    id: 'speed_demon',
    name: 'Speed Demon',
    description: 'Complete a level in your first attempt',
    icon: '⚡',
    category: 'skill',
    requirement: { type: 'perfect_attempts', count: 1 },
    points: 25,
    rarity: 'common',
    unlockedAt: null
  },
  {
    id: 'first_try_warrior',
    name: 'First Try Warrior',
    description: 'Complete 10 levels on the first attempt',
    icon: '🎯',
    category: 'skill',
    requirement: { type: 'perfect_attempts', count: 10 },
    points: 75,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'technique_master',
    name: 'Technique Master',
    description: 'Successfully use all 13 attack types',
    icon: '🔬',
    category: 'skill',
    requirement: { type: 'attack_types_used', count: 13 },
    points: 100,
    rarity: 'rare',
    unlockedAt: null
  },
  {
    id: 'no_hints_needed',
    name: 'No Hints Needed',
    description: 'Complete 5 levels without using any hints',
    icon: '🧠',
    category: 'skill',
    requirement: { type: 'levels_without_hints', count: 5 },
    points: 50,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'perfectionist',
    name: 'Perfectionist',
    description: 'Complete an entire tier without using any hints',
    icon: '✨',
    category: 'skill',
    requirement: { type: 'tier_without_hints', tier: 1 },
    points: 150,
    rarity: 'epic',
    unlockedAt: null
  },

  // ==========================================
  // DISCOVERY TIER (Novel Techniques)
  // ==========================================
  {
    id: 'injection_specialist',
    name: 'Injection Specialist',
    description: 'Complete 10 Direct Injection attacks',
    icon: '💉',
    category: 'discovery',
    requirement: { type: 'attack_category_count', category: 'Direct Injection', count: 10 },
    points: 40,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'jailbreak_artist',
    name: 'Jailbreak Artist',
    description: 'Complete 10 Jailbreak attacks',
    icon: '🔓',
    category: 'discovery',
    requirement: { type: 'attack_category_count', category: 'Jailbreak', count: 10 },
    points: 40,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'encoding_expert',
    name: 'Encoding Expert',
    description: 'Complete 10 Encoding attacks',
    icon: '🔐',
    category: 'discovery',
    requirement: { type: 'attack_category_count', category: 'Encoding', count: 10 },
    points: 40,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'multi_turn_tactician',
    name: 'Multi-Turn Tactician',
    description: 'Complete 10 Multi-Turn attacks',
    icon: '🎲',
    category: 'discovery',
    requirement: { type: 'attack_category_count', category: 'Multi-Turn', count: 10 },
    points: 40,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'strategy_seeker',
    name: 'Strategy Seeker',
    description: 'Discover and master 5 different attack strategies',
    icon: '🗺️',
    category: 'discovery',
    requirement: { type: 'unique_strategies', count: 5 },
    points: 80,
    rarity: 'rare',
    unlockedAt: null
  },

  // ==========================================
  // DEDICATION TIER (Streaks & Milestones)
  // ==========================================
  {
    id: 'score_hunter_500',
    name: 'Score Hunter',
    description: 'Reach 500 points total',
    icon: '💰',
    category: 'dedication',
    requirement: { type: 'total_points', count: 500 },
    points: 25,
    rarity: 'common',
    unlockedAt: null
  },
  {
    id: 'score_collector_1000',
    name: 'Score Collector',
    description: 'Reach 1,000 points total',
    icon: '💵',
    category: 'dedication',
    requirement: { type: 'total_points', count: 1000 },
    points: 50,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'score_millionaire_5000',
    name: 'Score Millionaire',
    description: 'Reach 5,000 points total',
    icon: '💳',
    category: 'dedication',
    requirement: { type: 'total_points', count: 5000 },
    points: 100,
    rarity: 'rare',
    unlockedAt: null
  },
  {
    id: 'score_billionaire_10000',
    name: 'Score Billionaire',
    description: 'Reach 10,000 points total',
    icon: '💎',
    category: 'dedication',
    requirement: { type: 'total_points', count: 10000 },
    points: 200,
    rarity: 'epic',
    unlockedAt: null
  },
  {
    id: 'three_day_streak',
    name: 'Three-Day Grind',
    description: 'Maintain a 3-day play streak',
    icon: '🔥',
    category: 'dedication',
    requirement: { type: 'play_streak_days', count: 3 },
    points: 50,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'week_warrior',
    name: 'Week Warrior',
    description: 'Maintain a 7-day play streak',
    icon: '🔥🔥🔥',
    category: 'dedication',
    requirement: { type: 'play_streak_days', count: 7 },
    points: 100,
    rarity: 'rare',
    unlockedAt: null
  },
  {
    id: 'month_legend',
    name: 'Month Legend',
    description: 'Maintain a 30-day play streak',
    icon: '🔥🔥🔥🔥🔥',
    category: 'dedication',
    requirement: { type: 'play_streak_days', count: 30 },
    points: 250,
    rarity: 'legendary',
    unlockedAt: null
  },
  {
    id: 'rank_apprentice',
    name: 'Apprentice Ascension',
    description: 'Reach Apprentice rank (500+ points)',
    icon: '⚔️',
    category: 'dedication',
    requirement: { type: 'rank_reached', rank: 'Apprentice' },
    points: 40,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'rank_hacker',
    name: 'Hacker\'s Mastery',
    description: 'Reach Hacker rank (1,500+ points)',
    icon: '💻',
    category: 'dedication',
    requirement: { type: 'rank_reached', rank: 'Hacker' },
    points: 60,
    rarity: 'uncommon',
    unlockedAt: null
  },
  {
    id: 'rank_expert',
    name: 'Expert\'s Excellence',
    description: 'Reach Expert rank (3,500+ points)',
    icon: '🎯',
    category: 'dedication',
    requirement: { type: 'rank_reached', rank: 'Expert' },
    points: 80,
    rarity: 'rare',
    unlockedAt: null
  },
  {
    id: 'rank_elite',
    name: 'Elite Intelligence',
    description: 'Reach Elite rank (7,000+ points)',
    icon: '⚡',
    category: 'dedication',
    requirement: { type: 'rank_reached', rank: 'Elite' },
    points: 120,
    rarity: 'rare',
    unlockedAt: null
  },
  {
    id: 'rank_master',
    name: 'Master Controller',
    description: 'Reach Master rank (12,000+ points)',
    icon: '👑',
    category: 'dedication',
    requirement: { type: 'rank_reached', rank: 'Master' },
    points: 150,
    rarity: 'epic',
    unlockedAt: null
  },
  {
    id: 'rank_grandmaster',
    name: 'Grandmaster\'s Glory',
    description: 'Reach Grandmaster rank (18,000+ points)',
    icon: '🏆',
    category: 'dedication',
    requirement: { type: 'rank_reached', rank: 'Grandmaster' },
    points: 300,
    rarity: 'legendary',
    unlockedAt: null
  },

  // ==========================================
  // MASTERY TIER (Ultimate Challenges)
  // ==========================================
  {
    id: 'explorer_supreme',
    name: 'Explorer Supreme',
    description: 'Attempt all 72 levels at least once',
    icon: '🧭',
    category: 'mastery',
    requirement: { type: 'levels_attempted', count: 72 },
    points: 100,
    rarity: 'epic',
    unlockedAt: null
  },
  {
    id: 'no_mercy_mode',
    name: 'No Mercy Mode',
    description: 'Complete an entire tier on first attempt without hints',
    icon: '💀',
    category: 'mastery',
    requirement: { type: 'tier_perfect_run', tier: 3 },
    points: 300,
    rarity: 'legendary',
    unlockedAt: null
  },
  {
    id: 'flawless_victory',
    name: 'Flawless Victory',
    description: 'Complete 20 consecutive levels without hints',
    icon: '👑',
    category: 'mastery',
    requirement: { type: 'consecutive_no_hints', count: 20 },
    points: 250,
    rarity: 'legendary',
    unlockedAt: null
  }
];

// ==========================================
// RARITY TIERS
// ==========================================

const RARITY_TIERS = {
  common: {
    name: 'Common',
    color: '#808080',
    description: 'Basic progression achievements',
    points: 10
  },
  uncommon: {
    name: 'Uncommon',
    color: '#008000',
    description: 'Skill-based achievements',
    points: 50
  },
  rare: {
    name: 'Rare',
    color: '#0000FF',
    description: 'Dedication required',
    points: 100
  },
  epic: {
    name: 'Epic',
    color: '#800080',
    description: 'Master-level challenges',
    points: 200
  },
  legendary: {
    name: 'Legendary',
    color: '#FFD700',
    description: 'Ultimate achievements',
    points: 500
  }
};

// ==========================================
// ACHIEVEMENT MANAGER CLASS
// ==========================================

class AchievementManager {
  constructor() {
    // Initialize achievement state
    this.achievements = JSON.parse(JSON.stringify(ACHIEVEMENTS));
    this.unlockedAchievements = [];
    this.achievementProgress = {};
    this.totalAchievementPoints = 0;
    this.lastCheckTime = Date.now();

    // Load saved progress
    this.loadFromStorage();
  }

  /**
   * Load achievement data from localStorage
   */
  loadFromStorage() {
    const saved = localStorage.getItem('raxe_achievements');
    if (saved) {
      try {
        const data = JSON.parse(saved);
        this.unlockedAchievements = data.unlockedAchievements || [];
        this.achievementProgress = data.achievementProgress || {};
        this.totalAchievementPoints = data.totalAchievementPoints || 0;

        // Update unlocked achievement times
        this.unlockedAchievements.forEach(id => {
          const achievement = this.achievements.find(a => a.id === id);
          if (achievement) {
            achievement.unlockedAt = data.unlockedTimes?.[id] || Date.now();
          }
        });
      } catch (e) {
        console.warn('Failed to load achievement data:', e);
      }
    }
  }

  /**
   * Save achievement data to localStorage
   */
  saveToStorage() {
    const data = {
      unlockedAchievements: this.unlockedAchievements,
      achievementProgress: this.achievementProgress,
      totalAchievementPoints: this.totalAchievementPoints,
      unlockedTimes: {}
    };

    this.unlockedAchievements.forEach(id => {
      const achievement = this.achievements.find(a => a.id === id);
      if (achievement?.unlockedAt) {
        data.unlockedTimes[id] = achievement.unlockedAt;
      }
    });

    localStorage.setItem('raxe_achievements', JSON.stringify(data));
  }

  /**
   * Check for newly unlocked achievements based on game state
   * @param {Object} gameState - Current game state
   * @returns {Array} Array of newly unlocked achievements
   */
  checkAchievements(gameState) {
    const newlyUnlocked = [];

    for (const achievement of this.achievements) {
      // Skip if already unlocked
      if (this.unlockedAchievements.includes(achievement.id)) {
        continue;
      }

      // Check if requirement is met
      if (this.checkRequirement(achievement.requirement, gameState)) {
        this.unlockAchievement(achievement.id);
        newlyUnlocked.push(achievement);
      } else {
        // Update progress tracking
        this.updateProgress(achievement.id, gameState);
      }
    }

    // Save if any achievements were unlocked
    if (newlyUnlocked.length > 0) {
      this.saveToStorage();
    }

    return newlyUnlocked;
  }

  /**
   * Check if a requirement is met
   * @private
   */
  checkRequirement(requirement, gameState) {
    if (!requirement) return false;

    switch (requirement.type) {
      case 'levels_completed':
        return gameState.completedLevels?.length >= requirement.count;

      case 'tier_completed': {
        const tierLevels = this.getLevelsInTier(requirement.tier);
        const completed = gameState.completedLevels?.filter(id =>
          tierLevels.includes(id)
        ).length || 0;
        return completed === tierLevels.length;
      }

      case 'perfect_attempts':
        return (this.achievementProgress[`perfect_${requirement.type}`] || 0) >= requirement.count;

      case 'attack_types_used':
        return (this.achievementProgress['attack_types_used'] || new Set()).size >= requirement.count;

      case 'levels_without_hints': {
        const count = gameState.completedLevels?.filter(id =>
          !(gameState.hintsUsed?.[id])
        ).length || 0;
        return count >= requirement.count;
      }

      case 'tier_without_hints': {
        const tierLevels = this.getLevelsInTier(requirement.tier);
        const completed = gameState.completedLevels?.filter(id =>
          tierLevels.includes(id) && !(gameState.hintsUsed?.[id])
        ).length || 0;
        return completed === tierLevels.length;
      }

      case 'attack_category_count': {
        const categoryLevels = this.getLevelsByCategory(requirement.category);
        const completed = gameState.completedLevels?.filter(id =>
          categoryLevels.includes(id)
        ).length || 0;
        return completed >= requirement.count;
      }

      case 'total_points':
        return (gameState.totalPoints || 0) >= requirement.count;

      case 'play_streak_days':
        return this.getPlayStreak() >= requirement.count;

      case 'rank_reached':
        return this.getRankIndex(gameState.playerRank || 'Rookie') >=
               this.getRankIndex(requirement.rank);

      case 'levels_attempted':
        return (Object.keys(gameState.attempts || {}).length) >= requirement.count;

      case 'tier_perfect_run': {
        const tierLevels = this.getLevelsInTier(requirement.tier);
        return tierLevels.every(id => {
          const attempts = gameState.attempts?.[id] || [];
          return attempts.length === 1 && !gameState.hintsUsed?.[id];
        });
      }

      case 'consecutive_no_hints': {
        const completed = gameState.completedLevels || [];
        let streak = 0;
        for (let i = completed.length - 1; i >= 0; i--) {
          if (gameState.hintsUsed?.[completed[i]]) {
            break;
          }
          streak++;
          if (streak >= requirement.count) return true;
        }
        return false;
      }

      case 'unique_strategies':
        return (this.achievementProgress['unique_strategies'] || new Set()).size >= requirement.count;

      default:
        return false;
    }
  }

  /**
   * Update progress toward an achievement
   * @private
   */
  updateProgress(achievementId, gameState) {
    const achievement = this.achievements.find(a => a.id === achievementId);
    if (!achievement) return;

    const req = achievement.requirement;
    const key = `progress_${achievementId}`;

    switch (req.type) {
      case 'levels_completed':
        this.achievementProgress[key] = gameState.completedLevels?.length || 0;
        break;

      case 'total_points':
        this.achievementProgress[key] = gameState.totalPoints || 0;
        break;

      case 'perfect_attempts':
        const perfectCount = (gameState.completedLevels || []).filter(id =>
          (gameState.attempts?.[id]?.length || 0) === 1
        ).length;
        this.achievementProgress[key] = perfectCount;
        break;

      case 'levels_without_hints':
        const noHintsCount = (gameState.completedLevels || []).filter(id =>
          !gameState.hintsUsed?.[id]
        ).length;
        this.achievementProgress[key] = noHintsCount;
        break;

      case 'levels_attempted':
        this.achievementProgress[key] = Object.keys(gameState.attempts || {}).length;
        break;
    }
  }

  /**
   * Manually unlock an achievement
   * @param {string} id - Achievement ID
   * @returns {boolean} Success status
   */
  unlockAchievement(id) {
    if (this.unlockedAchievements.includes(id)) {
      return false; // Already unlocked
    }

    const achievement = this.achievements.find(a => a.id === id);
    if (!achievement) {
      return false;
    }

    this.unlockedAchievements.push(id);
    achievement.unlockedAt = Date.now();
    this.totalAchievementPoints += achievement.points;
    this.saveToStorage();

    return true;
  }

  /**
   * Get all unlocked achievements
   * @returns {Array} Array of unlocked achievement objects
   */
  getUnlocked() {
    return this.unlockedAchievements.map(id =>
      this.achievements.find(a => a.id === id)
    ).filter(Boolean);
  }

  /**
   * Get progress toward a specific achievement
   * @param {string} id - Achievement ID
   * @returns {Object} Progress object with current and required values
   */
  getProgress(id) {
    const achievement = this.achievements.find(a => a.id === id);
    if (!achievement) return null;

    if (this.unlockedAchievements.includes(id)) {
      return {
        id,
        unlocked: true,
        progress: 100,
        current: achievement.requirement.count,
        required: achievement.requirement.count
      };
    }

    const key = `progress_${id}`;
    const current = this.achievementProgress[key] || 0;
    const required = achievement.requirement.count || 1;
    const progress = Math.min(100, Math.floor((current / required) * 100));

    return {
      id,
      unlocked: false,
      progress,
      current,
      required
    };
  }

  /**
   * Get all achievement definitions
   * @returns {Array} Array of all achievements
   */
  getAllAchievements() {
    return this.achievements;
  }

  /**
   * Get achievements by category
   * @param {string} category - Category name
   * @returns {Array} Filtered achievements
   */
  getAchievementsByCategory(category) {
    return this.achievements.filter(a => a.category === category);
  }

  /**
   * Get achievement statistics
   * @returns {Object} Statistics object
   */
  getStatistics() {
    const total = this.achievements.length;
    const unlocked = this.unlockedAchievements.length;
    const byRarity = {};

    Object.keys(RARITY_TIERS).forEach(rarity => {
      const count = this.achievements.filter(a => a.rarity === rarity).length;
      const unlockedCount = this.achievements.filter(a =>
        a.rarity === rarity && this.unlockedAchievements.includes(a.id)
      ).length;

      byRarity[rarity] = {
        total: count,
        unlocked: unlockedCount,
        percentage: count > 0 ? Math.floor((unlockedCount / count) * 100) : 0
      };
    });

    return {
      total,
      unlocked,
      percentage: Math.floor((unlocked / total) * 100),
      points: this.totalAchievementPoints,
      byRarity
    };
  }

  /**
   * Helper: Get level IDs for a specific tier
   * @private
   */
  getLevelsInTier(tier) {
    // Tier 1: 1-15, Tier 2: 16-30, Tier 3: 31-45, Tier 4: 46-59, Tier 5: 60-72
    const starts = [0, 1, 16, 31, 46, 60];
    const ends = [0, 15, 30, 45, 59, 72];

    const levels = [];
    for (let i = starts[tier]; i <= ends[tier]; i++) {
      levels.push(i);
    }
    return levels;
  }

  /**
   * Helper: Get level IDs by attack category
   * @private
   */
  getLevelsByCategory(category) {
    // This would normally query from LEVELS array
    // For now, returning empty array - should be populated from game data
    return [];
  }

  /**
   * Helper: Calculate current play streak
   * @private
   */
  getPlayStreak() {
    const streakData = localStorage.getItem('raxe_play_streak');
    if (!streakData) return 0;

    try {
      const data = JSON.parse(streakData);
      const today = new Date();
      const lastDate = new Date(data.lastDate);

      const dayDiff = Math.floor((today - lastDate) / (1000 * 60 * 60 * 24));

      if (dayDiff === 0) {
        return data.streak;
      } else if (dayDiff === 1) {
        return data.streak + 1;
      }
      return 0; // Streak broken
    } catch (e) {
      return 0;
    }
  }

  /**
   * Helper: Get rank index for comparison
   * @private
   */
  getRankIndex(rankName) {
    const ranks = ['Rookie', 'Apprentice', 'Hacker', 'Expert', 'Elite', 'Master', 'Grandmaster'];
    return ranks.indexOf(rankName);
  }

  /**
   * Update play streak on game activity
   */
  updatePlayStreak() {
    const today = new Date().toISOString().split('T')[0];
    const streakData = localStorage.getItem('raxe_play_streak');

    let data = { streak: 1, lastDate: today };

    if (streakData) {
      try {
        const current = JSON.parse(streakData);
        const lastDate = new Date(current.lastDate);
        const currentDate = new Date(today);

        const dayDiff = Math.floor((currentDate - lastDate) / (1000 * 60 * 60 * 24));

        if (dayDiff === 0) {
          data = current;
        } else if (dayDiff === 1) {
          data = { streak: current.streak + 1, lastDate: today };
        }
      } catch (e) {
        console.warn('Error updating play streak:', e);
      }
    }

    localStorage.setItem('raxe_play_streak', JSON.stringify(data));
  }
}

// ==========================================
// SINGLETON EXPORT
// ==========================================

// Create and export singleton instance
const AchievementManager_Instance = new AchievementManager();

// Make available globally if needed
if (typeof window !== 'undefined') {
  window.AchievementManager = AchievementManager_Instance;
}

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = AchievementManager_Instance;
}
