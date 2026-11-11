// ================================================================
// OKTATÓI FORRÁSKÓD – MeetingsController
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – Az Encoding.UTF8 szükséges a magyar cím és dátum szöveges multipart mezőinek helyes kódolásához.
using System.Text;
// TANANYAG – Az OmegaAiGateway az egyetlen továbbító réteg a Python REST API felé.
using MeetingNotesAPI.Infrastructure;
// TANANYAG – Az UploadMeetingRequest és SpeakerNamesRequest adatmodellek itt használhatók.
using MeetingNotesAPI.Models;
// TANANYAG – Az [HttpGet], [HttpPost], [FromForm] stb. attribútumokhoz szükséges MVC névtér.
using Microsoft.AspNetCore.Mvc;
// TANANYAG – Az IOptions segítségével a fájlfeltöltési korlátot a konfigurációból olvassuk.
using Microsoft.Extensions.Options;

// TANANYAG – A vezérlő névtere a többi REST-vezérlőtől ugyanazon gyűjtőben tartja a kódot.
namespace MeetingNotesAPI.Controllers;

// TANANYAG – Automatikus API-adatérvényesítést és Swagger-kompatibilis vezérlőműködést kapcsol.
[ApiController]
// TANANYAG – A megbeszélésekhez tartozó összes végpont /api/meetings útvonal alatt lesz.
[Route("api/meetings")]
// TANANYAG – A gateway és a beállítások a konstruktorból kapott, DI által kezelt szolgáltatások.
public sealed class MeetingsController(OmegaAiGateway omega, IOptions<MeetingOptions> settings) : ControllerBase
{
    // TANANYAG – A Swaggernek és a modellkötőnek jelzi, hogy fájlfeltöltéses (multipart/form-data) kérés érkezik.
    // TANANYAG – Az MVC form-beolvasás felső határa; ettől független a konfigurációs MaxUploadMb tényleges üzleti limit.
    // TANANYAG – A kulcs X-Meeting-Key fejlécből, a további mezők az űrlapból jönnek; a middleware már hitelesített.
    /// <summary>Hang feltöltése, sorba állítása. HTTP 202 + id + jobs_ahead; az átirat még nem készült el.</summary>
    [HttpPost]
    [Consumes("multipart/form-data")]
    [RequestFormLimits(MultipartBodyLengthLimit = 115_343_360)]
    public async Task<IResult> Upload([FromHeader(Name="X-Meeting-Key")] string key,
        // TANANYAG – A [FromForm] alakítja az űrlap audio/title/startedAt mezőit erősen típusos UploadMeetingRequest objektummá.
        [FromForm] UploadMeetingRequest body)
    {
        // TANANYAG – Nem fogadunk el üres hangfájlt, mert annak nincs értelmezhető átirata.
        if (body.Audio is null || body.Audio.Length == 0)
            // TANANYAG – Hibás bemenet esetén 400-as választ küldünk és nem terheljük az AI-t.
            return Results.BadRequest(new { error = "Adj meg nem üres hangfájlt." });
        // TANANYAG – A fájl hosszát bájtban összevetjük a konfigurációban megadott MB-határral.
        if (body.Audio.Length > (long)settings.Value.MaxUploadMb * 1024 * 1024)
            // TANANYAG – 413 (Payload Too Large) jelzi, hogy a fájl túl nagy az API számára.
            return Results.Json(new { error = "A fájl túl nagy." }, statusCode: 413);
        // TANANYAG – A szövegmezők hosszát és a cím kötelező voltát ellenőrzi az API-szerver.
        if (body.StartedAt.Length > 80 || body.Title.Length > 150 || string.IsNullOrWhiteSpace(body.Title))
            // TANANYAG – Hibás cím/dátum esetén szintén 400-as választ ad; nem kerül a munkasorba a kérés.
            return Results.BadRequest(new { error = "A cím vagy a dátum túl hosszú/hiányzik." });
        // TANANYAG – A korábbi kulcshitelesítéshez rendelt kliens/tenant azonosítót kapjuk meg – ez nem a böngésző által küldött tenant.
        var client = RequestClient.Get(HttpContext);
        // TANANYAG – Új multipart törzset állítunk össze, amelyet az OmegaAI már a saját adatmezőivel kap meg.
        using var multipart = new MultipartFormDataContent();
        // TANANYAG – Megnyitjuk a feltöltött fájlt olvasható streamként, így nem alakítjuk teljes stringgé vagy base64 adattá.
        var audio = new StreamContent(body.Audio.OpenReadStream());
        // TANANYAG – A Content-Type fejléc megadása segíti a hangformátum helyes továbbítását.
        audio.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(
            // TANANYAG – Ha a kliens audio/* MIME-típust küldött, megtartjuk, különben általános octet-streamet használunk.
            body.Audio.ContentType.StartsWith("audio/", StringComparison.OrdinalIgnoreCase) ? body.Audio.ContentType : "application/octet-stream");
        // Kötelező multipart mező; a tenantot a szerver rendeli hozzá, nem a kliens.
        // TANANYAG – A hangot audio néven és megtisztított fájlnévvel adjuk hozzá az OmegaAI formhoz.
        multipart.Add(audio, "audio", Path.GetFileName(body.Audio.FileName));
        // TANANYAG – A cím magyar karakterei UTF-8 kódolással kerülnek a multipart mezőbe.
        multipart.Add(new StringContent(body.Title, Encoding.UTF8), "title");
        // TANANYAG – A dátumot az OmegaAI által elvárt started_at mezőnévvel továbbítjuk.
        multipart.Add(new StringContent(body.StartedAt, Encoding.UTF8), "started_at");
        // TANANYAG – A diarize kapcsoló megadja, kérünk-e beszélőszétválasztást (nem feltétlenül személyazonosítást).
        multipart.Add(new StringContent(body.Diarize ? "true" : "false"), "diarize");
        // TANANYAG – A summarize kapcsoló szabályozza, készüljön-e a Qwen segítségével magyar összesítő.
        multipart.Add(new StringContent(body.Summarize ? "true" : "false"), "summarize");
        // TANANYAG – A tenant_id mezőt a hitelesített szerverkonfiguráció adja meg; ezzel elkülönítjük az alkalmazások adatait.
        multipart.Add(new StringContent(client.TenantId), "tenant_id");
        // TANANYAG – Az OmegaAI POST /v1/audio/jobs végpontja 202-es választ és feladatazonosítót adhat.
        return await omega.ForwardAsync(HttpContext, HttpMethod.Post, "/v1/audio/jobs", client,
            // TANANYAG – A már összeállított multipart tartalmat továbbítjuk; a Gateway hozzáteszi a titkos OmegaAI fejléceket.
            requestContent: multipart);
    }

    // TANANYAG – GET /api/meetings/{id} a feladat aktuális sorpozícióját és munkafázisát kéri.
    /// <summary>Állapot: queued/running/completed/failed, sorpozíció és szakaszonkénti progress.</summary>
    [HttpGet("{id}")]
    public Task<IResult> Status([FromHeader(Name="X-Meeting-Key")] string key, string id) =>
        // TANANYAG – Az Encode az URL-be illeszthetővé teszi az azonosítót; a RequestClient a saját tenantot biztosítja.
        omega.ForwardAsync(HttpContext, HttpMethod.Get, $"/v1/jobs/{OmegaAiGateway.Encode(id)}", RequestClient.Get(HttpContext));

    // TANANYAG – A text/event-stream jelölés a progress események élő, nyitott kapcsolaton érkezését jelenti.
    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Feladat progress + Qwen tokenek SSE eseményekben, megszakításig nyitott kapcsolat.</summary>
    [HttpGet("{id}/events")]
    [Produces("text/event-stream")]
    public async Task Events([FromHeader(Name="X-Meeting-Key")] string key, string id) =>
        // TANANYAG – Az SSE gateway az OmegaAI progress és Qwen eseményeit változatlan sorrendben továbbítja.
        await omega.ForwardSseAsync(HttpContext, $"/v1/jobs/{OmegaAiGateway.Encode(id)}/events", RequestClient.Get(HttpContext));

    // TANANYAG – A kész átiratot text/plain formában kérjük; ez nem JSON.
    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Kész szöveges átirat. A feladat befejezése előtt 404 lehet.</summary>
    [HttpGet("{id}/transcript")]
    [Produces("text/plain")]
    public Task<IResult> Transcript([FromHeader(Name="X-Meeting-Key")] string key, string id) =>
        // TANANYAG – Az átiratot a megfelelő feladatazonosító alapján tölti le az OmegaAI-ból.
        omega.ForwardAsync(HttpContext, HttpMethod.Get, $"/v1/jobs/{OmegaAiGateway.Encode(id)}/transcript", RequestClient.Get(HttpContext));

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Időbélyegek és speaker címkék JSON tömbje.</summary>
    [HttpGet("{id}/segments")]
    public Task<IResult> Segments([FromHeader(Name="X-Meeting-Key")] string key, string id) =>
        // TANANYAG – A beszélőszakaszok időbélyeget és SPEAKER_XX címkét tartalmaznak; ez még nem bizonyított személyazonosság.
        omega.ForwardAsync(HttpContext, HttpMethod.Get, $"/v1/jobs/{OmegaAiGateway.Encode(id)}/segments", RequestClient.Get(HttpContext));

    // TANANYAG – A válasz médiatípusának Swaggerben is látható megadása.
    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>A Qwen által elkészített magyar megbeszélés-összesítő.</summary>
    [HttpGet("{id}/summary")]
    [Produces("text/plain")]
    public Task<IResult> Summary([FromHeader(Name="X-Meeting-Key")] string key, string id) =>
        // TANANYAG – A már elkészült megbeszélés-összesítőt kéri le, új generálás nélkül.
        omega.ForwardAsync(HttpContext, HttpMethod.Get, $"/v1/jobs/{OmegaAiGateway.Encode(id)}/summary", RequestClient.Get(HttpContext));

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Várakozó/futó feladat megszakításának kérése.</summary>
    [HttpPost("{id}/cancel")]
    public Task<IResult> Cancel([FromHeader(Name="X-Meeting-Key")] string key, string id) =>
        // TANANYAG – A POST /cancel lemondja a várakozó munkát, vagy megszakítást kér a már futó feldolgozásra.
        omega.ForwardAsync(HttpContext, HttpMethod.Post, $"/v1/jobs/{OmegaAiGateway.Encode(id)}/cancel", RequestClient.Get(HttpContext));

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Saját befejezett feladat és az összes tárolt hanganyag törlése.</summary>
    [HttpDelete("{id}")]
    public Task<IResult> Delete([FromHeader(Name="X-Meeting-Key")] string key, string id) =>
        // TANANYAG – A törlés az OmegaAI tenant-szabályainak megfelelően történik, nem közvetlen fájltörléssel itt.
        omega.ForwardAsync(HttpContext, HttpMethod.Delete, $"/v1/jobs/{OmegaAiGateway.Encode(id)}", RequestClient.Get(HttpContext));

    // TANANYAG – A kliens új beszélőneveket küld; a külön X-Meeting-Key a hitelesítéshez kell.
    /// <summary>Beszélő címkéhez kézzel rendelt név; az átirat módosul, az összesítőt újra kell generálni.</summary>
    [HttpPut("{id}/speaker-names")]
    public Task<IResult> Rename([FromHeader(Name="X-Meeting-Key")] string key, string id,
        // TANANYAG – A [FromBody] a JSON-t SpeakerNamesRequest osztállyá alakítja.
        [FromBody] SpeakerNamesRequest body) =>
        // TANANYAG – PUT helyes, mert a meglévő beszélőnév-hozzárendelést módosítjuk.
        omega.ForwardAsync(HttpContext, HttpMethod.Put, $"/v1/jobs/{OmegaAiGateway.Encode(id)}/speaker-names",
            // TANANYAG – A names szótár a SPEAKER_00 → név párokat adja át az OmegaAI-nak.
            RequestClient.Get(HttpContext), new { names = body.Names });

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Összesítő újragenerálása a módosított személynevekkel, hang újrafeldolgozása nélkül.</summary>
    [HttpPost("{id}/regenerate-summary")]
    public Task<IResult> Regenerate([FromHeader(Name="X-Meeting-Key")] string key, string id) =>
        // TANANYAG – A Qwen csak az összesítést állítja elő újra; a Whisper átiratához nem nyúl.
        omega.ForwardAsync(HttpContext, HttpMethod.Post, $"/v1/jobs/{OmegaAiGateway.Encode(id)}/regenerate-summary", RequestClient.Get(HttpContext));
}
