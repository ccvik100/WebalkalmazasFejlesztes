"""A v1.5 változásait fedő izolált tesztek. NINCS AI letöltés vagy valódi inferencia."""
import json
import sys
import threading
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from offlineai import core, engines
from offlineai import main as web


def test_progress_whisper_is_based_on_audio_seconds():
    assert web.percent_from_event("whisper", {"percent": 0}) == 8
    assert web.percent_from_event("whisper", {"percent": 50}) == 39
    assert web.percent_from_event("whisper", {"percent": 100}) == 70
    assert web.percent_from_event("diarization", {"percent": 50}) is None
    assert web.percent_from_event("whisper", {"percent": 150}) is None


def test_sse_chat_events_and_auth(api, monkeypatch):
    client, headers = api
    monkeypatch.setattr(web, "qwen_stream", lambda prompt: iter(["Szia ", "világ! ", "áéű"]))
    assert client.post('/v1/chat/stream', json={'prompt': 'Teszt'}).status_code == 401
    result = client.post('/v1/chat/stream', json={'prompt': 'Teszt'}, headers=headers)
    assert result.status_code == 200
    assert result.headers['content-type'].startswith('text/event-stream')
    assert 'event: start' in result.text
    assert result.text.count('event: token') == 3
    assert 'event: done' in result.text
    assert 'áéű' in result.text


def test_sse_summary_stages_and_tokens(api, monkeypatch):
    client, headers = api
    def fake_summary(transcript, title, started, on_progress=None, on_token=None):
        on_progress('előfeldolgozás', 1, 2)
        on_token('Kezdő')
        on_token(' és befejező')
        return 'Kezdő és befejező'
    monkeypatch.setattr(engines, 'summary', fake_summary)
    response = client.post('/v1/summaries/stream', json={'transcript': 'Egy rövid átirat.'}, headers=headers)
    assert response.status_code == 200
    assert 'event: stage' in response.text
    assert response.text.count('event: token') == 2
    assert 'event: done' in response.text


def test_three_uploads_have_independent_ids_and_queue_positions(api, monkeypatch):
    client, headers = api
    submitted = []
    monkeypatch.setattr(web.executor, 'submit', lambda f, *a: submitted.append((f, a)))
    ids = []
    for n in range(3):
        result = client.post('/v1/audio/jobs',
            files={'audio': (f'meeting{n}.mp3', b'dummy', 'audio/mpeg')},
            data={'title': f'{n} meeting'}, headers=headers)
        assert result.status_code == 202
        ids.append(result.json()['id'])
    assert len(set(ids)) == 3
    assert [client.get(f'/v1/jobs/{i}', headers=headers).json()['queue_position'] for i in ids] == [1,2,3]
    # Nincs futó feladat: a várakozók között is 0,1,2 munka van előttük.
    assert [client.get(f'/v1/jobs/{i}', headers=headers).json()['jobs_ahead'] for i in ids] == [0,1,2]
    assert [client.get(f'/v1/jobs/{i}', headers=headers).json()['queue_position_overall'] for i in ids] == [1,2,3]
    assert client.get(f'/v1/jobs/{ids[2]}', headers=headers).json()['queue_message'] == 'Sorban áll: 2 feldolgozás van előtted.'
    overview = client.get('/v1/queue', headers=headers).json()
    assert overview['queued_jobs'] >= 3
    assert overview['max_parallel_audio_jobs'] == 1
    assert overview['waiting_ids'][:3] == ids
    # Az első feladat szimulált befejezése szabadít fel egy sorhelyet.
    def worker(jid, audio, dia, summ, event):
        folder = web.workdir(jid)
        web.atomic_write(folder / 'transcript.txt', 'Az elkészült átirat')
        web.atomic_write(folder / 'summary.txt', 'Összesítő')
    monkeypatch.setattr(web, 'launch_worker', worker)
    first, args = submitted[0]
    first(*args)
    assert client.get(f'/v1/jobs/{ids[0]}', headers=headers).json()['status'] == 'completed'
    assert [client.get(f'/v1/jobs/{i}', headers=headers).json()['queue_position'] for i in ids[1:]] == [1,2]
    # A várakozó feladat HTTP-n visszavonható; több adatot nem dolgoz fel.
    cancel = client.post(f'/v1/jobs/{ids[1]}/cancel', headers=headers)
    assert cancel.json()['status'] == 'canceled'
    for f,args in submitted[1:]:
        f(*args)
    assert client.get(f'/v1/jobs/{ids[1]}',headers=headers).json()['status'] == 'canceled'
    assert client.get(f'/v1/jobs/{ids[2]}',headers=headers).json()['status'] == 'completed'


def test_sse_completed_job_delivers_results(api, monkeypatch):
    client, headers = api
    monkeypatch.setattr(web.executor, 'submit', lambda f,*a: f(*a))
    def worker(jid, *args):
        folder = web.workdir(jid)
        web.atomic_write(folder / 'transcript.txt', 'Valós minta nincs')
        web.atomic_write(folder / 'summary.txt', 'SSE teszt.')
    monkeypatch.setattr(web, 'launch_worker', worker)
    result = client.post('/v1/audio/jobs', files={'audio': ('short.mp3', b'abc', 'audio/mpeg')}, headers=headers)
    jid = result.json()['id']
    response = client.get(f'/v1/jobs/{jid}/events', headers=headers)
    assert response.status_code == 200
    assert 'event: progress' in response.text and 'event: token' in response.text
    assert 'event: done' in response.text


def test_child_watchdog_can_cancel_blocked_worker(tmp_path, monkeypatch):
    import subprocess
    original_popen = subprocess.Popen
    monkeypatch.setattr(web, 'ROOT', tmp_path)
    folder = tmp_path / 'data' / 'jobs' / ('a' * 32)
    folder.mkdir(parents=True)
    web.write_json(folder, 'job.json', {'id': 'a'*32, 'status':'running', 'progress':0})
    cfg = core.DEFAULTS.copy()
    cfg['job_timeout_sec'] = 1
    monkeypatch.setattr(web, 'config', lambda: cfg)
    def fake_popen(*args, **kwargs):
        return original_popen([sys.executable, '-u', '-c', 'import time;time.sleep(15)'], **kwargs)
    monkeypatch.setattr(web.subprocess, 'Popen', fake_popen)
    with pytest.raises(TimeoutError,match='időtúllépés'):
        web.launch_worker('a'*32, 'audio.mp3', False, False, threading.Event())


def test_real_wav_chunk_count_and_nonoverlapping_coverage(tmp_path):
    import wave
    import numpy as np
    filename = tmp_path / 'test.wav'
    # 25 másodperc mono PCM16; a chunk ablak 10 mp, átfedés 2 mp.
    with wave.open(str(filename), 'wb') as fp:
        fp.setnchannels(1); fp.setsampwidth(2); fp.setframerate(16000)
        fp.writeframes(np.zeros(25*16000, dtype='<i2').tobytes())
    chunks = list(engines.wav_chunks(filename, 10, 2))
    assert len(chunks) == 3
    assert [round(ch['core_end']-ch['core_start']) for ch in chunks] == [10, 10, 5]
    assert sum(ch['core_end']-ch['core_start'] for ch in chunks) == 25
    assert [ch['index'] for ch in chunks] == [1,2,3]


def test_diarization_hook_receives_actual_count(monkeypatch, tmp_path):
    import numpy as np
    calls = []
    fake_audio = ModuleType('pyannote.audio')
    class FakePipe:
        def __call__(self, waveform, hook):
            hook('segmentation', object(), completed=5, total=10)
            hook('embeddings', object(), completed=9, total=10)
            segment=SimpleNamespace(start=0, end=2)
            return SimpleNamespace(exclusive_speaker_diarization=SimpleNamespace(
                itertracks=lambda yield_label: iter([(segment, None, 'SPEAKER_00')])))
    fake_audio.Pipeline=SimpleNamespace(from_pretrained=lambda path: FakePipe())
    monkeypatch.setitem(sys.modules, 'pyannote', ModuleType('pyannote'))
    monkeypatch.setitem(sys.modules, 'pyannote.audio', fake_audio)
    class FakeTorch(ModuleType):
        def from_numpy(self, n): return SimpleNamespace(unsqueeze=lambda d: 'waveform')
    monkeypatch.setitem(sys.modules, 'torch', FakeTorch('torch'))
    monkeypatch.setattr(engines, 'hardware_report' if hasattr(engines,'hardware_report') else 'local_path',
                        getattr(engines, 'local_path'), raising=False) if False else None
    import offlineai.hardware as hardware
    monkeypatch.setattr(hardware, 'hardware_report', lambda:{'pyannote_device':'cpu'})
    cfg = core.DEFAULTS.copy()
    model=tmp_path/'model'; model.mkdir()
    (model/'config.yaml').write_text('x')
    cfg['pyannote_model']=str(model)
    monkeypatch.setattr(engines, 'config', lambda:cfg)
    monkeypatch.setattr(engines, 'load_pcm16_wav', lambda wav:np.zeros(32000,dtype='float32'))
    result=engines.diarization(tmp_path/'a.wav',on_progress=lambda step,done,total,device:calls.append((step,done,total,device)))
    assert result[0]['speaker_id'] == 'SPEAKER_00'
    assert ('segmentation',5,10,'cpu') in calls
    assert ('embeddings',9,10,'cpu') in calls


def test_legacy_models_are_not_written_to_wwwroot():
    assert core.DEFAULTS['whisper_model'].startswith('models/')
    assert core.DEFAULTS['ollama_url'] == 'http://127.0.0.1:11434'
    assert core.DEFAULTS['host'] == '127.0.0.1'


def test_queue_ahead_counts_active_worker_as_well(api, monkeypatch):
    """A '2 van előttem' tartalmazza az egy futó + egy várakozó munkát."""
    client, headers = api
    monkeypatch.setattr(web.executor, 'submit', lambda f, *a: None)
    ids = []
    for n in range(3):
        resp=client.post('/v1/audio/jobs', files={'audio':(f'{n}.mp3',b'abc','audio/mpeg')},headers=headers)
        assert resp.status_code == 202
        ids.append(resp.json()['id'])
    # Az első munka éppen fut: a második előtt egy, a harmadik előtt kettő van.
    web.patch_job(web.workdir(ids[0]), status='running', stage='whisper')
    one = client.get('/v1/jobs/'+ids[0],headers=headers).json()
    two = client.get('/v1/jobs/'+ids[1],headers=headers).json()
    three = client.get('/v1/jobs/'+ids[2],headers=headers).json()
    assert one['status'] == 'running' and one['jobs_ahead'] == 0
    assert two['queue_position'] == 1 and two['jobs_ahead'] == 1
    assert three['queue_position'] == 2 and three['jobs_ahead'] == 2
    assert three['queue_position_overall'] == 3
    assert '2 feldolgozás' in three['queue_message']
    sse=client.post('/v1/jobs/'+ids[2]+'/cancel',headers=headers)
    assert sse.status_code==200
    assert client.get('/v1/jobs/'+ids[2],headers=headers).json()['jobs_ahead'] is None


def test_cancel_waiting_releases_capacity_exactly_once(api, tmp_path, monkeypatch):
    """Várakozó visszavonása azonnal felszabadít egy sorhelyet, de nem kétszer."""
    client, headers = api
    import threading
    monkeypatch.setattr(web, 'ROOT', tmp_path)
    (tmp_path / 'data' / 'jobs').mkdir(parents=True)
    monkeypatch.setattr(web, 'slots', threading.BoundedSemaphore(2))
    monkeypatch.setattr(web, '_submitted', set())
    monkeypatch.setattr(web, '_cancel_events', {})
    monkeypatch.setattr(web, '_slots_released_early', set())
    pending = []
    monkeypatch.setattr(web.executor, 'submit', lambda fn, *args: pending.append((fn, args)))

    def post(n):
        return client.post('/v1/audio/jobs',
            files={'audio': (f'{n}.mp3', b'example', 'audio/mpeg')}, headers=headers)

    first = post(1)
    second = post(2)
    assert first.status_code == 202 and second.status_code == 202
    assert post(3).status_code == 429
    canceled_id = second.json()['id']
    assert client.post(f'/v1/jobs/{canceled_id}/cancel', headers=headers).json()['status'] == 'canceled'
    third = post(4)
    assert third.status_code == 202  # cancel után rögtön visszakapható a hely
    pending[1][0](*pending[1][1])  # a törölt munkához az executor később is eljut
    assert post(5).status_code == 429  # nincs téves második release
    assert not web._slots_released_early


def test_job_events_include_jobs_ahead_and_terminal_event(api, monkeypatch):
    """A kliensnek szánt SSE is tartalmazza a sorhelyet és a lezárást."""
    client, headers = api
    monkeypatch.setattr(web.executor, 'submit', lambda fn, *args: None)
    response = client.post('/v1/audio/jobs',
        files={'audio': ('sse.mp3', b'example', 'audio/mpeg')}, headers=headers)
    jid = response.json()['id']
    orig = web.enriched_job
    calls = [0]

    def changing_state(job_id):
        result = orig(job_id)
        calls[0] += 1
        if calls[0] == 1:
            result.update(status='queued', jobs_ahead=2, queue_position_overall=3,
                          queue_message='Sorban áll: 2 feldolgozás van előtted.')
        else:
            result.update(status='canceled', jobs_ahead=None, queue_position_overall=None)
        return result

    monkeypatch.setattr(web, 'enriched_job', changing_state)
    sse = client.get(f'/v1/jobs/{jid}/events', headers=headers)
    assert sse.status_code == 200
    assert '"jobs_ahead": 2' in sse.text
    assert '"queue_position_overall": 3' in sse.text
    assert 'event: done' in sse.text
