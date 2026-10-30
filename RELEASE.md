# Foliage Release Runbook (GitHub Actions)

> [!NOTE]
> This file has been generated primarily by Copilot. *Caveat lector.*

## Release model

This repository uses a tag-driven release flow:

1. Prepare and merge release commit on main.
2. Push annotated tag vX.Y.Z.
3. GitHub Actions builds the macOS DMG and Windows MSI, then creates the GitHub Release
   with both installers attached. Foliage is not published to PyPI.

## Files to update for each release

- [CHANGELOG.md](CHANGELOG.md)
- [setup.cfg](setup.cfg)
- [foliage/__init__.py](foliage/__init__.py)
- [CITATION.cff](CITATION.cff)
- [codemeta.json](codemeta.json)

## Checklist

1. Sync local main:
   git checkout main
   git pull --ff-only

2. Update release metadata:
   - In [CHANGELOG.md](CHANGELOG.md), which follows
     [Keep a Changelog](https://keepachangelog.com/en/1.1.0/):
     - Rename the `## [Unreleased]` heading to `## [X.Y.Z] - YYYY-MM-DD`
     - Add a new, empty `## [Unreleased]` heading above it
     - At the bottom of the file, point the `[Unreleased]` link at
       `compare/vX.Y.Z...HEAD` and add an `[X.Y.Z]` link to
       `compare/vPREVIOUS...vX.Y.Z`
   - Set version in [setup.cfg](setup.cfg) to X.Y.Z
   - Set __version__ and metadata fields in [foliage/__init__.py](foliage/__init__.py)
   - Set version and date-released in [CITATION.cff](CITATION.cff)
   - Set version in [codemeta.json](codemeta.json)

3. Run tests locally:
   pytest -v --cov=foliage -l tests/

4. Commit release prep:
   git add CHANGELOG.md setup.cfg foliage/__init__.py CITATION.cff codemeta.json
   git commit -m "chore(release): X.Y.Z"

5. Create annotated tag:
   git tag -a vX.Y.Z -m "Release X.Y.Z"

6. Push commit and tag:
   git push origin main
   git push origin vX.Y.Z

7. Verify Actions:
   - Release from Tag workflow succeeds, including its macOS and Windows
     build jobs. If either build fails, no release is created; fix the
     problem, then delete and push the tag again.

8. Verify outputs:
   - GitHub Release exists for vX.Y.Z
   - The release has `foliage_X.Y.Z_macos_arm64.dmg` and
     `foliage_X.Y.Z_windows_x64.msi` attached

To test the installers before tagging, run the Build macOS DMG and Build
Windows MSI workflows by hand from the Actions tab. Their installers are
kept as workflow artifacts and are not attached to any release.

## DOI follow-up (if needed)

If DOI metadata changes after archival:

1. Update [README.md](README.md) DOI references.
2. Update [CITATION.cff](CITATION.cff) DOI reference.
3. Commit:
   git add README.md CITATION.cff
   git commit -m "docs: update DOI metadata after release X.Y.Z"
   git push origin main
