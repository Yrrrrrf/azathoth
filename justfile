# ── Azathoth ──────────────────────────────────────────
#  CI

[doc('Format code')]
[group('CI')]
fmt:
    uvx ruff format .
    # Remove cache dir. Bad practice but ...
    # I prefer to do not add any new hidden files
    rm -rf .ruff_cache
    @echo "✓ Code formatted"

[doc('Lint code')]
[group('CI')]
lint:
    -uvx ruff check .
    rm -rf .ruff_cache
    @echo "✓ Code linted"

[doc('Type-check code')]
[group('CI')]
typecheck:
    uvx ty check
    @echo "✓ Type-checked"

[doc('Full quality gate')]
[group('CI')]
quality: fmt lint typecheck
    @echo "✓ Quality checks passed"

# Build

[doc('Build dist files')]
[group('Build')]
build:
    uv build
