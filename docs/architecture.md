# Architecture

This document describes the internal structure of Subtitle Translator.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  CLI (cli.py)                                                   │
│  subtitle-translator translate / review / --version             │
│  Legacy positional-argument compatibility                        │
└────────────────┬──────────────────────────┬────────────────────┘
                 │                          │
                 ▼                          ▼
┌────────────────────────────┐  ┌──────────────────────────────────┐
│  Translation application   │  │  Review application              │
│  (app.py)                  │  │  (app.py: review_srt_files)      │
│                            │  │                                  │
│  ┌──────────────────────┐  │  │  ┌────────────────────────────┐ │
│  │ SubtitleTranslation  │  │  │  │ ConsistencyReviewService   │ │
│  │ Service              │  │  │  │                            │ │
│  │ (subtitle_translation│  │  │  │ Chunks translated pairs,   │ │
│  │  .py)                │  │  │  │ calls reviewer, renders    │ │
│  └──────────┬───────────┘  │  │  │ Markdown report            │ │
│             │              │  │  └──────────────┬─────────────┘ │
│  ┌──────────▼───────────┐  │  └─────────────────┼───────────────┘
│  │ Batch translation    │  │                    │
│  │ (batch.py)           │  │                    │
│  │ Splits subtitles,    │  │                    │
│  │ manages rolling      │  │                    │
│  │ context window       │  │                    │
│  └──────────┬───────────┘  │
└─────────────┼──────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────┐     ┌────────────────────────────────┐
│  Translation provider   │     │  Consistency reviewer          │
│  interface (base.py)    │     │  interface (consistency.py)    │
│                         │     │                                │
│  ┌───────────────────┐  │     │  ┌────────────────────────┐   │
│  │ OpenAIProvider    │  │     │  │OpenAIConsistency       │   │
│  │ (openai_provider  │  │     │  │Reviewer                │   │
│  │  .py)             │  │     │  │(openai_consistency_    │   │
│  └───────────────────┘  │     │  │ reviewer.py)           │   │
│  ┌───────────────────┐  │     │  └────────────────────────┘   │
│  │ GeminiProvider    │  │     │  ┌────────────────────────┐   │
│  │ (gemini_provider  │  │     │  │GeminiConsistency       │   │
│  │  .py)             │  │     │  │Reviewer                │   │
│  └───────────────────┘  │     │  │(gemini_consistency_    │   │
└─────────────────────────┘     │  │ reviewer.py)           │   │
                                │  └────────────────────────┘   │
                                └────────────────────────────────┘
```

## Provider-neutral services and models

The following modules have **no dependency on any provider SDK**:

| Module | Responsibility |
|---|---|
| `models.py` | `Subtitle` and `SubtitleFile` value objects |
| `batch.py` | Subtitle splitting, batching, rolling context assembly |
| `srt.py` | SRT file loading and atomic writing |
| `glossary.py` | Glossary JSON loading and validation |
| `prompts.py` | Prompt template loading from packaged resources |
| `consistency.py` | `ConsistencyReviewer` protocol, report model |
| `consistency_report.py` | Markdown report rendering and atomic writing |
| `consistency_review.py` | Review chunking and orchestration |
| `subtitle_translation.py` | Translation orchestration (batch loop, retry) |
| `app.py` | Top-level application logic (translate, review) |
| `config.py` | Configuration loading from environment variables |
| `persistence.py` | Temporary file and atomic rename utilities |

## Translation-provider adapters

`providers/openai_provider.py` and `providers/gemini_provider.py` each
implement the `TranslationProvider` interface (`providers/base.py`). Provider
SDKs are imported lazily inside these modules and are never loaded unless the
provider is actually selected and its extra is installed.

## Consistency-reviewer adapters

`providers/openai_consistency_reviewer.py` and
`providers/gemini_consistency_reviewer.py` each implement the
`ConsistencyReviewer` protocol. The same lazy-import rule applies.

## Provider factory

`providers/factory.py` constructs providers and reviewers by name, handles lazy
imports, and raises `TranslationProviderConfigurationError` with a focused
installation hint when a required SDK is missing.

## File and report boundaries

```
Input SRT ──► (read-only) ──► Translation service ──► Output SRT (new file)
                                       │
                                       ▼
                              Consistency review ──► Report file (new file)
```

- The input SRT is never modified.
- Output SRT is written atomically to a new path (default:
  `<stem>.translated.srt`).
- The consistency report is written atomically to a new path.
- If review fails after translation, the translated SRT is preserved.
- Existing output files are rejected before any API calls are made.

## Glossary and context flow

```
Glossary file ──► (parsed, validated) ──► Batch prompt
                                               ▲
Rolling context window ────────────────────────┘
(recent accepted translations, read-only)
```

- Glossary terms are injected into every translation batch prompt as approved
  target terminology. They guide the model but do not perform literal
  substitution.
- Rolling context contains previously accepted subtitle translations from the
  current run. It is local to the run and is not persisted.
- Both are sent as part of the provider request payload and may affect cost.

## Combined vs. standalone review

**Combined (`translate --consistency-report`)**:
1. Translate → save output SRT
2. Run consistency review on the saved pairs
3. Save consistency report

**Standalone (`review SOURCE TRANSLATED`)**:
1. Load and validate matching subtitle pairs from existing files
2. Run consistency review
3. Save consistency report

Both paths use the same `ConsistencyReviewService`.

## Safety invariants

1. No existing file is overwritten without an explicit `--output` override.
2. The input SRT is opened read-only.
3. All writes use atomic rename via a temporary file where the OS supports it.
4. A review failure after translation does not delete or corrupt the translated
   SRT.
5. Provider SDK imports are gated; the CLI starts without any provider SDK
   installed.
6. The `--version` flag and package import do not require provider SDKs.

## Dependency isolation

Provider SDKs (`openai`, `google-genai`) are optional extras. Tests verify that:

- `import subtitle_translator` succeeds without provider SDKs.
- `subtitle-translator --version` runs without provider SDKs.
- Translation and review only import SDK modules when a matching provider is
  selected and its extra is installed.
