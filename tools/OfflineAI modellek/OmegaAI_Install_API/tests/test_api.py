"""Önálló, modell nélküli regressziós API-tesztek."""
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
from offlineai import engines
from offlineai import main as web


def test_live(api):
    c, _ = api
    assert c.get('/health/live').status_code == 200


def test_root_swagger(api):
    c, _ = api
    assert c.get('/').json()['swagger'] == '/docs'
    assert c.get('/docs').status_code == 200


def test_unauthenticated(api):
    c, _ = api
    assert c.get('/v1/health/ready').status_code == 401
    assert c.post('/v1/chat', json={'prompt': 'Szia'}).status_code == 401


def test_bad_key(api):
    c, _ = api
    assert c.get('/v1/health/ready',headers={'X-Api-Key':'bad'}).status_code == 401


def test_chat(api, monkeypatch):
    c, h = api
    monkeypatch.setattr(web, 'qwen', lambda s: 'Kipróbált válasz')
    r = c.post('/v1/chat', json={'prompt':'Teszt'},headers=h)
    assert r.status_code == 200 and r.json()['answer'] == 'Kipróbált válasz'


def test_chat_validation(api):
    c, h=api
    assert c.post('/v1/chat', json={'prompt':''}, headers=h).status_code == 422


def test_summary(api,monkeypatch):
    c,h=api
    monkeypatch.setattr(engines,'summary',lambda tr,title,started:'Helyi minta')
    r=c.post('/v1/summaries', json={'transcript':'Egy megbeszélés.'},headers=h)
    assert r.status_code==200 and r.json()['summary']=='Helyi minta'


def test_bad_audio_extension(api):
    c,h=api
    r=c.post('/v1/audio/jobs',files={'audio':('test.exe',b'virus?','application/octet-stream')},headers=h)
    assert r.status_code == 400


def test_missing_audio(api):
    c,h=api
    assert c.post('/v1/audio/jobs',headers=h).status_code == 422


def test_traversal(api):
    c,h=api
    assert c.get('/v1/jobs/../../windows',headers=h).status_code in (404, 405)
    assert c.get('/v1/jobs/not-a-uuid',headers=h).status_code == 404


def test_full_audio_workflow_mock(api,monkeypatch):
    c,h=api
    monkeypatch.setattr(web.executor,'submit',lambda f,*a: f(*a))
    def fake_worker(job_id, name, diarize, summarize, cancel_event):
        folder = web.workdir(job_id)
        web.write_json(folder, 'segments.json', [{'start':0,'end':3,'text':'Jó napot!', 'speaker_id':'SPEAKER_A'}])
        web.atomic_write(folder / 'transcript.txt', 'SPEAKER_A: Jó napot!')
        web.atomic_write(folder / 'summary.txt', 'Megbeszélés összesítő teszt.')
    monkeypatch.setattr(web, 'launch_worker', fake_worker)
    monkeypatch.setattr(engines,'summary',lambda *args:'Megbeszélés összesítő teszt.')
    r=c.post('/v1/audio/jobs',files={'audio':('teszt.mp3',b'fake mp3','audio/mpeg')},
             data={'title':'Hallgatói példa','diarize':'true','summarize':'true'},headers=h)
    assert r.status_code == 202
    job_id=r.json()['id']
    status=c.get(f'/v1/jobs/{job_id}',headers=h).json()
    assert status['status']=='completed' and status['has_transcript'] and status['has_summary']
    seg=c.get(f'/v1/jobs/{job_id}/segments',headers=h).json()
    assert seg[0]['speaker_id']=='SPEAKER_A'
    assert 'SPEAKER_A' in c.get(f'/v1/jobs/{job_id}/transcript',headers=h).text
    assert 'összesítő' in c.get(f'/v1/jobs/{job_id}/summary',headers=h).text
    renamed=c.put(f'/v1/jobs/{job_id}/speaker-names',json={'names':{'SPEAKER_A':'Nóra'}},headers=h)
    assert renamed.status_code == 200
    assert 'Nóra' in c.get(f'/v1/jobs/{job_id}/transcript',headers=h).text
    assert c.get(f'/v1/jobs/{job_id}/summary',headers=h).status_code == 404
    assert c.post(f'/v1/jobs/{job_id}/regenerate-summary',headers=h).status_code == 200
    assert c.get(f'/v1/jobs/{job_id}/summary',headers=h).status_code == 200


def test_voice_id_explicitly_not_available(api):
    c,h=api
    assert c.post('/v1/voices/enroll',headers=h).status_code == 501
    assert c.post('/v1/voices/match',headers=h).status_code == 501


def test_private_ollama_url(monkeypatch):
    from offlineai import core
    config=core.config().copy()
    config['ollama_url']='https://example.com'
    monkeypatch.setattr(core,'config',lambda:config)
    with pytest.raises(RuntimeError,match='helyi HTTP'):
        core.ollama_request('/api/tags')


def test_ffmpeg_missing_diagnostic(monkeypatch,tmp_path):
    monkeypatch.setattr(engines,'ffmpeg_path',lambda:None)
    with pytest.raises(RuntimeError,match='FFmpeg hiányzik'):
        engines.convert_wav(tmp_path/'input.mp3',tmp_path/'output.wav')


def test_speaker_overlap():
    data=[{'start':0,'end':4,'text':'test','speaker_id':'SPEAKER_00'}]
    turns=[{'start':0,'end':1,'speaker_id':'X'}, {'start':1,'end':4,'speaker_id':'Y'}]
    assert engines.assign_speakers(data,turns)[0]['speaker_id']=='Y'


def test_summary_long_text_not_silently_cut(monkeypatch):
    prompts=[]
    monkeypatch.setattr(engines,'qwen',lambda prompt, system: prompts.append(prompt) or 'Tényszerű rész-összesítő')
    out=engines.summary('MEGBESZÉLÉS '+('adat ' * 16000)+' A LEGVÉGÉN.', 'Próba', '2026-11-08')
    assert out and len(prompts)>2
    assert any('A LEGVÉGÉN' in p for p in prompts)
