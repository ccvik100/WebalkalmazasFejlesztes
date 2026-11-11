// ================================================================
// OKTATÓI FORRÁSKÓD – AiController
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – Az OmegaAI elérését végző gateway-re hivatkozik; a vezérlő nem tölt be AI-modellt.
using MeetingNotesAPI.Infrastructure;
// TANANYAG – A ChatRequest és SummaryRequest DTO-k (adatátviteli objektumok) itt kapnak típust.
using MeetingNotesAPI.Models;
// TANANYAG – Az ASP.NET Core MVC attribútumait és ControllerBase osztályát importálja.
using Microsoft.AspNetCore.Mvc;

// TANANYAG – A Controllers névtér tartja elkülönítve a külső HTTP-felületért felelős osztályokat.
namespace MeetingNotesAPI.Controllers;

// TANANYAG – Az [ApiController] automatikus modellvalidációt és API-specifikus válaszkezelést tesz lehetővé.
[ApiController]
// TANANYAG – Az összes alábbi URL közös előtagja /api/ai, így csoportosíthatóak az AI-végpontok.
[Route("api/ai")]
// TANANYAG – A konstruktorparaméterben kapott gateway-t a beépített függőséginjektálás állítja elő.
public sealed class AiController(OmegaAiGateway omega) : ControllerBase
{
    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Qwen kérdés-válasz: egyszerre küldi vissza a teljes JSON-választ.</summary>
    [HttpPost("chat")]
    public Task<IResult> Chat([FromHeader(Name="X-Meeting-Key")] string key, [FromBody] ChatRequest body) =>
        // TANANYAG – A Gateway HTTP POST kérést továbbít az OmegaAI /v1/chat végpontjára, a middleware-ből megismert klienshez kötve.
        omega.ForwardAsync(HttpContext, HttpMethod.Post, "/v1/chat", RequestClient.Get(HttpContext),
            // TANANYAG – A kliens Prompt mezőjét kisbetűs prompt néven küldi tovább; ez az OmegaAI által elvárt JSON-mező.
            new { prompt = body.Prompt });

    // TANANYAG – A content-type jelzi, hogy ez eseményfolyam, nem egyetlen visszaadott JSON dokumentum.
    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Qwen tokenfolyam SSE-ben. A Swagger megjelenítője nem feltétlenül jeleníti meg élőben.</summary>
    [HttpPost("chat/stream")]
    [Produces("text/event-stream")]
    public async Task StreamChat([FromHeader(Name="X-Meeting-Key")] string key, [FromBody] ChatRequest body) =>
        // TANANYAG – A Qwen szövegét az OmegaAI-tól részletekben továbbítja, miközben a kapcsolat nyitva marad.
        await omega.ForwardSseAsync(HttpContext, "/v1/chat/stream", RequestClient.Get(HttpContext),
            // TANANYAG – A prompt ugyanaz, mint a hagyományos chatnél, csak a válasz átadása más.
            new { prompt = body.Prompt });

    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Magyar megbeszélés-összesítő kész átiratból (nem szükséges újra elküldeni a hangot).</summary>
    [HttpPost("summaries")]
    public Task<IResult> Summary([FromHeader(Name="X-Meeting-Key")] string key, [FromBody] SummaryRequest body) =>
        // TANANYAG – A meglévő átirat összesítését kéri; új hangfeldolgozást nem indít.
        omega.ForwardAsync(HttpContext, HttpMethod.Post, "/v1/summaries", RequestClient.Get(HttpContext),
            // TANANYAG – A C# StartedAt mezőt az OmegaAI snake_case started_at formájára alakítja a JSON-objektumban.
            new { transcript = body.Transcript, title = body.Title, started_at = body.StartedAt });

    // TANANYAG – Az SSE válasz MIME-típusát dokumentálja a kliens számára.
    // TANANYAG – Nyilvános API-művelet; a Task az aszinkron működést, az IResult a HTTP-választ képviseli.
    /// <summary>Magyar összesítő generálásakor a Qwen részszövege folyamatosan érkezik.</summary>
    [HttpPost("summaries/stream")]
    [Produces("text/event-stream")]
    public async Task StreamSummary([FromHeader(Name="X-Meeting-Key")] string key, [FromBody] SummaryRequest body) =>
        // TANANYAG – A hosszabb összesítést folyamatosan továbbítja, így a web/mobil kliens a generálódó szöveget részletenként mutathatja.
        await omega.ForwardSseAsync(HttpContext, "/v1/summaries/stream", RequestClient.Get(HttpContext),
            // TANANYAG – Az átirat, cím és kezdési idő mind bekerülnek a streamelő összesítő kérésbe.
            new { transcript = body.Transcript, title = body.Title, started_at = body.StartedAt });
}
