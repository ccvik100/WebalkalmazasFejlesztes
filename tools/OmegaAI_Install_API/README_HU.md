# OmegaAI v1.6.0 – központi, teljesen helyi REST AI-szolgáltatás

> **2026-11-08, v1.6 UTF-8 javítás:** A korábbi Whisper utáni magyar ékezetes
> állapotüzenetek Windows alatt `UnicodeEncodeError` hibát okozhattak. A javítás
> már része ennek a **teljes** csomagnak. A `C:\OmegaAI` meglévő modelljei
> és adatbázisai megmaradnak. Részletek: `docs/UTF8_JAVITAS_FRISSITES_HU.md`.

**Célhely:** `C:\OmegaAI` · **Ollama:** `http://127.0.0.1:11434` · **OmegaAI API:** `http://127.0.0.1:8768` · **Swagger:** `http://127.0.0.1:8768/docs`

A ZIP forrásokat és telepítőket tartalmaz, **nem a több GB-os modellfájlokat**. A telepítő a meglévő `C:\OmegaAI\models\ollama`, Whisper- és pyannote-állományokat, a titkos API-kulcsot és a felvételi eredményeket megőrzi. A már működő `qwen3:8b`-t nem tölti le újra. A modell- és hangfájlok nem kerülnek az IIS `wwwroot` alá.

## Gyors frissítés működő v1.2/v1.3 telepítésről

1. Állítsd le a korábbi `03_INDITAS.bat` ablakát (Ctrl+C). Ne töröld a `C:\OmegaAI` mappát.
2. Csomagold ki az új ZIP-et **másik** könyvtárba, nyisd meg a csomag `OmegaAI` mappáját PowerShellben.
3. Futtasd sorban:

```powershell
.\08_MEGLEVO_OLLAMA_ELLENORZES.bat
.\01_TELEPITES.bat CHECK
.\01_TELEPITES.bat INSTALL
.\02_ELLENORZES.bat DEEP
.\03_INDITAS.bat
```

4. A `03_INDITAS` ablakot hagyd nyitva. Második PowerShellben, ugyanezen csomagmappából:

```powershell
.\11_TEST_QWEN_STREAM.bat
.\12_CPU_GPU_DIAGNOSZTIKA.bat
.\05_TEST_MP3.bat "C:\Hangok\teszt.mp3"
.\06_TEST_BESZELOK.bat "C:\Hangok\teszt.mp3"
# Sorvizsgálathoz egy rövid (5–20 mp) hangmintával:
.\10_TEST_HAROM_FELTOLTES.bat "C:\Hangok\rovid.mp3"
# A kapott valós ID-vel:
.\13_JOB_ALLAPOT.bat "<32 hex karakteres job ID>"
```

**PowerShellben a helyi BAT előtt ` .\ ` előtag kell**, például `.\01_TELEPITES.bat CHECK`.

## Mi változott v1.5.1-ben?

- A felhasználó a sorban állásnál már a várakozó és az aktív munkák teljes számát látja.
- Várakozó feladat visszavonásakor a sorhely azonnal felszabadul, a későbbi worker nem számolhatja el másodszor.
- A 05_TEST_MP3.bat várakozáskor is kijelzi az előtted álló munkák számát.


- 1 feldolgozó worker, maximum 8 sorba fogadott felvétel; három felhasználó egyszerre feltölthet, a munkák sorban indulnak.
- A **`jobs_ahead`** mező a már futó munkát **is** beleszámolja az előttünk állók számába. `queue_position` továbbra is csak a várakozók között elfoglalt, 1-től induló sorszám (régi kliensek). A `queue_position_overall` az összes sorban levő között elfoglalt hely. Példa: 1 futó + 1 várakozó előttünk = `jobs_ahead: 2`, `queue_position_overall: 3`.
- `GET /v1/jobs/{id}` és `GET /v1/jobs/{id}/events` a személyre szabott sorhelyzetet adja; az új BAT-tesztek ugyanezt jelenítik meg. A leendő .NET API-nak a bejelentkezett felhasználó jogosultságait ehhez külön ellenőriznie kell.
- Valódi Whisper hangidő/chunk előrehaladás, szakasz- és teljes százalék külön értelmezve.
- Pyannote belső lépés- és darabszámlálók; nem állítunk kitalált teljes százalékot.
- Időkorlát, eltelt idő, worker heartbeat, explicit megszakítás.
- CPU/GPU környezetellenőrzés és `auto` módban CPU fallback betöltés/feldolgozás közben.
- Qwen tokenfolyam (SSE) önálló `/v1/chat/stream`, `/v1/summaries/stream` és jobhoz kötött `/v1/jobs/{id}/events` végpontokon.
- A `/v1/queue`, `/v1/jobs/{id}/cancel`, `/v1/hardware` új végpontok; a régi `/v1` API megmaradt.

## Biztonsági modell

A FastAPI csak `127.0.0.1:8768`-on figyel, az Ollama helyben `127.0.0.1:11434`-en. `X-Api-Key` szükséges minden `/v1/*` kéréshez. A későbbi nyilvános .NET 10 API az IIS-en, HTTPS alatt, végfelhasználói hitelesítéssel és job-jogosultságellenőrzéssel szolgálja ki a Blazor, HTML5, Kotlin és MAUI klienseket. **Ne tedd a belső kulcsot a mobilalkalmazásba vagy JavaScriptbe.**

## Dokumentáció

Az egyetlen egységes, szerkeszthető Word-kézikönyv:

`OmegaAI_v1_5_1_TELJES_Telepitesi_Tesztelesi_API_Kezikonyv.docx`

További rövid, szöveges API-útmutató: `docs/API_HASZNALAT_HU.md`, változásnapló: `CHANGELOG_HU.md`.

## Mit igazolnak a tesztek?

A `tests/` Python-tesztek modellhelyettesítéssel ellenőrzik a sor-kezelést, az HTTP-szerződést, a Whisper-chunkolást, a pyannote hookot, a Qwen SSE-eseménysorrendet és az időkorlátot. **Ez nem bizonyítja a tényleges Windowsos Whisper/pyannote/Qwen inferenciát.** A modelltesztet a célgépen a `DEEP`, a valódi MP3, beszélő, stream, sor és CPU/GPU BAT-okkal kell elvégezni.

## Új v1.6.0: alkalmazásonként külön hangprofilok (V17 alapján)

A korábbi Meeting AI Offline Web V17 SQLite hangprofil-megoldásából átvett elvek:
**személyenként 20 jóváhagyott hangminta**, helyi pyannote hangvektor,
normalizált centroid, százalékos (nem valószínűségi) találatjavaslat,
és manuális jóváhagyás. Az új v1.6 SQLite adatbázis alkalmazásonként külön:
`C:\OmegaAI\data\tenants\<tenant_id>\voices.sqlite3`.
A felvételek és hangvektorok is SQLite-ban vannak; 3–90 mp / max 15 MB / minta.
A régi V17 személyadatbázist **nem importáljuk automatikusan**.

Csak szerveroldali REST API, `X-Api-Key` **és** `X-Tenant-Key` együtt;
webes/mobilos alkalmazások továbbra is a .NET 10 API-n keresztül kapcsolódnak.
Az audio `/v1/audio/jobs` feltöltés `tenant_id` mezővel tenant-hoz rendelhető,
majd a `POST /v1/tenants/{tenant_id}/jobs/{id}/match` találatjavaslatot ad.
A tényleges név-hozzárendelés külön jóváhagyással történik.

- `14_HANGPROFIL_ALKALMAZAS.bat pilis_meeting "Pilis megbeszélések"`
- `15_HANGMINTA_ROGZITES.bat "C:\Hangok\egyszemely.mp3" pilis_meeting "Minta Katalin" "external-17"`
- `16_BESZELO_AZONOSITAS.bat <job_id> pilis_meeting`

Teljes részletek és kódrészletek:
`docs\HANGPROFILOK_MULTITENANT_API_HU.md`, valamint a bővített Word-kézikönyv.
