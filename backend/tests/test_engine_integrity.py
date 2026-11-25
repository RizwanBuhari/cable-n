"""The legacy engine module must be the original program, verbatim, except
the two documented I/O patches."""
import ast
import hashlib
from pathlib import Path

from app.engine import build_legacy
from app.engine.runtime import ORIGINAL_SHA256

ROOT = Path(__file__).resolve().parents[2]


def test_reference_copy_is_unchanged():
    data = (ROOT / 'reference' / 'original_engine' / 'cable_sizing_FINAL.py').read_bytes()
    assert hashlib.sha256(data).hexdigest() == ORIGINAL_SHA256


def test_legacy_module_is_regenerated_from_original():
    target = Path(build_legacy.TARGET).read_text(encoding='utf-8')
    assert target == build_legacy.build_source(), 'run: python -m app.engine.build_legacy'


def _defs(src):
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            out[node.name] = ast.dump(node)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):  # constants may be assigned more than once
                    out.setdefault('=' + t.id, []).append(ast.dump(node.value))
    return out


def test_every_function_and_constant_identical_except_patches():
    orig = _defs(build_legacy.ORIGINAL.read_text(encoding='utf-8'))
    legacy = _defs(Path(build_legacy.TARGET).read_text(encoding='utf-8'))
    assert set(orig) == set(legacy)
    diff = sorted(k for k in orig if orig[k] != legacy[k])
    assert diff == sorted(build_legacy.PATCHED_FUNCTIONS), diff


def test_engine_has_no_filesystem_side_effects_outside_target():
    src = Path(build_legacy.TARGET).read_text(encoding='utf-8')
    assert '/mnt/user-data' not in src
