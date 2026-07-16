#!/usr/bin/env bash
# Build Windows NSIS installer for OrcaLab
# Prerequisites: sudo apt-get install nsis
# Builds separate Chinese and English installers with fixed installer and app
# languages. The installed shortcut remains language-neutral after setup.
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
            echo "Builds both zh-CN and en-US installers."
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
BUILD_ROOT="$(mktemp -d "$SCRIPT_DIR/.installer-build.XXXXXX")"
cleanup_staging() {
    rm -rf "$BUILD_ROOT"
}
trap cleanup_staging EXIT

PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"

# Inject pip extra index URLs based on pip_source.
# Keep Tsinghua as the primary index because orca-gym releases are expected
# there first; PyPI remains a fallback for other public dependencies.
if [ "$PIP_SOURCE" = "test" ]; then
    EXTRA_INDEX_URLS="--extra-index-url https://pypi.org/simple --extra-index-url https://test.pypi.org/simple"
else
    EXTRA_INDEX_URLS="--extra-index-url https://pypi.org/simple"
fi

VI_VERSION=$(echo "$VERSION" | awk -F. '{if (NF==3) print $0".0"; else print $0}')

mkdir -p "$DIST_DIR"

build_variant() {
    local language="$1"
    local suffix="$2"
    local build_dir="$BUILD_ROOT/$language"
    local bat_file="$build_dir/orcalab.bat"
    local vbs_file="$build_dir/orcalab.vbs"

    mkdir -p "$build_dir"
    cp "$SCRIPT_DIR/orcalab.bat" "$bat_file"
    cp "$SCRIPT_DIR/orcalab.vbs" "$vbs_file"

    sed -i "s/__ORCALAB_VERSION__/$VERSION/g" "$bat_file"
    sed -i "s/__INSTALLER_LANGUAGE__/$language/g" "$bat_file" "$vbs_file"
    sed -i "s|__PIP_INDEX_URL__|$PIP_INDEX_URL|g" "$bat_file"
    sed -i "s|__PIP_EXTRA_INDEX_URLS__|$EXTRA_INDEX_URLS|g" "$bat_file"

    # Windows cmd.exe requires CRLF; VBScript is also more reliable with it.
    sed -i 's/\r$//;s/$/\r/' "$bat_file" "$vbs_file"

    local nsis_args=(
        "-DPRODUCT_VERSION=$VERSION"
        "-DVI_PRODUCT_VERSION=$VI_VERSION"
        "-DINSTALLER_SOURCE_DIR=$(basename "$BUILD_ROOT")/$language"
    )
    if [ "$language" = "en_US" ]; then
        nsis_args+=("-DORCALAB_ENGLISH")
    fi

    echo "Building $language installer..."
    makensis "${nsis_args[@]}" setup.nsi
    echo "✅ Installer built: $DIST_DIR/OrcaLab-$VERSION-Setup-$suffix.exe"
    ls -lh "$DIST_DIR/OrcaLab-$VERSION-Setup-$suffix.exe"
}

echo ""
build_variant "zh_CN" "zh-CN"
build_variant "en_US" "en-US"
