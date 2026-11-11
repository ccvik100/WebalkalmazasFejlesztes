// ================================================================
// OKTATÓI FORRÁSKÓD – Szerveroldali konfiguráció
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – A konfigurációs adatmodellek a Models névtérben szerepelnek.
namespace MeetingNotesAPI.Models;

// TANANYAG – A teljes MeetingNotes beállítási rész típusos megfelelője.
/// <summary>Csak szerveroldali konfiguráció: EZEK A KULCSOK SOSEM MENNEK A KLIENSHEZ.</summary>
public sealed class MeetingOptions
{
    // TANANYAG – A belső OmegaAI szolgáltatás címe és főkulcsa; csak szerveroldalon tárolható.
    public OmegaAiOptions OmegaAi { get; set; } = new();
    // TANANYAG – Több külön kliensalkalmazás saját kulcsot és tenantot kap a listában.
    public List<ClientOptions> Clients { get; set; } = new();
    // TANANYAG – A megbeszélés feltölthető hangfájljának beállítható maximális mérete MB-ban.
    public int MaxUploadMb { get; set; } = 100;
    // TANANYAG – A Swagger tesztfelület ki- vagy bekapcsolása környezetfüggően.
    public bool EnableSwagger { get; set; } = true;
}
// TANANYAG – A Python alapú OmegaAI külön HTTP-szolgáltatás kapcsolati beállításai.
public sealed class OmegaAiOptions
{
    // TANANYAG – A 127.0.0.1 mindig ugyanarra a gépre mutat; a későbbi szerveres telepítésnél ott helyben kell futnia az OmegaAI-nak.
    public string BaseUrl { get; set; } = "http://127.0.0.1:8768";
    // TANANYAG – A főkulcs üres az alap appsettingsben, a valós értéket a privát konfiguráció adja.
    public string ApiKey { get; set; } = "";
}
// TANANYAG – Egyetlen kliensalkalmazáshoz tartozó szerveroldali adatok.
public sealed class ClientOptions
{
    // TANANYAG – A Name az alkalmazás könnyen olvasható neve, nem jogosultságigazolás.
    public string Name { get; set; } = "";
    // TANANYAG – A ClientKey az ügyfél által küldött X-Meeting-Key titka.
    public string ClientKey { get; set; } = "";
    // TANANYAG – A TenantId az OmegaAI-ban elkülönített személy- és hangprofiladattár azonosítója.
    public string TenantId { get; set; } = "";
    // TANANYAG – A TenantKey az adott OmegaAI tenant külön kulcsa; ezt a kliensnek soha nem adjuk vissza.
    public string TenantKey { get; set; } = "";
}
