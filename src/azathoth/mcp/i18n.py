from pathlib import Path
from fastmcp import FastMCP

from azathoth.core.i18n import (
    InlangConfig,
    resolve_paths,
    load_all_translations,
    diff_against_base,
    translate_locale,
    merge_translations,
    write_translations,
    build_matrix,
)

mcp = FastMCP("azathoth-i18n")


@mcp.tool()
async def audit_project(settings_path: str) -> str:
    """Audit the translation coverage of a project.

    Args:
        settings_path: Absolute path to project.inlang/settings.json
    """
    path = Path(settings_path)
    config = InlangConfig.from_json(path)
    paths = resolve_paths(path, config)
    translations = load_all_translations(paths)

    matrix = build_matrix(translations, config.locales)

    report = [f"i18n Audit for {settings_path}"]
    report.append("-" * 40)

    for key in matrix.keys:
        status = []
        for locale in config.locales:
            val = matrix.matrix[key][locale]
            status.append(f"{locale}: {'✓' if val else '✗'}")
        report.append(f"{key}: {' | '.join(status)}")

    report.append("-" * 40)
    totals = []
    for locale in config.locales:
        count = sum(1 for k in matrix.keys if matrix.matrix[k][locale])
        totals.append(f"{locale}: {count}/{len(matrix.keys)}")
    report.append(f"TOTALS: {' | '.join(totals)}")

    return "\n".join(report)


@mcp.tool()
async def translate_project(settings_path: str, full: bool = False) -> str:
    """Translate missing keys in a project using AI.

    Args:
        settings_path: Absolute path to project.inlang/settings.json
        full: If True, retranslate all keys.
    """
    path = Path(settings_path)
    config = InlangConfig.from_json(path)
    paths = resolve_paths(path, config)
    translations = load_all_translations(paths)

    base_locale = config.base_locale
    base_set = translations[base_locale]
    target_locales = [loc for loc in config.locales if loc != base_locale]

    results_summary = []

    for locale in target_locales:
        target_set = translations[locale]
        diff = diff_against_base(base_set, target_set)

        keys_to_translate = diff.missing_keys
        if full:
            keys_to_translate = list(base_set.messages.keys())

        if not keys_to_translate:
            results_summary.append(f"{locale}: Already up to date.")
            continue

        values_to_translate = [base_set.messages[k] for k in keys_to_translate]

        # Style samples
        samples = []
        existing_keys = [
            k for k in base_set.messages.keys() if k in target_set.messages
        ]
        for k in existing_keys[:5]:
            samples.append((base_set.messages[k], target_set.messages[k]))

        try:
            new_values = await translate_locale(
                locale, keys_to_translate, values_to_translate, samples
            )
            new_set = merge_translations(target_set, keys_to_translate, new_values)
            write_translations(paths[locale], new_set)
            results_summary.append(
                f"{locale}: Translated {len(keys_to_translate)} keys."
            )
        except Exception as e:
            results_summary.append(f"{locale}: Failed - {str(e)}")

    return "\n".join(results_summary)
