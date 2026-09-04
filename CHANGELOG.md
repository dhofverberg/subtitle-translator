# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

> **Maintainer note:** When releasing a new version, move the entries below from
> `[Unreleased]` into a new `## [x.y.z] – YYYY-MM-DD` section. Add a link at the
> bottom of the file comparing the new tag with the previous one.

---

## [Unreleased]

### Changed

- **PyPI distribution name** – The package will be published to PyPI as
  `subtranslate-ai`. The Python import package (`subtitle_translator`) and the
  CLI command (`subtitle-translator`) are unchanged.

### Added

- **Core translation engine** – SRT subtitle translation using LLM providers.
  Batch translation preserves subtitle indices, timestamps, formatting, and
  line breaks.
- **OpenAI provider** – Translation and consistency review via the OpenAI API.
  Configured with `OPENAI_API_KEY` and optional `OPENAI_MODEL`.
- **Gemini provider** – Translation and consistency review via the Google Gemini
  API. Configured with `GEMINI_API_KEY` and optional `GEMINI_MODEL`.
- **Provider selection** – `--provider openai|gemini` (default: `openai`).
  Provider names are case-insensitive.
- **Rolling context** – Each translation batch optionally receives recently
  accepted translations as read-only guidance, configurable with
  `--context-size` (default: 10, disable with 0).
- **Glossary support** – `--glossary PATH` accepts a UTF-8 JSON file of
  approved source-to-target terminology. Glossary languages must match the CLI
  source and target languages.
- **Optional consistency report** – `--consistency-report PATH` triggers a
  separate advisory review after translation, writing a Markdown findings
  report. The review never modifies the translated SRT.
- **Cross-provider review** – `--review-provider` selects an independent
  provider for consistency review. `--review-model` overrides the review model
  independently of `--model`.
- **Standalone review command** – `subtitle-translator review SOURCE TRANSLATED`
  generates a consistency report from existing SRT files without re-translating.
  Both files must have matching subtitle indices and timestamps.
- **Legacy CLI compatibility** – Existing commands using positional SRT path
  arguments continue to work without a `translate` subcommand.
- **Automatic retry and resume** – Failed or interrupted translations can be
  retried; batch progress is preserved across runs.
- **Output-file safety** – Existing output files and report files are never
  overwritten by default. Writes use atomic replacement where supported.
- **`--version` flag** – Reports the installed package version without requiring
  provider SDKs.
- **Optional dependency extras** – `openai`, `gemini`, `all`, and `dev` extras
  allow selective installation of provider SDKs.
- **Packaging and distribution** – Wheel and source distribution build correctly
  with all prompt resources and the LICENSE file included.
- **CI** – GitHub Actions workflow running tests, Ruff, build, distribution
  verification, and installed-wheel verification across Python 3.11–3.13.
- **Release automation** – GitHub Actions release workflow using PyPI Trusted
  Publishing (OIDC); no stored API token required.
- **Documentation** – README, CONTRIBUTING, SECURITY, CHANGELOG, architecture
  overview, usage guide, release checklist, and sample files.

### Changed (continued)

- Improved help text and error messages to align with user-visible CLI behavior.
- Tightened provider-neutral import isolation: provider SDKs are not imported
  unless the relevant extra is installed and the provider is selected.

### Security

- Provider SDKs are optional extras; a user selecting a provider without its
  SDK receives a clear error rather than an import-time failure at startup.
- Subtitle source files are never modified by translation or review operations.
- Consistency reports do not overwrite existing files.

[Unreleased]: https://github.com/dhofverberg/subtitle-translator/compare/HEAD...HEAD
