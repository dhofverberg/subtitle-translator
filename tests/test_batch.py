import json
from dataclasses import FrozenInstanceError

import pytest

from subtitle_translator.batch import (
    BatchItem,
    BatchProtocolError,
    BatchTranslation,
    parse_batch_response,
    serialize_batch,
)


def test_batch_models_are_immutable():
    item = BatchItem(id=1, text="Hello")
    translation = BatchTranslation(id=1, text="Hej")

    with pytest.raises(FrozenInstanceError):
        item.text = "Goodbye"  # type: ignore[misc]

    with pytest.raises(FrozenInstanceError):
        translation.text = "Adjö"  # type: ignore[misc]


def test_serialize_batch_preserves_order_keys_multiline_and_unicode():
    items = [
        BatchItem(id=2, text="Första raden\nAndra raden 👋"),
        BatchItem(id=1, text="Nästa"),
    ]

    serialized = serialize_batch(items)

    assert json.loads(serialized) == [
        {"id": 2, "text": "Första raden\nAndra raden 👋"},
        {"id": 1, "text": "Nästa"},
    ]
    assert "Första" in serialized
    assert "👋" in serialized
    assert "\\u00f6" not in serialized


def test_parse_batch_response_preserves_expected_order():
    expected = [
        BatchItem(id=1, text="First\nline"),
        BatchItem(id=2, text="Second"),
    ]
    response = json.dumps(
        [
            {"id": 2, "text": "Andra 👋"},
            {"id": 1, "text": "Första\nraden"},
        ],
        ensure_ascii=False,
    )

    translations = parse_batch_response(response, expected)

    assert translations == [
        BatchTranslation(id=1, text="Första\nraden"),
        BatchTranslation(id=2, text="Andra 👋"),
    ]


def test_parse_batch_response_rejects_invalid_json():
    with pytest.raises(BatchProtocolError, match="Invalid JSON response"):
        parse_batch_response("not JSON", [])


def test_parse_batch_response_rejects_non_list_top_level():
    with pytest.raises(BatchProtocolError, match="must be a JSON list"):
        parse_batch_response('{"id": 1, "text": "Hej"}', [BatchItem(1, "Hello")])


def test_parse_batch_response_rejects_missing_items():
    expected = [BatchItem(1, "One"), BatchItem(2, "Two")]

    with pytest.raises(BatchProtocolError, match="Expected 2 translated items, received 1"):
        parse_batch_response('[{"id": 1, "text": "Ett"}]', expected)


def test_parse_batch_response_rejects_extra_items():
    expected = [BatchItem(1, "One")]

    with pytest.raises(BatchProtocolError, match="Expected 1 translated items, received 2"):
        parse_batch_response(
            '[{"id": 1, "text": "Ett"}, {"id": 2, "text": "Två"}]',
            expected,
        )


def test_parse_batch_response_rejects_duplicate_ids():
    expected = [BatchItem(1, "One"), BatchItem(2, "Two")]
    response = '[{"id": 1, "text": "Ett"}, {"id": 1, "text": "Ett igen"}]'

    with pytest.raises(BatchProtocolError, match="Duplicate translation ID: 1"):
        parse_batch_response(response, expected)


def test_parse_batch_response_rejects_unknown_ids():
    expected = [BatchItem(1, "One"), BatchItem(2, "Two")]
    response = '[{"id": 1, "text": "Ett"}, {"id": 3, "text": "Tre"}]'

    with pytest.raises(BatchProtocolError, match="Unknown translation ID: 3"):
        parse_batch_response(response, expected)


@pytest.mark.parametrize(
    ("response", "missing_field"),
    [
        ('[{"text": "Hej"}]', "id"),
        ('[{"id": 1}]', "text"),
    ],
)
def test_parse_batch_response_rejects_missing_fields(response, missing_field):
    with pytest.raises(BatchProtocolError, match=f"missing required field '{missing_field}'"):
        parse_batch_response(response, [BatchItem(1, "Hello")])


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ('["not an object"]', "must be a JSON object"),
        ('[{"id": "1", "text": "Hej"}]', "field 'id' must be an integer"),
        ('[{"id": true, "text": "Hej"}]', "field 'id' must be an integer"),
        ('[{"id": 1, "text": 42}]', "field 'text' must be a string"),
    ],
)
def test_parse_batch_response_rejects_incorrect_field_types(response, message):
    with pytest.raises(BatchProtocolError, match=message):
        parse_batch_response(response, [BatchItem(1, "Hello")])


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_parse_batch_response_rejects_blank_translation(text):
    response = json.dumps([{"id": 1, "text": text}])

    with pytest.raises(BatchProtocolError, match="must not be blank"):
        parse_batch_response(response, [BatchItem(1, "Hello")])


def test_parse_batch_response_rejects_unexpected_fields():
    response = '[{"id": 1, "text": "Hej", "note": "extra"}]'

    with pytest.raises(BatchProtocolError, match="unexpected fields: note"):
        parse_batch_response(response, [BatchItem(1, "Hello")])
