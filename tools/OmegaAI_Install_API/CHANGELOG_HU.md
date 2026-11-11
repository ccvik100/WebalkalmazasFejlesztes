## v1.6.0 – 2026. november 8. – Windows UTF-8 javítás (teljes kiadás)

- A `worker.py` JSONL-es állapotüzenetei ASCII-biztos `ensure_ascii=True` kódolást használnak; magyar `ő` és `ű` betűk is hiba nélkül átadhatók a szülőfolyamatnak.
- A `main.py` külön UTF-8 környezetet állít be az AI-gyermekfolyamat indításakor.
- A `setup/Start.ps1` és `03_INDITAS.bat` a fő REST-folyamat Python-kódolását is egységesítik.
- Új `tests/test_utf8_worker.py` regressziós teszt szándékosan régi Windows-kódolást szimulál.
- A fix a `UnicodeEncodeError: 'charmap' codec can't encode character '\u0151'` hibát célozza.
- Nem módosulnak a helyi Whisper/pyannote/Qwen modellek, a SQLite adatok és a meglévő API-kulcsok.
- A Windowsos, valós hanggal végzett teljes inferencia a célgépen ellenőrzendő.

## v1.5.1 – sorban előtted levők pontos számlálása (2026-11-08)

- Átadás előtti javítás: várakozó feladat lemondása azonnal felszabadít egy sorhelyet, duplán nem szabadítja fel.
- A `05_TEST_MP3.bat` a várakozáskor a `jobs_ahead` mezőt mutatja, futáskor a pontos szakaszállapotot.
- Új SSE- és sorhely-regressziós tesztek (44/44 teszt).

- Új `jobs_ahead` és `queue_position_overall` a POST audio válaszban, GET job állapotban és SSE progress eseményben.
- `jobs_ahead` **a futó munkát is beleszámolja**, nem csak a várakozókat. `queue_position` továbbra is csak a várakozók között értendő.
- `queue_message`: például „Sorban áll: 2 feldolgozás van előtted.”; folyamat indulásakor külön üzenet.
- Az executorba helyezés és a tartós `enqueue_order` kiosztása zárolva történik, hogy a feltöltések sorrendje és a feldolgozási sor egyezzen.
- 10_TEST_HAROM_FELTOLTES és 13_JOB_ALLAPOT már kiírja a sorban előtted állók számát, utána a szakasz progresszt.
- A teljes Word-dokumentáció frissült. Automatizált teszt: sorban álló (2 előtte) és futó állapot.

## v1.5.0 – 2026. november 8. – sorosított feldolgozás, folyamatos progress és stream

- A régi egyszeri 25%-os Whisper-állapot helyett chunk/hangidő-alapú tényleges előrehaladás.
- pyannote ProgressHook belső lépések + completed/total (nem kitalált teljes százalék).
- Külön Python worker, teljes és szakaszos watchdog időkorlát, folyamatos heartbeat és cancel.
- 1 egyidejű audio worker + 8 várakozó/futó kapacitás, sorpozíció, restart után várakozó jobok visszaállítása.
- POST /v1/chat/stream, POST /v1/summaries/stream, GET /v1/jobs/{id}/events; Qwen delta tokenek SSE.
- GET /v1/queue, GET /v1/hardware, POST /v1/jobs/{id}/cancel.
- CPU/GPU választás, auto fallback, modellfájlok és 11434 Ollama megtartása.
- A README és a 30 oldalas, egységes Word-kézikönyv frissítve; 10–13 BAT-tesztek.
- A hangdekóder továbbra is közvetlen PCM16/WAV chunk feldolgozást használ; av==18.1.0 pin.
- A teljes AI-inferencia és PowerShell 5.1 Windowsos futása célgépen ellenőrzendő.

## v1.3.0 – 2026-11-08 – valodi hang feldolgozasi javitas

- Ismert faster-whisper 1.2.1 / PyAV 19 `metadata_errors` inkompatibilitas kezelve.
- Az FFmpeg-bol erkezo 16 kHz/mono/PCM16 WAV a modellhez kozvetlen NumPy `float32` mintakent jut (nem a PyAV dekodolja).
- A tiszta INSTALL kovethetosegeert `av==18.1.0` fuggoseg rogzitesre kerult.
- Uj PCM-bemenet regresszios tesztek, 09_JAVITAS_HANGDEKODER.bat egyszeri hotfix.
- Ujra nem tolti le a Whisper, pyannote, Qwen modelleket; hotfix soran azokat nem is erinti.
- Teljes Windowsos MP3-feldolgozas meg a celgepen igazolando.

## v1.2 dokumentációs egyesítés (2026-11-08)

- A két régi, egymásnak ellentmondó Word-kézikönyv helyett egyetlen végleges v1.2 kézikönyv készült.
- A telepítő az egyetlen végleges DOCX-et másolja a C:\OmegaAI mappába.
- A diarizációs BAT-teszt a segments.json fájlt is menti a teszt eredménykönyvtárába.
- Az FFmpeg hiányáról szóló hibaüzenetben a régi C:\OfflineAI útvonal javítva.

## v1.2 - 2026-11-08 - Python CHECK javitas

- A `01_TELEPITES.bat CHECK` Windows PowerShell 5.1 alatt `File "<string>", line 1` hibat okozo `python -c` vizsgalata megszunt.
- Uj `setup/ProbePython.py` kulon ellenorzi a Python 3.12 + 64 bit kombinaciot.
- `Install.ps1` most mar a Python exe + argumentum-prefixet egy egyertelmu objektumban adja tovabb az izolalt virtualis kornyezet letrehozasahoz.
- A `C:\OmegaAI\models\ollama` es az osszes mar letezo modell, felvetel es API-kulcs erintetlen.
- A Linuxban futtatott tesztek nem igazoljak a Windowsos telepites vegponttol vegpontig mukodeset.

# OmegaAI (OfflineAI REST) változásnapló

## 1.1.0 – 2026-11-08 – a meglévő OmegaAI-környezethez igazítva

- Alapértelmezett gyökér: `C:\OmegaAI` a korábbi `C:\OfflineAI` helyett.
- Az új szolgáltatás változatlanul `127.0.0.1:8768` címen fut; az Ollama az **existing** `127.0.0.1:11434` porton.
- A Qwen3:8b modellt a már létező `C:\OmegaAI\models\ollama` tárolóból a futó Ollama szolgálja ki. Nincs külön 11435-ös példány, nincs új Qwen-letöltés.
- Az INSTALL és az indítás minden alkalommal ellenőrzi a 11434-es modelllistát, és célzott hibát ad, ha a Qwen hiányzik.
- A telepítő az `app`, `setup`, BAT-ok és dokumentáció elemeit a `C:\OmegaAI` alá másolja; meglévő modellek, felvételek és API-kulcs érintetlenek.
- Régi portbeállítás esetén a `settings.json` előzetes mentéssel migrálható.
- A BAT fájlok BOM nélküliek. A PowerShell 5.1 szkriptek UTF-8 BOM-mal készültek, pontosan egy BOM-mal.
- Friss magyar API- és szervertelepítési dokumentáció, Word-kézikönyv és tesztek.
- Valódi Windowsos telepítés, modellbetöltés és MP3-inferencia még célgépen igazolandó.

## 1.0.0

- Helyi REST API, Whisper Large-v3, pyannote Community-1, Qwen3:8b, kézi beszélőnév-hozzárendelés.
- A hangprofil-alapú automatikus személyazonosítás nincs megvalósítva: a végpontok 501-et adnak.

## v1.6.0 – V17 alapú, elkülönített SQLite hangprofilok

- Tenant-azonosító + külön alkalmazáskulcs; tenantonként privát SQLite `voices.sqlite3`.
- Személyek: saját külső SQLite ID, név, szervezet, pozíció, választott/tisztségbeli pozíció.
- Legfeljebb húsz, egyértelmű hozzájárulással tárolt 3–90 mp-es hangminta/személy;
  eredeti hang BLOB és pyannote-vektor SQLite-ban, centroid normalizálva.
- Belső egyfeldolgozós sorba kerülnek a hangminták is; külön status/progress REST.
- A diarizációban kinyert Community-1 hangvektorokat privát jobfájl tárolja;
  később ugyanazon tenant profiltárával javasolható személy, manuális jóváhagyással.
- Hangminták, személyek, jobok, tenantok törlési végpontjai; tenant kulcsforgatás.
- A V17 eredeti SQLite adatállományát nem másoljuk át automatikusan, és a
  TitaNet opcionális vektorait sem állítjuk automatikusan működőnek.
- A korábbi API, Qwen SSE, Whisper/pyannote progress, központi sor és teszt-BAT-ok megmaradnak.
- Modellek, konfigurációk és korábbi munkaállományok frissítéskor megőrzendők.
- Windowsos valódi vektor- és hangazonosítás még célgépi ellenőrzést igényel.
