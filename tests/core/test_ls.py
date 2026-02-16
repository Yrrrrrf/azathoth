import pytest
from azathoth.core.ls import list_directory, estimate_tokens

@pytest.mark.asyncio
async def test_list_directory_basic(temp_dir):
    result = await list_directory(str(temp_dir))
    
    assert result.total_files == 2
    assert result.total_dirs == 1
    
    names = {e.name for e in result.entries}
    assert "file1.txt" in names
    assert "file2.py" in names
    assert "subdir" in names

@pytest.mark.asyncio
async def test_list_directory_recursive(temp_dir):
    result = await list_directory(str(temp_dir), recursive=True)
    
    assert result.total_files == 3  # file1, file2, file3
    assert result.total_dirs == 1

@pytest.mark.asyncio
async def test_list_directory_tokens(temp_dir):
    result = await list_directory(str(temp_dir), show_tokens=True)
    
    # file1.txt is "Hello World" -> ~2 tokens
    file1 = next(e for e in result.entries if e.name == "file1.txt")
    assert file1.token_estimate is not None
    assert file1.token_estimate > 0

def test_estimate_tokens_fallback():
    # If tiktoken fails or just generic test
    text = "a" * 100
    assert isinstance(estimate_tokens(text), int)
