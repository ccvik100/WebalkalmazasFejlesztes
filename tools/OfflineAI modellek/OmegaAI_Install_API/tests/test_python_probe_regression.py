"""Regressziós tesztek a korábbi Windows 5.1 / Python -c hibára.

Ezek NEM valódi PowerShell-futtatások, azt Windows célgépen kell tesztelni.
"""
from pathlib import Path
import importlib.util
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / 'setup' / 'ProbePython.py'
INSTALL = ROOT / 'setup' / 'Install.ps1'


def load_probe():
    spec = importlib.util.spec_from_file_location('omega_probe', PROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_probe_version_rules():
    mod = load_probe()
    assert mod.valid_python(3, 12, 64)
    assert not mod.valid_python(3, 13, 64)
    assert not mod.valid_python(3, 11, 64)
    assert not mod.valid_python(3, 12, 32)


def test_installer_uses_script_not_python_inline():
    s = INSTALL.read_text(encoding='utf-8-sig')
    assert "-c 'import sys" not in s
    assert "@{ Exe = $launcher.Source; Prefix = @('-3.12') }" in s
    assert "Run $python.Exe" in s
    assert 'ProbePython.py' in s
    assert (ROOT / 'setup' / 'ProbePython.py').is_file()


def test_probe_handles_unicode_and_spaces(tmp_path):
    target = tmp_path / 'Asztali gép' / 'OmegaAI telepito'
    target.mkdir(parents=True)
    file = target / 'ProbePython.py'
    file.write_bytes(PROBE.read_bytes())
    res = subprocess.run([sys.executable, str(file)], capture_output=True, text=True, encoding='utf8')
    expected = 0 if sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32 else 12
    assert res.returncode == expected
    assert 'Python 3.12' in (res.stdout + res.stderr)


def test_installer_copies_probe_with_setup():
    s = INSTALL.read_text(encoding='utf-8-sig')
    assert "foreach ($relative in @('app','setup','docs'" in s
    assert "'models\\ollama'" not in '\n'.join(line for line in s.splitlines() if 'Remove-Item' in line)
