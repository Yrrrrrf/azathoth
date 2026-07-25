# ── test · prove ──────────────────────────────────────
[doc('Verify every module imports cleanly')]
[group('test')]
imports:
    uv run python -m azathoth.dev.import_check

[doc('Verify the architecture rules R1-R8 + B1')]
[group('test')]
arch:
    uv run python -m azathoth.dev.architecture_check

[doc('Run the test suite')]
[group('test')]
test *args: imports arch
    uv run pytest {{args}}

[doc('Run tests matching NAME')]
[group('test')]
test-one name:
    uv run pytest -k {{name}}

[doc('Run tests with coverage report')]
[group('test')]
cov:
    uv run pytest --cov=azathoth --cov-report=term-missing --cov-fail-under=85
