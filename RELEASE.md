# Release Process

## Prerequisites

Install dev dependencies (includes `build`, `twine`, `pytest`, `bandit`):

```bash
pip install -e ".[dev]"
```

Configure `~/.pypirc` for authentication:

```ini
[testpypi]
username = __token__
password = pypi-...

[pypi]
username = __token__
password = pypi-...
```

## 1. Prepare the release

1. Merge final feature or bug-fix branch into master
2. Update the version number in `pyproject.toml`
3. Update `CHANGELOG.txt` with release notes

## 2. Run pre-release checks

```bash
./scripts/pre_release.sh
```

This runs tests, bandit security scan, and checks for uncommitted changes.

## 3. Commit the release

Commit the version bump, changelog, and updated `bandit_report.txt` together:

```
Version, changelog and bandit sec run for vx.y.z
```

```bash
git add CHANGELOG.txt pyproject.toml bandit_report.txt
git commit -m "Release vx.y.z"
```

## 4. Build

```bash
./scripts/build.sh
```

Cleans `dist/` and builds wheel + sdist.

## 5. Test on Test PyPI

```bash
./scripts/publish_test.sh --verify
```

Uploads to Test PyPI and installs in a temp venv to verify.

If fixes are required:

1. Make changes and commit
2. Bump version to `x.y.z1` in `pyproject.toml` (Test PyPI doesn't allow re-uploads)
3. Rebuild and re-upload: `./scripts/build.sh && ./scripts/publish_test.sh --verify`
4. Once verified, reset version back to `x.y.z` if it was bumped

## 6. Publish to PyPI

1. Commit distributables with message `Distributables for vx.y.z`

2. Run the publish script:

   ```bash
   ./scripts/publish.sh
   ```

   This uploads to PyPI, creates a git tag `vx.y.z`, and pushes both to origin.

## 7. Create GitHub Release

Go to <https://github.com/nsmathew/myt-cli/releases/new>, select the tag `vx.y.z`,
and add the changelog contents as the release description.

## Script summary

| Script                    | What it does                                 | Automated?           |
| ------------------------- | -------------------------------------------- | -------------------- |
| `scripts/pre_release.sh`  | Tests + bandit + git status check            | Fully                |
| `scripts/build.sh`        | Clean dist/ and build                        | Fully                |
| `scripts/publish_test.sh` | Upload to Test PyPI, optional install verify | Fully                |
| `scripts/publish.sh`      | Upload to PyPI, git tag, git push            | Fully (with confirm) |
| GitHub Release            | Create release on GitHub                     | Manual               |

## What remains manual

- Writing changelog entries
- Deciding the version number
- Creating the GitHub release description
- Fixing issues found during Test PyPI verification
