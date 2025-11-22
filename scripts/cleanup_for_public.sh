#!/bin/bash
set -e

echo "🧹 RAXE Public Release Cleanup Script"
echo "======================================"
echo ""
echo "⚠️  WARNING: This will DELETE internal files!"
echo ""
echo "Before running this script, ensure you have:"
echo "  1. Committed all current work"
echo "  2. Created a backup branch: git checkout -b pre-public-release-backup"
echo "  3. Tagged current state: git tag backup-before-cleanup"
echo ""
echo "Press Ctrl+C to cancel, or Enter to continue..."
read

# Function to count files before deletion
count_files() {
    local pattern="$1"
    find . -name "$pattern" 2>/dev/null | wc -l | tr -d ' '
}

# Track statistics
total_removed=0

echo ""
echo "📊 Analysis Phase..."
echo "===================="

dirs_to_remove="CLAUDE_WORKING_FILES big_test_data ML-Team-Input venv .venv .venv-build htmlcov .pytest_cache .mypy_cache .ruff_cache"
files_to_remove="*_SUMMARY.md *_REPORT.md *_CHECKLIST.md *_PLAN.md *_IMPLEMENTATION.md *_ANALYSIS.md *_PROPOSAL.md *_INTEGRATION.md test_*.py coverage.json .coverage"

for dir in $dirs_to_remove; do
    if [ -d "$dir" ]; then
        count=$(find "$dir" -type f 2>/dev/null | wc -l | tr -d ' ')
        echo "  📁 $dir: $count files"
    fi
done

echo ""
echo "📋 Step 1: Removing internal development directories..."
for dir in CLAUDE_WORKING_FILES big_test_data ML-Team-Input; do
    if [ -d "$dir" ]; then
        count=$(find "$dir" -type f 2>/dev/null | wc -l | tr -d ' ')
        rm -rf "$dir"
        echo "  ✅ Removed $dir ($count files)"
        total_removed=$((total_removed + count))
    else
        echo "  ⏭️  Skipped $dir (not found)"
    fi
done

echo ""
echo "📋 Step 2: Removing virtual environments..."
for dir in venv .venv .venv-build; do
    if [ -d "$dir" ]; then
        rm -rf "$dir"
        echo "  ✅ Removed $dir"
    fi
done

echo ""
echo "📋 Step 3: Removing cache directories..."
for dir in htmlcov .pytest_cache .mypy_cache .ruff_cache; do
    if [ -d "$dir" ]; then
        rm -rf "$dir"
        echo "  ✅ Removed $dir"
    fi
done

echo ""
echo "📋 Step 4: Removing internal documents in root..."
removed_docs=0
for pattern in "*_SUMMARY.md" "*_REPORT.md" "*_CHECKLIST.md" "*_PLAN.md" "*_IMPLEMENTATION.md" "*_ANALYSIS.md" "*_PROPOSAL.md" "*_INTEGRATION.md"; do
    count=$(ls $pattern 2>/dev/null | wc -l | tr -d ' ')
    if [ $count -gt 0 ]; then
        rm -f $pattern
        removed_docs=$((removed_docs + count))
    fi
done
if [ $removed_docs -gt 0 ]; then
    echo "  ✅ Removed $removed_docs internal documents"
    total_removed=$((total_removed + removed_docs))
else
    echo "  ⏭️  No internal documents found"
fi

echo ""
echo "📋 Step 5: Removing scattered test files in root..."
test_count=$(ls test_*.py 2>/dev/null | wc -l | tr -d ' ')
if [ $test_count -gt 0 ]; then
    rm -f test_*.py
    echo "  ✅ Removed $test_count test files"
    total_removed=$((total_removed + test_count))
else
    echo "  ⏭️  No scattered test files found"
fi

echo ""
echo "📋 Step 6: Removing build artifacts..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true
rm -f coverage.json .coverage 2>/dev/null || true
echo "  ✅ Build artifacts removed"

echo ""
echo "📋 Step 7: Updating .gitignore..."
if ! grep -q "CLAUDE_WORKING_FILES/" .gitignore 2>/dev/null; then
    cat >> .gitignore << 'EOF'

# Internal development (added by cleanup script)
CLAUDE_WORKING_FILES/
big_test_data/
ML-Team-Input/

# Virtual environments
venv/
.venv*/
env/

# Coverage
coverage.json
htmlcov/
.coverage

# Caches
.pytest_cache/
.mypy_cache/
.ruff_cache/
__pycache__/
*.pyc
*.pyo

# Build
*.egg-info/
dist/
build/
EOF
    echo "  ✅ .gitignore updated"
else
    echo "  ⏭️  .gitignore already contains cleanup rules"
fi

echo ""
echo "📋 Step 8: Verifying critical directories..."
errors=0

if [ -d "src/raxe" ]; then
    echo "  ✅ src/raxe/ directory intact"
else
    echo "  ❌ ERROR: src/raxe/ directory missing!"
    errors=$((errors + 1))
fi

if [ -d "tests" ]; then
    echo "  ✅ tests/ directory intact"
else
    echo "  ❌ ERROR: tests/ directory missing!"
    errors=$((errors + 1))
fi

if [ -f "README.md" ]; then
    echo "  ✅ README.md intact"
else
    echo "  ⚠️  WARNING: README.md missing!"
fi

if [ -f "LICENSE" ]; then
    echo "  ⚠️  LICENSE file exists (needs manual review/replacement)"
else
    echo "  ❌ WARNING: LICENSE file missing!"
fi

if [ $errors -gt 0 ]; then
    echo ""
    echo "❌ CRITICAL ERRORS DETECTED!"
    echo "Please review the errors above before committing."
    exit 1
fi

echo ""
echo "🎉 Cleanup complete!"
echo ""
echo "📊 Statistics:"
echo "  Files removed: ~$total_removed+ tracked files"
echo "  Plus: All cache, build artifacts, and virtual environments"
echo ""
echo "✅ Next steps:"
echo "  1. Review changes: git status"
echo "  2. Check what was removed: git diff"
echo "  3. ⚠️  CRITICAL: Replace LICENSE file with proper MIT license!"
echo "  4. Update README.md (remove internal references)"
echo "  5. Run tests: source .venv/bin/activate && pytest"
echo "  6. Review security: Check the master report"
echo "  7. Commit: git add -A && git commit -m 'chore: clean repository for public release'"
echo ""
echo "⚠️  REMEMBER - These are STILL required:"
echo "   🚨 Fix LICENSE file (currently NOT open source!)"
echo "   🚨 Improve test coverage to >80%"
echo "   🚨 Review 84 security findings"
echo "   🚨 Update documentation"
echo ""
echo "📄 See MASTER_CLEANUP_REPORT.md for full details"
