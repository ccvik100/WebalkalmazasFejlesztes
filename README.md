# W03 Átirat export

A Webalkalmazás-fejlesztés beadandó W03 feladata az Omega Meeting Notes kész átiratának mentése TXT és JSON formátumban. A weboldalon a feltöltéskor kapott megbeszélés-azonosítóval lehet betölteni az átiratot.

## Indítás demó módban

A futtatáshoz .NET 10 SDK és egy böngésző kell. A projekt az ASP.NET Core beépített Blazor Server funkcióit használja. A repó gyökérmappájában futtasd:

```sh
dotnet run --project BlazorW03 -- --Demo=true
```

Nyisd meg a [helyi oldalt](http://127.0.0.1:3000), majd kattints a **Minta betöltése** gombra. A demó előre megadott szöveget használ, amit az oldal külön jelöl.

## Valódi átirat készítése és exportálása macOS-en

Az indításhoz .NET 10 SDK és a helyben telepített OmegaAI szükséges. Ha már megvan a `MeetingNotesAPI_NET10/MeetingNotesAPI/private/meetingnotes.secrets.json` fájl, nyiss három terminált a repó gyökérmappájában, és indítsd el a szolgáltatásokat ebben a sorrendben:

1. **OmegaAI**

   ```sh
   ./tools/OmegaAI_Install_API/inditas-macos.sh
   ```

2. **MeetingNotesAPI**

   ```sh
   cd MeetingNotesAPI_NET10/MeetingNotesAPI
   dotnet run --no-launch-profile -- --urls http://127.0.0.1:5200
   ```

3. **Blazor**

   ```sh
   export MEETING_API_KEY="$(plutil -extract MeetingNotes.Clients.0.ClientKey raw -o - MeetingNotesAPI_NET10/MeetingNotesAPI/private/meetingnotes.secrets.json)"
   export MEETING_API_URL=http://127.0.0.1:5200
   dotnet run --project BlazorW03
   ```

A terminálok maradjanak nyitva. Mindegyik szolgáltatást a saját termináljában állíthatod le a `Ctrl+C` billentyűkkel.

1. Nyisd meg a [MeetingNotesAPI Swaggert](http://127.0.0.1:5200/swagger). Az `X-Meeting-Key` mezőbe a `MeetingNotesAPI_NET10/MeetingNotesAPI/private/meetingnotes.secrets.json` fájlban lévő `ClientKey` értéket másold. A kulcsot ne tedd a forráskódba vagy a bemutatóba.
2. A `POST /api/meetings` végponton töltsd fel a [mesterséges magyar teszthangot](bemutato/teszthang.mp3). Adj meg címet és időpontot, például `2026-11-10T10:00:00+01:00`. A `Diarize` és a `Summarize` legyen `false`. A HTTP 202 válaszból másold ki az `id` mezőt.
3. A `GET /api/meetings/{id}` végponton ellenőrizd az állapotot. Ha `completed`, nyisd meg a [Blazor oldalt](http://127.0.0.1:3000), írd be az azonosítót, és kattints az **Átirat betöltése** gombra. Mindkét exportgomb elérhető lesz.

## Első beállítás új gépen

1. Kövesd az [OmegaAI macOS útmutatóját](tools/OmegaAI_Install_API/MACOS.md), majd indítsd el az OmegaAI-t. A MeetingNotesAPI projekt a repó gyökerében lévő `MeetingNotesAPI_NET10/MeetingNotesAPI` mappában található.
2. Az [OmegaAI Swaggerben](http://127.0.0.1:8768/docs) hívd meg a `POST /v1/tenants` végpontot. Az `X-Api-Key` az OmegaAI `config/api-key.txt` fájljában található. A kérésben adj meg egy egyedi `tenant_id` értéket és egy `label` mezőt. A válaszból másold ki a `tenant_api_key` értékét.
3. Hozd létre a `MeetingNotesAPI_NET10/MeetingNotesAPI/private` mappát, ha hiányzik. A benne lévő `meetingnotes.secrets.json` fájlt töltsd ki az alábbi minta alapján. A külön `ClientKey` értékét az `openssl rand -hex 32` paranccsal állíthatod elő.

   ```json
   {
     "MeetingNotes": {
       "OmegaAi": {
         "BaseUrl": "http://127.0.0.1:8768",
         "ApiKey": "OMEGAAI_FOKULCS"
       },
       "Clients": [{
         "Name": "W03 Blazor",
         "ClientKey": "GENERALT_KLIENSKULCS",
         "TenantId": "A_REGISZTRALT_TENANT_ID",
         "TenantKey": "A_VALASZBAN_KAPOTT_TENANT_API_KEY"
       }]
     }
   }
   ```

   Ezután indíthatod a MeetingNotesAPI-t és a Blazort a fenti parancsokkal.

## Hol van a megoldás?

- A `BlazorW03/Components/Home.razor` tartalmazza a felületet, az azonosító ellenőrzését és az export összeállítását. A JSON mezői az `id`, `title`, `startedAt` és `transcript`.
- A `BlazorW03/Services/MeetingService.cs` a meglévő MeetingNotesAPI státusz- és átirat-végpontját hívja. A demó ugyanennek a szolgáltatásnak a mintaadatait használja.
- A `BlazorW03/wwwroot/download.js` elindítja a böngészőben a Blazor által elkészített UTF-8 fájl mentését.

## Tesztesetek

A tesztek a demó módban indított alkalmazáson megismételhetők.

| Próba | Lépés | Elvárt eredmény |
| --- | --- | --- |
| Magyar ékezetek | Töltsd be a mintát, és nyisd meg mindkét letöltött fájlt. | A „gyűlés” és „jegyzőkönyv” helyesen jelenik meg mindkettőben. |
| Érvényes JSON | Olvasd be a letöltött JSON-t például a Node.js `JSON.parse` függvényével. | A fájl beolvasható. Benne van a minta címe, időpontja és teljes átirata. |
| Még nincs eredmény | Töltsd be a mintát, majd a `22222222222222222222222222222222` azonosítót. | Az előző átirat eltűnik, a feldolgozásról üzenet jelenik meg, mindkét exportgomb letilt. |
| Ismeretlen azonosító | Kérd le a `99999999999999999999999999999999` azonosítót. | Az oldal jelzi, hogy nincs ilyen megbeszélés, az exportgombok tiltva maradnak. |
| Hibás formátum | Írd be az `abc` azonosítót. | A Blazor ellenőrzi az azonosítót, kiírja a várt formátumot, és kihagyja a MeetingNotesAPI-hívást. |

A megvalósításhoz és a dokumentációhoz Codex kódgeneráló segítséget használtunk.

## Bemutató és ellenőrzés

- [Whisperrel készült átirat és a két exportgomb](bemutato/01-atirat.png)
- [Ismeretlen azonosító és letiltott letöltés](bemutato/02-hibas-azonosito.png)

A demó tesztesetei Chrome-ban sikeresek voltak. A teljes láncot is ellenőriztük a mellékelt mesterséges hanggal. A MeetingNotesAPI HTTP 202 választ adott, a Whisper elkészítette az átiratot, a Chrome-ból mentett TXT és a JSON átiratmezője pedig egyezett az API válaszával. Ismeretlen azonosítónál az API 404-et adott, és a Blazor letiltotta a letöltést.
