// ================================================================
// OKTATÓI FORRÁSKÓD – SpeakerIdentificationController
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – A gateway és a hitelesített RequestClient típusainak használatához szükséges névtér.
using MeetingNotesAPI.Infrastructure;
// TANANYAG – A MatchRequest és ApproveRequest bejövő JSON-adatszerződéseket teszi láthatóvá.
using MeetingNotesAPI.Models;
// TANANYAG – A REST-attribútumokhoz szükséges ASP.NET Core MVC névtér.
using Microsoft.AspNetCore.Mvc;

// TANANYAG – A beszélőazonosítás végpontjait külön vezérlő tartja áttekinthetően.
namespace MeetingNotesAPI.Controllers;

// TANANYAG – A bemenő JSON-adatok validálását az API infrastruktúrája végzi.
[ApiController]
// TANANYAG – A jobId útvonalelem megmondja, melyik megbeszélés beszélőit szeretnénk azonosítani.
[Route("api/meetings/{jobId}/identification")]
// TANANYAG – A DI által adott gateway továbbítja a műveleteket a központi OfflineAI szolgáltatásnak.
public sealed class SpeakerIdentificationController(OmegaAiGateway omega) : ControllerBase
{
    // TANANYAG – A kérésben a hitelesítő kulcs, a megbeszélés jobId-ja és a hasonlósági határok szerepelnek.
    /// <summary>
    /// Beszélő → személy javaslatok. A similarity_percent NEM az azonosság valószínűsége!
    /// Egyértelműnek nem bizonyítható találatot ismeretlenként kell kezelni.
    /// </summary>
    [HttpPost("suggest")]
    public Task<IResult> Suggest([FromHeader(Name="X-Meeting-Key")] string key, string jobId,
        // TANANYAG – A match értékei szerződés szerint felülvizsgálhatók, nem jelentenek százszázalékos bizonyítékot.
        [FromBody] MatchRequest match)
    {
        // TANANYAG – A hitelesítési middleware-ből átvett kliens mondja meg, melyik alkalmazás profiljait lehet összevetni.
        var client = RequestClient.Get(HttpContext);
        // TANANYAG – Az azonosítási javaslatokat a tenant saját hangmintái alapján kéri a szolgáltatás.
        return omega.ForwardAsync(HttpContext, HttpMethod.Post,
            // TANANYAG – Az URL-ben tenant és job azonosító is van, mindkettő biztonságosan URL-kódolva.
            $"/v1/tenants/{OmegaAiGateway.Encode(client.TenantId)}/jobs/{OmegaAiGateway.Encode(jobId)}/match",
            // TANANYAG – A threshold a minimum hasonlósági küszöb, a margin a két legjobb találat minimális elkülönülése.
            client, new { threshold = match.Threshold, margin = match.Margin });
    }

    // TANANYAG – A jóváhagyás külön művelet; az automatikus javaslatot nem tekintjük azonosításnak.
    /// <summary>Beszélő személyének kézi jóváhagyása – csak bizonyíték és ellenőrzés után.</summary>
    [HttpPost("approve")]
    public Task<IResult> Approve([FromHeader(Name="X-Meeting-Key")] string key, string jobId,
        // TANANYAG – Az Approved szótár a felhasználó által ellenőrzött SPEAKER_XX és személyazonosító párokat tartalmazza.
        [FromBody] ApproveRequest approve)
    {
        // TANANYAG – A személyhozzárendeléshez is a hitelesített tenant jogosultságát használjuk.
        var client = RequestClient.Get(HttpContext);
        // TANANYAG – A kézi jóváhagyást POST kérésként továbbítjuk a hangprofil-alrendszernek.
        return omega.ForwardAsync(HttpContext, HttpMethod.Post,
            // TANANYAG – A saját alkalmazás személyeihez köti a megbeszélést, más tenant adatait nem használja.
            $"/v1/tenants/{OmegaAiGateway.Encode(client.TenantId)}/jobs/{OmegaAiGateway.Encode(jobId)}/approve",
            // TANANYAG – Csak jóváhagyott mappinget adunk át az OmegaAI-nak; a javaslatokat külön kezeli.
            client, new { approved = approve.Approved });
    }
}
