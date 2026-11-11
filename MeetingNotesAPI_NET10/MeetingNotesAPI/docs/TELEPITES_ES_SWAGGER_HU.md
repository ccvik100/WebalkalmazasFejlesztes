# MeetingNotesAPI – .NET 10 / OmegaAI v1.6 – telepítés és Swagger-tesztek

## 0. Mit tartalmaz ez a projekt?

Ez **kizárólag a MeetingNotesAPI .NET 10 REST API**, nem tartalmazza az OmegaAI modelleket, a Blazor/HTML5 oldalt és az Android/MAUI klienseket. A későbbi alkalmazások az internet felől a HTTPS-es MeetingNotesAPI-t fogják hívni. Az OmegaAI továbbra is külön fut `C:\OmegaAI` alatt.

```text
Böngésző / Blazor / MAUI / Kotlin (KÉSŐBB)
        |
        | HTTPS + felhasználói authentikáció (később JWT/OIDC)
        v
MeetingNotesAPI  (.NET 10 + IIS, fejlesztői gépen 5200)
        | X-Api-Key és X-Tenant-Key, NEM kerül kliensre
        v
OmegaAI          (http://127.0.0.1:8768)
        | Whisper, pyannote, személyi SQLite, Qwen
        v
Ollama           (http://127.0.0.1:11434)
```

**A jelen első változatban** a `X-Meeting-Key` a Swaggerből és zárt tesztkörnyezetből való teszteléshez van. Ezt **ne építsd be publikus HTML5/Blazor WebAssembly vagy mobilalkalmazásba**, mert onnan kimásolható. A publikus kliensekhez a következő fázisban felhasználói login, JWT/OIDC, szerepkörök, felhasználónkénti hozzárendelés, adatmegőrzési szabályok és rate limit szükséges. Nincs még publikus klienshitelesítési készültség.

## 1. Előfeltételek a fejlesztői számítógépen

1. Windows 11, **Visual Studio 2026 18.x** és **.NET 10 SDK**.
2. A `C:\OmegaAI` már telepítve és **fut** (`03_INDITAS.bat`).
3. OmegaAI Swagger: `http://127.0.0.1:8768/docs`.
4. Ha `GET /health/live` válaszol, az csupán az API futását igazolja; a Qwen/Whisper működéshez külön inferenciateszt kell.
5. A `C:\OmegaAI\config\api-key.txt` tartalmazza a helyi OmegaAI főkulcsot (legalább 40 karakter).

A fejlesztői és a Rackforest szerver **külön számítógép**, ezért ott a `localhost` és a `C:\OmegaAI` is külön telepítésre mutat.

## 2. Fejlesztői telepítés – pontos futtatási sorrend

Csomagold ki a ZIP-et tetszőleges mappába. A megoldás: `MeetingNotesAPI.slnx`, a projekt: `MeetingNotesAPI\MeetingNotesAPI.csproj`.

Nyiss PowerShellt a `MeetingNotesAPI` **projektmappában** (ott, ahol a `.csproj` van):

```powershell
.\scripts\01_KONFIGURALAS.bat
.\scripts\02_ELLENORZES.bat
.\scripts\06_BUILD_ELLENORZES.bat
```

A konfiguráló a helyben futó OmegaAI-hoz csatlakozik. **Első alkalommal** létrehoz egy `meetingnotes` nevű tenantot és egy 64 karakteres, kizárólag e .NET API tesztklienséhez tartozó kulcsot. Az OmegaAI és a tenant belső kulcsát a `private\meetingnotes.secrets.json` fájlban őrzi, amely **nem része a publikációnak és nem a wwwroot alatt van**. A konfiguráló megőrzi a korábbi kulcsokat; már létező, ismeretlen tenant-kulcs esetén manuális megadást kér. Ne kerüljön verziókezelőbe!

Visual Studio: nyisd meg `MeetingNotesAPI.slnx` → indítóprofil `MeetingNotesAPI - Visual Studio` → F5.

Vagy a projektmappában:

```powershell
.\scripts\03_INDITAS.bat
```

Fejlesztői Swagger: **http://localhost:5200/swagger**.

Az API a **5200**-as porton fut, hogy ne ütközzön a régi MeetingNotes API 5100-as és az OmegaAI 8768-as portjával.

## 3. Hitelesítés Swaggerben

A `/api/health/live` nyilvános; a többi `/api/*` végpontnál `X-Meeting-Key` fejléc kötelező. A saját tesztkliens kulcsát PowerShellben (a `MeetingNotesAPI` projektmappából) így tudod megjeleníteni:

```powershell
(Get-Content '.\private\meetingnotes.secrets.json' -Raw | ConvertFrom-Json).MeetingNotes.Clients[0].ClientKey
```

A kapott kulcsot a Swagger minden kérésénél az `X-Meeting-Key` fejlécbe másold. Soha ne másold a publikus forráskódba és ne tedd közzé képernyőképen.

## 4. Swagger tesztek – ebben a sorrendben

### A. API és OmegaAI fut-e?

**GET `/api/health/live`** – HTTP 200, `status=running`: ez csak a .NET API-t teszteli.

**GET `/api/health/omegaai`** – HTTP 200 és `omegaAiOnline=true`: az OmegaAI elérhető és a modellfájlok megvannak; **nem valódi hangfeldolgozás**. Ha az OmegaAI áll, HTTP 503-at kell kapnod.

**GET `/api/system/models`**, **GET `/api/system/hardware`** – telepítési és hardver-adatok.

**GET `/api/queue`** – `activeJobs`, `waitingJobs`, `capacity`, `maxParallelAudioJobs`. A más alkalmazásokra vonatkozó feladatspecifikus azonosítók nem kerülnek ki.

### B. Qwen chat

**POST `/api/ai/chat`**, törzs:

```json
{ "prompt": "Mi az ASP.NET Core REST API? Válaszolj egy magyar mondatban." }
```

HTTP 200 esetén az `answer` szöveg valódi helyi Qwen-válasz. Ha az Ollama nem fut, 503 várható.

**POST `/api/ai/chat/stream`** SSE-események (`start`, `token`, `done`); az élő tokeneket a Swagger nem mindig jeleníti meg folyamatosan, mert az SSE nem szokványos JSON-válasz. Teszteld inkább cURL/PowerShell útján (lásd 6. fejezet).

### C. Új hangfeltöltés

**POST `/api/meetings`** – Swagger `Try it out`, `multipart/form-data`:

- `Audio`: saját, jogszerűen rögzített `C:\Hangok\teszt.mp3`.
- `Title`: `Teszt megbeszélés`.
- `StartedAt`: `2026-11-08T19:00:00+01:00` vagy később a tényleges idő.
- `Diarize`: `true`, `Summarize`: `true`.

Az API automatikusan hozzáadja az OmegaAI-hoz tartozó tenantot, a kliens NEM dönthet tetszőleges tenantazonosítóról. **Sikeres válasz HTTP 202**, például:

```json
{ "id": "32_karakteres_azonosito", "status": "queued", "jobs_ahead": 2, "queue_message": "Sorban áll: 2 feldolgozás van előtted." }
```

A `202` még nem kész átirat! Másold ki az `id`-t.

**GET `/api/meetings/{id}`** – figyeld a `status`, `jobs_ahead`, `stage`, `stage_percent`, `completed_seconds`, `total_seconds`, `chunks_completed`, `device` mezőket. `jobs_ahead=2` azt jelzi: **két feldolgozás van előtted**, a már futó munkát is beleszámolva.

**GET `/api/meetings/{id}/events`** – SSE progress: ha a kliens bontja a kapcsolatot, a háttérfeladat NEM szakad meg; újra lekérdezhető az id alapján.

Ha `status=completed`: **GET `/api/meetings/{id}/transcript`** és **GET `/api/meetings/{id}/summary`**. Beszélők szakaszai: **GET `/api/meetings/{id}/segments`**.

### D. Személyek, hangprofilok, beszélőazonosítás

**POST `/api/people`** törzs:

```json
{ "externalPersonId":"person-17", "name":"Minta Katalin", "organization":"Példa", "position":"Jegyző", "electedPosition":"Bizottsági tag" }
```

**GET `/api/people`** – csak a saját tenant személyei. 

**POST `/api/people/{personId}/samples`** – egyetlen személy 3–90 másodperces mintája, `ConsentConfirmed=true` és értelmes `ConsentNote` szükséges. Az OmegaAI személyenként legfeljebb **20 mintát** tárol az alkalmazás saját SQLite-adatbázisában.

**GET `/api/people/enrollments/{id}`** – hangminta feldolgozás állapota és sorpozíciója.

Befejezett, diarizált hangjobnál: **POST `/api/meetings/{id}/identification/suggest`**:

```json
{ "threshold": 0.88, "margin": 0.04 }
```

A javasolt `similarity_percent` nem valódi személyazonossági valószínűség. **Nem automatikus bizonyító erejű azonosítás.** Jóváhagyás csak külön, emberi döntés alapján:

**POST `/api/meetings/{id}/identification/approve`**:

```json
{ "approved": { "SPEAKER_00": "az_omegaai_person_id" } }
```

Az átirat módosítása után szükség esetén **POST `/api/meetings/{id}/regenerate-summary`**.

## 5. BAT-os automatikus ellenőrzés és eredménymentés

Második PowerShell ablakban, a projekt mappájában:

```powershell
.\scripts\04_TEST_API.bat
.\scripts\04_TEST_API.bat 'C:\Hangok\teszt.mp3'
```

A második teszt MP3-at feltölt, sorpozíciót és részletes státuszt figyel, majd `teszteredmeny_<job_id>\atirat.txt` és `osszesito.txt` fájlokat ment. Az MP3 tényleges átirata CPU esetén hosszú is lehet.

## 6. SSE-élő válasz egyszerű tesztje

PowerShellben:

```powershell
$key = (Get-Content '.\private\meetingnotes.secrets.json' -Raw | ConvertFrom-Json).MeetingNotes.Clients[0].ClientKey
$body = '{"prompt":"Sorolj fel három okot, miért jó a REST API."}'
curl.exe -N -X POST 'http://localhost:5200/api/ai/chat/stream' `
  -H "X-Meeting-Key: $key" -H 'Content-Type: application/json' `
  --data-binary $body
```

Várt események: `event: start`, `event: token`, `event: done`. PowerShell 5.1 esetén a JSON-parancssori idézőjelezés eltérhet; biztonságos alternatíva: a JSON-t UTF-8 fájlba írd és `--data-binary @chat.json` formában add át.

## 7. Rackforest Windows Server + IIS

1. A Rackforest szerver saját `C:\OmegaAI` telepítése **külön** történik; előbb `03_INDITAS.bat`, OmegaAI tesztek.
2. Fejlesztői gépen futtasd `scripts\05_PUBLISH.bat` → `publish\MeetingNotesAPI`.
3. Másold a publikált fájlokat pl. `C:\Sites\MeetingNotesAPI` alá. A **private/meetingnotes.secrets.json** nem publikálódik – szerveren futtasd újra a `scripts\01_KONFIGURALAS.bat` fájlt, amely a szerver saját OmegaAI tenantját és kulcsait állítja be.
4. Telepítsd a **.NET 10 ASP.NET Core Hosting Bundle** csomagot a szerverre (nem csak SDK-t). IIS Application Pool: **No Managed Code**, 64 bit. Webhely fizikai útvonala a publikált mappa. HTTPS 443 és érvényes tanúsítvány.
5. A Swagger csak korlátozott admin/tesztelési környezetben maradjon bekapcsolva; az internet felé éles üzemben célszerű tiltani `EnableSwagger=false` értékkel.
6. Csak a **443** legyen nyilvánosan elérhető. **Ne nyisd ki** a 8768 és 11434 portot. A Python FastAPI és az Ollama nem az IIS wwwroot alatt fut.
7. Az IIS 30 MB-os alapértelmezett requestFiltering korlátját a kívánt hangfeltöltési limithez kell igazítani. Ugyanígy korlátozd az éles végpontokat és naplózást, tárhelyet, megőrzési időt, kérésszámot, jogosultságokat.
8. A .NET API és az OmegaAI szerveroldali kapcsolatán ellenőrizd a `GET /api/health/omegaai` választ a **Rackforest szerveren is**.

**Biztonsági határ:** a jelenlegi `X-Meeting-Key` csak integrációs/oktatási teszthez való. A későbbi publikus kliensrendszerhez hozzá kell építeni a belépést, felhasználói jogosultságokat, rate limitinget, auditot, CSRF/CORS-szabályokat és adathozzáférési jogosultságokat.

## 8. Mi bizonyított / mi nem?

Ez a projekt a feltöltött OmegaAI **v1.6 tényleges Python REST-végpontjaihoz** igazodik (v1 chat, stream, queue, jobs, tenants, persons, voice samples). A belső protokoll forrásból összevethető. Ez a fejlesztői környezet **nem tartalmaz .NET SDK-t és Windows IIS-t**, ezért itt a valódi `dotnet build`, IIS-telepítés és végponttól végpontig Windows hangteszt **nem igazolható**. A csomag a végrehajtást és diagnosztikát támogatja; nem állít ellenőrizetlen fordítási sikert.
