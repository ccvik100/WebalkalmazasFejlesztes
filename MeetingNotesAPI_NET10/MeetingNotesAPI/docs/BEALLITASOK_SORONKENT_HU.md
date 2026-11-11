# MeetingNotesAPI – a konfigurációk soronkénti magyarázata

**Fontos:** az `appsettings*.json` és `launchSettings.json` fájlokban szándékosan **nincsenek `//` kommentek**, mert az ilyen szöveg egyes JSON-feldolgozókat megzavarhat. A program az eredeti, érvényes konfigurációval marad futtatható. A következő leírás a fájlok mezőit külön magyarázza.

## `appsettings.json`

| JSON mező | Mire való? | Miért fontos? |
|---|---|---|
| `MeetingNotes` | A saját API összes beállításának gyökere. | A `Program.cs` ezt köti a `MeetingOptions` osztályhoz. |
| `MeetingNotes.OmegaAi.BaseUrl` | A központi helyi AI REST API címe, alapból `http://127.0.0.1:8768`. | Ugyanazon a szerveren a .NET API a Python szolgáltatáshoz kapcsolódik. |
| `MeetingNotes.OmegaAi.ApiKey` | A belső OmegaAI főkulcs mezője. | **A publikus JSON-ban üres!** A titkos érték a `private/meetingnotes.secrets.json` fájlból töltődik be. |
| `MeetingNotes.Clients` | Regisztrált kliensalkalmazások beállításai. | A kliensnek X-Meeting-Key, a háttérnek tenantazonosító és külön tenantkulcs jár. |
| `MeetingNotes.MaxUploadMb` | A legnagyobb megbeszélés-feltöltés mérete megabájtban. | A `MeetingsController` ellenőrzi a fájl hosszát. |
| `MeetingNotes.EnableSwagger` | A böngészős Swagger tesztfelület bekapcsolása. | Az első fejlesztési teszthez kényelmes; éles üzemben mérlegelni kell a láthatóságát. |
| `Kestrel.Limits.MaxRequestBodySize` | A teljes HTTP-kéréstörzs felső mérethatára bájtban. | Nem ugyanaz, mint a hangfájl külön üzleti limitje. |
| `Logging.LogLevel.Default` | A saját alkalmazás alap naplózási részletessége. | Hibaelhárításkor több adatot kérhetünk. |
| `Logging.LogLevel.Microsoft.AspNetCore` | A keretrendszer naplózási részletessége. | Csökkenti a rutin HTTP-események zaját. |
| `AllowedHosts` | A webalkalmazás elfogadott Host-fejléceinek beállítása. | IIS/HTTPS előtt környezetfüggően szigorítandó. |

## `appsettings.Development.json`

A `Development` környezethez tartozó kiegészítő beállításokat tartalmazza. A .NET az alap `appsettings.json` után olvassa be, így fejlesztés közben felülírható egy-egy érték anélkül, hogy az éles szerverre azonos konfiguráció kerülne.

## `private/meetingnotes.secrets.json` (csak telepítés után keletkezik)

Ezt a fájlt a `scripts/01_KONFIGURALAS.bat` és a `Configure.ps1` hozza létre, **a ZIP nem tartalmazhat működő titkos kulcsot**. Soha ne másold a wwwroot mappába, ne töltsd fel Git-re és ne add át kliensalkalmazásnak.

- `MeetingNotes.OmegaAi.ApiKey`: a belső OmegaAI főkulcsa; csak a backend olvassa.
- `MeetingNotes.OmegaAi.BaseUrl`: a ténylegesen használt belső OmegaAI-cím.
- `MeetingNotes.Clients[i].Name`: kliensalkalmazás neve.
- `MeetingNotes.Clients[i].ClientKey`: a kliens által a `X-Meeting-Key` fejlécben küldött titok.
- `MeetingNotes.Clients[i].TenantId`: az OmegaAI saját, elkülönített alkalmazásadat-tárának azonosítója.
- `MeetingNotes.Clients[i].TenantKey`: a .NET API által az OmegaAI felé továbbított `X-Tenant-Key`.

## `Properties/launchSettings.json`

A Visual Studio és a `dotnet run` által használható fejlesztői indítási profil. Az `applicationUrl` alapértéke `http://localhost:5200`; ez a **MeetingNotesAPI** címe, nem az OmegaAI 8768-as portja. A beállított `ASPNETCORE_ENVIRONMENT=Development` fejlesztői módban lehetővé teszi a részletesebb diagnosztikát.

## `MeetingNotesAPI.csproj`

Ez XML, tehát a magyarázatok közvetlenül `<!-- TANANYAG: ... -->` kommentekként kerültek bele. A fontos sorok: `net10.0` célkeretrendszer, Swagger NuGet csomag, XML dokumentáció generálása, `private` könyvtár publikálásának tiltása.

## Milyen adat honnan jön?

```text
Böngésző / MAUI / Kotlin
  X-Meeting-Key: az adott kliens kulcsa
        |
        v
MeetingNotesAPI :5200
  ClientKeyMiddleware -> hitelesített ClientOptions
  OmegaAiGateway -> X-Api-Key + X-Tenant-Key
        |
        v
OmegaAI :8768
  Whisper / pyannote / Qwen / alkalmazásonkénti hangprofilok
```

A két külön kulcs szerepe szándékosan más: **az X-Meeting-Key a saját alkalmazásunkhoz azonosít**, míg **az X-Api-Key és X-Tenant-Key csak belső, szerver–szerver kommunikációhoz tartozik**.
