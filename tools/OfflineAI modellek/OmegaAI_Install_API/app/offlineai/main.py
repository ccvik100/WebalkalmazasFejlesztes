"""OmegaAI HTTP v1: hitelesítés, tartós fájlsor, egy AI-worker és SSE.

A /v1 API-t KIZÁRÓLAG a szerveren futó ASP.NET Core API hívhatja.
Az OmegaAI localhoston figyel, nem web-/mobilkliensnek szánt szolgáltatás.
Futási feltétel: pontosan EGY uvicorn worker / egy OmegaAI API-példány.
"""
from __future__ import annotations

import asyncio
import json
import os
import queue
import re
import secrets
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import __version__, engines
from .core import ROOT, api_key, config, ensure_folders, qwen, qwen_stream, status
from .hardware import hardware_report
from . import voice_store, voice_extract

app = FastAPI(title="OmegaAI – központi offline AI REST", version=__version__,
              description="Whisper, pyannote, Qwen: sorosított hangfeldolgozás; valódi progress; SSE.")
# A ThreadPoolExecutor pontosan EGY hangfelvételt enged a modellekhez egyszerre.
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="omegaai-audio")
# 8 hely a FUTÓ + VÁRAKOZÓ munkáknak. A már kész/hibás feladatok nem foglalnak helyet.
slots = threading.BoundedSemaphore(8)
lock = threading.RLock()
_cancel_events: dict[str, threading.Event] = {}
_submitted: set[str] = set()
# Visszavont VARAKOZO feladatnal a hely azonnal felszabadul,
# akkor sem szabad masodszor release-elni, amikor az executor kesobb atlepi.
_slots_released_early: set[str] = set()
_recovered = False
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".mp4", ".flac", ".aac", ".webm", ".3gp"}
TERMINAL = {"completed", "failed", "canceled"}
STAGE_TIMEOUT_KEYS = {"convert": "convert_timeout_sec", "whisper": "whisper_timeout_sec",
                      "diarization": "diarization_timeout_sec", "summary": "summary_timeout_sec"}
# Az összesített százalék illusztratív, súlyozott STAGE-mérő. A pyannote-nál
# NINCS globális valódi százalék; ott nem növeljük, amíg a szakasz nem fejeződik be.
STAGE_BANDS = {"convert": (1, 8), "whisper": (8, 70),
               "diarization": (70, 85), "summary": (85, 99)}


class ChatBody(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)


class SummaryBody(BaseModel):
    transcript: str = Field(min_length=1, max_length=90000)
    title: str = Field(default="Megbeszélés", max_length=150)
    started_at: str = Field(default="Nincs megadva", max_length=80)


class SpeakerNames(BaseModel):
    names: dict[str, str]


class TenantCreate(BaseModel):
    tenant_id: str
    label: str


class PersonInput(BaseModel):
    external_person_id: str | None = None
    name: str = Field(min_length=1, max_length=200)
    organization: str = Field(default='', max_length=250)
    position: str = Field(default='', max_length=250)
    elected_position: str = Field(default='', max_length=250)


class VoiceMatchInput(BaseModel):
    threshold: float = Field(default=0.88, ge=0.80, le=1.0)
    margin: float = Field(default=0.04, ge=0, le=0.30)


class ApproveVoices(BaseModel):
    approved: dict[str, str]


def require_key(x_api_key: str | None = Header(default=None, alias="X-Api-Key")):
    expected = api_key()
    if len(expected) < 40 or x_api_key is None or not secrets.compare_digest(expected, x_api_key):
        raise HTTPException(status_code=401, detail="Hiányzó vagy érvénytelen X-Api-Key.")


def check_tenant(tenant_id: str, tenant_key: str | None):
    try:
        valid = voice_store.authenticate_tenant(tenant_id, tenant_key)
    except ValueError:
        raise HTTPException(status_code=400, detail='Érvénytelen alkalmazásazonosító.')
    if not valid:
        raise HTTPException(status_code=403, detail='Hibás vagy hiányzó X-Tenant-Key; az alkalmazások adatai elkülönítettek.')


def guard_job_tenant(job_id: str, tenant_key: str | None):
    state = job_state(workdir(job_id))
    tenant_id = state.get('tenant_id')
    if tenant_id:
        check_tenant(tenant_id, tenant_key)
    return state


def workdir(job_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise HTTPException(status_code=404, detail="Ismeretlen azonosító.")
    folder = ROOT / "data" / "jobs" / job_id
    if not folder.is_dir():
        raise HTTPException(status_code=404, detail="Nincs ilyen feladat.")
    return folder


def read_json(folder: Path, filename: str):
    return json.loads((folder / filename).read_text(encoding="utf-8"))


def atomic_write(path: Path, text: str) -> None:
    # Windows alatt os.replace csak létező célfájl mellett is atomikus csere.
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_json(folder: Path, filename: str, value) -> None:
    atomic_write(folder / filename, json.dumps(value, ensure_ascii=False, indent=2))


def patch_job(folder: Path, **changes) -> None:
    with lock:
        state = read_json(folder, "job.json")
        state.update(changes)
        write_json(folder, "job.json", state)


def job_state(folder: Path) -> dict:
    with lock:
        return read_json(folder, "job.json")


def jobs_snapshot() -> list[dict]:
    """Az állapotot azonosítóhoz kötött lemezes job.json fájlokból olvassuk.

    A sor minden felvételét külön tároljuk; nem keverednek össze eredmények.
    """
    result = []
    for file in (ROOT / "data" / "jobs").glob("*/job.json"):
        try:
            result.append(read_json(file.parent, "job.json"))
        except (ValueError, OSError):
            continue
    # Az új munkák sorrendjét a submit alatt kiosztott tartós enqueue_order adja,
    # nem egy fájlírás időpontja (párhuzamos feltöltéskor eltérhet az indítás sorrendje).
    # A régi, számláló nélküli munkák helyét a régi created_at sorrend alapján tartjuk meg.
    return sorted(result, key=lambda j: (
        0 if j.get("enqueue_order") is None else 1,
        j.get("created_at_utc", "") if j.get("enqueue_order") is None else j["enqueue_order"],
        j.get("id", "")))


def all_jobs_snapshot() -> list[dict]:
    jobs = jobs_snapshot()
    for file in (ROOT / 'data' / 'tenants').glob('*/enrollments/*/job.json'):
        try:
            jobs.append(read_json(file.parent, 'job.json'))
        except (OSError, ValueError):
            continue
    return sorted(jobs, key=lambda j: (
        0 if j.get('enqueue_order') is None else 1,
        j.get('created_at_utc', '') if j.get('enqueue_order') is None else j['enqueue_order'],
        j.get('id', '')))


def queue_snapshot() -> dict:
    jobs = all_jobs_snapshot()
    active = [j for j in jobs if j.get("status") == "running"]
    waiting = [j for j in jobs if j.get("status") == "queued"]
    return {"active_job_id": active[0]["id"] if active else None,
            "active_jobs": len(active), "queued_jobs": len(waiting),
            "capacity": 8, "max_parallel_audio_jobs": 1,
            "waiting_ids": [j["id"] for j in waiting],
            "note": "Egyidejű feltöltés megengedett, tényleges AI-munka egyszerre csak egy feladathoz."}


def enriched_job(job_id: str) -> dict:
    """Visszaadja az egyéni feladat állapotát és a FELADAT ELŐTT állók számát.

    A queue_position a várakozók közti, 1-től induló pozíció (régi klienseknek).
    A jobs_ahead viszont az összes ELŐTTE levő munkát számolja, a futót is.
    Például 1 running + 1 queued előtte -> jobs_ahead=2, position_overall=3.
    Az állapot pillanatkép; indulás/befejezés pillanatában az érték megváltozhat.
    """
    state = job_state(workdir(job_id))
    current_status = state.get("status")
    if current_status == "queued":
        snapshot = queue_snapshot()
        pending = snapshot["waiting_ids"]
        waiting_ahead = pending.index(job_id) if job_id in pending else None
        active_ahead = snapshot["active_jobs"]
        # Ha a feltöltés közben épp átmenet történt, ne állítsunk be hamis pozíciót.
        jobs_ahead = waiting_ahead + active_ahead if waiting_ahead is not None else None
        state["queue_position"] = waiting_ahead + 1 if waiting_ahead is not None else None
        state["queue_ahead"] = waiting_ahead  # v1.5 kompatibilis: CSAK várakozók
        state["waiting_ahead"] = waiting_ahead
        state["jobs_ahead"] = jobs_ahead  # a felhasználói kijelzésben EZ használandó
        state["queue_position_overall"] = jobs_ahead + 1 if jobs_ahead is not None else None
        state["active_jobs"] = active_ahead
        state["total_waiting_jobs"] = snapshot["queued_jobs"]
        if jobs_ahead is not None:
            state["queue_message"] = (f"Sorban áll: {jobs_ahead} feldolgozás van előtted."
                                      if jobs_ahead else "A következő induló feldolgozás a tiéd.")
        else:
            state["queue_message"] = "A sor pillanatnyi állapota változik; lekérdezés megismételhető."
    elif current_status == "running":
        state.update(queue_position=None, queue_ahead=None, waiting_ahead=0,
                     jobs_ahead=0, queue_position_overall=1, active_jobs=1,
                     total_waiting_jobs=None, queue_message="A te hanganyagodat dolgozzuk fel.")
    else:
        state.update(queue_position=None, queue_ahead=None, waiting_ahead=None,
                     jobs_ahead=None, queue_position_overall=None, active_jobs=None,
                     total_waiting_jobs=None, queue_message=None)
    return state


def percent_from_event(stage: str, event: dict) -> int | None:
    """A Whisper-arány a ténylegesen végigszámolt hangmásodperceken alapul.

    A pyannote belső progress lépésenként ismert, de az egész pipeline
    időigénye nem, így nem számítunk belőle kitalált teljes százalékot.
    """
    if stage == "diarization" or stage not in STAGE_BANDS:
        return None
    fraction = event.get("percent")
    if not isinstance(fraction, (int, float)) or not 0 <= fraction <= 100:
        return None
    low, high = STAGE_BANDS[stage]
    return round(low + (high - low) * fraction / 100)


def _terminate_child(child) -> None:
    if child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def launch_worker(job_id: str, audio_name: str, diarize: bool, summarize: bool,
                  cancel_event: threading.Event) -> None:
    """Külön megszakítható Python-gyermekfolyamat, átlátható JSONL státuszokkal.

    A modell számolhat percekig egy chunkon: a watchdog 2 mp-enként
    ellenőrzi az időkeretet és a cancel gombot, ezért nem fagy az API.
    """
    folder = ROOT / "data" / "jobs" / job_id
    cfg = config()
    cmd = [sys.executable, "-u", "-m", "offlineai.worker", "--job-id", job_id, "--audio", audio_name]
    if diarize:
        cmd.append("--diarize")
    if summarize:
        cmd.append("--summarize")
    environment = os.environ.copy()
    environment.update({"OFFLINEAI_HOME": str(ROOT), "HF_HUB_OFFLINE": "1",
                        "TRANSFORMERS_OFFLINE": "1", "HF_DATASETS_OFFLINE": "1",
                        "PYTHONPATH": str(ROOT / "app"), "OLLAMA_NO_CLOUD": "1",
                        # A Windows pipe alapértelmezett cp125x kódolása helyett
                        # a worker stdout/stderr UTF-8. A worker JSONL-emittere
                        # emellett ASCII-safe JSON-t küld, kettős védelemként.
                        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8:backslashreplace",
                        "PYTHONUNBUFFERED": "1"})
    events: queue.Queue[dict] = queue.Queue()
    logfile = folder / "worker.stderr.log"
    started = time.monotonic()
    stage_started = started
    stage = "starting"
    last_report = 0.0
    last_token_report = 0.0
    completed = False
    last_error = ""
    with logfile.open("a", encoding="utf-8") as stderr:
        child = subprocess.Popen(cmd, cwd=str(ROOT), env=environment, stdout=subprocess.PIPE,
                                 stderr=stderr, text=True, encoding="utf-8", errors="replace", bufsize=1)

        def read_stdout():
            try:
                for raw in child.stdout:
                    try:
                        events.put(json.loads(raw))
                    except ValueError:
                        events.put({"event": "error", "message": "Sérült JSON worker-esemény"})
            finally:
                events.put({"event": "_closed"})

        reader = threading.Thread(target=read_stdout, daemon=True, name="omega-worker-reader")
        reader.start()
        try:
            while True:
                now = time.monotonic()
                elapsed = now - started
                stage_elapsed = now - stage_started
                if cancel_event.is_set():
                    raise InterruptedError("A feladatot felhasználói kérésre leállítottuk.")
                if elapsed > float(cfg["job_timeout_sec"]):
                    raise TimeoutError(f"Teljes feladat időtúllépés: {elapsed:.0f} másodperc.")
                key = STAGE_TIMEOUT_KEYS.get(stage)
                if key is not None and stage_elapsed > float(cfg[key]):
                    raise TimeoutError(f"{stage} szakasz időtúllépés: {stage_elapsed:.0f} mp. "
                                       f"A {logfile} és a /v1/hardware ellenőrizhető.")
                if now - last_report >= 2.0:
                    current = job_state(folder)
                    changes = {"elapsed_sec": round(elapsed), "stage_elapsed_sec": round(stage_elapsed),
                               "worker_pid": child.pid, "last_heartbeat_utc": datetime.now(timezone.utc).isoformat()}
                    since_progress = current.get("last_progress_monotonic_sec")
                    if isinstance(since_progress, (int, float)):
                        # Csak azt jelezzük, ha a worker az utóbbi időben nem jelentett előrelépést.
                        changes["waiting_for_model"] = (elapsed - since_progress > float(cfg["stall_warning_sec"]))
                    patch_job(folder, **changes)
                    last_report = now
                try:
                    event = events.get(timeout=0.6)
                except queue.Empty:
                    if child.poll() is not None and events.empty():
                        break
                    continue
                kind = event.get("event")
                if kind == "_closed":
                    break
                if kind == "error":
                    last_error = str(event.get("message", "Ismeretlen worker hiba"))[:900]
                    continue
                if kind == "done":
                    completed = True
                    continue
                if kind == "transcript_done":
                    patch_job(folder, has_transcript=True, message="Átirat elkészült")
                    continue
                if kind == "summary_done":
                    patch_job(folder, has_summary=True, summary_generated_chars=int(event.get("chars", 0)),
                              message="Qwen összesítő elkészült")
                    continue
                if kind == "summary_token":
                    # A child delta-fájlt 0.2 mp-enként írja. Nem írjuk át a job.json-t
                    # minden tokennél, mert a sok I/O maga lassítaná a Qwent.
                    if now-last_token_report >= 0.3:
                        patch_job(folder, summary_generated_chars=int(event.get("chars", 0)),
                                  message="Qwen folyamatosan generálja az összesítőt")
                        last_token_report = now
                    continue
                if kind in {"stage", "progress"}:
                    received = str(event.get("stage", stage))
                    if received in STAGE_TIMEOUT_KEYS and received != stage:
                        stage, stage_started = received, time.monotonic()
                    state = {"stage": received, "stage_detail": str(event.get("detail", ""))[:300],
                             "stage_percent": event.get("percent"),
                             "message": str(event.get("detail", "Feldolgozás"))[:250],
                             "last_progress_utc": datetime.now(timezone.utc).isoformat(),
                             "last_progress_monotonic_sec": round(elapsed, 2),
                             "waiting_for_model": False}
                    for field in ("completed_seconds", "total_seconds", "chunks_completed", "chunks_total",
                                  "stage_units_completed", "stage_units_total", "device", "speaker_turns"):
                        if field in event:
                            state[field] = event[field]
                    # diarization stage_percent kizárólag AKTUÁLIS belső művelet számlálója.
                    if received == "diarization" and isinstance(event.get("stage_units_total"), (int, float)):
                        total = event["stage_units_total"]
                        done = event.get("stage_units_completed")
                        state["stage_percent"] = round(100 * done / total, 2) if total and isinstance(done, (int, float)) else None
                    overall = percent_from_event(received, event)
                    if received == "whisper_done":
                        overall = STAGE_BANDS["whisper"][1]
                    elif received == "diarization_done":
                        overall = STAGE_BANDS["diarization"][1]
                    elif received == "summary":
                        overall = STAGE_BANDS["summary"][0]
                    if overall is not None:
                        state["progress"] = max(job_state(folder).get("progress", 0), overall)
                    patch_job(folder, **state)
            code = child.wait(timeout=10)
            if code != 0 or not completed:
                raise RuntimeError(last_error or f"Worker hibával kilépett ({code}). Napló: {logfile}")
        finally:
            _terminate_child(child)
            reader.join(timeout=3)


def process_audio(job_id: str, audio_name: str, diarize: bool, summarize: bool):
    folder = ROOT / "data" / "jobs" / job_id
    flag = _cancel_events.setdefault(job_id, threading.Event())
    try:
        # A queued -> running valtas a cancel kezelessel azonos zar alatt tortenik.
        # Igy a ket muvelet nem irhatja felul egymas allapotat.
        with lock:
            if flag.is_set() or job_state(folder)["status"] == "canceled":
                return
            patch_job(folder, status="running", progress=1, stage="starting", stage_percent=None,
                      started_processing_utc=datetime.now(timezone.utc).isoformat(),
                      message="AI feldolgozás elindult")
        launch_worker(job_id, audio_name, diarize, summarize, flag)
        patch_job(folder, status="completed", progress=100, stage="completed", stage_percent=100,
                  has_transcript=(folder / "transcript.txt").is_file(),
                  has_summary=(folder / "summary.txt").is_file(),
                  finished_at_utc=datetime.now(timezone.utc).isoformat(), message="Feldolgozás kész")
    except InterruptedError as exc:
        patch_job(folder, status="canceled", stage="canceled", message=str(exc),
                  finished_at_utc=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        patch_job(folder, status="failed", stage="failed", message=f"{type(exc).__name__}: {exc}"[:1000],
                  finished_at_utc=datetime.now(timezone.utc).isoformat())
    finally:
        (folder / "working.wav").unlink(missing_ok=True)
        with lock:
            _cancel_events.pop(job_id, None)
            _submitted.discard(job_id)
            was_released_early = job_id in _slots_released_early
            _slots_released_early.discard(job_id)
            if not was_released_early:
                slots.release()


def _submit(job_id: str, audio_name: str, diarize: bool, summarize: bool) -> None:
    # A kiosztott sorindex és az executorba beállítás EGY kritikus szakaszban fut.
    # Ez biztosítja, hogy a külső /jobs/{id} sorpozíció egyezzen a valódi futási renddel.
    with lock:
        if job_id in _submitted:
            return
        folder = ROOT / "data" / "jobs" / job_id
        state = job_state(folder)
        if state.get("enqueue_order") is None:
            previous = [int(j["enqueue_order"]) for j in all_jobs_snapshot()
                        if isinstance(j.get("enqueue_order"), int)]
            patch_job(folder, enqueue_order=max(previous, default=0) + 1)
        _submitted.add(job_id)
        _cancel_events.setdefault(job_id, threading.Event())
        try:
            executor.submit(process_audio, job_id, audio_name, diarize, summarize)
        except Exception:
            _submitted.discard(job_id)
            _cancel_events.pop(job_id, None)
            raise


def _recover_jobs() -> None:
    """Újraindításkor a várakozókat ismét sorba tesszük; a futót nem folytatjuk félig."""
    global _recovered
    with lock:
        if _recovered:
            return
        _recovered = True
        for state in all_jobs_snapshot():
            if state.get('kind') == 'voice_enrollment':
                folder = voice_enrollment_folder(state['tenant_id'], state['id'])
                if state.get('status') == 'running':
                    patch_job(folder, status='failed', stage='interrupted',
                              message='A gép leállt hangminta-bejegyzés közben; töltsd fel újra.')
                elif state.get('status') == 'queued':
                    # A hangminta-újraküldéshez ellenőrizhető jóváhagyás szükséges.
                    patch_job(folder, status='failed', stage='interrupted',
                              message='A szolgáltatás újraindult; a hangminta ismételt jóváhagyása szükséges.')
                continue
            folder = ROOT / "data" / "jobs" / state["id"]
            if state.get("status") == "running":
                patch_job(folder, status="failed", stage="interrupted", message=
                          "A szolgáltatás leállt munka közben; az eredeti hang megmaradt. Indíts új feladatot.")
            elif state.get("status") == "queued":
                audio_name = str(state.get("audio_name", ""))
                if not (folder / audio_name).is_file():
                    patch_job(folder, status="failed", message="Sorba állított hangfájl nem található")
                    continue
                if not slots.acquire(blocking=False):
                    patch_job(folder, status="failed", message="Újraindítás után a várakozó sor kapacitása megtelt")
                    continue
                _submit(state["id"], audio_name, bool(state.get("diarization_requested")),
                        bool(state.get("summary_requested")))


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _sse_response(generator):
    return StreamingResponse(generator, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


def _qwen_sse(prompt: str):
    try:
        yield _sse("start", {"model": config()["qwen_model"]})
        for token in qwen_stream(prompt):
            yield _sse("token", {"delta": token})
        yield _sse("done", {"ok": True})
    except Exception as exc:
        yield _sse("error", {"message": str(exc)[:500]})


@app.on_event("startup")
def startup():
    ensure_folders()
    _recover_jobs()


@app.get("/", tags=["Állapot"])
def root():
    return {"service": "OmegaAI", "api_version": "v1", "swagger": "/docs"}


@app.get("/health/live", tags=["Állapot"])
def health():
    return {"status": "running", "version": __version__, "note": "Nem modellteszt."}


@app.get("/v1/health/ready", dependencies=[Depends(require_key)], tags=["Állapot"])
def health_ready():
    return status()


@app.get("/v1/models", dependencies=[Depends(require_key)], tags=["Állapot"])
def models():
    return status()


@app.get("/v1/hardware", dependencies=[Depends(require_key)], tags=["Állapot"])
def hardware():
    return hardware_report()


@app.get("/v1/queue", dependencies=[Depends(require_key)], tags=["Feladatsor"])
def queue_overview():
    return queue_snapshot()


@app.post("/v1/chat", dependencies=[Depends(require_key)], tags=["Szöveg"])
async def chat(body: ChatBody):
    try:
        return {"model": config()["qwen_model"], "answer": await run_in_threadpool(qwen, body.prompt)}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/chat/stream", dependencies=[Depends(require_key)], tags=["Szöveg"])
def chat_stream(body: ChatBody):
    """POST + X-Api-Key. SSE-t HttpClient/fetch streaming API-val olvass; EventSource GET nem jó."""
    return _sse_response(_qwen_sse(body.prompt))


@app.post("/v1/summaries", dependencies=[Depends(require_key)], tags=["Szöveg"])
async def summarize(body: SummaryBody):
    try:
        answer = await run_in_threadpool(engines.summary, body.transcript, body.title, body.started_at)
        return {"summary": answer}
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/v1/summaries/stream", dependencies=[Depends(require_key)], tags=["Szöveg"])
def summarize_stream(body: SummaryBody):
    """Hosszú átirat részösszesítője stage eseményként, végső szöveg tokenenként érkezik."""
    def generate():
        updates: queue.Queue[tuple[str, dict]] = queue.Queue(maxsize=1000)
        def work():
            try:
                answer = engines.summary(body.transcript, body.title, body.started_at,
                    on_progress=lambda label, n, count: updates.put(("stage", {"step": label, "done": n, "total": count})),
                    on_token=lambda delta: updates.put(("token", {"delta": delta})))
                updates.put(("done", {"ok": True, "length": len(answer)}))
            except Exception as exc:
                updates.put(("error", {"message": str(exc)[:500]}))
        threading.Thread(target=work, daemon=True).start()
        yield _sse("start", {"model": config()["qwen_model"]})
        while True:
            try:
                kind, message = updates.get(timeout=15)
            except queue.Empty:
                yield ": alive\n\n"
                continue
            yield _sse(kind, message)
            if kind in ("done", "error"):
                return
    return _sse_response(generate())


@app.post("/v1/audio/jobs", status_code=202, dependencies=[Depends(require_key)], tags=["Hang"])
async def new_audio(audio: UploadFile = File(...), title: str = Form("Megbeszélés"),
                    started_at: str = Form("Nincs megadva"),
                    diarize: bool = Form(False), summarize: bool = Form(True),
                    tenant_id: str | None = Form(None),
                    x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    if tenant_id:
        check_tenant(tenant_id, x_tenant_key)
    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in AUDIO_EXT:
        raise HTTPException(status_code=400, detail="Nem támogatott hangkiterjesztés")
    if not title.strip() or len(title) > 150 or len(started_at) > 80:
        raise HTTPException(status_code=400, detail="Hibás cím vagy dátum")
    if not slots.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="A központi sor megtelt; próbáld újra később.")
    folder = None
    try:
        job_id = uuid4().hex
        folder = ROOT / "data" / "jobs" / job_id
        folder.mkdir(parents=True, exist_ok=False)
        name = "audio" + suffix
        limit = int(config()["max_audio_mb"]) * 1024 * 1024
        size = 0
        with (folder / name).open("wb") as out:
            while data := await audio.read(1024 * 1024):
                size += len(data)
                if size > limit:
                    raise HTTPException(status_code=413, detail="A hangfájl túl nagy.")
                out.write(data)
        if not size:
            raise HTTPException(status_code=400, detail="Üres hangfájl")
        write_json(folder, "job.json", {
            "id": job_id, "status": "queued", "stage": "queued", "progress": 0,
            "stage_percent": None, "stage_detail": "A feltöltés kész, feldolgozásra vár",
            "message": "Sorban áll", "audio_name": name, "bytes": size,
            "title": title.strip(), "started_at": started_at, "tenant_id": tenant_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "original_filename": Path(audio.filename or "").name,
            "diarization_requested": diarize, "summary_requested": summarize,
            "has_transcript": False, "has_summary": False,
            "completed_seconds": 0, "total_seconds": None,
            "chunks_completed": 0, "chunks_total": None,
            "stage_units_completed": None, "stage_units_total": None,
            "device": None, "elapsed_sec": 0,
        })
        _submit(job_id, name, diarize, summarize)
        current = enriched_job(job_id)
        return {"id": job_id, "status": current["status"],
                "poll_url": f"/v1/jobs/{job_id}", "events_url": f"/v1/jobs/{job_id}/events",
                "queue_position": current["queue_position"],
                "jobs_ahead": current["jobs_ahead"],
                "queue_position_overall": current["queue_position_overall"],
                "queue_message": current["queue_message"]}
    except Exception:
        slots.release()
        if folder and folder.is_dir():
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        await audio.close()


@app.get("/v1/jobs/{job_id}", dependencies=[Depends(require_key)], tags=["Feladatsor"])
def get_job(job_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    guard_job_tenant(job_id, x_tenant_key)
    return enriched_job(job_id)


@app.post("/v1/jobs/{job_id}/cancel", dependencies=[Depends(require_key)], tags=["Feladatsor"])
def cancel_job(job_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    guard_job_tenant(job_id, x_tenant_key)
    folder = workdir(job_id)
    current = job_state(folder)
    if current["status"] in TERMINAL:
        return {"id": job_id, "status": current["status"], "already_finished": True}
    with lock:
        flag = _cancel_events.get(job_id)
        if flag:
            flag.set()
        if current["status"] == "queued":
            patch_job(folder, status="canceled", stage="canceled", message="Várakozó munka visszavonva")
            # A felvetel mar nem fog AI-eroforrast igenyelni. Az uj feltoltes
            # azonnal elfoglalhatja a felszabadult sorhelyet; az executorban
            # meg jelen levo fuggvenyhivas kesobb nem szabadithatja fel ujra.
            if job_id not in _slots_released_early:
                _slots_released_early.add(job_id)
                slots.release()
    return {"id": job_id, "status": "cancel_requested" if current["status"] == "running" else "canceled"}


@app.get("/v1/jobs/{job_id}/events", dependencies=[Depends(require_key)], tags=["Feladatsor"])
async def job_events(job_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    guard_job_tenant(job_id, x_tenant_key)
    folder = workdir(job_id)
    async def stream():
        last = None
        chars_sent = 0
        while True:
            current = enriched_job(job_id)
            relevant = {k: v for k, v in current.items() if k not in
                        ("original_filename", "title", "started_at", "created_at_utc")}
            encoded = json.dumps(relevant, ensure_ascii=False, sort_keys=True)
            if encoded != last:
                yield _sse("progress", relevant)
                last = encoded
            filename = folder / "summary.partial.txt"
            if not filename.is_file():
                filename = folder / "summary.txt"
            if filename.is_file():
                text = filename.read_text(encoding="utf-8")
                if len(text) > chars_sent:
                    yield _sse("token", {"delta": text[chars_sent:]})
                    chars_sent = len(text)
            if current["status"] in TERMINAL:
                yield _sse("done", {"status": current["status"], "message": current.get("message")})
                return
            await asyncio.sleep(0.8)
    return _sse_response(stream())


@app.get("/v1/jobs/{job_id}/transcript", dependencies=[Depends(require_key)],
         response_class=PlainTextResponse, tags=["Hang"])
def transcript(job_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    guard_job_tenant(job_id, x_tenant_key)
    path = workdir(job_id) / "transcript.txt"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Az átirat még nincs kész.")
    return path.read_text(encoding="utf-8")


@app.get("/v1/jobs/{job_id}/segments", dependencies=[Depends(require_key)], tags=["Hang"])
def segments(job_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    guard_job_tenant(job_id, x_tenant_key)
    folder = workdir(job_id)
    if not (folder / "segments.json").is_file():
        raise HTTPException(status_code=404, detail="Beszélőszakasz még nincs kész.")
    return read_json(folder, "segments.json")


@app.get("/v1/jobs/{job_id}/summary", dependencies=[Depends(require_key)],
         response_class=PlainTextResponse, tags=["Hang"])
def get_summary(job_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    guard_job_tenant(job_id, x_tenant_key)
    file = workdir(job_id) / "summary.txt"
    if not file.is_file():
        raise HTTPException(status_code=404, detail="Összesítő még nincs kész.")
    return file.read_text(encoding="utf-8")


@app.put("/v1/jobs/{job_id}/speaker-names", dependencies=[Depends(require_key)], tags=["Beszélők"])
def speaker_names(job_id: str, body: SpeakerNames,
                  x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    guard_job_tenant(job_id, x_tenant_key)
    folder = workdir(job_id)
    if job_state(folder)["status"] != "completed":
        raise HTTPException(status_code=409, detail="Előbb várd meg a teljes feldolgozás végét.")
    if not (folder / "segments.json").is_file():
        raise HTTPException(status_code=409, detail="Nincs beszélőszakasz.")
    found = read_json(folder, "segments.json")
    allowed = {s["speaker_id"] for s in found}
    if len(body.names) > 50 or any(k not in allowed or not 1 <= len(v.strip()) <= 80
                                  for k, v in body.names.items()):
        raise HTTPException(status_code=400, detail="Érvénytelen beszélőcímke vagy név")
    write_json(folder, "speaker-names.json", body.names)
    atomic_write(folder / "transcript.txt", engines.transcript_text(found, body.names))
    (folder / "summary.txt").unlink(missing_ok=True)
    patch_job(folder, has_summary=False, message="Beszélőnevek rögzítve; összesítőt frissíts.")
    return {"names": body.names, "transcript_updated": True, "summary_needs_regeneration": True}


@app.post("/v1/jobs/{job_id}/regenerate-summary", dependencies=[Depends(require_key)], tags=["Beszélők"])
async def regenerate(job_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    guard_job_tenant(job_id, x_tenant_key)
    folder = workdir(job_id)
    if job_state(folder)["status"] != "completed":
        raise HTTPException(status_code=409, detail="Csak befejezett feladatra kérhető új összesítő.")
    transcript = folder / "transcript.txt"
    if not transcript.exists():
        raise HTTPException(status_code=409, detail="Nincs kész átirat")
    old = job_state(folder)
    try:
        answer = await run_in_threadpool(engines.summary, transcript.read_text(encoding="utf-8"),
                                         old["title"], old["started_at"])
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    atomic_write(folder / "summary.txt", answer)
    patch_job(folder, has_summary=True)
    return {"summary_updated": True}


@app.post("/v1/voices/enroll", dependencies=[Depends(require_key)], tags=["Hangprofil (jövőbeli)"])
def voice_enroll():
    raise HTTPException(status_code=501, detail="Automatikus személyazonosítás nem része a v1-nek.")


@app.post("/v1/voices/match", dependencies=[Depends(require_key)], tags=["Hangprofil (jövőbeli)"])
def voice_match():
    raise HTTPException(status_code=501, detail="A pyannote beszélőszétválasztás, nem hangprofil-azonosítás.")


# ============== ALKALMAZÁSONKÉNT ELKÜLÖNÍTETT V17 HANGPROFILOK ==============
# A REST-kéréseket KIZÁRÓLAG a hitelesített .NET API továbbíthatja. A tenant
# azonosító önmagában nem jogosultság, ezért minden művelet X-Tenant-Key-t kér.

@app.post('/v1/tenants', dependencies=[Depends(require_key)], tags=['Alkalmazások'])
def create_tenant(body: TenantCreate):
    try:
        return voice_store.provision_tenant(body.tenant_id, body.label)
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc
    except __import__('sqlite3').IntegrityError as exc:
        raise HTTPException(409, detail='Már létezik ez az alkalmazásazonosító.') from exc


@app.get('/v1/tenants', dependencies=[Depends(require_key)], tags=['Alkalmazások'])
def tenants():
    db = voice_store.registry()
    try:
        return [dict(row) for row in db.execute('SELECT tenant_id,label,created_at FROM tenants ORDER BY tenant_id')]
    finally:
        db.close()


@app.post('/v1/tenants/{tenant_id}/persons', dependencies=[Depends(require_key)], tags=['Hangprofilok'])
def save_person(tenant_id: str, body: PersonInput,
                x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    try:
        with voice_store.tenant_db(tenant_id) as db:
            return voice_store.upsert_person(db, **body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc


@app.get('/v1/tenants/{tenant_id}/persons', dependencies=[Depends(require_key)], tags=['Hangprofilok'])
def people(tenant_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    with voice_store.tenant_db(tenant_id) as db:
        return voice_store.list_people(db)


@app.delete('/v1/tenants/{tenant_id}/persons/{person_id}', dependencies=[Depends(require_key)], tags=['Hangprofilok'])
def delete_person(tenant_id: str, person_id: str,
                  x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    with voice_store.tenant_db(tenant_id) as db:
        with db:
            removed = db.execute('DELETE FROM persons WHERE id=?', (person_id,)).rowcount
        if not removed:
            raise HTTPException(404, detail='Nincs ilyen személy.')
    return {'deleted': True, 'voice_samples_deleted': True}


def voice_enrollment_folder(tenant_id: str, enrollment_id: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', enrollment_id):
        raise HTTPException(404, detail='Érvénytelen azonosító.')
    return voice_store.tenant_dir(tenant_id) / 'enrollments' / enrollment_id


def enroll_state(tenant_id: str, enrollment_id: str) -> dict:
    folder = voice_enrollment_folder(tenant_id, enrollment_id)
    if not (folder / 'job.json').is_file():
        raise HTTPException(404, detail='Nincs ilyen hangminta-feldolgozás.')
    state = job_state(folder)
    if state['status'] == 'queued':
        snap = queue_snapshot()
        ahead = snap['waiting_ids'].index(enrollment_id) if enrollment_id in snap['waiting_ids'] else None
        state['jobs_ahead'] = ahead + snap['active_jobs'] if ahead is not None else None
        state['queue_message'] = f"Sorban áll: {state['jobs_ahead']} feldolgozás van előtted." if state['jobs_ahead'] is not None else None
    else:
        state['jobs_ahead'] = 0 if state['status'] == 'running' else None
    return state


def _process_enrollment(tenant_id: str, enrollment_id: str, person_id: str, fname: str,
                        content_type: str, consent_note: str):
    folder = voice_enrollment_folder(tenant_id, enrollment_id)
    audio_path = folder / fname
    try:
        patch_job(folder, status='running', stage='voice_embedding', message='Helyi pyannote hangvektor készül',
                  started_at_utc=datetime.now(timezone.utc).isoformat())
        def on_profile_progress(label, completed, total):
            # Belső pyannote számláló: NEM a teljes időigény százaléka.
            fraction = round(100*completed/total, 1) if total and completed is not None else None
            patch_job(folder, status='running', stage='voice_embedding', step=str(label),
                      stage_percent=fraction, stage_units_completed=completed,
                      stage_units_total=total,
                      message='Hangminta – ' + str(label)[:120])
        vectors, duration = voice_extract.extract_sample(audio_path, on_progress=on_profile_progress)
        with voice_store.tenant_db(tenant_id) as db:
            result = voice_store.store_sample(db, person_id, audio_path.read_bytes(), fname, content_type,
                vectors[voice_store.MODEL], duration, consent_note)
        patch_job(folder, status='completed', stage='completed', progress=100, result=result,
                  message='Hangminta az alkalmazás saját SQLite adatbázisába elmentve.')
    except Exception as exc:
        patch_job(folder, status='failed', stage='failed', message=f'{type(exc).__name__}: {exc}'[:600])
    finally:
        audio_path.unlink(missing_ok=True)
        slots.release()


@app.post('/v1/tenants/{tenant_id}/persons/{person_id}/samples', status_code=202,
          dependencies=[Depends(require_key)], tags=['Hangprofilok'])
async def enroll_voice(tenant_id: str, person_id: str, audio: UploadFile = File(...),
                       consent_confirmed: bool = Form(...), consent_note: str = Form(...),
                       x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    if not consent_confirmed or not 3 <= len(consent_note.strip()) <= 500:
        raise HTTPException(400, detail='A személy igazolt hozzájárulását és rövid leírását rögzíteni kell.')
    with voice_store.tenant_db(tenant_id) as db:
        try:
            voice_store.person_dict(db, person_id)
        except KeyError:
            raise HTTPException(404, detail='Személy nem található.')
    extension = Path(audio.filename or '').suffix.lower()
    if extension not in {'.wav','.mp3','.flac','.m4a','.ogg'}:
        raise HTTPException(400, detail='Hangminta: WAV, MP3, FLAC, M4A vagy OGG szükséges.')
    if not slots.acquire(blocking=False):
        raise HTTPException(429, detail='A hangfeldolgozási sor megtelt.')
    folder = None
    try:
        enrollment_id = uuid4().hex
        folder = voice_enrollment_folder(tenant_id, enrollment_id)
        folder.mkdir(parents=True, exist_ok=False)
        fname = 'sample'+extension
        size = 0
        with (folder / fname).open('wb') as out:
            while content := await audio.read(1024*1024):
                size += len(content)
                if size > 15*1024*1024:
                    raise HTTPException(413, detail='Legfeljebb 15 MB-os hangminta küldhető.')
                out.write(content)
        if size < 100:
            raise HTTPException(400, detail='A hangminta túl rövid vagy üres.')
        with lock:
            sequence = [int(x['enqueue_order']) for x in all_jobs_snapshot()
                        if isinstance(x.get('enqueue_order'), int)]
            write_json(folder, 'job.json', {'id':enrollment_id,'kind':'voice_enrollment',
                'tenant_id':tenant_id,'person_id':person_id,'status':'queued','stage':'queued',
                'progress':0,'message':'Hangminta sorba állítva',
                'enqueue_order':max(sequence, default=0)+1,
                'created_at_utc':datetime.now(timezone.utc).isoformat()})
            executor.submit(_process_enrollment, tenant_id, enrollment_id, person_id, fname,
                            audio.content_type or 'application/octet-stream', consent_note.strip())
        return {**enroll_state(tenant_id, enrollment_id),
                'poll_url':f'/v1/tenants/{tenant_id}/enrollments/{enrollment_id}'}
    except Exception:
        slots.release()
        if folder:
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
        raise
    finally:
        await audio.close()


@app.get('/v1/tenants/{tenant_id}/enrollments/{enrollment_id}', dependencies=[Depends(require_key)], tags=['Hangprofilok'])
def enrollment_status(tenant_id: str, enrollment_id: str,
                      x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    return enroll_state(tenant_id, enrollment_id)


@app.get('/v1/tenants/{tenant_id}/persons/{person_id}/samples', dependencies=[Depends(require_key)], tags=['Hangprofilok'])
def list_voice_samples(tenant_id: str, person_id: str,
                       x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    with voice_store.tenant_db(tenant_id) as db:
        try:
            return voice_store.samples(db, person_id)
        except KeyError:
            raise HTTPException(404, detail='Személy nem található.')


@app.get('/v1/tenants/{tenant_id}/persons/{person_id}/samples/{sample_id}/audio',
         dependencies=[Depends(require_key)], tags=['Hangprofilok'])
def sample_audio(tenant_id: str, person_id: str, sample_id: str,
                 x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    with voice_store.tenant_db(tenant_id) as db:
        row = db.execute('SELECT audio, content_type FROM voice_samples WHERE person_id=? AND sample_id=?',
                         (person_id, sample_id)).fetchone()
        if not row:
            raise HTTPException(404, detail='Nincs ilyen hangminta.')
        return Response(bytes(row['audio']), media_type=row['content_type'],
                        headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})


@app.delete('/v1/tenants/{tenant_id}/persons/{person_id}/samples/{sample_id}',
            dependencies=[Depends(require_key)], tags=['Hangprofilok'])
def remove_voice_sample(tenant_id: str, person_id: str, sample_id: str,
                        x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    with voice_store.tenant_db(tenant_id) as db:
        try:
            return voice_store.delete_sample(db, person_id, sample_id)
        except KeyError:
            raise HTTPException(404, detail='Nincs ilyen hangminta.')


@app.post('/v1/tenants/{tenant_id}/jobs/{job_id}/match', dependencies=[Depends(require_key)], tags=['Beszélőazonosítás'])
def match_speakers(tenant_id: str, job_id: str, body: VoiceMatchInput,
                   x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    state = guard_job_tenant(job_id, x_tenant_key)
    if state.get('tenant_id') != tenant_id:
        raise HTTPException(403, detail='Más alkalmazás hangfeldolgozásához nem férhetsz hozzá.')
    folder = workdir(job_id)
    if state['status'] != 'completed' or not (folder / 'speaker-embeddings.json').is_file():
        raise HTTPException(409, detail='Előbb kész, diarizált feladat szükséges (diarize=true).')
    vectors = read_json(folder, 'speaker-embeddings.json')
    with voice_store.tenant_db(tenant_id) as db:
        result = voice_store.match(db, vectors, threshold=body.threshold, margin=body.margin)
    write_json(folder, 'voice-suggestions.json', result)
    return {'job_id':job_id,'tenant_id':tenant_id,'speakers':result,
            'requires_human_approval':True,'threshold':body.threshold,'margin':body.margin}


@app.post('/v1/tenants/{tenant_id}/jobs/{job_id}/approve', dependencies=[Depends(require_key)], tags=['Beszélőazonosítás'])
def approve_speaker_matches(tenant_id: str, job_id: str, body: ApproveVoices,
                            x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    state = guard_job_tenant(job_id, x_tenant_key)
    if state.get('tenant_id') != tenant_id:
        raise HTTPException(403, detail='Más alkalmazás adata nem módosítható.')
    folder = workdir(job_id)
    if state['status'] != 'completed' or not (folder / 'segments.json').is_file():
        raise HTTPException(409, detail='Befejezett, diarizált feldolgozás szükséges.')
    segments = read_json(folder, 'segments.json')
    allowed = {x['speaker_id'] for x in segments}
    if not body.approved or any(s not in allowed for s in body.approved):
        raise HTTPException(400, detail='Ismeretlen beszélőcímke.')
    with voice_store.tenant_db(tenant_id) as db:
        names = {}
        for speaker, person_id in body.approved.items():
            try:
                names[speaker] = voice_store.person_dict(db, person_id)['name']
            except KeyError:
                raise HTTPException(400, detail='Ismeretlen személyazonosító.')
    return speaker_names(job_id, SpeakerNames(names=names), x_tenant_key=x_tenant_key)


@app.post('/v1/tenants/{tenant_id}/rotate-key', dependencies=[Depends(require_key)], tags=['Alkalmazások'])
def rotate_key(tenant_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    return {'tenant_id': tenant_id, 'tenant_api_key': voice_store.rotate_tenant_key(tenant_id),
            'note': 'A régi kulcs azonnal érvénytelen. Az új csak most jelenik meg.'}


@app.delete('/v1/tenants/{tenant_id}', dependencies=[Depends(require_key)], tags=['Alkalmazások'])
def delete_tenant(tenant_id: str, x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    check_tenant(tenant_id, x_tenant_key)
    # A véletlen adatvesztés megelőzésére aktív hangminta-bejegyzés alatt nem törlünk.
    for state in all_jobs_snapshot():
        if state.get('tenant_id') == tenant_id and state.get('status') in ('queued', 'running'):
            raise HTTPException(409, detail='A tenant egyik feldolgozása még fut vagy várakozik.')
    # A tenant hozzájárulásának visszavonása nem hagyhat historikus
    # hangfelvételt / hangvektort a közös job tárolóban sem.
    import shutil
    history = [ROOT / 'data' / 'jobs' / state['id'] for state in jobs_snapshot()
               if state.get('tenant_id') == tenant_id]
    voice_store.remove_tenant(tenant_id)
    for folder in history:
        if folder.is_dir():
            shutil.rmtree(folder)
    return {'deleted':True, 'tenant_id':tenant_id, 'historical_jobs_deleted':len(history),
            'note':'Profilok, hangminták és ezen tenant feldolgozásai törölve; backupok külön kezelendők.'}


@app.delete('/v1/jobs/{job_id}', dependencies=[Depends(require_key)], tags=['Feladatsor'])
def delete_finished_job(job_id: str,
                        x_tenant_key: str | None = Header(default=None, alias='X-Tenant-Key')):
    current = guard_job_tenant(job_id, x_tenant_key)
    if current.get('status') not in TERMINAL:
        raise HTTPException(409, detail='Futó vagy sorban álló feldolgozás nem törölhető. Előbb cancel szükséges.')
    import shutil
    shutil.rmtree(workdir(job_id))
    return {'deleted':True, 'job_id':job_id, 'audio_and_embeddings_deleted':True}
