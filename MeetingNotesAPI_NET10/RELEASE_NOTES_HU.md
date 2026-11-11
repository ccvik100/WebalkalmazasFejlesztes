# MeetingNotesAPI 1.0 – átadási és ellenőrzési jegyzőkönyv

- **Célkeretrendszer:** .NET 10 (ASP.NET Core Web API)
- **Projekt:** `MeetingNotesAPI/MeetingNotesAPI.csproj`; solution `MeetingNotesAPI.slnx`
- **Swagger fejlesztői gépen:** `http://localhost:5200/swagger`
- **OmegaAI:** a meglévő v1.6 Python REST, `http://127.0.0.1:8768` (nem része ennek a ZIP-nek)
- **Ellenőrzés:** 12/12 Python statikus/regressziós teszt sikeres. Az OmegaAI szerződésének 36 route-ját a tényleges v1.6 forrásból vettük és a megfelelő hívásokat ellenőriztük.
- **Nem ellenőrzött itt:** `dotnet restore`, `dotnet build`, Visual Studio-futtatás, Windows PowerShell 5.1 valódi futtatása, IIS telepítés és tényleges modell-inferencia. A forráscsomagban `scripts/06_BUILD_ELLENORZES.bat` és `scripts/04_TEST_API.bat` végzi el ezeket Windows alatt.
- **Biztonság:** per-tenant tesztkliens kulcs; OmegaAI kulcsok privát konfigurációban, `wwwroot`-on kívül; SSE és feladatlekérdezések a tenant kontextusával.
- **Éles kliensauth még nincs:** a `X-Meeting-Key` fejlesztői/integrációs célra használható; webes és mobilos kliensbe nem helyezhető. Következő fázis: JWT/OIDC, szerepkörök, audit és sebességkorlátozás.
- **NuGet:** `Swashbuckle.AspNetCore` 10.3.1. A NuGet visszaállításhoz első buildnél internet kell; a futó API nem használ külső felhős AI-t.


## Oktatói kommentált forráskód – 2026. november

Az eredeti 1.0-s funkciók és végpontok megmaradtak. **592 új, célzott forráskomment** került közvetlenül a C#, PowerShell, Windows BAT és csproj állományokba (379 C# + 122 PowerShell + 74 BAT + 17 XML komment). Külön markdown dokumentáció ismerteti az összes JSON beállítás szerepét és a teljes kód működését.

A `tests/test_kommentek_valtozatlan_kod.py` SHA-256 ellenőrzéssel bizonyítja, hogy az oktatói megjegyzések eltávolítása után az eredeti C# és futtatható parancsfájlok programutasításai változatlanok maradnak. **18/18 Python teszt sikeres.** Ez nem helyettesíti a Windowsos .NET 10 buildet vagy az OmegaAI-val végzett valós inferenciatesztet.
