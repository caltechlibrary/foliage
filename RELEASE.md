# Foliage Release Runbook (GitHub Actions + Trusted Publishing)

> [!NOTE]
> This file has been generated primarily by Copilot. *Caveat lector.*

## Release model

This repository uses a tag-driven release flow:

1. Prepare and merge release commit on main.
2. Push annotated tag vX.Y.Z.
3. GitHub Actions creates GitHub Release, builds platform artifacts, and publishes to PyPI.

## Files to update for each release

- [CHANGES.md](CHANGES.md)
- [setup.cfg](setup.cfg)
- [foliage/__init__.py](foliage/__init__.py)
- [CITATION.cff](CITATION.cff)
- [codemeta.json](codemeta.json)

## Checklist

1. Sync local main:
   git checkout main
   git pull --ff-only

2. Update release metadata:
   - Add a new top entry in [CHANGES.md](CHANGES.md) using:
     `## ★ Version X.Y.Z (YYYY-MM-DD) ★`
   - Set version in [setup.cfg](setup.cfg) to X.Y.Z
   - Set __version__ and metadata fields in [foliage/__init__.py](foliage/__init__.py)
   - Set version and date-released in [CITATION.cff](CITATION.cff)
   - Set version in [codemeta.json](codemeta.json)

3. Run tests locally:
   pytest -v --cov=foliage -l tests/

4. Commit release prep:
   git add CHANGES.md setup.cfg foliage/__init__.py CITATION.cff codemeta.json
   git commit -m "chore(release): X.Y.Z"

5. Create annotated tag:
   git tag -a vX.Y.Z -m "Release X.Y.Z"

6. Push commit and tag:
   git push origin main
   git push origin vX.Y.Z

7. Verify Actions:
   - Release from Tag workflow succeeds.
   - Build macOS DMG workflow succeeds.
   - Build Windows MSI workflow succeeds.
   - Publish to PyPI workflow succeeds.

8. Verify outputs:
   - GitHub Release exists for vX.Y.Z
   - PyPI shows version X.Y.Z
   - Artifact workflows produced expected DMG and MSI artifacts

## DOI follow-up (if needed)

If DOI metadata changes after archival:

1. Update [README.md](README.md) DOI references.
2. Update [CITATION.cff](CITATION.cff) DOI reference.
3. Commit:
   git add README.md CITATION.cff
   git commit -m "docs: update DOI metadata after release X.Y.Z"
   git push origin main
