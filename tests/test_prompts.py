from subtitle_translator.prompts import build_prompt, load_prompt_template


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
