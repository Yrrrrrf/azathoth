"""tests/arch/test_architecture_rules.py — fitness functions catching violations.

Per §7.3 and §8 of plan3.md: a rule authored against already-clean code has
never demonstrated it can detect anything. Each new rule (R5-R8, B1) gets a
paired test here that injects a deliberate violation and asserts the checker
flags it, plus a clean-file sanity check that it does NOT false-positive.
"""

from pathlib import Path

import azathoth.dev.architecture_check as arch


def _write(root: Path, monkeypatch, rel: str, content: str) -> Path:
    """Write *rel* under a fake `_SRC_ROOT` pointed at *root* (tmp_path), so
    `_rel()` resolves the synthetic violation file cleanly."""
    monkeypatch.setattr(arch, "_SRC_ROOT", root)
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


# ── R5: presentation purity ─────────────────────────────────────────────────


def test_r5_catches_cli_importing_core_llm(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "cli/commands/bad.py",
        "from azathoth.core.llm import generate\n",
    )
    violations = arch._check_r5_presentation_purity([path])
    assert any(v.rule == "R5:presentation-purity" for v in violations)


def test_r5_catches_mcp_importing_providers(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "mcp/bad.py",
        "from azathoth.providers.gemini import GeminiProvider\n",
    )
    violations = arch._check_r5_presentation_purity([path])
    assert any(v.rule == "R5:presentation-purity" for v in violations)


def test_r5_catches_core_private_import(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "cli/commands/bad.py",
        "from azathoth.core.workflow import _internal_helper\n",
    )
    violations = arch._check_r5_presentation_purity([path])
    assert any(v.rule == "R5:presentation-purity" for v in violations)


def test_r5_allows_clean_cli_file(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "cli/commands/good.py",
        "from azathoth.core.workflow import repo_status\n",
    )
    assert arch._check_r5_presentation_purity([path]) == []


# ── R6: no cross-package privates ───────────────────────────────────────────


def test_r6_catches_cross_package_private_import(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "cli/bad.py",
        "from azathoth.core.workflow import _run_git\n",
    )
    violations = arch._check_r6_no_cross_package_privates([path])
    assert any(v.rule == "R6:no-cross-package-privates" for v in violations)


def test_r6_allows_same_package_private_import(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "core/workflow.py",
        "from azathoth.core.git import _internal\n",
    )
    assert arch._check_r6_no_cross_package_privates([path]) == []


def test_r6_exempts_dev_package(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "dev/architecture_check.py",
        "from azathoth.providers.registry import _PROVIDERS\n",
    )
    assert arch._check_r6_no_cross_package_privates([path]) == []


# ── R7: layer direction ─────────────────────────────────────────────────────


def test_r7_catches_core_importing_cli(tmp_path, monkeypatch):
    path = _write(
        tmp_path, monkeypatch, "core/bad.py", "from azathoth.cli.main import app\n"
    )
    violations = arch._check_r7_layer_direction([path])
    assert any(v.rule == "R7:layer-direction" for v in violations)


def test_r7_catches_providers_importing_core(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "providers/bad.py",
        "from azathoth.core.llm import generate\n",
    )
    violations = arch._check_r7_layer_direction([path])
    assert any(v.rule == "R7:layer-direction" for v in violations)


def test_r7_allows_clean_core_file(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "core/good.py",
        "from azathoth.providers.base import Provider\n",
    )
    assert arch._check_r7_layer_direction([path]) == []


# ── R8: no __future__ annotations ───────────────────────────────────────────


def test_r8_catches_future_annotations_import(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "core/bad.py",
        "from __future__ import annotations\n\nx = 1\n",
    )
    violations = arch._check_r8_no_future_annotations([path])
    assert any(v.rule == "R8:no-future-annotations" for v in violations)


def test_r8_allows_clean_file(tmp_path, monkeypatch):
    path = _write(tmp_path, monkeypatch, "core/good.py", "x: int = 1\n")
    assert arch._check_r8_no_future_annotations([path]) == []


# ── B1: cold-import budget ──────────────────────────────────────────────────


def test_b1_catches_budget_exceeded(monkeypatch):
    monkeypatch.setattr(arch, "_COLD_IMPORT_BUDGET_MS", -1.0)
    violations, elapsed_ms = arch._check_b1_cold_import_budget()
    assert any(v.rule == "B1:cold-import-budget" for v in violations)
    assert elapsed_ms is not None


def test_b1_passes_with_generous_budget(monkeypatch):
    monkeypatch.setattr(arch, "_COLD_IMPORT_BUDGET_MS", 60_000.0)
    violations, elapsed_ms = arch._check_b1_cold_import_budget()
    assert violations == []
    assert elapsed_ms is not None


# ── R4 extension: module-level get_config() call ────────────────────────────


def test_r4_catches_module_level_get_config_call(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "core/bad.py",
        "from azathoth.config import get_config\n\nconfig = get_config()\n",
    )
    violations = arch._check_r4_no_bare_config_import([path])
    assert any(v.rule == "R4:no-bare-config" for v in violations)


def test_r4_allows_function_scoped_get_config_call(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        monkeypatch,
        "core/good.py",
        "from azathoth.config import get_config\n\ndef f():\n    return get_config()\n",
    )
    assert arch._check_r4_no_bare_config_import([path]) == []


# ── Full sweep against the real tree ────────────────────────────────────────


def test_run_check_passes_on_real_tree():
    """The whole point: run against the actual src/azathoth tree and expect
    zero violations — this is what `just ci` actually gates on."""
    result = arch.run_check()
    assert result.ok, [v.to_dict() for v in result.violations]
