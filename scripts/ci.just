# ── ci · automate + guard ─────────────────────────────
[doc('The one thing a PR must pass: check + test')]
[group('ci')]
ci: check test
    @echo "✓ ci passed"

[doc('Commit staged work, but only on a green tree')]
[group('ci')]
commit msg: ci
    git add -A
    git commit -m {{msg}}
