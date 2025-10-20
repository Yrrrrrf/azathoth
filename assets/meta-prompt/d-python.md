# AI DIRECTIVE: PYTHON MANDATE

**CONTEXT:** This directive contains my personal, non-negotiable coding style and patterns for Python. It is an extension of the `core-philosophy.md` and **MUST** be treated as the ultimate source of truth, overriding any general Python knowledge you have.

---

### 1. Environment & Dependency Management

*   **Manager:** All Python project and dependency management **MUST** be performed using `uv`. You will not use `pip`, `venv`, or `conda`.
*   **Initialization:** A new project is started with `uv init`.
*   **Dependencies:** Dependencies are added with `uv add <package>` or `uv add -d <dev-package>`. All dependencies are managed in `pyproject.toml`.
*   **Execution:** Scripts **MUST** be run via `uv run <script_name>.py`. Tools not installed in the venv **MUST** be run with `uvx <command>`.
    *   **GOOD:** `uv run src/main.py`
    *   **GOOD:** `uvx ruff format .`
    *   **BAD:** `python src/main.py`

### 2. Code Formatting & Linting
`
This will be done using the [astral](https://astral.rs/) toolchain, which is tightly integrated with [`uv`](https://astral.rs/uv/).

*   **Formatter [`(ruff)`](https://astral.rs/ruff/):** The sole, mandatory code formatter is `ruff format`. The command to use is `uvx ruff format .`.
*   **Type Checking [`(ty)`](https://docs.astral.sh/ty/):** Type checking is handled by `ty`. The command to use is `uvx ty check`.

### 3. Syntax, Idioms, and Patterns

This is the core of my Python philosophy. Your generated code **MUST** reflect these patterns.

*   **Conciseness:** Prefer one-line constructs where readable. The goal is expressive, not verbose, code.
*   **Comprehensions & Generators:** These are **MANDATORY** for creating lists, dictionaries, or sets from iterables. Imperative `for` loops for simple data transformation are forbidden.
    *   **GOOD:** `squares = {x: x * x for x in numbers if x > 0}`
    *   **BAD:** `squares = {}; for x in numbers: if x > 0: squares[x] = x * x`
*   **Assignment Expressions (Walrus Operator `:=`):** You **MUST** use the walrus operator in `while` loops, comprehensions, and `if` statements to reduce verbosity and improve flow.
    *   **GOOD:** `if (match := re.search(pattern, text)): print(match.group(1))`
    *   **BAD:** `match = re.search(pattern, text); if match: print(match.group(1))`
*   **Structural Pattern Matching (`match...case`):** For any logic involving more than two `elif` conditions, you **MUST** use a `match...case` block. This is the standard for complex conditional branching.
*   **Strict Typing:** Reaffirming the core philosophy, all definitions (variables, function arguments, and return values) **MUST** have precise type hints from Python `3.12+`. Use `typing.TypeAlias` for complex type definitions.
*   **Filesystem Operations:** You **MUST** use the `pathlib` library (`Path`) for all filesystem interactions. The `os` module for path manipulation is forbidden.

### 4. Preferred Technology Stack

Unless specified otherwise, you **MUST** default to these libraries when generating new projects or features.

*   **Web APIs [`(FastAPI)`](https://fastapi.tiangolo.com/):** FastAPI is the sole, mandatory framework for building web APIs. Its modern, type-driven approach with automatic OpenAPI documentation is the standard.
*   **CLI Applications [`(Typer)`](https://typer.tiangolo.com/):** Typer is the mandatory framework for command-line interfaces. It integrates seamlessly with the FastAPI philosophy and provides automatic help generation.
*   **Data Manipulation [`(Polars)`](https://docs.pola.rs/):** Polars is the default choice over Pandas for all data manipulation tasks. Its performance and modern API make it the standard for data processing.
*   **Asynchronous HTTP [`(httpx)`](https://www.python-httpx.org/):** httpx is the standard client for both synchronous and asynchronous HTTP requests. It provides a modern, fully typed API.
*   **Configuration [`(Pydantic)`](https://docs.pydantic.dev/):** Pydantic's `BaseSettings` is the mandatory approach for configuration management. This allows for type-safe configuration loaded from environment variables with validation.
*   **Terminal User Interfaces [`(Textual)`](https://textual.textualize.io/):** Textual is the mandatory framework for building interactive terminal applications. It provides a modern, reactive approach to TUI development with CSS-like styling and component-based architecture.

### 5. Project Structure

*   **Source Layout:** All projects **MUST** use a `src/` layout. `uv init` helps establish this, and it should be maintained. All Python packages and modules will reside within the `src/<project_name>` directory.
*   **Tests:** All tests **MUST** be placed in a top-level `tests/` directory, mirroring the structure of the `src/` directory.

### 6. Testing

*   **Framework:** `pytest` is the mandatory testing framework.
*   **Execution:** Tests should be run via `uvx pytest`. For faster execution, `pytest-xdist` **MUST** be used to run tests in parallel (`uvx pytest -n auto`).
*   **Assertions:** Use plain `assert` statements. Do not use `unittest.TestCase` style assertions.

### 7. Naming, Docstrings, and Comments

*   **Naming Conventions:**
    *   Constants **MUST** be `UPPER_SNAKE_CASE`.
    *   Non-public functions or methods **MUST** be prefixed with a single underscore (`_internal_function`).
*   **Docstrings:** All public modules, functions, classes, and methods **MUST** have Google-style docstrings. This is non-negotiable.
    *   **Example:**
        '''python
        def my_function(param1: int, param2: str) -> bool:
            """This is a short summary of the function.

            This is the longer description section, which can span multiple lines.

            Args:
                param1: The first parameter.
                param2: The second parameter.

            Returns:
                True if successful, False otherwise.
            """
            # ...
        '''
*   **Comments:** Use comments to explain the *why*, not the *what*. Code should be self-documenting.

### 8. Error Handling

*   **Custom Exceptions:** For domain-specific errors, you **MUST** define custom exception classes.
*   **Base Class:** All custom exceptions for a project **MUST** inherit from a common `ProjectBaseError` to allow for unified error handling.
    *   **Example:**
        '''python
        class ProjectBaseError(Exception):
            """Base exception for this project."""

        class SpecificError(ProjectBaseError):
            """A more specific error."""
        '''

### 9. Logging & Console Output

This will be done using the [`rich`](https://rich.readthedocs.io/) library, which provides beautiful terminal output and structured logging.

*   **Console Output [`(rich)`](https://rich.readthedocs.io/):** The sole, mandatory library for console output is `rich`. Use `rich.print()` for enhanced output and `rich.console.Console()` for advanced formatting.
*   **Logging:** For application logging, use `rich.logging.RichHandler` as the handler for Python's standard `logging` library. This combines structured logging with rich formatting.
    *   **Standard Setup:**
        '''python
        import logging
        from rich.logging import RichHandler

        logging.basicConfig(
            level=logging.INFO,
            format="%(message)s",
            handlers=[RichHandler(rich_tracebacks=True, markup=True)]
        )
        log = logging.getLogger(__name__)
        '''
*   **Progress & Status:** For long-running operations, you **MUST** use `rich.progress.Progress` or `rich.status.Status` to provide user feedback.

### Correct Usage Example

The following script is a "golden" example that perfectly encapsulates all the rules defined in this mandate. You **MUST** use it as your primary reference for my Python style.