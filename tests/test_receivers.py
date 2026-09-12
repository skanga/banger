from banger.index import CodeIndex


def test_self_calls_keep_related_overrides_and_exclude_unrelated_classes(tmp_path):
    (tmp_path / "a.py").write_text(
        "class Base:\n"
        " def leaf(self): return 1\n"
        " def root(self): return self.leaf()\n"
        "class Child(Base):\n"
        " def leaf(self): return 2\n"
        "class Unrelated:\n"
        " def leaf(self): return 3\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    call = index.profile("root")["calls"][0]
    assert call["targets"] == ["a.py:2:leaf", "a.py:5:leaf"]
    assert call["resolution"] == "ambiguous"
    assert "receiver" in call["evidence"]
    assert index.get_callers("a.py:7:leaf") == []


def test_inherited_method_is_a_candidate_not_a_runtime_dispatch_claim(tmp_path):
    (tmp_path / "base.py").write_text("class Base:\n def leaf(self): return 1\n")
    (tmp_path / "child.py").write_text(
        "from base import Base\nclass Child(Base):\n def root(this): return this.leaf()\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    call = index.profile("root")["calls"][0]
    assert call["targets"] == ["base.py:2:leaf"]
    assert call["resolution"] == "ambiguous"


def test_static_method_parameter_named_self_is_not_an_implicit_receiver(tmp_path):
    (tmp_path / "a.py").write_text(
        "class A:\n def leaf(self): pass\n"
        " @staticmethod\n def root(self): return self.leaf()\n"
        "class B:\n def leaf(self): pass\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    call = index.profile("root")["calls"][0]
    assert len(call["targets"]) == 2
    assert "receiver hierarchy" not in call["evidence"]


def test_reassigned_receiver_keeps_unknown_object_candidates(tmp_path):
    (tmp_path / "a.py").write_text(
        "class A:\n def leaf(self): pass\n"
        " def root(self, other):\n  self = other\n  return self.leaf()\n"
        "class B:\n def leaf(self): pass\n"
    )
    index = CodeIndex(tmp_path)
    index.refresh()
    call = index.profile("root")["calls"][0]
    assert len(call["targets"]) == 2
    assert "receiver hierarchy" not in call["evidence"]
