"""Exercise the legacy Windows path limit without requiring a Windows host."""
import io
import json
import os
from pathlib import Path

from unmochon_live.stage4_dynamic import _save


def test_stage4_json_save_within_windows_legacy_path_budget(tmp_path, monkeypatch):
    # Match the user's 230-character final path. Appending a UUID to the
    # 69-character JSON filename used to exceed the 259-character budget.
    filename = 'a' * 64 + '.json'
    parent_length = 230 - len(filename) - 1
    padding = parent_length - len(str(tmp_path)) - 1
    assert padding > 0
    parent = tmp_path / ('d' * padding)
    parent.mkdir()
    destination = parent / filename
    assert len(str(destination)) == 230

    original_io_open, original_os_open, original_replace = io.open, os.open, os.replace

    def guard(path):
        if not isinstance(path, int) and len(os.fsdecode(path)) > 259:
            raise FileNotFoundError(2, 'Simulated Windows legacy path limit', str(path))

    def limited_io_open(path, *args, **kwargs):
        guard(path)
        return original_io_open(path, *args, **kwargs)

    def limited_os_open(path, *args, **kwargs):
        guard(path)
        return original_os_open(path, *args, **kwargs)

    def limited_replace(source, target, *args, **kwargs):
        guard(source)
        guard(target)
        return original_replace(source, target, *args, **kwargs)

    monkeypatch.setattr(io, 'open', limited_io_open)
    monkeypatch.setattr(os, 'open', limited_os_open)
    monkeypatch.setattr(os, 'replace', limited_replace)
    payload = {'text': 'বাংলা প্রমাণ', 'status': 'processed_unverified'}
    _save(destination, payload)
    assert json.loads(destination.read_text(encoding='utf-8')) == payload
    assert list(parent.iterdir()) == [destination]
