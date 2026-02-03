#!/bin/bash
# Setup isolated OpenClaw + RAXE test environment
# Location: /tmp/openclaw-test (easy to remove after testing)
#
# Usage:
#   ./scripts/setup_openclaw_test.sh
#
# After setup:
#   source /tmp/openclaw-test/activate_test_env.sh
#
# Clean up:
#   rm -rf /tmp/openclaw-test

set -e

TEST_DIR="/tmp/openclaw-test"

echo "=========================================="
echo "OpenClaw + RAXE Isolated Test Environment"
echo "=========================================="
echo ""
echo "Location: $TEST_DIR"
echo ""

# Clean up any previous test
if [ -d "$TEST_DIR" ]; then
    echo "Removing previous test environment..."
    rm -rf "$TEST_DIR"
fi

mkdir -p "$TEST_DIR" && cd "$TEST_DIR"

# Check Node.js
echo "1. Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo "   ERROR: Node.js not found. Install with: brew install node@22"
    exit 1
fi
echo "   Node.js $(node --version) found"

# Check Python
echo "2. Checking Python..."
if ! command -v python3 &> /dev/null; then
    echo "   ERROR: Python3 not found."
    exit 1
fi
echo "   Python $(python3 --version) found"

# Install OpenClaw locally (not global)
echo "3. Installing OpenClaw locally..."
npm init -y > /dev/null 2>&1
npm install openclaw --silent

# Create wrapper script
mkdir -p bin
cat > bin/openclaw << 'EOF'
#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec node "$DIR/node_modules/.bin/openclaw" "$@"
EOF
chmod +x bin/openclaw

# Set up isolated OpenClaw config directory
# NOTE: OpenClaw uses OPENCLAW_CONFIG_PATH and OPENCLAW_STATE_DIR (not OPENCLAW_HOME)
echo "4. Creating isolated OpenClaw config..."
OPENCLAW_DIR="$TEST_DIR/.openclaw"
mkdir -p "$OPENCLAW_DIR/hooks"

cat > "$OPENCLAW_DIR/openclaw.json" << 'EOF'
{
  "gateway": {
    "mode": "local",
    "port": 18789,
    "bind": "loopback",
    "auth": {
      "token": "test-token-for-local-dev"
    }
  },
  "hooks": {
    "internal": {
      "enabled": true,
      "entries": {}
    }
  }
}
EOF

# Set up Python virtual environment with RAXE
echo "5. Setting up Python venv with RAXE..."
python3 -m venv venv
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet raxe

# Create activation script for easy use
# NOTE: OpenClaw uses OPENCLAW_CONFIG_PATH and OPENCLAW_STATE_DIR
cat > activate_test_env.sh << ACTIVATE_EOF
#!/bin/bash
# Activate the isolated OpenClaw + RAXE test environment
export PATH="$TEST_DIR/bin:\$PATH"
export OPENCLAW_CONFIG_PATH="$TEST_DIR/.openclaw/openclaw.json"
export OPENCLAW_STATE_DIR="$TEST_DIR/.openclaw"
export OPENCLAW_HOME="$TEST_DIR/.openclaw"
source "$TEST_DIR/venv/bin/activate"
cd "$TEST_DIR"

echo ""
echo "✓ Test environment activated!"
echo ""
echo "  OpenClaw config: \$OPENCLAW_CONFIG_PATH"
echo "  OpenClaw state:  \$OPENCLAW_STATE_DIR"
echo "  OpenClaw:        \$(which openclaw)"
echo "  RAXE:            \$(which raxe)"
echo ""
echo "Test commands:"
echo "  raxe openclaw status"
echo "  raxe openclaw install"
echo "  openclaw hooks list"
echo "  openclaw gateway run --verbose"
echo "  raxe openclaw uninstall --force"
echo ""
ACTIVATE_EOF
chmod +x activate_test_env.sh

# Verify installations
echo "6. Verifying installations..."
export PATH="$TEST_DIR/bin:$PATH"
export OPENCLAW_CONFIG_PATH="$TEST_DIR/.openclaw/openclaw.json"
export OPENCLAW_STATE_DIR="$TEST_DIR/.openclaw"
export OPENCLAW_HOME="$TEST_DIR/.openclaw"

echo "   OpenClaw: $(./bin/openclaw --version 2>/dev/null || echo 'installed')"
echo "   RAXE: $(./venv/bin/raxe --version)"

echo ""
echo "=========================================="
echo "✓ Isolated test environment ready!"
echo "=========================================="
echo ""
echo "To activate:"
echo "  source $TEST_DIR/activate_test_env.sh"
echo ""
echo "To test RAXE integration:"
echo "  raxe openclaw status      # Check current state"
echo "  raxe openclaw install     # Install hook"
echo "  openclaw hooks list       # Verify hook registered"
echo "  openclaw gateway run --verbose  # Run gateway (foreground)"
echo "  raxe openclaw uninstall --force  # Remove hook"
echo ""
echo "To clean up (removes everything):"
echo "  rm -rf $TEST_DIR"
echo "=========================================="
