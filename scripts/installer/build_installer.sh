#!/usr/bin/env bash
# Build Windows NSIS installer for OrcaLab
# Prerequisites: sudo apt-get install nsis
# The installer wraps orcalab.bat + icon, creates desktop shortcut, and selects
# its UI language from the Windows system language at runtime.
# No code signing required — .bat scripts bypass Device Guard.

set -e

SCRIPT_DIR="$(CDPATH="" cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist"

cd "$SCRIPT_DIR"

echo "🔧 Building OrcaLab Windows Installer..."
echo ""

PIP_SOURCE="test"

while [ $# -gt 0 ]; do
    case "$1" in
        --pip-source)
            PIP_SOURCE="${2:-}"
            shift 2
            ;;
        --pip-source=*)
            PIP_SOURCE="${1#*=}"
            shift
            ;;
        test|prod)
            PIP_SOURCE="$1"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--pip-source test|prod]"
            echo "Legacy usage still works: $0 test|prod"
            exit 0
            ;;
        *)
            echo "Error: unknown argument '$1'"
            echo "Usage: $0 [--pip-source test|prod]"
            exit 1
            ;;
    esac
done

case "$PIP_SOURCE" in
    test|prod)
        ;;
    *)
        echo "Error: unsupported pip source '$PIP_SOURCE' (expected test or prod)"
        exit 1
        ;;
esac

echo "Pip source: $PIP_SOURCE"

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

# Prepare staged installer sources so parallel builds never mutate templates.
BUILD_DIR="$(mktemp -d "$SCRIPT_DIR/.installer-build.XXXXXX")"
cleanup_staging() {
    rm -rf "$BUILD_DIR"
}
trap cleanup_staging EXIT

BAT_FILE="$BUILD_DIR/orcalab.bat"
VBS_FILE="$BUILD_DIR/orcalab.vbs"
cp "$SCRIPT_DIR/orcalab.bat" "$BAT_FILE"
cp "$SCRIPT_DIR/orcalab.vbs" "$VBS_FILE"

# Inject version into staged orcalab.bat
sed -i "s/__ORCALAB_VERSION__/$VERSION/g" "$BAT_FILE"

PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"
sed -i "s|__PIP_INDEX_URL__|$PIP_INDEX_URL|g" "$BAT_FILE"

# Inject pip extra index URLs based on pip_source.
# Keep Tsinghua as the primary index because orca-gym releases are expected
# there first; PyPI remains a fallback for other public dependencies.
if [ "$PIP_SOURCE" = "test" ]; then
    EXTRA_INDEX_URLS="--extra-index-url https://pypi.org/simple --extra-index-url https://test.pypi.org/simple"
else
    EXTRA_INDEX_URLS="--extra-index-url https://pypi.org/simple"
fi
sed -i "s|__PIP_EXTRA_INDEX_URLS__|$EXTRA_INDEX_URLS|g" "$BAT_FILE"

VI_VERSION=$(echo "$VERSION" | awk -F. '{if (NF==3) print $0".0"; else print $0}')

# Convert .bat and .vbs to CRLF line endings
# Windows cmd.exe requires CRLF for batch files; VBScript also works better with CRLF
echo "Converting line endings to CRLF..."
sed -i 's/\r$//;s/$/\r/' "$BAT_FILE"
sed -i 's/\r$//;s/$/\r/' "$VBS_FILE"
echo "  ✓ Line endings converted"

# Build installer
mkdir -p "$DIST_DIR"
echo ""
echo "Building NSIS installer..."
NSIS_ARGS=(
    "-DPRODUCT_VERSION=$VERSION"
    "-DVI_PRODUCT_VERSION=$VI_VERSION"
    "-DINSTALLER_SOURCE_DIR=$(basename "$BUILD_DIR")"
)
makensis "${NSIS_ARGS[@]}" setup.nsi

echo ""
echo "✅ Installer built: $DIST_DIR/OrcaLab-$VERSION-Setup.exe"
ls -lh "$DIST_DIR"/OrcaLab-"$VERSION"-Setup.exe
