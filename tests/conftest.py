import shutil
import pytest
import subprocess
from pathlib import Path


@pytest.fixture
def temp_dir(tmp_path):
    """Provides a temporary directory with some dummy files."""
    d = tmp_path / "test_repo"
    d.mkdir()

    (d / "file1.txt").write_text("Hello World")
    (d / "file2.py").write_text("print('test')")
    (d / "subdir").mkdir()
    (d / "subdir" / "file3.md").write_text("# Markdown")

    return d


@pytest.fixture
def git_repo(tmp_path):
    d = tmp_path / "git_test"
    d.mkdir()
    subprocess.run(["git", "init"], cwd=d, check=True)
    subprocess.run(
        ["git", "config", "user.email", "you@example.com"], cwd=d, check=True
    )
    subprocess.run(["git", "config", "user.name", "Your Name"], cwd=d, check=True)
    return d
