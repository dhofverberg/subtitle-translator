from datetime import timedelta

import pytest

from subtitle_translator.batch import TranslationContextItem
from subtitle_translator.consistency import (
    ConsistencyCategory,
    ConsistencyFinding,
    ConsistencyOccurrence,
    ConsistencyReport,
    ConsistencyReviewer,
    ConsistencyReviewRequest,
    ConsistencySeverity,
)
from subtitle_translator.consistency_review import (
    ConsistencyReviewError,
    ConsistencyReviewService,
)
from subtitle_translator.glossary import Glossary, GlossaryTerm
from subtitle_translator.models import Subtitle, SubtitleFile


class FakeReviewer(ConsistencyReviewer):
    def __init__(self, reports: list[ConsistencyReport] | None = None) -> None:
        self.reports = reports or []
        self.requests: list[ConsistencyReviewRequest] = []

    def review(self, request: ConsistencyReviewRequest) -> ConsistencyReport:
        self.requests.append(request)
        if self.reports:
            return self.reports[len(self.requests) - 1]
        return ConsistencyReport()


def subtitle_file(ids: list[int], prefix: str) -> SubtitleFile:
    return SubtitleFile(
        [
            Subtitle(
                item_id,
                timedelta(seconds=position),
                timedelta(seconds=position + 1),
                f"{prefix} {item_id}\nline",
            )
            for position, item_id in enumerate(ids)
        ]
    )


def finding(
    severity: ConsistencySeverity,
    category: ConsistencyCategory,
    concept: str,
    ids: tuple[int, ...],
) -> ConsistencyFinding:
    return ConsistencyFinding(
        severity=severity,
        category=category,
        explanation=f"Check {concept}.",
        concept=concept,
        variants=("one", "two"),
        occurrences=tuple(
            ConsistencyOccurrence(item_id, f"source {item_id}", f"target {item_id}")
            for item_id in ids
        ),
        manual_check="Inspect the cited subtitles.",
    )


def test_review_pairs_source_and_accepted_translation_and_passes_glossary():
    glossary = Glossary(
        "English",
        "Swedish",
        (GlossaryTerm("warp drive", "warpdrift"),),
    )
    reviewer = FakeReviewer()
    service = ConsistencyReviewService(
        reviewer,
        "English",
        "Swedish",
        glossary=glossary,
        chunk_size=10,
        overlap=2,
    )

    report = service.review(
        subtitle_file([10, 30], "source"),
        subtitle_file([10, 30], "target"),
    )

    assert report == ConsistencyReport()
    assert reviewer.requests == [
        ConsistencyReviewRequest(
            items=(
                TranslationContextItem(10, "source 10\nline", "target 10\nline"),
                TranslationContextItem(30, "source 30\nline", "target 30\nline"),
            ),
            source_language="English",
            target_language="Swedish",
            glossary=glossary,
        )
    ]


def test_review_without_glossary_and_empty_input():
    reviewer = FakeReviewer()
    service = ConsistencyReviewService(
        reviewer,
        "English",
        "Swedish",
        chunk_size=3,
        overlap=1,
    )

    assert service.review(SubtitleFile(), SubtitleFile()) == ConsistencyReport()
    assert reviewer.requests == []


def test_long_input_uses_deterministic_overlapping_chunks_with_nonsequential_ids():
    reviewer = FakeReviewer()
    service = ConsistencyReviewService(
        reviewer,
        "English",
        "Swedish",
        chunk_size=3,
        overlap=1,
    )
    ids = [10, 20, 40, 80, 90, 120]

    service.review(subtitle_file(ids, "source"), subtitle_file(ids, "target"))

    assert [[item.id for item in request.items] for request in reviewer.requests] == [
        [10, 20, 40],
        [40, 80, 90],
        [90, 120],
    ]
    assert all(request.glossary is None for request in reviewer.requests)


def test_findings_are_merged_deduplicated_and_sorted():
    low = finding(
        ConsistencySeverity.LOW,
        ConsistencyCategory.TERMINOLOGY,
        "engine",
        (20,),
    )
    high = finding(
        ConsistencySeverity.HIGH,
        ConsistencyCategory.GLOSSARY_VIOLATION,
        "warp drive",
        (90,),
    )
    duplicate_high = finding(
        ConsistencySeverity.HIGH,
        ConsistencyCategory.GLOSSARY_VIOLATION,
        "WARP DRIVE",
        (90,),
    )
    medium = finding(
        ConsistencySeverity.MEDIUM,
        ConsistencyCategory.NAME_OR_TITLE,
        "Captain",
        (10,),
    )
    reviewer = FakeReviewer(
        [
            ConsistencyReport((low, high)),
            ConsistencyReport((duplicate_high, medium)),
        ]
    )
    service = ConsistencyReviewService(
        reviewer,
        "English",
        "Swedish",
        chunk_size=2,
        overlap=1,
    )

    report = service.review(
        subtitle_file([10, 20, 90], "source"),
        subtitle_file([10, 20, 90], "target"),
    )

    assert report.findings == (high, medium, low)


def test_review_state_does_not_leak_between_files():
    reviewer = FakeReviewer()
    service = ConsistencyReviewService(
        reviewer,
        "English",
        "Swedish",
        chunk_size=10,
        overlap=1,
    )

    service.review(subtitle_file([10], "first"), subtitle_file([10], "första"))
    service.review(subtitle_file([30], "second"), subtitle_file([30], "andra"))

    assert reviewer.requests[0].items[0].source_text == "first 10\nline"
    assert reviewer.requests[1].items == (
        TranslationContextItem(30, "second 30\nline", "andra 30\nline"),
    )


def test_review_rejects_mismatched_files():
    service = ConsistencyReviewService(
        FakeReviewer(),
        "English",
        "Swedish",
        chunk_size=10,
        overlap=1,
    )

    with pytest.raises(ConsistencyReviewError, match="same number"):
        service.review(
            subtitle_file([10], "source"),
            subtitle_file([10, 20], "target"),
        )


@pytest.mark.parametrize(
    ("chunk_size", "overlap", "message"),
    [
        (0, 0, "chunk_size"),
        (2, -1, "overlap must not be negative"),
        (2, 2, "overlap must be smaller"),
    ],
)
def test_review_rejects_invalid_chunk_configuration(chunk_size, overlap, message):
    with pytest.raises(ValueError, match=message):
        ConsistencyReviewService(
            FakeReviewer(),
            "English",
            "Swedish",
            chunk_size=chunk_size,
            overlap=overlap,
        )
