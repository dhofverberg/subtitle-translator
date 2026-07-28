# Subtitle Translator

AI-powered subtitle translation for SRT files using OpenAI and other LLM providers.

> **Status:** Early development (v0.1.0)

## Features (planned)

- OpenAI GPT-5.5 support
- Batch translation
- Resume after interruption
- Quality Check pass
- Multiple AI providers
- Rich command-line interface

## Installation

Create a virtual environment:

~~~bash
python -m venv .venv
~~~

Activate it on macOS or Linux:

~~~bash
source .venv/bin/activate
~~~

Or activate it on Windows PowerShell:

~~~powershell
.venv\Scripts\Activate.ps1
~~~

Install the provider support you need:

~~~bash
python -m pip install -e ".[openai]"       # OpenAI translation and review
python -m pip install -e ".[gemini]"       # Gemini translation and review
python -m pip install -e ".[all]"          # Both providers
python -m pip install -e ".[dev,all]"      # Both providers plus development tools
~~~

## Running

```bash
subtitle-translator --help
```

## Translation providers

OpenAI is the default provider, preserving existing commands. Select Gemini
explicitly with `--provider gemini`; provider names are case-insensitive:

~~~bash
subtitle-translator movie.srt --provider gemini \
  --source-language English --target-language Swedish
~~~

Set `GEMINI_API_KEY` to authenticate Gemini requests. `GEMINI_MODEL` optionally
sets the default Gemini model, and `--model` overrides the selected provider's
default for one command:

~~~bash
export GEMINI_API_KEY="your_api_key_here"
export GEMINI_MODEL="gemini-2.5-flash"
subtitle-translator movie.srt --provider gemini --model gemini-2.5-pro
~~~

On Windows PowerShell:

~~~powershell
$env:GEMINI_API_KEY = "your_api_key_here"
$env:GEMINI_MODEL = "gemini-2.5-flash"
subtitle-translator movie.srt --provider gemini
~~~

Model availability, cost, limits, and translation/review quality differ between
providers. Compare both providers using representative subtitle samples for
your language pair before selecting one for a project.

Credential requirements depend on provider choices:

- OpenAI translation/review needs `OPENAI_API_KEY`
- Gemini translation/review needs `GEMINI_API_KEY`
- Mixed-provider translation+review (for example Gemini translation with OpenAI
  review) requires both provider credentials

## Glossaries

Use `--glossary PATH` to supply approved source-to-target terminology as a
UTF-8 JSON file:

~~~json
{
  "source_language": "English",
  "target_language": "Swedish",
  "terms": [
    {
      "source": "warp drive",
      "target": "warpdrift"
    }
  ]
}
~~~

The glossary languages must match the CLI source and target languages. Glossary
entries guide the model toward consistent terminology; they are not literal
search-and-replace rules, so normal grammar and inflection still apply.

The repository includes `samples/glossary.en-sv.json`. Use it with the sample
subtitles:

~~~bash
subtitle-translator samples/openai_smoke_test.srt --source-language English --target-language Swedish --glossary samples/glossary.en-sv.json
~~~

## Rolling subtitle context

By default, each batch receives up to 10 recently translated subtitles from
the same file as read-only context. This can help resolve pronouns, names,
forms of address, recurring phrases, and ambiguous relationships. For example,
an earlier English subtitle may establish that "grandmother" is the speaker's
mother's mother and be accepted as Swedish "mormor"; a later batch can then see
that source and translation pair when choosing the same relationship term.

Set the maximum number of entries with `--context-size`, or disable context
with `--context-size 0`:

~~~bash
subtitle-translator samples/openai_smoke_test.srt --context-size 10
~~~

Context is limited to the current file and translation run. It is not
persistent, does not replace an explicit glossary, and may increase provider
input usage and cost.

## Optional consistency report

Use `--consistency-report PATH` to run a separate advisory review after the
translated SRT has been saved. By default, the review provider matches the
translation provider:

~~~bash
subtitle-translator movie.srt \
  --provider gemini \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
~~~

Use `--review-provider` to review with a different provider than the one used
for translation:

~~~bash
subtitle-translator movie.srt \
  --provider gemini \
  --review-provider openai \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
~~~

Use `--review-model` to override only the consistency-review model (independent
from `--model`, which controls translation):

~~~bash
subtitle-translator movie.srt \
  --provider openai \
  --model gpt-5.5 \
  --review-provider gemini \
  --review-model gemini-2.5-pro \
  --consistency-report movie.consistency.md
~~~

The Markdown report highlights likely cross-subtitle inconsistencies for human
inspection. For example, it may cite exact subtitle IDs where the same
"grandmother" appears as both "mormor" and "farmor" and suggest checking which
family relationship is intended.

This review makes additional paid API requests. It never changes or rewrites
the translated SRT. Findings are advisory, require manual review, and may
include false positives.

Review quality can differ between providers. Running a second-provider review
can catch issues that the translating provider missed, but this is not
guaranteed.

The three consistency features serve different purposes:

- A glossary supplies explicit approved terminology.
- Rolling context supplies recent accepted translations while translation is
  in progress.
- A consistency report reviews the completed translation afterward and
  reports possible issues without applying fixes.

## Standalone consistency review of existing subtitle files

Use the `review` command to generate a consistency report from existing source
and translated SRT files without re-translating. OpenAI remains the default
review provider for backward compatibility.

~~~bash
subtitle-translator review movie.en.srt movie.sv.srt \
  --provider gemini \
  --source-language English \
  --target-language Swedish \
  --consistency-report movie.consistency.md
~~~

This is useful for:

- Retrying a failed consistency report after the translation is complete
- Reviewing pre-existing or external subtitle files
- Adjusting glossary or language settings and re-running the review

### Requirements

Both SRT files must have:

- The same number of subtitles
- Matching subtitle indices (IDs)
- Identical start and end timestamps for each pair

If files don't match, the command fails before making any API requests.

### Glossary with standalone review

Supply a glossary with `--glossary PATH` exactly as with translation:

~~~bash
subtitle-translator review movie.en.srt movie.sv.srt \
  --source-language English \
  --target-language Swedish \
  --provider gemini \
  --glossary glossary.json \
  --consistency-report movie.consistency.md
~~~

Glossary languages must match the requested source and target languages.

### Important notes

- **No translation occurs** — neither source nor translated SRT is modified
- **Additional API requests** — the review makes separate, paid provider API calls
  for consistency analysis
- **Advisory only** — all findings require manual review and may include false
  positives
- **Cannot realign subtitles** — files must already have matching structure;
  automatic alignment is not performed
- **No automatic corrections** — neither reviewer rewrites subtitle text
- **Retry-friendly** — a failed review does not require retranslation; run the
  standalone `review` command later

### Review model environment variables

Review model selection order is:

1. `--review-model` (or `--model` for standalone `review`)
2. Provider-specific review model environment variable
3. Provider normal model environment variable
4. Provider default

Supported environment variables:

- `OPENAI_REVIEW_MODEL`
- `GEMINI_REVIEW_MODEL`

### Difference: translate with report vs. standalone review

| Aspect | `translate --consistency-report` | `review` command |
|--------|----------------------------------|------------------|
| **Input** | Source SRT file (English) | Source + translated SRT files |
| **Translation** | Yes, generates translated SRT | No, uses existing files |
| **Review** | Yes, after translation | Yes, only |
| **Output files** | Translated SRT + report | Report only |
| **Failed translation** | Partial report (if not caught before save) | No translation to preserve |
| **Use case** | Full workflow: translate and review | Retry review, external files |

## Manual OpenAI smoke test

Set your OpenAI API key in the shell. You can optionally override the default
model with *OPENAI_MODEL*.

On macOS or Linux:

~~~bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_MODEL="gpt-5.5"  # Optional
~~~

On Windows PowerShell:

~~~powershell
$env:OPENAI_API_KEY = "your_api_key_here"
$env:OPENAI_MODEL = "gpt-5.5"  # Optional
~~~

Translate the included sample from English to Swedish, optionally adding
`--glossary samples/glossary.en-sv.json`:

~~~bash
subtitle-translator samples/openai_smoke_test.srt --source-language English --target-language Swedish
~~~

The derived output is *samples/openai_smoke_test.translated.srt*. This command
makes a real, paid OpenAI API request. Inspect the generated SRT manually and
confirm that its indices, timestamps, line breaks, and translated text are
correct.

## License

MIT
