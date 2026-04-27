# Plan Resolutions

## OQ-2.1: What is the exact ty version to pin?
**Resolution**: The installed version of ty is `0.0.32`. We will pin `ty == 0.0.32` in `pyproject.toml` dev dependencies.

## OQ-2.2: Does ty support `# type: ignore[<rule>]` comments?
**Resolution**: Based on testing, `ty` does NOT support `# type: ignore[<rule>]` directly for its own rules (or it prefers its own syntax). We must use `# ty: ignore[<rule>]` syntax to silence ty errors specifically.
