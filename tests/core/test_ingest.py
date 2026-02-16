import pytest
from azathoth.core.ingest import ingest


@pytest.mark.asyncio
async def test_ingest_directory_list_only(temp_dir):
    # Tests the --list functionality (directory structure only)
    result = await ingest(str(temp_dir), list_only=True)

    assert result.metrics.file_count >= 2
    assert "file1.txt" in result.tree
    assert "file2.py" in result.tree
    assert "(Content omitted due to --list flag)" in result.content


@pytest.mark.asyncio
async def test_ingest_single_file(temp_dir):
    # Tests ingesting a single file
    file_path = temp_dir / "file1.txt"
    result = await ingest(str(file_path))

    assert result.metrics.file_count == 1
    assert "file1.txt" in result.summary
    assert "Hello World" in result.content
    assert result.suggested_filename == "file1"


@pytest.mark.asyncio
async def test_ingest_directory_full(temp_dir):
    # Tests full directory ingestion
    result = await ingest(str(temp_dir), list_only=False)

    assert result.metrics.file_count >= 2
    assert "Hello World" in result.content
    assert "print('test')" in result.content


@pytest.mark.asyncio
async def test_ingest_format_report(temp_dir):
    file_path = temp_dir / "file1.txt"
    result = await ingest(str(file_path))

    md_report = result.format_report(fmt="md")
    assert "## Summary" in md_report
    assert "## Content" in md_report
    assert "Hello World" in md_report
