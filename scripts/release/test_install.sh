#!/bin/bash
# Test package installation
# Usage: ./scripts/release/test_install.sh [local|test|prod]

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

SOURCE="${1:-local}"

echo "🧪 Testing package installation..."
echo "Source: $SOURCE"
echo ""

# Create a temporary virtual environment
TEMP_VENV=$(mktemp -d)/test_env
echo "Creating temporary virtual environment: $TEMP_VENV"
python -m venv "$TEMP_VENV"
source "$TEMP_VENV/bin/activate"

echo "✅ Virtual environment created"
echo ""

# Upgrade pip to latest version for better compatibility
echo "📦 Upgrading pip..."
pip install --upgrade pip
echo ""

# Install based on source
case "$SOURCE" in
    local)
        echo "📦 Installing from local dist/..."
        cd "$PROJECT_ROOT"
        if [ ! -d "dist" ]; then
            echo "❌ Error: dist/ not found. Run build.sh first."
            exit 1
        fi
        pip install dist/*.whl
        ;;
    test)
        echo "📦 Installing from TestPyPI..."
        echo "   Package: orca-lab-test"
        echo "   Index: https://test.pypi.org/simple/"
        pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ orca-lab-test
        ;;
    prod)
        echo "📦 Installing from PyPI..."
        echo "   Package: orca-lab"
        echo "   Index: https://pypi.org/simple/"
        pip install orca-lab
        ;;
    *)
        echo "❌ Error: Invalid source. Use 'local', 'test', or 'prod'"
        deactivate
        rm -rf "$TEMP_VENV"
        exit 1
        ;;
esac

echo ""
echo "✅ Installation completed"
echo ""

# Test import
echo "🧪 Testing import..."
python -c "import orcalab; print('✅ Import successful!')"
python -c "from orcalab.ui import main_window; print('✅ UI imports successful!')"
python -c "from orcalab.asset_service import AssetService; print('✅ Asset service imports successful!')"

echo ""
echo "📋 Package information:"
python -c "import orcalab; print(f'   Package: {orcalab.__name__}')"
python -c "import orcalab; print(f'   Version: {getattr(orcalab, \"__version__\", \"unknown\")}')"
python -c "import orcalab; print(f'   Location: {orcalab.__file__}')"

echo ""
echo "✅ All tests passed!"
echo ""

# Cleanup
deactivate
rm -rf "$(dirname $TEMP_VENV)"
echo "🧹 Cleaned up temporary environment"
