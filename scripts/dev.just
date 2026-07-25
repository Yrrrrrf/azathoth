# ── dev · loop ────────────────────────────────────────
[doc('Run the CLI')]
[group('dev')]
run *args:
    uv run azathoth {{ args }}

[doc('Build dist files')]
[group('dev')]
build:
    uv build

[doc('Remove build & cache artifacts')]
[group('dev')]
clean:
    rm -rf .ruff_cache .pytest_cache
    @echo "✓ cleaned"
