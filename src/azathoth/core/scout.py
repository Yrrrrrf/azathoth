from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from azathoth.core.ingest import ingest, IngestionResult
from azathoth.core.directives import get_master_context


class ScoutReport(BaseModel):
    directory: str
    result: IngestionResult
    primary_language: str
    directives_loaded: List[str]
    master_context: str
    entry_point: Optional[str] = None


async def scout(target_directory: str = ".") -> ScoutReport:
    """
    Analyzes a codebase to identify structure, language, and context.
    """
    root = Path(target_directory).resolve()

    # 1. Reconnaissance
    result = await ingest(str(root), list_only=True)

    # 2. Identify Language (heuristic based on manifest files)
    language = "unknown"
    manifests = {
        "pyproject.toml": "python",
        "package.json": "typescript",  # or javascript
        "Cargo.toml": "rust",
        "go.mod": "go",
        "build.gradle": "kotlin",
        "pom.xml": "java",
    }

    for manifest, lang in manifests.items():
        if (root / manifest).exists():
            language = lang
            break

    # 3. Load Directives
    master_context = await get_master_context([language])

    # 4. Find Entry Point (heuristic)
    entry_points = [
        "main.py",
        "app.py",
        "src/main.rs",
        "src/index.ts",
        "index.js",
        "src/app.ts",
        "main.go",
    ]
    found_entry = None
    for ep in entry_points:
        if (root / ep).exists():
            found_entry = ep
            break

    return ScoutReport(
        directory=str(root),
        result=result,
        primary_language=language,
        directives_loaded=["core", language],
        master_context=master_context,
        entry_point=found_entry,
    )
