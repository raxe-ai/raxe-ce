#!/bin/bash
# Cleanup script for RAXE CE repository
# Removes Python cache files and system files

set -e

echo "🧹 RAXE CE Repository Cleanup"
echo "=============================="
echo ""

# Count files before cleanup
PYCACHE_COUNT=$(find . -type d -name "__pycache__" -not -path "./.venv/*" -not -path "./.git/*" | wc -l | tr -d ' ')
PYC_COUNT=$(find . -type f -name "*.pyc" -not -path "./.venv/*" -not -path "./.git/*" | wc -l | tr -d ' ')
DS_STORE_COUNT=$(find . -name ".DS_Store" -not -path "./.venv/*" -not -path "./.git/*" | wc -l | tr -d ' ')

echo "Files to remove:"
echo "  - __pycache__ directories: $PYCACHE_COUNT"
echo "  - .pyc files: $PYC_COUNT"
echo "  - .DS_Store files: $DS_STORE_COUNT"
echo ""

if [ "$PYCACHE_COUNT" -eq 0 ] && [ "$PYC_COUNT" -eq 0 ] && [ "$DS_STORE_COUNT" -eq 0 ]; then
    echo "✅ Repository is already clean!"
    exit 0
fi

# Prompt for confirmation
read -p "Remove these files? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cleanup cancelled"
    exit 1
fi

echo ""
echo "Cleaning..."

# Remove __pycache__ directories
if [ "$PYCACHE_COUNT" -gt 0 ]; then
    echo "  Removing __pycache__ directories..."
    find . -type d -name "__pycache__" -not -path "./.venv/*" -not -path "./.git/*" -exec rm -rf {} + 2>/dev/null || true
    echo "  ✅ Removed $PYCACHE_COUNT __pycache__ directories"
fi

# Remove .pyc files
if [ "$PYC_COUNT" -gt 0 ]; then
    echo "  Removing .pyc files..."
    find . -type f -name "*.pyc" -not -path "./.venv/*" -not -path "./.git/*" -delete 2>/dev/null || true
    echo "  ✅ Removed $PYC_COUNT .pyc files"
fi

# Remove .DS_Store files
if [ "$DS_STORE_COUNT" -gt 0 ]; then
    echo "  Removing .DS_Store files..."
    find . -name ".DS_Store" -not -path "./.venv/*" -not -path "./.git/*" -delete 2>/dev/null || true
    echo "  ✅ Removed $DS_STORE_COUNT .DS_Store files"
fi

echo ""
echo "✅ Cleanup complete!"
echo ""

# Show remaining files
REMAINING=$(find . \( -type d -name "__pycache__" -o -type f -name "*.pyc" -o -name ".DS_Store" \) -not -path "./.venv/*" -not -path "./.git/*" | wc -l | tr -d ' ')

if [ "$REMAINING" -eq 0 ]; then
    echo "🎉 Repository is now clean!"
else
    echo "⚠️  Warning: $REMAINING cache files still remain (possibly in .venv or .git)"
fi
