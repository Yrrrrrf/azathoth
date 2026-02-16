import tomllib
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from azathoth.config import config


class DirectiveMeta(BaseModel):
    name: str
    version: str
    applies_to: List[str]


class Directive(BaseModel):
    meta: DirectiveMeta
    rules: Dict[str, str]
    examples: Optional[Dict[str, List[str]]] = None

    def render(self) -> str:
        """Renders the directive as a markdown string for the LLM."""
        lines = [f"# Directive: {self.meta.name} (v{self.meta.version})", ""]
        
        lines.append("## Rules")
        for key, value in self.rules.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")
        
        if self.examples:
            lines.append("## Examples")
            for lang, ex_list in self.examples.items():
                lines.append(f"### {lang}")
                for ex in ex_list:
                    lines.append(ex)
                    lines.append("")
        
        return "\n".join(lines)


async def load_directive(name: str) -> Optional[Directive]:
    """
    Loads a directive by name, searching built-ins first then user overrides.
    """
    # 1. Check user overrides first (as per guide, user wins)
    user_path = config.directives_dir / f"{name}.toml"
    
    # 2. Check built-ins (we'll look in a relative 'directives/' folder in the package)
    builtin_path = Path(__file__).parent.parent / "directives" / f"{name}.toml"
    
    target_path = None
    if user_path.exists():
        target_path = user_path
    elif builtin_path.exists():
        target_path = builtin_path
        
    if not target_path:
        return None
        
    with open(target_path, "rb") as f:
        data = tomllib.load(f)
        return Directive(**data)


async def get_master_context(languages: List[str]) -> str:
    """
    Combines core philosophy with language-specific directives.
    """
    directives = []
    
    # Always load core philosophy
    core = await load_directive("core")
    if core:
        directives.append(core.render())
    
    for lang in languages:
        d = await load_directive(lang.lower())
        if d:
            directives.append(d.render())
            
    return "\n\n---\n\n".join(directives)
