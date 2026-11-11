# MeetingNotesAPI – .NET 10 → OmegaAI v1.6

**Csak API.** Blazor / HTML5 / MAUI / Kotlin klienseket később fejlesztünk. A .NET API az OmegaAI helyi szolgáltatását (`http://127.0.0.1:8768`) hívja szerveroldali titkos API-kulcsokkal. Az eredeti AI-modellek a `C:\OmegaAI` könyvtárban maradnak.

**Azonnali sorrend (PowerShell a MeetingNotesAPI projektmappájából):**

```powershell
.\scripts\01_KONFIGURALAS.bat
.\scripts\02_ELLENORZES.bat
.\scripts\06_BUILD_ELLENORZES.bat
.\scripts\03_INDITAS.bat
```

Visual Studio 2026-ban: `MeetingNotesAPI.slnx` megnyitása → F5. Swagger: **http://localhost:5200/swagger**. A `X-Meeting-Key` a privát konfiguráció első klienskulcsa; részletek a `docs\TELEPITES_ES_SWAGGER_HU.md` dokumentumban.

Tesztek: `scripts\04_TEST_API.bat` vagy `scripts\04_TEST_API.bat "C:\Hangok\teszt.mp3"`. Publikálás: `scripts\05_PUBLISH.bat`. A privát kulcsok nem kerülnek a webes `wwwroot` alá és nem részei a publikációnak.

**FONTOS:** a tesztkulcs **nem** felhasználói belépés; éles web-/mobilkliensnél JWT/OIDC és jogosultsági rendszer szükséges.

## Oktatói, közel soronként kommentált forráskiadás

Ez a csomag az eredeti MeetingNotesAPI összes C# programutasítását és a Windowsos telepítő/teszt-szkriptek működését megtartja, és a fontos kódsorokat részletes magyar `TANANYAG` megjegyzésekkel látja el. Az XML-dokumentáció a Swagger számára is megmarad.

**Tanulási sorrend:** `Program.cs` → `Models/Contracts.cs` → `Infrastructure/ClientKeyMiddleware.cs` → `Controllers/SystemController.cs` → `Controllers/AiController.cs` → `Controllers/MeetingsController.cs` → `Infrastructure/OmegaAiGateway.cs` → `Controllers/PeopleController.cs` → `Controllers/SpeakerIdentificationController.cs` → `scripts/`.

- **[Oktatói kódséta](docs/OKTATOI_KODSETANY_HU.md):** magyarázatok, HTTP-kérések teljes útja, SSE, hitelesítés, tipikus hibák, órai bemutató.
- **[Beállítások soronként](docs/BEALLITASOK_SORONKENT_HU.md):** `appsettings.json`, titkos konfiguráció, fejlesztői profil, csproj.
- **[Telepítési útmutató](docs/TELEPITES_ES_SWAGGER_HU.md):** eredeti üzembe helyezési lépések.
- **[Kommentintegritás-teszt](../tests/test_kommentek_valtozatlan_kod.py):** ellenőrzi, hogy az új magyarázó sorok nélkül az eredeti programkód visszaáll.

A JSON konfigurációs fájlokba szándékosan nem kerültek kommentek, mert az érvényteleníthetné a konfigurációt. A Windows BAT-fájlok ékezetmentes ASCII megjegyzéseket kaptak a korábbi BOM- és konzolkódolási hibák elkerülésére.

**Ellenőrzés:** 18 forrásszintű Python-teszt sikeres. A jelen futtatókörnyezet nem tartalmaz .NET 10 SDK-t; a Visual Studio-s fordítást a célgépen a `scripts/06_BUILD_ELLENORZES.bat` segítségével kell elvégezni. Új AI-modelltelepítést ez a kommentált kiadás nem igényel.
