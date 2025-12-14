#!/bin/bash
# Installation Benchmark Script
# Tests package installation time and size across different methods

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

INSTALL_TIMEOUT=30  # Maximum install time in seconds
MAX_PACKAGE_SIZE=10485760  # 10MB in bytes

echo "========================================"
echo "RAXE Installation Benchmark"
echo "========================================"
echo ""

# Function to time command execution
time_command() {
    local start=$(date +%s)
    "$@"
    local end=$(date +%s)
    echo $((end - start))
}

# Function to cleanup
cleanup() {
    echo "Cleaning up..."
    rm -rf test_venv_*
    deactivate 2>/dev/null || true
}

trap cleanup EXIT

# Test 1: Package Size Check
echo "Test 1: Package Size Check"
echo "-------------------------------------------"

if [ -f "dist/"*.whl ]; then
    WHEEL_SIZE=$(ls -l dist/*.whl | awk '{print $5}')
    WHEEL_SIZE_MB=$(echo "scale=2; $WHEEL_SIZE / 1048576" | bc)

    echo "Wheel size: ${WHEEL_SIZE_MB}MB (${WHEEL_SIZE} bytes)"

    if [ "$WHEEL_SIZE" -gt "$MAX_PACKAGE_SIZE" ]; then
        echo -e "${RED}FAIL: Package exceeds 10MB limit${NC}"
        exit 1
    else
        echo -e "${GREEN}PASS: Package size within limit${NC}"
    fi
else
    echo -e "${YELLOW}WARNING: No wheel found in dist/. Building...${NC}"
    python3 -m build
    WHEEL_SIZE=$(ls -l dist/*.whl | awk '{print $5}')
    WHEEL_SIZE_MB=$(echo "scale=2; $WHEEL_SIZE / 1048576" | bc)
    echo "Wheel size: ${WHEEL_SIZE_MB}MB"
fi

echo ""

# Test 2: Fresh Install from Wheel
echo "Test 2: Fresh Install from Wheel"
echo "-------------------------------------------"

python3 -m venv test_venv_wheel
source test_venv_wheel/bin/activate

INSTALL_TIME=$(time_command pip install --quiet dist/*.whl)

echo "Installation time: ${INSTALL_TIME} seconds"

if [ "$INSTALL_TIME" -gt "$INSTALL_TIMEOUT" ]; then
    echo -e "${RED}FAIL: Installation exceeded ${INSTALL_TIMEOUT}s timeout${NC}"
else
    echo -e "${GREEN}PASS: Installation completed in ${INSTALL_TIME}s${NC}"
fi

# Verify installation
python -c "from raxe import Raxe; print('Import successful')"
raxe --version

deactivate
echo ""

# Test 3: Install with Dependencies
echo "Test 3: Install with All Dependencies"
echo "-------------------------------------------"

python3 -m venv test_venv_deps
source test_venv_deps/bin/activate

INSTALL_TIME=$(time_command pip install --quiet "dist/*.whl[all]")

echo "Installation time (with all deps): ${INSTALL_TIME} seconds"

# Test imports
python -c "
from raxe import Raxe
print('Core import: OK')
"

deactivate
echo ""

# Test 4: Editable Install
echo "Test 4: Editable Install (Development)"
echo "-------------------------------------------"

python3 -m venv test_venv_dev
source test_venv_dev/bin/activate

INSTALL_TIME=$(time_command pip install --quiet -e ".[dev]")

echo "Editable install time: ${INSTALL_TIME} seconds"

# Run quick test
python -c "from raxe import Raxe; r = Raxe(); print('Development install: OK')"

deactivate
echo ""

# Test 5: Import Time
echo "Test 5: Import Performance"
echo "-------------------------------------------"

source test_venv_wheel/bin/activate

# Measure import time
IMPORT_TIME=$(python -c "
import time
start = time.time()
from raxe import Raxe
end = time.time()
print(f'{(end - start) * 1000:.2f}')
")

echo "Import time: ${IMPORT_TIME}ms"

if (( $(echo "$IMPORT_TIME > 1000" | bc -l) )); then
    echo -e "${YELLOW}WARNING: Import time > 1 second${NC}"
else
    echo -e "${GREEN}PASS: Import time acceptable${NC}"
fi

deactivate
echo ""

# Test 6: Package Contents
echo "Test 6: Package Contents Check"
echo "-------------------------------------------"

unzip -l dist/*.whl | grep -E "\.(py|yaml|yml)$" | wc -l | xargs echo "Python/YAML files:"
unzip -l dist/*.whl | grep -E "\.(pyc|pyo)$" | wc -l | xargs echo "Compiled files:"
unzip -l dist/*.whl | grep -E "test|Test" | wc -l | xargs echo "Test files:"

TEST_FILES=$(unzip -l dist/*.whl | grep -E "test|Test" | wc -l)
if [ "$TEST_FILES" -gt 0 ]; then
    echo -e "${YELLOW}WARNING: Test files found in wheel${NC}"
else
    echo -e "${GREEN}PASS: No test files in wheel${NC}"
fi

echo ""

# Summary
echo "========================================"
echo "Benchmark Summary"
echo "========================================"
echo ""
echo "Package Size: ${WHEEL_SIZE_MB}MB"
echo "Install Time: ${INSTALL_TIME}s"
echo "Import Time: ${IMPORT_TIME}ms"
echo ""

if [ "$WHEEL_SIZE" -le "$MAX_PACKAGE_SIZE" ] && [ "$INSTALL_TIME" -le "$INSTALL_TIMEOUT" ]; then
    echo -e "${GREEN}All benchmarks PASSED${NC}"
    exit 0
else
    echo -e "${RED}Some benchmarks FAILED${NC}"
    exit 1
fi
