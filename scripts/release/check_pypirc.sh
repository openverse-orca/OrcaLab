#!/bin/bash
# Check .pypirc configuration
# Usage: ./scripts/release/check_pypirc.sh

set -e

echo "🔍 Checking PyPI configuration..."

# Check if .pypirc exists
if [ ! -f "$HOME/.pypirc" ]; then
    echo "❌ ~/.pypirc not found"
    echo ""
    echo "📝 To setup PyPI configuration:"
    echo "   make setup-pypirc"
    exit 1
fi

echo "✅ ~/.pypirc found"

# Check file permissions
PERMS=$(stat -c "%a" "$HOME/.pypirc")
if [ "$PERMS" != "600" ]; then
    echo "⚠️  Warning: ~/.pypirc permissions are $PERMS (should be 600)"
    echo "   Fix with: chmod 600 ~/.pypirc"
else
    echo "✅ ~/.pypirc permissions are correct (600)"
fi

# Check if configuration is valid
echo ""
echo "📋 Current configuration:"
echo "----------------------------------------"
cat "$HOME/.pypirc"
echo "----------------------------------------"

# Check for placeholder tokens
if grep -q "YOUR-PRODUCTION-TOKEN-HERE" "$HOME/.pypirc" || grep -q "YOUR-TEST-TOKEN-HERE" "$HOME/.pypirc"; then
    echo ""
    echo "⚠️  Warning: Placeholder tokens found in ~/.pypirc"
    echo "   Please replace with your actual API tokens:"
    echo "   - TestPyPI: https://test.pypi.org/manage/account/token/"
    echo "   - PyPI: https://pypi.org/manage/account/token/"
    exit 1
fi

echo ""
echo "✅ PyPI configuration looks good!"
echo ""
echo "🚀 You can now use:"
echo "   make release-test  # Upload to TestPyPI"
echo "   make release-prod  # Upload to PyPI"
