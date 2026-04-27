# Implementation Concerns — Azathoth Provider Refactor (Phases 0–7)

> Written after completion of all seven planned phases.
> Current state: **105 tests passing, 0 violations** on `azathoth-architecture-check`.
> Commit: `22f2ca9` (phase 7)

---

## Legend

| Symbol | Severity |
|---|---|
| 🔴 | **Critical** — wrong behaviour in production, silent data loss, or a security concern |
| 🟠 | **Semantic** — works now, but name/contract misleads callers; will cause a bug later |
| 🟡 | **Test gap** — untested code path that carries meaningful risk |
| 🔵 | **Tech debt** — works but is fragile, slow, or harder to extend than it should be |
| ⚪ | **Minor** — convention, style, or readability issue |

---

## 🔴 Critical

### C-1 · `llm_total_timeout` is a per-provider timeout, not a chain budget

**File:** `src/azathoth/core/llm.py` · `src/azathoth/config.py`

```python
# _resolve() — current behaviour
per_provider_timeout = _cfg.llm_total_timeout   # "total"?
...
response = await asyncio.wait_for(p.generate(...), timeout=per_provider_timeout)
```

The field is **named** `llm_total_timeout` and **documented** as "Total wall-clock budget per `generate()` call across the entire chain", but it is used as the **per-provider** timeout.
With 3 providers each allowed 120 s, the real ceiling is 360 s — 3× what the name implies.

**Fix:** Rename to `llm_per_provider_timeout: float` and add a separate `llm_chain_timeout: float` that wraps the entire `_resolve()` call.

---

### C-2 · `ProviderRateLimitError` is defined but never raised

**File:** `src/azathoth/providers/gemini.py` — `_classify_error()`

A `429 Too Many Requests` from the Gemini API falls through to `ProviderUnavailable` (retryable),
causing it to fall through to Ollama — the wrong semantic. Rate limits need backoff, not an immediate fallback.

**Fix:** Add `"429", "rate_limit", "quota"` to a `_RATE_HINTS` tuple and raise `ProviderRateLimitError` there. In `_resolve()`, catch it separately with a short backoff before continuing the chain.

---

### C-3 · `sync` CLI command was silently broken before Phase 7

**File:** `src/azathoth/cli/commands/i18n.py:265`

The `sync` command used `TranslationSet(...)` which was never imported (`F821`). This means `azathoth i18n sync` raised `NameError` at runtime for all users. Caught by `ruff` in EC-7.4 but was **undetected by the test suite** because `cli/commands/i18n.py` has 0% coverage.

**Lesson:** `azathoth-import-check` verifies module-level import health but cannot catch usage of undefined names inside function bodies. `ruff F821` is the right tool here; running it was blocked by the other pre-existing lint errors.

---

### C-4 · Python 3.14-only syntax shipped in a `>=3.11` package

**File:** `src/azathoth/core/ingest.py` (pre-Phase 7)

Six `except A, B:` clauses are valid on Python 3.14 but **SyntaxError** on Python 3.11–3.13 — the entire CI matrix range. Fixed in Phase 7.

**Ongoing risk:** Any new file written on Python 3.14 can silently introduce 3.12/3.11 incompatibilities. Consider adding a cross-version syntax check to CI:
```bash
python3.11 -c "import compileall; compileall.compile_dir('src/', quiet=2)"
```

---

## 🟠 Semantic Mismatches

### S-1 · `_load_providers()` is called on every `_resolve()` invocation

**File:** `src/azathoth/core/llm.py:143`

Python caches imported modules so this is a no-op after the first call, but it re-evaluates the
`import` statement each time and implies providers might change between calls, which they don't.

**Fix:** Add a module-level `_providers_loaded: bool = False` guard.

---

### S-2 · Self-registration creates a hidden call ordering dependency

Both provider modules call `_register(...)` at module import time. The registry is only populated after `_load_providers()` runs inside `_resolve()`. Calling `get_provider("gemini")` directly before `generate()` raises `KeyError`.

**Fix (short term):** Add a lazy trigger to `get_provider()`:
```python
def get_provider(name: str) -> Any:
    if not _PROVIDERS:
        from azathoth.core.llm import _load_providers
        _load_providers()
    ...
```

---

### S-3 · `_classify_error` raises internally but reads like a function that returns

**File:** `src/azathoth/providers/gemini.py`

```python
log.warning("GeminiProvider error ...", ...)
_classify_error(exc)   # raises internally — control never returns here
```

The `-> None` return type is the only signal that this raises. The original `return X from exc` bug (caught in Phase 5) arose from this exact confusion. Debuggers also show the inner raise as the origin.

**Fix:** Make `_classify_error` return the exception and have the caller `raise classified from exc`.

---

## 🟡 Test Gaps

### T-1 · `core/scout.py` has 0% coverage
All 24 lines are untested. No validation that the module even executes correctly.

### T-2 · `core/prompts.py` has 33% coverage
The commit/release prompt templates are the highest-value CLI output. A broken Jinja template would surface only as a generic LLM error.

### T-3 · EC-4.7 (live Ollama smoke test) was permanently skipped
The actual `/api/generate` wire protocol was never validated against a real daemon. Schema drift in Ollama will break `OllamaProvider` silently.

**Recommended:** `@pytest.mark.integration` test gated on `AZATHOTH_OLLAMA_INTEGRATION=1`.

### T-4 · `--provider` CLI flag end-to-end path not tested
EC-4.5 verified `--help` output only. The full path `az commit --provider ollama` → `_sync_generate(..., "ollama")` → `generate(provider="ollama")` → `_resolve(provider="ollama")` was never exercised.

### T-5 · `cli/commands/i18n.py` has 0% effective coverage
As C-3 demonstrated, this allowed a `NameError` to live in production code undetected for an unknown number of releases.

---

## 🔵 Technical Debt

### D-1 · `_PROVIDERS` is unguarded mutable global state
**File:** `src/azathoth/providers/registry.py`

No thread-safety lock. Two threads registering providers simultaneously could corrupt the dict. Tests use an isolation fixture, but it is not `autouse=True` everywhere.

### D-2 · `config = Settings()` instantiated at module import time
`monkeypatch.setenv(...)` in tests must be set before `azathoth.config` is imported. Tests avoid this via careful ordering, but it is fragile.

**Fix:** Lazy singleton `get_config() -> Settings`.

### D-3 · `_ListAwareEnvSource` is a bespoke workaround for pydantic-settings internals
**File:** `src/azathoth/config.py`

The custom `EnvSettingsSource` subclass exists because pydantic-settings v2 calls `decode_complex_value → json.loads()` before validators run. A pydantic-settings upgrade could make it a no-op or double-decode.

**Mitigation:** The existing `test_providers_env_csv` regression test covers this. Keep it alive on every dependency bump.

### D-4 · `azathoth-architecture-check` takes ~500ms for 33 modules
At 100+ modules it will exceed 1 s per commit. Consider caching `ast.parse()` results keyed by `(path, mtime)`.

### D-5 · Late imports inside `_resolve()` hide the `core → tools` dependency
**File:** `src/azathoth/core/llm.py:141`

```python
async def _resolve(...):
    from azathoth.core.tools import build_emulator_system_prompt, ...
```

Invisible to tools that scan only top-level imports (including the architecture check's R2 rule).

### D-6 · `pyright` is advisory in CI (`continue-on-error: true`)
**File:** `.github/workflows/ci.yml`

Advisory steps tend to stay advisory forever. Set a hard deadline (e.g., "before first tagged release") and remove `continue-on-error`.

---

## ⚪ Minor

### M-1 · `az` CLI alias removed without a deprecation notice
The user removed `az = "azathoth.cli.main:app"` from `pyproject.toml`. Shell aliases and docs pointing to `az commit` will fail silently.

### M-2 · Default provider order penalises local-first users
`["gemini", "ollama"]` means a missing API key triggers `ProviderAuthError` (non-retryable) and **halts the chain** before trying Ollama. Local-first users should set `AZATHOTH_LLM_PROVIDERS=ollama,gemini`.

### M-3 · Rate-limit classification asymmetry between providers
Ollama maps HTTP 429 → `ProviderRateLimitError`. Gemini's `_classify_error` does not. The fallback chain behaves differently for rate-limit events depending on which provider fires.

### M-4 · Registry isolation not enforced by autouse fixture in `test_llm.py`
`test_llm.py` bypasses the registry via `monkeypatch.setattr(get_provider, ...)` rather than using the isolation fixture. If a future test modifies `_PROVIDERS` directly, it leaks state into the session.

---

## Summary Table

| ID | Sev | File | One-liner |
|---|---|---|---|
| C-1 | 🔴 | `core/llm.py` + `config.py` | `llm_total_timeout` is per-provider, not chain-total |
| C-2 | 🔴 | `providers/gemini.py` | `ProviderRateLimitError` never raised; 429s fall through wrong |
| C-3 | 🔴 | `cli/commands/i18n.py` | `sync` command was a `NameError` at runtime (fixed P7) |
| C-4 | 🔴 | `core/ingest.py` | Python 3.14-only syntax in `>=3.11` package (fixed P7) |
| S-1 | 🟠 | `core/llm.py` | `_load_providers()` called every invocation, no idempotency guard |
| S-2 | 🟠 | `providers/registry.py` | Self-registration requires going through `generate()` first |
| S-3 | 🟠 | `providers/gemini.py` | `_classify_error` raises internally, misleads readers |
| T-1 | 🟡 | `core/scout.py` | 0% test coverage |
| T-2 | 🟡 | `core/prompts.py` | 33% coverage — prompt templates untested |
| T-3 | 🟡 | `providers/ollama.py` | Live wire protocol never validated (EC-4.7 skipped) |
| T-4 | 🟡 | `cli/commands/workflow.py` | `--provider` flag end-to-end path not tested |
| T-5 | 🟡 | `cli/commands/i18n.py` | 0% CLI command coverage |
| D-1 | 🔵 | `providers/registry.py` | `_PROVIDERS` dict has no thread-safety |
| D-2 | 🔵 | `config.py` | Singleton instantiated at import time |
| D-3 | 🔵 | `config.py` | `_ListAwareEnvSource` workaround for pydantic-settings internals |
| D-4 | 🔵 | `dev/architecture_check.py` | ~500ms cold run; no AST caching |
| D-5 | 🔵 | `core/llm.py` | Late imports hide `core → tools` dependency |
| D-6 | 🔵 | `.github/workflows/ci.yml` | `pyright` advisory (`continue-on-error: true`) |
| M-1 | ⚪ | `pyproject.toml` | `az` alias removed without deprecation notice |
| M-2 | ⚪ | `config.py` | Default provider order penalises local-first users |
| M-3 | ⚪ | `providers/ollama.py` | Rate-limit classification asymmetry vs Gemini |
| M-4 | ⚪ | `tests/core/test_llm.py` | Registry isolation not enforced by autouse fixture |

---

## Recommended Next Actions (Priority Order)

1. **Fix C-1** — Rename the timeout field; add a real chain-level `asyncio.wait_for` around `_resolve()`. 10-line change, high safety value.
2. **Fix C-2** — Add `ProviderRateLimitError` classification in `_classify_error` with a short backoff.
3. **Address T-3** — Write a `@pytest.mark.integration` Ollama test gated on an env var.
4. **Address D-2** — Switch `config` to a lazy singleton to unblock cleaner test isolation.
5. **Fix S-1** — Add `_providers_loaded` guard. Zero risk, eliminates surprise behaviour.
6. **Enforce D-6** — Remove `continue-on-error` from the pyright CI step once existing type errors are cleaned up.
