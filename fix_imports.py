import re

files = [
    "src/azathoth/cli/commands/ingest.py",
    "src/azathoth/core/directives.py",
    "src/azathoth/core/llm.py",
    "src/azathoth/core/utils.py",
    "src/azathoth/providers/gemini.py",
    "src/azathoth/providers/ollama.py"
]

for path in files:
    with open(path, "r") as f:
        text = f.read()
        
    text = text.replace("from azathoth.config import config as _cfg", "from azathoth.config import get_config\n    _cfg = get_config()")
    text = text.replace("from azathoth.config import config", "from azathoth.config import get_config\n    config = get_config()")
    
    # For module-level imports, we might have inserted `config = get_config()` at indent 0.
    # If the import was at top level:
    text = re.sub(r'^from azathoth\.config import get_config\n    config = get_config\(\)', 'from azathoth.config import get_config\nconfig = get_config()', text, flags=re.MULTILINE)

    with open(path, "w") as f:
        f.write(text)

with open("src/azathoth/config.py", "a") as f:
    f.write("\n\ndef get_config() -> Settings:\n    return config\n")
