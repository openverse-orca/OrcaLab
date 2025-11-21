#!/bin/bash
# Build distribution packages
# Usage: ./scripts/release/build.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"

cd "$PROJECT_ROOT"

echo "📦 Building distribution packages..."

# Check if build tool is installed
if ! python -c "import build" &> /dev/null; then
    echo "⚠️  'build' not found. Installing..."
    pip install build
fi

# Build the package (official name)
echo "Building with Python: $(which python)"
python -m build

echo ""
echo "📦 Building TestPyPI package (orca-lab)..."

# Prepare temp workspace for test package build
TEST_OUTDIR="$PROJECT_ROOT/dist-test"
TMP_DIR=$(mktemp -d -t orcalab-testbuild-XXXX)

# Copy source excluding build artifacts and VCS files
rsync -a \
    --exclude '.git' \
    --exclude '.gitignore' \
    --exclude 'dist' \
    --exclude 'dist-test' \
    --exclude 'build' \
    --exclude '*.egg-info' \
    --exclude '.idea' \
    --exclude '.vscode' \
    --exclude '.history' \
    "$PROJECT_ROOT/" "$TMP_DIR/"

# Keep the same package name (orca-lab) for TestPyPI build
# This allows for complete installation testing with the same package name

# Replace production URLs with test URLs in config file
CONFIG_FILE="$TMP_DIR/orcalab/orca.config.toml"
if [ -f "$CONFIG_FILE" ]; then
    echo "Replacing URLs for TestPyPI environment..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' 's|https://simassets.orca3d.cn/api|http://47.100.47.219/api|g' "$CONFIG_FILE"
        sed -i '' 's|https://simassets.orca3d.cn/|http://47.100.47.219/|g' "$CONFIG_FILE"
    else
        # Linux
        sed -i 's|https://simassets.orca3d.cn/api|http://47.100.47.219/api|g' "$CONFIG_FILE"
        sed -i 's|https://simassets.orca3d.cn/|http://47.100.47.219/|g' "$CONFIG_FILE"
    fi
fi

# Build the test package with same name
mkdir -p "$TEST_OUTDIR"
(cd "$TMP_DIR" && python -m build --outdir "$TEST_OUTDIR")

# Cleanup temp directory
rm -rf "$TMP_DIR"

echo ""
echo "✅ Build completed!"
echo ""
echo "Generated files (dist/):"
ls -lh dist/ || true
echo ""
echo "Generated files for TestPyPI (dist-test/):"
ls -lh "$TEST_OUTDIR" || true
