#!/bin/bash
# Upload to PyPI (Production)
# Usage: ./scripts/release/upload_prod.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

echo "🚀 Uploading to PyPI (Production)..."

# Check if twine is installed
if ! command -v twine &> /dev/null; then
    echo "❌ Error: 'twine' not found. Please install it: pip install twine"
    exit 1
fi

# Check if dist/ exists
if [ ! -d "dist" ]; then
    echo "❌ Error: dist/ directory not found. Run build.sh first."
    exit 1
fi

echo ""
echo "⚠️  WARNING: You are about to upload to PRODUCTION PyPI!"
echo "   This action CANNOT be undone."
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
echo
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "❌ Upload cancelled."
    exit 1
fi

# Check if .pypirc exists
if [ ! -f "$HOME/.pypirc" ]; then
    echo "❌ Error: ~/.pypirc not found."
    echo ""
    echo "📝 Please setup PyPI configuration first:"
    echo "   make setup-pypirc"
    echo ""
    echo "   Or manually copy and configure:"
    echo "   cp scripts/release/.pypirc.example ~/.pypirc"
    echo "   vim ~/.pypirc"
    echo "   chmod 600 ~/.pypirc"
    echo ""
    echo "   Get your API token at: https://pypi.org/manage/account/token/"
    exit 1
fi

echo ""
echo "📝 Using PyPI configuration from ~/.pypirc"
echo "   Get your API token at: https://pypi.org/manage/account/token/"
echo ""

# Upload to PyPI
twine upload dist/*

echo ""
echo "✅ Upload to PyPI completed!"
echo ""
echo "🔗 View your package at: https://pypi.org/project/orca-lab/"
echo ""
echo "📦 Install with:"
echo "   pip install orca-lab"
