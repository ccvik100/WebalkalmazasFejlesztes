"""Regresszio: faster-whisper 1.2.1 / PyAV 19 metadata_errors hiba elkerulese."""
import sys
import types
import wave
from pathlib import Path
import numpy as np
import pytest
from offlineai import engines


def make_pcm16_wav(path: Path, *, channels=1, rate=16000, n=1600):
    data = np.arange(n * channels, dtype=np.int16).tobytes()
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data)
    return path


def test_wav_pcm16_valid(tmp_path):
    x = engines.load_pcm16_wav(make_pcm16_wav(tmp_path/'input.wav'))
    assert x.dtype == np.float32 and x.shape == (1600,)
    assert x[0] == 0


def test_wav_pcm16_rejects_stereo(tmp_path):
    wav = make_pcm16_wav(tmp_path/'stereo.wav', channels=2)
    with pytest.raises(RuntimeError, match='mono'):
        engines.load_pcm16_wav(wav)


def test_wav_pcm16_rejects_empty(tmp_path):
    wav = make_pcm16_wav(tmp_path/'empty.wav', n=0)
    with pytest.raises(RuntimeError, match='ures'):
        engines.load_pcm16_wav(wav)


def test_whisper_gets_numpy_samples_not_path(tmp_path, monkeypatch):
    wav = make_pcm16_wav(tmp_path/'teszt.wav')
    model_dir = tmp_path/'model'
    model_dir.mkdir()
    (model_dir/'model.bin').write_bytes(b'dummy')
    observed = {}
    class FakeWhisperModel:
        def __init__(self, path, **kwargs):
            assert str(model_dir) == path
        def transcribe(self, audio, **kwargs):
            assert isinstance(audio, np.ndarray)
            assert audio.shape == (1600,)
            assert audio.dtype == np.float32
            observed['numpy'] = True
            return [types.SimpleNamespace(start=0.0, end=0.1, text='Szia!')], None
    monkeypatch.setitem(sys.modules,'faster_whisper',types.SimpleNamespace(WhisperModel=FakeWhisperModel))
    monkeypatch.setattr(engines,'config',lambda:{'whisper_model':'unused','device':'cpu','compute_type':'int8'})
    monkeypatch.setattr(engines,'local_path',lambda value:model_dir)
    result = engines.transcription(wav)
    assert observed['numpy'] is True and result[0]['text'] == 'Szia!'


def test_av_pinned_for_reproducible_install():
    req = (Path(__file__).resolve().parents[1]/'app'/'requirements-ai.txt').read_text('utf-8')
    assert 'av==18.1.0' in req
