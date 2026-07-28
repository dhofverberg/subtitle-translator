from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors

from subtitle_translator.batch import TranslationContextItem
from subtitle_translator.consistency import (
    ConsistencyCategory,
    ConsistencyReviewRequest,
    ConsistencySeverity,
)
from subtitle_translator.glossary import Glossary, GlossaryTerm
from subtitle_translator.providers.gemini_consistency_reviewer import (
    GeminiConsistencyReviewer,
    GeminiConsistencyReviewerError,
)


class FakeModels:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def generate_content(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class FakeClient:
    def __init__(self, responses: list[object]) -> None:
        self.models = FakeModels(responses)


def request(*, glossary: Glossary | None = None) -> ConsistencyReviewRequest:
    return ConsistencyReviewRequest(
        items=(
            TranslationContextItem(30, "Grandmother\ncalled.", "Mormor\nringde."),
            TranslationContextItem(10, "Grandmother arrived.", "Farmor kom."),
        ),
        source_language="English",
        target_language="Swedish",
        glossary=glossary,
    )


def response(
    text: str | None,
    *,
    finish_reason: str = "STOP",
    prompt_feedback: object | None = None,
) -> SimpleNamespace:
    parts = [] if text is None else [SimpleNamespace(text=text)]
    return SimpleNamespace(
        prompt_feedback=prompt_feedback,
        candidates=[
            SimpleNamespace(
                finish_reason=finish_reason,
                content=SimpleNamespace(parts=parts),
            )
        ],
    )


def valid_payload() -> dict[str, object]:
    return {
        "findings": [
            {
                "severity": "high",
                "category": "person_or_relationship",
                "explanation": "Check if relationship terms refer to the same person.",
                "concept": "grandmother",
                "variants": ["mormor", "farmor"],
                "occurrences": [
                    {
                        "id": 30,
                        "source": "Grandmother\ncalled.",
                        "translation": "Mormor\nringde.",
                    },
                    {
                        "id": 10,
                        "source": "Grandmother arrived.",
                        "translation": "Farmor kom.",
                    },
                ],
                "manual_check": "Confirm speaker and referent before changing terms.",
            }
        ]
    }


def test_gemini_reviewer_parses_valid_single_finding_and_uses_requested_model():
    client = FakeClient([response(json.dumps(valid_payload(), ensure_ascii=False))])
    reviewer = GeminiConsistencyReviewer(client=client, model="gemini-review-model")

    report = reviewer.review(request())

    assert len(report.findings) == 1
    assert report.findings[0].severity is ConsistencySeverity.HIGH
    assert report.findings[0].category is ConsistencyCategory.PERSON_OR_RELATIONSHIP
    call = client.models.calls[0]
    assert call["model"] == "gemini-review-model"
    assert call["config"].response_mime_type == "application/json"


def test_gemini_reviewer_parses_multiple_findings_and_keeps_nonsequential_ids():
    payload = valid_payload()
    payload["findings"].append(
        {
            "severity": "low",
            "category": "terminology",
            "explanation": "Terminology may vary.",
            "concept": "captain",
            "variants": ["kapten", "befälhavare"],
            "occurrences": [
                {
                    "id": 10,
                    "source": "Grandmother arrived.",
                    "translation": "Farmor kom.",
                }
            ],
            "manual_check": "Check whether role terminology should be unified.",
        }
    )
    client = FakeClient([response(json.dumps(payload, ensure_ascii=False))])
    reviewer = GeminiConsistencyReviewer(client=client, model="gemini-review-model")

    report = reviewer.review(request())

    assert len(report.findings) == 2
    assert [occ.id for occ in report.findings[0].occurrences] == [30, 10]


def test_gemini_reviewer_supports_valid_zero_findings():
    client = FakeClient([response('{"findings": []}')])
    reviewer = GeminiConsistencyReviewer(client=client, model="gemini-review-model")

    report = reviewer.review(request())

    assert report.findings == ()


def test_gemini_reviewer_uses_injected_client_and_serializes_structured_input():
    glossary = Glossary(
        "English",
        "Swedish",
        (GlossaryTerm("grandmother", "mormor"),),
    )
    client = FakeClient([response('{"findings": []}')])
    reviewer = GeminiConsistencyReviewer(client=client, model="gemini-review-model")

    reviewer.review(request(glossary=glossary))

    call = client.models.calls[0]
    payload = json.loads(call["contents"])
    assert payload["source_language"] == "English"
    assert payload["target_language"] == "Swedish"
    assert payload["glossary"] == {
        "source_language": "English",
        "target_language": "Swedish",
        "terms": [{"source": "grandmother", "target": "mormor"}],
    }
    assert payload["subtitle_pairs"] == [
        {
            "id": 30,
            "source": "Grandmother\ncalled.",
            "translation": "Mormor\nringde.",
        },
        {
            "id": 10,
            "source": "Grandmother arrived.",
            "translation": "Farmor kom.",
        },
    ]


def test_gemini_reviewer_supports_no_glossary_input():
    client = FakeClient([response('{"findings": []}')])
    reviewer = GeminiConsistencyReviewer(client=client, model="gemini-review-model")

    reviewer.review(request())

    payload = json.loads(client.models.calls[0]["contents"])
    assert payload["glossary"] is None


def test_gemini_reviewer_schema_covers_severity_and_category_enums():
    client = FakeClient([response('{"findings": []}')])
    reviewer = GeminiConsistencyReviewer(client=client, model="gemini-review-model")

    reviewer.review(request())

    schema = client.models.calls[0]["config"].response_json_schema
    finding = schema["properties"]["findings"]["items"]["properties"]
    assert set(finding["severity"]["enum"]) == {severity.value for severity in ConsistencySeverity}
    assert set(finding["category"]["enum"]) == {category.value for category in ConsistencyCategory}


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not JSON", "invalid consistency review"),
        ('{"findings": "not-a-list"}', "invalid consistency review"),
        ('{"findings":[{"severity":"urgent","category":"terminology","explanation":"x","concept":"c","variants":["v"],"occurrences":[{"id":30,"source":"Grandmother\\ncalled.","translation":"Mormor\\nringde."}],"manual_check":"m"}]}', "unknown severity"),
        ('{"findings":[{"severity":"high","category":"family","explanation":"x","concept":"c","variants":["v"],"occurrences":[{"id":30,"source":"Grandmother\\ncalled.","translation":"Mormor\\nringde."}],"manual_check":"m"}]}', "unknown category"),
        ('{"findings":[{"severity":"high","category":"terminology","explanation":" ","concept":"c","variants":["v"],"occurrences":[{"id":30,"source":"Grandmother\\ncalled.","translation":"Mormor\\nringde."}],"manual_check":"m"}]}', "explanation must not be blank"),
        ('{"findings":[{"severity":"high","category":"terminology","explanation":"x","concept":"c","variants":[],"occurrences":[{"id":30,"source":"Grandmother\\ncalled.","translation":"Mormor\\nringde."}],"manual_check":"m"}]}', "variants"),
        ('{"findings":[{"severity":"high","category":"terminology","explanation":"x","concept":"c","variants":["v"],"occurrences":[],"manual_check":"m"}]}', "occurrences"),
        ('{"findings":[{"severity":"high","category":"terminology","explanation":"x","concept":"c","variants":["v"],"occurrences":[{"id":99,"source":"x","translation":"y"}],"manual_check":"m"}]}', "unknown subtitle ID"),
        ('{"findings":[{"severity":"high","category":"terminology","explanation":"x","concept":"c","variants":["v"],"occurrences":[{"id":30,"source":"Grandmother\\ncalled.","translation":"Mormor\\nringde."},{"id":30,"source":"Grandmother\\ncalled.","translation":"Mormor\\nringde."}],"manual_check":"m"}]}', "duplicate occurrence IDs"),
        ('{"findings":[{"severity":"high","category":"terminology","explanation":"x","concept":"c","variants":["v"],"occurrences":[{"id":30,"source":"wrong","translation":"Mormor\\nringde."}],"manual_check":"m"}]}', "source does not match"),
        ('{"findings":[{"severity":"high","category":"terminology","explanation":"x","concept":"c","variants":["v"],"occurrences":[{"id":30,"source":"Grandmother\\ncalled.","translation":"wrong"}],"manual_check":"m"}]}', "translation does not match"),
    ],
)
def test_gemini_reviewer_rejects_invalid_model_output(payload: str, message: str):
    client = FakeClient([response(payload)])
    reviewer = GeminiConsistencyReviewer(client=client, model="gemini-review-model")

    with pytest.raises(GeminiConsistencyReviewerError, match=message):
        reviewer.review(request())


@pytest.mark.parametrize(
    ("sdk_response", "message"),
    [
        (SimpleNamespace(prompt_feedback=None, candidates=[]), "empty consistency review response"),
        (response(None), "empty consistency review response"),
        (response("[]", prompt_feedback=object()), "blocked"),
        (response("[]", finish_reason="SAFETY"), "blocked"),
        (response("[]", finish_reason="MAX_TOKENS"), "incomplete"),
        (
            SimpleNamespace(
                prompt_feedback=None,
                candidates=[
                    SimpleNamespace(
                        finish_reason="STOP",
                        content=SimpleNamespace(parts=[SimpleNamespace(inline_data="binary")]),
                    )
                ],
            ),
            "non-text consistency review response",
        ),
    ],
)
def test_gemini_reviewer_rejects_empty_blocked_incomplete_and_non_text_outputs(
    sdk_response: object,
    message: str,
):
    reviewer = GeminiConsistencyReviewer(client=FakeClient([sdk_response]), model="gemini-review-model")

    with pytest.raises(GeminiConsistencyReviewerError, match=message):
        reviewer.review(request())


def test_gemini_reviewer_wraps_and_sanitizes_sdk_errors():
    secret = "Authorization: Bearer secret-token"
    reviewer = GeminiConsistencyReviewer(
        client=FakeClient([errors.APIError(500, {"Authorization": secret}, None)]),
        model="gemini-review-model",
    )

    with pytest.raises(
        GeminiConsistencyReviewerError,
        match="Gemini consistency review request failed",
    ) as exc_info:
        reviewer.review(request())

    assert secret not in str(exc_info.value)
    assert "Grandmother" not in str(exc_info.value)
