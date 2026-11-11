// ================================================================
// OKTATÓI FORRÁSKÓD – SystemController
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – Az OmegaAI gateway és kulcsellenőrzés osztályaihoz szükséges import.
using MeetingNotesAPI.Infrastructure;
// TANANYAG – Az MVC-vezérlőkhöz használt HTTP attribútumokat hozza be.
using Microsoft.AspNetCore.Mvc;

// TANANYAG – Rendszerdiagnosztikai végpontok számára külön névtér.
namespace MeetingNotesAPI.Controllers;

// TANANYAG – Az ApiController egységes API-viselkedést biztosít.
[ApiController]
// TANANYAG – A rendszer végpontjainak közös útvonala /api.
[Route("api")]
// TANANYAG – Az OmegaAiGateway-t a DI konténer biztosítja.
public sealed class SystemController(OmegaAiGateway omega) : ControllerBase
{
    // TANANYAG – A válasz médiatípusának Swaggerben is látható megadása.
    // TANANYAG – Ez csak a saját .NET API működését bizonyítja, nem a Whisper/Ollama elérhetőségét.
    /// <summary>MeetingNotesAPI saját futásellenőrzése; ettől még az OmegaAI lehet leállítva.</summary>
    [HttpGet("health/live")]
    [Produces("application/json")]
    public IResult Live() => Results.Json(new { service = "MeetingNotesAPI", status = "running", framework = ".NET 10", omegaAiTested = false });

    // TANANYAG – Az OmegaAI tényleges hálózati/konfigurációs állapotát kérjük le a gateway segítségével.
    /// <summary>Megvizsgálja, hogy a helyi OmegaAI fut-e és a modellfájlok elérhetők-e.</summary>
    [HttpGet("health/omegaai")]
    public Task<IResult> CheckOmega([FromHeader(Name = "X-Meeting-Key")] string key) =>
        // TANANYAG – A RequestClient biztosítja, hogy a kérés csak hitelesített alkalmazás nevében induljon.
        omega.OmegaStatusAsync(HttpContext, RequestClient.Get(HttpContext));

    // TANANYAG – A fő AI szolgáltatás állapotát egy kulccsal védett végponton kérjük le.
    /// <summary>Teljes OmegaAI modelltábla: fájlok/függőségek és Qwen elérhetősége.</summary>
    [HttpGet("system/models")]
    public Task<IResult> Models([FromHeader(Name = "X-Meeting-Key")] string key) =>
        // TANANYAG – A /v1/models választ változtatás nélkül továbbítja; ebből látjuk a helyi modellszolgáltatásokat.
        omega.ForwardAsync(HttpContext, HttpMethod.Get, "/v1/models", RequestClient.Get(HttpContext));

    // TANANYAG – A /v1/hardware végpont CPU/GPU információt ad, amely nem azonos a valódi GPU-s inferencia sikerével.
    /// <summary>CPU/GPU képességek; nem egyenlő a GPU-n sikeresen lefuttatott inferenciával.</summary>
    [HttpGet("system/hardware")]
    public Task<IResult> Hardware([FromHeader(Name = "X-Meeting-Key")] string key) =>
        // TANANYAG – A hálózati kérést a gateway egészíti ki a szükséges belső kulcsokkal.
        omega.ForwardAsync(HttpContext, HttpMethod.Get, "/v1/hardware", RequestClient.Get(HttpContext));

    // TANANYAG – A kliens csak a teljes feladatsor statisztikáját láthatja, más tenant feladatazonosítóit nem.
    /// <summary>Központi munkasor létszámai. Más tenantok feladatazonosítóit nem adja ki.</summary>
    [HttpGet("queue")]
    public Task<IResult> Queue([FromHeader(Name = "X-Meeting-Key")] string key) =>
        // TANANYAG – A külön QueueStatusAsync kiszűri a más alkalmazásokra vonatkozó érzékeny mezőket.
        omega.QueueStatusAsync(HttpContext, RequestClient.Get(HttpContext));
}
