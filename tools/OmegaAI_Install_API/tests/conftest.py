"""A tesztek nem töltenek le modelleket és nem használnak internetet."""
import os
import tempfile
from pathlib import Path

# Fontos, hogy már az importálás előtt tesztadat-mappára állítsuk a ROOT-ot.
_TEST_ROOT = tempfile.TemporaryDirectory(prefix='offlineai-test-')
os.environ['OFFLINEAI_HOME'] = _TEST_ROOT.name
os.environ['HF_HUB_OFFLINE'] = '1'

import pytest
from fastapi.testclient import TestClient
from offlineai.core import ensure_folders, KEY_FILE
from offlineai.main import app

@pytest.fixture(scope='session')
def local_test_root():
    ensure_folders()
    return Path(_TEST_ROOT.name)

@pytest.fixture
def api(local_test_root):
    from offlineai.main import startup
    startup()
    return TestClient(app), {'X-Api-Key': KEY_FILE.read_text().strip()}
