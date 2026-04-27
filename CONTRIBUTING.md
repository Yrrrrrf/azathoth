# Contributing to Azathoth

> **Single-developer project** — these rules exist to keep the codebase
> verifiable by an autonomous agent as much as by a human.

---

## Quick-start

```bash
# Install dependencies (dev extras)
uv sync --extra dev

# Run the full local validation suite before every commit
uv run azathoth-import-check && \
uv run azathoth-architecture-check && \
uv run ruff check src/ && \
uv run ty check src/ && \
uv run pytest tests/ -q --strict-markers --strict-config
```

---

## Fitness functions

Two automated checks enforce architectural invariants. **Never disable or weaken
them to make a phase pass — fix the code instead.**

### `azathoth-import-check`

```bash
uv run azathoth-import-check          # human-readable; exits 1 on any failure
uv run azathoth-import-check --json   # machine-readable JSON report
uv run python -m azathoth.dev.import_check
```

What it does: walks every submodule under `azathoth.*` via
`pkgutil.walk_packages` and imports each one. Exits non-zero if any
`ImportError` or `SyntaxError` is encountered.

**Why it exists:** the original `core/i18n.py` carried a Python 2-style
`except A, B:` syntax error that silently escaped test collection because the
test file imported only a subset of the module's symbols, leaving the broken
`except` clause unexecuted at collection time. This check catches that entire
class of bug before it can hide in production.

**Run it on every commit** (it takes < 1 second).

### `azathoth-architecture-check`

```bash
uv run azathoth-architecture-check          # human-readable; exits 1 on any violation
uv run azathoth-architecture-check --json   # machine-readable JSON report
uv run python -m azathoth.dev.architecture_check
```

Parses every `.py` file under `src/azathoth/` with `ast` and enforces three
architectural rules:

| Rule                         | What it checks                                                                                                                                                                                                                                      |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **R1: SDK isolation**        | Only `providers/gemini.py` may import from the `google.*` / `genai.*` namespace. Any other module doing so is a violation.                                                                                                                          |
| **R2: Façade boundary**      | `core/llm.py` must contain zero SDK imports at any scope level. Additionally, no file outside `providers/` may do a module-level direct import of a concrete provider implementation (`azathoth.providers.gemini`, `azathoth.providers.ollama`, …). |
| **R3: Provider conformance** | Every non-framework file in `providers/` must self-register and produce an instance that satisfies `isinstance(instance, Provider)`.                                                                                                                |

**Why these rules matter:**

- **R1** prevents the Google SDK from bleeding into unrelated code paths. If
  `core/i18n.py` imports `genai`, rotating the API key requires understanding
  the i18n module.
- **R2** is the "seam" rule: consumer code that calls `generate()` must never
  know _which_ backend handled the request. The façade is the only door.
- **R3** ensures new provider additions don't silently break the plugin
  contract. The registry's own `register()` enforces this at import time, but
  the arch check re-verifies it statically as a double safety net.

**Self-test** — the check must catch deliberate violations:

```bash
# Temporarily inject a violation into cli/main.py, verify it fails, restore
echo 'from azathoth.providers.gemini import GeminiProvider' >> src/azathoth/cli/main.py && \
  (uv run azathoth-architecture-check; rc=$?; git checkout src/azathoth/cli/main.py; [ $rc -ne 0 ])
```

---

## Architectural rules and how they're enforced

The dependency directions are strictly one-way:

```
cli/*  mcp/*
  │       │
  └──┬───┘
     ↓
  core/*          ← only imports from providers.base, providers.registry
     │
     ↓
  providers/base.py   providers/registry.py
             \              /
              ↓            ↓
          providers/<name>.py  ← only imports from providers.base
```

Rules enforced by `azathoth-architecture-check` (R1–R3 above) and by
`azathoth-import-check` (full namespace traversal).

Adding a new provider (`providers/foo.py`) is the only architectural change that
should be routine after Phase 7. The template is `providers/ollama.py`:

1. Implement the `Provider` Protocol (no inheritance required).
2. Call `_register("foo", _factory)` at module bottom.
3. Add `import azathoth.providers.foo` inside `core/llm._load_providers()`.
4. Add `FooSettings` fields to `config.py` (prefixed `foo_*`).
5. Run `azathoth-architecture-check` — must pass with 0 violations.

## Code standards (non-negotiable)

| Rule                                                                        | Rationale                                                      |
| --------------------------------------------------------------------------- | -------------------------------------------------------------- |
| `from __future__ import annotations` at the top of every `.py`              | Consistent forward-ref behaviour across Python 3.11–3.13       |
| Full type hints on every public function                                    | `pyright` checks these in CI                                   |
| `ty check src/` in strict mode                                              | Providers and the LLM façade are the highest-risk surface      |
| `ruff` rulesets `E, F, I, B, RUF, UP, PLR, SIM, ASYNC, FBT, RET`            | Errors, not warnings                                           |
| No `print()` in `src/`                                                      | Use `logging.getLogger(__name__)`                              |
| No bare `except:` or `except Exception:` without re-raise or structured log | Silent failures are defects                                    |
| Pydantic models `frozen=True` by default                                    | Mutability must be justified in a docstring                    |
| `pytest --strict-markers --strict-config`                                   | Undeclared markers fail collection                             |
| ≥ 85 % line coverage for `providers/` and `core/llm.py`, `core/tools.py`    | Enforced by `pytest-cov --fail-under=85` scoped to those paths |

---

## Commit discipline

- **One commit per phase**, not per file.
- Commit message format: `phase N: <phase title>`
- Commit body must list exit-criterion results (pass / fail / skip).

---

## Logging contract

| Level     | What to log                                                                              |
| --------- | ---------------------------------------------------------------------------------------- |
| `DEBUG`   | Successful LLM calls — provider, model, token estimates (first 500 chars of prompt only) |
| `INFO`    | Fallback events — provider name, attempt index, error class                              |
| `WARNING` | Provider errors — error class, first 200 chars of message. **Never log API keys.**       |

---

## Out of scope (do not implement without a new plan)

- A2A agent protocol layer
- Streaming LLM responses
- Multi-modal inputs (image/audio)
- LLM response caching / cost tracking beyond `tiktoken`
- The `scout()` MCP integration
