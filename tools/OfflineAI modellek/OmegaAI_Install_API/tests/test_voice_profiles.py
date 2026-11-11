"""V17 SQLite hangprofil adaptáció: nincs valós AI-modell letöltés/inferencia."""
import io
import json
import time
from pathlib import Path
from offlineai import main as web, voice_store as store


def test_tenants_isolated_and_upsert(api):
    client, admin = api
    a = client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_a','label':'A intézmény'}).json()
    b = client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_b','label':'B intézmény'}).json()
    assert 'tenant_api_key' in a and a['tenant_api_key'] != b['tenant_api_key']
    h_a={**admin,'X-Tenant-Key':a['tenant_api_key']}
    h_b={**admin,'X-Tenant-Key':b['tenant_api_key']}
    person={'external_person_id':'1','name':'Kiss Katalin','position':'Jegyző','elected_position':'Bizottsági tag'}
    assert client.post('/v1/tenants/kozseg_a/persons',json=person,headers=admin).status_code==403
    first=client.post('/v1/tenants/kozseg_a/persons',json=person,headers=h_a)
    assert first.status_code==200,first.text
    assert client.get('/v1/tenants/kozseg_b/persons',headers=h_a).status_code==403
    assert client.get('/v1/tenants/kozseg_b/persons',headers=h_b).json()==[]
    assert first.json()['position']=='Jegyző'
    assert first.json()['elected_position']=='Bizottsági tag'
    second=client.post('/v1/tenants/kozseg_a/persons',json={**person,'position':'Polgármester'},headers=h_a)
    assert second.json()['id']==first.json()['id']
    assert len(client.get('/v1/tenants/kozseg_a/persons',headers=h_a).json())==1


def test_20_samples_centroid_and_biometrics_not_probability(api):
    client, admin=api
    t=client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_c','label':'C'}).json()
    headers={**admin,'X-Tenant-Key':t['tenant_api_key']}
    person=client.post('/v1/tenants/kozseg_c/persons',headers=headers,json={'name':'Teszt személy'}).json()
    with store.tenant_db('kozseg_c') as db:
        for i in range(20):
            answer=store.store_sample(db,person['id'],bytes([i+1])*300,f'{i}.wav','audio/wav',
                                      [1.,0.,0.01],8,'Jóváhagyás ellenőrizve')
            assert answer['person']['sample_count']==i+1
        # ugyanaz a hang ismételt feltöltése nem foglal plusz helyet
        assert store.store_sample(db,person['id'],bytes([20])*300,'20.wav','audio/wav',
                                  [1.,0.,0.01],8,'Jóváhagyás ellenőrizve')['reused'] is True
        import pytest
        with pytest.raises(ValueError,match='20 hangminta'):
            store.store_sample(db,person['id'],b'new'*100,'21.wav','audio/wav',[1,0,0],7,'Hozzájárulás')
        res=store.match(db,{'SPEAKER_00':{store.MODEL:[1,0,0.01]}},threshold=0.88)
        assert res['SPEAKER_00']['status']=='suggested_unverified'
        assert res['SPEAKER_00']['suggested_person']['person_id']==person['id']
        assert 'NEM személyazonossági valószínűség' in res['SPEAKER_00']['note']
        assert store.match(db, {'SPEAKER_01':{store.MODEL:[0,1,0]} })['SPEAKER_01']['status']=='unknown'
        delete=store.delete_sample(db,person['id'],answer['sample_id'])
        assert delete['sample_count']==19
    assert client.get(f"/v1/tenants/kozseg_c/persons/{person['id']}/samples",headers=headers).status_code==200
    assert client.delete(f"/v1/tenants/kozseg_c/persons/{person['id']}",headers=headers).json()['deleted']
    assert client.get('/v1/tenants/kozseg_c/persons',headers=headers).json()==[]


def test_real_route_voice_enrollment_with_fake_model(api, monkeypatch):
    client,admin=api
    tenant=client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_d','label':'D'}).json()
    h={**admin,'X-Tenant-Key':tenant['tenant_api_key']}
    person=client.post('/v1/tenants/kozseg_d/persons',headers=h,json={'name':'Hangminta személy'}).json()
    monkeypatch.setattr(web.voice_extract,'extract_sample',lambda path, on_progress=None: ({store.MODEL:[0.5,0.5,0.1]}, 8.0))
    resp=client.post(f"/v1/tenants/kozseg_d/persons/{person['id']}/samples",headers=h,
                     files={'audio':('egyszemely.mp3',b'X'*500,'audio/mpeg')},
                     data={'consent_confirmed':'true','consent_note':'Önkéntes hozzájárulás ellenőrizve'})
    assert resp.status_code==202,resp.text
    eid=resp.json()['id']
    for _ in range(100):
        current=client.get(f'/v1/tenants/kozseg_d/enrollments/{eid}',headers=h).json()
        if current['status']=='completed':break
        time.sleep(0.02)
    assert current['status']=='completed',current
    rows=client.get(f"/v1/tenants/kozseg_d/persons/{person['id']}/samples",headers=h).json()
    assert len(rows)==1
    sid=rows[0]['sample_id']
    audio=client.get(f"/v1/tenants/kozseg_d/persons/{person['id']}/samples/{sid}/audio",headers=h)
    assert audio.content==b'X'*500
    assert client.get(f"/v1/tenants/kozseg_d/persons/{person['id']}/samples/{sid}/audio",headers=admin).status_code==403
    assert client.delete(f"/v1/tenants/kozseg_d/persons/{person['id']}/samples/{sid}",headers=h).json()['sample_count']==0


def test_voice_match_job_requires_matching_tenant_credential(api,monkeypatch):
    client,admin=api
    a=client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_e','label':'E'}).json()
    b=client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_f','label':'F'}).json()
    ha={**admin,'X-Tenant-Key':a['tenant_api_key']}
    hb={**admin,'X-Tenant-Key':b['tenant_api_key']}
    person=client.post('/v1/tenants/kozseg_e/persons',headers=ha,json={'name':'Hangszemély'}).json()
    with store.tenant_db('kozseg_e') as db:
        store.store_sample(db,person['id'],b'A'*500,'audio.wav','audio/wav',[1.,0.,0.],6,'Hozzájárulás rögzítve')
    monkeypatch.setattr(web.executor,'submit',lambda *args:None)
    res=client.post('/v1/audio/jobs',headers=ha,
        files={'audio':('beszed.mp3',b'abc','audio/mpeg')},
        data={'tenant_id':'kozseg_e','diarize':'true'})
    assert res.status_code==202,res.text
    jid=res.json()['id']
    assert client.get(f'/v1/jobs/{jid}',headers=admin).status_code==403
    assert client.get(f'/v1/jobs/{jid}',headers=hb).status_code==403
    assert client.get(f'/v1/jobs/{jid}',headers=ha).status_code==200
    folder=web.workdir(jid)
    web.write_json(folder,'segments.json',[{'start':0,'end':5,'speaker_id':'SPEAKER_00','text':'Szia'}])
    web.write_json(folder,'speaker-embeddings.json',{'SPEAKER_00':{store.MODEL:[1,0,0]}})
    web.patch_job(folder,status='completed')
    assert client.post(f'/v1/tenants/kozseg_f/jobs/{jid}/match',headers=hb,json={}).status_code==403
    match=client.post(f'/v1/tenants/kozseg_e/jobs/{jid}/match',headers=ha,json={})
    assert match.status_code==200,match.text
    assert match.json()['speakers']['SPEAKER_00']['status']=='suggested_unverified'
    assert not (folder/'speaker-names.json').exists()  # csak javaslat!
    approved=client.post(f'/v1/tenants/kozseg_e/jobs/{jid}/approve',headers=ha,
                         json={'approved':{'SPEAKER_00':person['id']}})
    assert approved.status_code==200,approved.text
    assert web.read_json(folder,'speaker-names.json')['SPEAKER_00']=='Hangszemély'


def test_diarization_embeds_speaker_data_not_in_segments(tmp_path, monkeypatch):
    # pyannote saját visszatérő objektum szimulációja; bizonyítja a label-order mappinget
    import sys
    import types
    import numpy as np
    import torch
    from offlineai import engines
    from types import SimpleNamespace
    p=tmp_path/'pyannote-community-1';p.mkdir();(p/'config.yaml').write_text('test')
    monkeypatch.setattr(engines,'config',lambda:{'pyannote_model':str(p),'device':'cpu'})
    monkeypatch.setattr(engines,'local_path',lambda _:p)
    monkeypatch.setattr(engines,'load_pcm16_wav',lambda _:np.ones(16000,dtype='float32'))
    monkeypatch.setattr('offlineai.hardware.hardware_report',lambda:{'pyannote_device':'cpu'})
    class Annotation:
        def labels(self):return ['SPEAKER_00']
        def itertracks(self,yield_label=False):
            yield SimpleNamespace(start=0,end=1),0,'SPEAKER_00'
    class Pipeline:
        @staticmethod
        def from_pretrained(x):return Pipeline()
        def to(self,x):return self
        def __call__(self,*a,**kw):
            return SimpleNamespace(exclusive_speaker_diarization=Annotation(),
                                   speaker_diarization=Annotation(),speaker_embeddings=[[1.,0.,0.]])
    monkeypatch.setitem(sys.modules,'pyannote',types.ModuleType('pyannote'))
    pm=types.ModuleType('pyannote.audio');pm.Pipeline=Pipeline
    monkeypatch.setitem(sys.modules,'pyannote.audio',pm)
    turns,profiles=engines.diarization(tmp_path/'fake.wav',include_embeddings=True)
    assert turns[0]['speaker_id']=='SPEAKER_00'
    assert profiles['SPEAKER_00'][store.MODEL]==[1.0,0.0,0.0]


def test_key_rotation_and_tenant_deletion(api):
    client,admin=api
    t=client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_g','label':'G'}).json()
    h={**admin,'X-Tenant-Key':t['tenant_api_key']}
    assert client.get('/v1/tenants/kozseg_g/persons',headers=h).status_code==200
    rotated=client.post('/v1/tenants/kozseg_g/rotate-key',headers=h).json()
    assert client.get('/v1/tenants/kozseg_g/persons',headers=h).status_code==403
    h2={**admin,'X-Tenant-Key':rotated['tenant_api_key']}
    assert client.get('/v1/tenants/kozseg_g/persons',headers=h2).status_code==200
    assert client.delete('/v1/tenants/kozseg_g',headers=h2).json()['deleted']
    assert client.get('/v1/tenants/kozseg_g/persons',headers=h2).status_code==403


def test_deleted_tenant_removes_historical_job_and_biometrics(api,monkeypatch):
    client,admin=api
    t=client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_h','label':'H'}).json()
    h={**admin,'X-Tenant-Key':t['tenant_api_key']}
    monkeypatch.setattr(web.executor,'submit',lambda *args:None)
    result=client.post('/v1/audio/jobs',headers=h,
        files={'audio':('a.mp3',b'abc','audio/mpeg')},data={'tenant_id':'kozseg_h'})
    jid=result.json()['id']
    web.patch_job(web.workdir(jid),status='completed')
    assert client.delete('/v1/tenants/kozseg_h',headers=h).json()['historical_jobs_deleted']==1
    assert not (web.ROOT/'data'/'jobs'/jid).exists()


def test_tenant_job_delete_requires_matching_key(api, monkeypatch):
    client,admin=api
    t=client.post('/v1/tenants',headers=admin,json={'tenant_id':'kozseg_i','label':'I'}).json()
    h={**admin,'X-Tenant-Key':t['tenant_api_key']}
    monkeypatch.setattr(web.executor,'submit',lambda *args:None)
    resp=client.post('/v1/audio/jobs',headers=h,files={'audio':('a.mp3',b'abc','audio/mpeg')},data={'tenant_id':'kozseg_i'})
    jid=resp.json()['id']
    assert client.delete(f'/v1/jobs/{jid}',headers=admin).status_code==403
    assert client.delete(f'/v1/jobs/{jid}',headers=h).status_code==409
    web.patch_job(web.workdir(jid),status='failed')
    assert client.delete(f'/v1/jobs/{jid}',headers=h).json()['deleted']
    assert client.get(f'/v1/jobs/{jid}',headers=h).status_code==404
