"""Elkülönített SQLite hangprofiltár: egy adatbázis alkalmazásonként.

A V17 speaker_db.py elvei alapján: max. 20 beleegyezéses felvétel,
normalizált hangvektor-átlag és ismeretlenként hagyott bizonytalan egyezés.
A hangfájl BLOB és a vektor is kizárólag a tenant SQLite fájljában van.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from pathlib import Path
from contextlib import contextmanager
import numpy as np
from .core import ROOT

TENANT_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{2,63}$')
MODEL = 'pyannote-community-1-centroid-v1'
MAX_SAMPLES = 20


def tenant_dir(tenant_id: str) -> Path:
    if not TENANT_PATTERN.fullmatch(tenant_id):
        raise ValueError('Alkalmazásazonosító: 3–64 karakter, kisbetű, szám, _ vagy -, betűvel kezdve.')
    return ROOT / 'data' / 'tenants' / tenant_id


def connection(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(path), timeout=20, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=20000')
    db.execute('PRAGMA secure_delete=ON')
    return db


def registry() -> sqlite3.Connection:
    db = connection(ROOT / 'data' / 'tenants' / '_registry.sqlite3')
    db.execute('''CREATE TABLE IF NOT EXISTS tenants(
        tenant_id TEXT PRIMARY KEY, label TEXT NOT NULL,
        key_hash TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    db.commit()
    return db


def provision_tenant(tenant_id: str, label: str) -> dict:
    folder = tenant_dir(tenant_id)
    label = label.strip()
    if not 1 <= len(label) <= 160:
        raise ValueError('Az alkalmazás neve 1–160 karakter lehet.')
    token = secrets.token_urlsafe(48)
    db = registry()
    try:
        with db:
            db.execute('INSERT INTO tenants(tenant_id,label,key_hash) VALUES(?,?,?)',
                (tenant_id, label, hashlib.sha256(token.encode()).hexdigest()))
        folder.mkdir(parents=True, exist_ok=True)
        with tenant_db(tenant_id):
            pass
        return {'tenant_id': tenant_id, 'label': label, 'tenant_api_key': token,
                'note': 'A kulcsot csak most adjuk vissza, nem tároljuk olvashatóan.'}
    finally:
        db.close()


def authenticate_tenant(tenant_id: str, token: str | None) -> bool:
    tenant_dir(tenant_id)  # útvonalvalidáció
    if not token or len(token) > 256:
        return False
    db = registry()
    try:
        row = db.execute('SELECT key_hash FROM tenants WHERE tenant_id=?', (tenant_id,)).fetchone()
        return row is not None and hmac.compare_digest(row['key_hash'], hashlib.sha256(token.encode()).hexdigest())
    finally:
        db.close()


@contextmanager
def tenant_db(tenant_id: str):
    db = connection(tenant_dir(tenant_id) / 'voices.sqlite3')
    db.executescript('''
      CREATE TABLE IF NOT EXISTS persons (
        id TEXT PRIMARY KEY, external_person_id TEXT UNIQUE,
        name TEXT NOT NULL, organization TEXT NOT NULL DEFAULT '',
        position TEXT NOT NULL DEFAULT '', elected_position TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
      );
      CREATE TABLE IF NOT EXISTS voice_samples (
        sample_id TEXT PRIMARY KEY,
        person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
        audio_sha256 TEXT NOT NULL,
        filename TEXT NOT NULL,
        content_type TEXT NOT NULL,
        audio BLOB NOT NULL,
        embedding_model TEXT NOT NULL,
        embedding_json TEXT NOT NULL,
        duration_seconds REAL NOT NULL,
        consent_note TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(person_id,audio_sha256)
      );
      CREATE TRIGGER IF NOT EXISTS max_20_voice_samples
      BEFORE INSERT ON voice_samples
      WHEN (SELECT COUNT(*) FROM voice_samples WHERE person_id=NEW.person_id) >= 20
      BEGIN SELECT RAISE(ABORT, 'maximum 20 voice samples per person'); END;
      CREATE TABLE IF NOT EXISTS voice_centroids (
        person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
        model TEXT NOT NULL, embedding_json TEXT NOT NULL,
        sample_count INTEGER NOT NULL, PRIMARY KEY(person_id,model)
      );
      CREATE INDEX IF NOT EXISTS ix_samples_by_person ON voice_samples(person_id);
    ''')
    db.commit()
    try:
        yield db
    finally:
        db.close()


def norm(vec):
    try:
        ar = np.asarray(vec, dtype='float64').reshape(-1)
    except (ValueError, TypeError):
        return None
    magnitude = np.linalg.norm(ar)
    if not ar.size or not np.isfinite(ar).all() or not np.isfinite(magnitude) or magnitude < 1e-8:
        return None
    return ar / magnitude


def upsert_person(db, *, name, organization='', position='', elected_position='', external_person_id=None):
    import uuid
    values = [str(v).strip() for v in (name, organization, position, elected_position)]
    if not 1 <= len(values[0]) <= 200 or any(len(s) > 250 for s in values[1:]):
        raise ValueError('A személy neve 1–200, a pozíció és szervezet legfeljebb 250 karakter lehet.')
    if external_person_id is not None:
        external_person_id = str(external_person_id).strip()
        if not 1 <= len(external_person_id) <= 120:
            raise ValueError('Érvénytelen külső személyazonosító.')
    row = db.execute('SELECT id FROM persons WHERE external_person_id=?', (external_person_id,)).fetchone() if external_person_id else None
    person_id = row['id'] if row else uuid.uuid4().hex
    with db:
        if row:
            db.execute('UPDATE persons SET name=?,organization=?,position=?,elected_position=? WHERE id=?', (*values, person_id))
        else:
            db.execute('INSERT INTO persons(id,external_person_id,name,organization,position,elected_position) VALUES(?,?,?,?,?,?)',
                       (person_id, external_person_id, *values))
    return person_dict(db, person_id)


def person_dict(db, person_id):
    row = db.execute('SELECT * FROM persons WHERE id=?', (person_id,)).fetchone()
    if not row:
        raise KeyError('A személy nem található.')
    doc = dict(row)
    doc['sample_count'] = db.execute('SELECT COUNT(*) FROM voice_samples WHERE person_id=?', (person_id,)).fetchone()[0]
    doc['sample_limit'] = MAX_SAMPLES
    return doc


def list_people(db):
    return [person_dict(db, row['id']) for row in db.execute('SELECT id FROM persons ORDER BY name COLLATE NOCASE').fetchall()]


def _rebuild(db, person_id):
    db.execute('DELETE FROM voice_centroids WHERE person_id=?', (person_id,))
    groups = {}
    for row in db.execute('SELECT embedding_model,embedding_json FROM voice_samples WHERE person_id=?', (person_id,)):
        vector = norm(json.loads(row['embedding_json']))
        if vector is not None:
            groups.setdefault((row['embedding_model'], len(vector)), []).append(vector)
    for (model, _dim), vectors in groups.items():
        avg = norm(np.mean(vectors, axis=0))
        if avg is None:
            continue
        # A modellre egyetlen dimenzió engedélyezett; új modellverzió nem keverhető.
        db.execute('INSERT OR REPLACE INTO voice_centroids(person_id,model,embedding_json,sample_count) VALUES(?,?,?,?)',
                   (person_id, model, json.dumps(avg.tolist()), len(vectors)))


def store_sample(db, person_id, audio: bytes, filename: str, content_type: str,
                 vector, duration_seconds: float, consent_note: str, model: str = MODEL):
    import uuid
    vec = norm(vector)
    if vec is None or len(vec) > 4096:
        raise ValueError('Érvénytelen hangvektor.')
    if not 3 <= duration_seconds <= 90:
        raise ValueError('A hangminta hossza 3–90 másodperc legyen.')
    if len(audio) < 100 or len(audio) > 15 * 1024 * 1024:
        raise ValueError('A hangminta legfeljebb 15 MB és nem lehet üres.')
    if not consent_note.strip() or len(consent_note) > 500:
        raise ValueError('A hangminta felvételéhez rögzített hozzájárulás szükséges.')
    person_dict(db, person_id)
    sha = hashlib.sha256(audio).hexdigest()
    prev = db.execute('SELECT sample_id FROM voice_samples WHERE person_id=? AND audio_sha256=?', (person_id, sha)).fetchone()
    if prev is None:
        count = db.execute('SELECT COUNT(*) FROM voice_samples WHERE person_id=?', (person_id,)).fetchone()[0]
        if count >= MAX_SAMPLES:
            raise ValueError('A személyhez már 20 hangminta tartozik. Előbb törölj egy korábbit.')
        sample_id = uuid.uuid4().hex
    else:
        sample_id = prev['sample_id']
    # Sem Pyannote-, sem TitaNet-verziók hangvektor-dimenzióit nem keverjük.
    cent = db.execute('SELECT embedding_json FROM voice_centroids WHERE person_id=? AND model=?', (person_id, model)).fetchone()
    if cent is not None and len(norm(json.loads(cent['embedding_json']))) != len(vec):
        raise ValueError('A korábbitól eltérő vektorméret; modellmigráció szükséges.')
    with db:
        if prev is not None:
            # SQLite BEFORE INSERT trigger az UPSERT előtt is futhat, ezért a
            # már meglévő minta frissítése kifejezett UPDATE legyen.
            db.execute('UPDATE voice_samples SET embedding_json=?, audio=?, consent_note=? WHERE sample_id=?',
                       (json.dumps(vec.tolist()), sqlite3.Binary(audio), consent_note.strip(), sample_id))
        else:
            db.execute('''INSERT INTO voice_samples(sample_id,person_id,audio_sha256,filename,content_type,audio,
              embedding_model,embedding_json,duration_seconds,consent_note)
              VALUES(?,?,?,?,?,?,?,?,?,?)''',
              (sample_id, person_id, sha, Path(filename).name[:180], content_type[:90], sqlite3.Binary(audio),
               model, json.dumps(vec.tolist()), duration_seconds, consent_note.strip()))
        _rebuild(db, person_id)
    return {'sample_id': sample_id, 'reused': prev is not None, 'person': person_dict(db, person_id)}


def samples(db, person_id):
    person_dict(db, person_id)
    return [dict(row) for row in db.execute('''SELECT sample_id, filename, content_type, duration_seconds,
         embedding_model,created_at FROM voice_samples WHERE person_id=? ORDER BY created_at DESC, sample_id''', (person_id,))]


def delete_sample(db, person_id, sample_id):
    with db:
        cur = db.execute('DELETE FROM voice_samples WHERE person_id=? AND sample_id=?', (person_id, sample_id))
        if not cur.rowcount:
            raise KeyError('Nincs ilyen hangminta.')
        _rebuild(db, person_id)
    return person_dict(db, person_id)


def match(db, vectors: dict, threshold: float = 0.88, margin: float = 0.04, limit: int = 3):
    if not 0.80 <= threshold <= 1 or not 0 <= margin <= 0.3:
        raise ValueError('Küszöb: 0.80–1.00; különbség: 0–0.30.')
    result = {}
    rows = db.execute('''SELECT c.person_id,c.model,c.embedding_json,p.name,p.position,p.elected_position,
       p.external_person_id FROM voice_centroids c JOIN persons p ON p.id=c.person_id''').fetchall()
    for speaker, profiles in vectors.items():
        ranked = []
        for model, raw in profiles.items():
            vec = norm(raw)
            if vec is None:
                continue
            for row in rows:
                if row['model'] != model:
                    continue
                prev = norm(json.loads(row['embedding_json']))
                if prev is None or len(vec) != len(prev):
                    continue
                ranked.append(dict(person_id=row['person_id'], name=row['name'],
                    position=row['position'], elected_position=row['elected_position'],
                    external_person_id=row['external_person_id'],
                    model=model, cosine_similarity=round(float(np.clip(np.dot(vec, prev), -1, 1)), 4)))
        ranked.sort(key=lambda row: row['cosine_similarity'], reverse=True)
        top = ranked[0] if ranked else None
        runner = ranked[1]['cosine_similarity'] if len(ranked)>1 else -1.0
        valid = bool(top and top['cosine_similarity'] >= threshold and
                     top['cosine_similarity']-runner >= margin)
        result[speaker] = {
            'status': 'suggested_unverified' if valid else 'unknown',
            'suggested_person': top if valid else None,
            'candidates': [{**item, 'similarity_percent': round(item['cosine_similarity']*100, 1)} for item in ranked[:limit]],
            'note': 'A százalék koszinusz-hasonlóság, NEM személyazonossági valószínűség. Jóváhagyás szükséges.'}
    return result


def rotate_tenant_key(tenant_id: str) -> str:
    tenant_dir(tenant_id)
    token = secrets.token_urlsafe(48)
    db = registry()
    try:
        with db:
            result = db.execute('UPDATE tenants SET key_hash=? WHERE tenant_id=?',
                (hashlib.sha256(token.encode()).hexdigest(), tenant_id))
        if not result.rowcount:
            raise KeyError('Az alkalmazás nem található.')
        return token
    finally:
        db.close()


def remove_tenant(tenant_id: str):
    """Minden hangminta és hangvektor törlése; végrehajtás csak admin + tenant kulccsal."""
    import shutil
    folder = tenant_dir(tenant_id)
    db = registry()
    try:
        with db:
            result = db.execute('DELETE FROM tenants WHERE tenant_id=?', (tenant_id,))
        if not result.rowcount:
            raise KeyError('Az alkalmazás nem található.')
    finally:
        db.close()
    if folder.is_dir():
        shutil.rmtree(folder)
