#!/bin/bash
# Upload to PyPI, tag, and push
# Usage: ./scripts/publish.sh
set -e

cd "$(git rev-parse --show-toplevel)"

VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "=== Publishing myt-cli v${VERSION} to PyPI ==="

if [ ! -d "dist" ] || [ -z "$(ls dist/ 2>/dev/null)" ]; then
    echo "ERROR: No dist/ artifacts found. Run ./scripts/build.sh first."
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Uncommitted changes exist. Commit first."
    exit 1
fi

# Confirm
read -p "Upload v${VERSION} to PyPI and tag? [y/N] " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

# Upload to PyPI
python3 -m twine upload dist/*

# Tag
git tag -a "v${VERSION}" -m "Release tag for v${VERSION}"

# Push
git push origin
git push origin "v${VERSION}"

echo ""
echo "=== Published v${VERSION} ==="
echo "Next: Create a GitHub release at https://github.com/nsmathew/myt-cli/releases/new?tag=v${VERSION}"
