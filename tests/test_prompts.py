from subtitle_translator.prompts import (
    build_batch_prompt,
    build_prompt,
    load_batch_prompt_template,
    load_prompt_template,
)


def test_load_prompt_template():
    prompt = load_prompt_template()

    assert "{source_language}" in prompt
    assert "{target_language}" in prompt


def test_build_prompt_inserts_languages():
    prompt = build_prompt("English", "Swedish")

    assert "English" in prompt
    assert "Swedish" in prompt
    assert "{source_language}" not in prompt
    assert "{target_language}" not in prompt


def test_load_batch_prompt_template():
    prompt = load_batch_prompt_template()

    assert "{source_language}" in prompt
    assert "{target_language}" in prompt


def test_build_batch_prompt_inserts_languages_and_json_protocol():
    prompt = build_batch_prompt("English", "Swedish")

    assert "English" in prompt
    assert "Swedish" in prompt
    assert "{source_language}" not in prompt
    assert "{target_language}" not in prompt
    assert "valid JSON only" in prompt
    assert "top-level JSON array" in prompt
    assert "exactly one output object" in prompt
    assert 'only the keys "id" and "text"' in prompt
    assert "id unchanged" in prompt
    assert "code fences" in prompt
    assert "commentary" in prompt
    assert "line breaks" in prompt
    assert "approved target term" in prompt
    assert "grammatical inflection" in prompt
    assert "substitute synonyms" in prompt
    assert "normal translation quality" in prompt
    assert '"glossary", "context", and' in prompt
    assert "read-only reference material" in prompt
    assert "Translate only the current entries" in prompt
    assert "identity, relationships" in prompt
    assert "ambiguous choices" in prompt
    assert "glossary rules take precedence" in prompt
    assert "untrusted reference data" in prompt
    assert "every current item and nothing else" in prompt
