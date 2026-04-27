import pytest
import json
from pathlib import Path
from azathoth.core.i18n import (
    InlangConfig,
    resolve_paths,
    load_all_translations,
    diff_against_base,
    build_matrix,
    prune_orphans,
    TranslationSet,
    build_prompt,
    parse_llm_response,
    validate_canaries,
    validate_placeholders,
    export_registry,
    import_registry,
)
from azathoth.core.exceptions import TranslationError


@pytest.fixture
def i18n_root() -> Path:
    """Return the absolute path to the i18n fixture root."""
    return Path(__file__).parent.parent.parent / "i18n"


@pytest.fixture
def config_path(i18n_root: Path) -> Path:
    """Return path to settings.json."""
    return i18n_root / "project.inlang" / "settings.json"


def test_parse_inlang_config(config_path: Path):
    """Verify settings.json parsing."""
    config = InlangConfig.from_json(config_path)
    assert config.base_locale == "en"
    assert "es" in config.locales
    assert "ja" in config.locales
    assert config.path_pattern == "./translations/{locale}.json"


def test_resolve_paths(config_path: Path):
    """Verify path resolution for locales."""
    config = InlangConfig.from_json(config_path)
    paths = resolve_paths(config_path, config)

    expected_en = config_path.parent.parent / "translations" / "en.json"
    assert paths["en"] == expected_en
    assert paths["es"].name == "es.json"
    assert paths["ja"].name == "ja.json"


def test_load_all_translations(config_path: Path):
    """Verify loading translation files."""
    config = InlangConfig.from_json(config_path)
    paths = resolve_paths(config_path, config)
    translations = load_all_translations(paths)

    assert "en" in translations
    assert "es" in translations
    assert "ja" in translations

    # Check some known keys from the fixture
    assert translations["en"].messages["hello_world"] == "Hello {name} in English"
    assert translations["es"].messages["hello_world"] == "Hola {name} en español"


def test_diff_against_base():
    """Verify key diffing."""
    base = TranslationSet(locale="en", messages={"a": "1", "b": "2"})
    target = TranslationSet(locale="es", messages={"a": "1", "c": "3"})

    diff = diff_against_base(base, target)
    assert diff.missing_keys == ["b"]
    assert diff.orphan_keys == ["c"]


def test_build_matrix():
    """Verify matrix construction."""
    translations = {
        "en": TranslationSet(locale="en", messages={"a": "1", "b": "2"}),
        "es": TranslationSet(locale="es", messages={"a": "uno", "c": "tres"}),
    }
    locales = ["en", "es"]
    matrix = build_matrix(translations, locales)

    assert "a" in matrix.keys
    assert "b" in matrix.keys
    assert "c" in matrix.keys

    assert matrix.matrix["a"]["en"] == "1"
    assert matrix.matrix["a"]["es"] == "uno"
    assert matrix.matrix["b"]["es"] is None
    assert matrix.matrix["c"]["en"] is None


def test_prune_orphans():
    """Verify orphan key removal."""
    base = TranslationSet(locale="en", messages={"a": "1", "b": "2"})
    target = TranslationSet(locale="es", messages={"a": "1", "c": "3"})

    pruned = prune_orphans(target, base)
    assert "a" in pruned.messages
    assert "c" not in pruned.messages
    assert pruned.messages["a"] == "1"


def test_build_prompt():
    """Verify prompt construction with canaries."""
    locale = "es"
    keys = ["test_key"]
    values = ["Test Value"]
    system, user = build_prompt(locale, keys, values)

    assert "expert English-to-es translator" in system
    assert "curly braces" in system

    user_data = json.loads(user)
    assert len(user_data) == 3  # Canary, Value, Canary
    assert user_data[0] == "Hello"
    assert user_data[1] == "Test Value"
    assert user_data[2] == "Goodbye"


def test_parse_llm_response():
    """Verify LLM response parsing."""
    raw = '["Hola", "Prueba", "Adiós"]'
    parsed = parse_llm_response(raw, 3)
    assert parsed == ["Hola", "Prueba", "Adiós"]

    with pytest.raises(TranslationError):
        parse_llm_response(raw, 2)  # Wrong length


def test_validate_canaries():
    """Verify canary validation."""
    response = ["Hola", "Contenido", "Adiós"]
    assert validate_canaries(response, "es") is True

    with pytest.raises(TranslationError):
        validate_canaries(["Malo", "Contenido", "Adiós"], "es")


def test_validate_placeholders():
    """Verify placeholder detection."""
    source = ["Hello {name}", "Price: {amount}"]
    translated = ["Hola {name}", "Precio: {cantidad}"]

    warnings = validate_placeholders(source, translated)
    assert len(warnings) == 1
    assert warnings[0].key == "index_1"
    assert "{amount}" in warnings[0].expected
    assert "{cantidad}" in warnings[0].actual


def test_registry_roundtrip(tmp_path: Path):
    """Verify registry export and import."""
    translations = {
        "en": TranslationSet(locale="en", messages={"a": "1"}),
        "es": TranslationSet(locale="es", messages={"a": "uno"}),
    }
    matrix = build_matrix(translations, ["en", "es"])

    registry_file = tmp_path / "registry.json"
    export_registry(matrix, registry_file)

    imported = import_registry(registry_file)
    assert imported.locales == matrix.locales
    assert imported.keys == matrix.keys
    assert imported.matrix == matrix.matrix
