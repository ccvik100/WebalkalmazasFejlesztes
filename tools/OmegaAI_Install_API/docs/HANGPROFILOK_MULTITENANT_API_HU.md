# OmegaAI v1.6.0 – Hangprofilok és alkalmazásonkénti személytárak

## Mi változott a V17 alapján?

A feltöltött **Meeting_AI_Offline_Web_V17** projekt `speaker_db.py`, `manual_enrollment.py`, `voice_sample_files.py`, `auto_speakers.py`, valamint `engine.py` fájljait vizsgáltuk. Átvettük a 20 beleegyezéses hangminta-szabályt, a normalizált hangvektor-átlagolás elvét, a pyannote Community-1 beszélő-embeddinget és a nem végleges automatikus felismerési javaslatot. A V17 eredeti adatbázisa `data/meeting.sqlite3`; a mintahangjai külön `data/voice_samples` fájlokban is lehetnek. Az új OmegaAI adatbázisa **NEM** egy közös másolat ebből.

**Minden külön .NET alkalmazás külön tenantot kap.** Az egyik alkalmazás személyei és hangprofiljai más alkalmazás kulcsával nem láthatók. Az alkalmazás a saját SQLite/SQL Server személynyilvántartását megtarthatja, a személy `external_person_id` mezővel szinkronizálható.

## Alapbeállítások

- Gyökér: `C:\OmegaAI`
- Modellek: `C:\OmegaAI\models\whisper-large-v3`, `models\pyannote-community-1`, `models\ollama`
- Meglévő Ollama: `http://127.0.0.1:11434` – Qwen3:8b
- OmegaAI REST: `http://127.0.0.1:8768` – Swagger `/docs`
- Titkos főkulcs: `C:\OmegaAI\config\api-key.txt` (csak szerveroldal)
- Tenant-adatbázisok: `C:\OmegaAI\data\tenants\<tenant_id>\voices.sqlite3`
- Tenant-nyilvántartás: `C:\OmegaAI\data\tenants\_registry.sqlite3`, a tenant kulcsok csak SHA-256 lenyomattal tárolódnak.

A SQLite fájlban `persons`, `voice_samples`, `voice_centroids` táblák vannak. A `voice_samples.audio` mező BLOB; a hozzá tartozó pyannote-vektor JSON-szövegként ugyanabban az adatbázisban van. Egy személyhez legfeljebb **20 különböző, jóváhagyott hangfelvétel** tartozhat. A minták 3–90 másodperces, legfeljebb 15 MB-os, **egyetlen személy** tiszta beszédét tartalmazó felvételek legyenek. Ugyanazon hang újraküldése nem foglal új helyet.

## Architektúra

```text
Mobil (Kotlin/MAUI) / Web (HTML5/Blazor)
      | HTTPS, bejelentkezett felhasználó és jogosultság
      v
.NET 10 API  [minden felhasználói és tenant jogot ellenőriz]
      | X-Api-Key és X-Tenant-Key, csak szerveroldalon
      v
OmegaAI 127.0.0.1:8768  ----> Ollama 127.0.0.1:11434
      | REST + SSE, közös hangfeldolgozási sor
      +--> Whisper magyar átirat
      +--> pyannote diarizáció és hangvektorok
      +--> SQLite tenant-profil egyezés: javaslat vagy ismeretlen
      +--> Kézi jóváhagyás -> átirat frissítés -> Qwen összesítő
```

Az OmegaAI nem publikus mobil API. A böngésző vagy APK **soha** nem kapja meg a két belső API-kulcsot. Egy v1.6-os tenant-adatbázis nem azonos a V17 korábbi `meeting.sqlite3` fájljával. A régi adatbázis **nem importálódik automatikusan**, mivel személyes és biometrikus adatot tartalmaz; a személyeket a hitelesített .NET API külön szinkronizálhatja, a hangmintákhoz dokumentált hozzájárulás kell.

## Telepítés és frissítés

1. A korábbi `03_INDITAS.bat` folyamatát állítsd le. Ellenőrizd, hogy nincs futó audio-job.
2. Készíts biztonsági másolatot a `C:\OmegaAI\config` és `C:\OmegaAI\data` mappákról. **Ne töröld** a modelleket.
3. Az új ZIP-et külön mappába bontsd ki, nyiss PowerShellt az `OmegaAI` csomagmappában.
4. Futtasd: `./01_TELEPITES.bat CHECK`, majd `./01_TELEPITES.bat INSTALL` (PowerShellben a pontos előtag ` .\ `, pl. `.\01_TELEPITES.bat CHECK`).
5. Futtasd: `.\02_ELLENORZES.bat DEEP` és `.\03_INDITAS.bat`. Az utóbbi ablak maradjon nyitva.
6. Második PowerShell-ablakban teszteld: `.\04_TEST_QWEN.bat`, `.\05_TEST_MP3.bat "C:\Hangok\teszt.mp3"`, `.\06_TEST_BESZELOK.bat "C:\Hangok\teszt.mp3"`.
7. Ezután következnek a hangprofil-API tesztek (14–16 BAT).

A telepítő a már meglévő Qwen/Whisper/pyannote modelleket és az API-kulcsot megtartja. A hangprofil-adatbázisok és a korábbi feladatok **nem törlődnek**. A BAT-szkriptek BOM nélküliek; a PowerShell-szkriptek Windows PowerShell 5.1-hez is UTF-8 BOM-mal készülnek.

## REST végpontok (a meglévőkkel együtt)

Minden felsorolt végpont a `X-Api-Key` főkulcsot is megköveteli. A `/v1/tenants/{tenant_id}/...` végpontok ezen felül `X-Tenant-Key` kulcsot kérnek, amely csak a megfelelő alkalmazáshoz használható.

| Metódus | Útvonal | Funkció |
|---|---|---|
| POST | `/v1/tenants` | Új alkalmazás és egyszer megjelenített tenant kulcs |
| GET | `/v1/tenants` | Alkalmazáslista – csak főkulcs |
| POST | `/v1/tenants/{t}/rotate-key` | Tenant-kulcs cseréje (régit azonnal tiltja) |
| DELETE | `/v1/tenants/{t}` | Tenant, hangminták, saját történeti hangjobok törlése |
| POST | `/v1/tenants/{t}/persons` | Személy létrehozása/frissítése `external_person_id` alapján |
| GET | `/v1/tenants/{t}/persons` | Személyek, pozíciók és mintaszám |
| DELETE | `/v1/tenants/{t}/persons/{person_id}` | Személy és összes hangminta törlése |
| POST | `/v1/tenants/{t}/persons/{person_id}/samples` | Hangminta feltöltése, modellalapú hangvektorizálás sorba állítása |
| GET | `/v1/tenants/{t}/enrollments/{enroll_id}` | Hangminta feladatállapot, sorpozíció, belső progress |
| GET | `/v1/tenants/{t}/persons/{person_id}/samples` | Mintalista (20 maximummal) |
| GET | `/v1/tenants/{t}/persons/{person_id}/samples/{sample_id}/audio` | Megőrzött hangminta visszajátszáshoz, hitelesítetten |
| DELETE | `/v1/tenants/{t}/persons/{person_id}/samples/{sample_id}` | Hangminta törlése, profil újraszámítása |
| POST | `/v1/tenants/{t}/jobs/{job_id}/match` | Speaker → személy javaslat és jelöltlista, csak saját tenant job |
| POST | `/v1/tenants/{t}/jobs/{job_id}/approve` | Kézi jóváhagyás speaker→person_id térképpel |
| DELETE | `/v1/jobs/{job_id}` | Befejezett hangjob és hangvektorok törlése |
| POST | `/v1/audio/jobs` | Hangfeltöltés – új `tenant_id` form mező és `X-Tenant-Key` fejléc |
| GET | `/v1/jobs/{job_id}` | Állapot, `jobs_ahead`, több lépés részletes progress |
| GET | `/v1/jobs/{job_id}/events` | SSE: feldolgozási események és Qwen tokenek |
| POST | `/v1/chat/stream` | Qwen tokenfolyam SSE |

A régi `/v1/voices/enroll` és `/v1/voices/match` gyűjtőútvonal szándékosan 501-es választ ad: hiányzik belőle a szükséges **tenant-kontextus**. Használd a fent dokumentált alkalmazásspecifikus útvonalakat.

### 1. Tenant létrehozása – PowerShell

```powershell
$adminKey = (Get-Content 'C:\OmegaAI\config\api-key.txt' -Raw).Trim()
$admin = @{ 'X-Api-Key' = $adminKey }
$body = @{ tenant_id = 'pilis_meeting'; label = 'Pilis – megbeszélések' } | ConvertTo-Json
$t = Invoke-RestMethod -Uri 'http://127.0.0.1:8768/v1/tenants' -Method Post `
    -Headers $admin -ContentType 'application/json; charset=utf-8' `
    -Body ([Text.Encoding]::UTF8.GetBytes($body))
# A tenant_api_key csak ebben a válaszban jelenik meg. Mentsd szerveroldali titoktárba.
$tenantKey = $t.tenant_api_key
$h = @{ 'X-Api-Key' = $adminKey; 'X-Tenant-Key' = $tenantKey }
```

A főkulcsot és tenant kulcsot **soha ne küldd mobilapphoz**; az ASP.NET Core API kezeli és jogosultságellenőrzés után továbbítja a kérést.

### 2. Személy felvétele – a saját SQLite azonosítójával

```powershell
$person = @{ name = 'Minta Katalin'; organization = 'Pilis';
    position = 'Jegyző'; elected_position = 'Bizottsági tag';
    external_person_id = 'sqlite-person-17' } | ConvertTo-Json
$p = Invoke-RestMethod -Uri 'http://127.0.0.1:8768/v1/tenants/pilis_meeting/persons' `
    -Method Post -Headers $h -ContentType 'application/json; charset=utf-8' `
    -Body ([Text.Encoding]::UTF8.GetBytes($person))
# $p.id az OmegaAI lokális azonosítója; external_person_id a külső app saját azonosítója.
```

Ha a kliens a saját SQLite-jában módosítja a pozíciót, a backend ugyanazzal az `external_person_id` értékkel küld egy új POST-ot. **Nem keletkezik második személy**, a rekord frissül.

### 3. Hangminta rögzítése (PowerShell BAT)

```powershell
.\14_HANGPROFIL_ALKALMAZAS.bat pilis_meeting "Pilis megbeszélések"
.\15_HANGMINTA_ROGZITES.bat "C:\Hangok\egy_szemely.mp3" pilis_meeting "Minta Katalin" "sqlite-person-17"
```

A 14-es BAT egy helyi titkos fájlba menti a tenant kulcsát a `C:\OmegaAI\config\tenant-keys` mappában. Állíts be NTFS ACL-védelmet, ne oszd meg és ne tedd közzé. A 15-ös BAT kifejezett `IGEN` jóváhagyást kér a hangminta feldolgozása előtt. Csak az érintett által megfelelően engedélyezett, tiszta, egyszemélyes hangot használj. A feldolgozó **202 Accepted** állapotot ad, külön enrollment ID-vel; a BAT a `GET /enrollments/{id}` végpontot követi és befejezéskor kiírja a sample ID-t.

### 4. Megbeszélés feltöltése tenanttal

```powershell
curl.exe -X POST 'http://127.0.0.1:8768/v1/audio/jobs' `
  -H "X-Api-Key: $adminKey" -H "X-Tenant-Key: $tenantKey" `
  -F 'tenant_id=pilis_meeting' `
  -F 'audio=@C:\Hangok\testuleti.mp3;type=audio/mpeg' `
  -F 'title=Testületi megbeszélés' `
  -F 'diarize=true' -F 'summarize=true'
```

A `diarize=true` szükséges ahhoz, hogy a Community-1 a speaker-címkékhez hangvektorokat is készítsen. A program a feladathoz `speaker-embeddings.json` privát fájlt készít. Ez **soha nem része a publikus `/segments` válasznak**. Az állapotot `GET /v1/jobs/{id}` útvonalon vagy SSE-n kövesd; ott a `jobs_ahead` a már futó munkát is beleszámolja az előtted lévők számába.

### 5. Javasolt személyek és kézi jóváhagyás

```powershell
$jobId = '<a POST után kapott 32 karakteres id>'
$match = @{ threshold = 0.88; margin = 0.04 } | ConvertTo-Json
$suggest = Invoke-RestMethod -Uri "http://127.0.0.1:8768/v1/tenants/pilis_meeting/jobs/$jobId/match" `
   -Method Post -Headers $h -ContentType 'application/json' -Body $match
$suggest.speakers
# A felhasználó meghallgatja és jóváhagyja az első SPEAKER_00 -> személy párost.
$body = @{ approved = @{ SPEAKER_00 = $p.id } } | ConvertTo-Json -Depth 5
Invoke-RestMethod -Uri "http://127.0.0.1:8768/v1/tenants/pilis_meeting/jobs/$jobId/approve" `
    -Method Post -Headers $h -ContentType 'application/json' -Body $body
# Ezt követően új összesítő kérhető:
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8768/v1/jobs/$jobId/regenerate-summary" -Headers $h
```

A `candidates[].similarity_percent` koszinusz-hasonlóság*100, **nem személyazonossági megbízhatóság vagy kalibrált valószínűség**. Alapértelmezett elfogadási javaslathatár 0,88 és az első két jelölt közötti 0,04 eltérés. Az ismeretlen beszélő ismeretlen marad. Az API **nem hagy jóvá személyt magától**; az `/approve` végpont explicit, naplózható alkalmazási döntés.

### 6. Három teszt-BAT és eredmények

- `14_HANGPROFIL_ALKALMAZAS.bat <tenant_id> "Megnevezés"` – létrehozás és tenant kulcs privát helyi mentése.
- `15_HANGMINTA_ROGZITES.bat "C:\Hangok\egyszemely.mp3" <tenant_id> "Név" "külső ID"` – hangminta jóváhagyás, sorba állítás és státuszkövetés.
- `16_BESZELO_AZONOSITAS.bat <valós job_id> <tenant_id>` – találatok kilistázása, **nem alkalmazza** automatikusan.

A tesztek a meglévő `01`–`13` BAT-ok **mellett** futnak. Előbb a `02_ELLENORZES DEEP`, `03_INDITAS`, `05_TEST_MP3`, `06_TEST_BESZELOK` teljes működését ellenőrizd. A teszt-WAV/MP3 valódi személyhangot csak jogszerű hozzájárulással tartalmazzon.

## ASP.NET Core 10 szerveroldali integráció

A kliensek bejelentkezése, jogosultságai és a külső alkalmazásszemély-ID ellenőrzése a saját .NET API felelőssége. Az alábbi kód csak **szerveroldalon** futhat (nem Blazor WASM-ban vagy Kotlinban):

```csharp
using System.Net.Http.Json;
using System.Net.Http.Headers;

// Startup: builder.Services.AddHttpClient("OmegaAI", c =>
//     c.BaseAddress = new Uri("http://127.0.0.1:8768"));

var client = httpClientFactory.CreateClient("OmegaAI");
client.DefaultRequestHeaders.Add("X-Api-Key", configuration["OmegaAI:MasterKey"]);
client.DefaultRequestHeaders.Add("X-Tenant-Key", tenantSecretFromServerSideStore);

using var form = new MultipartFormDataContent();
await using var audio = File.OpenRead(@"C:\Hangok\test.mp3");
form.Add(new StreamContent(audio), "audio", "test.mp3");
form.Add(new StringContent("pilis_meeting"), "tenant_id");
form.Add(new StringContent("true"), "diarize");
form.Add(new StringContent("true"), "summarize");
using var response = await client.PostAsync("/v1/audio/jobs", form);
response.EnsureSuccessStatusCode();
var job = await response.Content.ReadFromJsonAsync<UploadResponse>();

// A végfelhasználó csak a SAJÁT feladata azonosítóját láthatja.
// A saját .NET API ellenőrzi a felhasználó -> tenant -> job hozzárendelést.
public sealed record UploadResponse(string Id, string Status, int? Jobs_Ahead);
```

A Swaggerben a `jobs_ahead` mező kliensoldalon például „2 feldolgozás van előtted”. A futó Whisper: feldolgozott hangmásodpercek/chunk-szám, pyannote: belső lépések/ismert százalék, Qwen: SSE-tokenfolyam. A REST API az eredeti, korábbi 1.5.1-es végpontokat is megtartja.

## Telepítés Rackforest Windows Serveren

1. A szerver egy **másik számítógép**: saját `C:\OmegaAI`, Python 3.12, FFmpeg, Whisper, pyannote, Ollama/Qwen szükséges.
2. A fejlesztői gép `C:\OmegaAI` adatai nem kerülnek át automatikusan. Érzékeny hangadatot ne másolj hozzájárulás nélkül.
3. Az OfflineAI csak a szerver `127.0.0.1:8768` címén fusson, az Ollama `127.0.0.1:11434` címen. **Ne nyisd meg a portokat az internet felé.**
4. Az IIS HTTPS 443-as felületén az ASP.NET Core 10 API biztosít felhasználói hitelesítést és saját jogosultsági ellenőrzést. Az OmegaAI nem publikus proxyn át megnyitott webalkalmazás.
5. Az admin API és tenant kulcsok csak szerveroldalon, korlátozott NTFS-jogosultsággal legyenek tárolva. A mintahangok és adatbázisok helyi lemezén használj BitLocker / kötet-szintű titkosítást (a sima SQLite **nem titkosított**).
6. A hangprofil és megbeszélési job adatok megőrzését és törlését (backupokkal együtt) külön adatkezelési szabályzat szabályozza.
7. A hangminta/tenant törlés nem teszi utólag visszamenőleg pontatlanná vagy semmissé a már exportált jegyzőkönyveket; a származtatott eredményeket az alkalmazásból is törölni kell, ha ez az adatkezelési cél szerint szükséges.
8. Felhasználói keresztalkalmazás-szinkronizáció **nincs automatikusan**; a .NET API egyértelmű tenantokat és `external_person_id` értékeket használ.

## Kipróbált és még ellenőrizendő

- Automatizált tesztek: API auth, tenant elkülönítés, kulcsforgatás, személy upsert, 20-as limit, BLOB-letöltés/törlés, cosine-javaslat, manuális jóváhagyás, sorállapot, SSE, ellenőrzött route-visszautasítás.
- A fenti tesztek egy része **helyettesített vektor- és modellválasszal** történik; ezek nem bizonyítják a konkrét Windowsos 3–90 másodperces pyannote hangminta-lekérdezés sikerét.
- Célgépi teljes igazolás: Windows Server telepítés, 15-ös BAT valódi hangból embeddinget készít, 16-os BAT a saját tenant profiltárával találatot ad, kézi jóváhagyás, új összesítés, CPU/GPU terhelés és megőrzési/törlési vizsgálatok.

## Adatvédelmi emlékeztető

A hangminta és hangvektor **biometrikus jellegű személyes adat**. Csak megfelelő jogalappal, tájékoztatással, konkrét céllal és szükséges megőrzési idővel kezelhető. A „hozzájárult” jelölés API-követelmény, **nem helyettesíti** a valódi, bizonyítható hozzájárulást. Iskolai vagy kiskorúakat érintő feldolgozásnál különösen körültekintő adatvédelmi felülvizsgálat szükséges. Hanghasonlóság önmagában nem alkalmas beléptetési vagy biztonsági személyazonosításra.
