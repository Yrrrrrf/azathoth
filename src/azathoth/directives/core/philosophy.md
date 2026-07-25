Azathoth is a single-developer project maintained with AI agents as
contributors. These principles keep the codebase verifiable by an
autonomous agent as much as by a human — they are enforced by executable
fitness functions, not just written down.

## Architecture

Dependencies flow one way: presentation (`cli/`, `mcp/`) depends on `core/`,
`core/` depends on the provider port (`providers/base.py`,
`providers/registry.py`), and only `providers/<name>.py` adapters may import
a vendor SDK. Presentation surfaces are peers — neither imports the other —
and contain no orchestration of their own; they parse input, invoke a `core/`
use case, and render the result.

## Code standards

- Modern, idiomatic syntax; avoid deprecated features.
- Full type hints on every public function.
- Functional constructs (maps, comprehensions) over imperative loops for
  data transformation.
- Comments explain *why*, never *what* — a comment restating the code next
  to it is noise.
- Favor simplicity: no speculative abstraction before a second concrete use
  case exists. Three similar lines beat a premature helper.
- Never fail silently: no bare `except:` or `except Exception:` without a
  re-raise or a structured log record.
- Immutable data transfer objects by default; mutability must be justified.

## Commit discipline

One reviewable unit of work per commit. Commit messages explain *why* a
change was made, not a restatement of the diff — that's what `git diff` is
for.

## Logging contract

`DEBUG` for successful calls, `INFO` for fallback events, `WARNING` for
provider errors. Never log API keys or other secrets.
