import pytest

from azathoth.core.git import run_git
from azathoth.core.workflow import commit, get_diff, stage_all


@pytest.mark.asyncio
async def test_workflow_full_cycle(git_repo):
    # 1. Create a file
    (git_repo / "new.txt").write_text("Change")

    # 2. Stage
    res_stage = await stage_all(cwd=str(git_repo))
    assert res_stage.success

    # 3. Check Diff (staged)
    diff = await get_diff(staged=True, cwd=str(git_repo))
    assert "new.txt" in diff

    # 4. Commit
    res_commit = await commit("feat: test", "body", cwd=str(git_repo))
    assert res_commit.success
    assert "feat: test" in res_commit.stdout

    # 5. Check Log (Verify commit exists)
    log = await run_git(["log"], cwd=str(git_repo))
    assert "feat: test" in log.stdout
