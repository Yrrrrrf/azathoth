import asyncio
import typer
from rich.console import Console
from typing import Optional
from azathoth.core.workflow import stage_all, commit, get_diff
from azathoth.core.prompts import get_commit_prompt

console = Console()
app = typer.Typer(help="Git workflow automation.")

@app.command("commit")
def commit_cmd(
    focus: Optional[str] = typer.Option(None, "--focus", "-f", help="Focus for the commit"),
):
    """Generate an AI commit message and commit changes."""
    async def _run():
        await stage_all()
        diff = await get_diff(staged=True)
        if not diff:
            console.print("[yellow]No changes to commit.[/]")
            return
            
        console.print(f"[bold]Changes staged.[/] [dim](Diff size: {len(diff)} chars)[/]")
        
        # In a real agent scenario, we would call the LLM here using the prompt.
        prompt = get_commit_prompt(focus)
        
        # Placeholder for LLM integration
        title = "refactor: implement new core architecture"
        body = "Ported scout, workflow, and ingest logic to pure core/ modules."
        
        if typer.confirm(f"Commit with message: '{title}'?"):
            res = await commit(title, body)
            if res.success:
                console.print("[bold green]✓ Commit successful.[/]")
            else:
                console.print(f"[bold red]✗ Commit failed: {res.stderr}[/]")

    asyncio.run(_run())
