/**
 * Leaderboard System - Usage Examples and Integration Guide
 */

// Initialize the leaderboard (singleton already created in leaderboard.js)
// LeaderboardManager is globally available

// ============================================================================
// 1. BASIC SCORE SUBMISSION
// ============================================================================

function exampleSubmitScore() {
  const result = LeaderboardManager.submitScore(
    'ShadowNinja',  // nickname
    25000,          // points
    42,             // level
    {
      achievements: 15,
      completion_time: 3600  // seconds
    }
  );

  if (result.success) {
    console.log('Score submitted!', result.entry);
    // Show success message to player
    showNotification(`Congratulations! Your score: ${result.entry.points}`);
  } else {
    console.error('Submission failed:', result.errors);
    showNotification(result.message, 'error');
  }
}

// ============================================================================
// 2. VIEW GLOBAL LEADERBOARD
// ============================================================================

function exampleViewGlobalLeaderboard() {
  // Get top 100 scores
  const topScores = LeaderboardManager.getGlobalLeaderboard(100);

  // Render to HTML container
  LeaderboardManager.renderLeaderboard(topScores, '#leaderboard-container', {
    showAchievements: true,
    showTime: true,
    showGithub: true,
    maxRows: 50
  });

  console.log('Top player:', topScores[0]);
}

// ============================================================================
// 3. VIEW WEEKLY LEADERBOARD
// ============================================================================

function exampleViewWeeklyLeaderboard() {
  const weeklyScores = LeaderboardManager.getWeeklyLeaderboard(50);

  LeaderboardManager.renderLeaderboard(weeklyScores, '#weekly-container', {
    showAchievements: true,
    showTime: true,
    showGithub: false
  });
}

// ============================================================================
// 4. CHECK PLAYER RANK
// ============================================================================

function exampleCheckPlayerRank(nickname) {
  const rankInfo = LeaderboardManager.getPlayerRank(nickname);

  if (rankInfo.entry) {
    console.log(`${nickname} is ranked #${rankInfo.position}`);
    LeaderboardManager.renderPlayerCard(rankInfo.entry, '#player-card');
  } else {
    console.log(rankInfo.message);
  }
}

// ============================================================================
// 5. ESTIMATE POSITION BEFORE SUBMIT
// ============================================================================

function exampleEstimatePosition(points) {
  const estimatedPosition = LeaderboardManager.calculatePosition(points);
  console.log(`Your score would place you at position #${estimatedPosition}`);
  return estimatedPosition;
}

// ============================================================================
// 6. SEARCH FOR PLAYER
// ============================================================================

function exampleSearchPlayer(query) {
  const results = LeaderboardManager.searchPlayer(query, 20);
  console.log(`Found ${results.length} players matching "${query}"`);
  return results;
}

// ============================================================================
// 7. GET LEADERBOARD STATISTICS
// ============================================================================

function exampleGetStats() {
  const stats = LeaderboardManager.getLeaderboardStats();
  console.log('Leaderboard Statistics:', stats);

  // Stats include:
  // - totalPlayers: Total unique players
  // - totalSubmissions: Total score submissions
  // - topScore: Highest score on leaderboard
  // - averageScore: Average score across all players
  // - medianScore: Median score
  // - topPlayer: Name of top player
  // - lastUpdate: When leaderboard was last updated

  return stats;
}

// ============================================================================
// 8. GITHUB GIST SETUP (Optional - MVP uses localStorage only)
// ============================================================================

function exampleSetupGithubGist() {
  // Step 1: Create a public GitHub Gist with this initial content:
  // {
  //   "version": "1.0",
  //   "synced": "2025-11-16T12:00:00Z",
  //   "entries": []
  // }

  // Step 2: Get the Gist ID (from URL: https://gist.github.com/{username}/{GIST_ID})
  const GIST_ID = 'abc123def456...';

  // Step 3: Set the Gist ID
  LeaderboardManager.setGistId(GIST_ID);

  // Step 4: (Optional) Set GitHub API token for syncing
  // NOTE: In production, get this from secure OAuth flow
  // const TOKEN = 'github_pat_...';
  // LeaderboardManager.setGitHubToken(TOKEN);
}

// ============================================================================
// 9. SYNC TO GITHUB GIST (Async)
// ============================================================================

async function exampleSyncToGist() {
  // Make sure GitHub Gist is set up first
  const result = await LeaderboardManager.syncToGist();

  if (result.success) {
    console.log('Synced successfully!', result.gistUrl);
  } else {
    console.error('Sync failed:', result.message);
  }
}

// ============================================================================
// 10. FETCH FROM GITHUB GIST (Async)
// ============================================================================

async function exampleFetchFromGist() {
  const remoteData = await LeaderboardManager.fetchFromGist();

  if (remoteData) {
    console.log('Remote leaderboard:', remoteData);

    // Merge with local leaderboard
    const merged = LeaderboardManager.mergeLeaderboards(remoteData.entries);
    console.log('Merged entries:', merged.length);
  }
}

// ============================================================================
// 11. GITHUB OAUTH CLAIM FLOW
// ============================================================================

function exampleInitiateGitHubClaim(entryId) {
  // Step 1: Get OAuth config
  const config = LeaderboardManager.getGitHubOAuthConfig();

  // Step 2: Build OAuth URL
  const oauthUrl = new URL('https://github.com/login/oauth/authorize');
  oauthUrl.searchParams.set('client_id', config.clientId);
  oauthUrl.searchParams.set('redirect_uri', config.redirectUri);
  oauthUrl.searchParams.set('scope', config.scopes.join(' '));
  oauthUrl.searchParams.set('state', entryId); // Pass entry ID for identification

  // Step 3: Redirect user to GitHub
  window.location.href = oauthUrl.toString();

  // After user authorizes, GitHub redirects to your callback URL with:
  // - code: Authorization code
  // - state: Entry ID (passed through)
}

// Callback handler (on /oauth/callback page)
async function exampleHandleGitHubCallback() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get('code');
  const entryId = params.get('state');

  if (code && entryId) {
    const result = await LeaderboardManager.claimWithGitHub(code, entryId);

    if (result.success) {
      console.log('Entry claimed!', result.entry);
      // Redirect back to leaderboard or show success
      window.location.href = '/leaderboard';
    } else {
      console.error('Claim failed:', result.error);
    }
  }
}

// ============================================================================
// 12. EXPORT LEADERBOARD DATA
// ============================================================================

function exampleExportData() {
  // Export as JSON
  const jsonData = LeaderboardManager.exportJSON();
  console.log('JSON:', jsonData);

  // Export as CSV
  const csvData = LeaderboardManager.exportCSV();
  console.log('CSV:', csvData);

  // Download as file
  downloadFile(jsonData, 'leaderboard.json', 'application/json');
  downloadFile(csvData, 'leaderboard.csv', 'text/csv');
}

function downloadFile(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ============================================================================
// 13. WEEKLY ARCHIVE & RESET
// ============================================================================

function exampleManageWeekly() {
  // Archive current week
  LeaderboardManager.archiveWeek();

  // View archived week
  const pastWeek = LeaderboardManager.getArchivedWeek('2025-11-09');
  console.log('Previous week entries:', pastWeek);

  // Get summary
  const summary = LeaderboardManager.getSummary();
  console.log('Leaderboard summary:', summary);
}

// ============================================================================
// 14. FULL HTML INTEGRATION EXAMPLE
// ============================================================================

const LEADERBOARD_HTML_EXAMPLE = `
<!DOCTYPE html>
<html>
<head>
  <title>RAXE Arena Leaderboard</title>
  <style>
    .leaderboard-container {
      max-width: 1200px;
      margin: 0 auto;
      padding: 20px;
    }

    .leaderboard-table {
      width: 100%;
      border-collapse: collapse;
      background: #1a1a1a;
      color: #fff;
    }

    .leaderboard-table thead th {
      background: #2a2a2a;
      padding: 12px;
      text-align: left;
      font-weight: bold;
      border-bottom: 2px solid #444;
    }

    .leaderboard-table tbody tr {
      border-bottom: 1px solid #333;
      transition: background 0.2s;
    }

    .leaderboard-table tbody tr:hover {
      background: #252525;
    }

    .leaderboard-table td {
      padding: 12px;
    }

    .rank-col { width: 80px; }
    .nick-col { width: 200px; }
    .points-col { width: 120px; text-align: right; }
    .level-col { width: 100px; text-align: center; }
    .tier-col { width: 130px; }
    .achievement-col { width: 80px; text-align: center; }
    .time-col { width: 100px; text-align: center; }
    .github-col { width: 150px; }

    .tier-badge {
      display: inline-block;
      padding: 4px 8px;
      border-radius: 4px;
      font-size: 12px;
      font-weight: bold;
    }

    .tier-badge[data-tier="Novice"] { background: #6c757d; }
    .tier-badge[data-tier="Apprentice"] { background: #17a2b8; }
    .tier-badge[data-tier="Journeyman"] { background: #ffc107; color: #000; }
    .tier-badge[data-tier="Master"] { background: #dc3545; }
    .tier-badge[data-tier="Legend"] { background: #ff6b00; }

    .github-link {
      color: #58a6ff;
      text-decoration: none;
    }

    .github-link:hover {
      text-decoration: underline;
    }

    .unclaimed {
      color: #6c757d;
      font-size: 12px;
    }

    /* Player Card */
    .player-card {
      background: #1a1a1a;
      border: 1px solid #333;
      border-radius: 8px;
      padding: 20px;
      max-width: 400px;
    }

    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 10px;
      border-bottom: 1px solid #333;
    }

    .card-header h2 {
      margin: 0;
      font-size: 20px;
    }

    .stat-row {
      display: flex;
      justify-content: space-between;
      padding: 8px 0;
      border-bottom: 1px solid #2a2a2a;
    }

    .stat-label {
      font-weight: bold;
      color: #aaa;
    }

    .stat-value {
      color: #fff;
    }

    .card-footer {
      margin-top: 20px;
      padding-top: 20px;
      border-top: 1px solid #333;
    }

    .btn-claim-github {
      width: 100%;
      padding: 10px;
      background: #1f6feb;
      color: #fff;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-weight: bold;
    }

    .btn-claim-github:hover {
      background: #388bfd;
    }
  </style>
</head>
<body>
  <div class="leaderboard-container">
    <h1>RAXE Arena Leaderboard</h1>

    <div style="margin-bottom: 20px;">
      <button onclick="showGlobalLeaderboard()">Global</button>
      <button onclick="showWeeklyLeaderboard()">Weekly</button>
    </div>

    <div id="leaderboard-container"></div>
  </div>

  <script src="leaderboard.js"></script>
  <script>
    function showGlobalLeaderboard() {
      const entries = LeaderboardManager.getGlobalLeaderboard(100);
      LeaderboardManager.renderLeaderboard(entries, '#leaderboard-container');
    }

    function showWeeklyLeaderboard() {
      const entries = LeaderboardManager.getWeeklyLeaderboard(100);
      LeaderboardManager.renderLeaderboard(entries, '#leaderboard-container');
    }

    // Show global by default
    showGlobalLeaderboard();

    // Auto-sync to Gist every 5 minutes (if configured)
    setInterval(async () => {
      if (LeaderboardManager.GITHUB_GIST_ID) {
        await LeaderboardManager.syncToGist();
      }
    }, 5 * 60 * 1000);
  </script>
</body>
</html>
`;

// ============================================================================
// 15. GAME INTEGRATION PATTERN
// ============================================================================

/**
 * Example: How to integrate leaderboard into game completion
 */
function exampleGameCompletionIntegration(gameResult) {
  const {
    playerNickname,
    finalScore,
    levelReached,
    achievements,
    totalTimePlayed
  } = gameResult;

  // Submit score to leaderboard
  const result = LeaderboardManager.submitScore(
    playerNickname,
    finalScore,
    levelReached,
    {
      achievements: achievements.length,
      completion_time: totalTimePlayed
    }
  );

  if (result.success) {
    // Show the player their position
    const rank = LeaderboardManager.getPlayerRank(playerNickname);
    const estimatedPosition = LeaderboardManager.calculatePosition(finalScore);

    // Display results
    showGameResultsModal({
      score: result.entry.points,
      rank: result.entry.rank,
      position: rank.position,
      nextTierScore: calculateNextTierScore(result.entry.rank),
      achievements: achievements
    });

    // Auto-sync if GitHub configured
    if (LeaderboardManager.GITHUB_GIST_ID) {
      LeaderboardManager.syncToGist().catch(err => {
        console.warn('Background sync failed:', err);
      });
    }
  }
}

function calculateNextTierScore(currentRank) {
  const tiers = ['Novice', 'Apprentice', 'Journeyman', 'Master', 'Legend'];
  const currentIdx = tiers.indexOf(currentRank);
  if (currentIdx === -1 || currentIdx === tiers.length - 1) return null;

  const nextTier = tiers[currentIdx + 1];
  return LeaderboardManager.RANK_TIERS[nextTier].min;
}

function showGameResultsModal(results) {
  console.log('Game Results:', results);
  // Implement your modal/UI here
}

function showNotification(message, type = 'success') {
  console.log(`[${type.toUpperCase()}] ${message}`);
  // Implement your notification system here
}

// ============================================================================
// API ENDPOINTS NEEDED (Backend)
// ============================================================================

const BACKEND_ENDPOINTS = `
# Backend Endpoints Required for Full Integration

POST /api/github/token
  Body: { code: "oauth_code" }
  Response: { access_token: "token" }
  Purpose: Exchange GitHub OAuth code for access token

POST /api/leaderboard/verify
  Body: { entry_id, signature }
  Response: { verified: boolean }
  Purpose: Server-side score validation (optional anti-cheat)

GET /api/leaderboard/gist
  Response: { gist_id, public_url }
  Purpose: Get public leaderboard Gist info

POST /api/leaderboard/report
  Body: { entry_id, reason }
  Response: { success, message }
  Purpose: Report suspicious scores
`;

// ============================================================================
// TESTING
// ============================================================================

function runLeaderboardTests() {
  console.log('=== LEADERBOARD TEST SUITE ===\n');

  // Clear previous test data
  LeaderboardManager.clearAll();

  // Test 1: Submit scores
  console.log('Test 1: Score submission');
  for (let i = 0; i < 5; i++) {
    const result = LeaderboardManager.submitScore(
      `Player${i}`,
      Math.floor(Math.random() * 50000) + 5000,
      Math.floor(Math.random() * 100) + 1
    );
    console.log(result.message, result.entry?.points);
  }

  // Test 2: View leaderboard
  console.log('\nTest 2: Global leaderboard');
  const global = LeaderboardManager.getGlobalLeaderboard(5);
  console.table(global.map((e, i) => ({
    'Rank': i + 1,
    'Player': e.nickname,
    'Points': e.points,
    'Level': e.level
  })));

  // Test 3: Get stats
  console.log('\nTest 3: Statistics');
  const stats = LeaderboardManager.getLeaderboardStats();
  console.table(stats);

  // Test 4: Check rank
  console.log('\nTest 4: Player rank');
  const rank = LeaderboardManager.getPlayerRank('Player0');
  console.log(`Player0 is at position #${rank.position}`);

  // Test 5: Search
  console.log('\nTest 5: Search');
  const search = LeaderboardManager.searchPlayer('Player', 3);
  console.log(`Found ${search.length} players`);

  // Test 6: Export
  console.log('\nTest 6: Export');
  const csv = LeaderboardManager.exportCSV();
  console.log('CSV lines:', csv.split('\n').length);

  console.log('\n=== ALL TESTS COMPLETED ===');
}

// Run tests: runLeaderboardTests()
