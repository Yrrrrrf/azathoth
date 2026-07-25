"""azathoth.core.scout — codebase reconnaissance: stack detection, entry point,
and the composed scout report.

Primitives (detect_stack, find_entry_point) are single-purpose and
synchronous; the use case (scout) sequences them with the async ingest and
directive primitives. See §3.4 of plan3.md for the contract.
"""

from pathlib import Path

from pydantic import BaseModel

from azathoth.core.directives import get_master_context
from azathoth.core.ingest import IngestionResult, ingest

_MANIFEST_LANGUAGES: dict[str, str] = {
    "pyproject.toml": "python",
    "package.json": "typescript",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "build.gradle": "kotlin",
    "pom.xml": "java",
}

_ENTRY_POINTS_BY_LANGUAGE: dict[str, list[str]] = {
    "python": ["main.py", "app.py"],
    "typescript": ["src/index.ts", "src/app.ts", "index.js"],
    "rust": ["src/main.rs"],
    "go": ["main.go"],
}
_FALLBACK_ENTRY_POINTS: list[str] = [
    "main.py",
    "app.py",
    "src/main.rs",
    "src/index.ts",
    "index.js",
    "src/app.ts",
    "main.go",
]


class StackInfo(BaseModel, frozen=True):
    """Result of manifest-based stack detection."""

    primary_language: str
    manifests_found: list[str]
    confidence: float


class ScoutReport(BaseModel, frozen=True):
    directory: str
    result: IngestionResult
    stack: StackInfo
    directives_loaded: list[str]
    master_context: str
    entry_point: str | None = None


# ── Primitives ───────────────────────────────────────────────────────────


def detect_stack(root: Path) -> StackInfo:
    """Detect the primary language from manifest files present at *root*."""
    manifests_found = [m for m in _MANIFEST_LANGUAGES if (root / m).exists()]

    if not manifests_found:
        return StackInfo(primary_language="unknown", manifests_found=[], confidence=0.0)

    primary = _MANIFEST_LANGUAGES[manifests_found[0]]
    confidence = 1.0 if len(manifests_found) == 1 else 1.0 / len(manifests_found)
    return StackInfo(
        primary_language=primary, manifests_found=manifests_found, confidence=confidence
    )


def find_entry_point(root: Path, language: str) -> str | None:
    """Return the first known entry-point path (relative) that exists under *root*."""
    candidates = _ENTRY_POINTS_BY_LANGUAGE.get(language, _FALLBACK_ENTRY_POINTS)
    for candidate in candidates:
        if (root / candidate).exists():
            return candidate
    return None


# ── Use case ─────────────────────────────────────────────────────────────


async def scout(target_directory: str = ".") -> ScoutReport:
    """Analyze a codebase to identify structure, language, and context."""
    root = Path(target_directory).resolve()

    result = await ingest(str(root), list_only=True)
    stack = detect_stack(root)
    entry_point = find_entry_point(root, stack.primary_language)
    master_context = await get_master_context([stack.primary_language])

    return ScoutReport(
        directory=str(root),
        result=result,
        stack=stack,
        directives_loaded=["core", stack.primary_language],
        master_context=master_context,
        entry_point=entry_point,
    )
