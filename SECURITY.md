# Security Policy

## Supported versions

This project is currently in active pre-release development. Security fixes are
applied to the latest unreleased code on the `main` branch.

Once a stable release is published, this section will be updated to list which
versions receive security support.

## Reporting a vulnerability

**Please do not open a public GitHub issue for an undisclosed security
vulnerability.**

Use GitHub's private vulnerability reporting to report security issues
confidentially:

> **[Report a vulnerability (private)](https://github.com/dhofverberg/subtitle-translator/security/advisories/new)**

> **Note for maintainer:** GitHub private vulnerability reporting must be
> enabled in the repository's Security settings before this link is active.
> Enable it before the first public release. Until it is enabled, this is a
> release blocker — there is no private reporting channel available.

### What to include

Please include as much of the following as is relevant:

- Package version (`subtitle-translator --version`)
- Python version and operating system
- Installation extras used (e.g., `[openai]`, `[gemini]`, `[all]`)
- A description of the vulnerability and its potential impact
- Steps to reproduce, using synthetic/anonymized data only
- Any relevant error messages or log output (with credentials removed)
- Whether you have a suggested fix

### What to expect

The maintainer will acknowledge receipt of the report as promptly as possible.
No specific response-time guarantee is made. You will be credited in the
security advisory unless you request otherwise.

## Scope

The following are considered in scope:

- Exposure of API keys or credentials through logs, error messages, or file
  output
- Unsafe file overwrite or creation outside the intended output location
- Path traversal or directory escape in file handling
- Injection of malicious content through subtitle or glossary input that causes
  unintended behavior
- Dependency or packaging issues that introduce a vulnerability

The following are out of scope:

- Translation quality disagreements or incorrect translations
- False positives or false negatives in advisory consistency reports
- Upstream provider outages, API changes, or pricing changes
- Model behavior that is the responsibility of the AI provider
- Denial-of-service through intentionally large input files (beyond normal
  expected use)
