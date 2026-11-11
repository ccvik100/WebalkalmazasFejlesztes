# OmegaAI / OfflineAI v1.1 – REST API használat és példahívások

## 1. Önálló AI-szolgáltatás, stabil URL-ek

Alap URL **csak szerveroldali hívásokhoz**: `http://127.0.0.1:8768`.

A rendszer nem HTML-felületet szolgál ki, hanem REST API-t, amelyhez Swagger dokumentáció is jár: `http://127.0.0.1:8768/docs`. A későbbi .NET 10 API ezt fogja továbbhasználni, és a Blazor/HTML5/Kotlin/MAUI kliensek a .NET API-t hívják felhasználói hitelesítés után.

Minden `/v1/*` kérés fejlécében:

```http
X-Api-Key: <a C:\OmegaAI\config\api-key.txt tartalma>
```

A kulcs **soha nem kerül a böngésző vagy mobilalkalmazás forráskódjába**. A valódi publikus felhasználói hitelesítés a későbbi .NET API felelőssége.

## 2. Végponttábla

| HTTP | URL | Cél | Válasz |
|---|---|---|---|
| GET | `/health/live` | Futtatókörnyezet állapota | 200, de NEM modellteszt |
| GET | `/v1/health/ready` | Helyi fájlok és Ollama elérhetősége | JSON |
| GET | `/v1/models` | Telepített komponensek | JSON |
| POST | `/v1/chat` | Qwen prompt → válasz | `{ "answer": "..." }` |
| POST | `/v1/summaries` | Kész átirat → magyar összesítő | `{ "summary": "..." }` |
| POST | `/v1/audio/jobs` | MP3/WAV feltöltés + feldolgozás indítása | 202, `id`, `poll_url` |
| GET | `/v1/jobs/{id}` | Feldolgozási állapot | `queued / running / completed / failed` |
| GET | `/v1/jobs/{id}/transcript` | Szöveges átirat | text/plain |
| GET | `/v1/jobs/{id}/segments` | Időbélyegzett beszélő-szakaszok | JSON-tömb |
| GET | `/v1/jobs/{id}/summary` | Magyar összesítő | text/plain |
| PUT | `/v1/jobs/{id}/speaker-names` | Beszélőcímke → személynév **kézzel** | JSON |
| POST | `/v1/jobs/{id}/regenerate-summary` | Névjavítás után új összesítő | JSON |
| POST | `/v1/voices/enroll` | Hangprofil-regisztráció | **501 – még nincs megvalósítva** |
| POST | `/v1/voices/match` | Hangminta alapján névfelismerés | **501 – még nincs megvalósítva** |

### Hitelesítési hibák

- **401**: hiányzó/érvénytelen `X-Api-Key`.
- **400/413/422**: hibás vagy túl nagy hangfájl; nem elfogadott paraméter.
- **429**: túl sok párhuzamos hangfeldolgozási kérés.
- **503**: a helyi Qwen szolgáltatás nem érhető el.
- **202**: a hangfeldolgozás *elindításra vár* – **nem** azt jelenti, hogy elkészült!
- **501**: hangprofil-alapú automatikus személyazonosítás nincs implementálva.

## 3. Qwen – PowerShell példa

A szolgáltatásnak már futnia kell (`03_INDITAS.bat`). Ez a példa **PowerShellben** fut; a CMD-s `Invoke-RestMethod` hibát elkerülöd, ha a PowerShellt használod.

```powershell
$key = (Get-Content 'C:\OmegaAI\config\api-key.txt' -Raw).Trim()
$body = @{ prompt = 'Írj három mondatot arról, mi az a REST API.' } | ConvertTo-Json
Invoke-RestMethod -Method POST `
  -Uri 'http://127.0.0.1:8768/v1/chat' `
  -Headers @{ 'X-Api-Key' = $key } `
  -ContentType 'application/json; charset=utf-8' `
  -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

Példaválasz (illusztráció, nem tényleges futási eredmény):

```json
{ "model": "qwen3:8b", "answer": "A REST API ..." }
```

## 4. Hangfeldolgozás – Swagger vagy BAT

A legbiztosabb első út: `05_TEST_MP3.bat "C:\Hangok\teszt.mp3"`.

Swaggerben: `http://127.0.0.1:8768/docs`, `POST /v1/audio/jobs`, `Try it out`. Az `X-Api-Key`-t a fejlécben add át, majd töltsd fel a fájlt.

**Multipart/form-data mezők:**

- `audio`: `file`, pl. `teszt.mp3` (kötelező).
- `title`: `Testületi megbeszélés` (opcionális).
- `started_at`: `2026-11-08T18:00:00+01:00` (opcionális, ajánlott).
- `diarize`: `true`/`false` (alapból `false`; valódi beszélőszétválasztáshoz `true`).
- `summarize`: `true`/`false` (alapból `true`).

**PowerShell + curl.exe** (a `curl.exe` explicit hívása kerüli a PowerShell régi `curl` aliasát):

```powershell
$key = (Get-Content 'C:\OmegaAI\config\api-key.txt' -Raw).Trim()
curl.exe -X POST 'http://127.0.0.1:8768/v1/audio/jobs' `
  -H "X-Api-Key: $key" `
  -F 'audio=@C:\Hangok\teszt.mp3;type=audio/mpeg' `
  -F 'title=Teszt megbeszélés' `
  -F 'started_at=2026-11-08T18:00:00+01:00' `
  -F 'diarize=true' `
  -F 'summarize=true'
```

Sikeres válasz **például**:

```json
{ "id": "a1234bcd5678e90123456789abcdef01", "status": "queued", "poll_url": "/v1/jobs/a1234bcd5678e90123456789abcdef01" }
```

**Utána**, az előző válasz `id` mezőjével (a példában szereplő azonosítót cseréld ki):

```powershell
$id = '<a POST válaszból kapott id>'
$h = @{ 'X-Api-Key' = $key }
Invoke-RestMethod -Uri "http://127.0.0.1:8768/v1/jobs/$id" -Headers $h
# Ha status=completed, akkor:
Invoke-WebRequest -Uri "http://127.0.0.1:8768/v1/jobs/$id/transcript" -Headers $h -OutFile 'atirat.txt'
Invoke-WebRequest -Uri "http://127.0.0.1:8768/v1/jobs/$id/summary" -Headers $h -OutFile 'osszesito.txt'
```

Az állapot `failed` esetén a `message` mező tartalmazza a konkrét hibát, pl. hiányzó FFmpeg, modell vagy Qwen.

## 5. Beszélőcímkék elnevezése

A beszélőszétválasztás például `SPEAKER_00`, `SPEAKER_01` értékeket ad. Ez **nem állítja**, hogy a rendszer ismeri az adott személyt.

```powershell
$id = '<a feldolgozás azonosítója>'
$key = (Get-Content 'C:\OmegaAI\config\api-key.txt' -Raw).Trim()
$names = @{ names = @{ SPEAKER_00 = 'Dávid'; SPEAKER_01 = 'Alexandra' } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method PUT `
 -Uri "http://127.0.0.1:8768/v1/jobs/$id/speaker-names" `
 -Headers @{ 'X-Api-Key' = $key } -ContentType 'application/json; charset=utf-8' `
 -Body ([Text.Encoding]::UTF8.GetBytes($names))
```

Ezután az új összesítő (nem a hang újbóli feldolgozása) ugyanazzal az `id`-val:

```powershell
Invoke-RestMethod -Method POST `
  -Uri "http://127.0.0.1:8768/v1/jobs/$id/regenerate-summary" `
  -Headers @{ 'X-Api-Key' = $key }
```

## 6. Önálló összesítő egy már elkészült átiratból

```powershell
$key = (Get-Content 'C:\OmegaAI\config\api-key.txt' -Raw).Trim()
$body = @{
  title = 'Konzorciumi megbeszélés'
  started_at = '2026-11-08T18:00:00+01:00'
  transcript = '[00:00:01] SPEAKER_00: A következő pályázatról egyeztessünk.'
} | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method POST -Uri 'http://127.0.0.1:8768/v1/summaries' `
 -Headers @{ 'X-Api-Key' = $key } -ContentType 'application/json; charset=utf-8' `
 -Body ([Text.Encoding]::UTF8.GetBytes($body))
```

## 7. C# (.NET 10) szerveroldali hívási példa

**Csak ASP.NET Core szerveren** használd. Az `X-Api-Key` nem kerülhet a JavaScript/Blazor WebAssembly/Android/iOS kliensbe!

```csharp
using System.Net.Http.Json;

var http = new HttpClient { BaseAddress = new Uri("http://127.0.0.1:8768") };
var key = Environment.GetEnvironmentVariable("OFFLINEAI_API_KEY")
          ?? throw new InvalidOperationException("OFFLINEAI_API_KEY hiányzik");
http.DefaultRequestHeaders.Add("X-Api-Key", key);

// Példa: Qwen-válasz lekérése.
var result = await http.PostAsJsonAsync("/v1/chat", new {
    prompt = "Foglald össze, hogyan működik egy ASP.NET Core API."
});
result.EnsureSuccessStatusCode();
var json = await result.Content.ReadFromJsonAsync<ChatResponse>();
Console.WriteLine(json?.Answer);

public sealed record ChatResponse(string Model, string Answer);
```

**Fájl feltöltése C# szerverből**:

```csharp
using var form = new MultipartFormDataContent();
await using var input = File.OpenRead(@"C:\Hangok\teszt.mp3");
form.Add(new StreamContent(input), "audio", "teszt.mp3");
form.Add(new StringContent("Közös megbeszélés"), "title");
form.Add(new StringContent("2026-11-08T18:00:00+01:00"), "started_at");
form.Add(new StringContent("true"), "diarize");
form.Add(new StringContent("true"), "summarize");
var response = await http.PostAsync("/v1/audio/jobs", form);
response.EnsureSuccessStatusCode(); // várható HTTP 202, még NEM kész az átirat
Console.WriteLine(await response.Content.ReadAsStringAsync());
```

Éles .NET API-ban célszerű `IHttpClientFactory`-t használni és korlátozni a felhasználónkénti hangfájlméretet, kérésszámot.

## 8. API-verzió és kompatibilitás

- A jelenlegi stabil végpontok `/v1/...` kezdetűek.
- Új funkciókat `/v1` alatt csak visszafelé kompatibilisen érdemes felvenni; törő változtatás `/v2` útvonalon történjen.
- A feladatokból keletkező fájlok a `C:\OmegaAI\data\jobs` könyvtárban maradnak; az `id` nem jogosultságkezelés, ezért minden végpont API-kulcsot kér.
- A `GET /v1/health/ready` pozitív értéke NEM garantálja az első valódi inferencia sikerét – erre van a `DEEP` és a teljes MP3-teszt.


## OmegaAI v1.5: valós előrehaladás, sor és Qwen SSE

A régi API-végpontok változatlanok. Új végpontok (mindegyikhez X-Api-Key kell):

| HTTP | Útvonal | Funkció |
| --- | --- | --- |
| GET | `/v1/queue` | aktív job, várakozók és kapacitás |
| GET | `/v1/jobs/{id}` | `stage`, `stage_percent`, hangidő, chunk, queue_position, eltelt idő, CPU/GPU |
| GET | `/v1/jobs/{id}/events` | `progress` és generálódó `token` SSE, majd `done` |
| POST | `/v1/jobs/{id}/cancel` | várakozó/futó feladat megszakítása |
| GET | `/v1/hardware` | CPU/CUDA-vizsgálat és figyelmeztetés |
| POST | `/v1/chat/stream` | Qwen prompt → tokenenként `text/event-stream` |
| POST | `/v1/summaries/stream` | kész átirat → streamelt magyar összesítő |

**Jelzések:** `queued` = várakozik, `running` = feldolgozás alatt, `completed` = kész, `failed` = hiba vagy időkorlát, `canceled` = visszavonva. Az `audio_processing_tested` csak akkor lesz True, ha korábban volt legalább egy befejezett feldolgozás; a minőségértékelést nem helyettesíti.

Whisper: `completed_seconds/total_seconds`, `chunks_completed/chunks_total`, `stage_percent` valós hangidő-arány. Pyannote: a `stage_units_completed/total` az adott belső lépés számlálója. Ha a pyannote összesített teljesítése nem ismert, a teljes globális progress nem változik; az `elapsed_sec` és a `stage_detail` frissül. Qwen: az `event: token` adatmezője `{"delta":"..."}`; nincs kitalált hátralévő százalék.

Példa SSE keret:

```text
event: token
data: {"delta":"A projekt következő lépése "}

event: done
data: {"ok":true}
```

Tesztelés: `.\11_TEST_QWEN_STREAM.bat`, `.\10_TEST_HAROM_FELTOLTES.bat "C:\Hangok\rovid.mp3"`, `.\12_CPU_GPU_DIAGNOSZTIKA.bat`, `.\13_JOB_ALLAPOT.bat "<id>"`.

A POST SSE-végpontot HttpClient/fetch stream-olvasással lehet hívni (EventSource GET és saját X-Api-Key fejléc nélkül nem használható). A későbbi .NET API szerveroldali gateway; az OmegaAI X-Api-Key nem kerülhet ki kliensbe.

## v1.5.1 – Személyre szabott munkasor, webes és mobilos visszajelzés

A `POST /v1/audio/jobs` HTTP 202 választ ad akkor is, ha a feladat még várakozik. A beküldőnek visszaadott `id` alapján a saját .NET API 2–5 másodpercenként lekérdezheti a `GET /v1/jobs/{id}` állapotot, vagy olvashatja a `GET /v1/jobs/{id}/events` SSE streamet. Az OmegaAI belső API-kulcsát a kliens nem láthatja.

**Példa, amikor egy másik munka fut, és még egy további várakozik előttünk:**

```json
{
  "id": "0123456789abcdef0123456789abcdef",
  "status": "queued",
  "queue_position": 2,
  "queue_ahead": 1,
  "waiting_ahead": 1,
  "jobs_ahead": 2,
  "queue_position_overall": 3,
  "active_jobs": 1,
  "queue_message": "Sorban áll: 2 feldolgozás van előtted."
}
```

A `queue_position` és `queue_ahead` **csak a várakozókat számolja**, az új `jobs_ahead` a már aktív munkát is. Futáskor `status=running`, `jobs_ahead=0`, és a `stage`, `stage_detail`, `stage_percent`, `completed_seconds`, `total_seconds`, `chunks_completed`, `chunks_total` mezők alapján jeleníthető meg a részletes készültség. A `progress` súlyozott, teljes-feladat kijelzés; a Whisper `stage_percent` hangidő alapú; a pyannote-nál kizárólag a pillanatnyi belső lépés %-a, ha ismert a nevező. Ismeretlen értéknél a kliens mutasson eltelt időt és „feldolgozás folyamatban” állapotot, **ne kitalált százalékot**.

A sorban állók számát **ne tekintsd időbecslésnek**: a munkák hanghossza és hardverigénye különböző. A szervernek kell a sor sorrendjét kezelnie; a kliens csak megjeleníti az adatokat. A `/v1/queue` az egész rendszer állapotát adja, ezt csak admin jogosultság esetén érdemes a publikus .NET API-ból megmutatni.
