"""Render and safely persist advisory consistency reports."""

from __future__ import annotations

from pathlib import Path

from .consistency import (
    ConsistencyReport,
    ConsistencySeverity,
    normalize_consistency_report,
)
from .persistence import write_text_atomic


def render_consistency_report(
    report: ConsistencyReport,
    *,
    source_path: Path,
    translated_path: Path,
    source_language: str,
    target_language: str,
    glossary_used: bool,
) -> str:
    """Render a deterministic human-readable Markdown consistency report."""

    normalized = normalize_consistency_report(report)
    counts = {
        severity: sum(
            finding.severity is severity
            for finding in normalized.findings
        )
        for severity in ConsistencySeverity
    }

    lines = [
        "# Subtitle Translation Consistency Report",
        "",
        f"- Source file: `{source_path}`",
        f"- Translated file: `{translated_path}`",
        f"- Source language: {source_language}",
        f"- Target language: {target_language}",
        f"- Glossary used: {'yes' if glossary_used else 'no'}",
        "",
        "## Summary",
        "",
        f"- Total findings: {len(normalized.findings)}",
        f"- High: {counts[ConsistencySeverity.HIGH]}",
        f"- Medium: {counts[ConsistencySeverity.MEDIUM]}",
        f"- Low: {counts[ConsistencySeverity.LOW]}",
        "",
        (
            "> This report is advisory, may contain false positives, and requires "
            "manual review. It does not modify the translated subtitles."
        ),
        "",
    ]

    if not normalized.findings:
        lines.extend(
            [
                "## Findings",
                "",
                "No likely consistency issues were identified.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(["## Findings", ""])
    for number, finding in enumerate(normalized.findings, start=1):
        ids = ", ".join(str(occurrence.id) for occurrence in finding.occurrences)
        variants = ", ".join(f"`{variant}`" for variant in finding.variants)
        lines.extend(
            [
                f"### {number}. {finding.concept}",
                "",
                f"- Severity: **{finding.severity.value}**",
                f"- Category: `{finding.category.value}`",
                f"- Explanation: {finding.explanation}",
                f"- Observed variants: {variants}",
                f"- Subtitle IDs: {ids}",
                f"- Suggested manual check: {finding.manual_check}",
                "",
                "#### Evidence",
                "",
            ]
        )
        for occurrence in finding.occurrences:
            lines.extend(
                [
                    f"**Subtitle {occurrence.id}**",
                    "",
                    "Source:",
                    "",
                    *_indented_lines(occurrence.source_text),
                    "",
                    "Translation:",
                    "",
                    *_indented_lines(occurrence.translated_text),
                    "",
                ]
            )

    return "\n".join(lines)


def save_consistency_report(report_text: str, path: str | Path) -> None:
    """Atomically save a UTF-8 Markdown report without overwriting."""

    write_text_atomic(report_text, path)


def _indented_lines(text: str) -> list[str]:
    return [f"    {line}" if line else "    " for line in text.split("\n")]
