import pytest
from azathoth.core.to_txt import to_txt

@pytest.mark.asyncio
async def test_to_txt_basic(temp_dir):
    result = await to_txt(["*.txt"], root_path=str(temp_dir))
    
    assert result.file_count == 1
    assert "file1.txt" in result.files
    assert "Hello World" in result.content
    assert "file2.py" not in result.files

@pytest.mark.asyncio
async def test_to_txt_multiple_globs(temp_dir):
    result = await to_txt(["*.txt", "*.py"], root_path=str(temp_dir))
    
    assert result.file_count == 2
    assert "file1.txt" in result.files
    assert "file2.py" in result.files

@pytest.mark.asyncio
async def test_to_txt_header(temp_dir):
    result = await to_txt(["*.txt"], root_path=str(temp_dir), include_header=True)
    assert "--- FILE: file1.txt ---" in result.content

@pytest.mark.asyncio
async def test_to_txt_no_header(temp_dir):
    result = await to_txt(["*.txt"], root_path=str(temp_dir), include_header=False)
    assert "--- FILE: file1.txt ---" not in result.content
    assert "Hello World" in result.content
