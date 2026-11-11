"""Izolált AI-worker: JSONL státusz-eseményeket ír stdout-ra.

A REST-szolgáltatás külön folyamatban indítja; a szülő ellenőrzi a
szakasz-időkorlátokat, és szükség esetén megszakítja a gyermeket.
A hang, modellek, tokenek nem kerülnek az eseménynaplóba.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import threading
import traceback
from pathlib import Path

from . import engines
from .core import ROOT, config

_OUTPUT_LOCK = threading.Lock()


def emit(event: str, **data) -> None:
    """JSONL esemény a szülőfolyamatnak, Windows codepage-től függetlenül.

    A ő/ű és más nem ASCII karaktereket JSON Unicode escape-ként küldjük.
    Így az eseménysor mindig ASCII bájtsorozat (és érvényes UTF-8),
    még akkor is, ha a Python stdout például cp1252-re van állítva.
    A json.loads az eredeti magyar szöveget hibátlanul visszaállítja.
    """
    with _OUTPUT_LOCK:
        payload = json.dumps({"event": event, **data}, ensure_ascii=True)
        print(payload, flush=True)


def atomic_file(path: Path, data: str):
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(data, encoding="utf-8")
    os.replace(temp, path)


def atomic_json(path: Path, data):
    atomic_file(path, json.dumps(data, ensure_ascii=False, indent=2))


def run(job_id: str, audio_name: str, diarize: bool, summarize: bool):
    if len(job_id) != 32 or not all(c in '0123456789abcdef' for c in job_id):
        raise ValueError("Érvénytelen job azonosító")
    if audio_name != 'audio' + Path(audio_name).suffix.lower() or '/' in audio_name or '\\' in audio_name:
        raise ValueError("Érvénytelen feltöltési név")
    home = ROOT / 'data' / 'jobs' / job_id
    if not home.is_dir() or not (home / audio_name).is_file():
        raise FileNotFoundError("Hiányzik a hangfeldolgozási munkakönyvtár vagy a felvétel")
    settings = config()
    wav = home / 'working.wav'
    try:
        emit('stage', stage='convert', detail='FFmpeg hangkonvertálás', percent=0)
        engines.convert_wav(home / audio_name, wav)
        total_sec = engines.wav_duration(wav)
        emit('stage', stage='whisper', detail='Whisper betöltése és szakaszos átirat', percent=0,
             total_seconds=round(total_sec, 2))

        def on_whisper(done, total, number, count, stage_detail='', device_used='cpu'):
            emit('progress', stage='whisper', completed_seconds=round(done, 2),
                 total_seconds=round(total, 2), chunks_completed=number if stage_detail == 'Whisper chunk elkészült' else max(0, number-1),
                 chunks_total=count, percent=round(100 * done / total, 2) if total else 0,
                 detail=stage_detail, device=device_used)

        segments = engines.transcription(wav, on_progress=on_whisper)
        emit('stage', stage='whisper_done', detail='Whisper átirat elkészült', percent=100)
        if diarize:
            emit('stage', stage='diarization', detail='pyannote teljes hangon: modell betöltése', percent=None)

            def on_diarization(step, completed, total, device):
                emit('progress', stage='diarization', detail=str(step),
                     stage_units_completed=completed if isinstance(completed, (int, float)) else None,
                     stage_units_total=total if isinstance(total, (int, float)) else None,
                     percent=None, device=device)

            turns, speaker_embeddings = engines.diarization(wav, on_progress=on_diarization,
                                                          include_embeddings=True)
            # Titkos hangbiometrikus vektor: csak a helyi job mappába kerül,
            # nem szerepelhet az általános /segments válaszban.
            atomic_json(home / 'speaker-embeddings.json', speaker_embeddings)
            segments = engines.assign_speakers(segments, turns)
            emit('stage', stage='diarization_done', detail='Beszélőszétválasztás elkészült', percent=100,
                 speaker_turns=len(turns))
        atomic_json(home / 'segments.json', segments)
        text = engines.transcript_text(segments)
        atomic_file(home / 'transcript.txt', text)
        emit('transcript_done', segments=len(segments))

        if summarize:
            job = json.loads((home / 'job.json').read_text(encoding='utf-8'))
            emit('stage', stage='summary', detail='Qwen összesítő generálása', percent=None)
            partial = home / 'summary.partial.txt'
            partial.unlink(missing_ok=True)
            buffer = []
            generated_chars = [0]
            last_flush = [time.monotonic()]

            def on_token(token):
                buffer.append(token)
                generated_chars[0] += len(token)
                # Kis csomagokban írjuk le: az SSE olvasó közben láthatja a szöveget.
                if time.monotonic() - last_flush[0] > 0.20:
                    atomic_file(partial, ''.join(buffer))
                    last_flush[0] = time.monotonic()
                emit('summary_token', chars=generated_chars[0])

            def on_summary(step, completed, total):
                emit('progress', stage='summary', detail=step,
                     stage_units_completed=completed, stage_units_total=total,
                     percent=round(100*completed/total, 2) if total else None)

            out = engines.summary(text, job['title'], job['started_at'],
                                  on_progress=on_summary, on_token=on_token)
            atomic_file(home / 'summary.txt', out)
            partial.unlink(missing_ok=True)
            emit('summary_done', chars=len(out))
        emit('done')
    finally:
        wav.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--job-id', required=True)
    parser.add_argument('--audio', required=True)
    parser.add_argument('--diarize', action='store_true')
    parser.add_argument('--summarize', action='store_true')
    args = parser.parse_args()
    try:
        run(args.job_id, args.audio, args.diarize, args.summarize)
    except Exception as exc:
        emit('error', message=f'{type(exc).__name__}: {exc}'[:1000])
        traceback.print_exc(file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
