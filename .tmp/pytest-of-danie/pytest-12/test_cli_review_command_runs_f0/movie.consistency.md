# Subtitle Translation Consistency Report

- Source file: `C:\src\subtitle-translator.worktrees\agents-consistency-review-standalone-cli\.tmp\pytest-of-danie\pytest-12\test_cli_review_command_runs_f0\movie.en.srt`
- Translated file: `C:\src\subtitle-translator.worktrees\agents-consistency-review-standalone-cli\.tmp\pytest-of-danie\pytest-12\test_cli_review_command_runs_f0\movie.sv.srt`
- Source language: English
- Target language: Swedish
- Glossary used: no

## Summary

- Total findings: 1
- High: 0
- Medium: 1
- Low: 0

> This report is advisory, may contain false positives, and requires manual review. It does not modify the translated subtitles.

## Findings

### 1. grandmother

- Severity: **medium**
- Category: `person_or_relationship`
- Explanation: Grandmother may use inconsistent relationship terms.
- Observed variants: `mormor`, `farmor`
- Subtitle IDs: 10, 20
- Suggested manual check: Confirm the intended family relationship.

#### Evidence

**Subtitle 10**

Source:

    Hello
    world

Translation:

    Hej
    världen

**Subtitle 20**

Source:

    Grandmother called.

Translation:

    Mormor ringde.
