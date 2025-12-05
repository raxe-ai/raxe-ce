"""
Exit codes for RAXE CLI.

Standardized exit codes for consistent scripting and CI/CD integration.

Exit Code Reference:
    EXIT_SUCCESS (0)         - Command completed successfully (no threats detected)
    EXIT_THREAT_DETECTED (1) - Threat(s) detected during scan
    EXIT_INVALID_INPUT (2)   - Invalid command arguments or input
    EXIT_CONFIG_ERROR (3)    - Configuration problem (missing config, invalid settings)
    EXIT_SCAN_ERROR (4)      - Scan execution failed (internal error)

Usage in CI/CD:
    # Check for threats
    raxe scan "prompt" --quiet
    if [ $? -eq 1 ]; then
        echo "Threat detected!"
    fi

    # Handle different error types
    raxe scan "prompt" --quiet
    case $? in
        0) echo "Clean" ;;
        1) echo "Threat detected" ;;
        2) echo "Invalid input" ;;
        3) echo "Config error" ;;
        4) echo "Scan failed" ;;
    esac
"""

# Success - no threats detected, command completed normally
EXIT_SUCCESS: int = 0

# Threat detected during scan (used with --quiet mode for CI/CD)
EXIT_THREAT_DETECTED: int = 1

# Invalid input - bad command usage, missing required arguments
EXIT_INVALID_INPUT: int = 2

# Configuration error - missing config file, invalid settings
EXIT_CONFIG_ERROR: int = 3

# Scan execution error - internal failure during scan
EXIT_SCAN_ERROR: int = 4

# Authentication/credential error - expired or invalid API key
EXIT_AUTH_ERROR: int = 5


__all__ = [
    "EXIT_AUTH_ERROR",
    "EXIT_CONFIG_ERROR",
    "EXIT_INVALID_INPUT",
    "EXIT_SCAN_ERROR",
    "EXIT_SUCCESS",
    "EXIT_THREAT_DETECTED",
]
