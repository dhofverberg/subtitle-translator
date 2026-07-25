from pathlib import Path

import pytest

from subtitle_translator.consistency import (
    ConsistencyCategory,
    ConsistencyFinding,
    ConsistencyOccurrence,
    ConsistencyReport,
    ConsistencySeverity,
)
from subtitle_translator.consistency_report import (
    render_consistency_report,
    save_consistency_report,
)


def report() -> ConsistencyReport:
    return ConsistencyReport(
        (
            ConsistencyFinding(
                severity=ConsistencySeverity.MEDIUM,
                category=ConsistencyCategory.PERSON_OR_RELATIONSHIP,
                explanation="Grandmother may refer to one person.",
                concept="grandmother",
                variants=("mormor", "farmor"),
                occurrences=(
                    ConsistencyOccurrence(
                        10,
                        "Grandmother\ncalled.",
                        "Mormor\nringde.",
                    ),
                    ConsistencyOccurrence(30, "Grandmother arrived.", "Farmor kom."),
                ),
                manual_check="Confirm the family relationship.",
            ),
        )
    )


def test_render_report_contains_metadata_summary_evidence_and_disclaimer():
    text = render_consistency_report(
        report(),
        source_path=Path("movie.srt"),
        translated_path=Path("movie.translated.srt"),
        source_language="English",
        target_language="Swedish",
        glossary_used=True,
    )

    assert text.startswith("# Subtitle Translation Consistency Report")
    assert "Source file: `movie.srt`" in text
    assert "Translated file: `movie.translated.srt`" in text
    assert "Source language: English" in text
    assert "Target language: Swedish" in text
    assert "Glossary used: yes" in text
    assert "Total findings: 1" in text
    assert "Medium: 1" in text
    assert "person_or_relationship" in text
    assert "Subtitle IDs: 10, 30" in text
    assert "    Grandmother" in text
    assert "    Mormor" in text
    assert "false positives" in text


def test_render_no_findings_report_is_advisory():
    text = render_consistency_report(
        ConsistencyReport(),
        source_path=Path("source.srt"),
        translated_path=Path("target.srt"),
        source_language="English",
        target_language="Swedish",
        glossary_used=False,
    )

    assert "Total findings: 0" in text
    assert "No likely consistency issues were identified." in text
    assert "guaranteed consistent" not in text
    assert "Glossary used: no" in text


def test_save_report_is_atomic_and_does_not_overwrite(tmp_path: Path):
    path = tmp_path / "report.md"
    save_consistency_report("# First", path)
    assert path.read_text(encoding="utf-8") == "# First"

    with pytest.raises(FileExistsError):
        save_consistency_report("# Replacement", path)

    assert path.read_text(encoding="utf-8") == "# First"
    assert not list(tmp_path.glob("*.tmp"))
