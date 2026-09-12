import sys

from banger.execution import Executor


async def test_indexing_hundreds_of_classes_finishes_without_native_failure(tmp_path):
    source = ["class Base: pass"]
    source.extend(f"class Child{i}(Base):\n def method{i}(self): return {i}" for i in range(300))
    (tmp_path / "domain.py").write_text("\n".join(source) + "\n")
    driver = tmp_path / "driver.py"
    driver.write_text(
        "from pathlib import Path\nfrom banger.index import CodeIndex\n"
        "index = CodeIndex(Path.cwd())\nindex.refresh()\n"
        "assert len(index.get_hierarchy('Base')['subclasses']) == 300\n"
        "print('INDEX_COMPLETE')\n"
    )
    result = await Executor(tmp_path).run_argv([sys.executable, str(driver)], timeout=15)
    assert not result["timed_out"], result
    assert result["exit_code"] == 0, result
    assert "INDEX_COMPLETE" in result["output"]
