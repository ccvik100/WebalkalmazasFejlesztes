# MeetingNotesAPI – részletes oktatói kódséta (.NET 10)

Ez a kiegészítő kézikönyv az új, `// TANANYAG –`, `# TANANYAG –` és `REM TANANYAG -` megjegyzéseket egészíti ki. A hallgatók **az eredeti C#-utasításokat**, a HTTP-átvitelt és a szerveroldali biztonsági döntéseket tanulmányozzák. A ZIP működő AI-modelleket nem tartalmaz; a .NET API a külön telepített OmegaAI-t hívja.

## 1. Az alkalmazás öt rétege

1. **Indítás – `Program.cs`**: konfigurációk, függőséginjektálás, Swagger, HTTP méretkorlátok, middleware, routing.
2. **Hitelesítés – `Infrastructure/ClientKeyMiddleware.cs`**: `X-Meeting-Key` feldolgozása, kliens-/tenant-hozzárendelés, 401/503 válaszok.
3. **HTTP-végpontok – `Controllers/*.cs`**: felhasználói kérések fogadása, validáció, JSON/multipart műveletek, eredmények lekérése.
4. **AI-közvetítő – `Infrastructure/OmegaAiGateway.cs`**: belső fejléc, biztonságos URL, HTTP hiba- és SSE-kezelés, alapállapot.
5. **Adatszerződés – `Models/*.cs`**: bejövő DTO-k, adatannotációs validáció, privát konfiguráció típusa.

### 1.1. Mit jelent a függőséginjektálás?

A vezérlő így kezdődik: `public sealed class AiController(OmegaAiGateway omega)`. Nem hoz létre `new HttpClient()` vagy `new OmegaAiGateway()` példányt. A `Program.cs` regisztrálja a gateway-t `AddHttpClient<OmegaAiGateway>` hívással; ezért a keretrendszer megfelelően előállítja, amikor a vezérlőre szükség van. Előnye: központi konfiguráció, tesztelhetőség és a hálózati kapcsolatok szakszerű kezelése.

## 2. Teljes hangfeldolgozási életciklus

1. A kliens `POST /api/meetings` kérést küld `multipart/form-data` törzzsel: `Audio`, `Title`, `StartedAt`, `Diarize`, `Summarize`.
2. A `ClientKeyMiddleware` ellenőrzi az `X-Meeting-Key` fejlécet. Siker esetén elmenti a `ClientOptions` objektumot a kérés kontextusába.
3. A `MeetingsController.Upload` ellenőrzi, hogy a fájl nem üres és a maximális méreten belül van, majd új multipart kérésbe csomagolja az adatokat.
4. A **tenantot nem a kliens diktálja**: a `RequestClient.Get(HttpContext)` a szerver által beállított TenantId-t adja.
5. Az `OmegaAiGateway` hozzáteszi a belső `X-Api-Key` és `X-Tenant-Key` fejléceket, és a `POST /v1/audio/jobs` végpontot hívja.
6. Az OmegaAI várhatóan `HTTP 202 Accepted` választ ad. Ekkor **még nincs kész átirat**: van `id` és várakozási információ (`jobs_ahead`).
7. A kliens időnként `GET /api/meetings/{id}` kéréssel, vagy élő SSE kapcsolattal (`GET /api/meetings/{id}/events`) követheti a sorpozíciót és az aktuális Whisper/pyannote/Qwen lépéseket.
8. `completed` után külön kérhető az átirat és az összesítő. `failed` esetén a státusz üzenet segít a hibakeresésben.

**Hallgatói ellenőrző kérdés:** miért nem elegendő a POST 202-es eredménye ahhoz, hogy a kliens „Kész” állapotot mutasson? Mert az aszinkron feldolgozás csak sorba került, a művelet még nem fejeződött be.

## 3. Fájlok és szerepük

| Fájl | Mit mutass be? | Tipikus hiba vagy tanulság |
|---|---|---|
| `Program.cs` | Szolgáltatások, Swagger, Kestrel, middleware sorrend | Ha hiányzik a middleware, a vezérlő nem találja a hitelesített klienst. |
| `ClientKeyMiddleware.cs` | HTTP-fejléc, állandó idejű összehasonlítás, tenantkötés | A 401 és a 503 nem ugyanaz: az egyik hibás kulcs, a másik konfiguráció. |
| `OmegaAiGateway.cs` | HTTP kliens, két belső kulcs, URL-összeállítás, válaszkódok | A 127.0.0.1 mindig az **adott szerveren** lévő szolgáltatást jelenti. |
| `MeetingsController.cs` | Multipart továbbítás, státusz, eredmények, lemondás | A `jobs_ahead` sorpozíciót az OmegaAI számolja, nem a kliens. |
| `AiController.cs` | Hagyományos JSON vs. SSE stream | A Swagger nem minden esetben jelenít meg SSE-részleteket élőben. |
| `PeopleController.cs` | Személyek, hangminták, hozzájárulás, bináris letöltés | A hangminta érzékeny adat, a tárolás és megőrzés jogszerűsége külön feladat. |
| `SpeakerIdentificationController.cs` | Beszélőazonosítási javaslat és kézi jóváhagyás | A `similarity_percent` **nem bizonyított személyazonossági valószínűség**. |
| `SystemController.cs` | Saját életjel, OmegaAI állapot, queue, modellek | A „modellfájl megvan” ≠ „valódi MP3 átírás sikeres”. |
| `Contracts.cs` | DTO-k, `[Required]`, `[Range]`, IFormFile | Az érvénytelen kérés gyakran 400-as válaszként megáll a vezérlő előtt. |
| `MeetingOptions.cs` | Típusos konfiguráció | A titkos kulcsokat soha ne írd kliensoldali JavaScriptbe. |
| `scripts/Configure.ps1` | Kulcsgenerálás és tenant-regisztráció | A generált fájlt a private mappában kell őrizni. |
| `scripts/TestApi.ps1` | Automata HTTP-próba, feltöltés, polling | A `completed` meglétét ellenőrizni kell a fájlmentés előtt. |
| `scripts/*.bat` | Egyszerű indítás, ellenőrzés, publish | A BAT ASCII és BOM-mentes maradt a korábbi CMD-kódolási hibák miatt. |

## 4. Mit jelent a JSON, a multipart és az SSE?

**JSON:** szöveges, kulcs–érték párokból álló adatcsere-formátum. A chatnél `{"prompt":"..."}` megy a szerverre, és `{"answer":"..."}` jellegű válasz érkezik. Az UTF-8 kezeli a magyar ékezeteket. **Multipart/form-data:** bináris fájl és kísérő szöveges mezők egyetlen HTTP-kérésben. MP3-at nem célszerű JSON-stringgé alakítani. **SSE:** a szerver hosszú HTTP-kapcsolaton, részletekben küld eseményeket; a gateway `FlushAsync` hívása segít, hogy a kliens ne csak a legvégén lássa a progresszt.

## 5. A HTTP hibakódok értelmezése

| Kód | Jelentés | Lehetséges ok |
|---|---|---|
| 200 | Sikeres lekérdezés | Az állapot vagy kész eredmény visszaérkezett. |
| 202 | Befogadva | A hang a sorban vár vagy később indul. |
| 400 | Hibás bemenet | Hiányzó cím, érvénytelen mező. |
| 401 | Nincs megfelelő klienskulcs | `X-Meeting-Key` hiányzik/hibás. |
| 404 | Nem található | Hibás jobId, még nem elkészült vagy nem saját erőforrás. |
| 413 | Túl nagy feltöltés | A konfigurációban megadott mérethatár túllépése. |
| 429 | Túl sok kérés | Az OmegaAI túlterhelési korlátja. |
| 503 | Szolgáltatás nem elérhető | OmegaAI leállt, vagy nincs tenantkonfiguráció. |
| 504 | Időtúllépés | A háttérhívás túllépte a megengedett várakozást. |

## 6. Sorbanállás: mit mutat a kliensnek a két API?

A `GET /api/queue` csak a központi terhelés darabszámát adja; **más tenantok azonosítóit elrejti**. A konkrét megbeszélés `GET /api/meetings/{id}` válasza saját `jobs_ahead` mezőt tartalmazhat, például `2`, ha egy aktív és egy várakozó munka van előtte. Amikor a feladat fut, a feladat progress mezői szolgálnak a szakaszonkénti előrehaladáshoz; a beszélőszétválasztásnál a tényleges belső lépéseket mutatjuk, nem kitalált százalékot.

## 7. Személyek és hangminták: miért tenantonként?

A MeetingNotesAPI egyetlen központi OmegaAI-t hív, de az OmegaAI-ban külön személytár juthat az egyes alkalmazásoknak. A `ClientOptions` tartalmazza az alkalmazás `TenantId` és `TenantKey` értékét. A web- és mobilkliensek csak a saját .NET API-hitelesítésüket ismerik; az OmegaAI belső kulcsait **nem**.

A hangminták regisztrálásánál a személy hozzájárulását ellenőrizni kell; a hangmintás azonosítás javaslat, emberi jóváhagyással. Az OmegaAI hangprofiljaihoz legfeljebb 20 minta/személy az eddig kialakított korlát.

## 8. Oktatási bemutató 15–20 percben

1. `Program.cs` – mutasd meg az `AddControllers`, `AddHttpClient`, `UseMiddleware` és `MapControllers` sorokat.
2. `ClientKeyMiddleware.cs` – küldj Swaggerből rossz kulcsot; magyarázd el a HTTP 401-et.
3. `SystemController.cs` – mutasd meg, mi a különbség a saját health és az OmegaAI health között.
4. `AiController.cs` – küldj rövid magyar Qwen kérdést és hasonlítsd össze a teljes JSON választ az SSE-vel.
5. `MeetingsController.cs` – tölts fel teszt-MP3-at, figyeld a `202`, `id`, `jobs_ahead` mezőket.
6. `OmegaAiGateway.cs` – keresd meg az `X-Tenant-Key`, `ResponseHeadersRead`, `FlushAsync` sorokat.
7. `PeopleController.cs` – magyarázd el a személy, hangminta és hozzájárulás különbségét.

**Külön a konfigurációs JSON-ok teljes mezőmagyarázata:** [BEALLITASOK_SORONKENT_HU.md](BEALLITASOK_SORONKENT_HU.md).

## 9. Tesztelés és bizonyítottság

A kommentálás nem változtatja meg az eredeti C# és szkriptutasításokat. A Pythonos forrásszintű tesztek vizsgálják az eredeti API-szerződést és a kommentek épségét, de **ez önmagában nem .NET 10 build**. A célgépen `scripts/06_BUILD_ELLENORZES.bat` segítségével kell valóban fordítani; az AI-eredményt csak az OmegaAI telepítés és egy sikeres MP3-feldolgozás bizonyítja.
