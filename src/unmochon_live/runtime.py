"""Load the shipped stage sources; archived pilot datasets are not runtime code.

The original full-package validators remain unchanged for reproducing the pilots.
Application execution verifies every frozen Python module it uses independently.
Sealed generation verification is always performed by Stage 6 itself.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys


def verify_sources(package: Path, prefixes: tuple[str, ...]) -> int:
    package = Path(package).resolve()
    expected = json.loads((package / 'package_checksums.json').read_text(encoding='utf-8'))
    expected = expected.get('sha256', expected)
    names = [n for n in expected if n.endswith('.py') and n.startswith(prefixes)]
    if not names:
        raise ValueError('No frozen runtime source hashes')
    for name in names:
        path = (package / name).resolve()
        if (not path.is_relative_to(package) or not path.is_file() or path.is_symlink()
                or hashlib.sha256(path.read_bytes()).hexdigest() != expected[name]):
            raise ValueError('Frozen runtime source missing or changed: ' + name)
    return len(names)


def load_stage4(package):
    package = Path(package).resolve()
    count = verify_sources(package, ('stage2/', 'stage3/', 'stage4/'))
    for name in ('stage3', 'stage4'):
        loaded = sys.modules.get(name)
        if loaded and Path(loaded.__file__).resolve().parent.parent != package:
            raise ValueError('A different stage package is already imported; restart the application')
    if str(package) not in sys.path:
        sys.path.insert(0, str(package))
    return count


def load_stage6(package):
    package = Path(package).resolve()
    verify_sources(package, ('stage6/', 'compat/'))
    loaded = sys.modules.get('stage6')
    if loaded and Path(loaded.__file__).resolve().parent.parent != package:
        raise ValueError('A different Stage 6 package is already imported')
    if str(package) not in sys.path:
        sys.path.insert(0, str(package))

