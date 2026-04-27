# Azathoth — Provider Abstraction Refactor: Execution Plan

**Document type:** Spec-driven architectural plan, designed for autonomous execution
**Target executor:** A coding agent operating without human supervision
**Strictness level:** Maximum — every exit criterion is a CLI command with a binary pass/fail return code
**Plan author posture:** Principal Software Architect, 20+ years
**Plan version:** 1.0

---

## 0. Executive Summary

Azathoth's LLM seam is currently a single hardcoded function calling Google's `genai` SDK. This plan converts that seam into a Protocol-based provider abstraction that supports any LLM provider (Google, Alibaba, Anthropic, OpenAI, local Ollama, etc.) with a single contract, a universal tool-calling layer that works on every model regardless of native tool support, and a fallback chain so cloud outages degrade gracefully to local inference. The architecture is designed to absorb new providers and new models with one file per addition and zero changes to consumer code.

Three correctness fixes (Phase 0) are non-negotiable prerequisites: a Python 2 syntax error in `core/i18n.py`, an artificial `>=3.14` Python pin that locks out collaborators, and a preview-tag default model that can vanish without notice. After those, the refactor proceeds in seven phases, each independently shippable and CLI-verifiable.

---

## 1. Context & Constraints

### 1.1 Project Snapshot
- **Project**: Azathoth — Python AI agent framework (CLI + MCP servers)
- **Stage**: Pre-alpha, version 0.0.1
- **Stack**: Python (currently pinned `>=3.14`), Pydantic v2, Typer, FastMCP, `google-genai`, `gitingest`, `tiktoken`, `httpx`
- **Build/dependency**: `uv` + `hatchling`
- **Test framework**: `pytest` + `pytest-asyncio` + `pytest-cov`
- **Lint/type**: `ruff` + `pyright`
- **Single developer** (yrrrrrf), no external users yet — breaking changes are free

### 1.2 Goals (definition of done)
1. Project loads and tests on Python 3.11+ without surprises
2. LLM layer is provider-agnostic via a single `Provider` Protocol
3. Adding a new provider (Anthropic, OpenAI, Alibaba, etc.) requires exactly one new file and one config entry — no consumer code changes
4. Tool calling works on every model via dual-path execution (native when supported, JSON-mode emulation as universal fallback)
5. CLI commands accept `--provider` flag; config supports an ordered fallback chain
6. CI enforces architectural boundaries through fitness functions, not human review

### 1.3 Architectural Rules (mandatory, derived from project's stated coding philosophy)
- **Functional/expressive style** — comprehensions, generators, iterator chains over imperative loops
- **Pydantic v2 for all data crossing boundaries** — no plain dicts as transport between layers
- **Type hints non-negotiable** — every public function fully typed; `pyright --strict` clean for new code
- **`from __future__ import annotations`** at top of every module
- **Modular composition** — small focused modules; explicit imports; no star imports
- **No silent failures** — every `except` clause either re-raises or logs structured context
- **Protocol over inheritance** — duck typing via PEP 544, no abstract base classes for the provider layer

### 1.4 Out of Scope (explicit)
- The A2A agent protocol layer (separate concern, future plan)
- The `scout()` MCP integration (referenced in original Plan 2, deferred)
- Streaming responses (current `generate()` is non-streaming; streaming is a Phase 8+ concern)
- Multi-modal inputs (image/audio) — text-only for this refactor
- Caching/memoization of LLM responses
- Cost tracking / token accounting beyond what `tiktoken` already provides

### 1.5 Assumptions Made
- **[ASSUMPTION]** No external Azathoth users currently depend on the `core.llm.generate()` signature; breaking it is acceptable
- **[ASSUMPTION]** Ollama daemon will be assumed reachable at `http://localhost:11434` by default; configurable
- **[ASSUMPTION]** Local development hardware is RTX 4060 Laptop (8GB VRAM), so default local model recommendation is sized accordingly
- **[ASSUMPTION]** The `providers/__init__.py` empty file in the current repo was placed there with this refactor in mind and can be repurposed as the new module's anchor
- **[ASSUMPTION]** Test failures uncovered by Phase 1's diagnostic are acceptable to surface; this plan does not pre-allocate scope to fix them, but Phase 1 will produce a triage report

---

## 2. Architecture Overview

### 2.1 High-Level Layering

```
┌──────────────────────────────────────────────────────────────┐
│                     CLI / MCP Servers                        │
│           (azathoth.cli.*, azathoth.mcp.*)                   │
└───────────────────────┬──────────────────────────────────────┘
                        │ depends on
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                core (orchestration layer)                    │
│      core/llm.py    →  resolver + fallback chain             │
│      core/tools.py  →  ToolSpec/ToolCall + dispatch loop     │
│      core/prompts.py, core/workflow.py, ...   (unchanged)    │
└───────────────────────┬──────────────────────────────────────┘
                        │ depends on
                        ▼
┌──────────────────────────────────────────────────────────────┐
│            providers (Protocol + implementations)            │
│      providers/base.py     →  Provider Protocol + types      │
│      providers/registry.py →  name → factory mapping         │
│      providers/gemini.py   →  Google                         │
│      providers/ollama.py   →  local                          │
│      providers/anthropic.py, providers/openai.py, ...        │
│            (added later — one file each, no core changes)    │
└──────────────────────────────────────────────────────────────┘
                        │ depends on
                        ▼
┌──────────────────────────────────────────────────────────────┐
│                  external SDKs / HTTP                        │
│              google-genai, ollama-python, httpx              │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 Dependency Direction Rules (enforced by fitness functions in Phase 7)
- `cli/*` may import from `core/*` and `providers/base` (only for type hints)
- `cli/*` MUST NOT import concrete provider modules (`providers/gemini`, etc.)
- `core/llm.py` is the ONLY module in `core/` allowed to import from `providers/*`
- `providers/<name>.py` MUST NOT import from any other `providers/<other>.py`
- `providers/*` MUST NOT import from `cli/*` or `mcp/*`
- No circular imports anywhere

### 2.3 Core Domain vs. Supporting
- **Core domain**: the `Provider` Protocol, `ToolSpec`, `ToolCall`, `LLMResponse`, the resolver/fallback chain, the universal tool-dispatch loop
- **Supporting**: each concrete provider implementation (replaceable, plug-in nature)

---

## 3. Design Patterns & Code Standards

### 3.1 Pattern: Strategy + Registry (for provider selection)

**Pattern chosen:** Strategy pattern via `typing.Protocol`, with a name-keyed registry for runtime resolution.

**Why this pattern:**
At year 1, the project has 2–3 providers. At year 5, expect 8+ as the LLM landscape fragments further. At year 10, expect provider rotation (some die, new ones emerge). Inheritance hierarchies for this would calcify; abstract base classes force every provider to import from a central module and obey a fragile contract; Protocol gives structural typing — a provider is anything that quacks correctly, verified at type-check time and at module-load time.

**How it's applied:**
- `providers/base.py` declares the `Provider` Protocol (a structural type, no inheritance required)
- Each `providers/<name>.py` declares a class that satisfies the Protocol structurally
- `providers/registry.py` maintains a `dict[str, Callable[[], Provider]]` of factory callables, populated via explicit registration (not auto-discovery — explicitness wins for debugging at year 3)
- `core/llm.py` calls the registry to resolve a name to an instance

**Standards enforced:**
- Provider class names: `<Name>Provider` (e.g., `GeminiProvider`, `OllamaProvider`)
- Provider module names: lowercase, single word (`gemini.py`, `ollama.py`, `anthropic.py`)
- Every provider exposes a class-level `name: str` attribute matching its registry key
- Every provider exposes a class-level `supports_native_tools: bool` attribute
- Every provider's `generate()` method is `async`, returns `LLMResponse`
- Every provider raises `ProviderUnavailable` for retryable transport failures (timeouts, 5xx, connection errors) and `ProviderError` (or a subclass) for non-retryable failures (auth, schema, billing, rate limits where retry would not help)

> **What this protects against:**
> - **Year 3**: New developer adds the 4th provider. They don't read existing providers; the Protocol type-checks their work or pyright fails CI.
> - **Year 5**: Anthropic deprecates an SDK. Replacement only touches one file.
> - **Year 10**: The Gemini SDK is gone. Ripping out `providers/gemini.py` doesn't ripple anywhere.

### 3.2 Pattern: Chain of Responsibility (for provider fallback)

**Pattern chosen:** Ordered list of providers, tried in sequence, with a typed exception protocol distinguishing "try the next one" from "stop now."

**Why this pattern:**
Naive try/except chains turn into spaghetti once you have 3+ providers. A first-class fallback chain with typed exceptions makes the fallback policy declarative (in config) rather than imperative (in code). At year 3, a new developer reading the config understands the fallback order at a glance. The exception types are the contract.

**How it's applied:**
- Config field `llm_providers: list[str]` (ordered; default `["gemini", "ollama"]`)
- Resolver iterates the list, instantiates each, calls `generate()`, catches `ProviderUnavailable` and continues
- Catches `ProviderError` (non-retryable) and stops — re-raises immediately
- If all providers exhaust without success, raises `AllProvidersFailedError` with the list of underlying causes

**Standards enforced:**
- The fallback chain is the ONLY place that catches `ProviderUnavailable`; consumer code never handles it
- Logging at INFO level on each fallback hop with provider name and underlying error class
- Total wall-clock budget per call is enforced by `asyncio.wait_for` at the resolver level (default 120 seconds, configurable)

### 3.3 Pattern: Adapter (for tool-calling normalization)

**Pattern chosen:** Each provider adapts its native tool-calling format to/from a unified `ToolSpec`/`ToolCall` shape. Providers without native tool calling fall through to the JSON-mode emulator.

**Why this pattern:**
Gemini, Anthropic, OpenAI, Ollama, and others all express tool calls differently (JSON Schema variants, XML, structured function objects). Pushing that variance into consumers is a maintenance disaster. The Adapter pattern at the provider boundary is the only sustainable answer.

**How it's applied:**
- `core/tools.py` defines `ToolSpec` (Pydantic model with `name`, `description`, `parameters_schema: dict`)
- Each provider's `generate()` accepts `tools: list[ToolSpec] | None` and translates to native format internally
- A provider with `supports_native_tools = False` ignores native translation; the resolver wraps the call with a JSON-mode emulator that injects the tool catalog into the system prompt and parses the model's JSON output back into `ToolCall` instances
- The resolver, not the provider, decides which path to take

**Standards enforced:**
- `ToolSpec.parameters_schema` is JSON Schema 2020-12 (the LCD across providers)
- All tool call results are `ToolCall` instances; consumers never see provider-native types
- Tool dispatch (executing the named tool with the parsed args) is a separate concern in `core/tools.py`, not a provider responsibility

### 3.4 Pattern: Repository / Façade (for `core/llm.py`)

**Pattern chosen:** `core/llm.py` becomes a thin façade exposing `generate()`, `generate_with_tools()`, hiding the resolver, registry, and tool emulator from consumers.

**Why this pattern:**
Consumers have already coupled to `core.llm.generate()`. Keeping that import path stable while replumbing internals is what a façade is for. Consumers continue to call `from azathoth.core.llm import generate`; everything underneath changes.

**How it's applied:**
- `core/llm.py` exposes exactly: `generate()`, `generate_with_tools()`, `LLMError`, `ProviderUnavailable`, `ProviderError`, `AllProvidersFailedError`
- Internal modules (`_resolver`, `_emulator`) are private (underscore-prefixed)
- Consumers never import from `providers/*` directly; pyright will check this in Phase 7

### 3.5 Strictness Standards (the "Python is lax" countermeasures)

These are non-negotiable for all new and refactored code:

- **`pyright` in `strict` mode** for `src/azathoth/providers/` and `src/azathoth/core/llm.py`, `src/azathoth/core/tools.py` — enforced by CI
- **`ruff`** with rulesets `E, F, I, B, RUF, UP, PLR, SIM, ASYNC, FBT, RET` enabled, errors not warnings
- **No `Any`** in new code without an inline `# type: ignore[<rule>]  # reason: <prose>` comment
- **No `**kwargs`** in public function signatures — declare explicitly
- **No bare `except:`**, no `except Exception:` without re-raise or structured log
- **No `print()`** in `src/`; use `logging` (the CLI rich console output is allowed in `cli/*` only)
- **Pydantic models are `frozen=True` by default**; mutable models must justify in a docstring
- **`from __future__ import annotations`** at the top of every `.py` file under `src/`
- **`pytest --strict-markers --strict-config`** in CI; unknown marker → fail
- **Coverage gate**: new code in `providers/` and `core/llm.py`, `core/tools.py` requires ≥85% line coverage; enforced by `pytest-cov` with `--fail-under=85` scoped to those paths

### 3.6 Logging & Observability
- Use `logging.getLogger(__name__)` at top of every module
- Log fallback events at INFO with structured fields: `provider`, `error_class`, `attempt_index`
- Log provider errors at WARNING with the underlying SDK exception's `__class__.__name__` and `str(exc)` only — never log API keys, never log full prompts at INFO/WARNING (DEBUG only, and only the first 500 chars)
- No metrics layer in this refactor — that's a future concern, but the logging shape must be stable enough that a metrics layer can scrape it later

---

## 4. Component Map & Directory Structure

### 4.1 Final Target Tree (after Phase 7)

```
src/azathoth/
├── __init__.py
├── config.py                          # adds llm_provider, llm_providers, ollama_*
├── agent/                             # untouched
├── cli/
│   ├── __init__.py
│   ├── main.py                        # untouched
│   └── commands/
│       ├── __init__.py
│       ├── i18n.py                    # untouched
│       ├── ingest.py                  # untouched
│       └── workflow.py                # adds --provider flag (Phase 4)
├── core/
│   ├── __init__.py
│   ├── directives.py                  # untouched
│   ├── exceptions.py                  # adds AzathothError base (Phase 2)
│   ├── i18n.py                        # syntax fix (Phase 0)
│   ├── ingest.py                      # untouched
│   ├── llm.py                         # rewritten as façade (Phase 3)
│   ├── tools.py                       # NEW (Phase 5) — ToolSpec, dispatch, emulator
│   ├── prompts.py                     # untouched
│   ├── scout.py                       # untouched
│   ├── utils.py                       # untouched
│   └── workflow.py                    # untouched
├── dev/
│   ├── __init__.py                    # NEW (Phase 1)
│   └── import_check.py                # NEW (Phase 1) — fitness function entry
├── mcp/                               # untouched
├── providers/
│   ├── __init__.py                    # exports Provider, ToolSpec, etc.
│   ├── base.py                        # NEW (Phase 2) — Protocol, types, exceptions
│   ├── registry.py                    # NEW (Phase 2) — name → factory
│   ├── gemini.py                      # NEW (Phase 3) — extracted from core/llm.py
│   ├── ollama.py                      # NEW (Phase 4)
│   ├── anthropic.py                   # NEW (deferred, post-Phase 7)
│   └── openai.py                      # NEW (deferred, post-Phase 7)
└── transforms/                        # untouched

tests/
├── conftest.py                        # audited (Phase 1)
├── core/
│   ├── test_directives.py             # untouched
│   ├── test_i18n.py                   # un-skip / fix imports (Phase 1)
│   ├── test_ingest.py                 # untouched
│   ├── test_llm.py                    # rewritten (Phase 3)
│   ├── test_tools.py                  # NEW (Phase 5)
│   └── test_workflow.py               # untouched
└── providers/
    ├── __init__.py
    ├── test_base.py                   # NEW (Phase 2) — Protocol conformance
    ├── test_gemini.py                 # NEW (Phase 3)
    ├── test_ollama.py                 # NEW (Phase 4)
    ├── test_registry.py               # NEW (Phase 2)
    └── test_fallback.py               # NEW (Phase 6)
```

### 4.2 Component Responsibilities

| Component | Single-sentence responsibility | Must NOT do |
|---|---|---|
| `providers/base.py` | Define the `Provider` Protocol and the typed transport models (`ToolSpec`, `ToolCall`, `LLMResponse`) plus the exception hierarchy | Contain any provider implementation, network logic, or SDK imports |
| `providers/registry.py` | Map provider names to factory callables; provide `get_provider(name)` and `list_providers()` | Decide fallback policy or instantiate by default |
| `providers/<name>.py` | Adapt one external LLM API to the `Provider` Protocol; translate `ToolSpec`↔native | Import other providers, depend on `core/*`, contain orchestration logic |
| `core/llm.py` | Façade exposing `generate()` and `generate_with_tools()`; resolves provider chain; handles fallback | Contain provider-specific logic or SDK imports |
| `core/tools.py` | Define `ToolSpec` semantics, dispatch loop, JSON-mode emulator, schema generation from Pydantic | Make network calls or know provider details |
| `core/exceptions.py` | Root `AzathothError` and re-export of LLM exceptions for consumer convenience | Contain logic |
| `dev/import_check.py` | Walk every module under `azathoth.*` and import it; exit non-zero on any `ImportError` or `SyntaxError` | Run application code, depend on test fixtures |
| `cli/commands/workflow.py` | Existing CLI; gains a `--provider` / `-p` Typer option that overrides the config default for one invocation | Know how providers work — only passes the name string through |

---

## 5. Trade-off Analysis

### 5.1 DECISION: Provider abstraction style

```
DECISION: How is the provider boundary expressed in Python?
OPTIONS CONSIDERED:
  A. Abstract Base Class (ABC) in providers/base.py
     pros: Familiar; runtime enforcement of abstract methods at instantiation
     cons: Forces inheritance; couples every provider to the base module;
           harder to mock in tests; Pythonic community has shifted toward Protocol
  B. Plain duck typing (no contract)
     pros: Maximum flexibility
     cons: No type checker enforcement; year-3 maintenance nightmare;
           breaks the user's "strict typing is non-negotiable" rule
  C. typing.Protocol (PEP 544)
     pros: Structural typing — a provider doesn't need to inherit;
           pyright enforces conformance at compile time;
           easy to mock; community-modern
     cons: Conformance not checked at runtime by default
           (mitigated by an explicit @runtime_checkable + assert in registry)
  D. attrs/dataclass + composition (provider as a struct of callables)
     pros: Functional flavor matches user's coding philosophy
     cons: Loses method-based mental model; harder to add provider-internal
           state (like a cached HTTP client)
CHOSEN: C — typing.Protocol with @runtime_checkable
REASON: Matches the project's "Protocol over inheritance" stance, gives
        compile-time enforcement via pyright (which is already in the
        toolchain), and keeps providers fully decoupled from the base
        module beyond importing the type itself. Runtime checkable
        annotation plus an isinstance assertion in the registry catches
        any provider that drifts.
REVISIT IF: pyright support for Protocol regresses, or the Python typing
            community standardizes on a different idiom.
```

### 5.2 DECISION: Tool-calling unification strategy (Path A vs B vs both)

```
DECISION: How do we expose tool calling across providers with wildly different native APIs?
OPTIONS CONSIDERED:
  A. Native-only — only support providers/models with native tool calling
     pros: Simple, fast, model output reliable
     cons: Locks out smaller local models, gemma family, older models;
           every provider needs to do the work; no graceful degradation
  B. JSON-mode emulation only — universal injection of tool spec into
     system prompt, parse JSON output
     pros: Works on any model; one code path
     cons: Slower (more tokens), less reliable on tiny models, can't
           leverage providers' fine-tuned tool-call paths
  C. Both — native when supports_native_tools=True, emulator otherwise;
     resolver picks the path
     pros: Best of both — performance when available, universality when
           not; isolates the choice in the resolver
     cons: Two code paths to maintain; emulator needs careful prompt design
CHOSEN: C — dual-path with provider-declared capability
REASON: User explicitly chose Path B as the floor for model agnosticism.
        Layering native on top costs almost nothing — each provider that
        has native tools just sets the flag and translates ToolSpec to
        its native format. Providers that don't get the emulator for free.
        This is the only choice that lets adding a new "weak" model (no
        tool support) require zero new code.
REVISIT IF: A standard for cross-provider tool calling emerges (e.g., MCP
            tool spec becomes universal) and obsoletes the translation layer.
```

### 5.3 DECISION: Fallback chain mechanism

```
DECISION: When a provider fails, how do we move on?
OPTIONS CONSIDERED:
  A. Single provider, no fallback (status quo)
     pros: Simplest; no policy decisions
     cons: One outage = total failure; the actual problem the user filed
  B. Try-once fallback (call provider 2 only if provider 1 raises)
     pros: Simple; matches user's terminal-output use case (Gemini 503 →
           Ollama)
     cons: No retry within a provider before falling back; might thrash
  C. Per-provider retry, then fall back
     pros: Handles transient flakes within a provider before moving on
     cons: More complex; adds latency budget concerns
  D. Configurable strategy per provider (retry count, backoff, then fall back)
     pros: Maximum flexibility
     cons: Overkill for Phase 6; configuration surface explosion
CHOSEN: B for Phase 6, with a retry hook reserved for Phase 8+
REASON: User's failure mode is Gemini 503 from quota exhaustion — retrying
        the same provider doesn't help. Falling through to Ollama does.
        Adding per-provider retry can come later if real telemetry shows
        transient flakes within a provider. YAGNI for now.
REVISIT IF: Production telemetry (when it exists) shows intra-provider
            transient errors are common.
```

### 5.4 DECISION: Provider configuration model

```
DECISION: How are providers configured (model, host, key, etc.)?
OPTIONS CONSIDERED:
  A. One flat Settings class — every provider's keys live at the top level
     pros: Matches existing config.py shape; pydantic-settings handles it
     cons: Settings explodes as providers multiply; namespace collisions
  B. Nested Settings — Settings.gemini.api_key, Settings.ollama.host
     pros: Clean grouping; pydantic-settings supports nested models with
           env var prefixes (AZATHOTH_GEMINI__API_KEY)
     cons: Slightly more verbose access; one-time migration of existing keys
  C. Provider self-config — each provider reads its own env vars
     pros: Maximum decoupling
     cons: Hides config surface; can't list "what's configurable" centrally;
           breaks the user's preference for explicit/declarative
CHOSEN: B — nested Settings with per-provider sub-models
REASON: Configuration grows linearly with providers (option A is quadratic
        in confusion). Nested models are pydantic-settings idiomatic and
        give a clean introspection path (`Settings.model_fields` lists
        every provider's config tree). The migration is one-time.
REVISIT IF: pydantic-settings deprecates nested model support (unlikely).
```

### 5.5 DECISION: Where the JSON-mode tool-emulator lives

```
DECISION: Is the tool emulator a provider concern or a core concern?
OPTIONS CONSIDERED:
  A. Each provider implements its own emulator
     pros: Provider-specific tweaks possible
     cons: Duplicate logic across N providers; impossible to maintain at year 3
  B. Shared emulator in core/tools.py, called by the resolver when
     provider.supports_native_tools is False
     pros: One implementation; provider stays dumb; resolver decides path
     cons: Emulator can't tweak per-provider quirks
CHOSEN: B
REASON: The whole point of the universal emulator is that it works anywhere.
        Per-provider tweaks are a smell — if a provider needs special
        emulator behavior, it should set supports_native_tools=True and
        implement native tools. The resolver-orchestrated split keeps each
        component's concern clean.
REVISIT IF: A specific provider needs emulator tweaks that can't be expressed
            via the standard JSON spec injection.
```

### 5.6 DECISION: Local default model

```
DECISION: What is the default Ollama model recommended in config?
OPTIONS CONSIDERED:
  A. gemma4:e4b (user's currently installed model)
     pros: Already on disk; multimodal; current generation
     cons: Doesn't fit fully in 8GB VRAM (CPU spillover); native tool
           calling on Ollama had bugs through 0.20.x (fixed in 0.20.2+)
  B. qwen3:8b-32k (custom 32K context variant of Qwen 3 8B)
     pros: Fits fully in 8GB VRAM; battle-tested tool calls on Ollama;
           ~40-50 tok/s on RTX 4060 mobile
     cons: Older generation than gemma4/qwen3.6; not multimodal
  C. qwen3.6:* — Qwen 3.6 family (only 27B/35B-A3B available as of plan date)
     pros: Newest agentic-coding-focused model; flagship benchmarks
     cons: 27B Q4 = 16.8GB, won't fit in 8GB VRAM without heavy CPU split;
           slower locally
  D. Document a recommended model but don't hardcode anything (user picks)
     pros: No commitment; user chooses based on their hardware
     cons: First-run UX worse; user wanted explicit recommendation
CHOSEN: A (gemma4:e4b) as the default value, with documentation pointing
        to Path B options for users with constrained hardware
REASON: User explicitly stated preference for current-generation models
        (gemma4, qwen3.6) over older sweet-spot models, AND stated their
        speed (~40 wpm equivalent) is acceptable. The CPU spillover is a
        known and accepted cost. Path B's universal emulator means tool
        calling works regardless of native support quirks. Documentation
        will list qwen3:8b-32k and qwen3.6 cloud as alternates.
REVISIT IF: User upgrades hardware, OR a smaller qwen3.6 variant is
            released, OR ollama tool calling for gemma4:e4b regresses.
```

---

## 6. Phased Implementation Plan

Each phase is independently shippable. Each phase has CLI exit criteria. An autonomous executor MUST verify all exit criteria of phase N before starting phase N+1. If any exit criterion fails, the executor MUST stop and report.

### Notation
- `$EXIT` means "the command's exit code must be 0"
- `$STDOUT contains "X"` means substring match in stdout
- `$STDERR empty` means stderr produced no content
- All commands are run from the repo root unless otherwise specified
- All commands use `uv run` to ensure the project's venv is used

---

### PHASE 0 — Floor (correctness)

**Goal:** Project imports cleanly on Python 3.11; tests can be discovered and run; default model is stable.

**Components touched:**
- `src/azathoth/core/i18n.py` (line ~5238 area: replace `except json.JSONDecodeError, IOError:` with `except (json.JSONDecodeError, OSError):`)
- `pyproject.toml` (change `requires-python = ">=3.14"` to `requires-python = ">=3.11"`)
- `src/azathoth/config.py` (change `gemini_model` default from a `*-preview` tag to the current Gemini stable model identifier; add Pydantic field validator that emits `UserWarning` when the configured model name contains `preview`, `experimental`, or `exp`)

**Dependencies:** None (this is the floor)

**Exit criteria (CLI, all must pass):**

```
EC-0.1 | uv sync                                          | $EXIT
EC-0.2 | uv run python -c "import azathoth"               | $EXIT
EC-0.3 | uv run python -c "import azathoth.core.i18n"     | $EXIT
EC-0.4 | uv run python -c "from azathoth.cli.main import app" | $EXIT
EC-0.5 | uv run ruff check src/azathoth/core/i18n.py --select E999 | $EXIT
EC-0.6 | uv run python -c "from azathoth.config import config; assert 'preview' not in config.gemini_model.lower(), config.gemini_model" | $EXIT
EC-0.7 | grep -q 'requires-python = ">=3.11"' pyproject.toml | $EXIT
EC-0.8 | AZATHOTH_GEMINI_MODEL=gemini-3.1-flash-lite-preview uv run python -W error::UserWarning -c "from azathoth.config import config; _ = config.gemini_model" 2>&1 | grep -q "UserWarning" | $EXIT
```

**Risk flags:**
- **[REVISIT]** EC-0.6 hardcodes "preview" check. If Gemini's stable channel ever uses "preview" in a stable model name, this check needs adjusting. Acceptable risk for Phase 0.
- **[ASSUMPTION]** The current Gemini stable model name at execution time will be looked up by the executor via web search at execution time and pinned literally; this plan does not commit a specific string, only the validator behavior.

---

### PHASE 1 — Test Truth + Import Fitness

**Goal:** Establish that the test suite actually runs every module; identify and document why the broken `i18n.py` slipped past tests; install a fitness function that prevents recurrence.

**Components touched:**
- `tests/conftest.py` (audit — must not silently swallow `ImportError`)
- `tests/core/test_i18n.py` (must collect and run)
- `src/azathoth/dev/__init__.py` (new, empty)
- `src/azathoth/dev/import_check.py` (new — walks `pkgutil.walk_packages` over `azathoth`, imports every submodule, exits non-zero with the failing module name on any `ImportError` or `SyntaxError`)
- `pyproject.toml` (add `pytest --strict-markers --strict-config -W error` to default pytest options; add a `[project.scripts]` entry for `azathoth-import-check`)

**Dependencies:** Phase 0 must be complete.

**Exit criteria (CLI, all must pass):**

```
EC-1.1 | uv run pytest --collect-only -q 2>&1 | grep -q "test_i18n" | $EXIT
EC-1.2 | uv run pytest tests/ -q --strict-markers --strict-config | $EXIT (note: tests must execute; passing/failing of individual tests is captured in EC-1.6)
EC-1.3 | uv run azathoth-import-check                    | $EXIT
EC-1.4 | uv run azathoth-import-check --json | python -c "import sys, json; d=json.load(sys.stdin); assert d['errors']==[], d" | $EXIT
EC-1.5 | uv run python -m azathoth.dev.import_check      | $EXIT
EC-1.6 | uv run pytest tests/core/test_i18n.py -q 2>&1 | tee /tmp/i18n_test.log; grep -E "passed|failed|error" /tmp/i18n_test.log | $EXIT
EC-1.7 | test -f CONTRIBUTING.md && grep -q "import-check" CONTRIBUTING.md | $EXIT
```

**Risk flags:**
- **[REVISIT]** EC-1.6 documents that tests run; this plan does NOT require all tests to pass. Discovering real test failures here is the point. The executor MUST produce a triage report at `/tmp/azathoth-phase1-triage.md` listing every test that fails after Phase 0 fixes, with one-sentence root cause per failure. Fixing them is a separate scope.
- **[HIGH RISK]** If Phase 1 reveals more than 5 broken tests, the executor MUST stop and produce the triage report rather than proceeding. Stop condition: `[ $(pytest tests/ -q 2>&1 | grep -c "FAILED") -gt 5 ]` → halt.

---

### PHASE 2 — Provider Protocol Contract

**Goal:** Define the abstract contract — types, Protocol, registry — with zero provider implementations. Pyright must accept the Protocol; tests must verify the contract is well-formed.

**Components touched:**
- `src/azathoth/providers/__init__.py` (re-exports from `base`)
- `src/azathoth/providers/base.py` (new — `Provider` Protocol with `name`, `supports_native_tools`, `generate()`; `LLMResponse`, `ToolSpec`, `ToolCall` Pydantic models; exception hierarchy: `ProviderError` → `ProviderUnavailable`, `ProviderAuthError`, `ProviderRateLimitError`, `ProviderSchemaError`)
- `src/azathoth/providers/registry.py` (new — `register(name, factory)`, `get_provider(name)`, `list_providers()`, `_PROVIDERS: dict[str, Callable[[], Provider]]`)
- `src/azathoth/core/exceptions.py` (extended — `AzathothError` base, re-exports of provider exceptions)
- `tests/providers/__init__.py` (new, empty)
- `tests/providers/test_base.py` (new — verifies Pydantic models reject malformed input, verifies exception hierarchy, verifies `Provider` Protocol is `@runtime_checkable`)
- `tests/providers/test_registry.py` (new — verifies registration/lookup, verifies `get_provider` raises `KeyError` for unknown names, verifies a fake provider passing `isinstance(x, Provider)` can be registered)
- `pyproject.toml` (add `[tool.pyright]` strict-scoped section: `strict = ["src/azathoth/providers", "src/azathoth/core/llm.py", "src/azathoth/core/tools.py"]`)

**Dependencies:** Phase 1 complete.

**Exit criteria (CLI, all must pass):**

```
EC-2.1 | uv run python -c "from azathoth.providers.base import Provider, ToolSpec, ToolCall, LLMResponse, ProviderError, ProviderUnavailable, ProviderAuthError, ProviderRateLimitError, ProviderSchemaError" | $EXIT
EC-2.2 | uv run python -c "from azathoth.providers.registry import register, get_provider, list_providers; assert list_providers() == [], list_providers()" | $EXIT
EC-2.3 | uv run pyright src/azathoth/providers/ | $EXIT
EC-2.4 | uv run pyright --outputjson src/azathoth/providers/ | python -c "import sys, json; d=json.load(sys.stdin); assert d['summary']['errorCount']==0, d['summary']" | $EXIT
EC-2.5 | uv run pytest tests/providers/test_base.py tests/providers/test_registry.py -q | $EXIT
EC-2.6 | uv run python -c "from azathoth.providers.base import Provider; from typing import get_type_hints; assert hasattr(Provider, '__protocol_attrs__') or callable(Provider)" | $EXIT
EC-2.7 | uv run python -c "from azathoth.providers.base import Provider; import typing; assert getattr(Provider, '_is_runtime_protocol', False) or '@runtime_checkable' in (Provider.__doc__ or '')" | $EXIT
EC-2.8 | uv run azathoth-import-check | $EXIT
```

**Risk flags:**
- None significant — this phase adds new code, doesn't change behavior. The contract is the bet; if it's wrong, Phase 3 will surface it.

---

### PHASE 3 — Gemini Extraction (refactor existing)

**Goal:** Move Google `genai` SDK code from `core/llm.py` into `providers/gemini.py`. Existing CLI behavior is unchanged. Consumers of `core.llm.generate()` see no breaking change.

**Components touched:**
- `src/azathoth/providers/gemini.py` (new — `GeminiProvider` class implementing `Provider`; supports `generate()` text + JSON mode; `supports_native_tools = True` but tools translation is a no-op stub returning empty `tool_calls` (real translation lands in Phase 5))
- `src/azathoth/providers/__init__.py` (registers `gemini` provider via the registry on import)
- `src/azathoth/core/llm.py` (rewritten as a façade — `generate()` resolves provider from config and delegates; preserves the existing public signature for backward compatibility, with a deprecation warning if called without `provider=` argument)
- `src/azathoth/config.py` (adds `llm_provider: str = "gemini"`; nested `GeminiSettings` sub-model with `api_key` and `model`; existing flat `gemini_api_key` and `gemini_model` continue to work via backward-compat aliases that emit `DeprecationWarning`)
- `tests/providers/test_gemini.py` (new — mocks `google.genai.Client`; verifies request shape, response parsing, error mapping: 4xx → `ProviderError`, 5xx → `ProviderUnavailable`, network → `ProviderUnavailable`, auth → `ProviderAuthError`)
- `tests/core/test_llm.py` (rewritten — verifies façade routes to registered provider, verifies deprecated signature still works with warning)

**Dependencies:** Phase 2 complete.

**Exit criteria (CLI, all must pass):**

```
EC-3.1 | uv run python -c "from azathoth.providers import gemini; from azathoth.providers.registry import get_provider; p = get_provider('gemini'); assert p.name == 'gemini'" | $EXIT
EC-3.2 | uv run python -c "from azathoth.providers.registry import get_provider; from azathoth.providers.base import Provider; p = get_provider('gemini'); assert isinstance(p, Provider)" | $EXIT
EC-3.3 | uv run pyright src/azathoth/providers/gemini.py src/azathoth/core/llm.py | $EXIT
EC-3.4 | uv run pytest tests/providers/test_gemini.py tests/core/test_llm.py -q | $EXIT
EC-3.5 | uv run pytest --cov=src/azathoth/providers/gemini --cov=src/azathoth/core/llm --cov-fail-under=85 tests/providers/test_gemini.py tests/core/test_llm.py | $EXIT
EC-3.6 | grep -q "from google" src/azathoth/core/llm.py && exit 1 || exit 0  (* google-genai must NOT be imported from core/llm.py *)
EC-3.7 | uv run python -c "import ast, pathlib; tree = ast.parse(pathlib.Path('src/azathoth/core/llm.py').read_text()); imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]; mods = [getattr(n, 'module', None) or (n.names[0].name if isinstance(n, ast.Import) else None) for n in imports]; assert not any(m and ('google' in m or 'genai' in m) for m in mods), mods" | $EXIT
EC-3.8 | uv run azathoth-import-check | $EXIT
EC-3.9 | uv run ruff check src/azathoth/providers/gemini.py src/azathoth/core/llm.py | $EXIT
```

**Risk flags:**
- **[HIGH RISK]** Backward compatibility shim for the deprecated `gemini_api_key`/`gemini_model` flat fields is the most error-prone bit. The executor MUST verify with EC-3.4 that calling `core.llm.generate()` with the OLD signature still works (Phase 3 must not break existing CLI commands).
- **[REVISIT]** `supports_native_tools=True` with stub translation is a deliberate placeholder. Phase 5 lands the real implementation. The Phase 3 → Phase 5 gap is acceptable because no consumer calls `generate_with_tools()` until Phase 5.

---

### PHASE 4 — Ollama Provider

**Goal:** A second concrete provider exists and is selectable via config and CLI flag. Local development with Ollama works end-to-end.

**Components touched:**
- `src/azathoth/providers/ollama.py` (new — `OllamaProvider` class; uses `httpx.AsyncClient` against the Ollama HTTP API at `/api/chat`; reads `model`, `host` from `OllamaSettings`; `supports_native_tools = True` with native translation working for non-tool calls; tools support stubbed pending Phase 5 emulator integration; honors `num_ctx` from config)
- `src/azathoth/providers/__init__.py` (registers `ollama` provider)
- `src/azathoth/config.py` (adds nested `OllamaSettings` with `host: str = "http://localhost:11434"`, `model: str = "gemma4:e4b"`, `num_ctx: int = 32768`, `request_timeout: float = 120.0`; updates `Settings.llm_provider` documentation to list valid choices)
- `src/azathoth/cli/commands/workflow.py` (adds `--provider / -p` option to `commit_cmd` and any other commands that call `core.llm.generate`; the option overrides config for that invocation only)
- `pyproject.toml` (add `ollama` dependency? — NO; use `httpx` directly to avoid extra dep weight; if needed for typed responses add `ollama` as `[project.optional-dependencies] local = ["ollama>=..."]`. **Decision: stick with httpx, document the daemon URL contract**.)
- `tests/providers/test_ollama.py` (new — uses `pytest-httpx` to mock the Ollama daemon; verifies request payload shape, response parsing, error mapping for 4xx/5xx/timeout/connection-refused)

**Dependencies:** Phase 3 complete.

**Exit criteria (CLI, all must pass):**

```
EC-4.1 | uv run python -c "from azathoth.providers import ollama as o; from azathoth.providers.registry import get_provider; p = get_provider('ollama'); assert p.name == 'ollama'" | $EXIT
EC-4.2 | uv run pyright src/azathoth/providers/ollama.py | $EXIT
EC-4.3 | uv run pytest tests/providers/test_ollama.py -q | $EXIT
EC-4.4 | uv run pytest --cov=src/azathoth/providers/ollama --cov-fail-under=85 tests/providers/test_ollama.py | $EXIT
EC-4.5 | uv run az workflow commit --help 2>&1 | grep -q "\-\-provider" | $EXIT
EC-4.6 | uv run az workflow commit -p ollama --help 2>&1 | grep -q "ollama" || true   (* sanity: -p is parseable *)
EC-4.7 | (curl -fsS http://localhost:11434/api/tags >/dev/null 2>&1 && uv run az workflow commit --provider=ollama --dry-run --yes -f "test" 2>&1 | grep -qiE "(commit|message|generated)") || echo "SKIP: ollama daemon not available"   (* Conditional: only enforced if daemon is reachable; the executor must run "ollama serve" in the background before this phase if not running *)
EC-4.8 | grep -q "ollama" src/azathoth/config.py | $EXIT
EC-4.9 | uv run azathoth-import-check | $EXIT
EC-4.10 | uv run ruff check src/azathoth/providers/ollama.py src/azathoth/cli/commands/workflow.py | $EXIT
```

**Risk flags:**
- **[REVISIT]** EC-4.7 conditionally skips if no Ollama daemon. The executor MUST attempt to start `ollama serve` in the background and pull `gemma4:e4b` before this phase if not present, OR explicitly mark this exit criterion as "SKIPPED" in the phase report. Skipping without record is a stop condition.
- **[ASSUMPTION]** `httpx>=0.28.1` is already in dependencies (verified in pyproject.toml) — no new dependency added.

---

### PHASE 5 — Universal Tool Calling

**Goal:** `ToolSpec` is the cross-provider tool definition. Tool calls work natively when the provider declares support, fall back to JSON-mode emulation otherwise. Both paths are testable in isolation.

**Components touched:**
- `src/azathoth/core/tools.py` (new — `ToolSpec` Pydantic model with `name`, `description`, `parameters_schema: dict`; helper `tool_spec_from_pydantic(model: type[BaseModel]) -> ToolSpec` that derives JSON Schema from a Pydantic input model; `render_tools_as_json_spec(tools: list[ToolSpec]) -> str` for prompt injection; `parse_tool_calls_from_json(text: str) -> list[ToolCall]` for emulator path; `dispatch(call: ToolCall, registry: dict[str, Callable]) -> Any` for actual tool execution)
- `src/azathoth/core/llm.py` (extended — adds `generate_with_tools(system, user, tools, *, provider=None) -> LLMResponse`; if resolved provider has `supports_native_tools=True`, calls `provider.generate(..., tools=tools)`; otherwise wraps with the emulator: augments system prompt with tool spec, requests JSON mode, parses output back into `LLMResponse.tool_calls`)
- `src/azathoth/providers/gemini.py` (extended — implements native `tools` translation: `ToolSpec` → `google.genai.types.Tool` with `FunctionDeclaration`; parses native response back into `ToolCall` instances)
- `src/azathoth/providers/ollama.py` (extended — implements native `tools` translation: `ToolSpec` → Ollama's `tools` array per the `/api/chat` schema; parses `tool_calls` field back into `ToolCall` instances)
- `tests/core/test_tools.py` (new — verifies `tool_spec_from_pydantic`, `render_tools_as_json_spec`, `parse_tool_calls_from_json` on synthetic inputs; verifies dispatch behavior; verifies that an emulator round-trip on a fake provider whose generate() returns a JSON tool-call string produces the expected `ToolCall`)
- `tests/providers/test_gemini.py` (extended — verifies native tool round-trip with mocked SDK)
- `tests/providers/test_ollama.py` (extended — verifies native tool round-trip with mocked HTTP)

**Dependencies:** Phase 4 complete.

**Exit criteria (CLI, all must pass):**

```
EC-5.1 | uv run python -c "from azathoth.core.tools import ToolSpec, tool_spec_from_pydantic, render_tools_as_json_spec, parse_tool_calls_from_json, dispatch" | $EXIT
EC-5.2 | uv run python -c "from azathoth.core.llm import generate_with_tools" | $EXIT
EC-5.3 | uv run pyright src/azathoth/core/tools.py | $EXIT
EC-5.4 | uv run pytest tests/core/test_tools.py -q | $EXIT
EC-5.5 | uv run pytest --cov=src/azathoth/core/tools --cov-fail-under=85 tests/core/test_tools.py | $EXIT
EC-5.6 | uv run pytest tests/providers/test_gemini.py tests/providers/test_ollama.py -q -k "tools or tool_call" | $EXIT
EC-5.7 | uv run python -c "
from pydantic import BaseModel
from azathoth.core.tools import tool_spec_from_pydantic
class Args(BaseModel):
    city: str
    units: str = 'celsius'
spec = tool_spec_from_pydantic(Args)
assert spec.parameters_schema['properties']['city']['type'] == 'string', spec
assert 'units' in spec.parameters_schema['properties']
" | $EXIT
EC-5.8 | uv run azathoth-import-check | $EXIT
```

**Risk flags:**
- **[REVISIT]** Pydantic-to-JSON-Schema generation has known quirks (refs, `$defs`, optional handling). The implementation must use `model.model_json_schema()` and then flatten any `$defs` for compatibility with providers that don't follow refs. EC-5.7 asserts a specific schema shape; deviations break the test.
- **[HIGH RISK]** The emulator path has the highest defect potential. Two-shot tests are mandatory: (a) emulator → fake provider → tool dispatch → final response, (b) same flow with native path. Both must pass identical assertions on the final state.

---

### PHASE 6 — Selector & Fallback Chain

**Goal:** Multi-provider configuration works. When provider 1 raises `ProviderUnavailable`, provider 2 is tried. The CLI flag continues to override.

**Components touched:**
- `src/azathoth/config.py` (changes `llm_provider: str` to `llm_providers: list[str] = ["gemini", "ollama"]`; keeps `llm_provider: str | None = None` as a single-provider override that coerces to a 1-element list when set; adds `llm_total_timeout: float = 120.0`)
- `src/azathoth/core/llm.py` (extended — `generate()` and `generate_with_tools()` iterate `config.llm_providers` (or the CLI-overridden list), trying each, catching `ProviderUnavailable` and `asyncio.TimeoutError` to continue, catching `ProviderError` to halt and re-raise; on full exhaustion raises `AllProvidersFailedError` with a `causes: list[Exception]` attribute; logs each fallback hop at INFO with structured fields)
- `src/azathoth/providers/base.py` (extended — `AllProvidersFailedError(ProviderError)` with `causes` attribute)
- `tests/providers/test_fallback.py` (new — uses two synthetic test providers in the registry; verifies: (a) success on first provider returns immediately, (b) `ProviderUnavailable` on first triggers second, (c) `ProviderError` on first halts and re-raises without trying second, (d) all-fail raises `AllProvidersFailedError` with all causes, (e) total-timeout enforced via `asyncio.wait_for`)

**Dependencies:** Phase 5 complete.

**Exit criteria (CLI, all must pass):**

```
EC-6.1 | uv run python -c "from azathoth.config import config; assert config.llm_providers == ['gemini', 'ollama'], config.llm_providers" | $EXIT
EC-6.2 | uv run python -c "from azathoth.providers.base import AllProvidersFailedError, ProviderError; assert issubclass(AllProvidersFailedError, ProviderError)" | $EXIT
EC-6.3 | uv run pytest tests/providers/test_fallback.py -q | $EXIT
EC-6.4 | uv run pytest --cov=src/azathoth/core/llm --cov-fail-under=85 tests/providers/test_fallback.py tests/core/test_llm.py | $EXIT
EC-6.5 | AZATHOTH_LLM_PROVIDERS='["nonexistent","gemini"]' uv run python -c "from azathoth.config import Settings; s = Settings(); assert s.llm_providers == ['nonexistent', 'gemini'], s.llm_providers" | $EXIT
EC-6.6 | uv run pyright src/azathoth/core/llm.py | $EXIT
EC-6.7 | uv run azathoth-import-check | $EXIT
```

**Risk flags:**
- **[REVISIT]** EC-6.5 verifies env var parsing of a JSON list. pydantic-settings' default behavior for `list[str]` from env vars is comma-separated; this plan REQUIRES JSON list parsing, which means setting `model_config["env_parse_none_str"]` and using a Pydantic `field_validator` for list coercion. The executor must verify both JSON-list (`'["a","b"]'`) and comma-separated (`'a,b'`) forms work.
- **[HIGH RISK]** Logging during fallback can leak sensitive data if not careful. Tests must verify that no API key, no full prompt, and no full diff text appears in logged fallback events.

---

### PHASE 7 — Architecture Fitness Functions (CI gates)

**Goal:** The architectural rules from §2.2 are enforced automatically. A pull request that violates a dependency rule fails CI without human review.

**Components touched:**
- `src/azathoth/dev/import_check.py` (already exists from Phase 1; no change)
- `src/azathoth/dev/architecture_check.py` (new — uses `ast` to walk every `.py` file under `src/azathoth/` and verify the dependency rules from §2.2; emits a machine-readable JSON report on stdout when `--json` is passed; exits non-zero on any violation with a human-readable summary on stderr)
- `pyproject.toml` (add `azathoth-architecture-check` as a `[project.scripts]` entry)
- `.github/workflows/ci.yml` (new or extended — runs on Python 3.11, 3.12, 3.13 matrix: `uv sync`, `uv run azathoth-import-check`, `uv run azathoth-architecture-check`, `uv run ruff check src/`, `uv run pyright src/`, `uv run pytest tests/ --strict-markers --strict-config`)
- `CONTRIBUTING.md` (extended — section "Architectural rules and how they're enforced", lists each fitness function and what it catches)

**Dependencies:** Phase 6 complete.

**Exit criteria (CLI, all must pass):**

```
EC-7.1 | uv run azathoth-architecture-check | $EXIT
EC-7.2 | uv run azathoth-architecture-check --json | python -c "import sys, json; d=json.load(sys.stdin); assert d['violations']==[], d['violations']" | $EXIT
EC-7.3 | uv run azathoth-import-check | $EXIT
EC-7.4 | uv run ruff check src/                   | $EXIT
EC-7.5 | uv run pyright src/azathoth/providers/ src/azathoth/core/llm.py src/azathoth/core/tools.py | $EXIT
EC-7.6 | uv run pytest tests/ --strict-markers --strict-config -q | $EXIT
EC-7.7 | test -f .github/workflows/ci.yml         | $EXIT
EC-7.8 | grep -E "azathoth-import-check|azathoth-architecture-check" .github/workflows/ci.yml | $EXIT
EC-7.9 | grep -q "Architectural rules" CONTRIBUTING.md | $EXIT
EC-7.10 | (* Self-test: introduce a deliberate violation and verify the check catches it. *)
         echo 'from azathoth.providers.gemini import GeminiProvider' >> /tmp/violation.py && \
         cp src/azathoth/cli/main.py src/azathoth/cli/main.py.bak && \
         cat /tmp/violation.py >> src/azathoth/cli/main.py && \
         (uv run azathoth-architecture-check; rc=$?; cp src/azathoth/cli/main.py.bak src/azathoth/cli/main.py; rm src/azathoth/cli/main.py.bak; [ $rc -ne 0 ]) | $EXIT
```

**Risk flags:**
- **[REVISIT]** EC-7.10 mutates source temporarily to verify the fitness function actually catches violations. The executor MUST restore the file before continuing regardless of the test's outcome (the inline `cp .bak` handles this).
- **[ASSUMPTION]** GitHub Actions is the CI target. If a different CI is used, EC-7.7/7.8 must be adapted to the actual CI config file location.

---

### Optional Phase 8+ — Provider Expansion (deferred)

Adding Anthropic, OpenAI, Alibaba Cloud (Qwen) providers becomes a single-file PR per provider after Phase 7. Each follows the template established by `providers/ollama.py` and adds an entry to its config sub-model. Exit criteria for each new provider:
- `EC-8.X.1 | uv run pyright src/azathoth/providers/<name>.py | $EXIT`
- `EC-8.X.2 | uv run pytest tests/providers/test_<name>.py -q | $EXIT`
- `EC-8.X.3 | uv run azathoth-architecture-check | $EXIT`
- `EC-8.X.4 | uv run azathoth-import-check | $EXIT`

This is intentionally not part of the main plan because (a) it's mechanical, (b) it depends on which providers the user prioritizes, (c) the architecture's whole point is to make these additions trivial.

---

## 7. Implementation Management

### 7.1 Sequencing (dependency graph)

```
Phase 0 (Floor)
   │
   └─→ Phase 1 (Test truth + import fitness)
          │
          └─→ Phase 2 (Provider Protocol contract)
                 │
                 └─→ Phase 3 (Gemini extraction)
                        │
                        └─→ Phase 4 (Ollama provider)
                               │
                               └─→ Phase 5 (Universal tool calling)
                                      │
                                      └─→ Phase 6 (Selector + fallback chain)
                                             │
                                             └─→ Phase 7 (Fitness functions in CI)
                                                    │
                                                    └─→ Phase 8+ (more providers, deferred)
```

The chain is strictly linear. There is no parallelization opportunity given the single-developer constraint.

### 7.2 Critical Path
**The entire chain is critical path.** Any phase failing its exit criteria blocks the next. There is no "we can start Phase 4 while Phase 3 is being polished" — Phase 3's exit criteria include behavior preservation tests that Phase 4 depends on for confidence.

### 7.3 Integration Points
- **Phase 3 ↔ existing CLI commands**: backward compatibility shim is the single highest-risk integration point. Failure here breaks user-facing functionality.
- **Phase 5 emulator ↔ Phase 5 native paths**: must produce identical `LLMResponse` shapes for callers; integration tests cross-validate.
- **Phase 6 fallback ↔ Phase 4 Ollama**: fallback assumes Ollama works locally; if Ollama daemon isn't reachable during testing, fallback test (EC-6.3) uses synthetic providers.

### 7.4 Breaking Changes (flag explicitly)
- **[BREAKING — accepted]** `requires-python` floor changes from `>=3.14` to `>=3.11` (Phase 0). This is not actually breaking (it widens compatibility), but it changes the lockfile.
- **[BREAKING — internal only]** `core.llm.generate()` gains an optional `provider` parameter (Phase 3); old callers continue to work via deprecation warning. Removal of the deprecation is a future concern, not part of this plan.
- **[BREAKING — accepted]** Default model identifier changes (Phase 0). Users with custom configs are unaffected; users on defaults get a stable model instead of a preview tag.
- **[BREAKING — config schema]** `gemini_api_key` and `gemini_model` flat fields are deprecated in favor of nested `gemini.api_key` and `gemini.model` (Phase 3). Backward-compat alias maintained with deprecation warning. **This is the only schema change visible to end users.**

### 7.5 Ownership
Single-developer project; ownership is a non-issue. The plan is structured so an autonomous coding agent can own the entirety, with the human gating each phase by reviewing the exit criteria report.

---

## 8. Validation & Testing Strategy

### 8.1 Test Layer Matrix

| Layer | Test type | What it verifies | Where |
|---|---|---|---|
| Pydantic types | Unit | Model validation rejects bad input | `tests/providers/test_base.py` |
| Provider Protocol conformance | Unit | A class structurally satisfying Provider passes `isinstance` | `tests/providers/test_base.py` |
| Provider registry | Unit | Register/lookup, unknown names raise | `tests/providers/test_registry.py` |
| Gemini provider | Unit (mocked SDK) | Request shape, response parse, error mapping | `tests/providers/test_gemini.py` |
| Ollama provider | Unit (mocked HTTP via pytest-httpx) | Request shape, response parse, error mapping | `tests/providers/test_ollama.py` |
| Tool spec generation | Unit | Pydantic → JSON Schema correctness | `tests/core/test_tools.py` |
| Tool emulator | Unit (synthetic provider) | Round-trip: spec injection → fake JSON output → ToolCall parse | `tests/core/test_tools.py` |
| LLM façade | Unit | Routes to correct provider; deprecation warning fires | `tests/core/test_llm.py` |
| Fallback chain | Integration (synthetic providers) | Provider 1 fails → Provider 2 called; halt on non-retryable | `tests/providers/test_fallback.py` |
| CLI workflow | E2E (mocked HTTP) | `az workflow commit --provider=ollama --dry-run` produces output | `tests/cli/test_workflow.py` |
| Architecture | Fitness function | Dependency direction rules; no forbidden imports | `azathoth-architecture-check` |
| Import health | Fitness function | Every module loads | `azathoth-import-check` |

### 8.2 Architecture Fitness Functions (machine-enforced rules)

The single most important deliverable of this plan is the set of automated checks that run in CI and locally:

1. **Import health** (`azathoth-import-check`) — walks every module via `pkgutil.walk_packages`, imports each, exits non-zero on the first `ImportError` or `SyntaxError`. Catches the original i18n.py-style bug class permanently.

2. **Architecture rules** (`azathoth-architecture-check`) — uses `ast` to parse every `.py` file in `src/azathoth/` and verifies:
   - No file in `cli/` or `mcp/` imports from `azathoth.providers.<concrete>` (only `azathoth.providers.base` is allowed)
   - No file in `core/` (other than `core/llm.py`) imports from `azathoth.providers.*`
   - No file in `providers/<name>.py` imports from `azathoth.providers.<other>`
   - No file in `providers/*` imports from `azathoth.cli.*` or `azathoth.mcp.*`

3. **Type contracts** (`pyright --strict` scoped) — `src/azathoth/providers/`, `src/azathoth/core/llm.py`, `src/azathoth/core/tools.py` must have zero pyright errors in strict mode.

4. **Lint rules** (`ruff check src/`) — strict ruleset, errors not warnings, no exclusions for new code.

5. **Coverage budgets** (`pytest --cov-fail-under=85` scoped) — `providers/`, `core/llm.py`, `core/tools.py` require ≥85% coverage; if a phase's coverage drops below, CI fails.

6. **Pytest strictness** (`--strict-markers --strict-config`) — undeclared markers fail collection; configuration drift fails immediately.

### 8.3 Local Dev Validation (pre-commit equivalent)

A single command must clear before any commit:

```
uv run azathoth-import-check && \
uv run azathoth-architecture-check && \
uv run ruff check src/ && \
uv run pyright src/azathoth/providers/ src/azathoth/core/llm.py src/azathoth/core/tools.py && \
uv run pytest tests/ -q --strict-markers --strict-config
```

This command MUST be documented in `CONTRIBUTING.md`. It SHOULD be wired as a `just check` recipe in a `Justfile` (or equivalent) for one-keystroke invocation.

### 8.4 Observability Strategy
Out of scope for this refactor in terms of *infrastructure* (no metrics endpoint, no tracing). In scope as *log structure*:
- All fallback events log at INFO with fields `provider`, `attempt_index`, `error_class`
- All provider errors log at WARNING with fields `provider`, `error_class`, `error_message_preview` (first 200 chars)
- All successful LLM calls log at DEBUG with fields `provider`, `model`, `prompt_token_estimate`, `response_token_estimate`
- Logging uses `logging.getLogger("azathoth")` as the root; per-module loggers via `logging.getLogger(__name__)` inherit

This shape is a contract: any future metrics/tracing layer can scrape these log fields without code changes.

---

## 9. Open Questions & Risks

### 9.1 Open Questions (blocking resolution at execution time)

| ID | Question | Resolution path |
|---|---|---|
| OQ-1 | What is the current Gemini stable model name at execution time? | Executor MUST web-search Google AI docs at the start of Phase 0 and pin the literal string. Do not commit a placeholder. |
| OQ-2 | Does the user's `gemma4:e4b` Ollama install support tool calling natively in Ollama 0.21.0? | Executor MUST run `ollama show gemma4:e4b` and check the `Capabilities` line for `tools`. If absent, set `OllamaProvider.supports_native_tools = False` and rely on the emulator path. |
| OQ-3 | Are there other syntax errors in the codebase besides `i18n.py:5238`? | Phase 1's `azathoth-import-check` answers this in one CI run. If found, they're additional Phase 0 fixes. |
| OQ-4 | Does the existing test suite (passed before Phase 0) have failures that surface after Phase 0 fixes? | Phase 1's triage report (forced output of EC-1.6) lists them. >5 failures → halt and report. |
| OQ-5 | What's the canonical JSON Schema dialect each provider expects for tool parameters? | Phase 5 implementation pins JSON Schema 2020-12 (the most permissive common ancestor). If a provider rejects, an adapter shim in that provider's file flattens to draft-07. |

### 9.2 Risk Register

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R-1 | Phase 0 fix to `i18n.py` exposes a cascade of test failures the original suite was hiding | High likelihood, medium impact | Phase 1 triage report; `>5 failures = halt` stop condition |
| R-2 | Pydantic-to-JSON-Schema generation produces output that some provider's API rejects | Medium likelihood, medium impact | EC-5.7 asserts a known-good shape; per-provider shim allowed in `providers/<name>.py` |
| R-3 | Backward-compat shim for old `core.llm.generate()` signature is incomplete; existing CLI breaks | Medium likelihood, high impact | EC-3.4 mandates regression test; manual smoke test of `az workflow commit --dry-run` against a mock |
| R-4 | Ollama daemon not reachable in CI; Phase 4 EC-4.7 conditionally skips, masking real failures | Low likelihood (CI), medium impact | Phase 4 documents that the executor must start an Ollama daemon and pull `gemma4:e4b` before this phase, OR explicitly mark EC-4.7 as SKIPPED in the report |
| R-5 | Architecture fitness function (Phase 7) produces false positives, blocking legitimate work | Medium likelihood, low impact | EC-7.10 self-test verifies it catches a real violation; if it errors on legitimate code, the rules in §2.2 are wrong and must be revised — surface this rather than disabling the check |
| R-6 | Phase 6 fallback logging leaks API keys or full prompts | Low likelihood, high impact | Tests in `test_fallback.py` MUST assert that no string matching `[A-Za-z0-9_]{30,}` (a key-shaped token) appears in any logged record; full prompts truncated to 200 chars at WARNING and below |
| R-7 | Plan execution drifts from spec because the executor "improves" on it | Medium likelihood, high impact | Plan is the source of truth; deviations require a documented `[DEVIATION]` block in the executor's report. Anything else is a defect. |

### 9.3 Things to Spike Before Committing
None of significance. The architecture is conventional (Strategy + Registry + Adapter + Chain of Responsibility) and the patterns are well-understood. The risks are in execution discipline, not design.

---

## 10. Executor Instructions (for autonomous run)

If a coding agent is executing this plan without supervision, it MUST:

1. **Read this plan in its entirety** before writing any code. Do not start Phase 0 with only Phase 0 in context.
2. **Resolve Open Questions OQ-1 and OQ-2** before starting Phase 0. Use web search (OQ-1) and `ollama show` (OQ-2). Document the resolved values in a `PLAN_RESOLUTIONS.md` file at the repo root.
3. **For each phase**:
   - Implement the components listed under "Components touched"
   - Run all exit criteria as a script: `bash phase-N-check.sh` exits 0 if all pass
   - Produce a phase report at `/tmp/azathoth-phase-N-report.md` with: pass/fail per exit criterion, time elapsed, any deviations
4. **Halt and report** if any of the following:
   - Any exit criterion fails after 3 honest attempts to fix
   - Phase 1 triage shows >5 unrelated test failures
   - Phase 7's self-test (EC-7.10) cannot be made to pass without disabling the architecture check
   - Open Question discovered mid-phase that requires human input
5. **Never silence a fitness function.** If `azathoth-architecture-check` complains, fix the code. Do not edit the check to ignore the violation.
6. **Never weaken pyright strictness or ruff rulesets** to make a phase pass. They are floor not ceiling.
7. **Commit per phase**, not per file. One git commit at the end of each phase, message: `phase N: <phase title>`. The body lists exit criteria results.
8. **No scope creep.** If a desirable improvement is discovered (e.g., "I noticed `core/workflow.py` could use a refactor"), record it in `FUTURE.md` and proceed. Do not implement.

---

## 11. Plan Sign-off Checklist

Before considering this plan complete, the user (yrrrrrf) should confirm:

- [ ] §1.4 "Out of Scope" matches the user's mental model of what NOT to build
- [ ] §1.5 Assumptions are all acceptable (especially the breaking-change tolerance)
- [ ] §5.6 Default local model choice (`gemma4:e4b`) aligns with stated preference
- [ ] §7.4 Breaking changes are all acceptable (especially the config schema migration)
- [ ] §10 Executor instructions are sufficient for the intended autonomous run

If any item is unchecked, revise the plan before execution begins.

---

**End of plan.**