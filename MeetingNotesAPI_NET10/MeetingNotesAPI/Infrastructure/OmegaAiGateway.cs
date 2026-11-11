// ================================================================
// OKTATÓI FORRÁSKÓD – Központi szerver–OmegaAI HTTP-kapcsolat
// A magyarázó kommentek a kód értelmét és biztonsági szerepét írják le.
// A működő programutasításokat az eredeti kiadáshoz képest nem módosítjuk.
// ================================================================
// TANANYAG – A HTTP státuszkódok és hálózati típusok .NET névterének importja.
using System.Net;
// TANANYAG – A HTTP-fejlécekben használt tartalomtípusokhoz szükséges névtér.
using System.Net.Http.Headers;
// TANANYAG – A szöveges válaszokat UTF-8-ban továbbítjuk, ezért kell az Encoding.
using System.Text;
// TANANYAG – A JSON-dokumentum feldolgozó és sorosító API névtere.
using System.Text.Json;
// TANANYAG – Az OmegaAiOptions és ClientOptions szerveroldali beállításokat használjuk.
using MeetingNotesAPI.Models;
// TANANYAG – Az IOptions a konfiguráció típusos beolvasását támogatja.
using Microsoft.Extensions.Options;

// TANANYAG – Az infrastruktúra gateway-osztály egy helyre vonja össze a külső AI HTTP-hívásait.
namespace MeetingNotesAPI.Infrastructure;

// TANANYAG – A gateway konstruktorparaméterei: megosztott HttpClient, alkalmazásbeállítás és naplózó szolgáltatás.
/// <summary>
/// Egyetlen helyen kezeljük az OmegaAI címet, főkulcsot és tenantkulcsot.
/// A böngésző vagy mobil eszköz SOHA nem hívhatja közvetlenül a 8768-as portot.
/// </summary>
public sealed class OmegaAiGateway(HttpClient http, IOptions<MeetingOptions> options,
                                  // TANANYAG – A logger a hibák rögzítésére való, de sosem írjuk bele az API-kulcsokat.
                                  ILogger<OmegaAiGateway> logger)
{
    // TANANYAG – A beállításokat a DI IOptions szolgáltatásából olvassuk ki és a példányhoz kötjük.
    private readonly MeetingOptions _settings = options.Value;
    // TANANYAG – A webes JSON alapbeállítás a C# tulajdonságneveket a REST-ben megszokott kisbetűs alakra alakíthatja.
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    // TANANYAG – Az ID URL-kódolása elengedhetetlen, hogy egy speciális karakter ne alakítson át útvonalat.
    public static string Encode(string id) => Uri.EscapeDataString(id);

    // TANANYAG – A Url segédfüggvény egy helyen építi fel a cél HTTP-címet a konfigurációból.
    private Uri Url(string relative)
    {
        // TANANYAG – A BaseUrl végére pontosan egy / karaktert biztosít, így jól illeszthetők a relatív végpontok.
        var baseUrl = _settings.OmegaAi.BaseUrl.TrimEnd('/') + "/";
        // TANANYAG – Ellenőrzi, hogy érvényes, abszolút HTTP/HTTPS címet kaptunk-e.
        var parsed = new Uri(baseUrl, UriKind.Absolute);
        // A Python API alapból csak a szerveren figyel. Külső szerver csak HTTPS-sel lehet cél.
        // TANANYAG – Helyi (loopback) szerver esetén HTTP megengedett; távoli OmegaAI-nál kizárólag HTTPS.
        if (!(parsed.IsLoopback && parsed.Scheme == Uri.UriSchemeHttp) && parsed.Scheme != Uri.UriSchemeHttps)
            // TANANYAG – Tiltott célcímnél kivétellel állítja meg a hívást még a hálózati kapcsolat előtt.
            throw new InvalidOperationException("OmegaAI címe helyi HTTP vagy HTTPS lehet.");
        // TANANYAG – A konfigurációs alapcímhez hozzáilleszti a konkrét /v1 végpontot.
        return new Uri(parsed, relative.TrimStart('/'));
    }

    // TANANYAG – A Request metódus a teljesen előkészített HttpRequestMessage objektumot adja vissza.
    private HttpRequestMessage Request(HttpMethod method, string path, ClientOptions client)
    {
        // TANANYAG – HTTP metódus és URL alapján új kérést hoz létre (GET/POST/PUT/DELETE).
        var request = new HttpRequestMessage(method, Url(path));
        // TANANYAG – A központi OmegaAI főkulcsot csak a szerveren adja hozzá a HTTP fejlécbe.
        request.Headers.TryAddWithoutValidation("X-Api-Key", _settings.OmegaAi.ApiKey);
        // TANANYAG – A külön klienshez tartozó tenantkulcsot hozzáadva az OmegaAI nem keveri az alkalmazások személyadatait.
        request.Headers.TryAddWithoutValidation("X-Tenant-Key", client.TenantKey);
        // TANANYAG – A beállított fejlécekkel ellátott HTTP kérést visszaadja a hívónak.
        return request;
    }

    // TANANYAG – Az alacsony szintű SendRawAsync minden OmegaAI HTTP-hívás közös útvonala.
    public async Task<HttpResponseMessage> SendRawAsync(HttpMethod method, string path,
        // TANANYAG – A content HTTP-törzs (JSON vagy multipart), a cancellationToken a kérés megszakítására szolgál.
        ClientOptions client, HttpContent? content, CancellationToken cancellationToken)
    {
        // TANANYAG – Előbb azonosítókkal és biztonsági fejlécekkel építi fel a kérést.
        var request = Request(method, path, client);
        // TANANYAG – A hívó által összeállított adatot (ha van) a HTTP-kérés törzséhez kapcsolja.
        request.Content = content;
        // ResponseHeadersRead: az SSE stream-et NEM puffereljük végig a memóriában.
        // TANANYAG – A ResponseHeadersRead a szerver válaszfejlécei után továbbenged, nem várja végig az SSE adatfolyamot.
        try { return await http.SendAsync(request, HttpCompletionOption.ResponseHeadersRead, cancellationToken); }
        // TANANYAG – A request erőforrást felszabadítjuk a SendAsync után; a visszakapott válasz élettartama a hívóé.
        finally { request.Dispose(); }
    }

    // TANANYAG – Az általános JSON- vagy szöveges REST-továbbítás belépési pontja.
    public async Task<IResult> ForwardAsync(HttpContext context, HttpMethod method, string path,
        // TANANYAG – A jsonBody objektumból JSON készül; requestContent kész bináris/multipart tartalom lehet.
        ClientOptions client, object? jsonBody = null, HttpContent? requestContent = null)
    {
        try
        {
            // TANANYAG – Elsőként a kívülről átadott HTTP-tartalmat vesszük alapul.
            HttpContent? content = requestContent;
            // TANANYAG – Ha objektumot is kaptunk, azt JSON-ként kell elküldeni.
            if (jsonBody is not null)
            {
                // TANANYAG – JSON sorosítás UTF-8 kódolással és application/json tartalomtípussal.
                content = new StringContent(JsonSerializer.Serialize(jsonBody, Json), Encoding.UTF8, "application/json");
            }
            // TANANYAG – A using felszabadítja a request HTTP-törzsét a továbbítás után.
            using (content)
            // TANANYAG – A másik using biztosítja, hogy a HTTP-válasz hálózati erőforrásai is lezáruljanak.
            using (var response = await SendRawAsync(method, path, client, content, context.RequestAborted))
            {
                // TANANYAG – A beérkező OmegaAI-választ szövegként olvassa; az eredeti státuszkódot később megtartjuk.
                var body = await response.Content.ReadAsStringAsync(context.RequestAborted);
                // TANANYAG – A válasz médiatípusát megőrzi, hiány esetén alapértelmezésként JSON-t használ.
                var type = response.Content.Headers.ContentType?.MediaType ?? "application/json";
                // Megőrizzük a 202, 400, 403, 404, 409, 429, 503 stb. upstream HTTP-kódot.
                // TANANYAG – A no-store válaszfejléc különösen érzékeny beszélő- és megbeszélésadatoknál fontos.
                context.Response.Headers["Cache-Control"] = "no-store";
                // TANANYAG – Az OmegaAI státuszkódját átadja a saját kliensnek, hogy a 202/401/404/429 stb. pontosan látszódjon.
                return Results.Content(body, type, Encoding.UTF8, (int)response.StatusCode);
            }
        }
        // TANANYAG – Hálózati hiba: például az OmegaAI nem fut, vagy nem érhető el a megadott porton.
        catch (HttpRequestException ex)
        {
            // TANANYAG – A belső naplóba a hibát és a hívott relatív útvonalat írjuk, nem a kulcsot.
            logger.LogWarning(ex, "OmegaAI hálózati hiba: {Path}", path);
            // TANANYAG – 503-mal jelezzük, hogy a függő AI-szolgáltatás nem elérhető; nem állítjuk, hogy az MP3 hibás.
            return Results.Json(new { error = "OmegaAI nem érhető el a szerveren.", upstream = _settings.OmegaAi.BaseUrl }, statusCode: 503);
        }
        // TANANYAG – Külön fogjuk a kiszolgálóoldali időtúllépést, ha nem a felhasználó szakította meg a kérést.
        catch (OperationCanceledException) when (!context.RequestAborted.IsCancellationRequested)
        {
            // TANANYAG – A 504 Gateway Timeout jelzi, hogy a proxy hívása nem fejeződött be időben.
            return Results.Json(new { error = "Az OmegaAI hívása időtúllépés miatt megszakadt." }, statusCode: 504);
        }
        // TANANYAG – Hibás szerverkonfiguráció esetén nem szivárogtatjuk ki a kivétel részleteit az ügyfélnek.
        catch (InvalidOperationException ex)
        {
            // TANANYAG – A részletes hiba szervernaplóba kerül a rendszergazdának.
            logger.LogError(ex, "Hibás OmegaAI konfiguráció");
            // TANANYAG – Az ügyfél csak rövid, biztonságos hibaüzenetet és 503-as kódot kap.
            return Results.Json(new { error = "OmegaAI konfigurációs hiba." }, statusCode: 503);
        }
    }

    // TANANYAG – A bináris letöltés külön metódust igényel, mert a hangminta nem dekódolható JSON/szövegként.
    public async Task<IResult> ForwardBinaryAsync(HttpContext context, string path, ClientOptions client)
    {
        try
        {
            // TANANYAG – A belső hangfájl letöltését GET kéréssel indítjuk.
            using var response = await SendRawAsync(HttpMethod.Get, path, client, null, context.RequestAborted);
            // TANANYAG – Ha a belső szolgáltatás elutasította a letöltést, nem adunk vissza félrevezető fájlokat.
            if (!response.IsSuccessStatusCode)
            {
                // TANANYAG – A JSON hibaüzenetet olvassuk és továbbítjuk az eredeti hibakóddal.
                var error = await response.Content.ReadAsStringAsync(context.RequestAborted);
                // TANANYAG – A hibás válasz szövege JSON típust kap; a kliens megfelelően értelmezheti.
                return Results.Content(error, "application/json", statusCode: (int)response.StatusCode);
            }
            // TANANYAG – Siker esetén byte[] formában beolvassuk a hangminta tartalmát.
            var bytes = await response.Content.ReadAsByteArrayAsync(context.RequestAborted);
            // TANANYAG – Érzékeny biometrikus adatot a HTTP cache nem tárolhat.
            context.Response.Headers["Cache-Control"] = "no-store";
            // TANANYAG – A Results.File egy letölthető bináris választ állít elő a meglévő médiatípussal.
            return Results.File(bytes, response.Content.Headers.ContentType?.MediaType ?? "application/octet-stream",
                // TANANYAG – A range feldolgozást kikapcsoljuk: teljes letöltési válasz érkezik.
                enableRangeProcessing: false);
        }
        // TANANYAG – A hálózati hiba itt is külön kivételkezelést kap.
        catch (HttpRequestException ex)
        {
            // TANANYAG – A hiba naplózása segíti a szerver üzemeltetőjét anélkül, hogy a hangot naplóznánk.
            logger.LogWarning(ex, "Hangminta letöltés sikertelen");
            // TANANYAG – 503-as hibával jelezzük, hogy a tárolt hangminta jelenleg nem érhető el.
            return Results.Json(new { error = "OmegaAI nem érhető el." }, statusCode: 503);
        }
    }

    // TANANYAG – Az SSE továbbítás JSON-törzset (POST) vagy puszta GET-kérést is kezel.
    /// <summary>Qwen és feladatprogress SSE események pufferelés nélküli továbbítása.</summary>
    public async Task ForwardSseAsync(HttpContext context, string path, ClientOptions client,
        // TANANYAG – A body alapértéke null: az állapotstream GET, míg a Qwen chat-stream POST.
        object? body = null)
    {
        try
        {
            // TANANYAG – Csak akkor építünk JSON HttpContentet, ha a hívó kéréstörzset is küldött.
            using HttpContent? content = body is null ? null :
                // TANANYAG – A tartalom application/json és UTF-8 a streamet megnyitó kérésnél.
                new StringContent(JsonSerializer.Serialize(body, Json), Encoding.UTF8, "application/json");
            // TANANYAG – A body jelenléte alapján választja a POST vagy GET HTTP-metódust.
            using var response = await SendRawAsync(body is null ? HttpMethod.Get : HttpMethod.Post,
                // TANANYAG – Az SSE kérés ugyanúgy titkos fejlécekkel és megszakíthatósággal indul.
                path, client, content, context.RequestAborted);
            // TANANYAG – Előbb ellenőrizzük a HTTP-státuszt, csak utána kezdjük el az SSE-adatfolyamot.
            if (!response.IsSuccessStatusCode)
            {
                // TANANYAG – Hiba esetén az eredeti OmegaAI hibakódot adja vissza.
                context.Response.StatusCode = (int)response.StatusCode;
                // TANANYAG – Sikertelen megnyitáskor JSON-hibát küldünk, nem eseményfolyamot.
                context.Response.ContentType = "application/json";
                // TANANYAG – Az eredeti hibatartalmat átmásolja a kliens válaszába.
                await response.Content.CopyToAsync(context.Response.Body, context.RequestAborted);
                // TANANYAG – A return miatt nem indul el az élő eseménytovábbítás.
                return;
            }
            // TANANYAG – A text/event-stream határozza meg a böngésző és .NET kliens által értelmezett SSE adatfolyamot.
            context.Response.ContentType = "text/event-stream; charset=utf-8";
            // TANANYAG – A no-cache/no-transform megakadályozza a proxyk által végzett nemkívánatos pufferelést/átalakítást.
            context.Response.Headers["Cache-Control"] = "no-cache, no-transform";
            // TANANYAG – Az X-Accel-Buffering: no támogatott proxyknál kikapcsolhatja a pufferelést.
            context.Response.Headers["X-Accel-Buffering"] = "no";
            // TANANYAG – A nosniff megakadályozza, hogy a böngésző más tartalomtípusnak próbálja felismerni a streamet.
            context.Response.Headers["X-Content-Type-Options"] = "nosniff";
            // TANANYAG – Azonnal megkezdjük a HTTP-választ, hogy a kliens már a generálás alatt kapcsolatban legyen.
            await context.Response.StartAsync(context.RequestAborted);
            // TANANYAG – Megnyitjuk az upstream válasz testét olvasható adatfolyamként.
            await using var stream = await response.Content.ReadAsStreamAsync(context.RequestAborted);
            // TANANYAG – 8 KB-os pufferrel, kis memóriahasználattal továbbítjuk az eseményeket.
            var buffer = new byte[8192];
            // TANANYAG – A read változó tárolja az éppen beolvasott bájtok számát.
            int read;
            // TANANYAG – Addig olvasunk a hálózati streamből, amíg el nem érkezik a végjel (0 bájt).
            while ((read = await stream.ReadAsync(buffer, context.RequestAborted)) != 0)
            {
                // TANANYAG – Csak a ténylegesen olvasott bájtokat írjuk a kliens felé, fölösleges pufferadat nélkül.
                await context.Response.Body.WriteAsync(buffer.AsMemory(0, read), context.RequestAborted);
                // TANANYAG – A FlushAsync azonnal kiküldi az aktuális SSE-részletet, ezért a felhasználó élő progresszt lát.
                await context.Response.Body.FlushAsync(context.RequestAborted);
            }
        }
        // TANANYAG – A kliens bezárhatja a böngészőt; RequestAborted esetén ez rendes lemondás, nem belső hiba.
        catch (OperationCanceledException) when (context.RequestAborted.IsCancellationRequested)
        {
            // A kliens bezárta a kapcsolatot, nem API hiba.
        }
        // TANANYAG – A hálózat megszakadása itt is elkülöníthető az AI által visszaadott általános hibáktól.
        catch (HttpRequestException ex)
        {
            // TANANYAG – A naplóba az érintett stream végpont kerül a titkos fejlécek nélkül.
            logger.LogWarning(ex, "OmegaAI SSE kapcsolat hiba: {Path}", path);
            // TANANYAG – Ha már elküldtük a fejlécet, nem tudunk új hibastátuszt beállítani.
            if (!context.Response.HasStarted)
            {
                // TANANYAG – Ha még nem indult az eseményfolyam, HTTP 503-mal jelezhető az upstream kapcsolat hibája.
                context.Response.StatusCode = 503;
                // TANANYAG – A kliens gépileg feldolgozható JSON hibaüzenetet kap.
                await context.Response.WriteAsJsonAsync(new { error = "OmegaAI nem érhető el." });
            }
        }
    }

    // TANANYAG – Egyetlen rendszerállapot-hívásban ellenőrzi az OmegaAI futását és alap-előfeltételeit.
    public async Task<IResult> OmegaStatusAsync(HttpContext context, ClientOptions client)
    {
        try
        {
            // /health/live önmagában nem bizonyítja, hogy a modellek ténylegesen inferálnak.
            // TANANYAG – A /health/live csak azt mutatja, él-e az OmegaAI HTTP-szervere.
            using var live = await SendRawAsync(HttpMethod.Get, "/health/live", client, null, context.RequestAborted);
            // TANANYAG – A /v1/health/ready a modellfájlok és helyi függőségek elérhetőségét ellenőrzi.
            using var ready = await SendRawAsync(HttpMethod.Get, "/v1/health/ready", client, null, context.RequestAborted);
            // TANANYAG – Mindkét ellenőrzésnek sikeres HTTP-kódot kell adnia a ready jelzéshez.
            if (!live.IsSuccessStatusCode || !ready.IsSuccessStatusCode)
                // TANANYAG – A részleges üzemzavar esetén jelezzük, melyik egészségellenőrzés sikerült.
                return Results.Json(new { omegaAiOnline = live.IsSuccessStatusCode,
                    // TANANYAG – Fontos oktatási megkülönböztetés: ez nem valódi AI-inferencia teszt.
                    configured = ready.IsSuccessStatusCode, note = "Nem történt valódi AI-inferencia." }, statusCode: 503);
            // TANANYAG – A JSON-választ strukturált JsonDocumentté alakítjuk az egyes mezők kiolvasásához.
            using var parsed = JsonDocument.Parse(await ready.Content.ReadAsStringAsync(context.RequestAborted));
            // TANANYAG – A feldolgozott JSON gyökérelemére mutat a rövid r változó.
            var r = parsed.RootElement;
            // TANANYAG – A lokális Flag függvény óvatosan ellenőrzi: létezik-e a tulajdonság, és true-e a logikai értéke.
            bool Flag(string n) => r.TryGetProperty(n, out var p) && p.ValueKind == JsonValueKind.True;
            // TANANYAG – A saját status JSON-t mi építjük, mert egységes API-formátumot szeretnénk a klienseknek.
            return Results.Json(new {
                // TANANYAG – Az omegaAiOnline külön az elérhetőséget, a modelAvailability a komponensek meglétét jelzi.
                omegaAiOnline = true, omegaAiStatus = "running", modelAvailability = new {
                    // TANANYAG – A Whisper és pyannote fájljainak megléte önmagában még nem bizonyít sikeres felismerést.
                    whisper = Flag("whisper_files"), pyannote = Flag("pyannote_files"),
                    // TANANYAG – Az Ollama Qwen és FFmpeg elérhetőségi zászlóit is átadjuk.
                    qwen = Flag("qwen_available"), ffmpeg = Flag("ffmpeg") },
                // TANANYAG – A ready csak akkor igaz, ha mind a négy alapfeltétel teljesül.
                ready = Flag("whisper_files") && Flag("pyannote_files") && Flag("qwen_available") && Flag("ffmpeg"),
                // TANANYAG – A note figyelmezteti a hívót: teljes MP3-tesztet külön kell végrehajtani.
                note = "Fájl- és API-ellenőrzés, nem valódi hangfeldolgozási próba."
            });
        }
        // TANANYAG – Az OmegaAI elérhetetlenségét 503-as JSON válasszá alakítjuk.
        catch (HttpRequestException) { return Results.Json(new { omegaAiOnline = false, ready = false, error = "OmegaAI nem fut." }, statusCode: 503); }
        // TANANYAG – JSON/parsing vagy konfigurációs hiba esetére külön kivételkezelő ág van.
        catch (Exception ex) when (ex is JsonException or InvalidOperationException)
        // TANANYAG – A belső részleteket naplózzuk, az ügyfélnek rövid, 502 Bad Gateway üzenetet adunk.
        { logger.LogWarning(ex, "OmegaAI állapotlekérdezés hiba"); return Results.Json(new { omegaAiOnline = false, error = "Hibás OmegaAI válasz." }, statusCode: 502); }
    }

    // TANANYAG – A QueueStatusAsync központi munkasor statisztikát ad, de nem adja ki más tenantok munkáit.
    public async Task<IResult> QueueStatusAsync(HttpContext context, ClientOptions client)
    {
        try
        {
            // TANANYAG – A helyi /v1/queue endpoint lekérdezése egyszeri HTTP GET-tel történik.
            using var response = await SendRawAsync(HttpMethod.Get, "/v1/queue", client, null, context.RequestAborted);
            // TANANYAG – Sikertelen upstream válasznál megtartjuk az eredeti státuszkódot.
            if (!response.IsSuccessStatusCode)
                // TANANYAG – A válasz hibáját a szerveroldali API közvetlenül továbbítja.
                return Results.Content(await response.Content.ReadAsStringAsync(context.RequestAborted), "application/json", statusCode: (int)response.StatusCode);
            // TANANYAG – A munkasor JSON-válaszát JsonDocumenttel feldolgozzuk.
            using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync(context.RequestAborted));
            // TANANYAG – A data a kapott JSON gyökér, amelyben a számlálók találhatók.
            var data = doc.RootElement;
            // Szándékosan kihagyjuk a waiting_ids és active_job_id adatokat: ezek más alkalmazások feladatai.
            // TANANYAG – A GetInt biztonságosan 0-t ad hiányzó vagy hibás számláló esetén.
            int GetInt(string n) => data.TryGetProperty(n, out var p) && p.TryGetInt32(out var value) ? value : 0;
            // TANANYAG – Csak az aktív és sorban álló munkák darabszámát adjuk vissza; feladatazonosítókat nem.
            return Results.Json(new { activeJobs = GetInt("active_jobs"), waitingJobs = GetInt("queued_jobs"),
                // TANANYAG – A kapacitás adatait is láthatják a kliensek, hogy megjeleníthessék a várakozást.
                capacity = GetInt("capacity"), maxParallelAudioJobs = GetInt("max_parallel_audio_jobs") });
        }
        // TANANYAG – Ha a munkasor nem elérhető, a kliens 503-as válaszból tudhatja, hogy újrapróbálkozás kell.
        catch (HttpRequestException) { return Results.Json(new { error = "OmegaAI nem érhető el." }, statusCode: 503); }
    }
}
