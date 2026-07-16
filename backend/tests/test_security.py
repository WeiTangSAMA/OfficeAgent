from pathlib import Path
import pytest
from app.security import safe_child

def test_safe_child_rejects_escape(tmp_path: Path):
    with pytest.raises(ValueError,match="PATH_ESCAPE"): safe_child(tmp_path,"..","outside.txt")

def test_safe_child_accepts_descendant(tmp_path: Path):
    assert safe_child(tmp_path,"a","b.txt").is_relative_to(tmp_path)
