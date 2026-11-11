"""Statikus regresszios ellenorzesek: Windows-futas NEM tortenik itt."""
from pathlib import Path
from offlineai import core

BASE=Path(__file__).resolve().parents[1]


def test_new_ollama_url_default():
    assert core.DEFAULTS['ollama_url'] == 'http://127.0.0.1:11434'
    assert core.DEFAULTS['qwen_model'] == 'qwen3:8b'


def test_expected_working_dir_in_configuration():
    assert r'models\ollama' in (BASE/'README_HU.md').read_text(encoding='utf8')
    assert 'C:\\OmegaAI' in (BASE/'README_HU.md').read_text(encoding='utf8')


def test_bat_files_have_no_bom():
    bats=list(BASE.glob('*.bat'))
    assert len(bats) >= 8
    assert all(p.read_bytes().startswith(b'@echo off') for p in bats)
    assert all(not p.read_bytes().startswith(b'\xef\xbb\xbf') for p in bats)


def test_powershell_files_have_exactly_one_bom():
    ps_files=list((BASE/'setup').glob('*.ps1'))
    assert len(ps_files) >= 5
    assert all(p.read_bytes().startswith(b'\xef\xbb\xbf') for p in ps_files)
    assert all(not p.read_bytes().startswith(b'\xef\xbb\xbf\xef\xbb\xbf') for p in ps_files)


def test_installer_reuses_existing_model_no_second_port():
    s=(BASE/'setup'/'Install.ps1').read_text(encoding='utf-8-sig')
    assert "if ('qwen3:8b' -notin $names)" in s
    assert "'http://127.0.0.1:11434/api/tags'" in s
    assert "'config\\settings.example.json'" in s
    assert 'models\\ollama' in s
    assert 'ollama pull' not in s.lower()
    assert 'Remove-Item' not in '\n'.join(x for x in s.splitlines() if 'ollama' in x.lower())


def test_only_prior_port_migration_mentions_old_port_in_scripts():
    sources='\n'.join(f.read_text(encoding='utf-8-sig') for f in (BASE/'setup').glob('*.ps1'))
    occurrences = sources.count('11435')
    assert occurrences == 2


def test_installer_installs_own_test_files_into_root():
    s=(BASE/'setup'/'Install.ps1').read_text(encoding='utf-8-sig')
    assert "Get-ChildItem -LiteralPath $Source -Filter '*.bat'" in s
    assert "CopyWhenSeparate 'config\\settings.example.json'" not in s  # in array, not separate call
