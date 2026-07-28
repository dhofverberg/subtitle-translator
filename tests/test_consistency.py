import json
from dataclasses import FrozenInstanceError

import pytest

from subtitle_translator.batch import TranslationContextItem
from subtitle_translator.consistency import (
    ConsistencyCategory,
    ConsistencyProtocolError,
    ConsistencyReviewRequest,
    ConsistencySeverity,
    parse_consistency_response,
)

EXPECTED = (
    TranslationContextItem(10, "Grandmother\ncalled.", "Mormor\nringde."),
    TranslationContextItem(30, "Grandmother arrived.", "Farmor kom."),
)


def valid_payload() -> dict:
    return {
        "findings": [
            {
                "severity": "high",
                "category": "person_or_relationship",
                "explanation": "The same relationship may use two terms.",
                "concept": "grandmother",
                "variants": ["mormor", "farmor"],
                "occurrences": [
                    {
                        "id": 10,
                        "source": "Grandmother\ncalled.",
                        "translation": "Mormor\nringde.",
                    },
                    {
                        "id": 30,
                        "source": "Grandmother arrived.",
                        "translation": "Farmor kom.",
                    },
                ],
                "manual_check": "Confirm which side of the family is intended.",
            }
        ]
    }


def test_parse_valid_consistency_report_with_unicode_and_multiline():
    report = parse_consistency_response(
        json.dumps(valid_payload(), ensure_ascii=False),
        EXPECTED,
    )

    finding = report.findings[0]
    assert finding.severity is ConsistencySeverity.HIGH
    assert finding.category is ConsistencyCategory.PERSON_OR_RELATIONSHIP
    assert finding.variants == ("mormor", "farmor")
    assert finding.occurrences[0].translated_text == "Mormor\nringde."

    with pytest.raises(FrozenInstanceError):
        finding.explanation = "Changed"  # type: ignore[misc]


def test_parse_empty_findings():
    assert parse_consistency_response('{"findings": []}', EXPECTED).findings == ()


def test_review_request_and_occurrences_are_immutable():
    request = ConsistencyReviewRequest(EXPECTED, "English", "Swedish")
    report = parse_consistency_response(
        json.dumps(valid_payload(), ensure_ascii=False),
        EXPECTED,
    )

    with pytest.raises(FrozenInstanceError):
        request.items = ()  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        report.findings[0].occurrences[0].translated_text = "Changed"  # type: ignore[misc]


def test_parse_rejects_invalid_json():
    with pytest.raises(ConsistencyProtocolError, match="Invalid consistency JSON"):
        parse_consistency_response("not JSON", EXPECTED)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("severity", "urgent", "unknown severity"),
        ("category", "family", "unknown category"),
        ("explanation", "   ", "explanation must not be blank"),
        ("occurrences", [], "occurrences.*non-empty list"),
        ("variants", "mormor", "variants.*non-empty list"),
        ("variants", [], "variants.*non-empty list"),
        ("variants", ["mormor", ""], "variant at index 1 must not be blank"),
        ("variants", ["Mormor", "mormor"], "duplicate variants"),
    ],
)
def test_parse_rejects_invalid_finding_fields(field, value, message):
    payload = valid_payload()
    payload["findings"][0][field] = value

    with pytest.raises(ConsistencyProtocolError, match=message):
        parse_consistency_response(json.dumps(payload), EXPECTED)


def test_parse_rejects_unknown_subtitle_id():
    payload = valid_payload()
    payload["findings"][0]["occurrences"][0]["id"] = 99

    with pytest.raises(ConsistencyProtocolError, match="unknown subtitle ID: 99"):
        parse_consistency_response(json.dumps(payload), EXPECTED)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("source", "Different source", "source does not match"),
        ("translation", "Different translation", "translation does not match"),
    ],
)
def test_parse_rejects_mismatched_occurrence_text(field, value, message):
    payload = valid_payload()
    payload["findings"][0]["occurrences"][0][field] = value

    with pytest.raises(ConsistencyProtocolError, match=message):
        parse_consistency_response(json.dumps(payload), EXPECTED)


def test_parse_rejects_duplicate_occurrence_ids():
    payload = valid_payload()
    payload["findings"][0]["occurrences"][1] = dict(
        payload["findings"][0]["occurrences"][0]
    )

    with pytest.raises(ConsistencyProtocolError, match="duplicate occurrence IDs"):
        parse_consistency_response(json.dumps(payload), EXPECTED)
