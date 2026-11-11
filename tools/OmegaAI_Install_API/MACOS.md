# OmegaAI 1.6 futtatása macOS-en

A csomag Windowsos BAT-fájljai mellett az `inditas-macos.sh` indítja ugyanazt a Python API-t ezen a gépen.

## Indítás

A repó gyökérmappájából:

```sh
./tools/OmegaAI_Install_API/inditas-macos.sh
```

A Swagger a [8768-as porton](http://127.0.0.1:8768/docs) érhető el. Az OmegaAI első induláskor helyben hozza létre a `config/api-key.txt` kulcsfájlt. Ezt a kulcsot a MeetingNotesAPI küldi az OmegaAI-nak. A Blazor alkalmazás a MeetingNotesAPI saját, külön klienskulcsát használja.

## Telepítés másik Macen

Python 3.12 és a PATH-on elérhető FFmpeg szükséges. Az OmegaAI mappájában futtasd:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r app/requirements-api.txt -r app/requirements-ai.txt
HF_HUB_OFFLINE=0 HF_HUB_DISABLE_XET=1 .venv/bin/hf download Systran/faster-whisper-large-v3 --local-dir models/whisper-large-v3
```

A W03-hoz elegendő a Whisper. A Swaggerben a `POST /v1/audio/jobs` kérésnél állítsd a `diarize` és `summarize` mezőket `false` értékre. A MeetingNotesAPI Swaggerében ugyanezeket a kapcsolókat a `POST /api/meetings` kérésben találod.

A beszélők elkülönítéséhez a [pyannote modelloldalán](https://huggingface.co/pyannote/speaker-diarization-community-1) el kell fogadni a hozzáférési feltételeket, majd a letöltéshez saját Hugging Face tokent kell megadni a `HF_TOKEN` változóban. Ha hozzáférsz a modellhez, az OmegaAI mappájából futtasd:

```sh
HF_HUB_OFFLINE=0 HF_HUB_DISABLE_XET=1 PYTHONPATH=app .venv/bin/python app/prepare_models.py
```

Az összefoglaláshoz futó helyi Ollama és `qwen3:8b` modell szükséges.
