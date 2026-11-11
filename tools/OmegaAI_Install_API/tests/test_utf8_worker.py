"""Regressziós teszt a Windows cp1252 JSONL UnicodeEncodeError hibájára.

A teszt szándékosan UTF-8 helyett cp1252 stdout kódolással indítja a
workert; az ékezetes állapotszövegnek így sem szabad kivételt okoznia.
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def test_unicode_events_survive_legacy_windows_pipe_encoding():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    child_code = (
        "from offlineai.worker import emit; "
        "emit('stage', stage='summary', detail='Qwen \u00f6sszes\u00edt\u0151 gener\u00e1l\u00e1sa', percent=None); "
        "emit('stage', stage='diarization_done', detail='Besz\u00e9l\u0151sz\u00e9tv\u00e1laszt\u00e1s elk\u00e9sz\u00fclt', percent=100)"
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(app_dir)
    env["PYTHONIOENCODING"] = "cp1252:strict"  # ő nem kódolható ebbe.
    env.pop("PYTHONUTF8", None)
    result = subprocess.run(
        [sys.executable, "-X", "utf8=0", "-c", child_code],
        cwd=app_dir, env=env, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr.decode("ascii", "backslashreplace")
    messages = [json.loads(line) for line in result.stdout.decode("ascii").splitlines()]
    assert messages[0]["detail"] == "Qwen összesítő generálása"
    assert messages[1]["detail"] == "Beszélőszétválasztás elkészült"
    assert all(ord(character) < 128 for character in result.stdout.decode("ascii"))


def test_utf8_worker_subprocess_configured():
    project = Path(__file__).resolve().parents[1]
    source = (project / "app" / "offlineai" / "main.py").read_text(encoding="utf-8")
    assert '"PYTHONUTF8": "1"' in source
    assert '"PYTHONIOENCODING": "utf-8:backslashreplace"' in source
