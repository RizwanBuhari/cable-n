"""Execution harness around the legacy engine module.

The original program talks to a terminal: it print()s warnings, asks
input() questions inside its PDF generators and writes PDFs to the current
directory. This harness runs engine calls without a terminal:

* stdout is captured, so anything the engine prints (e.g. "Warning: size X not
  in resistivity table; Cs=1.0") is returned as an engine message instead of
  being lost;
* input() is answered from a scripted queue - an unexpected prompt raises
  EngineInputRequired instead of blocking the server;
* FPDF.output() is redirected to a caller-supplied directory.

All three are module-global, so calls are serialised with one lock. That is
fine for the expected load (engineering calcs take milliseconds) and is
documented in docs/KNOWN_LIMITATIONS.md.
"""
from __future__ import annotations

import builtins
import contextlib
import io
import math
import os
import threading
from typing import Any, Iterable

from . import legacy_engine as L

ENGINE_LOCK = threading.RLock()
ENGINE_VERSION = 'cable_sizing_FINAL r6059 / Cable-N adapter 1.0.0'
ORIGINAL_SHA256 = 'fb3abae23df4b78f011bc9823a24b4b6e1b415b5cf3998829e440d4fa0492157'


class EngineInputRequired(RuntimeError):
    """The engine asked a terminal question the adapter did not script."""


class _ScriptedInput:
    def __init__(self, answers: Iterable[str]):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def __call__(self, prompt: str = '') -> str:
        self.prompts.append(str(prompt))
        if not self.answers:
            raise EngineInputRequired(f'engine asked an unscripted question: {prompt!r}')
        return self.answers.pop(0)


_output_dir = threading.local()
_OriginalFPDF = L.FPDF


class _RedirectedFPDF(_OriginalFPDF):
    """Writes PDFs into the directory set by run_engine(pdf_dir=...).

    Also restores the classic PyFPDF multi_cell() cursor behaviour the
    original report code is written for: after a multi_cell the cursor goes
    to the LEFT margin of the next line. fpdf2 >= 2.5.2 leaves it at the
    right margin by default, so the original's consecutive
    multi_cell(0, ...) calls get zero width and raise "Not enough horizontal
    space". Only the default is changed; explicit new_x/new_y/ln win."""

    def multi_cell(self, *args, **kwargs):
        if 'ln' not in kwargs:
            from fpdf.enums import XPos, YPos
            kwargs.setdefault('new_x', XPos.LMARGIN)
            kwargs.setdefault('new_y', YPos.NEXT)
        return super().multi_cell(*args, **kwargs)

    def output(self, name='', *args, **kwargs):  # noqa: D401
        target = getattr(_output_dir, 'path', None)
        if name and target:
            name = os.path.join(target, os.path.basename(str(name)))
            _output_dir.last_file = name
        return super().output(name, *args, **kwargs)


L.FPDF = _RedirectedFPDF


class EngineRun:
    def __init__(self):
        self.stdout = ''
        self.prompts: list[str] = []
        self.pdf_file: str | None = None

    @property
    def messages(self) -> list[str]:
        return [ln.strip() for ln in self.stdout.splitlines() if ln.strip()]

    @property
    def warnings(self) -> list[str]:
        return [m for m in self.messages if m.lower().startswith(('warning', 'note'))]


@contextlib.contextmanager
def run_engine(answers: Iterable[str] = (), pdf_dir: str | None = None):
    """Context for one engine call. Yields an EngineRun that receives the
    captured stdout, the prompts the engine asked and the PDF it wrote."""
    run = EngineRun()
    scripted = _ScriptedInput(answers)
    buf = io.StringIO()
    with ENGINE_LOCK:
        old_input = builtins.input
        L.input = scripted            # module global shadows the builtin
        _output_dir.path = pdf_dir
        _output_dir.last_file = None
        try:
            with contextlib.redirect_stdout(buf):
                yield run
        finally:
            if 'input' in vars(L):
                del L.input
            builtins.input = old_input
            run.stdout = buf.getvalue()
            run.prompts = scripted.prompts
            run.pdf_file = getattr(_output_dir, 'last_file', None)
            _output_dir.path = None


def latin1(text: Any) -> str:
    """The legacy PDFs use core fonts (latin-1). Make user text safe for them."""
    s = '' if text is None else str(text)
    return s.encode('latin-1', 'replace').decode('latin-1')


class NonFiniteResult(ValueError):
    pass


def to_jsonable(obj: Any, path: str = '$', strict: bool = False):
    """Convert engine output (dicts with tuples, complex numbers, numpy-free
    floats) into JSON. Non-finite floats become None and are reported, never
    silently shown as numbers."""
    if isinstance(obj, bool) or obj is None or isinstance(obj, str):
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if math.isfinite(obj):
            return obj
        if strict:
            raise NonFiniteResult(f'non-finite value at {path}')
        return None
    if isinstance(obj, complex):
        return {'re': to_jsonable(obj.real, path + '.re', strict),
                'im': to_jsonable(obj.imag, path + '.im', strict),
                'abs': to_jsonable(abs(obj), path + '.abs', strict)}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v, f'{path}.{k}', strict) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [to_jsonable(v, f'{path}[{i}]', strict) for i, v in enumerate(obj)]
    return str(obj)


def find_non_finite(obj: Any, path: str = '$') -> list[str]:
    bad = []
    if isinstance(obj, float) and not math.isfinite(obj):
        bad.append(path)
    elif isinstance(obj, complex):
        bad += find_non_finite(obj.real, path + '.re') + find_non_finite(obj.imag, path + '.im')
    elif isinstance(obj, dict):
        for k, v in obj.items():
            bad += find_non_finite(v, f'{path}.{k}')
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            bad += find_non_finite(v, f'{path}[{i}]')
    return bad
