"""Egyszeri ONLINE letöltés, meglévő helyi modellfájlok megtartásával.

Ha a korábbi Omega Meeting API-ból már át lettek másolva a modellek,
akkor ne töltse le őket újra. Ez csökkenti a letöltési időt és forgalmat.
"""
import os
from offlineai.core import ROOT

whisper = ROOT / 'models' / 'whisper-large-v3'
pyannote = ROOT / 'models' / 'pyannote-community-1'

if (whisper / 'model.bin').is_file():
    print('[KÉSZ] Whisper Large-v3 modell.bin már megvan; letöltés kihagyva.')
else:
    from huggingface_hub import snapshot_download
    print('[LETÖLTÉS] Whisper Large-v3 (Systran/faster-whisper-large-v3)')
    snapshot_download(repo_id='Systran/faster-whisper-large-v3', local_dir=whisper, max_workers=2)
    if not (whisper / 'model.bin').is_file():
        raise RuntimeError('Whisper letöltése hiányos: model.bin nem található.')

if (pyannote / 'config.yaml').is_file():
    print('[KÉSZ] pyannote Community-1 config.yaml már megvan; letöltés kihagyva.')
else:
    token = os.environ.get('HF_TOKEN', '').strip()
    if not token:
        raise SystemExit('A hiányzó pyannote modell letöltéséhez HF_TOKEN szükséges, és a modell hozzáférési feltételeit el kell fogadni.')
    from huggingface_hub import snapshot_download
    print('[LETÖLTÉS] pyannote/speaker-diarization-community-1')
    snapshot_download(repo_id='pyannote/speaker-diarization-community-1', token=token,
                      local_dir=pyannote, max_workers=2)
    if not (pyannote / 'config.yaml').is_file():
        raise RuntimeError('pyannote letöltés hiányos: config.yaml nem található.')
print('Modellek rendelkezésre állnak. A tényleges betöltést a DEEP ellenőrzés vizsgálja.')
