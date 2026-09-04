# Release checklist

This document is a manual checklist for the maintainer. **Do not execute
these steps in a pull request or automated workflow.** The release workflow
(`.github/workflows/release.yml`) automates the build and publish steps, but
all preparation steps are manual.

---

## Naming

This project intentionally uses three different names. Do not confuse them:

| Name                 | Value                | Where it appears                                  |
|-----------------------|-----------------------|---------------------------------------------------|
| PyPI distribution name | `subtranslate-ai`    | `pip install`, PyPI project page, `pyproject.toml` `project.name` |
| Python import package  | `subtitle_translator` | `import subtitle_translator`, `src/subtitle_translator/` |
| CLI command             | `subtitle-translator` | Terminal invocation, `[project.scripts]` entry point |

---

## Pre-release

1. **Confirm a clean working tree.**

   ```bash
   git status
   git --no-pager log --oneline -5
   ```

2. **Choose a semantic version** following [semver.org](https://semver.org/).
   For the first stable release use `1.0.0`.

3. **Update the version.**

   This project does not use dynamic versioning, so the version must be
   updated in **two places** and kept in sync:

   - `pyproject.toml`:
     ```toml
     version = "X.Y.Z"
     ```
   - `src/subtitle_translator/version.py`:
     ```python
     __version__ = "X.Y.Z"
     ```

   `pyproject.toml`'s `version` is what `importlib.metadata.version(...)`
   reports for the installed distribution. `subtitle_translator.version.__version__`
   is what the CLI's `--version` flag reads at runtime (via installed package
   metadata) and what `subtitle_translator.__version__` exposes for
   programmatic use. The automated test
   `test_package_version_matches_importlib_metadata` in
   `tests/test_package.py` fails if these two values ever diverge, so run the
   test suite after bumping both.

4. **Move CHANGELOG entries from `[Unreleased]`** into a new section:

   ```markdown
   ## [X.Y.Z] – YYYY-MM-DD
   ```

   Add a comparison link at the bottom:
   ```
   [X.Y.Z]: https://github.com/dhofverberg/subtitle-translator/compare/vPREV...vX.Y.Z
   ```

5. **Run the full test suite and linter:**

   ```bash
   ruff check .
   pytest
   ```

6. **Build artifacts from a clean checkout:**

   ```bash
   python -m build
   ```

7. **Inspect the wheel and source distribution:**

   ```bash
   python -m twine check dist/*
   ```

   Manually inspect the wheel contents:
   ```bash
   python - <<'PY'
   from pathlib import Path; import zipfile
   w = next(Path("dist").glob("*.whl"))
   with zipfile.ZipFile(w) as z:
       for n in sorted(z.namelist()): print(n)
   PY
   ```

   Verify that prompt resources and LICENSE are present.

8. **Test installation outside the source tree.**

   Create a fresh virtual environment, install the wheel with the `all` extra,
   move to a directory outside the repository, and verify:

   ```bash
   python -m venv /tmp/st-release-verify
   /tmp/st-release-verify/bin/pip install dist/subtranslate_ai-X.Y.Z-*.whl[all]
   cd /tmp
   /tmp/st-release-verify/bin/subtitle-translator --version
   /tmp/st-release-verify/bin/subtitle-translator --help
   /tmp/st-release-verify/bin/subtitle-translator translate --help
   /tmp/st-release-verify/bin/subtitle-translator review --help
   ```

9. **Run network-free integration tests** (automated — confirm they still pass):

   ```bash
   pytest
   ```

10. **Optionally run real-provider smoke tests** using the sample files if you
    have API credentials. These are manual, paid, and excluded from CI. See
    [manual smoke-test checklist](#manual-smoke-test-checklist) below.

11. **Verify documentation and metadata.**

    - `pyproject.toml` version matches `version.py`.
    - README renders correctly (check locally, e.g. via `grip` or GitHub preview).
    - All links in README are valid.
    - CHANGELOG entry is complete with the correct date.

12. **Verify package name and ownership on PyPI.**

    - Log in to <https://pypi.org> and confirm that you own or can create the
      `subtranslate-ai` project.
    - Optionally test on TestPyPI first: <https://test.pypi.org>.

13. **Verify Trusted Publisher configuration on PyPI.**

    Go to the PyPI project → Publishing → Add a new publisher:
    - **Owner:** `dhofverberg`
    - **Repository:** `subtitle-translator`
    - **Workflow filename:** `release.yml`
    - **Environment:** `pypi`

    Confirm the matching GitHub environment (`pypi`) has required approvals
    configured in repository Settings → Environments.

---

## Release

1. **Commit the version bump and changelog update:**

   ```bash
   git add src/subtitle_translator/version.py CHANGELOG.md
   git commit -m "Release vX.Y.Z"
   ```

2. **Create an annotated or signed version tag:**

   ```bash
   git tag -a "vX.Y.Z" -m "Release vX.Y.Z"
   ```

3. **Push the commit and tag to GitHub:**

   ```bash
   git push origin main
   git push origin "vX.Y.Z"
   ```

4. **Create a GitHub release** for the tag. Select "Publish release" (not
   draft). This triggers the release workflow.

5. **Monitor the release workflow** in GitHub Actions. The build job runs tests
   and builds the distribution; the publish job uploads it to PyPI after
   approval.

6. **Verify the PyPI page** at <https://pypi.org/project/subtranslate-ai/>.
   Confirm the version, description, and metadata are correct.

7. **Install the published version into a clean environment:**

   ```bash
   python -m venv /tmp/st-published
   /tmp/st-published/bin/pip install "subtranslate-ai[all]==X.Y.Z"
   /tmp/st-published/bin/subtitle-translator --version
   ```

8. **Verify uploaded artifact hashes** against the local build artifacts if
   desired.

---

## Post-release

1. **Restore a fresh `[Unreleased]` section** in CHANGELOG.md.

2. **Update the comparison link** for `[Unreleased]` to compare from `vX.Y.Z`:

   ```
   [Unreleased]: https://github.com/dhofverberg/subtitle-translator/compare/vX.Y.Z...HEAD
   ```

3. **Announce the release** where appropriate (GitHub Discussions, project
   README badge, etc.).

4. **Monitor issues** for unexpected regressions.

5. **Document rollback criteria.** If the release contains a critical bug,
   consider yanking the release on PyPI:
   ```
   pip install twine
   twine yank subtranslate-ai X.Y.Z
   ```

---

## Manual smoke-test checklist

These tests are manual, require real provider API credentials, and incur charges.
They are **not run in CI**.

### OpenAI

```bash
export OPENAI_API_KEY="..."

# Basic translation
subtitle-translator translate samples/openai_smoke_test.srt \
  --source-language English --target-language Swedish

# Glossary
subtitle-translator translate samples/openai_glossary_test.srt \
  --source-language English --target-language Swedish \
  --glossary samples/glossary.en-sv.json

# Rolling context
subtitle-translator translate samples/context_smoke_test.srt \
  --source-language English --target-language Swedish \
  --context-size 10

# Translation + consistency report
subtitle-translator translate samples/consistency_smoke_test.srt \
  --source-language English --target-language Swedish \
  --consistency-report /tmp/test.consistency.md

# Standalone review
subtitle-translator review \
  samples/consistency_smoke_test.srt \
  /tmp/consistency_smoke_test.translated.srt \
  --source-language English --target-language Swedish \
  --consistency-report /tmp/review.consistency.md
```

### Gemini

```bash
export GEMINI_API_KEY="..."

# Basic translation
subtitle-translator translate samples/openai_smoke_test.srt \
  --provider gemini \
  --source-language English --target-language Swedish

# Glossary
subtitle-translator translate samples/openai_glossary_test.srt \
  --provider gemini \
  --source-language English --target-language Swedish \
  --glossary samples/glossary.en-sv.json

# Translation + consistency report
subtitle-translator translate samples/consistency_smoke_test.srt \
  --provider gemini \
  --source-language English --target-language Swedish \
  --consistency-report /tmp/gemini.consistency.md

# Standalone review
subtitle-translator review \
  samples/consistency_smoke_test.srt \
  /tmp/consistency_smoke_test.gemini.translated.srt \
  --provider gemini \
  --source-language English --target-language Swedish \
  --consistency-report /tmp/gemini.review.consistency.md
```

### Cross-provider

```bash
export OPENAI_API_KEY="..."
export GEMINI_API_KEY="..."

# OpenAI translation, Gemini review
subtitle-translator translate samples/consistency_smoke_test.srt \
  --provider openai --review-provider gemini \
  --source-language English --target-language Swedish \
  --consistency-report /tmp/cross1.consistency.md

# Gemini translation, OpenAI review
subtitle-translator translate samples/consistency_smoke_test.srt \
  --provider gemini --review-provider openai \
  --source-language English --target-language Swedish \
  --consistency-report /tmp/cross2.consistency.md
```

### Safety checks

```bash
# Reject existing output
subtitle-translator translate samples/openai_smoke_test.srt \
  --output /tmp/existing.srt  # run once to create it, then run again — must fail

# Reject existing report
subtitle-translator translate samples/openai_smoke_test.srt \
  --output /tmp/new.srt \
  --consistency-report /tmp/existing.consistency.md  # must fail if report exists

# Standalone review rejects mismatched pair
subtitle-translator review \
  samples/openai_smoke_test.srt \
  samples/consistency_smoke_test.srt \
  --source-language English --target-language Swedish \
  --consistency-report /tmp/mismatch.consistency.md  # must fail before API call
```

---

## Release blockers (must resolve before v1.0.0)

- **Private vulnerability reporting:** Enable GitHub private vulnerability
  reporting in repository Settings → Security → Private vulnerability reporting
  before the first public release. Until it is enabled, `SECURITY.md` lacks a
  functional private reporting channel.
- **PyPI Trusted Publisher:** Configure the Trusted Publisher on PyPI as
  described in step 13 of the pre-release checklist above.
- **PyPI project name:** Verify that `subtranslate-ai` is available or
  already owned on PyPI before publishing.
- **GitHub environment `pypi`:** Create the protected `pypi` environment in
  repository Settings → Environments and configure required reviewers before
  running the release workflow for the first time.
