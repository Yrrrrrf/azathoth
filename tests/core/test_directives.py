import pytest

from azathoth.core.directives import (
    Directive,
    DirectiveMeta,
    _load_directive_folder,
)
from azathoth.core.exceptions import DirectiveError


def test_directive_render():
    meta = DirectiveMeta(name="Test", version="1.0", applies_to=["py"])
    d = Directive(
        meta=meta,
        rules={"rule1": "Do this."},
        philosophy="Write clean code.",
        examples="print('hi')",
    )

    rendered = d.render()
    assert "# Directive: Test (v1.0)" in rendered
    assert "## Rules" in rendered
    assert "- **rule1**: Do this." in rendered
    assert "## Philosophy" in rendered
    assert "Write clean code." in rendered
    assert "## Examples" in rendered
    assert "print('hi')" in rendered


def test_directive_render_without_examples():
    meta = DirectiveMeta(name="Test", version="1.0", applies_to=["py"])
    d = Directive(meta=meta, rules={}, philosophy="Write clean code.")

    rendered = d.render()
    assert "## Examples" not in rendered
    assert "## Rules" not in rendered


def test_load_directive_folder_raises_on_missing_meta(tmp_path):
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "philosophy.md").write_text("prose")

    with pytest.raises(DirectiveError, match="meta.toml"):
        _load_directive_folder(folder)


def test_load_directive_folder_raises_on_missing_philosophy(tmp_path):
    folder = tmp_path / "broken"
    folder.mkdir()
    (folder / "meta.toml").write_text(
        '[meta]\nname = "X"\nversion = "1.0"\napplies_to = ["*"]\n'
    )

    with pytest.raises(DirectiveError, match="philosophy.md"):
        _load_directive_folder(folder)


def test_load_directive_folder_success(tmp_path):
    folder = tmp_path / "ok"
    folder.mkdir()
    (folder / "meta.toml").write_text(
        '[meta]\nname = "X"\nversion = "1.0"\napplies_to = ["*"]\n\n'
        '[rules]\nfoo = "bar"\n'
    )
    (folder / "philosophy.md").write_text("Prose here.")

    directive = _load_directive_folder(folder)
    assert directive.meta.name == "X"
    assert directive.rules == {"foo": "bar"}
    assert directive.philosophy == "Prose here."
    assert directive.examples is None
