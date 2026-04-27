# ── Azathoth ──────────────────────────────────────────
#  CI

[doc('Format code')]
[group('CI')]
fmt:
    uvx ruff format .
    @echo "✓ Code formatted"

[doc('Lint code')]
[group('CI')]
lint:
    -uvx ruff check .
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
