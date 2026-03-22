#!/bin/bash
# Upload to Test PyPI and optionally verify install
# Usage: ./scripts/publish_test.sh [--verify]
set -e

cd "$(git rev-parse --show-toplevel)"

VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "=== Uploading myt-cli v${VERSION} to Test PyPI ==="

if [ ! -d "dist" ] || [ -z "$(ls dist/ 2>/dev/null)" ]; then
    echo "ERROR: No dist/ artifacts found. Run ./scripts/build.sh first."
    exit 1
fi

# Upload to Test PyPI
python3 -m twine upload --repository testpypi dist/*

echo "Upload complete."

# Optionally verify by installing in a temp venv
if [ "$1" = "--verify" ]; then
    echo ""
    echo "--- Verifying install from Test PyPI ---"
    TMPDIR=$(mktemp -d)
    python3 -m venv "${TMPDIR}/venv"
    source "${TMPDIR}/venv/bin/activate"
    pip install -i https://test.pypi.org/simple/ \
        --extra-index-url https://pypi.org/simple/ \
        "myt-cli==${VERSION}"
    echo ""
    echo "Installed version:"
    myt version
    deactivate
    rm -rf "${TMPDIR}"
    echo "Verification complete."
fi
