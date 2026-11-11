"""Konfiguráció és a helyi Qwen (Ollama) kapcsolat."""
from __future__ import annotations
import json
import os
import secrets
import threading
import shutil
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Nem elegendő csupán nem hívni a Hubot: a könyvtárakat is offline módba állítjuk.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
os.environ.setdefault("PYANNOTE_METRICS_ENABLED", "0")

ROOT = Path(os.environ.get("OFFLINEAI_HOME", Path(__file__).resolve().parents[2])).resolve()
CONFIG_FILE = ROOT / "config" / "settings.json"
KEY_FILE = ROOT / "config" / "api-key.txt"

DEFAULTS = {
    "port": 8768,
    "host": "127.0.0.1",  # HTTPS-re IIS/Caddy/NGINX reverse proxy mögött tedd.
    "max_audio_mb": 250,
    "whisper_model": "models/whisper-large-v3",
    "pyannote_model": "models/pyannote-community-1",
    "ffmpeg": "tools/ffmpeg.exe",
    "device": "auto",
    "compute_type": "auto",
    "ollama_url": "http://127.0.0.1:11434",
    "qwen_model": "qwen3:8b",
    "qwen_timeout_sec": 900,
    "qwen_num_ctx": 8192,
    "audio_chunk_seconds": 35,
    "audio_overlap_seconds": 2,
    "whisper_timeout_sec": 7200,
    "diarization_timeout_sec": 7200,
    "summary_timeout_sec": 1800,
    "convert_timeout_sec": 900,
    "job_timeout_sec": 14400,
    "stall_warning_sec": 300,
}

def config() -> dict[str, Any]:
    cfg = DEFAULTS.copy()
    if CONFIG_FILE.is_file():
        loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8-sig"))
        unknown = set(loaded) - set(DEFAULTS)
        if unknown:
            raise ValueError("Ismeretlen beállítás: " + ", ".join(sorted(unknown)))
        cfg.update(loaded)
    return cfg

def local_path(value: str) -> Path:
    p = Path(value)
    return (p if p.is_absolute() else ROOT / p).resolve()

def ffmpeg_path() -> str | None:
    configured = local_path(config()["ffmpeg"])
    if configured.is_file():
        return str(configured)
    return shutil.which("ffmpeg")

def api_key() -> str:
    if not KEY_FILE.is_file():
        return ""
    return KEY_FILE.read_text(encoding="utf-8-sig").strip()

def ollama_request(endpoint: str, payload: dict | None = None, timeout: int = 10) -> dict:
    """Az Ollama sosem publikusan érhető el; kizárólag loopbacken hívjuk."""
    from urllib.parse import urlsplit
    base = str(config()["ollama_url"]).rstrip("/")
    parsed = urlsplit(base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Biztonsági hiba: Ollama kizárólag helyi HTTP címen használható.")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + endpoint, data=data, headers={"Content-Type": "application/json"},
        method="GET" if data is None else "POST")
    # Proxy-t nem használunk: semmilyen hangsor vagy prompt nem megy internetes proxyra.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as res:
            return json.load(res)
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        raise RuntimeError("A helyi Ollama nem válaszol: " + str(err)) from err

_qwen_lock = threading.RLock()  # Egyetlen Qwen generálás a lassú szerveren.

def qwen_stream(prompt: str, system: str = "Magyar nyelvű offline asszisztens vagy.") -> Iterator[str]:
    """Valós Ollama token-stream; a modell lokális, nincs külső HTTP-proxy.

    A chunkok hossza nem kötött; hiba esetén a kivétel a stream olvasásánál
    keletkezik. A kliens csak 'done' esemény után tekintheti késznek.
    """
    from urllib.parse import urlsplit
    cfg = config()
    base = str(cfg['ollama_url']).rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise RuntimeError('Ollama csak a gép saját loopback címén használható.')
    request = urllib.request.Request(base + '/api/generate',
        data=json.dumps({
            'model': cfg['qwen_model'], 'prompt': prompt, 'system': system,
            'stream': True, 'think': False,
            'options': {'temperature': 0.15, 'num_ctx': int(cfg['qwen_num_ctx'])}
        }).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    # A Qwen többi /chat és /summaries végponttal közös kizáró záron fut.
    # A stream végéig foglalja a modellt; nem terheljük túl párhuzamos hívásokkal.
    with _qwen_lock:
        try:
            with opener.open(request, timeout=int(cfg['qwen_timeout_sec'])) as response:
                done = False
                for line in response:
                    if not line.strip():
                        continue
                    obj = json.loads(line)
                    if obj.get('error'):
                        raise RuntimeError('Ollama hiba: ' + str(obj['error'])[:400])
                    if obj.get('response'):
                        yield str(obj['response'])
                    if obj.get('done'):
                        done = True
                        break
                if not done:
                    raise RuntimeError('Az Ollama stream a záró done jelzés nélkül megszakadt.')
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError('Helyi Qwen stream hiba: ' + str(exc)) from exc


def qwen(prompt: str, system: str = "Magyar nyelvű offline asszisztens vagy.") -> str:
    cfg = config()
    with _qwen_lock:
        answer = ollama_request("/api/generate", {
            "model": cfg["qwen_model"], "prompt": prompt, "system": system,
            "stream": False, "think": False,
            "options": {"temperature": 0.15, "num_ctx": int(cfg["qwen_num_ctx"])},
        }, timeout=int(cfg["qwen_timeout_sec"]))
    content = str(answer.get("response", "")).strip()
    if not content:
        raise RuntimeError("A Qwen üres választ adott.")
    return content

def status() -> dict:
    import importlib.util
    cfg = config()
    whisper = local_path(cfg["whisper_model"])
    pyannote = local_path(cfg["pyannote_model"])
    try:
        models = ollama_request("/api/tags", timeout=3).get("models", [])
        names = [m.get("name", "") for m in models]
        ollama_ok = True
    except Exception:
        names, ollama_ok = [], False
    return {
        "service": "OfflineAI", "version": "1.6.0", "root": str(ROOT),
        "python_faster_whisper": importlib.util.find_spec("faster_whisper") is not None,
        "python_pyannote": importlib.util.find_spec("pyannote") is not None,
        "whisper_files": (whisper / "model.bin").is_file(),
        "pyannote_files": (pyannote / "config.yaml").is_file(),
        "ffmpeg": ffmpeg_path() is not None,
        "ollama_local": ollama_ok,
        "qwen_available": cfg["qwen_model"] in names,
        "qwen_model": cfg["qwen_model"],
        "audio_processing_tested": any(
            (j / "transcript.txt").is_file() and
            (j / "job.json").is_file() and
            '"status": "completed"' in (j / "job.json").read_text(encoding="utf-8")
            for j in (ROOT / "data" / "jobs").glob("*") if j.is_dir()),
        "note": "audio_processing_tested csak a korabban elkészült valós feldolgozást jelzi; "
                "az új modellverziók és a minőség külön ellenőrzendők.",
    }

def ensure_folders() -> None:
    for d in [ROOT / "config", ROOT / "models", ROOT / "data" / "jobs", ROOT / "data" / "tenants", ROOT / "tools"]:
        d.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULTS, ensure_ascii=False, indent=2), encoding="utf-8")
    if not KEY_FILE.exists():
        KEY_FILE.write_text(secrets.token_urlsafe(48), encoding="utf-8")
