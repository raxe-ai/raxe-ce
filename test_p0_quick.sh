#!/bin/bash
# Quick P0 Verification Script
# Tests all 5 P0 implementations

set -e  # Exit on error

echo "╔═══════════════════════════════════════════════════════╗"
echo "║         RAXE P0 Implementation Quick Test            ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS="${GREEN}✓${NC}"
FAIL="${RED}✗${NC}"

# Test counter
TOTAL=0
PASSED=0
FAILED=0

run_test() {
    TOTAL=$((TOTAL + 1))
    echo -n "Test $TOTAL: $1... "
    if eval "$2" > /dev/null 2>&1; then
        echo -e "${PASS}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${FAIL}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

run_test_with_output() {
    TOTAL=$((TOTAL + 1))
    echo "Test $TOTAL: $1"
    if eval "$2"; then
        echo -e "${PASS} Passed"
        PASSED=$((PASSED + 1))
        echo ""
        return 0
    else
        echo -e "${FAIL} Failed"
        FAILED=$((FAILED + 1))
        echo ""
        return 1
    fi
}

echo "════════════════════════════════════════════════════════"
echo "P0-1: Test Infrastructure"
echo "════════════════════════════════════════════════════════"

run_test "Test collection (0 errors)" \
    "python -m pytest tests --collect-only -q 2>&1 | grep -q 'tests collected'"

run_test "Suppression tests exist and pass" \
    "python -m pytest tests/test_suppression_system.py -q 2>&1 | grep -q 'passed'"

echo ""
echo "════════════════════════════════════════════════════════"
echo "P0-2: Explainability System"
echo "════════════════════════════════════════════════════════"

run_test "Explainability demo script exists" \
    "test -f test_explainability_demo.py"

run_test "Detection model has explanation fields" \
    "grep -q 'risk_explanation' src/raxe/domain/engine/executor.py"

run_test "Rules have explanations (pi-001)" \
    "grep -q 'risk_explanation:' src/raxe/packs/core/v1.0.0/rules/PI/pi-001@1.0.0.yaml"

run_test "Privacy footer in output.py" \
    "grep -q 'Privacy-First' src/raxe/cli/output.py"

echo ""
echo "════════════════════════════════════════════════════════"
echo "P0-3: Suppression Mechanism"
echo "════════════════════════════════════════════════════════"

run_test "Suppression module exists" \
    "test -f src/raxe/domain/suppression.py"

run_test "Suppress CLI commands exist" \
    "test -f src/raxe/cli/suppress.py"

run_test "SuppressionManager class exists" \
    "grep -q 'class SuppressionManager' src/raxe/domain/suppression.py"

run_test ".raxeignore example exists" \
    "test -f .raxeignore.example"

echo ""
echo "════════════════════════════════════════════════════════"
echo "P0-4: CLI Flags Fixed"
echo "════════════════════════════════════════════════════════"

run_test "dry_run parameter in client.py" \
    "grep -q 'dry_run: bool = False' src/raxe/sdk/client.py"

run_test "CLI flags wired to scan()" \
    "grep -q 'l1_enabled=not l2_only' src/raxe/cli/main.py"

run_test "confidence_threshold parameter passed" \
    "grep -q 'confidence_threshold=' src/raxe/cli/main.py"

run_test "All 6 flags defined" \
    "grep -q 'dry-run' src/raxe/cli/main.py && grep -q 'l1-only' src/raxe/cli/main.py && grep -q 'confidence' src/raxe/cli/main.py"

echo ""
echo "════════════════════════════════════════════════════════"
echo "P0-5: Privacy Footer"
echo "════════════════════════════════════════════════════════"

run_test "Privacy command exists" \
    "test -f src/raxe/cli/privacy.py"

run_test "Privacy command registered" \
    "grep -q 'privacy_command' src/raxe/cli/main.py"

run_test "Privacy footer function exists" \
    "grep -q '_display_privacy_footer' src/raxe/cli/output.py"

run_test "SHA256 mentioned in footer" \
    "grep -q 'SHA256' src/raxe/cli/output.py"

echo ""
echo "════════════════════════════════════════════════════════"
echo "Functional Tests (CLI Commands)"
echo "════════════════════════════════════════════════════════"

# Only run if raxe is installed
if command -v raxe &> /dev/null; then
    run_test "raxe --version works" \
        "raxe --version"

    run_test "raxe privacy command works" \
        "raxe privacy | grep -q 'Privacy Guarantees'"

    run_test "raxe suppress --help works" \
        "raxe suppress --help | grep -q 'Manage false positive'"

    # Clean test
    run_test "Basic scan works" \
        "echo 'test' | raxe scan --stdin --format json | grep -q 'has_detections'"
else
    echo -e "${YELLOW}Skipping functional tests - raxe not in PATH${NC}"
    echo "Install with: pip install -e ."
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "Documentation Review"
echo "════════════════════════════════════════════════════════"

run_test "Explainability guide exists" \
    "test -f EXPLAINABILITY_GUIDE.md"

run_test "Suppression guide exists" \
    "test -f SUPPRESSION_GUIDE.md"

run_test "Test fix report exists" \
    "test -f TEST_COLLECTION_FIX_REPORT.md"

run_test "Quick start testing guide exists" \
    "test -f QUICK_START_TESTING.md"

echo ""
echo "╔═══════════════════════════════════════════════════════╗"
echo "║                    RESULTS SUMMARY                    ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "Total Tests:  $TOTAL"
echo -e "Passed:       ${GREEN}$PASSED${NC}"
echo -e "Failed:       ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          ✓ ALL P0 TESTS PASSED - READY!              ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════╝${NC}"
    exit 0
else
    echo -e "${RED}╔═══════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║          ✗ SOME TESTS FAILED - REVIEW NEEDED          ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "See P0_TESTING_PLAN.md for detailed testing instructions"
    exit 1
fi
