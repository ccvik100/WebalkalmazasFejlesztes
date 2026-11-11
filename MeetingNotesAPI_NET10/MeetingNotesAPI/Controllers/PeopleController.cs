// ================================================================
// OKTATÓI FORRÁSKÓD – PeopleController
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – Az UTF-8 kódolást használjuk a hangmintához tartozó hozzájárulási szöveg továbbításánál.
using System.Text;
// TANANYAG – Az infrastruktúra réteg biztosítja a kliens azonosítását és az OmegaAI hívását.
using MeetingNotesAPI.Infrastructure;
// TANANYAG – A PersonRequest, VoiceSampleRequest és ClientOptions adattípusok névtere.
using MeetingNotesAPI.Models;
// TANANYAG – Az MVC vezérlők HTTP-attribútumait importálja.
using Microsoft.AspNetCore.Mvc;

// TANANYAG – A személykezelésért felelős vezérlő névtere.
namespace MeetingNotesAPI.Controllers;

// TANANYAG – A személyek HTTP-s útvonala /api/people; a tényleges tárolás az OmegaAI saját tenantjában történik.
// TANANYAG – A szerveroldali gateway-t automatikusan megkapja a DI konténertől.
/// <summary>Tenant-specifikus személyek és hozzájárulás alapján rögzített hangminták.</summary>
[ApiController]
[Route("api/people")]
public sealed class PeopleController(OmegaAiGateway omega) : ControllerBase
{
    // TANANYAG – Rövidített tulajdonság: a middleware által hitelesített aktuális alkalmazás ClientOptions objektuma.
    private ClientOptions Client => RequestClient.Get(HttpContext);
    // TANANYAG – Minden személy-URL tartalmazza a hitelesített alkalmazás tenantazonosítóját – nem kérjük be a klienstől.
    private string Base => $"/v1/tenants/{OmegaAiGateway.Encode(Client.TenantId)}";

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Saját alkalmazás személylistája: név, szervezet, pozíció, mintaszám.</summary>
    [HttpGet]
    public Task<IResult> List([FromHeader(Name="X-Meeting-Key")] string key) =>
        // TANANYAG – A saját tenant személylistáját kéri az OmegaAI-tól, a hangblobjai nélkül.
        omega.ForwardAsync(HttpContext, HttpMethod.Get, Base + "/persons", Client);

    // TANANYAG – A személyadatok POST törzsből érkeznek; external_person_id alapján az üzleti rendszer és a hangprofil összeköthető.
    /// <summary>Személy létrehozása vagy frissítése external_person_id alapján.</summary>
    [HttpPost]
    public Task<IResult> Upsert([FromHeader(Name="X-Meeting-Key")] string key, [FromBody] PersonRequest p) =>
        // TANANYAG – A JSON-kérés a tenant saját /persons listájára megy.
        omega.ForwardAsync(HttpContext, HttpMethod.Post, Base + "/persons", Client,
            // TANANYAG – A külső személyazonosító és a megjelenített név átadása; a kulcsnevek az OmegaAI REST-szerződését követik.
            new { external_person_id = p.ExternalPersonId, name = p.Name,
                  // TANANYAG – A szervezet, általános pozíció és választott tisztség külön mező, hogy később pontosan megjeleníthető legyen.
                  organization = p.Organization, position = p.Position, elected_position = p.ElectedPosition });

    // TANANYAG – Csak a hitelesített tenant saját személyét törölheti a kérés.
    /// <summary>Személy és összes hangminta törlése; csak megfelelő alkalmazási jogosultsággal.</summary>
    [HttpDelete("{personId}")]
    public Task<IResult> Delete([FromHeader(Name="X-Meeting-Key")] string key, string personId) =>
        omega.ForwardAsync(HttpContext, HttpMethod.Delete,
            // TANANYAG – Az azonosítót URL-kódoljuk, mielőtt az OmegaAI útvonalába illesztjük.
            Base + "/persons/" + OmegaAiGateway.Encode(personId), Client);

    // TANANYAG – A hangminta fájlt és metaadatokat multipart/form-data formában fogadjuk.
    // TANANYAG – A hangminta űrlapfeldolgozásának külön mérethatára van, amely eltér a teljes megbeszélésétől.
    // TANANYAG – Egy személyazonosító útvonalparaméter és a VoiceSampleRequest űrlapmodell érkezik a művelethez.
    /// <summary>Jóváhagyott, 3-90 másodperces hangminta (max. 20/személy), aszinkron munkasor.</summary>
    [HttpPost("{personId}/samples")]
    [Consumes("multipart/form-data")]
    [RequestFormLimits(MultipartBodyLengthLimit = 18_000_000)]
    public async Task<IResult> Enroll([FromHeader(Name="X-Meeting-Key")] string key,
        // TANANYAG – [FromForm] a hangot és a hozzájárulási adatokat kötözi típusos mezőkhöz.
        string personId, [FromForm] VoiceSampleRequest body)
    {
        // TANANYAG – Rögzített hozzájárulás nélkül hangbiometrikus profilt nem hozhatunk létre.
        if (!body.ConsentConfirmed || body.ConsentNote.Trim().Length < 3)
            // TANANYAG – Hiányzó vagy nem megfelelő hozzájárulás esetén 400-as választ küldünk.
            return Results.BadRequest(new { error = "A rögzített hozzájárulás megerősítése és leírása kötelező." });
        // TANANYAG – A hangfájl meglétét, nem-ürességét és 15 MB-os korlátját ellenőrzi.
        if (body.Audio is null || body.Audio.Length == 0 || body.Audio.Length > 15 * 1024 * 1024)
            // TANANYAG – A túl nagy vagy üres fájlhoz 413-as HTTP-választ rendel.
            return Results.Json(new { error = "A hangminta hiányzik vagy meghaladja a 15 MB-ot." }, statusCode: 413);
        // TANANYAG – Az OmegaAI számára összeállítunk egy új, kontrollált multipart kérést.
        using var multipart = new MultipartFormDataContent();
        // TANANYAG – A hangmintát streamként csatoljuk, hogy a bináris adatot ne kódoljuk szöveggé.
        using var audio = new StreamContent(body.Audio.OpenReadStream());
        // TANANYAG – Az eredeti névből csak a fájlnevet tartjuk meg, nem engedünk teljes fájlrendszer-útvonalat átadni.
        multipart.Add(audio, "audio", Path.GetFileName(body.Audio.FileName));
        // TANANYAG – A true értékkel a hozzájárulás visszaigazolását továbbítjuk.
        multipart.Add(new StringContent("true"), "consent_confirmed");
        // TANANYAG – A hozzájárulási megjegyzés ékezetes szövegét UTF-8-ként küldjük.
        multipart.Add(new StringContent(body.ConsentNote, Encoding.UTF8), "consent_note");
        // TANANYAG – Az OmegaAI saját, adott személyhez tartozó hangminta-regisztrációs végpontját hívjuk.
        return await omega.ForwardAsync(HttpContext, HttpMethod.Post,
            // TANANYAG – A személyazonosítót URL-kódolva beépítjük; így a feltöltés nem kerülhet más személyre véletlenül.
            Base + "/persons/" + OmegaAiGateway.Encode(personId) + "/samples",
            // TANANYAG – A kliens tenantkulcsát a Gateway helyezi el a szerveroldali HTTP-kérés fejlécében.
            Client, requestContent: multipart);
    }

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Hangminta-vektorizálás állapota és sorpozíciója.</summary>
    [HttpGet("enrollments/{enrollmentId}")]
    public Task<IResult> Enrollment([FromHeader(Name="X-Meeting-Key")] string key, string enrollmentId) =>
        omega.ForwardAsync(HttpContext, HttpMethod.Get,
            // TANANYAG – A hangminta-vektorizálás elhúzódhat; külön enrollment állapot lekérdezhető.
            Base + "/enrollments/" + OmegaAiGateway.Encode(enrollmentId), Client);

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Egy személy saját hangmintái, a privát SQLite hangblob nélkül.</summary>
    [HttpGet("{personId}/samples")]
    public Task<IResult> Samples([FromHeader(Name="X-Meeting-Key")] string key, string personId) =>
        omega.ForwardAsync(HttpContext, HttpMethod.Get,
            // TANANYAG – A hangminták metaadatlistáját kérjük le, nem közvetlenül a biometrikus fájlokat.
            Base + "/persons/" + OmegaAiGateway.Encode(personId) + "/samples", Client);

    // TANANYAG – A letöltés csak hitelesített backend-kérés, nem nyilvános statikus fájl.
    /// <summary>Hangminta visszajátszása hitelesítve. Biometrikus személyes adat.</summary>
    [HttpGet("{personId}/samples/{sampleId}/audio")]
    public Task<IResult> Audio([FromHeader(Name="X-Meeting-Key")] string key, string personId, string sampleId) =>
        // TANANYAG – A Gateway bináris válaszmódban kéri le a hangot, nem UTF-8 szövegként.
        omega.ForwardBinaryAsync(HttpContext,
            // TANANYAG – A tenant, a személy és a hangminta ID-ja is szerepel az útvonalban.
            Base + "/persons/" + OmegaAiGateway.Encode(personId) + "/samples/" + OmegaAiGateway.Encode(sampleId) + "/audio", Client);

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Egy hangminta törlése; az OmegaAI újraszámítja az illető hangprofilját.</summary>
    [HttpDelete("{personId}/samples/{sampleId}")]
    public Task<IResult> DeleteSample([FromHeader(Name="X-Meeting-Key")] string key, string personId, string sampleId) =>
        // TANANYAG – A DELETE végpont egy meghatározott mintát távolít el.
        omega.ForwardAsync(HttpContext, HttpMethod.Delete,
            // TANANYAG – A személy hangprofilja a fennmaradó minták alapján később újraszámítható.
            Base + "/persons/" + OmegaAiGateway.Encode(personId) + "/samples/" + OmegaAiGateway.Encode(sampleId), Client);
}
