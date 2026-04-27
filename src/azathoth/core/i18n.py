import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field

from azathoth.core.exceptions import ConfigParseError, I18nError, TranslationError
from azathoth.core.llm import generate, LLMError

# Known translations for "Hello" and "Goodbye" for canary validation
CANARY_TRANSLATIONS = {
    "es": {"hello": "Hola", "goodbye": "Adiós"},
    "fr": {"hello": "Bonjour", "goodbye": "Au revoir"},
    "de": {"hello": "Hallo", "goodbye": "Auf Wiedersehen"},
    "it": {"hello": "Ciao", "goodbye": "Arrivederci"},
    "pt": {"hello": "Olá", "goodbye": "Adeus"},
    "ru": {"hello": "Привет", "goodbye": "До свидания"},
    "hi": {"hello": "नमस्ते", "goodbye": "अलविदा"},
    "ar": {"hello": "مرحباً", "goodbye": "وداعاً"},
    "zh": {"hello": "你好", "goodbye": "再见"},
    "ja": {"hello": "こんにちは", "goodbye": "さようなら"},
    "ko": {"hello": "안녕하세요", "goodbye": "안녕히 가세요"},
    "vi": {"hello": "Xin chào", "goodbye": "Tạm biệt"},
}


class InlangConfig(BaseModel):
    """Pydantic model for project.inlang/settings.json."""

    base_locale: str = Field(alias="baseLocale")
    locales: List[str]
    path_pattern: str = Field(alias="plugin.inlang.messageFormat")

    @classmethod
    def from_json(cls, path: Path) -> "InlangConfig":
        """Parse settings.json and extract relevant fields."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # extract the path pattern from the plugin config
            plugin_key = "plugin.inlang.messageFormat"
            if plugin_key not in data or "pathPattern" not in data[plugin_key]:
                raise ConfigParseError(f"Missing {plugin_key}.pathPattern in {path}")

            return cls(
                baseLocale=data["baseLocale"],
                locales=data["locales"],
                **{plugin_key: data[plugin_key]["pathPattern"]},
            )
        except (json.JSONDecodeError, KeyError) as e:
            raise ConfigParseError(f"Failed to parse inlang config at {path}: {str(e)}")


class TranslationSet(BaseModel):
    """Represents a set of translations for a specific locale."""

    locale: str
    messages: Dict[str, str]


class TranslationDiff(BaseModel):
    """Difference between base and target translations."""

    locale: str
    missing_keys: List[str]
    orphan_keys: List[str]


class TranslationMatrix(BaseModel):
    """Key -> Map of locale to value."""

    locales: List[str]
    keys: List[str]
    matrix: Dict[str, Dict[str, Optional[str]]]


class PlaceholderWarning(BaseModel):
    """Warning for missing or mismatched placeholders."""

    key: str
    expected: Set[str]
    actual: Set[str]


def resolve_paths(config_path: Path, config: InlangConfig) -> Dict[str, Path]:
    """Resolve locale file paths based on the pathPattern in config."""
    # settings.json is in project.inlang/settings.json
    # paths are relative to the parent of project.inlang
    root = config_path.parent.parent

    paths = {}
    for locale in config.locales:
        path_str = config.path_pattern.replace("{locale}", locale)
        paths[locale] = root / path_str

    return paths


def load_all_translations(paths: Dict[str, Path]) -> Dict[str, TranslationSet]:
    """Load all translation files into memory."""
    translations = {}
    for locale, path in paths.items():
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Filter out $schema and other non-translation keys if they exist
                    messages = {k: v for k, v in data.items() if not k.startswith("$")}
                    translations[locale] = TranslationSet(
                        locale=locale, messages=messages
                    )
            except (json.JSONDecodeError, OSError):
                translations[locale] = TranslationSet(locale=locale, messages={})
        else:
            translations[locale] = TranslationSet(locale=locale, messages={})
    return translations


def diff_against_base(base: TranslationSet, target: TranslationSet) -> TranslationDiff:
    """Identify missing and orphan keys compared to base locale."""
    base_keys = set(base.messages.keys())
    target_keys = set(target.messages.keys())

    missing = sorted(list(base_keys - target_keys))
    orphans = sorted(list(target_keys - base_keys))

    return TranslationDiff(
        locale=target.locale, missing_keys=missing, orphan_keys=orphans
    )


def build_matrix(
    translations: Dict[str, TranslationSet], locales: List[str]
) -> TranslationMatrix:
    """Construct the master registry matrix."""
    # Union of all keys from all sets, but primarily driven by base if available
    all_keys = set()
    for ts in translations.values():
        all_keys.update(ts.messages.keys())

    sorted_keys = sorted(list(all_keys))
    matrix_data = {}

    for key in sorted_keys:
        matrix_data[key] = {
            locale: translations[locale].messages.get(key) for locale in locales
        }

    return TranslationMatrix(locales=locales, keys=sorted_keys, matrix=matrix_data)


def prune_orphans(target: TranslationSet, base: TranslationSet) -> TranslationSet:
    """Remove keys from target that do not exist in base."""
    base_keys = set(base.messages.keys())
    pruned_messages = {k: v for k, v in target.messages.items() if k in base_keys}
    return TranslationSet(locale=target.locale, messages=pruned_messages)


def build_prompt(
    locale: str,
    keys: list[str],
    values: list[str],
    sample_pairs: list[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """Construct system and user prompt for translation."""

    system_prompt = f"""You are an expert English-to-{locale} translator for a software project.
CRITICAL: Any text inside curly braces `{{...}}` is a code variable. You MUST preserve it exactly as-is in English. 
Never translate, remove, rename, or reorder the content inside `{{}}`. 
Example: `{{count}} tasks remaining` -> `{{count}} tareas restantes` (NOT `{{cantidad}} tareas restantes`).

Return ONLY a JSON array of translated strings in the exact same order as the input array.
Do not include any other text or explanation."""

    if sample_pairs:
        samples_text = "\n".join([f"'{k}': '{v}'" for k, v in sample_pairs])
        system_prompt += (
            f"\n\nExisting translations for style reference:\n{samples_text}"
        )

    # Inject canaries at index 0 and -1
    canary_hello = ("__canary_hello", "Hello")
    canary_goodbye = ("__canary_goodbye", "Goodbye")

    full_values = [canary_hello[1]] + values + [canary_goodbye[1]]

    user_message = json.dumps(full_values, ensure_ascii=False)

    return system_prompt, user_message


def parse_llm_response(raw_json: str, expected_count: int) -> list[str]:
    """Validate JSON array length and format."""
    try:
        data = json.loads(raw_json)
        if not isinstance(data, list):
            raise TranslationError("LLM response is not a JSON array")
        if len(data) != expected_count:
            raise TranslationError(
                f"LLM response length mismatch: expected {expected_count}, got {len(data)}"
            )
        return data
    except json.JSONDecodeError as e:
        raise TranslationError(f"Failed to decode LLM response: {str(e)}")


def validate_canaries(response_values: list[str], locale: str) -> bool:
    """Check canary values at index 0 and -1 against known translations."""
    if locale not in CANARY_TRANSLATIONS:
        return True  # Skip if we don't know the canaries for this locale

    expected = CANARY_TRANSLATIONS[locale]
    actual_hello = response_values[0].lower()
    actual_goodbye = response_values[-1].lower()

    # Simple check: does the response contain the expected canary word?
    hello_match = (
        expected["hello"].lower() in actual_hello
        or actual_hello in expected["hello"].lower()
    )
    goodbye_match = (
        expected["goodbye"].lower() in actual_goodbye
        or actual_goodbye in expected["goodbye"].lower()
    )

    if not (hello_match and goodbye_match):
        raise TranslationError(
            f"Canary validation failed for {locale}. Expected '{expected['hello']}' and '{expected['goodbye']}', got '{response_values[0]}' and '{response_values[-1]}'"
        )

    return True


def validate_placeholders(
    source_values: list[str], translated_values: list[str]
) -> list[PlaceholderWarning]:
    """Extract {...} tokens from source, verify presence in translation."""
    placeholder_regex = re.compile(r"\{[^}]+\}")
    warnings = []

    for i, (src, trans) in enumerate(zip(source_values, translated_values)):
        src_placeholders = set(placeholder_regex.findall(src))
        trans_placeholders = set(placeholder_regex.findall(trans))

        if src_placeholders != trans_placeholders:
            warnings.append(
                PlaceholderWarning(
                    key=f"index_{i}",
                    expected=src_placeholders,
                    actual=trans_placeholders,
                )
            )

    return warnings


async def translate_locale(
    locale: str,
    keys: list[str],
    values: list[str],
    sample_pairs: list[tuple[str, str]] | None = None,
) -> list[str]:
    """Full pipeline for a single locale."""
    if not keys:
        return []

    system, user = build_prompt(locale, keys, values, sample_pairs)

    try:
        raw_response = await generate(system, user, json_mode=True)
        # expected_count = len(keys) + 2 (canaries)
        response_values = parse_llm_response(raw_response, len(keys) + 2)

        validate_canaries(response_values, locale)

        # Strip canaries
        clean_values = response_values[1:-1]

        return clean_values

    except (LLMError, TranslationError) as e:
        raise TranslationError(f"Translation failed for {locale}: {str(e)}")


def merge_translations(
    existing: TranslationSet, new_keys: list[str], new_values: list[str]
) -> TranslationSet:
    """Merge new translations into existing set."""
    updated_messages = dict(existing.messages)
    for k, v in zip(new_keys, new_values):
        updated_messages[k] = v
    return TranslationSet(locale=existing.locale, messages=updated_messages)


def write_translations(path: Path, translations: TranslationSet):
    """Write translations back to JSON file."""
    # Preserve $schema if it exists
    existing_data = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # Update with new messages, keeping $schema
    final_data = {k: v for k, v in existing_data.items() if k.startswith("$")}
    final_data.update(translations.messages)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(final_data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def export_registry(matrix: TranslationMatrix, output: Path, fmt: str = "json") -> None:
    """Write the master registry to a file."""
    if fmt == "json":
        data = {
            "__version": "1.0",
            "locales": matrix.locales,
            "keys": matrix.keys,
            "translations": matrix.matrix,
        }
        with open(output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
    elif fmt == "py":
        with open(output, "w", encoding="utf-8") as f:
            f.write("REGISTRY = ")
            f.write(
                str(
                    {
                        "locales": matrix.locales,
                        "keys": matrix.keys,
                        "translations": matrix.matrix,
                    }
                )
            )
            f.write("\n")


def import_registry(path: Path) -> TranslationMatrix:
    """Read the master registry from a JSON file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle both 'matrix' and 'translations' for backward compatibility during development
        matrix_data = data.get("translations") or data.get("matrix")

        return TranslationMatrix(
            locales=data["locales"], keys=data["keys"], matrix=matrix_data
        )
    except (json.JSONDecodeError, KeyError, IOError) as e:
        raise I18nError(f"Failed to import registry: {str(e)}")
