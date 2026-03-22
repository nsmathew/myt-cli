#!/bin/bash
# Build distribution artifacts
# Usage: ./scripts/build.sh
set -e

cd "$(git rev-parse --show-toplevel)"

VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "=== Building myt-cli v${VERSION} ==="

# Clean previous builds
echo "Cleaning dist/..."
rm -rf dist/

# Build
echo "Building..."
python -m build

echo ""
echo "=== Build complete ==="
echo "Artifacts:"
ls -la dist/
