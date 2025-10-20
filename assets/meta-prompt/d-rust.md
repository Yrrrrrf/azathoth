<!-- filepath: /home/yrrrrrf/docs/lab/azathoth/assets/meta-prompt/d-rust.md -->
# AI DIRECTIVE: RUST MANDATE

**CONTEXT:** This directive contains my personal, non-negotiable coding style and patterns for Rust. It is an extension of the `core-philosophy.md` and **MUST** be treated as the ultimate source of truth, overriding any general Rust knowledge you have.

---

### 1. Project & Dependency Management

*   **Manager:** All Rust project and dependency management **MUST** be performed using `cargo`. This is the standard and only tool you will use.
*   **Initialization:** A new project is started with `cargo new <project_name>` for binaries or `cargo new --lib <project_name>` for libraries.
*   **Dependencies:** Dependencies are added to `Cargo.toml` under `[dependencies]` or `[dev-dependencies]`. Use `cargo add <crate>` for automated addition.
*   **Execution:** Binaries **MUST** be run via `cargo run`. Development builds use `cargo build`, release builds use `cargo build --release`.
    *   **GOOD:** `cargo run --release`
    *   **GOOD:** `cargo test`
    *   **BAD:** Direct execution of compiled binaries during development

### 2. Code Formatting & Linting

*   **Formatter [`(rustfmt)`](https://rust-lang.github.io/rustfmt/):** The sole, mandatory code formatter is `rustfmt`. The command to use is `cargo fmt`.
*   **Linter [`(clippy)`](https://doc.rust-lang.org/clippy/):** Clippy is the mandatory linter. The command to use is `cargo clippy -- -D warnings`. All clippy warnings **MUST** be addressed before committing.
*   **Configuration:** Place a `rustfmt.toml` and `.clippy.toml` in the project root to enforce consistent formatting and linting rules.

### 3. Syntax, Idioms, and Patterns

This is the core of my Rust philosophy. Your generated code **MUST** reflect these patterns.

*   **Ownership & Borrowing:** You **MUST** leverage Rust's ownership system correctly. Prefer borrowing (`&T`, `&mut T`) over cloning unless absolutely necessary.
*   **Pattern Matching:** You **MUST** use `match` expressions for control flow. Avoid excessive `if let` chains; use `match` for clarity and exhaustiveness checking.
    *   **GOOD:** `match result { Ok(val) => process(val), Err(e) => log_error(e) }`
    *   **BAD:** `if let Ok(val) = result { process(val) } else if let Err(e) = result { log_error(e) }`
*   **Error Handling:** You **MUST** use `Result<T, E>` for fallible operations. The `?` operator is mandatory for error propagation. Never use `unwrap()` or `expect()` in production code except for prototyping or when panic is truly the only option.
    *   **GOOD:** `let data = read_file(path)?;`
    *   **BAD:** `let data = read_file(path).unwrap();`
*   **Iterators:** Prefer iterator chains over explicit loops. You **MUST** use `.iter()`, `.map()`, `.filter()`, `.collect()`, etc., for data transformation.
    *   **GOOD:** `let squares: Vec<_> = numbers.iter().filter(|&&x| x > 0).map(|&x| x * x).collect();`
    *   **BAD:** `let mut squares = Vec::new(); for x in &numbers { if *x > 0 { squares.push(x * x); } }`
*   **Type Inference:** Leverage Rust's type inference. Only add explicit type annotations when necessary for clarity or when the compiler requires it.
*   **Const & Static:** Use `const` for compile-time constants. Use `static` only when you need a global variable with a fixed memory address.
*   **Modules & Privacy:** Organize code into modules using `mod`. All items are private by default; use `pub` judiciously to expose public APIs.

### 4. Preferred Technology Stack

Unless specified otherwise, you **MUST** default to these crates when generating new projects or features.

*   **Web APIs [`(axum)`](https://docs.rs/axum/):** Axum is the mandatory framework for building web APIs. Its ergonomic, type-safe approach with tokio integration is the standard.
*   **CLI Applications [`(clap)`](https://docs.rs/clap/):** Clap is the mandatory framework for command-line interfaces. Use the derive API for simplicity and type safety.
*   **Async Runtime [`(tokio)`](https://tokio.rs/):** Tokio is the standard async runtime for all asynchronous code. Use `tokio::main` for async entry points.
*   **HTTP Client [`(reqwest)`](https://docs.rs/reqwest/):** reqwest is the standard HTTP client for both sync and async operations. It provides a high-level, ergonomic API.
*   **Serialization [`(serde)`](https://serde.rs/):** Serde is the mandatory framework for serialization and deserialization. Use derive macros for automatic implementations.
*   **Error Handling [`(anyhow/thiserror)`](https://docs.rs/anyhow/):** Use `anyhow` for application-level error handling and `thiserror` for library-level custom error types.
*   **Logging [`(tracing)`](https://docs.rs/tracing/):** tracing is the mandatory framework for structured logging and diagnostics. Use `tracing::info!`, `tracing::error!`, etc.
*   **Configuration [`(config)`](https://docs.rs/config/):** The `config` crate is the standard for configuration management, supporting multiple formats and environment variables.
*   **Terminal UI [`(ratatui)`](https://ratatui.rs/):** ratatui is the mandatory framework for building terminal user interfaces with immediate-mode rendering.

### 5. Project Structure

*   **Binary Projects:** The entry point **MUST** be `src/main.rs`. Additional modules go in `src/<module_name>.rs` or `src/<module_name>/mod.rs`.
*   **Library Projects:** The entry point **MUST** be `src/lib.rs`. All public APIs are exported from here.
*   **Tests:** Unit tests **MUST** be in the same file as the code, in a `#[cfg(test)] mod tests { }` block. Integration tests **MUST** be in a top-level `tests/` directory.
*   **Examples:** Example binaries **MUST** be placed in an `examples/` directory and run with `cargo run --example <name>`.
*   **Benchmarks:** Benchmarks **MUST** be placed in a `benches/` directory and run with `cargo bench`.

### 6. Testing

*   **Framework:** The built-in test framework is mandatory. Use `#[test]` for unit tests and `#[cfg(test)]` for test modules.
*   **Execution:** Tests are run via `cargo test`. For faster execution, use `cargo test -- --test-threads=<n>` to control parallelism.
*   **Assertions:** Use standard `assert!`, `assert_eq!`, and `assert_ne!` macros. For more complex assertions, consider the `assert_matches` or `pretty_assertions` crates.
*   **Documentation Tests:** You **MUST** include examples in doc comments that can be run as tests with `cargo test --doc`.

### 7. Naming, Docstrings, and Comments

*   **Naming Conventions:**
    *   Types (structs, enums, traits) **MUST** be `PascalCase`.
    *   Functions, variables, and modules **MUST** be `snake_case`.
    *   Constants and statics **MUST** be `SCREAMING_SNAKE_CASE`.
    *   Lifetimes **MUST** be short, lowercase, and descriptive (`'a`, `'buf`, `'ctx`).
*   **Documentation:** All public items (modules, functions, structs, enums, traits) **MUST** have doc comments (`///` or `/**`). Use Markdown formatting.
    *   **Example:**
        ```rust
        /// Reads a file and returns its contents.
        ///
        /// # Arguments
        ///
        /// * `path` - The path to the file to read.
        ///
        /// # Errors
        ///
        /// Returns an error if the file cannot be read.
        ///
        /// # Examples
        ///
        /// ```
        /// let contents = read_file("data.txt")?;
        /// ```
        pub fn read_file(path: &str) -> Result<String, std::io::Error> {
            // ...
        }
        ```
*   **Comments:** Use `//` for inline comments. Explain the *why*, not the *what*. Code should be self-documenting.

### 8. Error Handling

*   **Application Errors:** Use `anyhow::Result<T>` for application-level error handling. The `anyhow` crate provides context and easy error propagation.
*   **Library Errors:** Use `thiserror` to define custom error types with automatic `std::error::Error` implementations.
    *   **Example:**
        ```rust
        use thiserror::Error;

        #[derive(Error, Debug)]
        pub enum ProjectError {
            #[error("IO error: {0}")]
            Io(#[from] std::io::Error),
            #[error("Parse error: {0}")]
            Parse(String),
        }
        ```
*   **Error Propagation:** Always use `?` for error propagation. Never suppress errors with `.ok()` or `.unwrap_or_default()` unless explicitly justified.

### 9. Logging & Observability

This will be done using the [`tracing`](https://docs.rs/tracing/) framework, which provides structured, contextual logging.

*   **Logging [`(tracing)`](https://docs.rs/tracing/):** The sole, mandatory logging framework is `tracing`. Use macros like `tracing::info!`, `tracing::error!`, `tracing::debug!` for all logging.
*   **Subscriber Setup:** Initialize a tracing subscriber in `main()` using `tracing-subscriber`.
    *   **Standard Setup:**
        ```rust
        use tracing_subscriber::{fmt, EnvFilter};

        fn main() {
            tracing_subscriber::fmt()
                .with_env_filter(EnvFilter::from_default_env())
                .with_target(false)
                .init();

            tracing::info!("Application started");
        }
        ```
*   **Spans:** For long-running operations or request tracing, you **MUST** use `tracing::instrument` or manual spans to provide context.

### Correct Usage Example

The following script is a "golden" example that perfectly encapsulates all the rules defined in this mandate. You **MUST** use it as your primary reference for my Rust style.