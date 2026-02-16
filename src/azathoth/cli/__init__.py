# cli/__init__.py — just re-export, nothing else
from azathoth.cli.main import app


def init_cli():
    app()
