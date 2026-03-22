#!/bin/bash
# Pre-release checks: run tests, bandit scan, and verify version
# Usage: ./scripts/pre_release.sh
set -e

cd "$(git rev-parse --show-toplevel)"

VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "\(.*\)"/\1/')
echo "=== Pre-release checks for v${VERSION} ==="

# 1. Run tests
echo ""
echo "--- Running tests ---"
pytest tests/ -v
echo "Tests passed."

# 2. Run bandit security scan
echo ""
echo "--- Running bandit scan ---"
out_file=bandit_report.txt
bandit --recursive --severity-level all --output $out_file --format txt src/
echo "" >> $out_file
echo "myt-cli app version for bandit run is:" >> $out_file
grep "^version = " pyproject.toml >> $out_file
echo "Bandit scan passed. Report saved to ${out_file}"

# 3. Check for uncommitted changes
echo ""
echo "--- Checking git status ---"
if [ -n "$(git status --porcelain)" ]; then
    echo "WARNING: There are uncommitted changes:"
    git status --short
else
    echo "Working tree is clean."
fi

echo ""
echo "=== Pre-release checks complete for v${VERSION} ==="
