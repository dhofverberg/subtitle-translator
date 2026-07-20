Project goals

The goal is to build an open source subtitle translation tool
focused on professional subtitle translation using modern LLMs.

Core principles

- Preserve subtitle timing
- Preserve subtitle numbering
- Preserve formatting
- Preserve line breaks whenever possible
- Deterministic output
- Retry automatically
- Resume after interruption
- Provider independent

## Development principles

- Small pull requests
- Every pull request must include tests where applicable
- Every commit must leave the project in a working state
- Prefer simplicity over cleverness
- Avoid unnecessary dependencies
- Keep provider-specific code isolated

Non-goals

- Subtitle editing
- OCR
- Speech recognition
- Video encoding