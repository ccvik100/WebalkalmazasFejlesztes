"""Kétlépcsős diagnosztika: BASIC állomány/kapcsolat, DEEP tényleges helyi modellbetöltés.

A DEEP sem pótolja a valós hangos tesztet: arra az 05_TEST_MP3.bat szolgál.
"""
from __future__ import annotations
import argparse
import os
from .core import config, local_path, ffmpeg_path, status

def doctor(deep: bool = False) -> int:
    s = status()
    for k, v in s.items():
        print(f"{k}: {v}")
    needed = ('python_faster_whisper', 'python_pyannote', 'whisper_files', 'pyannote_files',
              'ffmpeg', 'ollama_local', 'qwen_available')
    missing = [x for x in needed if not s.get(x)]
    if missing:
        print("HIBA - HIÁNYZÓ ELŐFELTÉTEL: " + ", ".join(missing))
        return 1
    if not deep:
        print("BASIC SIKER: fájlok és helyi Ollama API. NEM történt Whisper/pyannote inferencia.")
        return 0
    print("DEEP: helyi Whisper modell betöltése ...")
    from faster_whisper import WhisperModel
    cfg = config()
    from .hardware import hardware_report
    hw = hardware_report()
    print('CPU/GPU kornyezet: ' + str(hw))
    WhisperModel(str(local_path(cfg['whisper_model'])), device=hw['whisper_device'],
                 compute_type=hw['whisper_compute_type'], local_files_only=True)
    print("Whisper betöltés sikeres.")
    print("DEEP: helyi pyannote pipeline betöltése ...")
    from pyannote.audio import Pipeline
    Pipeline.from_pretrained(str(local_path(cfg['pyannote_model'])))
    print("pyannote betöltés sikeres.")
    return 0

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--deep', action='store_true')
    ap.add_argument('--basic', action='store_true')
    a = ap.parse_args()
    try:
        raise SystemExit(doctor(deep=a.deep))
    except Exception as e:
        print(f"ELLENŐRZÉSI HIBA [{type(e).__name__}]: {e}")
        raise SystemExit(2)
