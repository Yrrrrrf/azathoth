# Azathoth — Plan 2: First-Run UX Hardening + ty Migration

**Document type:** Spec-driven architectural plan, designed for autonomous execution
**Sequel to:** `azathoth-provider-refactor-plan.md` (Phases 0–7)
**Phases in this plan:** 8 through 14
**Strictness level:** Maximum — every exit criterion is a CLI command with binary pass/fail
**Plan version:** 2.0

---

## 0. Executive Summary

Plan 1 built a correct and architecturally clean provider abstraction. This plan addresses the gap between *correct* and *trustworthy from a stranger's terminal*. Three classes of problem are surfaced by the post-mortem and by real-world execution: (a) the type-checker we used (`pyright` running advisory) let through ~25 real type errors that Astral's `ty` catches, including read-only-property mutations, `Optional` propagation gaps, and a Python 3.14-only syntax error in a `>=3.11` package; (b) the first-run UX for a user running `uvx azathoth workflow commit` is broken — the warning spam fires on `--help`, the missing-API-key case halts the chain instead of falling through to local Ollama, and the default provider order penalizes local-first users; (c) the model output contract is unenforced — when Gemini returns prose instead of JSON, the failure is a parse exception, not a typed retryable error. This plan addresses all three through seven independently-shippable phases, every one of which has CLI-verifiable exit criteria.

**Migration headline:** This plan switches from `pyright` to `ty` as the project's type checker. `ty` is faster, caught real bugs `pyright` missed, and integrates cleanly with the existing Astral tooling (`uv`, `ruff`). The risk that `ty` is at version 0.0.x is acknowledged and mitigated.

---

## 1. Context & Constraints

### 1.1 Project Snapshot
- **Project**: Azathoth (post Plan 1)
- **Stage**: Architecture in place, 105 tests passing, 0 violations on `azathoth-architecture-check`, all Plan 1 fitness functions green
- **New tooling**: `ty` (Astral's type checker), to replace `pyright`
- **Single developer**, distribution model includes `uvx azathoth` (ephemeral venv invocation)
- **Real-world signal**: terminal logs show preview-tag warnings on every command and JSON-parse failures on a 38K-char diff

### 1.2 Goals (definition of done)
1. A user running `uvx azathoth workflow commit` with neither `GEMINI_API_KEY` set nor Ollama running gets a single actionable error message — not a stack trace
2. The same user with Ollama running and no Gemini key succeeds, transparently using the local model
3. Every commit message panel shows which provider and model produced it
4. No warnings appear on `--help`, `--version`, or `azathoth doctor` invocations
5. Model output that violates the JSON contract is a typed retryable failure with one retry per provider, not a CLI crash
6. `azathoth doctor` reports what the resolver would do, without making any LLM call
7. `ty check` passes in strict mode on `src/`; CI runs `ty` and treats it as a hard gate (no `continue-on-error`)
8. The integration test against a real Ollama daemon (T-3 from the post-mortem) exists and runs in CI when the appropriate env var is set

### 1.3 Architectural Rules (carried forward from Plan 1, plus new)
- All Plan 1 rules from §1.3 of `azathoth-provider-refactor-plan.md` remain in force
- **NEW**: `ty check src/` is the single source of type-correctness truth. `pyright` is removed from the project entirely.
- **NEW**: Capability probes are pure async functions returning a structured `Capability` record; they MUST NOT raise for "provider not available," only for genuine implementation bugs
- **NEW**: Any code path that produces user-facing output MUST be able to identify which provider produced it; `LLMResponse` is the source of truth for attribution
- **NEW**: Warnings about configuration are emitted at the *first actual use* of the configuration, not at module import / `Settings()` construction

### 1.4 Out of Scope (explicit)
- Adding Anthropic, OpenAI, Alibaba providers (still deferred to post-Plan-2)
- Streaming responses
- Multimodal inputs
- Persistent config init (`azathoth init` interactive setup) — could be a Plan 3 concern
- Cost/token accounting beyond what's already in place
- Any behavior change to `core/scout.py`, `core/ingest.py`, or i18n features

### 1.5 Assumptions
- **[ASSUMPTION]** `ty` continues to be actively maintained by Astral through plan execution; if Astral abandons it (extremely unlikely), Plan 2 Phase 8 must rollback to `pyright` and that's a flag-day decision
- **[ASSUMPTION]** `ty` version 0.0.x APIs are stable enough across patch releases that pinning a minor version is sufficient; rule names may rename and that's acceptable churn cost
- **[ASSUMPTION]** Capability probing for Ollama can be done by hitting `GET /api/tags` (lightweight, no model load) within a short timeout
- **[ASSUMPTION]** "First-run" = no `~/.config/azathoth/config.toml`, no `GEMINI_API_KEY`, possibly Ollama running. The plan optimizes for this profile.
- **[ASSUMPTION]** The user's `commit` workflow returns a deterministic JSON shape today via `json_mode=True`; failures are due to model misbehavior, not API contract changes

---

## 2. Architecture Overview

### 2.1 New Components in This Plan

```
┌───────────────────────────────────────────────────────────────┐
│                     CLI / MCP Servers                         │
│        (commands now render LLMResponse.provider_name)        │
│                + new: cli/commands/doctor.py                  │
└───────────────────────┬───────────────────────────────────────┘
                        │ uses
                        ▼
┌───────────────────────────────────────────────────────────────┐
│                    core (orchestration)                       │
│   core/llm.py        →  uses capabilities at startup;         │
│                          splits timeouts; retries on JSON     │
│                          contract violation                   │
│   core/capabilities.py  →  NEW — probe per provider           │
│   core/tools.py      →  unchanged                             │
└───────────────────────┬───────────────────────────────────────┘
                        │ asks
                        ▼
┌───────────────────────────────────────────────────────────────┐
│                  providers (Protocol layer)                   │
│   providers/base.py  →  LLMResponse adds provider_name +      │
│                          model fields; ProviderSchemaError    │
│                          becomes retryable                    │
│   providers/gemini.py   →  classifies 429 as RateLimit;       │
│                              validates JSON; populates attrib │
│   providers/ollama.py   →  same; honors num_ctx for probe     │
└───────────────────────────────────────────────────────────────┘
```

### 2.2 New Information Flow: First-Run Resolution

```
azathoth workflow commit
  │
  ▼
core.llm.generate()
  │
  ▼
_resolve_with_capabilities():
  │
  ├─→ for each provider in config.llm_providers:
  │     │
  │     ├─→ capability = await probe_<provider>()
  │     │     (returns Capability(available, reason, metadata))
  │     │
  │     ├─→ if not capability.available:
  │     │     log INFO("skipping {p}: {reason}")
  │     │     continue
  │     │
  │     ├─→ try: await provider.generate(...)
  │     │
  │     ├─→ except ProviderUnavailable | RateLimitError:
  │     │     log INFO("falling through from {p}: {err}")
  │     │     continue
  │     │
  │     ├─→ except ProviderSchemaError:
  │     │     # JSON contract violation — retry once
  │     │     try: await provider.generate(...)
  │     │     except ProviderSchemaError: continue  # then fall through
  │     │
  │     └─→ except ProviderError: raise  # auth mid-call halts
  │
  └─→ if no provider succeeded:
        if no provider was available:
          raise NoProvidersAvailableError(remediation_hint=...)
        else:
          raise AllProvidersFailedError(causes=[...])
```

### 2.3 Error Taxonomy (refined)

| Error class | Meaning | Resolver action |
|---|---|---|
| `ProviderUnavailable` | Network/5xx/timeout — try later | Fall through immediately, no backoff |
| `ProviderRateLimitError` | 429/quota — try again later | Fall through with short backoff |
| `ProviderSchemaError` | Model violated output contract (e.g., not valid JSON when json_mode=True) | Retry once same provider, then fall through |
| `ProviderAuthError` (mid-call) | Credentials revoked during a session | Halt chain — re-raise immediately |
| `ProviderUnconfigured` (NEW) | Credentials absent at startup; surfaced by capability probe | Skip provider in probe, never enter generate(); never user-facing as "auth error" |
| `ProviderError` (other) | Non-retryable bug (schema, billing, etc.) | Halt chain |
| `NoProvidersAvailableError` (NEW) | All providers were unavailable per probe; never tried | Show friendly remediation message |
| `AllProvidersFailedError` | At least one provider was tried and all failed | Show error with all causes |

The key distinction added in this plan: *unconfigured at startup* is not the same as *failed mid-call*. Plan 1 conflated them.

---

## 3. Design Patterns & Code Standards

### 3.1 Pattern: Capability Probe (new)

**Pattern chosen:** Each provider exposes (or has, beside it) an async `probe()` function returning a `Capability` record. The resolver calls probes before instantiating providers.

**Why this pattern:**
"Try and catch what blows up" is the wrong default for first-run UX. By the time a `ProviderAuthError` reaches the user, the abstraction has leaked. A separate probe phase asks "is this provider usable right now?" and answers with structured data. The resolver then makes a routing decision before any model call. This is the single highest-leverage UX improvement in the plan.

**How it's applied:**
- `core/capabilities.py` defines a `Capability` Pydantic model: `available: bool`, `reason: str | None`, `metadata: dict[str, str]` (e.g., `{"model": "gemma4:e4b", "host": "http://localhost:11434"}`)
- One probe function per provider — `probe_gemini()`, `probe_ollama()` — colocated with the provider in `providers/<n>.py`
- Probes are pure async; they MUST NOT raise except for genuine implementation bugs
- Probe timeouts are short and explicit (default 2 seconds; configurable as `Settings.probe_timeout`)
- `_resolve()` calls probes in the order of `config.llm_providers` and uses the first available

**Standards enforced:**
- `probe_<n>() -> Capability` is a class-level method on each Provider (not a free function), so the Protocol can require it
- `Capability.available = False` with a `reason` string is the *normal* return for an unconfigured provider; not an error
- The `reason` field is a single human-readable sentence intended to surface in `azathoth doctor` output, e.g. `"GEMINI_API_KEY environment variable not set"`

> **What this protects against at year 3:** A new provider is added that has different "what counts as available" semantics (e.g., a paid provider with quota that may be exhausted). The probe pattern accommodates this without resolver changes — the new provider's probe returns `available=False, reason="quota exhausted today"` and the resolver just falls through.

### 3.2 Pattern: Decorator / Wrapper for JSON Contract Enforcement

**Pattern chosen:** When `json_mode=True` is requested, the resolver wraps the provider's `generate()` in a JSON-validation step. Failure raises `ProviderSchemaError`; the resolver retries once before falling through.

**Why this pattern:**
The contract violation we saw in production (Gemini returning prose, code blocks, or diff fragments) is structurally identical to a transient network error from the resolver's perspective: "this provider didn't satisfy the request, try something else." Encoding it as a typed exception puts it in the same routing logic as everything else, and makes "model output didn't match contract" first-class telemetry.

**How it's applied:**
- `core/llm.py` private helper `_validate_json_response(text: str) -> None` raises `ProviderSchemaError` if `text` is not parseable as JSON
- The validation runs only when the original call had `json_mode=True`
- The resolver catches `ProviderSchemaError` and retries the SAME provider once with the same prompt; on second failure, falls through
- The retry is logged at WARNING with the provider name and the offending output's first 200 chars (for debugging)

**Standards enforced:**
- `ProviderSchemaError.preview` field carries the offending response's first 200 characters — used in logging only, never user-facing
- Retry count is hardcoded to 1; not configurable in this plan (configurable retries are a future concern)

### 3.3 Pattern: Lazy Singleton for Config (D-2 from post-mortem)

**Pattern chosen:** Replace `config = Settings()` at module import with `get_config()` that lazily constructs and caches the singleton.

**Why this pattern:**
D-2 from the post-mortem flagged that `monkeypatch.setenv()` in tests is fragile because `azathoth.config` evaluates `Settings()` at import time. Lazy construction defers env var reading until the first access, making test isolation reliable and making `--help` and other no-LLM commands cheaper.

**How it's applied:**
- `azathoth.config` exposes `get_config() -> Settings` and `_reset_config_for_tests()` (test-only, underscore-prefixed)
- The bare `config` symbol is removed; consumers update to `get_config()` calls
- `_reset_config_for_tests()` is called by an autouse pytest fixture in `tests/conftest.py`

**Standards enforced:**
- No module in `src/azathoth/` imports `config` as a bare name; only `get_config`
- `azathoth-architecture-check` extends to flag `from azathoth.config import config` as a violation

### 3.4 Pattern: Adapter (carried forward, extended)

The Adapter pattern from Plan 1 §3.3 is extended: each provider's adapter now also populates `LLMResponse.provider_name` and `LLMResponse.model` based on what was actually used. This lets the CLI render "via gemini-2.5-flash" without coupling to provider internals.

### 3.5 Strictness Standards (updated for ty)

- **`ty check src/`** in strict mode (all rules promoted to error severity via `[tool.ty.rules]` table) — enforced by CI as a hard gate (no `continue-on-error`)
- **`pyright` is removed**: the `[tool.pyright]` block in `pyproject.toml` is deleted; CI no longer runs it; documentation no longer mentions it
- All other Plan 1 strictness rules carry forward: `ruff`, `pytest --strict-markers --strict-config`, `--cov-fail-under=85` for new code, no `print()` in `src/`, etc.
- **NEW**: `ty.toml` (or `[tool.ty]` in pyproject.toml) explicitly enables the rules `unresolved-attribute`, `invalid-argument-type`, `invalid-return-type`, `invalid-parameter-default`, `invalid-syntax`, and `invalid-assignment` at `error` severity; these are the rules that caught real bugs in the post-mortem
- **NEW**: A cross-version syntax check via `compileall` runs in CI for each Python version in the matrix (3.11, 3.12, 3.13). This catches the `except A, B:` class of bug across versions even when `ty` is configured for a single version.

---

## 4. Component Map & Directory Structure (delta from Plan 1)

### 4.1 Files Touched in This Plan

```
src/azathoth/
├── config.py                              # major rewrite (Phase 8 + 11)
├── cli/
│   └── commands/
│       ├── doctor.py                      # NEW (Phase 13)
│       └── workflow.py                    # render attribution (Phase 14)
├── core/
│   ├── capabilities.py                    # NEW (Phase 10)
│   └── llm.py                             # split timeouts, JSON retry (Phase 9, 12)
├── providers/
│   ├── base.py                            # LLMResponse + ProviderUnconfigured
│   │                                      # + NoProvidersAvailableError (Phase 9, 10)
│   ├── gemini.py                          # probe + 429 + JSON validate (Phase 9, 10, 12)
│   └── ollama.py                          # probe + JSON validate (Phase 10, 12)
└── dev/
    └── architecture_check.py              # extend rules (Phase 8)

tests/
├── conftest.py                            # autouse config reset (Phase 8)
├── core/
│   ├── test_capabilities.py               # NEW (Phase 10)
│   ├── test_llm.py                        # extend (Phase 9, 12)
│   └── test_workflow.py                   # extend (Phase 14)
├── cli/
│   ├── test_doctor.py                     # NEW (Phase 13)
│   └── test_workflow.py                   # attribution rendering (Phase 14)
├── providers/
│   ├── test_base.py                       # extend for new errors (Phase 9, 10)
│   ├── test_gemini.py                     # extend (Phase 9, 10, 12)
│   └── test_ollama.py                     # extend (Phase 10, 12)
└── integration/
    ├── __init__.py                        # NEW
    └── test_ollama_live.py                # NEW (Phase 14, gated on env var)

pyproject.toml                             # ty config; remove pyright (Phase 8)
ty.toml                                    # NEW — full ty config (Phase 8)
.github/workflows/ci.yml                   # ty replaces pyright (Phase 8)
CONTRIBUTING.md                            # documents ty (Phase 8)
```

---

## 5. Trade-off Analysis

### 5.1 DECISION: Type checker — pyright vs ty

```
DECISION: Which type checker is the project's source of truth?
OPTIONS CONSIDERED:
  A. Keep pyright, fix the bugs ty caught manually
     pros: Mature, widely used, well-documented; no migration cost
     cons: pyright didn't catch ~25 real bugs in this codebase that ty did;
           Microsoft tool inside an Astral ecosystem (uv + ruff + ty all
           share runtime, AST, IDE story); pyright is in advisory CI mode
           per D-6 — that "we'll fix it later" never happens
  B. Run both pyright AND ty, treat union of complaints as gating
     pros: Maximum coverage
     cons: Doubled CI time; conflicting rule names mean two configs to
           maintain; one-tool-failure-blocks-PR is the common path
  C. Migrate fully to ty, remove pyright
     pros: Faster (Rust-native, sub-second on this codebase); native to
           the Astral toolchain we already use; caught real bugs;
           ty.toml/[tool.ty] config is cleaner than pyright's; fewer
           "tools to learn" for new contributors
     cons: ty is at version 0.0.x — pre-stable API; rule names may rename
           between versions; some advanced typing features not yet
           supported (intersection types, narrowing) but those aren't
           used here
  D. Migrate to mypy
     pros: Most established in the ecosystem
     cons: Slower than both ty and pyright; rejected by the project's
           "modern Astral toolchain" preference; offers no improvement
           over the bugs that pyright already caught
CHOSEN: C — full migration to ty
REASON: Concrete evidence that ty caught 25+ real bugs that the
        established alternative missed is decisive. The 0.0.x risk is
        real but bounded — the executor pins a specific version, and
        rollback to pyright is a 30-minute operation if needed (we know
        what the pyright config looked like). The ecosystem coherence
        argument (uv + ruff + ty all from Astral) compounds: shared
        diagnostic style, shared IDE plugin model, shared release cadence.
REVISIT IF: ty is abandoned by Astral, OR ty introduces a regression that
            we can't pin around within a single release cycle, OR the
            project gains a typing requirement ty cannot express
            (intersection types, etc.).
```

### 5.2 DECISION: Capability probes — separate functions or methods on Provider?

```
DECISION: Where do capability probes live?
OPTIONS CONSIDERED:
  A. Free functions in core/capabilities.py — probe_gemini(), probe_ollama()
     pros: Decouples probe from provider class; easy to call without
           instantiating
     cons: Splits provider-related code across two files per provider;
           Protocol can't enforce that a probe exists for every provider
  B. Methods on each Provider class — gemini.GeminiProvider.probe()
     pros: Colocated with the provider; Protocol can require probe();
           obvious where to look
     cons: Probe shouldn't need provider instantiation (which may itself
           require credentials); resolved by making probe() a classmethod
           or @staticmethod
  C. A separate Capability Protocol that providers implement alongside
     pros: Maximum decoupling
     cons: Two protocols per provider; mental overhead
CHOSEN: B with classmethod / staticmethod
REASON: Colocation is the strongest signal here. When someone reads
        providers/gemini.py at year 3 they should see how the provider
        identifies itself as available. Making it a classmethod sidesteps
        the "instantiation requires credentials" problem.
REVISIT IF: Probe behavior diverges from provider behavior in a way that
            forces sharing logic across multiple files, suggesting the
            probe should be its own concept.
```

### 5.3 DECISION: How is "missing API key" surfaced?

```
DECISION: When GEMINI_API_KEY is unset, what does the system do?
OPTIONS CONSIDERED:
  A. Status quo (Plan 1): Gemini provider raises ProviderAuthError; this
     is non-retryable; the chain halts; user sees auth error
  B. Re-classify ProviderAuthError-at-startup as ProviderUnavailable
     pros: One-line fix; no new error class; chain falls through naturally
     cons: Conflates "missing config" with "credentials revoked mid-call";
           the latter SHOULD halt; can't distinguish in logs/errors
  C. New error class ProviderUnconfigured (subclass of ProviderError);
     probe returns Capability(available=False) instead of raising;
     resolver skips unavailable providers in probe phase
     pros: Clean taxonomy; probe is the single point of "is this usable";
           mid-call auth failures (a real ProviderAuthError) still halt
     cons: One more concept to teach
  D. Heuristic — if no providers have credentials, special-case to a
     friendly message without changing classifications
     pros: Targeted fix
     cons: Heuristics are fragile; multiplies code paths
CHOSEN: C — new ProviderUnconfigured + probe phase
REASON: This is the cleanest expression of the actual semantic difference.
        "Was never configured" and "was configured and now broken" are
        different events with different right responses. Encoding them
        differently is the only way the resolver can route them
        differently. The cost is one new exception class — small.
REVISIT IF: A provider needs probe-state semantics that don't fit the
            available/unavailable binary (e.g., "available but degraded").
```

### 5.4 DECISION: Where does the JSON-mode validation happen?

```
DECISION: Who enforces "if json_mode=True, output must parse as JSON"?
OPTIONS CONSIDERED:
  A. Each provider validates its own output before returning
     pros: Provider closest to the data; can use provider-specific knowledge
     cons: Duplicate validation logic across N providers
  B. The resolver wraps every json_mode=True call with a validator
     pros: One implementation; trivially consistent across providers
     cons: Resolver knows about the json_mode flag's semantics
  C. A response post-processor in core/tools.py
     pros: Reusable from CLI/MCP layers too
     cons: Adds indirection; the resolver is the natural place
CHOSEN: B — resolver-level validation
REASON: The resolver already orchestrates retries and fallback;
        validation is part of "did this succeed" logic and belongs there.
        Per-provider validation risks divergent rules.
REVISIT IF: Some provider's response shape requires custom pre-validation
            (unlikely with json_mode = "give me JSON or fail").
```

### 5.5 DECISION: Default provider order

```
DECISION: What should config.llm_providers default to?
OPTIONS CONSIDERED:
  A. ["gemini", "ollama"] (current) — cloud first
     pros: Better quality output by default; matches what the maintainer
           uses
     cons: First-run user without GEMINI_API_KEY hits friction; uvx user
           with no config hits an immediate error; "tries paid service
           first" may surprise privacy-sensitive users
  B. ["ollama", "gemini"] — local first
     pros: First-run user with Ollama running succeeds; no surprise
           network calls; no API key required for default usage; matches
           the philosophy of a local-first agent framework
     cons: Output quality varies more; user with cloud key but no local
           setup still works (probe phase skips Ollama)
  C. Empty default; require explicit configuration
     pros: No surprise behavior
     cons: Worst first-run UX of any option; user gets "no providers
           configured" before anything works
  D. Auto-detect at first run: probe both, use whatever's available,
     persist the choice
     pros: Smart default
     cons: "Persist where" is hard for uvx ephemeral usage; magic
           behavior is bad architecture
CHOSEN: B — ["ollama", "gemini"]
REASON: The capability probe layer (Phase 10) makes order-tolerant. If
        a user has a Gemini key and no Ollama, the probe skips Ollama
        and Gemini is used — order ceases to matter for "which one
        actually runs." Order matters only for tie-breaking, which is
        where local-first wins on philosophy and on the uvx use case.
REVISIT IF: Telemetry shows users overwhelmingly prefer cloud-first
            (unlikely for an OSS local-first tool).
```

### 5.6 DECISION: How is the configuration warning suppressed on innocent commands?

```
DECISION: How do we keep --help, --version, doctor from emitting model warnings?
OPTIONS CONSIDERED:
  A. Move the warning from a Pydantic validator to the LLM call site
     pros: Warning fires only when actually using the LLM
     cons: Have to remember to fire it; dilutes Pydantic's "validate at
           construction" guarantee
  B. Detect default vs. user-set value via a Pydantic field validator
     that inspects whether the value came from a default or from env/config
     pros: Warning only fires when user explicitly chose a preview model
     cons: pydantic-settings v2's "where did this value come from"
           introspection is non-trivial; bespoke logic
  C. Check sys.argv in the warning emitter and skip for known non-LLM
     commands
     pros: Targeted fix
     cons: Ugly; couples config to CLI; brittle as new commands are added
  D. Combine A and B: warn at first generate() call, AND only if the
     value differs from the stable default
     pros: Best UX — warning fires once, only when relevant, only for
           non-default models
     cons: Slightly more code
CHOSEN: D — first-call + non-default check
REASON: User experience drives this. A user on default config never sees
        the warning. A user who explicitly set a preview model sees the
        warning once per process, not on every --help. The cost is a
        module-level flag and a small "is this the default" check.
REVISIT IF: Multi-process scenarios surface where each subprocess emits
            the warning (would need IPC or a marker file).
```

---

## 6. Phased Implementation Plan

Phase numbering continues from Plan 1 (which ended at Phase 7). Each phase is independently shippable. Each has CLI-verifiable exit criteria. The autonomous executor MUST verify all exit criteria of phase N before starting phase N+1.

---

### PHASE 8 — ty migration + fix all latent type errors

**Goal:** `pyright` is removed from the project. `ty check src/` passes with zero errors. All ~25 type errors surfaced by `ty` in the recent terminal output are fixed, including the Python 3.14-only syntax in `assets/meta-prompt/d-python.py`. Cross-version syntax check is added to CI.

**Components touched:**
- `pyproject.toml` — remove `[tool.pyright]` block; add `[tool.ty]` table with `python-version = "3.11"`, exclude patterns, and rule severities (`error` for the diagnostic codes from the post-mortem); add `ty` as an explicit dev dependency, version-pinned
- `ty.toml` — alternative location for ty config if `[tool.ty]` proves limited; created only if needed
- `.github/workflows/ci.yml` — replace pyright step with ty step; remove `continue-on-error: true`; add a parallel `compileall` step running on each matrix Python version
- All files surfaced by ty errors:
  - `assets/meta-prompt/d-python.py` — fix Python 3.14 syntax (parenthesize the `except` tuple)
  - `src/azathoth/cli/commands/i18n.py` — handle `TranslationSet | None` properly
  - `src/azathoth/core/i18n.py` — fix `list[tuple[str, str]] = None` mutable defaults
  - `src/azathoth/core/ingest.py` — fix `list` vs `set[str]` mismatch on `include_patterns` / `exclude_patterns`
  - `src/azathoth/core/llm.py` — fix `tools` argument type narrowing
  - `src/azathoth/core/workflow.py` — fix `int | None` returncode in `Tuple[int, str, str]`
  - `src/azathoth/mcp/i18n.py` — same fixes as cli i18n
  - `src/azathoth/providers/gemini.py` — fix `Schema` argument; handle `dict | Any` for response candidates; fix implicit None return
  - `tests/core/test_tools.py` — fix invariant generic dict types in dispatch
  - `tests/providers/test_base.py` — remove illegal frozen-Pydantic mutations or use `model_copy(update=...)`
  - `tests/providers/test_fallback.py` — fix invariant `list[Exception]` parameter
  - `tests/providers/test_registry.py` — fix `Callable[[], Provider]` type annotation
- `CONTRIBUTING.md` — section "Type checking with ty"
- `src/azathoth/dev/architecture_check.py` — extend to flag direct `from azathoth.config import config` imports (D-2 prep)

**Dependencies:** Plan 1 complete (Phase 7 green).

**Exit criteria (CLI, all must pass):**

```
EC-8.1  | uv run ty check src/                                                        | $EXIT
EC-8.2  | ! grep -q "tool.pyright" pyproject.toml                                     | $EXIT
EC-8.3  | ! grep -q "pyright" .github/workflows/ci.yml                                | $EXIT
EC-8.4  | grep -q "tool.ty\|ty.toml" pyproject.toml                                   | $EXIT
EC-8.5  | grep -q "ty check" .github/workflows/ci.yml                                 | $EXIT
EC-8.6  | ! grep -q "continue-on-error" .github/workflows/ci.yml                      | $EXIT
EC-8.7  | for v in 3.11 3.12 3.13; do uv run --python $v python -m compileall -q src/ assets/ || exit 1; done | $EXIT
EC-8.8  | uv run pytest tests/ -q                                                     | $EXIT
EC-8.9  | uv run azathoth-import-check                                                | $EXIT
EC-8.10 | uv run azathoth-architecture-check                                          | $EXIT
EC-8.11 | uv run ruff check src/                                                      | $EXIT
EC-8.12 | grep -q "ty" CONTRIBUTING.md                                                | $EXIT
EC-8.13 | uv run ty --version | grep -qE "^ty 0\.[0-9]"                               | $EXIT
EC-8.14 | (echo "from azathoth.config import config" > /tmp/violation.py && \
          cp src/azathoth/cli/main.py src/azathoth/cli/main.py.bak && \
          cat /tmp/violation.py >> src/azathoth/cli/main.py && \
          (uv run azathoth-architecture-check; rc=$?; cp src/azathoth/cli/main.py.bak src/azathoth/cli/main.py; rm src/azathoth/cli/main.py.bak; [ $rc -ne 0 ])) | $EXIT
```

**Risk flags:**
- **[HIGH RISK]** EC-8.7 (`compileall` across Python versions) requires `uv` to have multiple Python versions installed. The executor MUST verify with `uv python list` before this phase and `uv python install 3.11 3.12 3.13` if missing. Skipping any matrix version is a stop condition, not a SKIP.
- **[REVISIT]** ty's rule names may rename between 0.0.x versions. The pinned ty version in dev dependencies must be exact (`ty==0.0.X`), not a range. Acceptable churn cost: when bumping ty, expect to update rule names in `[tool.ty.rules]`.
- **[REVISIT]** Some test files mutate frozen Pydantic models with `# type: ignore[misc]`. ty does not honor mypy/pyright `# type: ignore` syntax universally — verify whether `# ty: ignore[invalid-assignment]` is the correct form and use it consistently.

---

### PHASE 9 — LLMResponse attribution + chain timeout split + rate limit classification

**Goal:** Every `LLMResponse` knows which provider and model produced it. The C-1 (chain vs per-provider timeout) and C-2 (rate limit classification) issues from the post-mortem are fixed.

**Components touched:**
- `src/azathoth/providers/base.py` — `LLMResponse` gains `provider_name: str` and `model: str` fields (both required, frozen)
- `src/azathoth/providers/gemini.py` — `generate()` populates both fields from `self.name` and the configured model; `_classify_error()` adds `429`, `rate_limit`, `quota`, `RESOURCE_EXHAUSTED` to a `_RATE_HINTS` tuple and raises `ProviderRateLimitError`
- `src/azathoth/providers/ollama.py` — `generate()` populates both fields; `_classify_error()` already maps 429 correctly (verified, no change needed)
- `src/azathoth/config.py` — rename `llm_total_timeout` → `llm_per_provider_timeout`; add new `llm_chain_timeout: float = 300.0`; backward-compat alias for the old name with `DeprecationWarning`
- `src/azathoth/core/llm.py` — wrap entire `_resolve()` body in `asyncio.wait_for(..., timeout=cfg.llm_chain_timeout)`; per-provider call uses `cfg.llm_per_provider_timeout`; on `asyncio.TimeoutError` from the chain budget, raise `AllProvidersFailedError` with a single-cause TimeoutError
- `tests/providers/test_base.py` — extend tests for new `LLMResponse` fields
- `tests/providers/test_gemini.py` — verify 429 → `ProviderRateLimitError`; verify attribution populated
- `tests/providers/test_ollama.py` — verify attribution populated
- `tests/core/test_llm.py` — verify chain timeout vs per-provider timeout distinct behavior

**Dependencies:** Phase 8 complete.

**Exit criteria (CLI, all must pass):**

```
EC-9.1  | uv run python -c "from azathoth.providers.base import LLMResponse; r = LLMResponse(text='x', provider_name='gemini', model='gemini-2.5-flash'); assert r.provider_name == 'gemini' and r.model == 'gemini-2.5-flash'" | $EXIT
EC-9.2  | uv run python -c "from azathoth.providers.base import LLMResponse; from pydantic import ValidationError; \
          try: LLMResponse(text='x'); raise SystemExit(1); \
          except ValidationError: pass" | $EXIT  # provider_name + model are required
EC-9.3  | uv run python -c "from azathoth.providers.base import ProviderRateLimitError, ProviderError; assert issubclass(ProviderRateLimitError, ProviderError)" | $EXIT
EC-9.4  | uv run python -c "from azathoth.config import get_config; c = get_config(); assert hasattr(c, 'llm_per_provider_timeout') and hasattr(c, 'llm_chain_timeout')" | $EXIT
EC-9.5  | uv run pytest tests/providers/test_gemini.py -q -k "rate_limit or 429"      | $EXIT
EC-9.6  | uv run pytest tests/providers/test_gemini.py tests/providers/test_ollama.py -q -k "attribution or provider_name or model" | $EXIT
EC-9.7  | uv run pytest tests/core/test_llm.py -q -k "chain_timeout or per_provider_timeout" | $EXIT
EC-9.8  | uv run ty check src/                                                        | $EXIT
EC-9.9  | uv run azathoth-import-check                                                | $EXIT
EC-9.10 | uv run azathoth-architecture-check                                          | $EXIT
EC-9.11 | AZATHOTH_LLM_TOTAL_TIMEOUT=60 uv run python -W error::DeprecationWarning -c "from azathoth.config import get_config; c = get_config(); _ = c.llm_per_provider_timeout" 2>&1 | grep -q "DeprecationWarning" | $EXIT
```

**Risk flags:**
- **[REVISIT]** EC-9.2 makes `provider_name` and `model` required. This is a breaking change to any existing test that constructs `LLMResponse` with only `text=`. Phase 9 must update all such test fixtures.
- **[ASSUMPTION]** The old `llm_total_timeout` env var name is in active use by no one yet; backward-compat alias is mostly principle, not necessity.

---

### PHASE 10 — Capability probing + first-run UX + default order flip + lazy config

**Goal:** The first-run user with no GEMINI_API_KEY but Ollama running gets a working tool. The first-run user with nothing gets a single friendly error. Default provider order is local-first.

**Components touched:**
- `src/azathoth/core/capabilities.py` (new) — `Capability` Pydantic model; `async def probe_chain(provider_names: list[str]) -> list[Capability]` that runs all probes in parallel; logging at INFO for each result
- `src/azathoth/providers/base.py` — `Provider` Protocol gains `@classmethod async def probe(cls) -> Capability`; new exceptions `ProviderUnconfigured(ProviderError)` and `NoProvidersAvailableError(ProviderError)` (the latter has a `remediation: str` field with friendly setup hint)
- `src/azathoth/providers/gemini.py` — `probe()` checks `GEMINI_API_KEY`; returns `Capability(available=False, reason="GEMINI_API_KEY not set")` if absent; otherwise `available=True, metadata={"model": cfg.gemini.model}`
- `src/azathoth/providers/ollama.py` — `probe()` does `httpx.get(host + "/api/tags", timeout=cfg.probe_timeout)`; returns `Capability(available=True, metadata={"models": [...]})` on success, `available=False, reason="Ollama daemon not reachable at <host>"` on connection error/timeout
- `src/azathoth/core/llm.py` — `_resolve()` calls `probe_chain()` first; iterates available providers only; if none available, raises `NoProvidersAvailableError` with concatenated remediation hints from all probes
- `src/azathoth/config.py` — change default `llm_providers = ["ollama", "gemini"]`; add `probe_timeout: float = 2.0`; rewrite as `get_config()` lazy singleton; add `_reset_config_for_tests()`
- `tests/conftest.py` — autouse fixture calling `_reset_config_for_tests()` before each test
- `tests/core/test_capabilities.py` (new) — verify Capability model; verify probe_chain runs in parallel; verify probe failure modes
- `tests/providers/test_gemini.py` — extend with probe tests
- `tests/providers/test_ollama.py` — extend with probe tests (mocked HTTP)
- `tests/core/test_llm.py` — extend: with no providers available, raises `NoProvidersAvailableError`; with one available, uses it; with capability mismatch (Gemini key set but daemon down), works correctly

**Dependencies:** Phase 9 complete.

**Exit criteria (CLI, all must pass):**

```
EC-10.1 | uv run python -c "from azathoth.core.capabilities import Capability, probe_chain" | $EXIT
EC-10.2 | uv run python -c "from azathoth.providers.base import ProviderUnconfigured, NoProvidersAvailableError" | $EXIT
EC-10.3 | uv run python -c "from azathoth.config import get_config; c = get_config(); assert c.llm_providers == ['ollama', 'gemini'], c.llm_providers" | $EXIT
EC-10.4 | uv run python -c "from azathoth.config import get_config; assert callable(get_config)" | $EXIT
EC-10.5 | uv run pytest tests/core/test_capabilities.py -q                            | $EXIT
EC-10.6 | uv run pytest --cov=src/azathoth/core/capabilities --cov-fail-under=85 tests/core/test_capabilities.py | $EXIT
EC-10.7 | uv run pytest tests/providers/test_gemini.py tests/providers/test_ollama.py -q -k "probe" | $EXIT
EC-10.8 | uv run pytest tests/core/test_llm.py -q -k "no_providers or capability"     | $EXIT
EC-10.9 | env -u GEMINI_API_KEY -u AZATHOTH_GEMINI_API_KEY \
          AZATHOTH_OLLAMA_HOST=http://127.0.0.1:1 \
          uv run python -c "
import asyncio
from azathoth.core.llm import generate
from azathoth.providers.base import NoProvidersAvailableError
try:
    asyncio.run(generate('sys', 'usr'))
    raise SystemExit(1)
except NoProvidersAvailableError as e:
    assert 'GEMINI_API_KEY' in e.remediation or 'Ollama' in e.remediation, e.remediation
" | $EXIT
EC-10.10 | uv run ty check src/                                                       | $EXIT
EC-10.11 | uv run azathoth-import-check                                               | $EXIT
EC-10.12 | uv run azathoth-architecture-check                                         | $EXIT
```

**Risk flags:**
- **[HIGH RISK]** Phase 10 changes the default provider order. Existing users with `GEMINI_API_KEY` set in their env who DON'T have an explicit `llm_providers` config will now have their requests go to Ollama first if Ollama is also running. For most users, the probe will skip Ollama if not running, so behavior is unchanged. Document this in CHANGELOG and CONTRIBUTING.
- **[HIGH RISK]** EC-10.9 sets `AZATHOTH_OLLAMA_HOST=http://127.0.0.1:1` to ensure Ollama is unreachable. Port 1 is privileged and never listening. This must work consistently across CI environments.
- **[REVISIT]** The autouse `_reset_config_for_tests()` fixture may surface tests that were depending on lingering config state. If tests fail unexpectedly after this fixture is added, treat as a real isolation bug to fix, not a fixture problem.

---

### PHASE 11 — Warning hygiene

**Goal:** No model-related warnings appear on `--help`, `--version`, or `azathoth doctor`. Warnings only fire when a non-default model is configured AND the LLM is actually called.

**Components touched:**
- `src/azathoth/config.py` — remove the warning from the Pydantic validator; add a module-level `_preview_warning_emitted: bool = False` flag and a `maybe_warn_about_preview_model()` function
- `src/azathoth/core/llm.py` — call `maybe_warn_about_preview_model()` once at the start of the first `generate()` invocation per process
- The function checks: (a) is the configured model in the deny-list (`preview`, `experimental`, `exp`); (b) is the configured value different from the stable default; if both true, emit warning and set the flag
- `tests/core/test_config.py` (new or extend existing) — verify warning does not fire on `Settings()` construction with default; verify warning fires only on first generate() call when explicit preview model is set; verify warning fires at most once per process

**Dependencies:** Phase 10 complete.

**Exit criteria (CLI, all must pass):**

```
EC-11.1 | env -u AZATHOTH_GEMINI_MODEL uv run python -W error::UserWarning -c "from azathoth.config import get_config; _ = get_config()" | $EXIT
EC-11.2 | env -u AZATHOTH_GEMINI_MODEL uv run azathoth --help 2>&1 | grep -qi "warning" && exit 1 || exit 0 | $EXIT
EC-11.3 | env -u AZATHOTH_GEMINI_MODEL uv run azathoth workflow --help 2>&1 | grep -qi "warning" && exit 1 || exit 0 | $EXIT
EC-11.4 | AZATHOTH_GEMINI_MODEL=gemini-3.1-flash-lite-preview uv run python -W error::UserWarning -c "from azathoth.config import get_config; _ = get_config()" | $EXIT  # warning does NOT fire at construction
EC-11.5 | uv run pytest tests/core/test_config.py -q -k "warning or preview"          | $EXIT
EC-11.6 | uv run ty check src/                                                        | $EXIT
EC-11.7 | uv run azathoth-import-check                                                | $EXIT
EC-11.8 | uv run azathoth-architecture-check                                          | $EXIT
```

**Risk flags:**
- **[REVISIT]** Detecting "different from stable default" requires comparing against a known string; if the stable default itself contains "preview" (unlikely but possible if Google ships oddly-named stable models), the heuristic breaks. Fallback: maintain an explicit `_KNOWN_STABLE_MODELS` tuple.
- **[ASSUMPTION]** Process-level warning state (the `_preview_warning_emitted` flag) is acceptable. Multi-process scenarios (e.g., `pytest-xdist`) will emit one warning per worker; that's fine.

---

### PHASE 12 — JSON contract validation with retry

**Goal:** Model returning non-JSON when `json_mode=True` becomes a `ProviderSchemaError` with one retry, instead of a parse exception that crashes the CLI.

**Components touched:**
- `src/azathoth/providers/base.py` — `ProviderSchemaError` gains `preview: str` field (first 200 chars of offending output, for logging only)
- `src/azathoth/core/llm.py` — `_resolve()` now wraps `provider.generate()` calls when `json_mode=True` with `_validate_json_response()`; on `ProviderSchemaError`, retry the same provider once with the same prompt; on second failure, fall through; both attempts logged at WARNING with the preview field
- `src/azathoth/cli/commands/workflow.py` — remove the existing `try: json.loads(raw); except: typer.Exit(1)` in favor of catching `AllProvidersFailedError` and showing a friendlier message (the JSON validation now happens inside `generate()`)
- `tests/core/test_llm.py` — extend: verify a synthetic provider returning bad JSON twice falls through to next provider; verify a synthetic provider returning bad JSON once then good JSON succeeds via retry; verify the preview field is captured in the exception
- `tests/providers/test_base.py` — verify `ProviderSchemaError.preview` field

**Dependencies:** Phase 11 complete.

**Exit criteria (CLI, all must pass):**

```
EC-12.1 | uv run python -c "from azathoth.providers.base import ProviderSchemaError; e = ProviderSchemaError('bad', preview='not json'); assert e.preview == 'not json'" | $EXIT
EC-12.2 | uv run pytest tests/core/test_llm.py -q -k "schema or json_retry or json_contract" | $EXIT
EC-12.3 | uv run pytest tests/providers/test_base.py -q -k "schema_error or preview"  | $EXIT
EC-12.4 | uv run pytest --cov=src/azathoth/core/llm --cov-fail-under=85 tests/core/test_llm.py | $EXIT
EC-12.5 | uv run ty check src/                                                        | $EXIT
EC-12.6 | uv run azathoth-import-check                                                | $EXIT
EC-12.7 | uv run azathoth-architecture-check                                          | $EXIT
EC-12.8 | uv run pytest tests/cli/test_workflow.py -q                                 | $EXIT  # CLI still works after refactor
```

**Risk flags:**
- **[HIGH RISK]** The `cli/commands/workflow.py` JSON parse error handling is moved from CLI to core. The CLI must still produce reasonable output for the case where the chain exhausts. EC-12.8 verifies the CLI tests pass after this refactor.
- **[REVISIT]** Retry policy is hardcoded to 1. If telemetry shows two retries would meaningfully reduce fall-through rate, configurable retries become a future concern.

---

### PHASE 13 — `azathoth doctor` command

**Goal:** A new CLI command that probes all configured providers and reports what the resolver would do, without making any LLM call.

**Components touched:**
- `src/azathoth/cli/commands/doctor.py` (new) — `doctor_cmd()` calls `probe_chain()` for `config.llm_providers`; renders each capability as a row in a Rich table with status (✓/✗), reason, and metadata; renders a "Recommended provider" line at the bottom
- `src/azathoth/cli/main.py` — register `doctor` as a top-level command (`az doctor` and `azathoth doctor`)
- `tests/cli/test_doctor.py` (new) — verify command runs; verify it makes no LLM calls (assert no `genai.Client.generate_content` and no `httpx.AsyncClient.post` to `/api/chat` or `/api/generate`); verify exit code 0 when at least one provider is available, exit code 1 when none are
- `CONTRIBUTING.md` — document `azathoth doctor` as the canonical first-step troubleshooting command

**Dependencies:** Phase 12 complete.

**Exit criteria (CLI, all must pass):**

```
EC-13.1 | uv run azathoth doctor --help 2>&1 | grep -qi "doctor"                      | $EXIT
EC-13.2 | uv run azathoth doctor 2>&1 | grep -qE "(gemini|ollama)"                    | $EXIT
EC-13.3 | uv run pytest tests/cli/test_doctor.py -q                                   | $EXIT
EC-13.4 | uv run pytest --cov=src/azathoth/cli/commands/doctor --cov-fail-under=85 tests/cli/test_doctor.py | $EXIT
EC-13.5 | (env -u GEMINI_API_KEY -u AZATHOTH_GEMINI_API_KEY \
          AZATHOTH_OLLAMA_HOST=http://127.0.0.1:1 \
          uv run azathoth doctor; rc=$?; [ $rc -eq 1 ]) | $EXIT
EC-13.6 | grep -q "azathoth doctor" CONTRIBUTING.md                                   | $EXIT
EC-13.7 | uv run ty check src/                                                        | $EXIT
EC-13.8 | uv run azathoth-import-check                                                | $EXIT
EC-13.9 | uv run azathoth-architecture-check                                          | $EXIT
EC-13.10 | uv run pytest tests/cli/test_doctor.py -q -k "no_llm_call" | $EXIT  # explicit no-network test
```

**Risk flags:**
- **[REVISIT]** EC-13.10 requires careful mocking. The test must patch `httpx.AsyncClient` and `google.genai.Client` to record any call attempts and assert none were made. Static analysis won't catch this; the test is the contract.

---

### PHASE 14 — CLI provider attribution + live Ollama integration test

**Goal:** Every commit message panel shows which provider+model produced it. T-3 (live Ollama wire-protocol validation) is closed.

**Components touched:**
- `src/azathoth/cli/commands/workflow.py` — `commit_cmd()` extracts `LLMResponse.provider_name` and `LLMResponse.model` from the result; renders them as a dim subtitle line under the commit message panel (e.g., `via gemini · gemini-2.5-flash` or `via ollama · gemma4:e4b`); chooses border color based on provider category (cyan for cloud, green for local; mapping declared in a small `_PROVIDER_BORDERS: dict[str, str]` constant)
- `src/azathoth/cli/commands/workflow.py` — same change applied to `release_cmd` and any other workflow command that calls `generate()`
- `src/azathoth/core/llm.py` — `generate()` and `generate_with_tools()` return `LLMResponse` (already do); CLI now uses both fields instead of just `.text`
- `tests/cli/test_workflow.py` — verify subtitle is rendered when LLMResponse has attribution; verify border color matches provider category
- `tests/integration/__init__.py` (new, empty)
- `tests/integration/test_ollama_live.py` (new) — `@pytest.mark.integration` test gated on `AZATHOTH_OLLAMA_INTEGRATION=1`; runs against a real Ollama daemon; verifies request/response wire shape; verifies tool calling round trip with a trivial tool spec
- `pyproject.toml` — add `[tool.pytest.ini_options]` `markers = ["integration: marks tests requiring live external services"]`
- `.github/workflows/ci.yml` — add a separate optional CI job `integration-tests` that runs only on schedule (nightly) or on `workflow_dispatch`, starts an Ollama service container, pulls a small model, runs `pytest -m integration`

**Dependencies:** Phase 13 complete.

**Exit criteria (CLI, all must pass):**

```
EC-14.1 | uv run pytest tests/cli/test_workflow.py -q -k "attribution or border or via" | $EXIT
EC-14.2 | grep -E "provider_name|provider_borders|via " src/azathoth/cli/commands/workflow.py | $EXIT
EC-14.3 | uv run pytest tests/integration/test_ollama_live.py --collect-only -q       | $EXIT  # test exists and is collectible
EC-14.4 | uv run pytest -m "not integration" tests/ -q                                | $EXIT  # integration tests skip in normal runs
EC-14.5 | (curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && \
          AZATHOTH_OLLAMA_INTEGRATION=1 uv run pytest tests/integration/test_ollama_live.py -q) || \
          echo "SKIP: ollama daemon not available — integration test gated, must run in nightly CI" | $EXIT
EC-14.6 | grep -q "integration-tests" .github/workflows/ci.yml                        | $EXIT
EC-14.7 | grep -q "integration:" pyproject.toml                                       | $EXIT
EC-14.8 | uv run ty check src/                                                        | $EXIT
EC-14.9 | uv run azathoth-import-check                                                | $EXIT
EC-14.10 | uv run azathoth-architecture-check                                         | $EXIT
EC-14.11 | uv run pytest tests/ -q -m "not integration"                               | $EXIT  # full suite still green
```

**Risk flags:**
- **[REVISIT]** EC-14.5 conditionally skips when no Ollama daemon is available. The CI nightly job is the actual enforcement point. The executor must verify the `.github/workflows/ci.yml` change explicitly schedules the integration job, OR the regression coverage is illusory.
- **[ASSUMPTION]** Border color choice (cyan for cloud / green for local) is a stylistic call. If the user has a strong preference here, this is the one place in the plan most likely to be re-bikeshed. Hard-coded values are easy to change.

---

## 7. Implementation Management

### 7.1 Sequencing

```
Phase 8  (ty migration + fix latent type errors)
   │
   └─→ Phase 9  (LLMResponse attribution + timeouts + rate limit)
          │
          └─→ Phase 10 (Capability probing + first-run UX + default flip + lazy config)
                 │
                 └─→ Phase 11 (Warning hygiene)
                        │
                        └─→ Phase 12 (JSON contract validation + retry)
                               │
                               └─→ Phase 13 (azathoth doctor command)
                                      │
                                      └─→ Phase 14 (CLI attribution + Ollama integration test)
```

Strictly linear. No parallelization opportunities given single-developer constraint.

### 7.2 Critical Path
Phases 8 and 10 are the riskiest. Phase 8 because it touches every type-error site in the codebase and a misstep here means CI cannot be brought to green. Phase 10 because it changes runtime behavior in ways visible to existing users (default order flip).

### 7.3 Breaking Changes (flag explicitly)
- **[BREAKING — internal only]** `LLMResponse.provider_name` and `LLMResponse.model` become required fields (Phase 9). Any test fixture or code constructing `LLMResponse` directly must update. Plan covers this in Phase 9 components.
- **[BREAKING — config]** Default `llm_providers` order changes from `["gemini", "ollama"]` to `["ollama", "gemini"]` (Phase 10). Users who relied on the old default see different behavior; users with explicit config are unaffected. **CHANGELOG entry required.**
- **[BREAKING — internal]** `azathoth.config.config` (the bare singleton) is removed in Phase 10 in favor of `get_config()`. Internal callers updated; no external API consumers exist.
- **[BREAKING — config]** `llm_total_timeout` is renamed to `llm_per_provider_timeout` with a deprecation alias (Phase 9).
- **[BREAKING — toolchain]** `pyright` is removed entirely (Phase 8). No alias, no transition period. Anyone with editor configuration pointing at the project's `[tool.pyright]` table needs to switch to `[tool.ty]`.

### 7.4 Integration Points
- **Phase 9 ↔ Phase 14**: attribution fields added in Phase 9 are consumed by Phase 14 CLI rendering. If Phase 9 ships and Phase 14 lags, behavior is correct (just no UI surface yet). Acceptable.
- **Phase 10 ↔ Phase 13**: `azathoth doctor` (Phase 13) is a UI on top of `probe_chain()` from Phase 10. Phase 13 cannot ship before Phase 10. Strictly enforced by sequencing.
- **Phase 8 ↔ everything**: ty migration is the foundation. If Phase 8's exit criteria don't pass, no later phase can ship green.

---

## 8. Validation & Testing Strategy

### 8.1 Test Layer Matrix (delta from Plan 1)

| Layer | Test type | What it verifies | Where |
|---|---|---|---|
| Capability probing | Unit (mocked HTTP / env) | Each provider's probe returns correct `Capability` for all states | `tests/core/test_capabilities.py` + provider tests |
| First-run UX | Integration (no providers configured) | `NoProvidersAvailableError` raised with remediation hint | `tests/core/test_llm.py` |
| JSON contract enforcement | Unit (synthetic provider) | Bad JSON → `ProviderSchemaError`; one retry; fall through | `tests/core/test_llm.py` |
| Warning hygiene | Unit | Default config: no warning. Explicit preview: one warning at first generate(). | `tests/core/test_config.py` |
| `azathoth doctor` | Unit + no-network test | Command runs; never makes LLM call | `tests/cli/test_doctor.py` |
| CLI attribution | Unit | Subtitle rendered with provider+model; border color correct | `tests/cli/test_workflow.py` |
| Live Ollama wire | Integration (gated) | Real daemon round-trip; tool calling end-to-end | `tests/integration/test_ollama_live.py` |
| Type correctness | Architecture fitness | `ty check src/` passes in strict mode | CI step |
| Cross-version syntax | Architecture fitness | `compileall` passes on 3.11, 3.12, 3.13 | CI matrix |

### 8.2 Architecture Fitness Functions (extended)

Plan 1's six fitness functions remain in force. This plan adds:

7. **Type correctness** (`ty check src/`) — replaces pyright; runs in strict mode; CI gate (no `continue-on-error`)
8. **Cross-version syntax** (`compileall` on each matrix Python version) — catches the `except A, B:` class permanently
9. **No bare config import** (extension to `azathoth-architecture-check`) — flags `from azathoth.config import config` as a violation; forces use of `get_config()`
10. **No-network in doctor** (test in `tests/cli/test_doctor.py`) — the doctor command's contract is that it never makes a real LLM call; enforced via mock-based assertion

### 8.3 Local Dev Validation (updated)

Single command for pre-commit verification:

```
uv run azathoth-import-check && \
uv run azathoth-architecture-check && \
uv run ruff check src/ && \
uv run ty check src/ && \
uv run pytest tests/ -m "not integration" -q --strict-markers --strict-config
```

Note: `pyright` is removed from this chain. `ty` replaces it. Integration tests are excluded from the default run; they execute in nightly CI.

---

## 9. Open Questions & Risks

### 9.1 Open Questions

| ID | Question | Resolution path |
|---|---|---|
| OQ-2.1 | What is the exact ty version to pin? | Executor MUST run `uvx ty --version` at start of Phase 8 and pin the resolved patch version in `pyproject.toml`'s dev dependencies. Document in `PLAN_RESOLUTIONS.md`. |
| OQ-2.2 | Does ty support `# type: ignore[<rule>]` comments inherited from pyright/mypy code, or does it require its own syntax? | Executor MUST verify experimentally during Phase 8; document the answer; update `# type: ignore` comments globally to whichever syntax ty honors. |
| OQ-2.3 | What categorization mapping (cyan/cloud, green/local) does the user actually want for provider borders? | The plan picks defaults. If the user has a preference, this is a 5-line change in `_PROVIDER_BORDERS`. Surface to user before Phase 14. |
| OQ-2.4 | Is `gemini-2.5-flash` the correct stable Gemini model name at execution time? | Executor MUST web-search at execution start (same instruction as Plan 1 OQ-1, carried forward). |
| OQ-2.5 | Does the existing `core/i18n.py` `list[tuple[str, str]] = None` pattern affect runtime behavior, or is it purely a type-annotation lie? | Inspect call sites; if `None` is actually a sentinel for "use empty list," fix the type annotation to `list[tuple[str, str]] | None = None` and add explicit handling. If it's a bug, fix the default to `[]` (but watch for mutable-default trap — use `None` + post-init coerce). |

### 9.2 Risk Register

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R-2.1 | ty version is bumped during plan execution; rule names rename and break CI | Medium likelihood, medium impact | Pin exact version; bump only in dedicated commits with rule-name updates |
| R-2.2 | Phase 8 surfaces type errors that require non-trivial code changes in unrelated modules | Medium likelihood, high impact | Plan 8's components list is comprehensive based on the post-mortem terminal output. New surprises → triage report at `/tmp/azathoth-phase-8-triage.md`, halt if >3 unrelated modules need touching |
| R-2.3 | Default order flip (Phase 10) confuses an existing user whose Gemini-first workflow was working fine | Low likelihood, medium impact | CHANGELOG entry; document migration in CONTRIBUTING; existing explicit configs unaffected |
| R-2.4 | Capability probe takes too long (slow Ollama daemon, slow DNS); first-run UX is sluggish | Medium likelihood, low impact | Aggressive default `probe_timeout=2.0`; probes run in parallel via `asyncio.gather`; total probe phase capped by total chain budget |
| R-2.5 | JSON validation false-positives on valid-but-unusual JSON (e.g., model wraps response in markdown fences) | Medium likelihood, medium impact | Validator strips common wrappers (```json...```, ``` ... ```) before parsing; documented in code comment |
| R-2.6 | Doctor command's no-LLM-call invariant breaks when a future provider's probe inadvertently makes a real call | Low likelihood, medium impact | EC-13.10 is the contract; if a future provider's probe needs to call the model (anti-pattern), it MUST do so behind a separate `verify_credentials()` call, not in `probe()` |
| R-2.7 | Removing `pyright` breaks IDE setups for any contributor who has it configured | Low likelihood (single dev), low impact | CONTRIBUTING.md updates explain the switch |

---

## 10. Executor Instructions (autonomous run)

Same standing instructions as Plan 1 §10, plus:

1. **Resolve OQ-2.1 (ty version) and OQ-2.2 (`# type: ignore` syntax)** before starting Phase 8. Document in `PLAN_RESOLUTIONS.md`.
2. **For Phase 8 specifically**: produce a triage report at `/tmp/azathoth-phase-8-triage.md` listing every type error before fixing any. If new errors surface beyond the ~25 enumerated in §4.1 components, list them. If more than 3 *unrelated* modules need touching (modules not listed in components), HALT and surface the report.
3. **For the default-order flip (Phase 10)**: append a `CHANGELOG.md` entry. If `CHANGELOG.md` does not exist, create one. The entry must explicitly state the order change.
4. **For OQ-2.3 (border colors)**: use cyan for cloud, green for local as the default, but make the `_PROVIDER_BORDERS` dict explicit and easy to discover for the user to override.
5. **Never silence ty.** If `ty check src/` fails, fix the code, not the rules. If a rule is genuinely wrong for this codebase, document the rationale in a `# ty: ignore[<rule>]  # reason: <prose>` comment AND open a `FUTURE.md` entry to revisit when ty matures.
6. **Never re-introduce pyright.** If during Phase 8 the executor decides ty is insufficient, HALT and surface the question, do not silently keep both checkers.

---

## 11. Plan Sign-off Checklist

Before considering this plan complete, the user (yrrrrrf) should confirm:

- [ ] §1.4 "Out of Scope" still matches intent (Anthropic/OpenAI/Alibaba providers remain deferred)
- [ ] §1.5 Assumptions are acceptable (especially OQ-2.4 model name resolution at execution time)
- [ ] §5.5 Default order flip to local-first matches user preference (the explicit M-2 fix)
- [ ] §5.1 ty migration is desired (vs. keeping pyright as a fallback)
- [ ] §7.3 Breaking changes are acceptable (especially the `LLMResponse` field requirement and the `pyright` removal)
- [ ] §10 Executor instructions are sufficient for autonomous run

If any item is unchecked, revise before execution.

---

**End of plan.**