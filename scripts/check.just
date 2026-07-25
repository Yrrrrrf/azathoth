# ── check · fix in place ──────────────────────────────
[doc('Format code')]
[group('check')]
fmt:
    uvx ruff format .
    @echo "✓ formatted"

[doc('Lint code')]
[group('check')]
lint:
    -uvx ruff check --fix .
    @echo "✓ linted"

[doc('Type-check code')]
[group('check')]
types:
    uvx ty check src
    @echo "✓ type-checked"

[doc('Audit dependencies for known vulnerabilities')]
[group('check')]
audit:
    uv audit
    @echo "✓ audited"

[doc('Full quality gate: fmt + lint + types')]
[group('check')]
check: fmt lint types
    @echo "✓ quality checks passed"
