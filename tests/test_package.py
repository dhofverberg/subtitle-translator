"""Release-facing package tests.

These tests verify packaging metadata, version consistency, prompt resources,
provider-neutral imports, CLI entry points, and extras correctness.
They do not make real API calls.
"""

from __future__ import annotations

import sys
from pathlib import Path


# ── Version consistency ──────────────────────────────────────────────────────


def test_package_version_matches_importlib_metadata():
    """Installed metadata version must equal subtitle_translator.__version__."""
    from importlib.metadata import version as pkg_version

    import subtitle_translator

    assert pkg_version("subtitle-translator") == subtitle_translator.__version__


def test_package_version_is_pep440():
    """The package version must be a valid PEP 440 version string."""
    from importlib.metadata import version as pkg_version
    from packaging.version import Version

    v = pkg_version("subtitle-translator")
    parsed = Version(v)
    assert str(parsed) == v or str(parsed) != ""  # parses without exception


def test_version_module_exposes_version_string():
    from subtitle_translator.version import __version__

    assert isinstance(__version__, str)
    assert __version__  # non-empty


# ── Provider-neutral imports ─────────────────────────────────────────────────


def test_core_import_does_not_require_provider_sdks(monkeypatch):
    """Importing subtitle_translator must not load any provider SDK."""
    # Remove any cached provider modules to test from a clean state.
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("google"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    import subtitle_translator  # noqa: F401

    assert "openai" not in sys.modules
    assert "google.genai" not in sys.modules


def test_version_check_does_not_require_provider_sdks(monkeypatch):
    """Querying the package version must not import provider SDKs."""
    # Remove any already-imported provider modules to simulate a fresh env.
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("google"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    from importlib.metadata import version as pkg_version

    pkg_version("subtitle-translator")

    assert "openai" not in sys.modules
    assert "google.genai" not in sys.modules


def test_batch_module_does_not_import_provider_sdks(monkeypatch):
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("google"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    import subtitle_translator.batch  # noqa: F401

    assert "openai" not in sys.modules
    assert "google.genai" not in sys.modules


def test_models_module_does_not_import_provider_sdks(monkeypatch):
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("google"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    import subtitle_translator.models  # noqa: F401

    assert "openai" not in sys.modules
    assert "google.genai" not in sys.modules


def test_glossary_module_does_not_import_provider_sdks(monkeypatch):
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("google"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    import subtitle_translator.glossary  # noqa: F401

    assert "openai" not in sys.modules
    assert "google.genai" not in sys.modules


def test_prompts_module_does_not_import_provider_sdks(monkeypatch):
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("google"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    import subtitle_translator.prompts  # noqa: F401

    assert "openai" not in sys.modules
    assert "google.genai" not in sys.modules


def test_consistency_module_does_not_import_provider_sdks(monkeypatch):
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("google"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    import subtitle_translator.consistency  # noqa: F401

    assert "openai" not in sys.modules
    assert "google.genai" not in sys.modules


# ── Packaged prompt resources ─────────────────────────────────────────────────


def test_prompt_resource_loads_from_installed_package():
    from importlib.resources import files

    resources = files("subtitle_translator").joinpath("resources")
    text = resources.joinpath("prompt.txt").read_text(encoding="utf-8")
    assert text.strip()


def test_batch_prompt_resource_loads_from_installed_package():
    from importlib.resources import files

    resources = files("subtitle_translator").joinpath("resources")
    text = resources.joinpath("batch_prompt.txt").read_text(encoding="utf-8")
    assert text.strip()


def test_consistency_prompt_resource_loads_from_installed_package():
    from importlib.resources import files

    resources = files("subtitle_translator").joinpath("resources")
    text = resources.joinpath("consistency_prompt.txt").read_text(encoding="utf-8")
    assert text.strip()


# ── pyproject.toml metadata ───────────────────────────────────────────────────


def test_package_metadata_name():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    assert meta["Name"] == "subtitle-translator"


def test_package_metadata_has_description():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    assert meta["Summary"]


def test_package_metadata_requires_python():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    requires_python = meta["Requires-Python"]
    assert requires_python, "Requires-Python must be set"
    assert "3.11" in requires_python or ">=" in requires_python


def test_package_metadata_license():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    assert meta["License-Expression"] or meta["License"], "License metadata must be set"


def test_package_metadata_has_classifiers():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    classifiers = meta.get_all("Classifier") or []
    assert any("Python" in c for c in classifiers), "Python classifiers must be present"
    # Development status classifier must be present
    assert any("Development Status" in c for c in classifiers), (
        "Development Status classifier must be present"
    )


def test_package_metadata_has_console_entry_point():
    from importlib.metadata import entry_points

    eps = entry_points(group="console_scripts")
    names = [ep.name for ep in eps]
    assert "subtitle-translator" in names, "console_scripts entry point must exist"


def test_package_metadata_has_project_url():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    urls = meta.get_all("Project-URL") or []
    assert urls, "At least one Project-URL must be set"


# ── Optional extras ───────────────────────────────────────────────────────────


def test_optional_extras_exist():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    requires = meta.get_all("Requires-Dist") or []
    extra_names = {
        req.split("; extra ==")[-1].strip().strip('"').strip("'")
        for req in requires
        if "extra ==" in req
    }
    assert "openai" in extra_names, "openai extra must be declared"
    assert "gemini" in extra_names, "gemini extra must be declared"
    assert "all" in extra_names, "all extra must be declared"
    assert "dev" in extra_names, "dev extra must be declared"


def test_openai_sdk_is_in_openai_extra():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    requires = meta.get_all("Requires-Dist") or []
    openai_deps = [r for r in requires if "openai" in r.casefold() and "extra ==" in r]
    assert openai_deps, "openai SDK must be in the openai extra"
    assert any('"openai"' in r or "'openai'" in r for r in openai_deps), (
        "openai SDK must be in the 'openai' extra specifically"
    )


def test_gemini_sdk_is_in_gemini_extra():
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    requires = meta.get_all("Requires-Dist") or []
    gemini_deps = [r for r in requires if "google-genai" in r.casefold() and "extra ==" in r]
    assert gemini_deps, "google-genai SDK must be in the gemini extra"
    assert any('"gemini"' in r or "'gemini'" in r for r in gemini_deps), (
        "google-genai SDK must be in the 'gemini' extra specifically"
    )


def test_provider_sdks_are_not_mandatory_dependencies():
    """Provider SDKs must not appear as unconditional (non-extra) dependencies."""
    from importlib.metadata import metadata

    meta = metadata("subtitle-translator")
    requires = meta.get_all("Requires-Dist") or []
    unconditional = [r for r in requires if "extra ==" not in r]
    sdk_names = ("openai", "google-genai")
    for dep in unconditional:
        for sdk in sdk_names:
            assert sdk not in dep.casefold(), (
                f"Provider SDK '{sdk}' must not be a mandatory dependency: {dep}"
            )


# ── CLI entry point ───────────────────────────────────────────────────────────


def test_cli_app_is_importable():
    from subtitle_translator.cli import app

    assert app is not None


def test_cli_version_option_exists():
    """The --version flag must be available on the CLI app."""
    from click.testing import CliRunner

    from subtitle_translator.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "subtitle-translator" in result.output
    # Version string should appear in the output
    from importlib.metadata import version as pkg_version

    assert pkg_version("subtitle-translator") in result.output


def test_cli_help_works_without_provider_sdks(monkeypatch):
    """--help must succeed without any provider SDK being installed."""
    for mod in list(sys.modules):
        if mod == "openai" or mod.startswith("google"):
            monkeypatch.delitem(sys.modules, mod, raising=False)

    from click.testing import CliRunner

    from subtitle_translator.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "translate" in result.output.lower()


# ── Source files sanity ────────────────────────────────────────────────────────


def test_readme_exists():
    readme = Path(__file__).parent.parent / "README.md"
    assert readme.exists(), "README.md must exist"
    assert readme.stat().st_size > 0, "README.md must not be empty"


def test_changelog_exists():
    changelog = Path(__file__).parent.parent / "CHANGELOG.md"
    assert changelog.exists(), "CHANGELOG.md must exist"


def test_contributing_exists():
    contributing = Path(__file__).parent.parent / "CONTRIBUTING.md"
    assert contributing.exists(), "CONTRIBUTING.md must exist"


def test_security_exists():
    security = Path(__file__).parent.parent / "SECURITY.md"
    assert security.exists(), "SECURITY.md must exist"


def test_license_exists():
    license_file = Path(__file__).parent.parent / "LICENSE"
    assert license_file.exists(), "LICENSE must exist"


def test_no_local_absolute_paths_in_pyproject():
    """pyproject.toml must not contain Windows or Unix absolute developer paths."""
    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    content = pyproject.read_text(encoding="utf-8")
    import re

    # Match C:\Users\, /home/, /Users/ etc.
    pattern = re.compile(r"(?:C:\\|D:\\|/home/|/Users/)", re.IGNORECASE)
    assert not pattern.search(content), (
        "pyproject.toml must not contain absolute local filesystem paths"
    )
