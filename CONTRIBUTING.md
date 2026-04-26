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
uv run ruff check src/ && \
uv run pyright src/azathoth/ && \
uv run pytest tests/ -q --strict-markers --strict-config
```

---

## Fitness functions

Two automated checks enforce architectural invariants. **Never disable or
weaken them to make a phase pass — fix the code instead.**

### `azathoth-import-check`

```bash
uv run azathoth-import-check          # human-readable; exits 1 on any failure
uv run azathoth-import-check --json   # machine-readable JSON report
uv run python -m azathoth.dev.import_check
```

What it does: walks every submodule under `azathoth.*` via
`pkgutil.walk_packages` and imports each one.  Exits non-zero if any
`ImportError` or `SyntaxError` is encountered.

**Why it exists:** the original `core/i18n.py` carried a Python 2-style
`except A, B:` syntax error that silently escaped test collection because
the test file imported only a subset of the module's symbols, leaving the
broken `except` clause unexecuted at collection time.  This check catches
that entire class of bug before it can hide in production.

**Run it on every commit** (it takes < 1 second).

### `azathoth-architecture-check` *(coming in Phase 7)*

Parses every `.py` file under `src/azathoth/` with `ast` and verifies the
dependency-direction rules from the architecture spec:

- `cli/*` and `mcp/*` must not import concrete provider modules
- `core/*` (except `core/llm.py`) must not import from `providers/*`
- `providers/<name>.py` must not import from any sibling provider
- `providers/*` must not import from `cli/*` or `mcp/*`

---

## Code standards (non-negotiable)

| Rule | Rationale |
|------|-----------|
| `from __future__ import annotations` at the top of every `.py` | Consistent forward-ref behaviour across Python 3.11–3.13 |
| Full type hints on every public function | `pyright` checks these in CI |
| `pyright --strict` for `providers/` and `core/llm.py`, `core/tools.py` | Providers and the LLM façade are the highest-risk surface |
| `ruff` rulesets `E, F, I, B, RUF, UP, PLR, SIM, ASYNC, FBT, RET` | Errors, not warnings |
| No `print()` in `src/` | Use `logging.getLogger(__name__)` |
| No bare `except:` or `except Exception:` without re-raise or structured log | Silent failures are defects |
| Pydantic models `frozen=True` by default | Mutability must be justified in a docstring |
| `pytest --strict-markers --strict-config` | Undeclared markers fail collection |
| ≥ 85 % line coverage for `providers/` and `core/llm.py`, `core/tools.py` | Enforced by `pytest-cov --fail-under=85` scoped to those paths |

---

## Commit discipline

- **One commit per phase**, not per file.
- Commit message format: `phase N: <phase title>`
- Commit body must list exit-criterion results (pass / fail / skip).

---

## Logging contract

| Level | What to log |
|-------|-------------|
| `DEBUG` | Successful LLM calls — provider, model, token estimates (first 500 chars of prompt only) |
| `INFO`  | Fallback events — provider name, attempt index, error class |
| `WARNING` | Provider errors — error class, first 200 chars of message. **Never log API keys.** |

---

## Out of scope (do not implement without a new plan)

- A2A agent protocol layer
- Streaming LLM responses
- Multi-modal inputs (image/audio)
- LLM response caching / cost tracking beyond `tiktoken`
- The `scout()` MCP integration
