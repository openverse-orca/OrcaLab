#!/bin/bash
# Setup .pypirc configuration for PyPI uploads
# Usage: ./scripts/release/setup_pypirc.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

echo "🔧 Setting up PyPI configuration..."

# Check if .pypirc already exists
if [ -f "$HOME/.pypirc" ]; then
    echo "⚠️  ~/.pypirc already exists."
    echo ""
    echo "Current content:"
    echo "----------------------------------------"
    cat "$HOME/.pypirc"
    echo "----------------------------------------"
    echo ""
    read -p "Do you want to overwrite it? (yes/no): " -r
    echo
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "❌ Setup cancelled."
        exit 0
    fi
fi

# Copy example file to home directory
echo "📋 Copying .pypirc.example to ~/.pypirc..."
cp "$SCRIPT_DIR/.pypirc.example" "$HOME/.pypirc"

# Set proper permissions
echo "🔒 Setting proper permissions..."
chmod 600 "$HOME/.pypirc"

echo ""
echo "✅ .pypirc configuration file created!"
echo ""
echo "📝 Next steps:"
echo "   1. Edit ~/.pypirc and add your API tokens:"
echo "      vim ~/.pypirc"
echo ""
echo "   2. Get your tokens at:"
echo "      - TestPyPI: https://test.pypi.org/manage/account/token/"
echo "      - PyPI: https://pypi.org/manage/account/token/"
echo ""
echo "   3. Replace the placeholder tokens:"
echo "      - pypi-YOUR-PRODUCTION-TOKEN-HERE"
echo "      - pypi-YOUR-TEST-TOKEN-HERE"
echo ""
echo "   4. Test your configuration:"
echo "      make release-test  # Test with TestPyPI"
echo "      make release-prod  # Release to PyPI"
echo ""
echo "🔍 Current configuration:"
echo "----------------------------------------"
cat "$HOME/.pypirc"
echo "----------------------------------------"
