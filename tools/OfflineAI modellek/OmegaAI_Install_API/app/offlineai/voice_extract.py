"""Offline pyannote Community-1 hangvektor-képzés a V17 manuális jóváhagyási elvével.

Valódi, helyi inferenciát végez, ezért a közös egyfeldolgozós executorban fusson!
"""
from __future__ import annotations
import tempfile
from pathlib import Path
from .voice_store import MODEL, norm
from . import engines
from .core import config, local_path


def extract_sample(audio: Path, on_progress=None) -> tuple[dict, float]:
    import torch
    from pyannote.audio import Pipeline
    from .hardware import hardware_report
    with tempfile.TemporaryDirectory(prefix='omegaai-profile-') as temp:
        wav = Path(temp) / 'sample.wav'
        if on_progress:
            on_progress('konvertálás', None, None)
        engines.convert_wav(audio, wav)
        duration = engines.wav_duration(wav)
        if duration < 3 or duration > 90:
            raise ValueError('Egyetlen személy 3–90 mp hosszú, tiszta beszédhangja szükséges.')
        data = engines.load_pcm16_wav(wav)
        import numpy as np
        if float(np.sqrt(np.mean(np.square(data, dtype=np.float64)))) < 0.001:
            raise ValueError('A hangminta néma vagy túl halk.')
        path = local_path(config()['pyannote_model'])
        if not (path / 'config.yaml').is_file():
            raise RuntimeError('Helyi pyannote Community-1 modell hiányzik.')
        if on_progress:
            on_progress('pyannote modell betöltése', None, None)
        pipe = Pipeline.from_pretrained(str(path))
        hw = hardware_report()
        device = hw['pyannote_device']
        if device == 'cuda':
            try:
                pipe.to(torch.device('cuda'))
            except Exception:
                if config().get('device') != 'auto':
                    raise
                device = 'cpu'
        if device == 'cpu':
            pipe.to(torch.device('cpu'))
        class ProgressHook:
            def __call__(self, step_name, step_artifact=None, completed=None, total=None, **kwargs):
                if on_progress:
                    on_progress(str(step_name), completed if isinstance(completed,(int,float)) else None,
                                total if isinstance(total,(int,float)) else None)
        if on_progress:
            on_progress('hangvektor-képzés indul', None, None)
        with torch.no_grad():
            result = pipe({'waveform': torch.from_numpy(data.copy()).unsqueeze(0),
                           'sample_rate': 16000}, num_speakers=1, hook=ProgressHook())
        embeddings = getattr(result, 'speaker_embeddings', None)
        if embeddings is None or len(embeddings) != 1:
            raise RuntimeError('A pyannote nem adott egyértelmű egyszemélyes hangvektort.')
        vec = norm(embeddings[0])
        if vec is None:
            raise RuntimeError('Érvénytelen pyannote hangvektor.')
        if on_progress:
            on_progress('hangvektor elkészült', 1, 1)
        return {MODEL: vec.tolist()}, duration
