#!/bin/bash
# Upload to TestPyPI
# Usage: ./scripts/release/upload_test.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

echo "🚀 Uploading to TestPyPI..."

# Check if twine is installed
if ! command -v twine &> /dev/null; then
    echo "❌ Error: 'twine' not found. Please install it: pip install twine"
    exit 1
fi

# Check if dist-test/ exists (built by build.sh)
if [ ! -d "dist-test" ]; then
    echo "❌ Error: dist-test/ directory not found. Run build.sh first."
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
    echo "   Get your API token at: https://test.pypi.org/manage/account/token/"
    exit 1
fi

echo ""
echo "📝 Using PyPI configuration from ~/.pypirc"
echo "   Get your API token at: https://test.pypi.org/manage/account/token/"
echo ""

# Upload to TestPyPI (use the test package artifacts)
twine upload --repository testpypi dist-test/*

echo ""
echo "✅ Upload to TestPyPI completed!"
echo ""
echo "🔗 View your package at: https://test.pypi.org/project/orca-lab/"
echo ""
echo "📦 Test installation:"
echo "   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ orca-lab"
