# Azathoth — Plan 3: Architecture Consolidation

**A spec-driven implementation plan. Zero code by design — every interface below
is described as a contract, not an implementation.**

|                |                                                                                                        |
| -------------- | ------------------------------------------------------------------------------------------------------ |
| **Supersedes** | Plan 1 (complete, see §1.4), Plan 2 (absorbed into Phases 5-6)                                         |
| **Assumes**    | The `just` harness (`justfile` + `scripts/*.just`) exists and is authoritative. Not re-specified here. |
| **Baseline**   | Snapshot `azathoth-20260724_232855` + `ci-report.md` deltas                                            |
| **Horizon**    | 10 years                                                                                               |

---

## 0 · Executive Summary

Azathoth is an opinionated AI development framework: a provider-agnostic LLM
façade with a fallback chain, wrapped by three capability domains (ingest, git
workflow, i18n translation, plus scout), surfaced through two peer presentation
packages (a Typer CLI and FastMCP stdio servers).

Its provider layer is already well-architected — a real Protocol port, typed
exception hierarchy, lazy registry, fallback resolver, and two AST-based fitness
functions. **The problem is that this discipline stops at the `providers/`
boundary.** Everything above it — `core/i18n.py`, `core/ingest.py`,
`core/workflow.py`, all of `cli/`, all of `mcp/` — predates it, and the seam is
literally visible: `from __future__ import annotations` appears in exactly the
eight post-discipline files and none of the fourteen others.

The consequence is that `core/` exposes **primitives but no workflows**, so
`cli/` and `mcp/` each independently re-orchestrate the same five use cases —
ten implementations for five behaviours, with one nine-line git-porcelain parser
existing byte-identically in two files. Adding the scout MCP server (Plan 2)
would make it a third re-orchestration.

This plan does one structural thing — **push orchestration down into `core/` and
reduce `cli/` and `mcp/` to renderers** — and uses that move as the vehicle for
a Python 3.14 modernisation pass, a shared git/serialisation substrate, and four
new architecture fitness functions that make the dependency diagram executable
rather than aspirational.

The long-term bet: **the ports (`Provider` Protocol) and the use-case contracts
(result DTOs) outlive every SDK, every CLI framework, and every agent protocol
they are rendered through.** In a field where the LLM provider API surface
churns annually, the code that survives is the code that never named a vendor.

---

## 1 · Context & Constraints

### 1.1 Project context

Existing single-package Python project, pre-alpha (`0.0.3`), single developer,
no external users. Hatchling build, `uv` dependency management, Nix devshell.
Not a monorepo. Distribution is one PyPI package exposing console scripts plus
MCP stdio servers.

### 1.2 Scale targets

Deliberately modest and stated so the architecture is not over-built:

| Dimension             | Target                                             |
| --------------------- | -------------------------------------------------- |
| Team size             | 1 developer + AI agents as contributors            |
| Concurrent users      | 1 (a local CLI / a local MCP client)               |
| Providers             | 2 today, plan for 5-6 within 3 years               |
| Presentation surfaces | 2 today (CLI, MCP), plan for 3-4 (A2A agent, HTTP) |
| Capability domains    | 4 (ingest, workflow, i18n, scout)                  |
| Repo size handled     | 10k-file monorepos via `ingest`                    |

**The scale that matters here is not user load — it is _surface_ count ×
_domain_ count.** Two surfaces × four domains is already eight orchestration
sites if you write them per-surface. That product is what this architecture
exists to keep linear instead of multiplicative.

### 1.3 Confirmed decisions (from intake)

| #  | Decision                                                                       | Consequence                                                                                        |
| -- | ------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| Q1 | `requires-python = ">=3.14"`                                                   | PEP 649 makes `from __future__ import annotations` a no-op → rule inverts from mandatory to banned |
| Q2 | Keep the four-layer diagram; orchestration lives in `core/*` beside primitives | No `core/usecases/` package. DTOs live in their domain module.                                     |
| Q3 | No backward compatibility, ever                                                | Delete every shim, deprecation path, and dual-format reader now in the tree                        |
| Q4 | `assets/meta-prompt/` does not exist                                           | Plan 2's "migration" has no source; it becomes a format _cutover_ plus fresh authoring             |
| Q5 | Restore the preview-model warning as a CLI-startup check                       | Not a Pydantic validator — see §5.9                                                                |
| Q6 | Single sequenced plan                                                          | This document                                                                                      |
| —  | `workflow commit` must display **tokens and chars**                            | §5.10, delivered in Phase 4                                                                        |

### 1.4 Plan 1 status — already complete, do not re-run

Verified against the snapshot. Four of five items shipped:

| Plan 1 item                                     | State                                                                              |
| ----------------------------------------------- | ---------------------------------------------------------------------------------- |
| §2.1 Python-2 `except` syntax in `core/i18n.py` | ✅ now `except (json.JSONDecodeError, OSError)`                                    |
| §2.2 `requires-python >=3.14` → `>=3.11`        | ✅ (and now reverts to `>=3.14` deliberately, per Q1 — different reason, see §5.1) |
| §2.3 Preview model default                      | ✅ repinned to `gemini-3.1-flash-lite`                                             |
| Phase 3 import-health gate                      | ✅ `dev/import_check.py` exists                                                    |
| Phase 4 preview warning                         | ⚠️ **written then commented out** (`config.py:137-149`) — Phase 7 restores it      |

The `ci-report.md` dependency-group fix also closes what my analysis filed as
§1.4. **Do not re-open any of the above.**

### 1.5 Architectural rules (mandated, non-negotiable)

1. The four-layer dependency direction, unchanged: `cli/* mcp/*` → `core/*` →
   `providers/base.py providers/registry.py` → `providers/<name>.py`
2. `cli/` and `mcp/` are **peer consumers**. Neither imports the other. Neither
   is privileged.
3. Simplicity first: no speculative abstraction before a second use case exists.
4. Functional over imperative; small composable helpers over large functions.
5. Rust-first CLI tooling; `uv` / `ruff` / `ty` for Python; `just` as the only
   task runner.
6. Comments explain _why_, never _what_.

### 1.6 Out of scope

- The `just` harness (exists; treated as the exit-criteria mechanism throughout)
- A2A agent protocol layer
- Streaming LLM responses, multi-modal input
- Response caching / cost tracking beyond token estimation
- Authoring new language directives (format lands, content deferred — Q4)
- Splitting into multiple distributions (evaluated and deferred — §5.8)

### 1.7 Assumptions

- **[ASSUMPTION]** No external users; every breaking change is free (stated in
  Plan 1, reconfirmed Q3).
- **[ASSUMPTION]** The working tree at implementation time is _newer_ than my
  snapshot — ruff is configured, dep-groups fixed, `scripts/*.just` exists, an
  `i18n/` fixture directory exists. Line numbers below are indicative; re-derive
  at execution.
- **[ASSUMPTION]** `assets/meta-prompt/` will not be resurrected. If it
  reappears, Phase 6's content step grows; the format decision does not change.
- **[ASSUMPTION]** `providers/base.py` defines `Provider` as a
  `@runtime_checkable` Protocol, plus frozen Pydantic `ToolSpec` / `ToolCall` /
  `LLMResponse`, and `AllProvidersFailedError` subclasses `ProviderError`.
  **This file was unreadable in the snapshot** — verify before Phase 3.

---

## 2 · Architecture Overview

### 2.1 The layer model

```
┌──────────────────────────────────────────────────────────────────┐
│  PRESENTATION  ·  peer packages, no shared code, no logic        │
│                                                                  │
│    cli/                          mcp/                            │
│    Typer + rich renderers        FastMCP stdio servers           │
│    renders DTO → terminal        renders DTO → agent text        │
└───────────────┬──────────────────────────┬───────────────────────┘
                │                          │
                │   consumes use cases, never primitives
                ↓                          ↓
┌──────────────────────────────────────────────────────────────────┐
│  CORE  ·  the only place behaviour is defined                    │
│                                                                  │
│   ┌────────────────── use cases (orchestration) ──────────────┐  │
│   │  workflow · i18n · scout · ingest                         │  │
│   │  return typed result DTOs, raise AzathothError            │  │
│   └────────────────────────┬──────────────────────────────────┘  │
│                            ↓                                     │
│   ┌────────────────── primitives (single-purpose) ───────────┐   │
│   │  git · serde · utils · directives · prompts · tools      │   │
│   └────────────────────────┬─────────────────────────────────┘   │
│                            ↓                                     │
│   ┌────────────────── llm façade ────────────────────────────┐   │
│   │  generate · generate_model · generate_with_tools         │   │
│   │  fallback chain · timeout budget · tool emulation        │   │
│   └────────────────────────┬─────────────────────────────────┘   │
└────────────────────────────┼─────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────┐
│  PORT  ·  providers/base.py  ·  providers/registry.py            │
│  Provider Protocol · ToolSpec/ToolCall/LLMResponse · exceptions  │
└────────────────────────────┬─────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────┐
│  ADAPTERS  ·  providers/gemini.py · providers/ollama.py · …      │
│  the ONLY files that may import a vendor SDK                     │
└──────────────────────────────────────────────────────────────────┘

        dev/  ·  fitness functions  ·  reads all layers, imported by none
```

Note the **use-case / primitive split inside `core/`**. Per Q2 this is a
_convention_, not a package boundary — `core/workflow.py` holds `stage_all`
(primitive) and `propose_commit` (use case) in the same file, separated by a
section comment. The rule is directional: use cases may call primitives;
primitives may never call use cases.

### 2.2 Core domain vs. supporting domains

- **Core domain — the LLM façade and provider port.** This is the differentiated
  asset. Everything else is replaceable; this is what makes Azathoth _Azathoth_.
- **Capability domains — workflow, i18n, scout, ingest.** Applications of the
  core domain. Each is independently deletable without touching the others.
- **Supporting — directives, prompts, git, serde, utils.** Shared
  infrastructure. Zero domain knowledge.
- **Meta — `dev/`.** Enforces the shape of everything above it.

**Scout is strategically distinct.** Ingest, workflow, and i18n are commodity
capabilities that any AI tool could offer. Scout — codebase analysis grounded in
_your_ opinionated directives — is the only capability that encodes taste. Plan
2 was right about this. It gets first-class treatment in Phase 5.

### 2.3 What deliberately does NOT exist

Named so nobody adds them later thinking they were an oversight:

| Not built                               | Why not                                                                                                                        |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| DI container                            | Two providers and a registry. Constructor injection via factory callables is sufficient at this scale and readable at year 10. |
| Plugin discovery via entry points       | The registry works. Entry points buy third-party providers you don't have and can't test. Revisit at provider #5.              |
| Result / Either type                    | Python's exception model is the idiom. A `Result` type fights the language and every library you depend on.                    |
| Event bus                               | No async fan-out requirement. A bus turns a 3-frame traceback into a 40-frame one.                                             |
| `core/models.py` shared DTO module      | Creates a module every other module imports — an artificial cycle magnet. DTOs live beside their use case.                     |
| Repository pattern over i18n JSON files | One storage backend (the filesystem), forever. `read_json`/`write_json` is the honest abstraction.                             |

---

## 3 · Design Patterns & Code Standards

### 3.1 Ports & Adapters (Hexagonal) — the provider layer

**Pattern.** `providers/base.py` defines the port: a `@runtime_checkable`
Protocol with `name`, `supports_native_tools`, and an async `generate`. Each
`providers/<name>.py` is an adapter that satisfies it structurally — no
inheritance. Vendor SDK imports are confined to the adapter file, enforced
statically by rule R1.

**Why.** LLM provider APIs are the fastest-churning dependency in the stack.
Google renamed its Python SDK twice in three years. Structural typing over
inheritance means an adapter can be written against a vendor SDK you've never
seen without importing anything from Azathoth beyond `providers.base`.

**How it's applied.** Adapters translate in both directions: canonical
`ToolSpec` → vendor tool format on the way in, vendor response → canonical
`LLMResponse` on the way out, and vendor exception → typed `ProviderError`
subclass via a classification helper. Adapters are stateless apart from
credentials and model name; every instance is disposable.

**Standards.** Adapters must annotate their `generate` method with
`typing.override` (3.12+) so Protocol drift becomes a type error rather than a
runtime `AttributeError`. Adapters must never read config directly — the
module-level factory does that, so the adapter class stays a pure function of
its constructor arguments and is trivially testable.

**10-year view.** _Year 3:_ provider #4 and #5 land as pure additions — one new
file, one registry line, one config block. _Year 5:_ a vendor ships a breaking
major version; the blast radius is one file and its test. _Year 10:_ "LLM
provider" may not be the right abstraction any more — but the port's shape (send
framed text, optionally offer tools, get structured text back) is a description
of _conversation_, not of any product, and is likely to survive the category.

### 3.2 Registry + Lazy Factory — provider resolution

**Pattern.** A name → zero-argument-factory mapping. `get_provider(name)`
invokes the factory on demand.

**Why not Abstract Factory.** Abstract Factory implies a family of related
objects created together. There is one product type here. A dict of callables is
the whole pattern, and it stays readable when a future maintainer opens the file
cold.

**Critical correction (Phase 2).** Registration currently instantiates the
factory eagerly to run an `isinstance` conformance check. Because the Gemini
factory raises on a missing API key, _importing the module crashes when no key
is configured_ — which defeats the fallback chain precisely in the scenario it
exists for, and takes both fitness functions down with it. **Conformance must be
checked against the class, not a live instance**, or deferred to first
resolution. Registration must never touch credentials, the network, or the
filesystem.

**Standards.** The registry decides _nothing_ about ordering, defaults, or
fallback policy — that is the façade's job, and the separation is what lets the
resolver be tested with fake providers and no registry at all.

### 3.3 Façade + Chain of Responsibility — `core/llm.py`

**Pattern.** A narrow public surface (`generate`, `generate_model`,
`generate_with_tools`) over an internal resolver that walks the configured
provider chain, falling through on retryable failures and halting on
non-retryable ones, under a two-level timeout budget (per-provider and
whole-chain).

**Why.** Consumer code must never know which backend answered. This is the
single most important boundary in the codebase and the one rule R2 exists to
protect.

**Structural change — aggregate failure becomes an `ExceptionGroup`.**
`AllProvidersFailedError` currently carries a list of causes. That is a
hand-rolled ExceptionGroup. Making it a real one (it can subclass
`ExceptionGroup` while remaining an `AzathothError`) means every failed provider
keeps its own full traceback, callers can filter selectively with `except*`, and
the interpreter renders the whole tree natively. This is the clearest example in
the codebase of a modern feature that _deletes_ code rather than adding surface.

**New method — `generate_model`.** Currently four call sites hand-write the same
LLM→JSON→dict round trip with a `json.loads` + `KeyError` guard and no
validation whatsoever: a model returning `{"title": 42}` sails straight through.
`generate_model` takes a Pydantic model class as a type parameter (PEP 695
generic, `[T: BaseModel]`), calls `generate` in JSON mode, validates, and raises
`ProviderSchemaError` on mismatch — an exception that already flows through the
provider hierarchy. Four hand-written parse blocks collapse to four one-liners
and gain real validation.

**Standard.** The façade must not import `rich` or print. It currently
constructs a `Console` and writes provider-attempt banners to stderr from inside
the resolver (`core/llm.py:168-173`). That is presentation inside the core
domain; it becomes an `INFO` log record, and the CLI renders it.

**10-year view.** _Year 3:_ a fifth surface (HTTP, A2A) consumes the same façade
with no changes. _Year 5:_ streaming or batching arrives as an additive method;
existing callers are untouched. _Year 10:_ the façade is the seam that let you
swap out an entire generation of model APIs without a rewrite.

### 3.4 Application Service (Interactor) + Result DTO — the use-case layer

**This is the structural heart of the plan.**

**Pattern.** For each capability domain, a small number of orchestrating async
functions that sequence primitives, call the façade, and return an immutable
typed DTO. They perform no I/O to the terminal, raise only `AzathothError`
subclasses, and know nothing about who called them.

**Why.** Today `cli/` and `mcp/` each implement the workflow themselves:

| Use case       | CLI site                           | MCP site                  | What is duplicated                                       |
| -------------- | ---------------------------------- | ------------------------- | -------------------------------------------------------- |
| commit         | `cli/commands/workflow.py:57-110`  | `mcp/workflow.py:78-101`  | stage → diff → prompt → generate → parse → commit        |
| release        | `cli/commands/workflow.py:187-248` | `mcp/workflow.py:114-144` | tag → log → prompt → generate → parse → tag/push/publish |
| status         | `cli/commands/workflow.py:120-163` | `mcp/workflow.py:37-68`   | **the porcelain parser is byte-identical**               |
| i18n translate | `cli/commands/i18n.py:60-158`      | `mcp/i18n.py:52-105`      | load → diff → samples → translate → merge → write        |
| i18n audit     | `cli/commands/i18n.py:172-207`     | `mcp/i18n.py:18-49`       | matrix construction + totals arithmetic                  |

Five behaviours, ten implementations. A bug in the porcelain parser must be
fixed twice, and the two copies have already drifted in their error handling.
Adding `mcp/scout.py` makes it eleven.

**How it's applied.** Each use case returns a frozen Pydantic model carrying
everything any renderer could need — including presentational metadata like
counts and sizes, computed once in core. Renderers select from the DTO; they
never recompute. The DTO is the contract between core and every present and
future surface.

**Contracts to be defined (described, not implemented):**

| Module             | Use case             | Inputs                                                | Returns                                                                                     | Raises                      |
| ------------------ | -------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------------- | --------------------------- |
| `core/workflow.py` | `repo_status`        | optional cwd                                          | `RepoStatus` — branch, staged/unstaged/untracked counts, latest tag, commits since tag      | `GitError`                  |
|                    | `propose_commit`     | focus hint, provider override, cwd                    | `CommitProposal` — validated `CommitMessage`, `diff_chars`, `diff_tokens`                   | `ProviderError`, `GitError` |
|                    | `perform_commit`     | a `CommitProposal`, cwd                               | `GitResult`                                                                                 | `GitError`                  |
|                    | `propose_release`    | provider override, cwd                                | `ReleaseProposal` — validated `ReleaseNotes`, previous tag, commit count                    | `ProviderError`, `GitError` |
|                    | `perform_release`    | a `ReleaseProposal`, prerelease flag                  | `GitResult`                                                                                 | `GitError`                  |
| `core/i18n.py`     | `load_project`       | settings path                                         | `I18nProject` — config, resolved paths, loaded translation sets                             | `ConfigParseError`          |
|                    | `audit_project`      | an `I18nProject`                                      | `TranslationMatrix` + per-locale coverage totals                                            | —                           |
|                    | `translate_project`  | an `I18nProject`, full/prune flags, provider override | list of `LocaleOutcome` — locale, keys touched, values, placeholder warnings, error-or-none | `TranslationError`          |
|                    | `apply_translations` | an `I18nProject`, outcomes, prune flag                | list of written paths                                                                       | `OSError`                   |
| `core/scout.py`    | `detect_stack`       | root path                                             | `StackInfo` — primary language, manifests found, confidence                                 | —                           |
|                    | `find_entry_point`   | root path, language                                   | optional relative path                                                                      | —                           |
|                    | `scout`              | root path                                             | `ScoutReport` — ingest result, stack, directives loaded, master context, entry point        | —                           |

**The propose / perform split is deliberate.** Every AI-assisted mutation has a
preview step and a commit step. Separating them means the CLI can render a
preview and prompt for confirmation, the MCP tool can return the proposal for an
agent to reason about, and a future HTTP surface can put a human in the loop —
all against one implementation. Fusing them, as both current surfaces do, is
what forces each surface to re-implement the sequence.

**10-year view.** _Year 3:_ the A2A agent surface is a renderer, not a rewrite.
_Year 5:_ Typer is replaced or FastMCP majors; logic is untouched because it
never imported either. _Year 10:_ the use-case contracts are the durable
description of what this software _does_, independent of every interface it has
ever been worn behind. This is the single highest-leverage structural change in
the plan.

### 3.5 Presenter — `cli/` and `mcp/`

**Pattern.** Both packages contain _only_ argument parsing, use-case invocation,
rendering, and exit-code mapping. Per Q5, they are peers: neither imports the
other, no shared "presentation utils" module is created between them (that would
be a fifth layer nobody asked for).

**Standard — presentation purity, enforced by new rule R5.** `cli/**` and
`mcp/**` may not import `azathoth.core.llm`, `azathoth.providers.*`, or any
underscore-prefixed name from `core`. Today all three are violated: both
surfaces import `generate` and `LLMError` from the façade, and both import
`_run_git` — a private name crossing two package boundaries, which is the layer
audibly asking to be made public.

**Error handling.** Each surface installs exactly one error boundary. The CLI
catches `AzathothError` once at the Typer dispatch level and maps to an exit
code; the identical five-line `except I18nError → print red → Exit(1)` block
currently repeated in all four i18n commands is deleted. MCP tools catch
`AzathothError` and return the message as tool text, because an MCP tool raising
is worse than an MCP tool reporting.

### 3.6 Anti-Corruption Layer — `core/git.py` (new)

**Pattern.** One module owning all git subprocess interaction, exposing async
`run_git` and `find_git_root`, returning typed results and raising `GitError`.

**Why.** There are currently _two_ git layers in `core/`: an async `_run_git` in
`workflow.py`, and four copies of a synchronous
`subprocess.run(["git", "rev-parse", "--show-toplevel"])` block in `ingest.py`
(lines 106, 153, 275, 301), each with its own swallow-everything `except`.
Worse, the synchronous calls sit inside `async def` functions, blocking the
event loop — so `_ingest_user`'s `Semaphore(5)` concurrency is partly cosmetic,
since every worker serialises on git.

**Standard.** Nothing outside `core/git.py` may spawn a git process. The `gh`
invocation in `create_release` moves here too — it is the same category of
foreign-CLI interaction and deserves the same error typing.

**10-year view.** _Year 5:_ if git interaction ever needs to move to a library
(pygit2, gitoxide bindings) for performance on large monorepos, exactly one file
changes.

### 3.7 Composite — `core/directives.py`

**Pattern.** A master context is composed from a universal core directive plus
zero or more language directives, each rendered to Markdown and concatenated.
The composition is the product; individual directives are the leaves.

**Format cutover (Phase 6, per Q3+Q4).** A directive becomes a folder:
structured `meta.toml` (name, version, applies-to, rules dict) plus prose
`philosophy.md` and optional `examples.md`. Rules are key-value data and belong
in TOML; philosophy is prose with code fences and belongs in Markdown. Forcing
either format on both creates friction in whichever direction you pick.

**Per Q3 there is no shim, no dual-format reader, and no `directives migrate`
command.** The single existing `directives/core.toml` is converted by hand in
the same commit that changes the loader. Per Q4 no language directives are
authored yet — but `core/philosophy.md` is seeded from the genuinely existing
coding philosophy in `INSTRUCTIONS`/`CONTRIBUTING`, so scout returns something
real from day one rather than an empty string.

**Standard.** The loader must raise explicitly when a directive folder is
malformed. Returning an empty `Directive` on a missing file would let a
half-migrated tree pass silently — the exact failure mode Plan 2 flagged as
high-risk.

### 3.8 Fitness Functions — `dev/`

**Pattern.** Architecture as executable tests. AST-walk the source tree, assert
the dependency rules, exit non-zero.

**Why this is the load-bearing choice for a 10-year horizon.** Every rule in
§1.5 is a rule an AI agent or a future you will violate by accident at 2am. A
rule enforced by a document is a suggestion; a rule enforced by `just ci` is
architecture. This project already has this instinct — the plan extends it from
three rules to eight, and adds a performance budget.

| Rule                               | Status | Enforces                                                                                      |
| ---------------------------------- | ------ | --------------------------------------------------------------------------------------------- |
| R1 SDK isolation                   | exists | Only `providers/gemini.py` imports `google.*`                                                 |
| R2 façade boundary                 | exists | No SDK import in `core/llm.py`; no module-level concrete-provider import outside `providers/` |
| R3 provider conformance            | exists | Every non-framework `providers/*.py` self-registers and satisfies the Protocol                |
| R4 no bare config import           | exists | **Extend** to also reject module-level `get_config()` calls (§5.7)                            |
| **R5 presentation purity**         | new    | `cli/**` and `mcp/**` may not import `core.llm`, `providers.*`, or `core` private names       |
| **R6 no cross-package privates**   | new    | An underscore-prefixed name may not be imported across a package boundary                     |
| **R7 layer direction**             | new    | `core/**` may not import `cli/**` or `mcp/**`; `providers/**` may not import `core/**`        |
| **R8 no `__future__` annotations** | new    | The 3.14 inversion (§5.1) — the import is now dead weight                                     |
| **B1 cold-import budget**          | new    | `import azathoth` under a fixed millisecond ceiling                                           |

**B1 deserves justification.** A CLI that takes 800ms to print `--help` is a CLI
people stop using. `azathoth/__init__.py` currently runs `load_dotenv` and pulls
in Typer and rich at import time. Import cost only ever grows, and it grows
invisibly. A budget check turns a slow creep into a failed build. _Year 10:_
this is the difference between a tool that still feels instant and one that
everyone quietly replaced with a shell alias.

### 3.9 Code standards (revised for 3.14)

| Standard                                              | Change from today                                                                                                    |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| `from __future__ import annotations`                  | **BANNED** (was: mandatory). PEP 649 makes it a no-op. Delete from all 8 files that have it; R8 enforces.            |
| Modern builtin generics (`dict`, `list`, `X \| None`) | Mandatory. Ruff `UP` autofixes the 14 legacy-typing files.                                                           |
| PEP 695 type parameters (`def f[T: Bound]`)           | Preferred over `TypeVar` for new generic code                                                                        |
| `typing.override`                                     | Mandatory on all provider `generate` methods                                                                         |
| Frozen models                                         | All Pydantic DTOs `frozen=True`. Currently **0 of 12** comply.                                                       |
| Exhaustive dispatch                                   | `match` + `assert_never` where a closed set is dispatched (§5.4)                                                     |
| Structured concurrency                                | `asyncio.TaskGroup` over bare `gather` (§5.5)                                                                        |
| `print()` in `src/`                                   | Banned except `dev/` CLI entry points — carve the exception into the rule rather than tolerating 8 silent violations |
| Blind `except Exception`                              | Banned without re-raise or structured log. Ruff `BLE001` already flags these; four sites remain.                     |
| Naming                                                | `SCREAMING_CASE` constants, `snake_case` functions, `kebab-case` CLI flags                                           |

---

## 4 · Component Map & Directory Structure

### 4.1 Target tree

```
azathoth/
├── justfile                       existing harness — untouched by this plan
├── scripts/*.just                 existing harness — untouched by this plan
├── pyproject.toml                 requires-python >=3.14 · 5 console scripts · ruff/ty/pytest config
├── flake.nix                      drop pkgs.cargo (no Rust); pin python314
│
├── src/azathoth/
│   ├── __init__.py                dotenv bootstrap ONLY — no re-export indirection
│   ├── config.py                  Settings · no deprecated aliases · no side-effecting properties
│   │
│   ├── core/
│   │   ├── llm.py                 façade · fallback chain · generate_model · ExceptionGroup
│   │   ├── tools.py               tool spec derivation · JSON-mode emulator · dispatch
│   │   ├── git.py            NEW  the ONLY git/gh subprocess owner
│   │   ├── serde.py          NEW  read_json / write_json — 5 read + 3 write sites collapse here
│   │   ├── utils.py               token estimation · size formatting (bug fix, §5.10)
│   │   ├── exceptions.py          AzathothError root · GitError added
│   │   ├── directives.py          Composite loader · folder-per-directive
│   │   ├── prompts.py             JSON-mode system prompts ONLY — legacy agent trio deleted
│   │   ├── ingest.py              primitives + use cases · git calls delegated to core/git
│   │   ├── workflow.py            primitives + repo_status/propose_*/perform_*  + DTOs
│   │   ├── i18n.py                primitives + load_project/audit/translate/apply + DTOs
│   │   └── scout.py               detect_stack · find_entry_point · scout + DTOs
│   │
│   ├── providers/
│   │   ├── base.py                PORT · Protocol · transport models · exception hierarchy
│   │   ├── registry.py            name → lazy factory · class-level conformance check
│   │   ├── gemini.py              ADAPTER · the only google.* importer
│   │   └── ollama.py              ADAPTER · httpx against /api/chat
│   │
│   ├── cli/
│   │   ├── main.py                Typer root · single AzathothError boundary · startup checks
│   │   └── commands/
│   │       ├── ingest.py          renderer
│   │       ├── workflow.py        renderer  (tokens + chars, §5.10)
│   │       ├── i18n.py            renderer
│   │       └── scout.py      NEW  renderer
│   │
│   ├── mcp/
│   │   ├── workflow.py            renderer + run()
│   │   ├── i18n.py                renderer + run()          ← run() is currently MISSING
│   │   └── scout.py          NEW  renderer + run()          ← Plan 2's deliverable
│   │
│   ├── directives/
│   │   └── core/
│   │       ├── meta.toml          rules dict
│   │       └── philosophy.md      prose  (seeded from CONTRIBUTING/INSTRUCTIONS)
│   │
│   └── dev/
│       ├── import_check.py        import-health fitness function
│       ├── architecture_check.py  R1-R8 + B1
│       └── _cli.py           NEW  shared --json/human/exit harness for the two above
│
└── tests/
    ├── conftest.py                hermetic fixtures — tmp_path only, no repo-relative paths
    ├── core/ · providers/ · cli/ · mcp/
    └── arch/                 NEW  tests that the fitness functions catch deliberate violations
```

**Deleted outright** (Q3 — no compatibility burden): `core/prompts.py`'s
`get_scout_prompt` / `get_commit_prompt` / `get_release_prompt` (~100 lines,
zero callers); `config.py`'s `llm_total_timeout` alias and its validator;
`config.py`'s dead `_PREVIEW_TAGS` constant; `core/i18n.py`'s dual-key
`import_registry` reader; `cli/commands/workflow.py`'s `_sync_generate`;
`azathoth/__init__.py`'s `main()` and `cli/__init__.py`'s `init_cli()`
indirection hops; the empty `agent/`, `agent/tasks/`, and `transforms/`
packages.

### 4.2 Component contracts

| Component            | Responsibility         | Exposes                                         | Consumes                                                     | Must NOT                                                                         |
| -------------------- | ---------------------- | ----------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| `providers/base`     | Define the port        | Protocol, transport models, exception hierarchy | stdlib, pydantic                                             | Import anything from `azathoth`                                                  |
| `providers/registry` | Name → lazy factory    | register, get_provider, list_providers          | `providers.base`                                             | Decide ordering, defaults, or fallback policy; touch credentials at registration |
| `providers/<name>`   | Adapt one vendor       | A Protocol-satisfying class + a factory         | `providers.base`, one vendor SDK, `config` (in factory only) | Import `core.*` or another adapter                                               |
| `core/llm`           | Façade + chain         | generate, generate_model, generate_with_tools   | `providers.base`, `providers.registry`, `core.tools`         | Import a vendor SDK; import rich; print                                          |
| `core/git`           | Git/gh anti-corruption | run_git, find_git_root, GitResult               | stdlib asyncio                                               | Be bypassed by any other module spawning git                                     |
| `core/serde`         | JSON file I/O          | read_json, write_json                           | stdlib                                                       | Know any domain model                                                            |
| `core/<domain>`      | Primitives + use cases | Use-case functions returning DTOs               | `core.llm`, `core.git`, `core.serde`, `core.directives`      | Import `cli.*`, `mcp.*`, or `providers.<name>`; render output                    |
| `cli/**`             | Terminal presentation  | Typer commands                                  | `core` use cases only                                        | Import `core.llm`, `providers.*`, `core` privates, or `mcp.*`                    |
| `mcp/**`             | Agent presentation     | FastMCP tools + run()                           | `core` use cases only                                        | Import `core.llm`, `providers.*`, `core` privates, or `cli.*`                    |
| `dev/**`             | Enforce the above      | Fitness function CLIs                           | Everything (read-only)                                       | Be imported by any non-dev module                                                |

### 4.3 Entry points (`[project.scripts]`)

Five console scripts. Today there is **one**, while `CONTRIBUTING.md` documents
two more and `mcp/workflow.py` documents a fourth — all of which fail.

| Script                  | Target             | Note                                                                                         |
| ----------------------- | ------------------ | -------------------------------------------------------------------------------------------- |
| `azathoth`              | CLI root           | plus an `az` alias — `cli/commands/workflow.py:5-7` already documents `az workflow commit`   |
| `azathoth-mcp-workflow` | `mcp.workflow:run` |                                                                                              |
| `azathoth-mcp-i18n`     | `mcp.i18n:run`     | **`run()` must be written — it does not exist**                                              |
| `azathoth-mcp-scout`    | `mcp.scout:run`    | Phase 5                                                                                      |
| —                       | fitness functions  | Folded into `azathoth dev imports` / `azathoth dev arch` rather than two more scripts (§5.6) |

---

## 5 · Trade-off Analysis

### 5.1 Python version floor

```
DECISION: What Python version does Azathoth require?
OPTIONS CONSIDERED:
  A. >=3.11 (Plan 1's choice)
     pros: widest distro reach; ExceptionGroup/TaskGroup/StrEnum all available
     cons: no PEP 695 generics, no @override, `from __future__ import
           annotations` stays mandatory in every file forever
  B. >=3.12
     pros: PEP 695 + @override; Ubuntu 24.04 LTS ships it; safe wheel coverage
     cons: still carrying the __future__ import boilerplate
  C. >=3.14
     pros: PEP 649 makes annotations lazy BY DEFAULT — the __future__ import
           becomes a no-op and the rule inverts from "mandatory in every file"
           to "banned", deleting boilerplate instead of enforcing it;
           everything from A and B included; best error messages and
           asyncio introspection for debugging the provider chain
     cons: newest binary-extension wheels required (tiktoken, pydantic-core);
           distro Python is behind; contributors need a managed toolchain
CHOSEN: C  (user decision, and the reasoning holds)
REASON: The project is a single-developer prototype using `uv`, which
        provisions interpreters directly — distro Python was never the
        install path, so A's main advantage doesn't apply here. PEP 649
        resolves a live compliance problem (14 of 22 modules violate the
        __future__ rule) by removing the rule rather than mechanically
        fixing 14 files. Doing this on a prototype costs nothing; doing it
        at year 3 with users costs a major version.
REVISIT IF: A required dependency lacks 3.14 wheels (see §9 — this is the
        one item that can block Phase 1), or a contributor is genuinely
        pinned to a distro interpreter.
```

> **Footnote worth knowing.** PEP 758 legalises `except A, B:` without
> parentheses in 3.14 — the exact syntax that was Plan 1's stop-ship bug would
> now parse _and behave correctly_. That is a good argument for keeping
> `import_check` rather than relying on syntax errors to catch broken modules.

### 5.2 Where orchestration lives

```
DECISION: Where does use-case orchestration live?
OPTIONS CONSIDERED:
  A. Stay as-is — each surface orchestrates
     pros: zero migration cost
     cons: 5 behaviours × N surfaces; already drifting; scout would make 11
  B. New core/usecases/ package (5-layer diagram)
     pros: maximal separation; trivially enforceable import rule
     cons: adds a layer to a diagram the user explicitly likes; splits each
           domain across two files for a 4-domain project
  C. In core/<domain>.py beside primitives, separated by convention
     pros: preserves the 4-layer diagram exactly; each domain stays one
           cohesive file; import rule still enforceable at package level
     cons: relies on discipline within a file rather than a directory wall
CHOSEN: C  (user decision)
REASON: At four domains, a per-domain file is 200-350 lines — comfortably
        readable, and cohesion within a domain is worth more than a wall
        between two kinds of function. The enforcement that actually matters
        is R5 (presentation may not reach past use cases), and that is
        checkable at the package level regardless of internal layout.
REVISIT IF: Any core/<domain>.py passes ~600 lines, or a domain grows more
        than ~6 use cases. At that point split that domain into a package
        (core/workflow/{primitives,usecases}.py) rather than introducing a
        global usecases/ layer — keep the change local to the domain that
        outgrew the file.
```

### 5.3 Aggregate provider failure

```
DECISION: How is "every provider in the chain failed" represented?
OPTIONS CONSIDERED:
  A. Current: AllProvidersFailedError holding a list of causes
     pros: works; simple
     cons: causes are data, not exceptions — tracebacks are lost; callers
           cannot selectively handle "all failed because of auth" vs
           "all failed because of timeout"
  B. Raise only the last failure, chain the rest via __cause__
     pros: idiomatic pre-3.11
     cons: silently discards the interesting failures; the first provider's
           auth error is usually the real story
  C. ExceptionGroup subclass carrying every cause as a live exception
     pros: full traceback per cause; native interpreter rendering; `except*`
           lets callers filter by type across the whole group; it is what
           the current API was approximating by hand
     cons: callers must learn except* semantics
CHOSEN: C
REASON: This is the clearest case in the codebase of a modern language
        feature that removes hand-rolled machinery rather than adding
        surface. Debugging a 3-provider fallback failure without per-cause
        tracebacks is guesswork.
REVISIT IF: Never, realistically — ExceptionGroup is now the language's
        answer to this shape of problem.
```

### 5.4 Token counting for the commit view

```
DECISION: How are token counts computed for the staged diff?
OPTIONS CONSIDERED:
  A. tiktoken cl100k_base (what estimate_tokens does today)
     pros: local, instant, zero network, already implemented
     cons: cl100k_base is OpenAI's tokenizer — for Gemini and Ollama it is
           a proxy, typically within ~10-20% but not exact
  B. Provider-native counting (Gemini count_tokens, Ollama prompt_eval_count)
     pros: exact for the provider that will actually answer
     cons: a network round-trip before every commit preview; fails offline;
           couples a display concern to the provider chain — a layering
           violation for what is decoration
  C. tiktoken now, labelled honestly as an estimate; provider-native later
     behind an explicit --exact-tokens flag
     pros: instant default, no new failure mode, exactness available on demand
     cons: two code paths if the flag is ever built
CHOSEN: C, shipping only the A half now
REASON: The number's job is to tell you "is this diff too big to send" —
        ±15% does not change that answer. Paying a network round-trip on
        every preview to refine a number nobody acts on at that precision
        is a bad trade. The DTO field is named to reflect estimation, so
        the display never overclaims.
REVISIT IF: Cost tracking becomes a real feature, at which point exact
        accounting matters and the provider-native path earns its cost.
```

### 5.5 Concurrency model

```
DECISION: How is concurrent work structured (multi-repo ingest, per-locale
          translation)?
OPTIONS CONSIDERED:
  A. Current: asyncio.gather + Semaphore, per-task try/except that swallows
     pros: works
     cons: a failure loses its reason entirely (ingest shows a red ✗ with no
           message); no structured cancellation; sync subprocess calls inside
           async functions block the loop and partly negate the concurrency
  B. asyncio.TaskGroup
     pros: structured concurrency — a failure cancels siblings deterministically,
           and unhandled failures surface as an ExceptionGroup, which composes
           exactly with §5.3
     cons: all-or-nothing by default; needs explicit per-item result capture
           where partial success is desired
  C. TaskGroup for fan-out where partial success is meaningful, with each
     task returning a result-or-error DTO rather than raising
     pros: partial success is explicit and typed, cancellation is still
           structured, and the renderer can show per-item status with reasons
     cons: slightly more ceremony per fan-out site
CHOSEN: C
REASON: Both fan-out sites want partial success — one bad repo shouldn't
        abort a 40-repo profile ingest, one failed locale shouldn't abort
        the others. But "partial success" must be modelled, not achieved by
        swallowing exceptions. The LocaleOutcome DTO already carries an
        error slot; ingest gets the same treatment.
REVISIT IF: A fan-out appears where any failure should abort everything —
        use a bare TaskGroup there and let it propagate.
```

### 5.6 Fitness function delivery

```
DECISION: How are import-check and architecture-check invoked?
OPTIONS CONSIDERED:
  A. Two dedicated console scripts (what CONTRIBUTING documents)
     pros: independent, no CLI import cost
     cons: two more entry points; each hand-rolls the same
           --json/human/exit harness; neither currently exists in pyproject
  B. Subcommands under the main CLI: azathoth dev imports / azathoth dev arch
     pros: one entry point; Typer already handles --json and exit codes;
           discoverable via --help; the duplicated harness disappears
     cons: the checks now import the CLI, so a broken CLI hides them —
           the one failure mode these tools exist to catch
  C. B, plus `python -m azathoth.dev.import_check` preserved as the
     escape hatch for when the CLI itself is broken
     pros: ergonomic default, guaranteed fallback, no extra scripts
     cons: two invocation paths to document
CHOSEN: C
REASON: Option B's objection is real and fatal on its own — but the module
        execution path already exists and costs nothing to keep. The just
        recipes call the module form for robustness; humans use the
        subcommand. The shared dev/_cli.py harness deletes the duplication
        either way.
REVISIT IF: CLI cold-import cost (budget B1) makes the subcommand path slow
        enough to discourage running checks locally.
```

### 5.7 Configuration and state

```
DECISION: How is configuration accessed?
OPTIONS CONSIDERED:
  A. Current: module-level singleton, captured at import by three modules
     (core/utils.py:4, core/directives.py:7, cli/commands/ingest.py:33)
     pros: convenient
     cons: binds before any test can patch it — the exact problem rule R4
           was written to prevent, arrived at by a different route;
           config.directives_dir also runs mkdir() as a property side effect
     on every access
  B. Explicit dependency injection — pass Settings into every function
     pros: maximal testability, zero global state
     cons: threads a parameter through every signature in the codebase for
           a single-process single-user CLI; heavy tax, thin benefit
  C. Lazy accessor called inside function bodies, never at module scope,
     with R4 extended to enforce it
     pros: patchable in tests, no signature churn, one enforceable rule
     cons: a function call rather than a module constant at each use
CHOSEN: C
REASON: B is the textbook answer and the wrong one at this scale — it taxes
        every signature to solve a problem that a lint rule solves. The
        real defect is timing (import-time binding), not the singleton
        itself. Fixing timing is a three-line change per site plus a rule.
        Separately: directives_dir stops calling mkdir — a property that
        mutates the filesystem on read is a trap, and directory creation
        moves to an explicit ensure step at CLI startup.
REVISIT IF: Azathoth ever runs multi-tenant or in-process concurrently for
        different configs — then contextvars, not parameter threading.
```

### 5.8 Packaging and deployment

```
DECISION: One distribution or several (azathoth-core / -cli / -mcp)?
OPTIONS CONSIDERED:
  A. Single distribution, all surfaces always installed
     pros: simplest; one version number; no cross-package version skew
     cons: MCP users install Typer/rich they never use, and vice versa
  B. Three distributions matching the layer diagram
     pros: matches the stated mental model ("cli + mcp are separate pkgs
           using the core"); minimal install per use case
     cons: three release processes, three changelogs, and a version-skew
           matrix — for a one-person prototype with no users, this is
           overhead with no beneficiary
  C. Single distribution with optional extras (cli / mcp / agent)
     pros: one release process; users can install a lean subset; the extras
           boundary documents the layer split and forces you to notice if a
           dependency crosses it
     cons: extras are a weaker boundary than separate packages
CHOSEN: C
REASON: The layering, not the packaging, is what makes the split real —
        and R5/R7 enforce the layering regardless of how it ships. Extras
        give most of B's benefit at none of its release cost, and because
        the code is already correctly layered, a future split to B is
        mechanical: move directories, add two pyproject files. Do it when
        someone actually wants to install one without the other.
REVISIT IF: A third party wants to build on azathoth-core without the CLI
        dependencies, or the dependency sets genuinely diverge.
```

### 5.9 Preview-model warning (Plan 1 Phase 4, restored)

```
DECISION: Where does the "you configured a preview model" warning fire?
OPTIONS CONSIDERED:
  A. Pydantic field_validator on gemini_model (as originally written, now
     commented out at config.py:137-149)
     pros: co-located with the field; impossible to bypass
     cons: config.py constructs Settings at module scope (line 198), so the
           warning fires on every `import azathoth` — including every test
           collection and every MCP server start. Near-certainly why it was
           disabled.
  B. Delete the feature
     pros: no code
     cons: loses a real protection — Plan 1 correctly identified silent
           overnight breakage from yanked preview tags as a live risk
  C. An explicit startup check invoked by the CLI root callback and by each
     MCP run(), emitting a UserWarning
     pros: fires once per invocation, at the moment a human or agent can
           act on it; suppressible via standard warnings machinery for CI;
           import stays silent
     cons: must be wired at each entry point (4 sites) rather than one
CHOSEN: C  (user decision Q5)
REASON: A validator on a module-scope singleton is a warning attached to
        an import, which is the wrong event. The right event is "someone
        is about to run something". Four wiring sites is a small price and
        each is one line calling a shared check.
REVISIT IF: Entry points multiply past ~6, at which point a shared
        bootstrap helper should own all startup checks together.
```

### 5.10 Directive storage format

```
DECISION: What is the on-disk format for directives?
OPTIONS CONSIDERED:
  A. TOML only (current: directives/core.toml)
     pros: structured, Pydantic-validated, already loading
     cons: prose-heavy philosophy content in TOML strings is miserable to
           write and produces unreadable diffs
  B. Markdown only with frontmatter
     pros: natural authoring; clean diffs
     cons: loses schema validation on the rules dict
  C. Folder per directive: meta.toml (structure) + philosophy.md (prose)
     + optional examples.md
     pros: each format used for what it is good at; rules stay validated;
           prose stays writable and diffable
     cons: multiple files per directive; loader must handle a folder
CHOSEN: C  (Plan 2's decision D, carried forward)
REASON: Directives genuinely have two natures and the current single-format
        choice pinches on whichever half it isn't suited to. Per Q3 there
        is no compatibility shim and no migration command — the one
        existing core.toml is converted by hand in the same commit.
REVISIT IF: Directive count exceeds ~20 and folder-per-directive becomes
        navigational overhead — consolidate to single-file with frontmatter.
```

---

## 6 · Phased Implementation Plan

Every phase ends green under the existing harness. `just ci` (= `check` +
`test`) is the gate; no phase is complete until it passes.

### Phase 0 — Toolchain floor `[HIGH RISK — may block everything]`

**Goal.** A trustworthy, current dependency tree on Python 3.14 before any code
moves.

**Work.** Bump `requires-python` to `>=3.14`; pin the Nix devshell to python314
and drop `pkgs.cargo` (there is no Rust in this repo, despite the flake
description and the README's crates.io badges). Run `uv lock --upgrade` to clear
the **69 CVEs** the audit reports across `cryptography`, `starlette`, `urllib3`,
and `mcp`. Verify every dependency with a binary extension has 3.14 wheels —
specifically `tiktoken`, `pydantic-core`, and whatever `gitingest` pulls.

**Exit criteria.** `uv sync` succeeds on 3.14; `just audit` reports zero
known-critical CVEs; `just ci` green with **no source changes**.

**Risk flags.** `[HIGH RISK]` If `tiktoken` or `pydantic-core` lack 3.14 wheels,
this phase stops the plan — building from source is not an acceptable install
story. Fallback is Q1 option B (`>=3.12`), which costs only the PEP 649 benefit
and leaves the `__future__` rule in place. **Determine this first, before any
other work.** `[HIGH RISK]` The `fastmcp` and `google-genai` majors move fast;
an upgrade may break adapter code. This is why it is Phase 0 and not folded into
a refactor commit — you want a green tree between "deps moved" and "code moved".

### Phase 1 — Unblock

**Goal.** Every documented command actually runs; nothing crashes on import.

**Work.** Fix eager provider instantiation in `registry.register` so a missing
API key can no longer crash module import (§3.2). Declare all five console
scripts and write the missing `mcp/i18n.run()`. Delete `_sync_generate` and
await the façade directly at both CLI call sites — the MCP server already does
this correctly, which is the proof the wrapper was never needed. Fix
`format_size`'s integer division, which makes every size in the ingest panel
render as a whole unit (1.5 MB shows as 1.0 MB).

**Exit criteria.** `azathoth --help`, `azathoth-mcp-workflow`,
`azathoth-mcp-i18n` all start. `python -m azathoth.dev.import_check` passes
**with no `GEMINI_API_KEY` set** — this is the specific regression test for the
registry fix. `just ci` green.

**Risk flags.** None. Pure correctness.

### Phase 2 — Substrate

**Goal.** The shared primitives the use-case layer will stand on.

**Work.** Create `core/git.py` (§3.6) and migrate all five git call sites plus
the `gh` invocation; the four synchronous `subprocess.run` blocks in `ingest.py`
become awaited calls, unblocking the event loop. Create `core/serde.py` and
collapse the five JSON reads and three writes in `core/i18n.py`. Add
`generate_model` to the façade (§3.3) and convert `AllProvidersFailedError` to
an `ExceptionGroup`. Move the façade's rich-console provider banner to an `INFO`
log record. Extract `dev/_cli.py`, the shared `--json`/human/exit harness.

**Exit criteria.** Nothing outside `core/git.py` spawns a subprocess named git
or gh (grep-verifiable, and R-rule enforced in Phase 7). `generate_model` has
unit tests covering valid parse, malformed JSON, and schema mismatch.
Fallback-chain tests assert `except*` selection by cause type. `just ci` green.

**Risk flags.** `[REVISIT]` Making `AllProvidersFailedError` an `ExceptionGroup`
changes what `except AllProvidersFailedError` catches in existing tests. Per Q3
this is a free break — but expect test churn in
`tests/providers/test_fallback.py`, which was unreadable in the snapshot and may
need rewriting rather than patching.

### Phase 3 — The use-case layer `[the structural core of this plan]`

**Goal.** Behaviour is defined exactly once, in `core/`.

**Work.** Implement every contract in §3.4's table, plus the frozen DTOs beside
them. Domain by domain: `workflow` (repo_status, propose/perform commit and
release), then `i18n` (load_project, audit_project, translate_project,
apply_translations), then `scout` (detect_stack, find_entry_point, scout).
Presentation is not touched yet — the old orchestration keeps working while the
new layer is built and tested underneath it.

**Exit criteria.** Every use case has unit tests against fake providers and
`tmp_path` fixtures, with no terminal output and no network. The git-porcelain
parser exists in exactly one place. `just cov` shows the use-case functions at
≥85%. `just ci` green.

**Risk flags.** `[HIGH RISK]` This is the largest phase and the one where scope
creep lives. Discipline: **move logic, do not improve it.** Behaviour changes
are separate commits. If a bug is found during the move, note it and fix it
after — a refactor commit that also fixes bugs is unreviewable and unbisectable.

### Phase 4 — Thin the presenters

**Goal.** `cli/` and `mcp/` contain no orchestration; the duplication is gone.

**Work.** Rewrite every CLI command and MCP tool as: parse → invoke use case →
render DTO → map exit code. Install the single `AzathothError` boundary in
`cli/main.py` and delete the four repeated `except I18nError` blocks. Delete the
now-orphaned imports of `core.llm` and `_run_git` from both surfaces.

**Ship the tokens + chars feature here.** `CommitProposal` carries `diff_chars`
and `diff_tokens` (§5.4), computed once in `core/workflow.propose_commit` via
the existing `estimate_tokens`. The CLI renders both on the staged-diff line,
replacing today's chars-only display at `cli/commands/workflow.py:65`. **Because
the count lives in the DTO rather than the renderer, the MCP `stage_and_commit`
tool gets it for free** — which is a compact demonstration of why the whole
layer exists.

**Exit criteria.** No file under `cli/` or `mcp/` imports `core.llm`,
`providers.*`, or a `core` private name. `azathoth workflow commit` displays
chars and estimated tokens; the MCP tool reports both. Both surfaces produce
identical _data_ for the same input, differing only in formatting — assert this
in a test. `just ci` green.

**Risk flags.** `[REVISIT]` Confirm the `AzathothError` hierarchy actually
contains everything the surfaces need to catch, especially whether
`AllProvidersFailedError` reaches the boundary — this is the item blocked on
reading `providers/base.py`.

### Phase 5 — Scout as a first-class capability _(Plan 2, resequenced)_

**Goal.** The most differentiated capability is reachable from any MCP client.

**Work.** Build `mcp/scout.py` with three tools per Plan 2's decision C — an
orchestrating `scout()` for onboarding, plus `detect_stack()` and
`get_directives()` for narrow follow-up questions that shouldn't trigger a
re-scan. Add the matching `cli/commands/scout.py`. Both are thin renderers over
the Phase 3 use cases, which is why this phase is small.

Note the resequencing: Plan 2 put its directive migration first and scout third.
Per Q4 there is no meta-prompt content to migrate, so the dependency that
justified that ordering does not exist. Scout ships first because it is purely
additive.

**Exit criteria.** `azathoth-mcp-scout` starts on stdio and registers three
tools. Dogfood test: scout the Azathoth repo itself and get a usable report.
Spike a 10k-file repo to confirm `list_only` ingest stays fast enough to be
worth calling from an agent.

**Risk flags.** `[REVISIT]` Scout's value is bounded by directive content, which
Phase 6 supplies. Shipping scout first means it initially returns a thin master
context — acceptable, and honest, provided the CLI says so rather than returning
a confident-looking empty string.

### Phase 6 — Directive format cutover

**Goal.** One unambiguous source of truth for directive content.

**Work.** Convert the loader to folder-per-directive (§5.10). Convert
`directives/core.toml` into `directives/core/meta.toml` +
`directives/core/philosophy.md` by hand. Seed the philosophy content from the
coding standards that genuinely exist in `CONTRIBUTING.md` and your INSTRUCTIONS
— that is real, opinionated, already-written material, and it is exactly what
scout should be returning. Per Q3: no shim, no dual-format reader, no migrate
command.

**Exit criteria.** The loader raises explicitly on a malformed directive folder
rather than returning an empty `Directive`. A fitness function asserts every
directory under `directives/` has a `meta.toml`. Scout returns a non-trivial
master context.

**Risk flags.** `[REVISIT]` No language directives are authored (Q4). The format
supports them; content is a later editorial task, not an engineering one.

### Phase 7 — Make the architecture executable

**Goal.** Every rule in this document is enforced by `just ci`, not by memory.

**Work.** Implement R5, R6, R7, R8 and budget B1 (§3.8). Extend R4 to catch
module-level `get_config()`. Restore the preview-model check as a startup check
at all four entry points (§5.9). Sweep the standards: delete
`from __future__ import annotations` from the eight files that have it, apply
`frozen=True` to all twelve Pydantic models, resolve the remaining `BLE001`
blind excepts, and carve the `dev/` exception into the no-`print` rule. Make the
i18n tests hermetic on `tmp_path` so they stop failing when a fixture directory
is deleted from the working tree. Update `CONTRIBUTING.md` — it currently says
three architecture rules (there are already four), mandates
`from __future__ import annotations` (now banned), and names `pyright` (the
stack is `ty`).

**Exit criteria.** Each new rule has a test in `tests/arch/` proving it _catches
a deliberate violation_ — a fitness function that has never been seen to fail is
not known to work. `just ci` green with all rules active.

**Risk flags.** `[REVISIT]` Before treating the 85 outstanding ruff findings as
debt, separate genuine issues from ruleset misconfiguration: `EXE002` (missing
shebang) firing across 53 files suggests `EXE` is selected too broadly for a
library. `BLE001` and `B008` are real and overlap the blind-except and
mutable-default findings.

---

## 7 · Implementation Management

### 7.1 Dependency graph

```
Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──▶ Phase 3 ──▶ Phase 4 ──▶ Phase 5
(wheels,     (unblock)   (git,       (use        (thin       (scout
 CVEs)                    serde,      cases)      presenters,  MCP)
                          generate_               tokens)
                          model)                      │
                                                      ├──▶ Phase 6 (directives)
                                                      └──▶ Phase 7 (fitness)
```

**Critical path: 0 → 1 → 2 → 3 → 4.** Any delay there cascades. Phases 6 and 7
are independent of each other and of Phase 5, and can be interleaved or run in
parallel once Phase 4 lands.

**Phase 0 is a genuine gate, not a formality.** If 3.14 wheels are missing, the
floor decision reverts to `>=3.12` and §3.9's annotation-rule inversion is
cancelled. Everything else in the plan is unaffected. Resolve this before
writing anything.

### 7.2 Ownership

Single developer plus AI agents. The useful split is by _reviewability_:

| Work type     | Best handled by           | Why                                                                            |
| ------------- | ------------------------- | ------------------------------------------------------------------------------ |
| Phases 0-2, 7 | AI agent, human review    | Mechanical, well-specified, verified by the harness                            |
| Phase 3       | Human-led, agent-assisted | Contract design is judgement; getting DTO shapes wrong is expensive later      |
| Phase 4       | AI agent, human review    | Mechanical once Phase 3's contracts exist                                      |
| Phases 5-6    | Human                     | Scout tool granularity and directive prose are taste, and taste is the product |

### 7.3 High-risk integration points

- **Phase 3 → 4 handoff.** The DTOs are the contract. If Phase 4 finds a
  renderer needs data the DTO lacks, add the field in `core/` — never recompute
  in the renderer. A single recomputation in a presenter is how this whole class
  of duplication started.
- **Phase 0 → everything.** A dependency upgrade landing mid-refactor makes
  bisection useless. Keep them in separate commits with a green tree between.
- **Phase 7 rules vs. Phases 3-5 code.** Write each new fitness function
  _before_ the sweep that satisfies it, so you see it fail first. A rule
  authored against already-clean code has never demonstrated it can detect
  anything.

### 7.4 Hard-to-undo decisions

| Decision                                   | Reversibility                          | Note                                                                               |
| ------------------------------------------ | -------------------------------------- | ---------------------------------------------------------------------------------- |
| `>=3.14` floor                             | Easy now, hard once anyone installs it | Phase 0 gate exists for this                                                       |
| Orchestration in `core/<domain>.py` (Q2-c) | Moderate                               | §5.2 defines the split-by-domain escape hatch                                      |
| `ExceptionGroup` for aggregate failure     | Hard                                   | Changes catch semantics for every caller. Free now, breaking later.                |
| DTO field names                            | Hard once a surface renders them       | Name for meaning, not for current display. `diff_tokens_estimated` beats `tokens`. |
| Folder-per-directive                       | Easy                                   | One converted file, no users                                                       |
| Single distribution + extras               | Easy                                   | §5.8 — layering makes a later split mechanical                                     |

---

## 8 · Validation & Testing Strategy

| Layer             | Test type                | Verifies                                                                                                                                                   |
| ----------------- | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Provider adapters | Unit, mocked transport   | Vendor translation both ways; exception classification per error class                                                                                     |
| Provider port     | Contract tests           | Fake providers satisfy the Protocol; `register` rejects non-conformers                                                                                     |
| LLM façade        | Unit, fake providers     | Chain order, fall-through on retryable, halt on non-retryable, both timeout tiers, ExceptionGroup composition, `generate_model` valid/malformed/mismatched |
| Core primitives   | Unit, `tmp_path`         | git helpers against real temp repos; serde round-trips; token/size formatting                                                                              |
| Core use cases    | Unit, fakes + `tmp_path` | Full orchestration with no network, no terminal, no repo-relative paths                                                                                    |
| CLI               | Typer `CliRunner`        | Exit codes, error boundary, rendering of each DTO variant                                                                                                  |
| MCP               | FastMCP test client      | Tool registration, string output, error-as-text rather than raise                                                                                          |
| Cross-surface     | Parity test              | CLI and MCP produce identical DTOs for identical input                                                                                                     |
| Architecture      | Fitness functions        | R1-R8, B1 — **plus a test per rule proving it catches a violation**                                                                                        |
| End-to-end        | Dogfood                  | Scout, ingest, and commit-dry-run against the Azathoth repo itself                                                                                         |

**The parity test is the load-bearing one.** It is the executable statement of
this plan's thesis: two surfaces, one behaviour. If it ever fails, orchestration
has leaked back into a presenter.

**Fitness functions.** Eight dependency rules plus one performance budget
(§3.8). Each gets a paired negative test in `tests/arch/` that injects a
deliberate violation and asserts a non-zero exit. `CONTRIBUTING.md` already
documents this self-test discipline for the existing rules — extend it rather
than reinventing it.

**Hermetic tests are mandatory.** Three i18n tests currently fail because they
depend on a real `i18n/project.inlang/settings.json` on disk, so coverage is
hostage to working-tree state. Every fixture becomes `tmp_path`-constructed. A
test that fails because a file was deleted from your checkout is not testing
your code.

**Local dev validation.** `just ci` — the harness is the contract. A PR that
hasn't passed it locally hasn't happened.

**Observability.** Keep the existing logging contract (DEBUG for successful
calls, INFO for fallback events, WARNING for provider errors, never log API
keys) and add: `AZATHOTH_LOG_LEVEL` env var so MCP clients can debug their
integration, structured key=value fields for machine parsing, and the
provider-attempt banner moved from rich-stderr into an INFO record the CLI can
choose to render. 3.14's `asyncio` introspection is worth knowing about when a
provider chain hangs.

---

## 9 · Open Questions & Risks

**Must resolve before Phase 0 completes**

1. **[HIGH RISK] Do `tiktoken` and `pydantic-core` publish 3.14 wheels?** The
   single item that can invalidate the floor decision. Fallback is `>=3.12`,
   which costs only the PEP 649 benefit. **Check this first.**
2. **`providers/base.py` was unreadable in my snapshot.** Confirm `Provider` is
   `@runtime_checkable`, that the transport models are frozen, and — critically
   — that `AllProvidersFailedError` subclasses `ProviderError`. If it does not,
   error handling in `core/i18n.translate_locale` has a hole today, and Phase
   4's error boundary needs a wider catch.
3. **My baseline is stale.** The CI report describes a newer tree (ruff
   configured, `scripts/*.just`, an `i18n/` fixture directory). Re-derive line
   numbers at execution time; the structure of this plan is unaffected.

**Carrying risk**

4. **`fastmcp` and `google-genai` API velocity.** Both are pre-1.0-culture
   packages. Adapter breakage on upgrade is likely, not possible. Mitigation:
   the Ports & Adapters boundary means breakage is one file — this is exactly
   the scenario §3.1 is built for.
5. **[REVISIT] `estimate_tokens` uses cl100k_base**, an OpenAI tokenizer, for
   Gemini and Ollama. Fine as a labelled estimate (§5.4); wrong the moment
   anyone treats it as cost accounting. Name the DTO field so it cannot be
   mistaken for exact.
6. **Scout's value is content-bound.** The architecture ships in Phase 5; the
   thing that makes scout worth using is directive prose that does not exist
   yet. Engineering cannot substitute for authoring here.
7. **`config.settings_customise_sources` silently drops `dotenv_settings` and
   `file_secret_settings`**, while `azathoth/__init__.py` loads `.env` manually.
   Two mechanisms for one job, one of them pretending not to exist. Not
   blocking, but decide during Phase 7 whether to wire the source back in or
   document why the manual path wins.

**Worth spiking**

8. **Cold-import budget (B1) — what is the actual number?** Measure before
   setting a ceiling. Set it ~30% above the Phase 4 measurement so it catches
   regression without failing on noise.
9. **Scout on a 10k-file monorepo.** Plan 2 flagged this and it is still open.
   `list_only` ingest _should_ be fast; verify before advertising scout to
   agents that will call it speculatively.

---

## 10 · What this buys you at year 10

Strip away the phases and the durable claims are these:

- **A vendor SDK can be replaced in one file.** The port is the asset; adapters
  are consumables. The Google SDK has already been renamed twice — plan for the
  third.
- **A presentation surface costs a renderer, not a rewrite.** CLI, MCP, A2A,
  HTTP — each is parse-invoke-render against contracts that never learned what a
  terminal is.
- **The dependency diagram is executable.** Eight rules and a budget, checked on
  every commit. Documented architecture rots at exactly the rate people stop
  reading the document; enforced architecture does not rot.
- **Behaviour is defined once.** The number of orchestration sites stays equal
  to the number of behaviours, no matter how many surfaces you grow. That
  product staying linear instead of multiplicative is the entire thesis.
- **Modern Python was used where it deletes code.** ExceptionGroup replaced a
  hand-rolled aggregate; PEP 649 deleted a rule instead of enforcing it across
  fourteen files; `generate_model` replaced four hand-written parsers. Nothing
  was adopted for being new.

The bet is that the ports and the use-case contracts outlive every SDK, every
CLI framework, and every agent protocol they get rendered through. That is the
only kind of bet worth making on a ten-year horizon in a field this young.
