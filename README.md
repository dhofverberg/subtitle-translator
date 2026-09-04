# Subtitle Translator

AI-powered subtitle translation for SRT files, supporting OpenAI and Google Gemini.

---

> **Status:** Pre-release (v0.1.0 — not yet published to PyPI).
> Install from a local checkout or built wheel. See [Installation](#installation).

---

## Key capabilities

- Translates SRT subtitle files between any language pair supported by your provider
- Preserves subtitle indices, timestamps, formatting, and line breaks
- Supports **OpenAI** and **Google Gemini** (provider-neutral core)
- Optional **glossary** for approved terminology
- Optional **rolling context** for consistent terminology within a file
- Optional **consistency report** — advisory AI review highlighting possible inconsistencies
- **Standalone review** command for reviewing existing translated files without retranslating
- **Cross-provider review** — translate with one provider, review with another
- Resumes after interruption; atomic output writes; never overwrites existing files

---

## Requirements

- Python 3.11, 3.12, or 3.13
- At least one provider SDK installed (see [Installation](#installation)):
  - OpenAI: `pip install "subtitle-translator[openai]"`
  - Gemini: `pip install "subtitle-translator[gemini]"`
- A valid API key for each provider you use

---

## Installation

This project is not yet published on PyPI. Install from a local checkout.

**Clone and create a virtual environment:**

```bash
git clone https://github.com/dhofverberg/subtitle-translator.git
cd subtitle-translator
python -m venv .venv
```

Activate on macOS or Linux:

```bash
source .venv/bin/activate
```

Activate on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

**Install the provider you need:**

```bash
# OpenAI only
pip install -e ".[openai]"

# Gemini only
pip install -e ".[gemini]"

# Both providers
pip install -e ".[all]"

# Both providers plus development tools
pip install -e ".[all,dev]"
```

**After publication** (not yet available):

```bash
# These commands will work once the package is published to PyPI:
# pip install "subtitle-translator[openai]"
# pip install "subtitle-translator[gemini]"
# pip install "subtitle-translator[all]"
```

---

## Quick start

### OpenAI

```bash
# Set your API key
export OPENAI_API_KEY="your_api_key_here"   # macOS / Linux
# $env:OPENAI_API_KEY = "your_api_key_here"  # Windows PowerShell

# Translate a subtitle file (default: English → Swedish)
subtitle-translator translate movie.srt \
  --source-language English \
  --target-language French
```

Output is written to `movie.translated.srt` in the same directory.

### Gemini

```bash
# Set your API key
export GEMINI_API_KEY="your_api_key_here"   # macOS / Linux
# $env:GEMINI_API_KEY = "your_api_key_here"  # Windows PowerShell

# Translate using Gemini
subtitle-translator translate movie.srt \
  --provider gemini \
  --source-language English \
  --target-language French
```

---

## Provider configuration

### Selecting a provider

Use `--provider` to choose the translation provider. The default is `openai`.
Provider names are case-insensitive.

```bash
subtitle-translator translate movie.srt --provider gemini ...
```

### Environment variables

| Variable | Provider | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI | API authentication (required) |
| `OPENAI_MODEL` | OpenAI | Default translation model |
| `OPENAI_REVIEW_MODEL` | OpenAI | Default consistency-review model |
| `GEMINI_API_KEY` | Gemini | API authentication (required) |
| `GEMINI_MODEL` | Gemini | Default translation model |
| `GEMINI_REVIEW_MODEL` | Gemini | Default consistency-review model |

### Default models

The default models are defined in the application configuration. They may
change between releases. Check `subtitle-translator translate --help` for the
current defaults. Use `--model` or the environment variables above to override
them.

> **Note:** Model availability, cost, token limits, and translation quality
> vary by provider and account type. Choose models supported by your account.
> The tool does not fall back between providers automatically.

### Overriding models

Use `--model` to override the translation model for a single command:

```bash
subtitle-translator translate movie.srt --provider openai --model gpt-4o ...
```

Use `--review-model` to override only the consistency-review model:

```bash
subtitle-translator translate movie.srt \
  --provider openai --model gpt-4o \
  --review-provider gemini --review-model gemini-2.5-pro \
  --consistency-report movie.consistency.md
```

### Cross-provider review

Translate with one provider and review with another using `--review-provider`.
Cross-provider workflows require credentials and installed extras for **both**
providers.

```bash
subtitle-translator translate movie.srt \
  --provider gemini \
  --review-provider openai \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

---

## Common workflows

All examples assume the subtitle file exists and no output file exists yet.

### Basic OpenAI translation

```bash
subtitle-translator translate movie.srt \
  --source-language English \
  --target-language French
```

### Basic Gemini translation

```bash
subtitle-translator translate movie.srt \
  --provider gemini \
  --source-language English \
  --target-language French
```

### Explicit output path

```bash
subtitle-translator translate movie.en.srt \
  --output movie.fr.srt \
  --source-language English \
  --target-language French
```

### Custom batch size

```bash
subtitle-translator translate movie.srt \
  --batch-size 10 \
  --source-language English \
  --target-language German
```

### Disable rolling context

```bash
subtitle-translator translate movie.srt \
  --context-size 0 \
  --source-language English \
  --target-language Swedish
```

### Using a glossary

```bash
subtitle-translator translate movie.srt \
  --glossary glossary.en-sv.json \
  --source-language English \
  --target-language Swedish
```

### Translation plus consistency report

```bash
subtitle-translator translate movie.srt \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

### Standalone consistency review

```bash
subtitle-translator review movie.en.srt movie.sv.srt \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

### Gemini translation with OpenAI review

```bash
subtitle-translator translate movie.srt \
  --provider gemini \
  --review-provider openai \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

### OpenAI translation with Gemini review

```bash
subtitle-translator translate movie.srt \
  --provider openai \
  --review-provider gemini \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

### Explicit translation and review models

```bash
subtitle-translator translate movie.srt \
  --provider openai --model gpt-4o \
  --review-provider gemini --review-model gemini-2.5-pro \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

### Legacy positional syntax

The original command style (without a `translate` subcommand) is preserved for
backward compatibility:

```bash
subtitle-translator movie.srt --source-language English --target-language Swedish
```

---

## Glossary

A glossary supplies approved source-to-target terminology as a UTF-8 JSON file.

### JSON shape

```json
{
  "source_language": "English",
  "target_language": "Swedish",
  "terms": [
    { "source": "warp drive", "target": "warpdrift" },
    { "source": "First Officer", "target": "sekond" }
  ]
}
```

The `source_language` and `target_language` fields must match the
`--source-language` and `--target-language` values you pass on the command
line. The comparison is case-insensitive and trims whitespace.

### Behavior

- Glossary terms guide the model toward consistent terminology. They are not
  literal search-and-replace rules.
- Normal grammar and inflection apply: `"warp drive" → "warpdrift"` may still
  appear inflected as appropriate.
- Glossary priority is higher than rolling context: when the same concept
  appears in both, the glossary term takes precedence.
- Ambiguous proper nouns or relationship terms may not be resolved consistently
  if the glossary does not explicitly cover them.

### Failure behavior

If the glossary file cannot be read, is not valid JSON, or has mismatched
language fields, the command fails immediately before making any API calls.

### Example

```bash
subtitle-translator translate samples/openai_smoke_test.srt \
  --source-language English \
  --target-language Swedish \
  --glossary samples/glossary.en-sv.json
```

---

## Rolling context

Each translation batch optionally receives recently accepted translations from
the current file as read-only reference material.

- Context contains previously accepted subtitle pairs from the **current run
  only**. It is not persistent translation memory.
- It is read-only: the model uses it as guidance, not as a mandatory rule.
- It is local to the current file and run. Different runs start fresh.
- Context can help resolve pronouns, recurring names, and ambiguous relationship
  terms. For example, if an earlier subtitle establishes "grandmother" as
  Swedish `mormor` (mother's mother), a later batch may consistently use the
  same term.
- `--context-size 0` disables rolling context entirely.
- Larger context values may increase provider input usage and cost.
- Context does not replace an explicit glossary.

```bash
# Use a context window of 20 recently translated entries
subtitle-translator translate movie.srt --context-size 20

# Disable context
subtitle-translator translate movie.srt --context-size 0
```

---

## Consistency reports

### Combined translation + review

Add `--consistency-report` to generate an advisory review after translation:

```bash
subtitle-translator translate movie.srt \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

- The review runs **after** the translated SRT has been saved.
- The report is a Markdown file listing possible inconsistencies for human
  inspection.
- The review **never modifies** the translated SRT.
- All findings are advisory. Film context may be needed to interpret them.
  False positives are possible.
- Review incurs **separate paid API calls**.

### Example finding

A report might note that the English word "grandmother" appears in subtitles
10, 20, and 30, translated as Swedish `farmor` (father's mother) in some places
and `mormor` (mother's mother) in others, and ask whether the references all
concern the same person. This is not a claim that an error was made — it is a
prompt for the user to verify.

### Review failure

If the review fails after translation, the translated SRT is **preserved**. The
review failure is reported as an error. Use the standalone `review` command to
retry the review later.

---

## Standalone review

Review existing SRT files without retranslating:

```bash
subtitle-translator review movie.en.srt movie.sv.srt \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

Use `--provider` to select the review provider (default: `openai`).

### Requirements

Both files must have:

- The same number of subtitles
- Matching subtitle indices (IDs)
- Identical start and end timestamps for each pair

If the files do not match, the command fails before making any API calls.

### Difference: translate with report vs. standalone review

| | `translate --consistency-report` | `review` |
|---|---|---|
| Input | Source SRT | Source + translated SRT |
| Translation | Yes | No |
| Output files | Translated SRT + report | Report only |
| Use case | Full workflow | Retry review, external files |

---

## Output safety

- Existing output files are **not overwritten** by default. Use `--output` to
  specify a new path.
- Existing consistency report files are not overwritten. Specify a new path.
- Output writes use atomic rename where the OS supports it.
- Source SRT files are never modified.
- If a review fails after translation, the translated SRT is preserved.
- Keep your originals and backups regardless.

---

## Cost, privacy, and API considerations

> **Important:** Subtitle text is sent to external API providers. Review these
> considerations before translating sensitive content.

- Subtitle text is transmitted to the selected provider (OpenAI or Google).
- Glossary terms and rolling context data are also sent as part of each
  translation request.
- Standalone review sends both source and translated subtitle text.
- Cross-provider workflows may send content to **two providers**.
- You are responsible for reviewing each provider's terms of service, data
  retention policies, data-control settings, regional requirements, and billing.
- The tool cannot guarantee a specific cost. Batch size, context size, review
  chunking, model choice, and subtitle length all influence token usage.
- Transport encryption (HTTPS) does not mean your content is private. Consult
  your provider's data-processing agreements for details.
- The application does not log API keys. You are responsible for protecting
  your local environment and configuration files.

---

## Troubleshooting

### `command not found: subtitle-translator`

Ensure the virtual environment is activated and the package is installed:

```bash
pip show subtitle-translator
subtitle-translator --help
```

### Missing provider SDK

```
Error: OpenAI support is not installed. Install subtitle-translator[openai].
Error: Gemini support is not installed. Install subtitle-translator[gemini].
```

Install the required extra:

```bash
pip install -e ".[openai]"   # or [gemini] or [all]
```

### Missing API key

OpenAI requires `OPENAI_API_KEY`. Gemini requires `GEMINI_API_KEY`.

```bash
# macOS / Linux
export OPENAI_API_KEY="your_key_here"
export GEMINI_API_KEY="your_key_here"

# Windows PowerShell
$env:OPENAI_API_KEY = "your_key_here"
$env:GEMINI_API_KEY = "your_key_here"
```

### Invalid or unavailable model

Check that the model name is correct and available on your account. Use
`--model` to override the default.

### Output file already exists

```
Error: Output file already exists: movie.translated.srt
```

Delete the existing file or specify a different output path with `--output`.

### Consistency report already exists

```
Error: Consistency report already exists: movie.consistency.md
```

Delete the existing report or specify a new path.

### Glossary language mismatch

Ensure `source_language` and `target_language` in your glossary JSON match
the `--source-language` and `--target-language` values exactly
(case-insensitive).

### Incompatible source and translated files in standalone review

Both files must have the same subtitle count, matching IDs, and identical
timestamps for each entry.

### Provider returned an invalid or blocked response

Try a smaller batch size (`--batch-size`) or check your provider's content
moderation settings.

### Translation succeeded but review failed

The translated SRT is preserved. Retry the review with the `review` command:

```bash
subtitle-translator review movie.en.srt movie.translated.srt \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
```

### Unicode display in the terminal

If translated text looks garbled in the terminal but the SRT file opens
correctly in a text editor, this is a terminal encoding issue. Files are
written as UTF-8 regardless of terminal display.

### Getting help

```bash
subtitle-translator --help
subtitle-translator translate --help
subtitle-translator review --help
subtitle-translator --version
```

---

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for full setup instructions.

```bash
git clone https://github.com/dhofverberg/subtitle-translator.git
cd subtitle-translator
python -m venv .venv
source .venv/bin/activate          # or .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[all,dev]"
pytest
ruff check .
python -m build
python -m twine check dist/*
```

See [docs/architecture.md](docs/architecture.md) for the internal design.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

Bug reports and feature requests:
[GitHub Issues](https://github.com/dhofverberg/subtitle-translator/issues)

---

## Security

See [SECURITY.md](SECURITY.md) for the supported-version policy and
instructions for reporting vulnerabilities privately.

---

## License

[MIT](LICENSE)

