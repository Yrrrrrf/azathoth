# ── test · prove ──────────────────────────────────────
[doc('Run the test suite')]
[group('test')]
test *args:
    uv run pytest {{args}}

[doc('Run tests matching NAME')]
[group('test')]
test-one name:
    uv run pytest -k {{name}}

[doc('Run tests with coverage report')]
[group('test')]
cov:
    uv run pytest --cov=azathoth --cov-report=term-missing
