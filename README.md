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

Then install the project and development tools:

~~~bash
python -m pip install -e ".[dev]"
~~~

## Running

```bash
subtitle-translator --help
```

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
persistent, does not replace an explicit glossary, and may increase OpenAI
input usage and cost.

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
