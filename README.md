# Subtitle Translator

AI-powered subtitle translation for SRT files using OpenAI and other LLM providers.

> **Status:** Early development (v0.1.0)

## Features (planned)

- OpenAI GPT-5.5 support
- Batch translation
- Resume after interruption
- Translation glossary
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

Translate the included sample from English to Swedish:

~~~bash
subtitle-translator samples/openai_smoke_test.srt --source-language English --target-language Swedish
~~~

The derived output is *samples/openai_smoke_test.translated.srt*. This command
makes a real, paid OpenAI API request. Inspect the generated SRT manually and
confirm that its indices, timestamps, line breaks, and translated text are
correct.

## License

MIT
