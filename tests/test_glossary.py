from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from subtitle_translator.glossary import (
    Glossary,
    GlossaryError,
    GlossaryTerm,
    glossary_to_dict,
    load_glossary,
    parse_glossary,
)


def valid_payload() -> dict[str, object]:
    return {
        "source_language": "English",
        "target_language": "Swedish",
        "terms": [
            {"source": "warp drive", "target": "warpdrift"},
            {"source": "crew", "target": "besättning"},
        ],
    }


def parse_payload(payload: object) -> Glossary:
    return parse_glossary(
        json.dumps(payload, ensure_ascii=False),
        source_language="English",
        target_language="Swedish",
    )


def test_loads_utf8_glossary_and_trims_values(tmp_path: Path):
    path = tmp_path / "glossary.json"
    payload = valid_payload()
    payload["source_language"] = " English "
    payload["target_language"] = " Swedish "
    payload["terms"] = [{"source": " café ", "target": " kafé "}]
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    glossary = load_glossary(path, "english", "SWEDISH")

    assert glossary == Glossary(
        source_language="English",
        target_language="Swedish",
        terms=(GlossaryTerm(source="café", target="kafé"),),
    )
    assert glossary_to_dict(glossary) == {
        "source_language": "English",
        "target_language": "Swedish",
        "terms": [{"source": "café", "target": "kafé"}],
    }


def test_glossary_models_are_immutable():
    term = GlossaryTerm("warp drive", "warpdrift")
    glossary = Glossary("English", "Swedish", (term,))

    with pytest.raises(FrozenInstanceError):
        term.target = "motor"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        glossary.target_language = "German"  # type: ignore[misc]


def test_rejects_invalid_json():
    with pytest.raises(GlossaryError, match="Invalid glossary JSON"):
        parse_glossary("{not JSON", "English", "Swedish")


def test_rejects_invalid_utf8(tmp_path: Path):
    path = tmp_path / "glossary.json"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(GlossaryError, match="valid UTF-8"):
        load_glossary(path, "English", "Swedish")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "must be a JSON object"),
        (
            {"target_language": "Swedish", "terms": []},
            "missing required field.*source_language",
        ),
        (
            {"source_language": "English", "terms": []},
            "missing required field.*target_language",
        ),
        (
            {"source_language": "English", "target_language": "Swedish"},
            "missing required field.*terms",
        ),
        (
            {
                "source_language": 1,
                "target_language": "Swedish",
                "terms": [],
            },
            "source_language.*must be a string",
        ),
        (
            {
                "source_language": "English",
                "target_language": False,
                "terms": [],
            },
            "target_language.*must be a string",
        ),
        (
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": {},
            },
            "terms.*must be a JSON list",
        ),
        (
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": ["invalid"],
            },
            "term at index 0 must be a JSON object",
        ),
        (
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": [{"target": "mål"}],
            },
            "missing required field.*source",
        ),
        (
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": [{"source": "source"}],
            },
            "missing required field.*target",
        ),
        (
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": [{"source": 1, "target": "mål"}],
            },
            "source.*must be a string",
        ),
        (
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": [{"source": "source", "target": []}],
            },
            "target.*must be a string",
        ),
        (
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": [],
                "extra": True,
            },
            "unexpected field.*extra",
        ),
        (
            {
                "source_language": "English",
                "target_language": "Swedish",
                "terms": [{"source": "source", "target": "mål", "extra": 1}],
            },
            "unexpected field.*extra",
        ),
    ],
    ids=[
        "non-object",
        "missing-source-language",
        "missing-target-language",
        "missing-terms",
        "source-language-type",
        "target-language-type",
        "terms-type",
        "term-type",
        "missing-source",
        "missing-target",
        "source-type",
        "target-type",
        "root-extra-field",
        "term-extra-field",
    ],
)
def test_rejects_invalid_schema(payload, message):
    with pytest.raises(GlossaryError, match=message):
        parse_payload(payload)


@pytest.mark.parametrize(
    ("source", "target", "message"),
    [
        ("", "mål", "source.*must not be blank"),
        (" \n\t", "mål", "source.*must not be blank"),
        ("source", "", "target.*must not be blank"),
        ("source", "  ", "target.*must not be blank"),
    ],
)
def test_rejects_blank_terms(source, target, message):
    payload = valid_payload()
    payload["terms"] = [{"source": source, "target": target}]

    with pytest.raises(GlossaryError, match=message):
        parse_payload(payload)


def test_rejects_duplicate_source_terms_after_trim_and_case_normalization():
    payload = valid_payload()
    payload["terms"] = [
        {"source": "Warp Drive", "target": "warpdrift"},
        {"source": "  warp drive  ", "target": "annan term"},
    ]

    with pytest.raises(GlossaryError, match="Duplicate glossary source term"):
        parse_payload(payload)


@pytest.mark.parametrize(
    ("source_language", "target_language", "message"),
    [
        ("German", "Swedish", "source language"),
        ("English", "Norwegian", "target language"),
    ],
)
def test_rejects_language_mismatch(source_language, target_language, message):
    with pytest.raises(GlossaryError, match=message):
        parse_glossary(
            json.dumps(valid_payload()),
            source_language,
            target_language,
        )
