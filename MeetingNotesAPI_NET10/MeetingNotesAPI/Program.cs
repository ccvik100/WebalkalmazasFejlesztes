// ================================================================
// OKTATÓI FORRÁSKÓD – Indítás és függőséginjektálás
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – Betölti a saját infrastruktúra névteret: itt található az OmegaAI közvetítő és a kulcsellenőrző middleware.
using MeetingNotesAPI.Infrastructure;
// TANANYAG – A konfigurációs típusokat (MeetingOptions, ClientOptions) teszi elérhetővé a programindítónak.
using MeetingNotesAPI.Models;
// TANANYAG – A FormOptions a több részből álló fájlfeltöltések mérethatárához szükséges.
using Microsoft.AspNetCore.Http.Features;
// TANANYAG – Az IOptions a konfiguráció típusosan átadott értékeinek kezeléséhez használt .NET-megoldás.
using Microsoft.Extensions.Options;

// TANANYAG – Létrehozza az ASP.NET Core alkalmazásépítőt; az args tartalmazhat indítási paramétereket is.
var builder = WebApplication.CreateBuilder(args);

// Külső publikus konfiguráció + csak szerveren található titkos konfiguráció.
// A private fájl SOSEM kerül a wwwroot könyvtárba, és a .csproj nem publikálja.
// TANANYAG – A publikus appsettings után hozzáadja a titkos szerveroldali JSON-fájlt; optional=true miatt helyi build titkok nélkül is indulhat, reloadOnChange az újraolvasás.
builder.Configuration.AddJsonFile("private/meetingnotes.secrets.json", optional: true, reloadOnChange: true);
// TANANYAG – A MeetingNotes szakaszt MeetingOptions objektummá köti; ezután a szolgáltatások IOptions<MeetingOptions> útján olvassák.
builder.Services.Configure<MeetingOptions>(builder.Configuration.GetSection("MeetingNotes"));

// TANANYAG – Felveszi az MVC vezérlőket, hogy az [HttpGet]/[HttpPost] attribútumok REST-végpontokká váljanak.
builder.Services.AddControllers();
// TANANYAG – Az API-végpontok metaadatai a Swagger/OpenAPI dokumentálását segítik.
builder.Services.AddEndpointsApiExplorer();
// TANANYAG – Beállítja a Swagger-generátort; az alábbi lambda a létrejövő API-dokumentációt finomhangolja.
builder.Services.AddSwaggerGen(config =>
{
    // A részletes magyar C# XML megjegyzések közvetlenül a Swaggerben is láthatók.
    // TANANYAG – A build által előállított XML dokumentáció teljes útvonalát szerkeszti meg a futtatási mappából.
    var xml = Path.Combine(AppContext.BaseDirectory, "MeetingNotesAPI.xml");
    // TANANYAG – Ha az XML létrejött, beemeli a C# /// <summary> magyarázatokat a Swagger felületre.
    if (File.Exists(xml)) config.IncludeXmlComments(xml);
});
// TANANYAG – Az HttpClientFactory itt típushoz kötött HttpClientet regisztrál, így a közös OmegaAiGateway kezeli a hálózati hívásokat.
builder.Services.AddHttpClient<OmegaAiGateway>(client =>
{
    // Az 8 perces hang átirata CPU-n akár hosszabb is lehet; a SSE kérések maradjanak nyitva.
    // A felhasználói megszakítást a HttpContext.RequestAborted továbbítja.
    // TANANYAG – A HTTP kliens saját globális idejét végtelenre állítja, mert SSE hosszú ideig él; a kérést továbbra is a kliens lemondása szakítja meg.
    client.Timeout = Timeout.InfiniteTimeSpan;
});

// TANANYAG – A MaxUploadMb beállítást olvassa; ha nincs megadva, 100 MB az alapérték.
var maxMb = builder.Configuration.GetValue("MeetingNotes:MaxUploadMb", 100);
// TANANYAG – Biztonsági korlát: 1 és 1000 MB közé szorítja a konfigurációból kapott értéket.
maxMb = Math.Clamp(maxMb, 1, 1000);
// TANANYAG – A Kestrel HTTP-szerver teljes kérésméret-limitjét bájtban állítja; a +10 MB a multipart fejlécek és kísérő mezők tartaléka.
builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = (long)(maxMb + 10) * 1024 * 1024);
// TANANYAG – Külön a multipart/form-data feldolgozó méretlimitjét emeli; a két limit eltérő feldolgozási rétegre vonatkozik.
builder.Services.Configure<FormOptions>(o => o.MultipartBodyLengthLimit = (long)(maxMb + 10) * 1024 * 1024);

// TANANYAG – A korábban regisztrált szolgáltatásokból létrehozza a ténylegesen futó ASP.NET Core alkalmazást.
var app = builder.Build();

// TANANYAG – A konfigurációs kapcsoló dönti el, hogy a Swagger tesztfelület elérhető-e; éles környezetben ezt külön mérlegeljük.
if (builder.Configuration.GetValue("MeetingNotes:EnableSwagger", true))
{
    // TANANYAG – Kiszolgálja az OpenAPI JSON-dokumentumot, amelyet a Swagger UI felhasznál.
    app.UseSwagger();
    // TANANYAG – A /swagger felület a megadott JSON végpontból építi fel a kattintható API-próbákat.
    app.UseSwaggerUI(ui => { ui.SwaggerEndpoint("/swagger/v1/swagger.json", "MeetingNotesAPI v1"); });
}

// A fejlécet minden /api végpontnál kötelező ellenőrizni (az élő health kivételével).
// TANANYAG – A saját hitelesítési middleware minden vezérlőhívás ELŐTT fut: először azonosítja a kliensalkalmazást.
app.UseMiddleware<ClientKeyMiddleware>();
// TANANYAG – Regisztrálja a vezérlők attribútumokkal megadott URL-jeit a routerben.
app.MapControllers();
// TANANYAG – A gyökércímről a Swaggerre irányít át; ez csak fejlesztői kényelmi végpont.
app.MapGet("/", () => Results.Redirect("/swagger"));

// TANANYAG – Elindítja a webszervert; ettől kezdve HTTP-kéréseket fogad a beállított porton.
app.Run();

// ASP.NET Core integrációs teszteknél felhasználható típus.
// TANANYAG – A partial Program lehetővé teszi, hogy egy későbbi integrációs teszt a WebApplicationFactory segítségével megtalálja az indítópontot.
public partial class Program { }
