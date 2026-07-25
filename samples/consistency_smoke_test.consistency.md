# Subtitle Translation Consistency Report

- Source file: `samples\consistency_smoke_test.srt`
- Translated file: `samples\consistency_smoke_test.translated.srt`
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
- Explanation: The same family relationship concept appears with different Swedish maternal/paternal terms. Subtitle 10 explicitly establishes the speaker's father's mother as "farmor", while later generic references to grandmother use "mormor"; this may be inconsistent if they refer to the same person/speaker.
- Observed variants: `farmor`, `mormor`
- Subtitle IDs: 10, 20, 30
- Suggested manual check: Check whether the grandmother references are from the same speaker and refer to the same paternal or maternal grandmother.

#### Evidence

**Subtitle 10**

Source:

    My father's mother lives nearby.

Translation:

    Min farmor bor i närheten.

**Subtitle 20**

Source:

    Grandmother called this morning.

Translation:

    Mormor ringde i morse.

**Subtitle 30**

Source:

    I will visit my grandmother tomorrow.

Translation:

    Jag ska hälsa på min mormor i morgon.
