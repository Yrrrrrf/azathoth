# Azathoth i18n Translation Automation Guide

This guide covers the usage of the `az i18n` command suite for automated
internationalization management.

## Commands Overview

The `i18n` subcommand group provides four primary tools:

| Command     | Purpose                                                      |
| ----------- | ------------------------------------------------------------ |
| `audit`     | Visualizes translation coverage across all locales.          |
| `translate` | Uses AI to translate missing or stale keys.                  |
| `export`    | Consolidates all translations into a single master registry. |
| `sync`      | Updates individual locale files from a master registry.      |

---

## 1. Audit Coverage

Before translating, use `audit` to see what's missing.

```bash
az i18n audit path/to/project.inlang/settings.json
```

**What it does:**

- Reads `settings.json` to find your base locale and target languages.
- Displays a Rich table with ✓ (green) for present keys and ✗ (red) for missing
  ones.
- Shows total coverage percentages per locale at the bottom.

---

## 2. AI Translation

The core feature for automating translations.

```bash
# Basic usage (translates missing keys)
az i18n translate path/to/project.inlang/settings.json

# Dry run (preview changes without writing to files)
az i18n translate path/to/project.inlang/settings.json --dry-run

# Force re-translation of all keys
az i18n translate path/to/project.inlang/settings.json --full

# Prune orphan keys (remove keys from target files that don't exist in base)
az i18n translate path/to/project.inlang/settings.json --prune
```

**Key Features:**

- **Canary Validation:** Verifies translation integrity using hidden "canary"
  pairs.
- **Placeholder Preservation:** Ensures `{count}`, `{name}`, etc., are preserved
  verbatim.
- **Style Context:** Uses existing translations as few-shot examples for
  consistent tone.
- **Parallel Processing:** Translates all languages simultaneously for maximum
  speed.

---

## 3. Master Registry Management

Consolidate translations into one file for bulk editing or review.

### Exporting

```bash
# Export to JSON (default)
az i18n export path/to/project.inlang/settings.json --output registry.json

# Export to Python dictionary format
az i18n export path/to/project.inlang/settings.json --format py --output registry.py
```

### Syncing

If you've edited the `registry.json` manually or want to restore files:

```bash
az i18n sync registry.json path/to/project.inlang/settings.json
```

---

## Typical Workflow

1. **Check coverage:** `az i18n audit ...`
2. **Auto-translate:** `az i18n translate ...`
3. **Verify results:** `az i18n audit ...` (should be all green ✓)
4. **Commit changes:** `az workflow commit` (i18n commands never commit for you)

## Troubleshooting

- **503 Unavailable:** The Gemini model is under high demand. Try again in a few
  minutes.
- **Canary validation failed:** The LLM output was malformed or incorrect. The
  tool will skip the affected locale to prevent file corruption.
- **Placeholder mismatch:** If a translated value is missing a variable like
  `{count}`, the tool will fall back to the English original and warn you.
