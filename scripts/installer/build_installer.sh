#!/usr/bin/env bash
# Build Windows NSIS installer for OrcaLab
# Prerequisites: sudo apt-get install nsis
# The installer wraps orcalab.bat + icon, creates desktop shortcut.
# No code signing required — .bat scripts bypass Device Guard.

set -e

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist"

cd "$SCRIPT_DIR"

cleanup() {
    [ -f "$SCRIPT_DIR/orcalab.bat.bak" ] && mv "$SCRIPT_DIR/orcalab.bat.bak" "$SCRIPT_DIR/orcalab.bat"
    [ -f "$SCRIPT_DIR/setup.nsi.bak" ]   && mv "$SCRIPT_DIR/setup.nsi.bak"   "$SCRIPT_DIR/setup.nsi"
}
trap cleanup EXIT

echo "🔧 Building OrcaLab Windows Installer..."
echo ""

# Check makensis
if ! command -v makensis > /dev/null 2>&1; then
    echo "Error: makensis not found. Install with: sudo apt-get install nsis"
    exit 1
fi

# Generate .ico from PNG
ICO_PATH="$PROJECT_ROOT/orcalab/assets/icons/orcalab_logo.ico"
PNG_PATH="$PROJECT_ROOT/orcalab/assets/icons/orcalab_logo.png"

if [ ! -f "$ICO_PATH" ] || [ "$PNG_PATH" -nt "$ICO_PATH" ]; then
    echo "Generating icon: $ICO_PATH"
    python3 -c "
from PIL import Image
img = Image.open('$PNG_PATH')
img.save('$ICO_PATH', format='ICO', sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
"
    echo "  ✓ Icon generated"
fi

# Extract version from pyproject.toml
VERSION=$(grep '^version' "$PROJECT_ROOT/pyproject.toml" | head -1 | sed 's/.*"\(.*\)".*/\1/')
echo "Version: $VERSION"

# Inject version into orcalab.bat
BAT_FILE="$SCRIPT_DIR/orcalab.bat"
cp "$BAT_FILE" "$BAT_FILE.bak"
sed -i "s/__ORCALAB_VERSION__/$VERSION/g" "$BAT_FILE"

# Inject pip extra index URLs based on pip_source
PIP_SOURCE="${1:-test}"
if [ "$PIP_SOURCE" = "test" ]; then
    EXTRA_INDEX_URLS="--extra-index-url https://pypi.org/simple --extra-index-url https://test.pypi.org/simple"
else
    EXTRA_INDEX_URLS=""
fi
sed -i "s|__PIP_EXTRA_INDEX_URLS__|$EXTRA_INDEX_URLS|g" "$BAT_FILE"

# Inject version into setup.nsi
NSI_FILE="$SCRIPT_DIR/setup.nsi"
cp "$NSI_FILE" "$NSI_FILE.bak"
sed -i "s/!define PRODUCT_VERSION \".*\"/!define PRODUCT_VERSION \"$VERSION\"/g" "$NSI_FILE"
VI_VERSION=$(echo "$VERSION" | awk -F. '{if (NF==3) print $0".0"; else print $0}')
sed -i "s/VIProductVersion \".*\"/VIProductVersion \"$VI_VERSION\"/g" "$NSI_FILE"

# Build installer
mkdir -p "$DIST_DIR"
echo ""
echo "Building NSIS installer..."
makensis setup.nsi

# Restore orcalab.bat
mv "$BAT_FILE.bak" "$BAT_FILE"

# Restore setup.nsi
mv "$NSI_FILE.bak" "$NSI_FILE"

echo ""
echo "✅ Installer built: $DIST_DIR/OrcaLab-*-Setup.exe"
ls -lh "$DIST_DIR"/OrcaLab-*-Setup.exe
