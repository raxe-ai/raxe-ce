/**
 * Anonymous Leaderboard System with GitHub Claim Feature
 * MVP: localStorage-based with optional GitHub Gist sync
 */

class Leaderboard {
  constructor() {
    this.STORAGE_KEY = 'raxe_leaderboard_entries';
    this.WEEKLY_STORAGE_KEY = 'raxe_weekly_leaderboard';
    this.STATS_KEY = 'raxe_leaderboard_stats';
    this.GITHUB_GIST_ID = null; // Set via setGistId()
    this.GITHUB_API_TOKEN = null; // Set via GitHub OAuth
    this.MAX_ENTRIES = 10000; // Prevent localStorage bloat
    this.RATE_LIMIT_MS = 60000; // 1 minute between submissions
    this.RANK_TIERS = {
      'Novice': { min: 0, max: 999, medal: '⭐' },
      'Apprentice': { min: 1000, max: 4999, medal: '🥈' },
      'Journeyman': { min: 5000, max: 14999, medal: '🥇' },
      'Master': { min: 15000, max: 49999, medal: '👑' },
      'Legend': { min: 50000, max: Infinity, medal: '🔥' }
    };
  }

  /**
   * Generate UUID v4
   */
  generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  /**
   * Validate score entry for anti-cheat
   */
  validateScore(nickname, points, level) {
    const errors = [];

    // Nickname validation
    if (!nickname || typeof nickname !== 'string') {
      errors.push('Invalid nickname');
    }
    if (nickname.length < 2 || nickname.length > 30) {
      errors.push('Nickname must be 2-30 characters');
    }
    if (!/^[a-zA-Z0-9_\-\s]+$/.test(nickname)) {
      errors.push('Nickname contains invalid characters');
    }

    // Points validation - sanity checks
    if (!Number.isInteger(points) || points < 0) {
      errors.push('Points must be non-negative integer');
    }
    if (points > 10000000) {
      errors.push('Points exceed maximum threshold');
    }

    // Level validation
    if (!Number.isInteger(level) || level < 1 || level > 100) {
      errors.push('Level must be between 1-100');
    }

    // Points/Level ratio check (anti-cheat)
    const expectedMaxPoints = level * 500; // Rough expected points per level
    if (points > expectedMaxPoints * 2) {
      errors.push('Points too high for level (possible cheat)');
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  /**
   * Check rate limiting for player
   */
  checkRateLimit(playerId) {
    const stats = this.getStats();
    const lastSubmit = stats.lastSubmissions?.[playerId];
    if (!lastSubmit) return true;

    const timeSinceLastSubmit = Date.now() - lastSubmit;
    return timeSinceLastSubmit >= this.RATE_LIMIT_MS;
  }

  /**
   * Update rate limit stats
   */
  updateRateLimit(playerId) {
    const stats = this.getStats();
    if (!stats.lastSubmissions) stats.lastSubmissions = {};
    stats.lastSubmissions[playerId] = Date.now();
    localStorage.setItem(this.STATS_KEY, JSON.stringify(stats));
  }

  /**
   * Get leaderboard stats
   */
  getStats() {
    const stored = localStorage.getItem(this.STATS_KEY);
    return stored ? JSON.parse(stored) : {
      totalSubmissions: 0,
      weeklyReset: new Date().toISOString().split('T')[0],
      lastSubmissions: {}
    };
  }

  /**
   * Submit anonymous score
   * @param {string} nickname - Player nickname
   * @param {number} points - Score points
   * @param {number} level - Player level
   * @param {object} additionalData - achievements, completion_time, etc.
   * @returns {object} { success, entry, message, errors }
   */
  submitScore(nickname, points, level, additionalData = {}) {
    // Validation
    const validation = this.validateScore(nickname, points, level);
    if (!validation.valid) {
      return {
        success: false,
        message: 'Score validation failed',
        errors: validation.errors
      };
    }

    // Generate player ID based on nickname + timestamp (pseudo-anonymous)
    const playerId = `${nickname}_${Math.floor(Date.now() / 1000)}`;

    // Rate limiting
    if (!this.checkRateLimit(playerId)) {
      return {
        success: false,
        message: 'Rate limited. Please wait before submitting again.',
        errors: ['Rate limit exceeded']
      };
    }

    // Create entry
    const entry = {
      id: this.generateUUID(),
      nickname: nickname.trim(),
      points: points,
      level: level,
      rank: this.calculateRank(points),
      timestamp: new Date().toISOString(),
      github_username: null,
      achievements: additionalData.achievements || 0,
      completion_time: additionalData.completion_time || 0,
      verified: false
    };

    // Deduplicate - keep best score for same nickname
    const entries = this.getGlobalEntries();
    const existingIndex = entries.findIndex(e =>
      e.nickname === nickname && !e.github_username
    );

    if (existingIndex !== -1) {
      const existing = entries[existingIndex];
      if (points <= existing.points) {
        return {
          success: false,
          message: 'You already have a better score.',
          entry: existing,
          errors: []
        };
      }
      // Replace with better score
      entries[existingIndex] = entry;
    } else {
      // Add new entry
      entries.push(entry);
    }

    // Sort and trim to MAX_ENTRIES
    entries.sort((a, b) => {
      if (b.points !== a.points) return b.points - a.points;
      return new Date(a.timestamp) - new Date(b.timestamp);
    });

    if (entries.length > this.MAX_ENTRIES) {
      entries.length = this.MAX_ENTRIES;
    }

    // Save
    localStorage.setItem(this.STORAGE_KEY, JSON.stringify(entries));
    this.updateRateLimit(playerId);

    // Update stats
    const stats = this.getStats();
    stats.totalSubmissions++;
    localStorage.setItem(this.STATS_KEY, JSON.stringify(stats));

    return {
      success: true,
      entry: entry,
      message: 'Score submitted successfully!',
      errors: []
    };
  }

  /**
   * Calculate rank tier based on points
   */
  calculateRank(points) {
    for (const [rankName, { min, max }] of Object.entries(this.RANK_TIERS)) {
      if (points >= min && points <= max) {
        return rankName;
      }
    }
    return 'Novice';
  }

  /**
   * Get all global entries (sorted)
   */
  getGlobalEntries() {
    const stored = localStorage.getItem(this.STORAGE_KEY);
    const entries = stored ? JSON.parse(stored) : [];

    // Re-sort just in case
    entries.sort((a, b) => {
      if (b.points !== a.points) return b.points - a.points;
      return new Date(a.timestamp) - new Date(b.timestamp);
    });

    return entries;
  }

  /**
   * Get global leaderboard (top N)
   * @param {number} limit - Number of entries to return
   * @returns {array} Top leaderboard entries
   */
  getGlobalLeaderboard(limit = 100) {
    const entries = this.getGlobalEntries();
    return entries.slice(0, limit).map((entry, index) => ({
      ...entry,
      position: index + 1
    }));
  }

  /**
   * Get weekly leaderboard (top N)
   * @param {number} limit - Number of entries to return
   * @returns {array} Top weekly entries
   */
  getWeeklyLeaderboard(limit = 100) {
    const entries = this.getGlobalEntries();
    const oneWeekAgo = new Date();
    oneWeekAgo.setDate(oneWeekAgo.getDate() - 7);

    const weeklyEntries = entries.filter(entry =>
      new Date(entry.timestamp) >= oneWeekAgo
    );

    return weeklyEntries.slice(0, limit).map((entry, index) => ({
      ...entry,
      position: index + 1
    }));
  }

  /**
   * Get player's rank in leaderboard
   * @param {string} nickname - Player nickname
   * @returns {object} { position, entry, rank }
   */
  getPlayerRank(nickname) {
    const entries = this.getGlobalEntries();
    const entry = entries.find(e => e.nickname === nickname);

    if (!entry) {
      return {
        position: null,
        entry: null,
        message: 'Player not found'
      };
    }

    const position = entries.findIndex(e => e.id === entry.id) + 1;
    return {
      position,
      entry: { ...entry, position },
      message: `Rank #${position}`
    };
  }

  /**
   * Get estimated position before submitting
   * @param {number} points - Score points
   * @returns {number} Estimated position
   */
  calculatePosition(points) {
    const entries = this.getGlobalEntries();
    let position = 1;
    for (const entry of entries) {
      if (entry.points > points) {
        position++;
      }
    }
    return position;
  }

  /**
   * Archive current week and reset weekly leaderboard
   */
  archiveWeek() {
    const stats = this.getStats();
    const today = new Date().toISOString().split('T')[0];

    if (stats.weeklyReset === today) {
      return { message: 'Already reset today' };
    }

    const weeklyArchive = localStorage.getItem('raxe_weekly_archive_' + stats.weeklyReset);
    if (!weeklyArchive) {
      const currentWeekly = this.getWeeklyLeaderboard(1000);
      localStorage.setItem(
        'raxe_weekly_archive_' + stats.weeklyReset,
        JSON.stringify(currentWeekly)
      );
    }

    stats.weeklyReset = today;
    localStorage.setItem(this.STATS_KEY, JSON.stringify(stats));

    return { message: 'Weekly leaderboard archived' };
  }

  /**
   * Get archived weekly leaderboard
   * @param {string} date - Date in YYYY-MM-DD format
   * @returns {array} Archived entries
   */
  getArchivedWeek(date) {
    const archived = localStorage.getItem('raxe_weekly_archive_' + date);
    return archived ? JSON.parse(archived) : [];
  }

  /**
   * Search player by nickname (partial match)
   * @param {string} query - Search query
   * @param {number} limit - Max results
   * @returns {array} Matching entries
   */
  searchPlayer(query, limit = 10) {
    const entries = this.getGlobalEntries();
    const q = query.toLowerCase();
    return entries
      .filter(e => e.nickname.toLowerCase().includes(q))
      .slice(0, limit);
  }

  /**
   * Get statistics summary
   * @returns {object} Stats object
   */
  getLeaderboardStats() {
    const entries = this.getGlobalEntries();
    const stats = this.getStats();

    if (entries.length === 0) {
      return {
        totalPlayers: 0,
        totalSubmissions: 0,
        topScore: 0,
        averageScore: 0,
        medianScore: 0
      };
    }

    const points = entries.map(e => e.points);
    const sorted = [...points].sort((a, b) => a - b);
    const median = sorted[Math.floor(sorted.length / 2)];

    return {
      totalPlayers: entries.length,
      totalSubmissions: stats.totalSubmissions || 0,
      topScore: entries[0].points,
      averageScore: Math.round(points.reduce((a, b) => a + b) / points.length),
      medianScore: median,
      topPlayer: entries[0].nickname,
      lastUpdate: entries[0].timestamp
    };
  }

  /**
   * Format rank with emoji
   * @param {number} position - Leaderboard position
   * @returns {string} Formatted rank string
   */
  formatRank(position) {
    const medals = {
      1: '🥇',
      2: '🥈',
      3: '🥉'
    };

    if (position <= 3) {
      return `${medals[position]} #${position}`;
    }
    return `#${position}`;
  }

  /**
   * Format time duration
   * @param {number} seconds - Duration in seconds
   * @returns {string} Formatted time
   */
  formatTime(seconds) {
    if (seconds === 0) return '--:--:--';
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }

  /**
   * Render leaderboard to HTML
   * @param {array} entries - Leaderboard entries
   * @param {string|HTMLElement} container - DOM element or selector
   * @param {object} options - Render options
   */
  renderLeaderboard(entries, container, options = {}) {
    const {
      showAchievements = true,
      showTime = true,
      showGithub = true,
      maxRows = 100
    } = options;

    const el = typeof container === 'string'
      ? document.querySelector(container)
      : container;

    if (!el) {
      console.error('Container not found');
      return;
    }

    const html = `
      <div class="leaderboard-container">
        <table class="leaderboard-table">
          <thead>
            <tr>
              <th class="rank-col">Rank</th>
              <th class="nick-col">Player</th>
              <th class="points-col">Points</th>
              <th class="level-col">Level</th>
              <th class="tier-col">Tier</th>
              ${showAchievements ? '<th class="achievement-col">🏆</th>' : ''}
              ${showTime ? '<th class="time-col">Time</th>' : ''}
              ${showGithub ? '<th class="github-col">GitHub</th>' : ''}
            </tr>
          </thead>
          <tbody>
            ${entries.slice(0, maxRows).map(entry => `
              <tr class="leaderboard-row" data-id="${entry.id}">
                <td class="rank-cell">${this.formatRank(entry.position)}</td>
                <td class="nick-cell">
                  <span class="nickname">${this.escapeHtml(entry.nickname)}</span>
                </td>
                <td class="points-cell"><strong>${entry.points.toLocaleString()}</strong></td>
                <td class="level-cell">Lv. ${entry.level}</td>
                <td class="tier-cell">
                  <span class="tier-badge" data-tier="${entry.rank}">
                    ${this.RANK_TIERS[entry.rank]?.medal || '⭐'} ${entry.rank}
                  </span>
                </td>
                ${showAchievements ? `<td class="achievement-cell">${entry.achievements || 0}</td>` : ''}
                ${showTime ? `<td class="time-cell">${this.formatTime(entry.completion_time)}</td>` : ''}
                ${showGithub ? `<td class="github-cell">
                  ${entry.github_username
                    ? `<a href="https://github.com/${entry.github_username}" target="_blank" class="github-link">@${entry.github_username}</a>`
                    : '<span class="unclaimed">Unclaimed</span>'
                  }
                </td>` : ''}
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;

    el.innerHTML = html;
    return el;
  }

  /**
   * Escape HTML special characters
   */
  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Render player card
   */
  renderPlayerCard(entry, container) {
    const el = typeof container === 'string'
      ? document.querySelector(container)
      : container;

    if (!el) return;

    const stats = this.getStats();
    const rank = this.getPlayerRank(entry.nickname);

    const html = `
      <div class="player-card">
        <div class="card-header">
          <h2>${this.escapeHtml(entry.nickname)}</h2>
          <span class="card-rank">${this.formatRank(rank.position || 0)}</span>
        </div>
        <div class="card-body">
          <div class="stat-row">
            <span class="stat-label">Points:</span>
            <span class="stat-value">${entry.points.toLocaleString()}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Level:</span>
            <span class="stat-value">Lv. ${entry.level}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Tier:</span>
            <span class="stat-value tier-badge" data-tier="${entry.rank}">
              ${this.RANK_TIERS[entry.rank]?.medal || '⭐'} ${entry.rank}
            </span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Achievements:</span>
            <span class="stat-value">🏆 ${entry.achievements || 0}</span>
          </div>
          <div class="stat-row">
            <span class="stat-label">Time:</span>
            <span class="stat-value">${this.formatTime(entry.completion_time)}</span>
          </div>
          ${entry.github_username ? `
            <div class="stat-row">
              <span class="stat-label">GitHub:</span>
              <span class="stat-value">
                <a href="https://github.com/${entry.github_username}" target="_blank">@${entry.github_username}</a>
              </span>
            </div>
          ` : ''}
          <div class="stat-row">
            <span class="stat-label">Submitted:</span>
            <span class="stat-value">${new Date(entry.timestamp).toLocaleString()}</span>
          </div>
        </div>
        ${!entry.github_username ? `
          <div class="card-footer">
            <button class="btn-claim-github" data-id="${entry.id}">
              Claim with GitHub
            </button>
          </div>
        ` : ''}
      </div>
    `;

    el.innerHTML = html;
    return el;
  }

  /**
   * Set GitHub Gist ID for syncing
   */
  setGistId(gistId) {
    this.GITHUB_GIST_ID = gistId;
    localStorage.setItem('raxe_gist_id', gistId);
  }

  /**
   * Set GitHub API token
   */
  setGitHubToken(token) {
    this.GITHUB_API_TOKEN = token;
    // Store securely (or use sessionStorage for demo)
    sessionStorage.setItem('raxe_github_token', token);
  }

  /**
   * Get GitHub API token from storage
   */
  getGitHubToken() {
    return this.GITHUB_API_TOKEN || sessionStorage.getItem('raxe_github_token');
  }

  /**
   * Fetch leaderboard from GitHub Gist (async)
   * @returns {Promise} Gist data
   */
  async fetchFromGist() {
    if (!this.GITHUB_GIST_ID) {
      console.warn('GitHub Gist ID not set');
      return null;
    }

    try {
      const response = await fetch(`https://api.github.com/gists/${this.GITHUB_GIST_ID}`);
      if (!response.ok) throw new Error('Failed to fetch gist');

      const gist = await response.json();
      const file = gist.files['raxe-leaderboard.json'];
      if (!file) throw new Error('Leaderboard file not found in gist');

      return JSON.parse(file.content);
    } catch (error) {
      console.error('Gist fetch error:', error);
      return null;
    }
  }

  /**
   * Sync leaderboard to GitHub Gist (async)
   * @returns {Promise} Sync result
   */
  async syncToGist() {
    if (!this.GITHUB_GIST_ID || !this.GITHUB_API_TOKEN) {
      return {
        success: false,
        message: 'GitHub Gist ID or token not configured'
      };
    }

    try {
      const entries = this.getGlobalEntries();
      const content = JSON.stringify({
        version: '1.0',
        synced: new Date().toISOString(),
        entries: entries.slice(0, 500) // Top 500 to keep gist size reasonable
      }, null, 2);

      const response = await fetch(`https://api.github.com/gists/${this.GITHUB_GIST_ID}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `token ${this.GITHUB_API_TOKEN}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          files: {
            'raxe-leaderboard.json': {
              content: content
            }
          }
        })
      });

      if (!response.ok) {
        throw new Error(`GitHub API error: ${response.statusText}`);
      }

      return {
        success: true,
        message: 'Leaderboard synced to GitHub Gist',
        gistUrl: `https://gist.github.com/${this.GITHUB_GIST_ID}`
      };
    } catch (error) {
      console.error('Gist sync error:', error);
      return {
        success: false,
        message: 'Failed to sync to GitHub Gist',
        error: error.message
      };
    }
  }

  /**
   * Merge local and remote leaderboards
   * @param {array} remoteEntries - Entries from GitHub Gist
   * @returns {array} Merged entries
   */
  mergeLeaderboards(remoteEntries) {
    const local = this.getGlobalEntries();
    const merged = new Map();

    // Add all local entries
    for (const entry of local) {
      const key = entry.github_username || entry.nickname;
      merged.set(key, entry);
    }

    // Merge with remote, keeping better scores
    for (const entry of remoteEntries) {
      const key = entry.github_username || entry.nickname;
      const existing = merged.get(key);

      if (!existing || entry.points > existing.points) {
        merged.set(key, entry);
      }
    }

    const result = Array.from(merged.values());
    result.sort((a, b) => {
      if (b.points !== a.points) return b.points - a.points;
      return new Date(a.timestamp) - new Date(b.timestamp);
    });

    return result;
  }

  /**
   * OAuth flow initiation for GitHub claim
   * @returns {object} OAuth config
   */
  getGitHubOAuthConfig() {
    return {
      clientId: process.env.GITHUB_CLIENT_ID || 'YOUR_GITHUB_CLIENT_ID',
      redirectUri: `${window.location.origin}/oauth/callback`,
      scopes: ['user:email', 'gist']
    };
  }

  /**
   * Handle OAuth callback and claim entry
   * @param {string} code - OAuth code from GitHub
   * @param {string} entryId - Leaderboard entry ID to claim
   * @returns {Promise} Claim result
   */
  async claimWithGitHub(code, entryId) {
    try {
      // Exchange code for token (requires backend endpoint)
      const tokenResponse = await fetch('/api/github/token', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code })
      });

      if (!tokenResponse.ok) {
        throw new Error('Failed to get GitHub token');
      }

      const { access_token } = await tokenResponse.json();
      this.setGitHubToken(access_token);

      // Get GitHub user info
      const userResponse = await fetch('https://api.github.com/user', {
        headers: { 'Authorization': `token ${access_token}` }
      });

      if (!userResponse.ok) {
        throw new Error('Failed to get GitHub user info');
      }

      const user = await userResponse.json();

      // Update entry with GitHub username
      const entries = this.getGlobalEntries();
      const entry = entries.find(e => e.id === entryId);

      if (!entry) {
        throw new Error('Entry not found');
      }

      entry.github_username = user.login;
      entry.verified = true;

      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(entries));

      return {
        success: true,
        message: `Entry claimed as @${user.login}`,
        entry: entry
      };
    } catch (error) {
      console.error('GitHub claim error:', error);
      return {
        success: false,
        message: 'Failed to claim with GitHub',
        error: error.message
      };
    }
  }

  /**
   * Export leaderboard as JSON
   */
  exportJSON() {
    const entries = this.getGlobalEntries();
    const stats = this.getLeaderboardStats();
    return JSON.stringify({
      exportDate: new Date().toISOString(),
      stats,
      entries
    }, null, 2);
  }

  /**
   * Export leaderboard as CSV
   */
  exportCSV() {
    const entries = this.getGlobalEntries();
    const headers = ['Rank', 'Nickname', 'Points', 'Level', 'Tier', 'GitHub', 'Achievements', 'Time', 'Timestamp'];
    const rows = entries.map((entry, idx) => [
      idx + 1,
      entry.nickname,
      entry.points,
      entry.level,
      entry.rank,
      entry.github_username || 'Unclaimed',
      entry.achievements || 0,
      this.formatTime(entry.completion_time),
      entry.timestamp
    ]);

    const csv = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    ].join('\n');

    return csv;
  }

  /**
   * Clear all local leaderboard data (admin only)
   */
  clearAll() {
    if (confirm('Are you sure? This will permanently delete all leaderboard data.')) {
      localStorage.removeItem(this.STORAGE_KEY);
      localStorage.removeItem(this.STATS_KEY);
      return { message: 'Leaderboard cleared' };
    }
    return { message: 'Clear cancelled' };
  }

  /**
   * Get leaderboard summary
   */
  getSummary() {
    const global = this.getGlobalLeaderboard(10);
    const weekly = this.getWeeklyLeaderboard(10);
    const stats = this.getLeaderboardStats();

    return {
      stats,
      globalTop10: global,
      weeklyTop10: weekly
    };
  }
}

/**
 * Singleton instance
 */
const LeaderboardManager = new Leaderboard();

// Export for use in modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = LeaderboardManager;
}
