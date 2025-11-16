/**
 * RAXE Arena - LocalStorage Management Module
 * Handles all data persistence, privacy, and compression features
 */

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Check if localStorage is available and accessible
 */
function isLocalStorageAvailable() {
  try {
    const test = '__localStorage_test__';
    localStorage.setItem(test, test);
    localStorage.removeItem(test);
    return true;
  } catch (e) {
    return false;
  }
}

/**
 * Compute SHA-256 hash of a string (browser-compatible)
 * Uses Web Crypto API
 */
async function sha256(text) {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Synchronous hash using simple implementation
 * For immediate hashing without async/await
 */
function simpleHash(text) {
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(16);
}

/**
 * Remove personally identifiable information from text
 */
function removePII(text) {
  if (typeof text !== 'string') return text;

  let cleaned = text;

  // Remove email addresses
  cleaned = cleaned.replace(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g, '[EMAIL]');

  // Remove phone numbers
  cleaned = cleaned.replace(/\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/g, '[PHONE]');

  // Remove common name patterns
  cleaned = cleaned.replace(/\b[A-Z][a-z]+ [A-Z][a-z]+\b/g, '[NAME]');

  // Remove SSN-like patterns
  cleaned = cleaned.replace(/\b\d{3}-\d{2}-\d{4}\b/g, '[SSN]');

  return cleaned;
}

/**
 * Get current timestamp
 */
function getCurrentTimestamp() {
  return new Date().getTime();
}

/**
 * Check if data is older than specified days
 */
function isDataExpired(timestamp, days = 30) {
  const now = getCurrentTimestamp();
  const millisPerDay = 24 * 60 * 60 * 1000;
  return (now - timestamp) > (days * millisPerDay);
}

/**
 * Estimate size of object in bytes
 */
function estimateSize(obj) {
  try {
    return new Blob([JSON.stringify(obj)]).size;
  } catch (e) {
    return 0;
  }
}

// ============================================================================
// STORAGE CLASS
// ============================================================================

class StorageManager {
  constructor() {
    this.STORAGE_AVAILABLE = isLocalStorageAvailable();
    this.KEYS = {
      PROGRESS: 'raxe_arena_progress',
      SETTINGS: 'raxe_arena_settings',
      SCANS: 'raxe_arena_scans',
      ACHIEVEMENTS: 'raxe_arena_achievements'
    };

    // Default settings
    this.DEFAULT_SETTINGS = {
      theme: 'dark',
      soundEnabled: true,
      dataCollection: false,
      difficulty: 'normal',
      language: 'en',
      privacyAgreed: false,
      lastBackup: 0
    };

    // Constraints
    this.MAX_SCANS = 1000;
    this.SCAN_RETENTION_DAYS = 30;
    this.COMPRESSION_THRESHOLD = 100000; // bytes
  }

  // ========================================================================
  // CORE METHODS
  // ========================================================================

  /**
   * Save game progress
   */
  saveProgress(gameState) {
    if (!this.STORAGE_AVAILABLE) {
      console.warn('Storage: localStorage not available, progress not saved');
      return false;
    }

    try {
      // Validate game state
      if (!gameState || typeof gameState !== 'object') {
        console.error('Storage: Invalid game state');
        return false;
      }

      // Create progress object with metadata
      const progress = {
        version: 1,
        timestamp: getCurrentTimestamp(),
        state: gameState
      };

      // Attempt to save
      const data = JSON.stringify(progress);
      localStorage.setItem(this.KEYS.PROGRESS, data);

      console.log('Storage: Progress saved successfully');
      return true;
    } catch (e) {
      if (e.name === 'QuotaExceededError') {
        console.error('Storage: LocalStorage quota exceeded');
        this._handleQuotaExceeded();
        return false;
      }
      console.error('Storage: Error saving progress', e);
      return false;
    }
  }

  /**
   * Load game progress with validation
   */
  loadProgress() {
    if (!this.STORAGE_AVAILABLE) {
      console.warn('Storage: localStorage not available, returning default state');
      return this._getDefaultGameState();
    }

    try {
      const data = localStorage.getItem(this.KEYS.PROGRESS);

      if (!data) {
        console.log('Storage: No progress found, returning default state');
        return this._getDefaultGameState();
      }

      const progress = JSON.parse(data);

      // Validate data structure
      if (!progress.state || typeof progress.state !== 'object') {
        console.error('Storage: Corrupted progress data');
        return this._getDefaultGameState();
      }

      console.log('Storage: Progress loaded successfully');
      return progress.state;
    } catch (e) {
      console.error('Storage: Error loading progress', e);
      return this._getDefaultGameState();
    }
  }

  /**
   * Clear all saved progress
   */
  clearProgress() {
    if (!this.STORAGE_AVAILABLE) {
      console.warn('Storage: localStorage not available, cannot clear');
      return false;
    }

    try {
      localStorage.removeItem(this.KEYS.PROGRESS);
      console.log('Storage: Progress cleared');
      return true;
    } catch (e) {
      console.error('Storage: Error clearing progress', e);
      return false;
    }
  }

  /**
   * Get user setting by key
   */
  getSetting(key) {
    try {
      const settings = this._loadSettings();
      return settings.hasOwnProperty(key) ? settings[key] : this.DEFAULT_SETTINGS[key];
    } catch (e) {
      console.error('Storage: Error getting setting', e);
      return this.DEFAULT_SETTINGS[key];
    }
  }

  /**
   * Set user setting
   */
  setSetting(key, value) {
    if (!this.STORAGE_AVAILABLE) {
      console.warn('Storage: localStorage not available, setting not saved');
      return false;
    }

    try {
      const settings = this._loadSettings();
      settings[key] = value;

      const data = JSON.stringify(settings);
      localStorage.setItem(this.KEYS.SETTINGS, data);

      console.log(`Storage: Setting '${key}' updated`);
      return true;
    } catch (e) {
      console.error('Storage: Error setting value', e);
      return false;
    }
  }

  /**
   * Store a scan for dataset (if opted in)
   */
  async storeScan(prompt, result) {
    // Check if user opted into data collection
    if (!this.getSetting('dataCollection')) {
      return false;
    }

    if (!this.STORAGE_AVAILABLE) {
      console.warn('Storage: localStorage not available, scan not stored');
      return false;
    }

    try {
      // Remove PII from prompt
      const cleanPrompt = removePII(prompt);

      // Hash the prompt for privacy
      const promptHash = simpleHash(cleanPrompt);

      // Create scan object
      const scan = {
        id: promptHash + '_' + getCurrentTimestamp(),
        promptHash: promptHash,
        promptLength: cleanPrompt.length,
        result: result,
        timestamp: getCurrentTimestamp(),
        privacyLevel: 'hashed'
      };

      // Load existing scans
      let scans = this._loadScans();

      // Add new scan
      scans.push(scan);

      // Apply compression (remove old/excess scans)
      scans = this._compressScans(scans);

      // Save compressed scans
      const data = JSON.stringify(scans);
      localStorage.setItem(this.KEYS.SCANS, data);

      console.log('Storage: Scan stored successfully');
      return true;
    } catch (e) {
      if (e.name === 'QuotaExceededError') {
        console.error('Storage: LocalStorage quota exceeded when storing scan');
        this._handleQuotaExceeded();
        return false;
      }
      console.error('Storage: Error storing scan', e);
      return false;
    }
  }

  /**
   * Get all stored scans
   */
  getScanHistory() {
    try {
      return this._loadScans();
    } catch (e) {
      console.error('Storage: Error loading scan history', e);
      return [];
    }
  }

  /**
   * Export all data as JSON
   */
  exportData() {
    try {
      const exportData = {
        version: 1,
        exportDate: new Date().toISOString(),
        privacyWarning: 'This export contains personal data. Keep it secure.',
        data: {
          progress: this._safeJSONParse(localStorage.getItem(this.KEYS.PROGRESS)),
          settings: this._safeJSONParse(localStorage.getItem(this.KEYS.SETTINGS)),
          scans: this._safeJSONParse(localStorage.getItem(this.KEYS.SCANS)),
          achievements: this._safeJSONParse(localStorage.getItem(this.KEYS.ACHIEVEMENTS))
        }
      };

      return JSON.stringify(exportData, null, 2);
    } catch (e) {
      console.error('Storage: Error exporting data', e);
      return null;
    }
  }

  /**
   * Import data from JSON
   */
  importData(jsonString) {
    if (!this.STORAGE_AVAILABLE) {
      console.warn('Storage: localStorage not available, cannot import');
      return false;
    }

    try {
      const importedData = JSON.parse(jsonString);

      // Validate import structure
      if (!importedData.data || importedData.version !== 1) {
        console.error('Storage: Invalid import format');
        return false;
      }

      // Import each data type with validation
      if (importedData.data.progress) {
        localStorage.setItem(this.KEYS.PROGRESS, JSON.stringify(importedData.data.progress));
      }

      if (importedData.data.settings) {
        localStorage.setItem(this.KEYS.SETTINGS, JSON.stringify(importedData.data.settings));
      }

      if (importedData.data.scans) {
        localStorage.setItem(this.KEYS.SCANS, JSON.stringify(importedData.data.scans));
      }

      if (importedData.data.achievements) {
        localStorage.setItem(this.KEYS.ACHIEVEMENTS, JSON.stringify(importedData.data.achievements));
      }

      console.log('Storage: Data imported successfully');
      return true;
    } catch (e) {
      console.error('Storage: Error importing data', e);
      return false;
    }
  }

  /**
   * Get storage statistics
   */
  getStorageStats() {
    try {
      const stats = {
        available: this.STORAGE_AVAILABLE,
        progress: {
          exists: !!localStorage.getItem(this.KEYS.PROGRESS),
          size: estimateSize(localStorage.getItem(this.KEYS.PROGRESS))
        },
        settings: {
          exists: !!localStorage.getItem(this.KEYS.SETTINGS),
          size: estimateSize(localStorage.getItem(this.KEYS.SETTINGS))
        },
        scans: {
          exists: !!localStorage.getItem(this.KEYS.SCANS),
          size: estimateSize(localStorage.getItem(this.KEYS.SCANS)),
          count: this._loadScans().length
        },
        achievements: {
          exists: !!localStorage.getItem(this.KEYS.ACHIEVEMENTS),
          size: estimateSize(localStorage.getItem(this.KEYS.ACHIEVEMENTS))
        },
        totalSize: 0
      };

      // Calculate total size
      stats.totalSize = stats.progress.size + stats.settings.size +
                        stats.scans.size + stats.achievements.size;

      return stats;
    } catch (e) {
      console.error('Storage: Error getting stats', e);
      return null;
    }
  }

  /**
   * Clear all data (nuclear option)
   */
  clearAllData() {
    if (!this.STORAGE_AVAILABLE) {
      return false;
    }

    try {
      for (const key of Object.values(this.KEYS)) {
        localStorage.removeItem(key);
      }
      console.log('Storage: All data cleared');
      return true;
    } catch (e) {
      console.error('Storage: Error clearing all data', e);
      return false;
    }
  }

  // ========================================================================
  // PRIVATE HELPER METHODS
  // ========================================================================

  /**
   * Load settings with defaults
   */
  _loadSettings() {
    try {
      const data = localStorage.getItem(this.KEYS.SETTINGS);
      if (!data) {
        return { ...this.DEFAULT_SETTINGS };
      }
      const settings = JSON.parse(data);
      return { ...this.DEFAULT_SETTINGS, ...settings };
    } catch (e) {
      console.error('Storage: Error loading settings', e);
      return { ...this.DEFAULT_SETTINGS };
    }
  }

  /**
   * Load scans array
   */
  _loadScans() {
    try {
      const data = localStorage.getItem(this.KEYS.SCANS);
      return data ? JSON.parse(data) : [];
    } catch (e) {
      console.error('Storage: Error loading scans', e);
      return [];
    }
  }

  /**
   * Get default game state
   */
  _getDefaultGameState() {
    return {
      level: 1,
      score: 0,
      health: 100,
      inventory: [],
      position: { x: 0, y: 0 },
      completedLevels: [],
      timePlayedMs: 0
    };
  }

  /**
   * Compress scans by removing old and excess entries
   */
  _compressScans(scans) {
    if (!Array.isArray(scans)) return [];

    let compressed = scans
      .filter(scan => !isDataExpired(scan.timestamp, this.SCAN_RETENTION_DAYS))
      .sort((a, b) => b.timestamp - a.timestamp) // Sort newest first
      .slice(0, this.MAX_SCANS); // Keep only most recent

    return compressed;
  }

  /**
   * Handle quota exceeded by removing oldest scans
   */
  _handleQuotaExceeded() {
    try {
      let scans = this._loadScans();
      if (scans.length > 0) {
        // Remove oldest scans
        scans = scans.sort((a, b) => b.timestamp - a.timestamp).slice(0, Math.floor(this.MAX_SCANS / 2));
        localStorage.setItem(this.KEYS.SCANS, JSON.stringify(scans));
        console.log('Storage: Removed old scans to free up space');
      }
    } catch (e) {
      console.error('Storage: Error handling quota exceeded', e);
    }
  }

  /**
   * Safe JSON parse
   */
  _safeJSONParse(jsonString) {
    try {
      return jsonString ? JSON.parse(jsonString) : null;
    } catch (e) {
      return null;
    }
  }
}

// ============================================================================
// SINGLETON EXPORT
// ============================================================================

// Create singleton instance
const Storage = new StorageManager();

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Storage;
}
