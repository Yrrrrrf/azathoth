def get_commit_system_prompt(focus: str | None = None) -> str:
    """System prompt for direct LLM commit-message generation (JSON mode)."""
    focus_section = ""
    if focus:
        focus_section = f'\n\nThe user wants the commit message to focus on: "{focus}". Tailor the title and body accordingly.'

    return f"""You are an expert git commit message writer.

Analyze the provided git diff and produce a single JSON object with exactly two keys:
  "title" — A concise imperative-mood summary following Conventional Commits (e.g. "feat: add user auth", "fix: resolve null pointer in parser").
  "body"  — A short paragraph or bullet list explaining *why* the changes were made, not just *what* changed.

Rules:
- The title MUST start with a valid Conventional Commits type (feat, fix, refactor, chore, docs, style, test, perf, ci, build, revert).
- Keep the title under 72 characters.
- The body should be informative but concise (3-5 lines max).
- NEVER add co-author, signed-off-by, or trailer lines.
- Output ONLY the JSON object, nothing else.
{focus_section}"""


def get_release_system_prompt() -> str:
    """System prompt for direct LLM release-notes generation (JSON mode)."""
    return """You are an expert release manager.

You will receive a commit log (one commit per line, prefixed with "- ").
Analyze the commits and produce a single JSON object with exactly two keys:
  "tag"   — A suggested semantic version tag (e.g. "v1.2.0"). Infer the appropriate bump from the commits.
  "notes" — Full Markdown release notes following this structure:

## 🚀 What's New
- [Feature/change 1]
- [Feature/change 2]

## 🐛 Bug Fixes
- [Fix 1]

## 🔧 Other Changes
- [Chore/refactor 1]

Omit any empty sections. Output ONLY the JSON object, nothing else."""
