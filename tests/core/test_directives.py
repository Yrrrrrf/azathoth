import pytest
from azathoth.core.directives import Directive, DirectiveMeta

def test_directive_render():
    meta = DirectiveMeta(name="Test", version="1.0", applies_to=["py"])
    d = Directive(
        meta=meta,
        rules={"rule1": "Do this."},
        examples={"py": ["print('hi')"]}
    )
    
    rendered = d.render()
    assert "# Directive: Test (v1.0)" in rendered
    assert "## Rules" in rendered
    assert "- **rule1**: Do this." in rendered
    assert "## Examples" in rendered
    assert "print('hi')" in rendered
