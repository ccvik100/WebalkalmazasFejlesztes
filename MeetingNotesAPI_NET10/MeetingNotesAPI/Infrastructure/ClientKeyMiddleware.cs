// ================================================================
// OKTATÓI FORRÁSKÓD – Kliensazonosítás és tenantbiztonság
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – A kulcsok időben állandó összehasonlításához használt kriptográfiai függvény névtere.
using System.Security.Cryptography;
// TANANYAG – A szöveges kulcsokat UTF-8 bájtsorrá alakítjuk az összehasonlításhoz.
using System.Text;
// TANANYAG – ClientOptions és MeetingOptions konfigurációs osztályok importálása.
using MeetingNotesAPI.Models;
// TANANYAG – Az IOptions típuson keresztül jutunk a konfiguráció aktuális értékeihez.
using Microsoft.Extensions.Options;

// TANANYAG – Az infrastruktúra réteg elválasztja a belépésvédelmet a konkrét vezérlőktől.
namespace MeetingNotesAPI.Infrastructure;

// TANANYAG – A RequestDelegate next a csővezeték következő lépcsője; ha megengedett a kérés, ezt hívjuk.
/// <summary>
/// Oktatási/első integrációs kulcshitelesítés. Minden későbbi kliensnek KÜLÖN kulcsot adunk.
/// A felhasználói belépés és szerepkörkezelés később JWT/OIDC-re bővíthető.
/// </summary>
public sealed class ClientKeyMiddleware(RequestDelegate next)
{
    // TANANYAG – Azonos kulcson tároljuk a sikeresen felismert klienst a kérés HttpContext.Items gyűjteményében.
    public const string ContextName = "MeetingNotes.Client";

    // TANANYAG – Minden beérkező HTTP-kérésnél az ASP.NET Core automatikusan meghívja ezt a metódust.
    public async Task InvokeAsync(HttpContext context, IOptions<MeetingOptions> options)
    {
        // TANANYAG – Csak az /api útvonalakat kell az API-kulccsal védeni; pl. a Swagger UI nem ide tartozik.
        if (!context.Request.Path.StartsWithSegments("/api") ||
            // TANANYAG – A /api/health/live kivétel: így akkor is látszik, fut-e a .NET folyamat, ha az AI-kulcs hibás.
            (context.Request.Path.Value?.Equals("/api/health/live", StringComparison.OrdinalIgnoreCase) == true))
        {
            // TANANYAG – A next(context) továbbengedi a kérést a következő middleware vagy vezérlő felé.
            await next(context);
            // TANANYAG – A return miatt a kivételként kezelt kérésnél nem fut le az alábbi kulcsellenőrzés.
            return;
        }
        // TANANYAG – A felhasználói HTTP X-Meeting-Key fejlécet beolvassa; ez a kliensalkalmazás külön titkos kulcsa.
        var supplied = context.Request.Headers["X-Meeting-Key"].ToString();
        // TANANYAG – A match addig null, amíg egy beállított kliens kulcsával nem találtunk egyezést.
        ClientOptions? match = null;
        // Fix idejű összehasonlítás; a naplóba SOHA nem írjuk a kulcsot.
        // TANANYAG – Csak értelmes hosszúságú kulcsot ellenőrzünk; túl rövid érték sosem fogadható el.
        if (supplied.Length >= 40 && supplied.Length <= 512)
        {
            // TANANYAG – A konfigurációban több kliens lehet, mindegyikhez saját tenantazonosító és kulcs tartozik.
            foreach (var client in options.Value.Clients)
            {
                // TANANYAG – A gyenge/túl rövid szerveroldali kulcsot sem fogadjuk el.
                if (client.ClientKey.Length < 40) continue;
                // TANANYAG – A beérkezett kulcs bájtjait készíti elő az összehasonlításhoz.
                byte[] a = Encoding.UTF8.GetBytes(supplied);
                // TANANYAG – Az éppen vizsgált szerveroldali klienskulcs bájtjait készíti elő.
                byte[] b = Encoding.UTF8.GetBytes(client.ClientKey);
                // TANANYAG – A FixedTimeEquals az egyezést időzítésfüggő kilépés nélkül vizsgálja, ha a hosszak megegyeznek.
                if (a.Length == b.Length && CryptographicOperations.FixedTimeEquals(a, b))
                {
                    // TANANYAG – Sikeres egyezéskor elmentjük a hozzárendelt klienskonfigurációt.
                    match = client;
                    // TANANYAG – A megfelelő kulcs megtalálása után nem kell a többi kliens bejegyzést megvizsgálni.
                    break;
                }
            }
        }
        // TANANYAG – Ha a ciklus nem talált egyezést, a kérés nem hitelesített.
        if (match is null)
        {
            // TANANYAG – A 401 Unauthorized HTTP-státusz jelzi a hiányzó vagy érvénytelen kulcsot.
            context.Response.StatusCode = StatusCodes.Status401Unauthorized;
            // TANANYAG – Egységes JSON hibaüzenet; a tényleges kulcsot soha nem írjuk a válaszba.
            await context.Response.WriteAsJsonAsync(new { error = "Hiányzó vagy érvénytelen X-Meeting-Key." });
            // TANANYAG – A return megállítja a továbbítást, ezért a vezérlő egyáltalán nem fut le.
            return;
        }
        // TANANYAG – A hitelesített kulcshoz a háttérben működő OmegaAI-tenant beállításai is kötelezők.
        if (string.IsNullOrWhiteSpace(match.TenantId) || string.IsNullOrWhiteSpace(match.TenantKey))
        {
            // TANANYAG – 503-as konfigurációs hibát küldünk, nem azt állítjuk, hogy a felhasználó hibázott.
            context.Response.StatusCode = StatusCodes.Status503ServiceUnavailable;
            // TANANYAG – A válasz leírja a hiányzó tenantkonfigurációt titkos értékek kiadása nélkül.
            await context.Response.WriteAsJsonAsync(new { error = "A kliens OmegaAI tenant-beállítása hiányzik." });
            return;
        }
        // TANANYAG – A hitelesített kliens adatait csak az aktuális kérés idejére a HttpContext.Items-be tesszük.
        context.Items[ContextName] = match;
        // TANANYAG – A no-store megakadályozza, hogy a köztes HTTP-cache tárolja az érzékeny API-válaszokat.
        context.Response.Headers["Cache-Control"] = "no-store";
        // TANANYAG – A kulcsellenőrzés után a kérés eljuthat a kiválasztott vezérlőhöz.
        await next(context);
    }
}
// TANANYAG – Külön segédosztály: a vezérlőknek nem kell közvetlenül a HttpContext.Items szótárat kezelni.
public static class RequestClient
{
    // TANANYAG – Egységes metódus az aktuális kérés szerveroldali, hitelesített ClientOptions objektumának elérésére.
    public static ClientOptions Get(HttpContext context) =>
        // TANANYAG – Biztonságos cast: csak ClientOptions típusú objektumot fogad el a tárolóból.
        context.Items[ClientKeyMiddleware.ContextName] as ClientOptions
        // TANANYAG – Ha a middleware nem töltötte fel a kontextust, programozási hibát jelez ahelyett, hogy névtelen tenantot használna.
        ?? throw new InvalidOperationException("A hitelesítési middleware nem futott le.");
}
