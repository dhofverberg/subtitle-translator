# Contributing to Subtitle Translator

Thank you for your interest in contributing! This document covers development
setup, conventions, and the process for reporting bugs and proposing changes.

## Supported Python versions

Python **3.11, 3.12, and 3.13** are supported and tested in CI.

## Setting up the development environment

1. Clone the repository:

   ```bash
   git clone https://github.com/dhofverberg/subtitle-translator.git
   cd subtitle-translator
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   # macOS / Linux
   source .venv/bin/activate
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   ```

3. Install all provider extras and development tools:

   ```bash
   python -m pip install -e ".[all,dev]"
   ```

   If you only need one provider:

   ```bash
   python -m pip install -e ".[openai,dev]"
   python -m pip install -e ".[gemini,dev]"
   ```

## Running the tests

```bash
pytest
```

Run a specific file:

```bash
pytest tests/test_cli.py
```

All automated tests must pass without making real API calls. Use fake/stub
clients (see `tests/` for examples) whenever provider interactions are tested.

## Running the linter

```bash
ruff check .
```

Ruff is configured in `pyproject.toml`. Fix reported issues before opening a
pull request.

## Building the wheel and source distribution

```bash
python -m build
```

Inspect the distribution contents:

```bash
python -m twine check dist/*
```

## Verifying the installed wheel

Build the wheel, then install it into a clean environment outside the source
tree and run the CLI:

```bash
# macOS / Linux
python -m venv /tmp/st-verify
wheel_path="$(python -c 'from pathlib import Path; print(next(Path(\"dist\").glob(\"subtitle_translator-*.whl\")).resolve())')"
wheel_uri="$(python -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).as_uri())' "$wheel_path")"
/tmp/st-verify/bin/pip install "subtitle-translator[all] @ $wheel_uri"
/tmp/st-verify/bin/subtitle-translator --version
/tmp/st-verify/bin/subtitle-translator --help
/tmp/st-verify/bin/subtitle-translator translate --help
/tmp/st-verify/bin/subtitle-translator review --help
```

```powershell
# Windows PowerShell
python -m venv "$env:TEMP\st-verify"
$wheelPath = (Get-ChildItem dist\subtitle_translator-*.whl | Select-Object -First 1).FullName
$wheelUri = python -c "from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().as_uri())" "$wheelPath"
& "$env:TEMP\st-verify\Scripts\pip.exe" install "subtitle-translator[all] @ $wheelUri"
& "$env:TEMP\st-verify\Scripts\subtitle-translator.exe" --version
& "$env:TEMP\st-verify\Scripts\subtitle-translator.exe" --help
& "$env:TEMP\st-verify\Scripts\subtitle-translator.exe" translate --help
& "$env:TEMP\st-verify\Scripts\subtitle-translator.exe" review --help
```
## Architecture overview

See [`docs/architecture.md`](docs/architecture.md) for a concise description of
the provider-neutral core, translation and review adapters, file boundaries, and
safety invariants.

## Adding a provider integration

1. Create a new module under `src/subtitle_translator/providers/`.
2. Implement the `TranslationProvider` interface from `providers/base.py` for
   translation, or `ConsistencyReviewer` from `consistency.py` for review.
3. Register the provider in `providers/factory.py`.
4. Add the provider SDK as an optional extra in `pyproject.toml`.
5. Write tests using a fake/stub client — do not make real API calls in
   automated tests.
6. Do not import the provider SDK at module load time; gate imports behind the
   point where the provider is first used.

## Keeping the core provider-neutral

The `models.py`, `batch.py`, `srt.py`, `glossary.py`, `consistency.py`, and
`prompts.py` modules must not import any provider SDK. Verify this with the
existing provider-neutral import tests.

## Writing tests with fake clients

Provider tests use fake/stub implementations of `TranslationProvider` and
`ConsistencyReviewer`. See `tests/test_cli_integration.py` for examples. Never
use `monkeypatch` to replace transport-level calls when a higher-level interface
can be faked instead.

## Adding changelog entries

Add a one-line summary under the appropriate heading in the `[Unreleased]`
section of `CHANGELOG.md` for every user-visible change. See the format in that
file. Do not edit released sections.

## Writing pull requests

- Keep the scope focused: one logical change per PR.
- Include or update tests for every behavioral change.
- Ensure `ruff check .` passes.
- Ensure `pytest` passes.
- Ensure `python -m build` and `python -m twine check dist/*` pass.
- Do not commit API keys, provider credentials, or personal environment details.
- Do not commit copyrighted subtitle files. Use original synthetic content in
  samples and test fixtures.
- Update documentation when behavior visible to users changes.
- Add a changelog entry for every user-visible change.

## Documentation-only changes

Documentation-only changes (README, docs/, CHANGELOG, etc.) do not require
new tests, but must not break existing ones. Ruff should still pass.

## Reporting bugs and proposing features

Use the GitHub issue tracker:
<https://github.com/dhofverberg/subtitle-translator/issues>

See the issue templates for the information to include. Never include real API
keys or private subtitle content in issues.

For security vulnerabilities, see [SECURITY.md](SECURITY.md).
